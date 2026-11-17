import pathlib,json,subprocess,shutil,hashlib
root=pathlib.Path('/root/Baxxhy/work2/reproductions/req2test/req2test-eval2051-resume-20261117-v1');backup=root/'concurrency-change-20261117-105721'
switch=json.loads((backup/'switch.json').read_text());assert (root/'jobs'/switch['job']/'exit.json').exists()
assert not (backup/'configuration-change.json').exists(), 'Refuse repeating an already applied pool switch'
assert json.loads((root/'frozen/config.json').read_text())['coddy_eval_workers']==3
subprocess.run(['systemctl','stop',root.name],check=True)
s=json.loads((root/'state.json').read_text());s['jobs'][switch['job']]['planned_concurrency_change']=True;s['evaluation_cpu_budget']=80
(root/'state.json').write_text(json.dumps(s,indent=2))
f=root/'frozen/config.json';cfg=json.loads(f.read_text());cfg.update(coddy_eval_workers=20,coddy_memory_reservation_gib=3,evaluation_max_cpu_budget=80);f.write_text(json.dumps(cfg,indent=2))
shutil.copy2('/tmp/coddy_resource_guard.py',root/'control/coddy_resource_guard.py')
f=root/'control/controller.py';code=f.read_text();original=code
code=code.replace('from seed_evaluation import seed_evaluations','from seed_evaluation import seed_evaluations\nfrom coddy_resource_guard import guard as coddy_guard, restore as restore_resource_checkpoint')
assert "'coddy-agent':18" in code
code=code.replace("'coddy-agent':18","'coddy-agent':CFG.get('coddy_memory_reservation_gib',18)")
needle="    if phase=='eval_req_project':\n        project=key;tries="
assert needle in code
code=code.replace(needle,"    if phase=='eval_req_project' and j.get('resource_pressure_abort'):\n        restore_resource_checkpoint(j,CFG,event)\n        S['projects'][key]='pending'\n        return\n"+needle)
needle="    S['evaluation_cpu_budget']=desired;S['project_parallelism']=2"
assert needle in code
code=code.replace(needle,"    if S['projects'].get('coddy-agent') in ('pending','running') and r['available_gib']>24:\n        desired=max(desired,min(CFG.get('evaluation_max_cpu_budget',32),4*CFG.get('coddy_eval_workers',1)))\n"+needle)
needle='poll();recover_quota_if_ready();r=resources();adapt(r);schedule(r);report(r)';assert needle in code
code=code.replace(needle,'poll();recover_quota_if_ready();r=resources();coddy_guard(S,CFG,ROOT,r,event);adapt(r);schedule(r);report(r)')
f.write_text(code)
subprocess.run(['/usr/bin/python3','-m','py_compile',str(f),str(root/'control/coddy_resource_guard.py')],check=True)
(backup/'configuration-change.json').write_text(json.dumps({'workers':20,'memory_reservation_per_worker_gib':3,'memory_reservation_is_estimate':True,'official_memory_cap_gib':16,'evaluation_cpu_budget':80,'original_controller_sha256':hashlib.sha256(original.encode()).hexdigest(),'new_controller_sha256':hashlib.sha256(code.encode()).hexdigest(),'resource_guard':'30s available<16GiB or memory PSI full>2 percent; 120s load>160 or IO PSI full>40 percent; backoff halves to minimum3; restores pre-attempt checkpoints'},indent=2))
r=subprocess.run(json.loads((root/'service-command.json').read_text()),text=True,capture_output=True);print(r.stdout,r.stderr);assert r.returncode==0
