import pathlib,json,subprocess,time,hashlib
root=pathlib.Path('/root/Baxxhy/work2/reproductions/req2test/req2test-eval2051-resume-20261117-v1');backup=root/'concurrency-change-20261117-130111'
switch=json.loads((backup/'switch.json').read_text());assert (root/'jobs'/switch['job']/'exit.json').exists(), 'Wait for official cancellation'
assert not (backup/'configuration-change.json').exists()
stopped=subprocess.run(['systemctl','stop',root.name],capture_output=True,text=True)
assert stopped.returncode in (0,5),stopped.stderr
# Official teardown is scoped to the cancelled pool and is idempotent.
pid=subprocess.check_output(['systemctl','show','user@1001.service','-p','MainPID','--value'],text=True).strip()
r=subprocess.run(['nsenter','-t',pid,'-m','--','runuser','-u','r2tbench','--','bash','-c','source /root/lby-docker/req2test/user/env.sh; exec req2test env down --project coddy-agent --nonce ee7fe3ffb'],capture_output=True,text=True,timeout=180)
(backup/'pool-teardown.txt').write_text(r.stdout+r.stderr);assert r.returncode==0 or 'no live environment' in r.stderr
s=json.loads((root/'state.json').read_text());s['jobs'][switch['job']]['planned_concurrency_change']=True;s['evaluation_cpu_budget']=128;s['last_adapt']=time.time();(root/'state.json').write_text(json.dumps(s,indent=2))
f=root/'frozen/config.json';old=f.read_text();c=json.loads(old);assert c['coddy_eval_workers']==20;c.update(coddy_eval_workers=32,coddy_memory_reservation_gib=2,evaluation_max_cpu_budget=128);f.write_text(json.dumps(c,indent=2))
(backup/'configuration-change.json').write_text(json.dumps({'workers_before':20,'workers_after':32,'cpu_scheduling_budget':128,'memory_reservation_per_worker_gib':2,'memory_reservation_is_estimate':True,'official_memory_cap_per_worker_gib':16,'previous_config_sha256':hashlib.sha256(old.encode()).hexdigest(),'current_config_sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'resource_guard_unchanged':True},indent=2))
r=subprocess.run(json.loads((root/'service-command.json').read_text()),capture_output=True,text=True);print(r.stdout,r.stderr);assert r.returncode==0
