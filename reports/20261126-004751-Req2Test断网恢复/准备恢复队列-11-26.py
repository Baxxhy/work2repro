"""Prepare the missing Medium tasks in a new run and retain the original results."""
import collections
import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

WORK = Path('/root/Baxxhy/work2')
RUNS = WORK / 'reproductions/req2test'
SOURCE = RUNS / 'req2test-medium-full-20261123'
RUN = RUNS / 'req2test-medium-recovery313-20261126'
USER = Path('/root/lby-docker/req2test/user')
OUTPUT = USER / 'runs' / RUN.name
ARCHIVE = WORK / 'diagnostics/20261126-004751-Req2Test断网恢复'
MANIFEST = WORK / 'diagnostics/20261123-152815-Req2Test全量Medium/全量任务-11-23.csv'
OLD_MERGE = WORK / 'diagnostics/20261123-172610-Medium断网任务恢复/merge.py'


def read_json(path):
    return json.loads(path.read_text())


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError(f'Expected one matching source block: {old}')
    return text.replace(old, new)


def prepare():
    if RUN.exists() or OUTPUT.exists():
        raise FileExistsError('Recovery run already exists')
    source_state = read_json(SOURCE / 'state.json')
    source_config = read_json(SOURCE / 'frozen/config.json')
    if (source_config['model'], source_config['reasoning']) != ('gpt-6-luna', 'medium'):
        raise ValueError('Unexpected source model or effort')
    if source_config.get('req_home') != str(USER):
        raise ValueError('Unexpected source benchmark home')
    source_output = Path(source_config['req_output'])
    comparison = read_json(SOURCE / 'result_comparison.json')
    blocked = {
        key: task for key, task in source_state['tasks'].items()
        if task['gen'] == 'infra_blocked' and task['reason'] == 'network_interruption'
    }
    blocked_ids = {task['id'] for task in blocked.values()}
    with MANIFEST.open() as stream:
        all_ids = [row['instance_id'] for row in csv.DictReader(stream)]
    if (len(blocked) != len(blocked_ids) or len(blocked_ids) != 313
            or len(comparison) != 1738 or blocked_ids.intersection(comparison)
            or len(all_ids) != 2051 or set(all_ids) != blocked_ids.union(comparison)):
        raise ValueError('Unexpected source coverage')
    for task in blocked.values():
        attempted = Path(task['prediction']).parent.parent
        if any(attempted.glob('*/predictions.jsonl')):
            raise ValueError(f'Existing prediction for {task["id"]}')
        if not (source_output / 'manifests/items' / (task['safe'] + '.jsonl')).is_file():
            raise FileNotFoundError(task['id'])

    canary = next(key for key, task in blocked.items() if task['project'] == 'python-docx')
    tasks = {
        key: {**{field: task[field] for field in ('id', 'safe', 'project', 'benchmark')},
              'gen': 'pending', 'evaluation': 'pending', 'gen_attempts': 0}
        for key, task in blocked.items()
    }
    control_source = (SOURCE / 'control/supervise_diagnostic.py').read_text()
    control_source = replace_once(
        control_source,
        '    while True:\n        with LOCK:',
        '''    def proxy_listening():
        try:
            with socket.create_connection(('127.0.0.1', 7890), timeout=2):
                return True
        except OSError:
            return False

    while True:
        proxy_ok = proxy_listening()
        with LOCK:''',
    )
    control_source = replace_once(
        control_source,
        "                if not S['block'] and time.time()>=S['cooldown_until']:",
        """                recent_failures = sum(time.time() - t < 120 for t in S.get('network_error_times', []))
                if proxy_ok and recent_failures < 8 and not S['block'] and time.time()>=S['cooldown_until']:""",
    )
    control_source = replace_once(
        control_source,
        """                        if t['gen']!='pending' or time.time()<t.get('not_before',0):continue""",
        """                        if k != CFG['canary_task_key'] and not (ROOT/'release-generation').is_file():continue
                        if t['gen']!='pending' or time.time()<t.get('not_before',0):continue""",
    )
    control_source = replace_once(
        control_source,
        """'--instances',str(ids),'--split','eval','--project',project,'--workers',"1",""",
        """'--instances',str(ids),'--split','eval','--project',project,
              '--workers', '10' if project == 'prestashop' else '1',""",
    )
    control_source = replace_once(
        control_source, 'summary=dict(total=2051,reused=0,new_total=2051,',
        'summary=dict(total=len(S["tasks"]),reused=0,new_total=len(S["tasks"]),proxy_listening=proxy_ok,',
    )
    merge_source = replace_once(OLD_MERGE.read_text(), "d/'全量任务-11-23.csv'",
                                f'Path({str(MANIFEST)!r})')
    merge_source = merge_source.replace('req2test-medium-network260-1123', RUN.name)
    compile(control_source, 'supervise_diagnostic.py', 'exec')
    compile(merge_source, '结算全量-11-26.py', 'exec')

    RUN.mkdir(mode=0o700)
    (RUN / 'jobs').mkdir()
    shutil.copytree(SOURCE / 'control', RUN / 'control', ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copytree(SOURCE / 'frozen', RUN / 'frozen')
    for folder in (OUTPUT, OUTPUT / 'input', OUTPUT / 'generation', OUTPUT / 'manifests', OUTPUT / 'manifests/items'):
        folder.mkdir()
    os.chown(OUTPUT / 'generation', 1001, 1001)
    shutil.copyfile(source_output / 'agent.py', OUTPUT / 'agent.py')
    for task in blocked.values():
        relative = Path('manifests/items') / (task['safe'] + '.jsonl')
        shutil.copyfile(source_output / relative, OUTPUT / relative)
    config = dict(source_config, run_id=RUN.name, req_run_id=RUN.name,
                  req_output=str(OUTPUT), gateway_port=18246, canary_task_key=canary)
    write_json(RUN / 'frozen/config.json', config)
    write_json(RUN / 'state.json', dict(tasks=tasks, jobs={}, groups={}, block=None, cooldown_until=0,
               generation_cap=8, evaluation_cpu_budget=8, request_retries=0, events_429=0,
               generation_completions=[], started=time.time(), network_error_times=[]))
    write_json(RUN / 'recovery-ids.json', sorted(blocked_ids))
    (RUN / 'control/supervise_diagnostic.py').write_text(control_source)
    (ARCHIVE / '结算全量-11-26.py').write_text(merge_source)
    write_json(ARCHIVE / '恢复清单核验-11-26.json', dict(
        source_state_sha256=hashlib.sha256((SOURCE / 'state.json').read_bytes()).hexdigest(),
        source_result_sha256=hashlib.sha256((SOURCE / 'result_comparison.json').read_bytes()).hexdigest(),
        recovered_ids=sorted(blocked_ids), projects=dict(collections.Counter(t['project'] for t in tasks.values())),
        canary=tasks[canary]['id'], source_executable_rows=len(comparison)))


def launch():
    source_command = read_json(SOURCE / 'service-command.json')
    command = [part.replace(SOURCE.name, RUN.name) for part in source_command]
    write_json(RUN / 'service-command.json', command)
    subprocess.run(command, check=True)


if __name__ == '__main__':
    prepare()
    launch()
