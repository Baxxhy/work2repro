"""Offline checks of the exported full-eval report, no model or benchmark run."""
import csv,json,math
from pathlib import Path
ROOT=Path(__file__).resolve().parent
summary=json.loads((ROOT/'Req2Test官方全量汇总-11-18.json').read_text())
audit=json.loads((ROOT/'全量完整性与结果保护核对-11-18.json').read_text())
manifest=list(csv.DictReader((ROOT/'全量任务清单-11-18.csv').open()))
rows=[json.loads(l) for l in (ROOT/'Req2Test全量逐任务指标-11-18.jsonl').read_text().splitlines()]
status=list(csv.DictReader((ROOT/'逐任务状态与排除原因-11-18.csv').open()))
ids=[r['instance_id'] for r in manifest]
assert len(ids)==len(set(ids))==2051
assert {r['instance_id'] for r in rows}==set(ids) and len(rows)==2051
assert {r['instance_id'] for r in status}==set(ids) and len(status)==2051
assert len(summary['population']['excluded'])==14
counts={k:sum(r['disposition']==k for r in status) for k in ['scored','population_excluded','infrastructure_excluded','outside_ladder_excluded']}
assert counts==dict(scored=2031,population_excluded=14,infrastructure_excluded=4,outside_ladder_excluded=2),counts
cells=summary['modes']['leaderboard']['cells'];assert len(cells)==8
assert sum(c['n'] for c in cells.values())==2037
assert sum(c['n']-c['excluded'] for c in cells.values())==2031
mean=summary['modes']['leaderboard']['mean']['th'];assert mean['complete']
for key in ['pass_at_1','kill_complete_at_1','api_f1','coverage_j','mutation_recall']:
 assert math.isclose(sum(c[key] for c in cells.values())/8,mean[key]['value'],abs_tol=1e-12)
assert audit['all_manifest_ids_have_results'] and not audit['missing'] and not audit['extra']
assert audit['completed_executions_preserved']==2047 and audit['all_generation_bytes_preserved']
assert sum(v['pairs'] for v in audit['mutations'].values())==59558
assert all(v['complete'] and v['unchanged'] for v in audit['mutations'].values())
print('PASS: 2051 unique IDs, 8 projects, all official exclusions and macro metrics agree; 59558 mutation records accounted for.')
