"""Read existing official evidence only. No model or evaluator invocation."""
import json,pathlib,collections,time
base=pathlib.Path('/root/Baxxhy/work2/reproductions/req2test/req2test-eval2051-20261115-v1')
home=pathlib.Path('/root/lby-docker/req2test/user')
s=json.loads((base/'state.json').read_text());p=json.loads((base/'progress.json').read_text())
rows=[];issues=[];completed={t['id']:t for t in s['tasks'].values() if t['evaluation']=='finished'}
for project in s['projects']:
 source=home/'benchmark/runs'/s['project_run_ids'][project]/project/'th/instances.jsonl'
 if not source.exists():continue
 for line in source.read_text().splitlines():
  if not line.strip():continue
  row=json.loads(line)
  if row['instance_id'] in completed:
   row['_source']=str(source);row['_prediction']=completed[row['instance_id']].get('prediction');rows.append(row)
seen=[r['instance_id'] for r in rows]
assert len(seen)==len(set(seen))
issues=sorted(set(completed)-set(seen))
requirements={}
for f in (home/'tasks').glob('*.eval.jsonl'):
 for line in f.read_text().splitlines():
  if not line.strip():continue
  r=json.loads(line);requirements[r['instance_id']]={'project':r['project'],'requirement_type':r['task']['criterion'].get('kind','unknown'),'title':r['task']['criterion'].get('scenario_title',''),'richness':r['task']['requirement'].get('richness','unknown')}
import yaml
population=yaml.safe_load((home/'repo/benchmark/config/benchmark_2.0_population.yml').read_text())
print(json.dumps(dict(collected=time.time(),progress=p,rows=rows,missing_completed_rows=issues,requirements=requirements,exclusions={r['instance_id']:r['reason'] for r in population['excluded']})))
