import pathlib,json,shutil,os,hashlib,collections,subprocess
home=pathlib.Path('/root/lby-docker/req2test/user')
parent=pathlib.Path('/root/Baxxhy/work2/reproductions/req2test/req2test-eval2051-20261115-v1')
name='req2test-eval2051-resume-20261117-v1';root=parent.parent/name;output=home/'runs'/name
assert not root.exists() and not output.exists()
root.mkdir();output.mkdir();(root/'jobs').mkdir()
shutil.copytree(parent/'control',root/'control',ignore=shutil.ignore_patterns('__pycache__'))
shutil.copytree(parent/'frozen',root/'frozen')
s=json.loads((parent/'state.json').read_text());cfg=json.loads((parent/'frozen/config.json').read_text())
assert len(s['tasks'])==2051 and all(t['benchmark']=='req2test' for t in s['tasks'].values())
assert not any(j['state']=='running' for j in s['jobs'].values())
old_project_runs=s['project_run_ids'].copy()
for k in ['run_id','req_run_id']:cfg[k]=name
cfg.update(req_output=str(output),gateway_port=18197,req_gate_run_id=name+'-technical',eval_worker_max=2,coddy_eval_workers=1)
(root/'frozen/config.json').write_text(json.dumps(cfg,indent=2))
(root/'parent-state.json').write_text((parent/'state.json').read_text())
(root/'parent-progress.json').write_text((parent/'progress.json').read_text())
(output/'manifests').symlink_to(home/'runs/req2test-eval2051-20261115-v1/manifests',target_is_directory=True)
base=s.get('known_total_token_usage',{})
s.update(jobs={},projects={p:'pending' for p in s['projects']},project_run_ids={p:name+'-'+p for p in s['projects']},generation_cap=8,evaluation_cpu_budget=8,project_parallelism=2,full_req_merged=False,final_report_done=False,evaluation_seeded=True,block=None,generation_completions=[],stage_done=0,best_rate=0,stage_since=__import__('time').time(),last_adapt=__import__('time').time(),cooldown_until=0)
s.pop('final_report_blocked',None);s.pop('final_audit_attempts',None)
restored=[];prediction_hashes=[]
for key,t in s['tasks'].items():
 if t['gen']=='infra_blocked':
  restored.append({'id':t['id'],'previous_reason':t.get('reason'),'previous_attempts':t['gen_attempts']})
  t.update(gen='pending',evaluation='pending',prior_infrastructure_attempts=t['gen_attempts'],gen_attempts=0);t.pop('reason',None);t.pop('not_before',None)
 else:
  p=pathlib.Path(t['prediction']);assert p.exists();r=[json.loads(x) for x in p.read_text().splitlines() if x.strip()];assert len(r)==1 and r[0]['instance_id']==t['id']
  prediction_hashes.append({'id':t['id'],'prediction':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
assert len(restored)==31
(root/'frozen/current-generation-reuse.json').write_text(json.dumps(prediction_hashes,indent=2))
(root/'frozen/infra-generation-recovery.json').write_text(json.dumps(restored,indent=2))
subset=home/'benchmark/runs/req2test-subset160-infra-recovery-20261116-v1'
subset_predictions={r['instance_id']:r for r in [json.loads(x) for x in (home/'runs/req2test-subset160-infra-recovery-20261116-v1/predictions.jsonl').read_text().splitlines()]}
taskmap={t['id']:t for t in s['tasks'].values()};provenance=[]
def rows(p):return [json.loads(l) for l in p.read_text().splitlines() if l.strip()] if p.exists() else []
def write(p,rs):
 p.parent.mkdir(parents=True,exist_ok=True);p.write_text(''.join(json.dumps(r)+'\n' for r in rs))
for project,runid in s['project_run_ids'].items():
 src=home/'benchmark/runs'/old_project_runs[project]/project/'th';sub=subset/project/'th';dest=home/'benchmark/runs'/runid/project/'th'
 ready={t['id'] for t in s['tasks'].values() if t['project']==project and t['gen'] in ('finished','failed')}
 er={r['item_id']:r for r in rows(src/'exec.jsonl') if r['item_id'] in ready and r['outcome'] not in ('harness_error','timeout')}
 # Official model errors including dependency injection are retained from the valid run.
 sub_ids=set()
 for r in rows(sub/'exec.jsonl'):
  iid=r['item_id'];assert iid in ready
  pred=json.loads(pathlib.Path(taskmap[iid]['prediction']).read_text());assert pred==subset_predictions[iid],iid
  er[iid]=r;sub_ids.add(iid)
 write(dest/'exec/raw/w_reused.jsonl',list(er.values()))
 baselines={r.get('instance_id',r.get('item_id')):r for r in rows(src/'mutation.baseline.jsonl') if r.get('instance_id',r.get('item_id')) in er and r.get('outcome') not in ('harness_error','container_error','timeout')}
 for r in rows(sub/'mutation.baseline.jsonl'):baselines[r.get('instance_id',r.get('item_id'))]=r
 write(dest/'mutation.baseline.jsonl',list(baselines.values()))
 pairs={}
 for folder in [src,sub]:
  for path in sorted((folder/'mutation').glob('*.jsonl')):
   for r in rows(path):
    iid=r.get('instance_id',r.get('item_id'))
    if iid in er and (folder==sub or iid not in sub_ids):
     pairs[(iid,r['mutant_id'])]=r
 write(dest/'mutation/w_reused.jsonl',list(pairs.values()))
 provenance.append({'project':project,'source':str(src),'subset_source':str(sub),'destination':str(dest),'reused_exec':len(er),'reused_mutant_pairs':len(pairs),'subset_ids':sorted(sub_ids)})
 for f in [dest.parent.parent,*dest.parent.parent.rglob('*')]:os.chown(f,1001,1001)
assert sum(len(x['subset_ids']) for x in provenance)==160
(root/'evaluation-reuse-provenance.json').write_text(json.dumps(provenance,indent=2))
(root/'state.json').write_text(json.dumps(s,indent=2))
# Keep scheduling and scoring logic, with bounded fresh infrastructure attempts and cautious pools.
code=(root/'control/controller.py').read_text().replace("if t['id'] in job['eval_ids']:t['evaluation']='running'","if t['id'] in job['eval_ids'] and t['evaluation']!='finished':t['evaluation']='running'")
(root/'control/controller.py').write_text(code)
for f in [output,*output.rglob('*')]:
 if not f.is_symlink():os.chown(f,1001,1001)
summary={'run_id':name,'root':str(root),'output':str(output),'tasks':2051,'reused_generations':len(prediction_hashes),'generation_infrastructure_to_resume':len(restored),'subset_reused':160,'reused_exec':sum(x['reused_exec'] for x in provenance),'reused_mutant_pairs':sum(x['reused_mutant_pairs'] for x in provenance),'config':cfg,'projects':provenance}
(root/'preparation-summary.json').write_text(json.dumps(summary,indent=2))
print(json.dumps(summary,indent=2))
