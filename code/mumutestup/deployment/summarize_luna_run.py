#!/usr/bin/env python3
"""Summarize recorded MuMu/Luna evidence without running tests or calling models.

Usage: python summarize_luna_run.py --run-dir /absolute/path/to/luna-run
Only summary.json and summary.md are written. A running batch can be summarized
as a snapshot; absent evidence stays unknown rather than becoming a test failure.
An accepted-retries.json file may explicitly replace selected sample records;
identity, commits, and both record hashes are checked before accepting it.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import time


MODEL_STATUSES = {'pass', 'compile_error', 'run_fail', 'coverage_loss',
                  'mutation_loss', 'coverage_and_mutation_loss'}


def load_json(path, warnings, required=False):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        if required:
            raise ValueError(f'Cannot read required JSON {path}: {exc}') from exc
        if path.exists():
            warnings.append(f'无法读取 {path.name}：{type(exc).__name__}')
        return None


def timestamp(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()
        except ValueError:
            pass
    return None


def number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def iteration_number(phase):
    match = re.search(r'(?:^|/)iteration_(\d+)(?:/|$)', phase.get('iteration_directory', ''))
    return int(match.group(1)) if match else None


def phase_verdict(phase):
    sure = phase.get('surefire') or {}
    commands = phase.get('maven_commands') or []
    codes = [command.get('returncode') for command in commands]
    fresh_target = any(r.get('fresh') is True and r.get('matched', 0) > 0
                       for r in sure.get('reports', []))
    passed = sure.get('passed', 0)
    failed = sure.get('failed', 0)
    matched = sure.get('matched', 0)
    if (fresh_target and passed > 0 and failed == 0 and matched > 0
            and codes and all(type(code) is int and code == 0 for code in codes)
            and not phase.get('exception')):
        verdict = 'verified_pass'
    elif fresh_target and failed > 0:
        verdict = 'verified_failure'
    elif phase.get('upstream_status') in {'COMPILE_ERROR', 'RUN_FAIL'} and any(
            type(code) is int and code != 0 for code in codes):
        verdict = 'verified_failure'
    else:
        verdict = 'not_verified'
    return {'iteration': iteration_number(phase), 'verdict': verdict,
            'maven_returncodes': codes, 'fresh_target_report': fresh_target,
            'target_class': sure.get('target_class'), 'target_method': sure.get('target_method'),
            'matched': matched, 'passed': passed, 'failed': failed,
            'skipped': sure.get('skipped', 0),
            'upstream_status': phase.get('upstream_status'),
            'iteration_directory': phase.get('iteration_directory'),
            'installed_sha256': phase.get('installed_sha256')}


def target_execution(record):
    result = record.get('result') or {}
    selected_iteration = result.get('iteration')
    phases = [p for p in record.get('phase_evidence', []) if p.get('phase') == '_run_jacoco']
    selected = [p for p in phases if selected_iteration is not None
                and iteration_number(p) == selected_iteration]
    verdicts = {phase_verdict(p)['verdict'] for p in selected}
    if 'verified_pass' in verdicts and 'verified_failure' in verdicts:
        verdict = 'conflicting_evidence'
    elif 'verified_pass' in verdicts:
        verdict = 'verified_pass'
    elif 'verified_failure' in verdicts:
        verdict = 'verified_failure'
    else:
        verdict = 'not_verified'
    return {'selected_result_iteration': selected_iteration, 'verdict': verdict,
            'verified_pass': True if verdict == 'verified_pass' else (
                False if verdict == 'verified_failure' else None),
            'selected_phases': selected,
            'all_attempts': [phase_verdict(p) for p in phases],
            'any_attempt_verified_pass': any(phase_verdict(p)['verdict'] == 'verified_pass' for p in phases)}


def summarize_sample(root, project, index, sample_id, project_status, now, warnings, record_override=None):
    path = root / 'projects' / project / 'samples' / f'{index:04d}.json'
    record = (load_json(path, warnings) or {}) if record_override is None else record_override
    state = record.get('state', 'unreadable' if path.exists() else 'not_started')
    if record.get('index', index) != index or record.get('project', project) != project:
        warnings.append(f'{project}:{index} 的记录身份与 manifest 不一致。')
    if sample_id is not None and record.get('sample_id', sample_id) != sample_id:
        warnings.append(f'{project}:{index} 的样本 ID 与 manifest 不一致。')
    elapsed = number(record.get('elapsed_seconds'))
    elapsed_source = 'recorded' if elapsed is not None else None
    if elapsed is None and timestamp(record.get('started_at')) is not None:
        end = timestamp(record.get('finished_at') or record.get('interrupted_at'))
        if end is None and state == 'running':
            end = now
            elapsed_source = 'elapsed_so_far'
        elif end is not None:
            elapsed_source = 'derived_from_record_timestamps'
        if end is not None:
            elapsed = round(max(0, end - timestamp(record['started_at'])), 3)
    result = record.get('result') or {}
    test_result = result.get('test_result') or {}
    test_case = test_result.get('test_case') or {}
    mumu_status = record.get('test_status')
    threshold_pass = (mumu_status == 'pass') if state == 'finished' and mumu_status in MODEL_STATUSES else None
    if mumu_status in MODEL_STATUSES and test_result.get('status') not in (None, mumu_status):
        warnings.append(f'{sample_id} 的顶层状态与返回结果状态不一致。')
    return {'project': project, 'index': index, 'sample_id': sample_id,
            'state': state, 'project_status': project_status, 'record_path': str(path),
            'started_at': record.get('started_at'), 'finished_at': record.get('finished_at'),
            'elapsed_seconds': elapsed, 'elapsed_source': elapsed_source,
            'aCommit': record.get('aCommit'), 'bCommit': record.get('bCommit'),
            'mumu_status': mumu_status, 'mumu_threshold_pass': threshold_pass,
            'target_execution': target_execution(record),
            'result': {'iteration': result.get('iteration'), 'score': result.get('score'),
                       'status': test_result.get('status'), 'test_name': test_case.get('name'),
                       'coverage_info': test_case.get('coverage_info'),
                       'mutation_info': test_case.get('mutation_info'),
                       'coverage_loss_details': test_result.get('coverage_loss_details'),
                       'mutation_loss_details': test_result.get('mutation_loss_details'),
                       'error_message': test_result.get('error_message')},
            'execution_guard_violations': record.get('execution_guard_violations', []),
            'harness_traceback': record.get('traceback'),
            'backend_fatal_marker': record.get('backend_fatal_marker'),
            'java_selection': record.get('java_selection'),
            'focal_metadata': record.get('focal_metadata')}


def summarize_model(audit_path, warmup_path, now, warnings):
    warmup = load_json(warmup_path, warnings) or {}
    warmup_rows = warmup.get('results', [])
    excluded = {(row.get('response') or {}).get('id') for row in warmup_rows}
    excluded.discard(None)
    verified_exclusion = bool(warmup_rows) and len(excluded) == len(warmup_rows)
    if not verified_exclusion:
        warnings.append('warmup 请求 ID 不完整；模型统计可能含未能识别的预热请求。')
    grouped, bridge_fatals = {}, []
    if not audit_path.exists():
        warnings.append('没有 bridge-audit.jsonl；模型耗时和 token 无法统计。')
    else:
        with audit_path.open(encoding='utf-8') as handle:
            for line_number, line in enumerate(handle, 1):
                try:
                    event = json.loads(line)
                except ValueError:
                    warnings.append(f'桥接日志第 {line_number} 行尚未写完或不是完整 JSON，已跳过。')
                    continue
                if not isinstance(event, dict):
                    continue
                request_id = event.get('request_id')
                if request_id in excluded:
                    continue
                if event.get('event') == 'fatal':
                    bridge_fatals.append(event)
                if request_id and event.get('event') in {'request', 'response', 'request_failed', 'fatal'}:
                    grouped.setdefault(request_id, []).append(event)
    requests = []
    for request_id, events in grouped.items():
        starts = [e for e in events if e.get('event') == 'request']
        responses = [e for e in events if e.get('event') == 'response']
        failures = [e for e in events if e.get('event') in {'request_failed', 'fatal'}]
        start = timestamp(starts[0].get('timestamp')) if starts else None
        terminal = failures[-1] if failures else responses[-1] if responses else {}
        status = 'failed' if failures else 'response_logged' if responses else 'unfinished'
        duration = number(terminal.get('duration_seconds'))
        duration_source = 'reported' if duration is not None else None
        end = timestamp(terminal.get('timestamp'))
        if duration is None and start is not None and end is not None:
            duration, duration_source = round(max(0, end - start), 6), 'audit_timestamps'
        usage_events = [e for e in events if isinstance(e.get('token_usage'), dict)
                        and (e['token_usage'].get('total') or e['token_usage'].get('last'))]
        usage = usage_events[-1]['token_usage'] if usage_events else {}
        totals = usage.get('total') or usage.get('last') or {}
        tokens = {key: number(totals.get(field)) for key, field in (
            ('input', 'inputTokens'), ('output', 'outputTokens'), ('total', 'totalTokens'),
            ('cached_input', 'cachedInputTokens'), ('reasoning_output', 'reasoningOutputTokens'))}
        requests.append({'request_id': request_id, 'status': status,
                         'started_at_epoch': start, 'ended_at_epoch': end,
                         'duration_seconds': duration, 'duration_source': duration_source,
                         'elapsed_so_far_seconds': round(max(0, now - start), 3)
                         if status == 'unfinished' and start is not None else None,
                         'tokens': tokens, 'token_usage_reported': bool(totals),
                         'error_code': terminal.get('code') if failures else None,
                         'thread_id': terminal.get('thread_id'), 'token_usage_raw': usage})
    requests.sort(key=lambda r: (r['started_at_epoch'] or 0, r['request_id']))
    totals, known_counts = {}, {}
    for key in ('input', 'output', 'total', 'cached_input', 'reasoning_output'):
        values = [r['tokens'][key] for r in requests if r['tokens'][key] is not None]
        totals[key] = sum(values) if values else None
        known_counts[key] = len(values)
    durations = [r['duration_seconds'] for r in requests if r['duration_seconds'] is not None]
    return {'audit_path': str(audit_path), 'warmup_path': str(warmup_path),
            'warmup_exclusion_verified': verified_exclusion,
            'excluded_warmup_request_ids': sorted(excluded),
            'request_count': len(requests), 'status_counts': dict(Counter(r['status'] for r in requests)),
            'duration_sum_seconds': round(sum(durations), 6) if durations else None,
            'duration_known_requests': len(durations),
            'reported_token_totals': totals, 'token_known_request_counts': known_counts,
            'token_unknown_request_count': sum(not r['token_usage_reported'] for r in requests),
            'requests': requests, 'bridge_fatals': bridge_fatals,
            'accounting_note': '每个 request_id 只计一次，失败请求保留；只排除 warmup 中明确记录的 ID。耗时为并发请求之和，并非实验墙钟时间；缺失 token 不按零补齐。'}


def manifest_identity(manifest, project, index):
    matches = []
    for row in manifest['datasets']:
        if row['project'] != project:
            continue
        indices, ids = row['selected_indices'], row.get('sample_ids', [])
        if len(indices) != len(ids):
            raise ValueError(f'Manifest identity is incomplete: {project}')
        matches.extend(ids[offset] for offset, selected in enumerate(indices) if selected == index)
    if len(matches) != 1:
        raise ValueError(f'Manifest must select exactly one {project}:{index}')
    return matches[0]


def checked_record(path, expected_hash, identity):
    raw = path.read_bytes()
    if not isinstance(expected_hash, str) or not re.fullmatch('[0-9a-fA-F]{64}', expected_hash):
        raise ValueError(f'Missing or invalid expected SHA-256: {path}')
    if hashlib.sha256(raw).hexdigest() != expected_hash.lower():
        raise ValueError(f'Record hash mismatch: {path}')
    record = json.loads(raw)
    if any(record.get(key) != value for key, value in identity.items()):
        raise ValueError(f'Record identity mismatch: {path}')
    return record


def apply_accepted_retries(root, manifest, samples, now, warnings):
    path = root / 'accepted-retries.json'
    if not path.exists():
        return [], []
    acceptance = load_json(path, warnings, required=True)
    replacements = acceptance.get('replacements')
    if not isinstance(replacements, list):
        raise ValueError('accepted-retries.json requires a replacements list')
    positions = {(sample['project'], sample['index']): offset for offset, sample in enumerate(samples)}
    accepted, end_times, seen = [], [], set()
    for entry in replacements:
        project, index, sample_id = entry['project'], entry['index'], entry['sample_id']
        key = (project, index)
        if type(index) is not int or key not in positions or key in seen:
            raise ValueError(f'Invalid or repeated accepted replacement: {key}')
        seen.add(key)
        if not isinstance(entry.get('reason'), str) or not entry['reason'].strip():
            raise ValueError(f'Accepted replacement must state its reason: {key}')
        retry_root = Path(entry['retry_run_dir'])
        retry_root = (retry_root if retry_root.is_absolute() else root / retry_root).resolve()
        if retry_root == root:
            raise ValueError('A retry must use a separate run directory')
        retry_manifest = load_json(retry_root / 'run-manifest.json', warnings, required=True)
        for selected_manifest in (manifest, retry_manifest):
            if manifest_identity(selected_manifest, project, index) != sample_id:
                raise ValueError(f'Accepted replacement differs from manifest identity: {key}')
        identity = {'project': project, 'index': index, 'sample_id': sample_id}
        relative = Path('projects') / project / 'samples' / f'{index:04d}.json'
        original = checked_record(root / relative, entry['original_record_sha256'], identity)
        replacement = checked_record(retry_root / relative, entry['replacement_record_sha256'], identity)
        for commit in ('aCommit', 'bCommit'):
            if not isinstance(original.get(commit), str) or not original[commit] or replacement.get(commit) != original[commit]:
                raise ValueError(f'Accepted replacement has different or missing {commit}: {key}')
        if replacement.get('state') != 'finished':
            raise ValueError(f'Accepted replacement is not finished: {key}')
        retry_status = load_json(retry_root / 'status.json', warnings, required=True)
        retry_project = next((p.get('state') for p in retry_status.get('completed_projects', [])
                              if p.get('project') == project), None)
        updated = summarize_sample(retry_root, project, index, sample_id, retry_project, now, warnings,
                                   record_override=replacement)
        original_attempt = summarize_sample(root, project, index, sample_id,
                                            samples[positions[key]]['project_status'], now, warnings,
                                            record_override=original)
        original_attempt['record_sha256'] = entry['original_record_sha256'].lower()
        verified = {**entry, 'retry_run_dir': str(retry_root), 'aCommit': original['aCommit'],
                    'bCommit': original['bCommit'], 'verified': True}
        updated.update(original_attempt=original_attempt, accepted_retry=verified,
                       record_sha256=entry['replacement_record_sha256'].lower())
        samples[positions[key]] = updated
        accepted.append(verified)
        for value in (retry_status.get('finished_at'), retry_status.get('stopped_at'), replacement.get('finished_at')):
            if timestamp(value) is not None:
                end_times.append(value)
    return accepted, end_times


def build_summary(root, audit_path=None, warmup_path=None):
    root = root.resolve()
    warnings = []
    now = time.time()
    manifest = load_json(root / 'run-manifest.json', warnings, required=True)
    status = load_json(root / 'status.json', warnings) or {}
    projects = {r.get('project'): r for r in status.get('completed_projects', [])}
    samples, seen = [], set()
    for dataset in manifest['datasets']:
        project = dataset['project']
        indices, ids = dataset['selected_indices'], dataset.get('sample_ids', [])
        if len(indices) != len(ids):
            warnings.append(f'{project} 的 manifest 索引与 ID 数量不一致。')
        for offset, index in enumerate(indices):
            key = (project, index)
            if key in seen:
                raise ValueError(f'Duplicate manifest selection: {key}')
            seen.add(key)
            sample_id = ids[offset] if offset < len(ids) else None
            samples.append(summarize_sample(root, project, index, sample_id,
                                           projects.get(project, {}).get('state'), now, warnings))
    if manifest.get('selected_count') != len(samples):
        warnings.append('manifest.selected_count 与选中索引总数不一致，以明确索引为准。')
    accepted_retries, retry_end_times = apply_accepted_retries(root, manifest, samples, now, warnings)
    primary_end = status.get('finished_at') or status.get('stopped_at')
    ends = [value for value in [primary_end, *retry_end_times] if timestamp(value) is not None]
    combined_end = max(ends, key=timestamp) if ends else None
    counts = {'selected': len(samples),
              'sample_states': dict(Counter(s['state'] for s in samples)),
              'mumu_statuses': dict(Counter(s['mumu_status'] or 'no_result' for s in samples)),
              'mumu_threshold_pass': sum(s['mumu_threshold_pass'] is True for s in samples),
              'target_execution': dict(Counter(s['target_execution']['verdict'] for s in samples))}
    model = summarize_model(audit_path or root / 'bridge-audit.jsonl',
                            warmup_path or root / 'bridge-warmup.json', now, warnings)
    for sample in samples:
        if sample['mumu_threshold_pass'] is True and sample['target_execution']['verdict'] != 'verified_pass':
            warnings.append(f'{sample["sample_id"]} 被 MuMu 判为 pass，但返回轮次缺少完整执行通过证据。')
    return {'schema_version': 2, 'generated_at': datetime.fromtimestamp(now, timezone.utc).isoformat(),
            'run_dir': str(root), 'run_state': status.get('state', 'not_started'),
            'run_started_at': status.get('started_at'),
            'run_finished_at': combined_end, 'primary_run_finished_at': primary_end,
            'manifest_sha256': hashlib.sha256((root / 'run-manifest.json').read_bytes()).hexdigest(),
            'runtime': manifest.get('runtime'), 'workers': manifest.get('workers'),
            'counts': counts, 'samples': samples, 'project_results': status.get('completed_projects', []),
            'model': model, 'warnings': warnings, 'accepted_retries': accepted_retries,
            'accepted_retry_count': len(accepted_retries),
            'definitions': {
                'target_test_pass': '仅对返回结果 result.iteration 对应的 JaCoCo 阶段判定：新鲜 Surefire 报告命中目标测试，至少一个未跳过用例通过、没有目标失败，且该阶段所有 Maven 命令返回码均为 0。',
                'mumu_threshold_pass': '样本 finished 且原方法 test_status=pass；不以测试执行通过替代覆盖与变异指标判定。',
                'missing_evidence': '运行中、未启动、后端中断和缺证据不自动算作测试失败。',
                'phase_evidence': '读取运行时保存的证据，不重新读取可能被后续样本覆盖的工作目录 XML。',
                'accepted_retry': '仅采用 accepted-retries.json 明确指定且身份、commit 和双记录哈希核对成功的已完成补跑；原尝试保留在 original_attempt，模型总量仍读主运行桥接日志。'}}


def cell(value):
    return str(value if value is not None else '—').replace('|', '\\|').replace('\n', ' ')


def metric(value):
    return f'{value:.1f}' if number(value) is not None else '—'


def render_markdown(summary):
    counts, model = summary['counts'], summary['model']
    states = counts['sample_states']
    target = counts['target_execution']
    model_states = model['status_counts']
    started, finished = timestamp(summary['run_started_at']), timestamp(summary['run_finished_at'])
    primary_finished = timestamp(summary.get('primary_run_finished_at'))
    elapsed_note = (f"从正式启动到结果完成共 {(finished - started) / 60:.1f} 分钟（含检查、修复与已接受的补跑）。"
                    if started is not None and finished is not None else '实验仍在运行，本页是当前快照。')
    if started is not None and primary_finished is not None:
        elapsed_note = f"主批次运行 {(primary_finished - started) / 60:.1f} 分钟。" + elapsed_note
    lines = [f"# Luna 小批量结果（{summary['run_state']}）", '',
             f"按 manifest 选中 {counts['selected']} 条。已完成 {states.get('finished', 0)} 条，"
             f"运行中 {states.get('running', 0)} 条，未启动 {states.get('not_started', 0)} 条，"
             f"中断 {states.get('interrupted', 0)} 条。", '',
             elapsed_note, '',
             f"已接受 {summary['accepted_retry_count']} 条有明确记录的补跑；原尝试保留在 summary.json，模型开销包含原尝试和补跑。", '',
             f"**返回测试实际通过 {target.get('verified_pass', 0)} 条；MuMu 指标达标 {counts['mumu_threshold_pass']} 条。** "
             '前者要求新鲜 Surefire 目标测试通过且 Maven 返回 0；后者沿用原方法的覆盖和变异判定。', '',
             f"正式模型请求 {model['request_count']} 次：返回 {model_states.get('response_logged', 0)} 次，"
             f"失败 {model_states.get('failed', 0)} 次，未结束 {model_states.get('unfinished', 0)} 次。"
             f"已排除 {len(model['excluded_warmup_request_ids'])} 条明确的 warmup 请求。", '',
             f"请求累计耗时 {metric(model['duration_sum_seconds'])} 秒（并发相加）；"
             f"已报告 token {cell(model['reported_token_totals']['total'])}，"
             f"另有 {model['token_unknown_request_count']} 次请求未报告 token。", '',
             '| 样本 | 状态 | 耗时/秒 | 返回测试实际通过 | MuMu 判定 | 行/分支/变异 % |',
             '| --- | --- | ---: | --- | --- | --- |']
    verdicts = {'verified_pass': '通过', 'verified_failure': '未通过',
                'not_verified': '无完成证据', 'conflicting_evidence': '证据冲突'}
    translations = {'pass': '指标达标', 'compile_error': '编译错误', 'run_fail': '执行失败',
                    'coverage_loss': '覆盖未达标', 'mutation_loss': '变异未达标',
                    'coverage_and_mutation_loss': '覆盖、变异未达标',
                    'harness_error': '实验程序错误', 'backend_unavailable': '后端中断'}
    for sample in summary['samples']:
        coverage = sample['result']['coverage_info'] or {}
        mutation = sample['result']['mutation_info'] or {}
        scores = '/'.join(metric(v) for v in (coverage.get('line_coverage_percentage'),
                                             coverage.get('branch_coverage_percentage'), mutation.get('kill_percentage')))
        elapsed = metric(sample['elapsed_seconds']) + ('+' if sample['elapsed_source'] == 'elapsed_so_far' else '')
        lines.append('| ' + ' | '.join(map(cell, (sample['sample_id'] or f"{sample['project']}[index={sample['index']}]",
                    sample['state'], elapsed, verdicts[sample['target_execution']['verdict']],
                    translations.get(sample['mumu_status'], sample['mumu_status'] or '—'), scores))) + ' |')
    lines += ['', '“返回测试”按方法选出的最佳轮次核对，不拿最后一次尝试代替。耗时带 + 表示仍在运行；— 表示未记录或不适用。']
    if summary['warnings']:
        lines += ['', '**待核对：**'] + ['- ' + warning for warning in summary['warnings']]
    lines += ['', f"快照时间：{summary['generated_at']}。完整证据和逐请求统计见 summary.json。", '']
    return '\n'.join(lines)


def write_atomic(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f'.{os.getpid()}.tmp')
    try:
        temporary.write_text(content, encoding='utf-8')
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--audit-file', type=Path)
    parser.add_argument('--warmup-file', type=Path)
    args = parser.parse_args()
    summary = build_summary(args.run_dir, args.audit_file, args.warmup_file)
    output = (args.output_dir or args.run_dir).resolve()
    write_atomic(output / 'summary.json', json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    write_atomic(output / 'summary.md', render_markdown(summary))
    print(json.dumps({'summary_json': str(output / 'summary.json'),
                      'summary_md': str(output / 'summary.md'), 'counts': summary['counts']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
