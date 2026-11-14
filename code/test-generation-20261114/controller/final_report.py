"""Read-only official scoring/statistics after every queued ID is terminal."""
import csv,json,shutil,sys
from pathlib import Path
from rich.console import Console
from programbench.eval.test_suite_eval import TestSuiteEvaluationResult
from programbench.eval.test_suite_eval_batch import InstanceTestSuiteEvalSummary,BatchTestSuiteEvalSummary
r=Path(sys.argv[1]);s=json.loads((r/'state.json').read_text());cfg=json.loads((r/'frozen/config.json').read_text())
out=r/'reports';out.mkdir(exist_ok=True)
summaries=[];rows=[];excluded=[]
for t in s['tasks'].values():
 if t['benchmark']!='tsb':continue
 if t['evaluation']=='finished':
  p=Path(t['official_report']);result=TestSuiteEvaluationResult.model_validate_json(p.read_text())
  summary=InstanceTestSuiteEvalSummary.from_eval_result(t['id'],result)
 elif t['gen']=='failed' and t['evaluation']=='not_applicable_no_suite':
  # Exact official no-payload branch, including mutation_score=None.
  summary=InstanceTestSuiteEvalSummary(instance_id=t['id'],score=0,n_passed=0,n_tests=0,error_code='no_test_suite')
 else:
  excluded.append(dict(instance_id=t['id'],reason=t.get('reason','infrastructure_blocked')));continue
 summaries.append(summary);rows.append(summary.model_dump())
batch=BatchTestSuiteEvalSummary(summaries=summaries)
payload=batch.model_dump();payload.update(manifest_total=cfg['tsb_task_count'],
 validity_denominator=len(rows),mutation_denominator=sum(x['mutation_score'] is not None for x in rows),
 infrastructure_unfinished=excluded,aggregation='locked official BatchTestSuiteEvalSummary')
(out/'tsb-official-summary.json').write_text(json.dumps(payload,indent=2))
if rows:
 with (out/'tsb-per-task.csv').open('w') as f:
  writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
console=Console(record=True,width=140);console.print(batch.summary());console.save_text(out/'tsb-official-report.txt')
reqroot=Path(cfg['req_home'])/'benchmark/runs'/cfg['req_run_id']
req=None
if (reqroot/'summary.json').exists():
 req=json.loads((reqroot/'summary.json').read_text())
 shutil.copy2(reqroot/'summary.json',out/'req2test-official-summary.json')
 if (reqroot/'report.md').exists():shutil.copy2(reqroot/'report.md',out/'req2test-official-report.md')
 cells=req.get('modes',{}).get('leaderboard',{}).get('cells',{})
 projectrows=[dict(cell=key,**row) for key,row in cells.items()]
 (out/'req2test-per-project.json').write_text(json.dumps(projectrows,indent=2))
 (out/'req2test-denominators-and-exclusions.json').write_text(json.dumps(dict(
   manifest_total=cfg['req_task_count'],official_population=req.get('population'),official_cells=cells,disclosures=req.get('disclosures')),indent=2))
 with (out/'req2test-per-task.jsonl').open('w') as target:
  seen=set()
  for p in sorted(reqroot.glob('*/th/instances.jsonl')):
   for line in p.read_text().splitlines():
    row=json.loads(line)
    if row['instance_id'] in seen:raise RuntimeError('Duplicate official scored ID')
    seen.add(row['instance_id']);target.write(line+'\n')
 (out/'req2test-scored-id-audit.json').write_text(json.dumps(dict(unique_ids=len(seen),manifest_total=cfg['req_task_count'],missing=sorted(set(t['id'] for t in s['tasks'].values() if t['benchmark']=='req2test')-seen)),indent=2))
table=['# Baseline results','',
 '| Benchmark | Manifest IDs | Official scored rows | Mean validity | Mutation score |',
 '|---|---:|---:|---:|---:|',
 f'| TestSuiteBench | {cfg["tsb_task_count"]} | {len(rows)} | {batch.average_validity_rate:.6f} | {batch.average_mutation_score} |',
 f'| Req2Test-Bench | {cfg["req_task_count"]} | see official denominators | see official report | see official report |','',
 'Req2Test metrics, equal-weight project means and exclusions are copied from its official report. Missing measures are not invented.',
 'TestSuiteBench infrastructure-blocked IDs remain explicit and are not silently treated as model results.',
 'See final-task-audit.json, failures-and-unfinished.json and the raw per-task generation/evaluation logs.']
(out/'RESULTS.md').write_text('\n'.join(table)+'\n')

from recovery_validation import validate as validate_recovery
validate_recovery(r)
