from pathlib import Path
import json,subprocess,shutil,time,hashlib,py_compile
root=Path('/root/Baxxhy/work2/reproductions/req2test/req2test-eval2051-resume-20261117-v1')
assert subprocess.check_output(['systemctl','show',root.name,'-p','ActiveState','--value'],text=True).strip()=='inactive'
backup=root/'recorder-compat-20261117-v1';backup.mkdir(exist_ok=False)
for rel in ['state.json','progress.json','frozen/config.json','control/controller.py','completion.json','final-task-audit.json','failures-and-unfinished.json']:
 if (root/rel).exists():shutil.copy2(root/rel,backup/Path(rel).name)
source=Path('/root/lby-docker/req2test/user/benchmark/runs/req2test-eval2051-resume-20261117-v1-coddy-agent/coddy-agent/th/mutation');shutil.copytree(source,backup/'mutation-checkpoint')
wrapper=Path('/root/lby-docker/req2test/recovery-control-20261113-v1/recorder-compat-20261117-v1')
for f in wrapper.glob('*.py'):py_compile.compile(str(f),doraise=True)
cfgp=root/'frozen/config.json';cfg=json.loads(cfgp.read_text());cfg.update(diagnostic_eval_wrapper=str(wrapper/'diagnostic_eval.py'),recorder_profile='before-goexit-recorder-v1',timeout_profile='extended-20261117-v1-recordercompat1',coddy_eval_workers=32,evaluation_max_cpu_budget=128);cfgp.write_text(json.dumps(cfg,indent=2))
p=root/'control/controller.py';text=p.read_text();old="PYTHONPATH='/root/lby-docker/req2test/recovery-control-20261113-v1/extended-timeouts-20261117:'";new="PYTHONPATH='/root/lby-docker/req2test/recovery-control-20261113-v1/recorder-compat-20261117-v1:'";assert text.count(old)==1;text=text.replace(old,new);p.write_text(text);py_compile.compile(str(p),doraise=True)
s=json.loads((root/'state.json').read_text());assert not any(j['state']=='running' for j in s['jobs'].values());s['projects']['coddy-agent']='pending'
for t in s['tasks'].values():
 if t.get('project')=='coddy-agent' and t['evaluation']!='finished': t['evaluation']='pending'
s['evaluation_cpu_budget']=128;s['final_report_done']=False;s.pop('final_report_blocked',None);s['final_audit_attempts']=0
(root/'state.json').write_text(json.dumps(s,indent=2))
if (root/'completion.json').exists():(root/'completion.json').rename(backup/'completion-before-resume.json')
event=dict(time=time.time(),kind='recorder_compatibility_recovery',workers=32,fix='suppress Passed callback before any Defined event when no definition exists',official_crash_classifier_unchanged=True,validation_unchanged=True,completed_rows_preserved=True,config_sha256=hashlib.sha256(cfgp.read_bytes()).hexdigest())
with (root/'events.jsonl').open('a') as f:f.write(json.dumps(event)+'\n')
(backup/'deployment.json').write_text(json.dumps(event,indent=2))
r=subprocess.run(json.loads((root/'service-command.json').read_text()),capture_output=True,text=True);print(r.stdout,r.stderr);assert r.returncode==0
print(json.dumps(event))
