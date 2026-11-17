from pathlib import Path
import json,subprocess,shutil,time,hashlib
root=Path('/root/Baxxhy/work2/reproductions/req2test/req2test-eval2051-resume-20261117-v1')
subprocess.run(['systemctl','stop',root.name],capture_output=True)
s=json.loads((root/'state.json').read_text())
assert not any(j['state']=='running' for j in s['jobs'].values()),'an evaluator is still recorded active'
backup=root/'extended-timeouts-20261117';backup.mkdir(exist_ok=True)
for f in ['state.json','frozen/config.json','control/controller.py','control/coddy_resource_guard.py']:
 if not (backup/Path(f).name).exists():shutil.copy2(root/f,backup/Path(f).name)
c=json.loads((root/'frozen/config.json').read_text());wrapper='/root/lby-docker/req2test/recovery-control-20261113-v1/extended-timeouts-20261117'
c.update(diagnostic_eval_wrapper=wrapper+'/diagnostic_eval.py',coddy_eval_workers=28,evaluation_max_cpu_budget=112,timeout_profile='extended-20261117-v1',req_generation_timeout=max(c.get('req_generation_timeout',3600),7200))
(root/'frozen/config.json').write_text(json.dumps(c,indent=2))
p=root/'control/controller.py';source=p.read_text()
old="and not x.get('unstable_resource_attempt') for x in S['jobs'].values())"
new="and not x.get('unstable_resource_attempt') and x.get('timeout_profile')==CFG.get('timeout_profile') for x in S['jobs'].values())"
assert source.count(old)==2;source=source.replace(old,new)
old="job.update(official_run_id=run_id,memory_reservation_gib=memory,workers=workers,eval_ids="
new="job.update(timeout_profile=CFG.get('timeout_profile'),official_run_id=run_id,memory_reservation_gib=memory,workers=workers,eval_ids="
assert source.count(old)==1;source=source.replace(old,new)
old="dict(R2T_RECOVERY_DIAGNOSTICS=str(RROOT/'evaluation-diagnostics'))"
new="dict(R2T_RECOVERY_DIAGNOSTICS=str(RROOT/'evaluation-diagnostics'),R2T_EXTENDED_TIMEOUTS='20261117-v1',PYTHONPATH='"+wrapper+":'+str(RR))"
assert source.count(old)==1;source=source.replace(old,new)
p.write_text(source)
p=root/'control/coddy_resource_guard.py';source=p.read_text().replace('timeout=180','timeout=600');p.write_text(source)
subprocess.run(['python','-m','py_compile',str(root/'control/controller.py'),str(p)],check=True)
s['projects']['coddy-agent']='pending';s['evaluation_cpu_budget']=112;s['last_adapt']=time.time();s['final_report_done']=False;s.pop('final_report_blocked',None)
(root/'state.json').write_text(json.dumps(s,indent=2))
pairs=set();path=Path(c['req_home'])/'benchmark/runs/req2test-eval2051-resume-20261117-v1-coddy-agent/coddy-agent/th/mutation'
for f in path.glob('*.jsonl'):
 for line in f.read_text().splitlines():
  r=json.loads(line);pairs.add((r['instance_id'],r['mutant_id']))
record=dict(time=time.time(),kind='extended_timeout_profile',profile=c['timeout_profile'],resume_pairs=len(pairs),workers=28,old_command_seconds=600,new_command_seconds=1800,old_helper_seconds=30,new_helper_seconds=600,cleanup_seconds=120,retire_seconds=1800,prior_results_preserved=True,new_profile_attempt_limit=3)
(backup/'deployment.json').write_text(json.dumps(record,indent=2))
with (root/'events.jsonl').open('a') as f:f.write(json.dumps(record)+'\n')
r=subprocess.run(json.loads((root/'service-command.json').read_text()),capture_output=True,text=True);print(r.stdout,r.stderr);assert r.returncode==0
print(json.dumps(record))
