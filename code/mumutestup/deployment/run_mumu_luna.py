#!/usr/bin/env python3
"""Fresh MuMuTestUp batch using the local Codex app-server text adapter.

The original runner retains the execution guards and sample selection. This
wrapper only adds backend provenance and fatal-backend interruption handling.
"""
import argparse
import importlib
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import urllib.request

import run_mumu as original

_original_preflight = original.preflight
_original_worker = original.worker
_original_process_pool_executor = original.ProcessPoolExecutor


def project_process_pool(*args, **kwargs):
    """Retire each worker after one project, keeping imported state isolated."""
    kwargs['max_tasks_per_child'] = 1
    return _original_process_pool_executor(*args, **kwargs)


def fatal_path():
    value = os.getenv('MUMU_LLM_FATAL_FILE')
    if not value:
        raise RuntimeError('MUMU_LLM_FATAL_FILE must name this run\'s backend stop marker')
    return Path(value)


def record_bridge_failure(reason):
    """Publish a complete stop marker without replacing the bridge's evidence."""
    marker = fatal_path()
    marker.parent.mkdir(parents=True, exist_ok=True)
    record = {
        'fatal': True, 'code': 'backend_healthcheck_failed',
        'message': reason, 'timestamp': original.now(),
        'model': 'gpt-6-luna', 'route': 'codex-app-server-text-adapter',
        'reported_by': 'run_mumu_luna',
    }
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8',
                                         dir=marker.parent, prefix='.bridge-fatal-',
                                         delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(record, handle)
            handle.write('\n')
        try:
            os.link(temporary, marker)
        except FileExistsError:
            pass
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def bridge_is_healthy():
    if fatal_path().exists():
        return False
    base = os.environ['MUMU_LUNA_BRIDGE_URL'].rstrip('/')
    health_url = base.removesuffix('/v1') + '/health'
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(health_url, timeout=3) as response:
            health = json.load(response)
        if (not isinstance(health, dict) or health.get('ok') is not True
                or health.get('model') != 'gpt-6-luna'
                or health.get('route') != 'codex-app-server-text-adapter'):
            record_bridge_failure('The local adapter health response is unavailable or inconsistent.')
            return False
    except Exception as exc:
        # Exception text can contain URLs or environment values. Record only its
        # type; the bridge's own audit retains detailed inference diagnostics.
        record_bridge_failure('Local adapter health request failed: ' + type(exc).__name__)
        return False
    return not fatal_path().exists()


def check_bridge_fatal():
    from _luna_runtime_guard import LunaBackendFatal
    if not bridge_is_healthy():
        raise LunaBackendFatal('Local model adapter stopped; see the backend fatal marker')


class GuardedIndices:
    """Keep the original selection, checking the backend before each sample."""
    def __init__(self, indices):
        self.indices = indices

    def __len__(self):
        return len(self.indices)

    def __iter__(self):
        for index in self.indices:
            check_bridge_fatal()
            yield index


def monitor_bridge(stopped):
    while not stopped.wait(5):
        if not bridge_is_healthy():
            return


def preflight(upstream, dataset_root, projects):
    marker = fatal_path()
    if marker.exists():
        raise RuntimeError(f'Backend fatal marker already exists: {marker}')
    runtime = _original_preflight(upstream, dataset_root, projects)
    from config import config
    expected_url = os.environ['MUMU_LUNA_BRIDGE_URL'].rstrip('/') + '/chat/completions'
    if runtime['model'] != 'gpt-6-luna' or runtime['api_url'] != expected_url:
        raise RuntimeError('Luna run requires gpt-6-luna at the configured local adapter')
    if runtime['temperature'] is not None:
        raise RuntimeError('Isolated Luna source was not patched: effective temperature must be None')
    if runtime['max_iterations'] != 4:
        raise RuntimeError('This small batch keeps the four-iteration MuMuTestUp budget')
    try:
        official_runner = importlib.import_module('run_complete_beam_multi')
        if not callable(getattr(official_runner, 'run_beam_with_real_execution', None)):
            raise RuntimeError('Official sample runner is missing')
    except Exception as exc:
        raise RuntimeError('Official MuMuTestUp entrypoint cannot load; repair the source/dependencies before running samples') from exc
    runtime.update(
        backend='codex-app-server-text-adapter',
        native_model_api=False,
        temperature=None,
        reasoning_effort='medium',
        speed='standard',
        request_context='new Codex thread per model request; original MuMu agent prompts',
        external_tools='disabled by adapter configuration',
        fatal_marker=str(marker),
        main_transport_max_retries=config.llm.max_retries,
        request_timeout_seconds=config.llm.timeout,
        official_entrypoint_import_verified=True,
        worker_process_policy='one fresh process per project',
        multiprocessing_start_method='spawn',
        max_tasks_per_child=1,
        provenance_note='Codex agent harness used as a text adapter, not a native bare-model API.',
    )
    return runtime


def worker(job):
    upstream, dataset_path, output, indices, _resume = job
    sys.path.insert(0, str(upstream))
    import _luna_runtime_guard as guard
    LunaBackendFatal = guard.LunaBackendFatal
    # Both copied chat clients import this function lazily inside the worker.
    guard.check_luna_fatal = check_bridge_fatal

    project = '/'.join(Path(dataset_path).parts[-3:-1])
    project_out = Path(output) / 'projects' / project
    progress_path = project_out / 'progress.json'
    stopped = threading.Event()
    monitor = None
    try:
        check_bridge_fatal()
        monitor = threading.Thread(target=monitor_bridge, args=(stopped,), daemon=True)
        monitor.start()
        guarded_job = (upstream, dataset_path, output, GuardedIndices(indices), _resume)
        try:
            result = _original_worker(guarded_job)
        except Exception:
            check_bridge_fatal()
            raise
        check_bridge_fatal()
        return result
    except LunaBackendFatal:
        progress = json.loads(progress_path.read_text()) if progress_path.exists() else {}
        interrupted = []
        finished = []
        for index in indices:
            path = project_out / 'samples' / f'{index:04d}.json'
            if not path.exists():
                continue
            record = json.loads(path.read_text())
            if record.get('state') == 'finished':
                finished.append(index)
                continue
            if record.get('state') == 'running':
                record.update(
                    state='interrupted',
                    test_status='backend_unavailable',
                    interrupted_at=original.now(),
                    backend_fatal_marker=str(fatal_path()),
                    interpretation='Backend failure interrupted this attempt; not a test-update failure.',
                )
                original.save(path, record)
                interrupted.append(index)
        report = {
            'project': project,
            'state': 'aborted_backend',
            'total': len(indices),
            'statuses': progress.get('statuses', {}),
            'finished_indices': finished,
            'interrupted_indices': interrupted,
            'not_started_indices': [i for i in indices if i not in finished and i not in interrupted],
            'backend_fatal_marker': str(fatal_path()),
            'finished_at': original.now(),
        }
        original.save(progress_path, report)
        return report
    finally:
        stopped.set()
        if monitor is not None:
            monitor.join(timeout=4)


def main():
    options = argparse.ArgumentParser(add_help=False)
    options.add_argument('--output', type=Path, required=True)
    parsed, _ = options.parse_known_args()
    original.preflight = preflight
    original.worker = worker
    # Cached log handlers and execution wrappers must not cross project jobs.
    original.ProcessPoolExecutor = project_process_pool
    original.main()
    status_path = parsed.output.resolve() / 'status.json'
    if not status_path.exists():
        return 0
    status = json.loads(status_path.read_text())
    harness_errors = []
    for project in status.get('completed_projects', []):
        if project.get('state') == 'worker_failed':
            project['worker_state'] = 'worker_failed'
            project['state'] = 'harness_error'
            project['interpretation'] = 'Experiment worker failed; not a test-update result.'
            harness_errors.append(project['project'])
    if harness_errors:
        status['harness_error_projects'] = harness_errors
    aborted = [p for p in status.get('completed_projects', []) if p.get('state') == 'aborted_backend']
    if aborted or fatal_path().exists():
        status.update(
            state='stopped_backend_error',
            backend_fatal_marker=str(fatal_path()),
            stopped_at=original.now(),
            aborted_projects=[p['project'] for p in aborted],
        )
        original.save(status_path, status)
        print(json.dumps({'state': status['state'], 'aborted_projects': status['aborted_projects']}), flush=True)
        return 3
    if harness_errors:
        status.update(state='stopped_harness_error', stopped_at=original.now())
        original.save(status_path, status)
        print(json.dumps({'state': status['state'], 'harness_error_projects': harness_errors}), flush=True)
        return 4
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
