import collections
import csv
import json
from pathlib import Path

here = Path(__file__).resolve().parent
baseline = here.parent / '20261118-010456-Req2Test全量尾项恢复与统计修正'
rate_limited = json.loads((here / '限流中断任务-11-18.json').read_text())
historical = json.loads((here / '历史启动异常任务-11-18.json').read_text())
assert len(rate_limited) == 41
assert all(r['http'] == [429] and r['turn_completed'] == 0
           and r['turn_failed'] == 1 and r['same_prediction_dir']
           and r['trace_error_tags'] == ['429', '429'] and r['files'] == 0
           and 0 < r['calls'] < 200 for r in rate_limited)
assert collections.Counter(r['kind'] for r in historical) == dict(
    thread_start_failure=6, view_empty_file=3, unresolved=3)
assert all(r['file_count'] == 0 for r in historical)
with (baseline / '逐任务状态与排除原因-11-18.csv').open() as source:
    all_rows = {r['instance_id']:r for r in csv.DictReader(source)}
assert len(all_rows) == 2051
suspect = rate_limited + historical
assert len({r['id'] for r in suspect}) == 53
assert all(all_rows[r['id']]['disposition'] == 'scored'
           and all_rows[r['id']]['engine_outcome'] == 'no_files_returned' for r in suspect)
count = collections.Counter(r['project'] for r in all_rows.values() if r['disposition'] == 'scored')
passed = collections.Counter(r['project'] for r in all_rows.values() if r['disposition'] == 'scored' and r['outcome'] == 'pass')
def counterfactual(rows):
    affected = collections.Counter(r['project'] for r in rows)
    excluded = sum(passed[p] / (n - affected[p]) for p, n in count.items()) / len(count)
    all_pass = sum((passed[p] + affected[p]) / n for p, n in count.items()) / len(count)
    return {k: round(v * 100, 4) for k, v in {'excluded_for_diagnosis':excluded,'all_recovered_pass':all_pass}.items()}
confirmed = rate_limited + [r for r in historical if r['kind'] != 'unresolved']
assert len(confirmed) == 50
print('baseline', sum(passed[p] / n for p, n in count.items()) / len(count) * 100)
print('confirmed_by_project', collections.Counter(r['project'] for r in confirmed))
print('confirmed_50', counterfactual(confirmed))
print('including_unresolved_53', counterfactual(suspect))
