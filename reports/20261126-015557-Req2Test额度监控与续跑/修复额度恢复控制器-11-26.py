"""Restore quota-interrupted work and keep the recovery queue waiting for quota."""
import ast
import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time

ROOT = Path('/root/Baxxhy/work2/reproductions/req2test/req2test-medium-recovery313-20261126')
UNIT = ROOT.name + '.service'
ARCHIVE = Path(__file__).resolve().parent
SUPERVISOR = ROOT / 'control/supervise_diagnostic.py'
CONTROLLER = ROOT / 'control/controller.py'


def replace_once(source, old, new):
    if source.count(old) != 1:
        raise ValueError(f'Expected source block was not unique: {old}')
    return source.replace(old, new)


def replace_atomic(path, text):
    temporary = path.with_name(path.name + '.quota-patch.tmp')
    temporary.write_text(text)
    temporary.chmod(path.stat().st_mode & 0o777)
    temporary.replace(path)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def update_supervisor(source):
    source = replace_once(source, '    def finish(j, result):', '''    def interrupted_by_quota(job, outcome):
        block = S.get('block') or {}
        if block.get('status') != 429 or outcome.get('kind') != 'infrastructure':
            return False
        if outcome.get('prediction_valid') or outcome.get('turn_completed') or job['end'] < block['time']:
            return False
        if job['id'] == block.get('job'):
            return any('usage_limit_reached' in error.get('message', '') for error in job.get('api_errors', []))
        return 'Provider authentication or quota blocked' in text(outcome['trace'])

    def requeue_quota_task(task, job):
        task.update(gen='pending', evaluation='pending', reason='provider_quota_interruption')
        job['failure_classification'] = 'provider_quota_interruption'
        event('quota_interrupted_task_requeued', key=job['key'], job=job['id'])

    restored = []
    if (S.get('block') or {}).get('status') == 429:
        for key, task in S['tasks'].items():
            if task['gen'] != 'infra_blocked':
                continue
            attempts = [job for job in S['jobs'].values() if job['phase'] == 'gen_req' and job['key'] == key]
            last = max(attempts, key=lambda job: job['start'], default=None)
            if last and interrupted_by_quota(last, last.get('generation_outcome', {})):
                requeue_quota_task(task, last)
                restored.append(task['id'])
        if restored:
            atomic(STATE, S)
            atomic(ROOT/'quota-requeued.json', sorted(restored))

    def finish(j, result):''')
    return replace_once(source,
        """                if t['gen_attempts']<2 and not S['block']:
                    t.update(gen='pending', not_before=max(time.time()+120,S['cooldown_until']))
                else:
                    t['gen']='infra_blocked'
            else:
                t['gen']='finished' if outcome['prediction_valid'] else 'generation_failed'
            t['reason']=outcome['reason']""",
        """                if interrupted_by_quota(j, outcome):
                    requeue_quota_task(t, j)
                    return
                ordinary_attempts = sum(
                    attempt['phase'] == 'gen_req' and attempt['key'] == j['key']
                    and attempt.get('failure_classification') != 'provider_quota_interruption'
                    for attempt in S['jobs'].values()
                )
                if ordinary_attempts < 2 and not S['block']:
                    t.update(gen='pending', not_before=max(time.time()+120,S['cooldown_until']))
                else:
                    t['gen']='infra_blocked'
            else:
                t['gen']='finished' if outcome['prediction_valid'] else 'generation_failed'
            t['reason']=outcome['reason']""")


def update_controller(source):
    source = replace_once(source, """    if len(attempts) == 1:
        first = attempts[0]
        if first.get('status') == 'check_failed' and first.get('error') in ('URLError', 'TimeoutError'):
            return max(reset + 60, first['checked_at'] + 900)
    return None""", """    last = attempts[-1]
    status = last.get('status')
    if status == 'still_blocked':
        return max(last['checked_at'] + 900, last.get('next_reset_at') or 0)
    if status == 'checking' or (
        status == 'check_failed' and last.get('error') in ('URLError', 'TimeoutError', 'retryable_http')
    ):
        return max(reset + 60, last['checked_at'] + 900)
    return None""")
    source = replace_once(source, """        if check['status']!='available':
            event('quota_window_still_blocked',check=check);return""", """        if check['status']!='available':
            exhausted_resets = [
                window['reset_at'] for window in (
                    rate.get('primary_window') or {}, rate.get('secondary_window') or {})
                if isinstance(window.get('reset_at'), (int, float))
                and (window.get('used_percent') or 0) >= 100
                and window['reset_at'] > time.time()
            ]
            if exhausted_resets:
                check['next_reset_at'] = max(exhausted_resets) + 60
            event('quota_window_still_blocked',check=check);return""")
    return replace_once(source, """    except Exception as exc:
        check.update(status='check_failed',error=type(exc).__name__)
        event('quota_window_check_failed',check=check)""", """    except Exception as exc:
        retryable_http = isinstance(exc, urllib.error.HTTPError) and exc.code in (429, 500, 502, 503, 504)
        check.update(status='check_failed', error='retryable_http' if retryable_http else type(exc).__name__)
        if isinstance(exc, urllib.error.HTTPError):
            check['http_status'] = exc.code
        event('quota_window_check_failed',check=check)""")


def validate_quota_schedule(updated):
    syntax = ast.parse(updated)
    target = next(node for node in syntax.body
                  if isinstance(node, ast.FunctionDef) and node.name == 'next_quota_check')
    namespace = {}
    exec(compile(ast.Module(body=[target], type_ignores=[]), '<quota schedule>', 'exec'), namespace)
    next_check = namespace['next_quota_check']
    assert next_check(100, []) == 160
    assert next_check(100, [dict(reset_at=100, checked_at=160, status='still_blocked')]) == 1060
    assert next_check(100, [dict(reset_at=100, checked_at=160, status='still_blocked', next_reset_at=2600)]) == 2600
    assert next_check(100, [dict(reset_at=100, checked_at=160, status='check_failed', error='URLError')]) == 1060
    assert next_check(100, [dict(reset_at=100, checked_at=160, status='checking')]) == 1060
    assert next_check(100, [dict(reset_at=100, checked_at=160, status='check_failed', error='HTTPError')]) is None


def main():
    state = json.loads((ROOT / 'state.json').read_text())
    assert (state.get('block') or {}).get('status') == 429
    assert state['quota_resume_at'] > time.time() + 120
    assert all(job['state'] != 'running' for job in state['jobs'].values())
    paths = {SUPERVISOR: update_supervisor(SUPERVISOR.read_text()),
             CONTROLLER: update_controller(CONTROLLER.read_text())}
    validate_quota_schedule(paths[CONTROLLER])
    for path, source in paths.items():
        ast.parse(source)
        backup = path.with_suffix('.py.pre-quota-monitor-1126')
        with backup.open('x') as stream:
            stream.write(path.read_text())
        replace_atomic(path, source)
    subprocess.run(['systemctl', 'restart', UNIT], check=True)
    evidence = {
        'updated_at': datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
        'controller': {p.name: digest(p) for p in paths},
        'expected_resume_at': state['quota_resume_at'],
        'blocked_before': sum(t['gen'] == 'infra_blocked' for t in state['tasks'].values()),
        'finished_before': sum(t['gen'] == 'finished' for t in state['tasks'].values()),
        'schedule_tests': 6,
    }
    (ARCHIVE / '控制器变更核验-11-26.json').write_text(json.dumps(evidence, indent=2) + '\n')
    print(json.dumps(evidence))


if __name__ == '__main__':
    main()
