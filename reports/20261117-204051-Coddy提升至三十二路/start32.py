from pathlib import Path
import json,subprocess,time,os,hashlib
root=Path('/root/Baxxhy/work2/reproductions/req2test/req2test-eval2051-resume-20261117-v1'); backup=root/'concurrency32-20261117-late'
switch=json.loads((backup/'switch.json').read_text()); exitfile=root/'jobs'/switch['job']/'exit.json'
deadline=time.time()+600
while not exitfile.exists():
 if time.time()>deadline: raise SystemExit('Official cancellation still pending; controller remains paused, inspect before resuming')
 time.sleep(2)
print('official cancellation complete',exitfile.read_text(),flush=True)
r=subprocess.run(['systemctl','stop',root.name],capture_output=True,text=True,timeout=50); assert r.returncode in (0,5),r.stderr
pid=subprocess.check_output(['systemctl','show','user@1001.service','-p','MainPID','--value'],text=True).strip()
cmd=['nsenter','-t',pid,'-m','--','runuser','-u','r2tbench','--','bash','-c','source /root/lby-docker/req2test/user/env.sh; exec req2test env down --project coddy-agent --nonce '+switch['nonce']]
r=subprocess.run(cmd,capture_output=True,text=True,timeout=600); (backup/'pool-teardown.txt').write_text(r.stdout+r.stderr); assert r.returncode==0 or 'no live environment' in r.stderr, r.stderr
source=Path('/root/lby-docker/req2test/user/benchmark/runs/req2test-eval2051-resume-20261117-v1-coddy-agent/coddy-agent/th/mutation')
def rows(folder):
 out={}
 for f in folder.glob('*.jsonl'):
  for l in f.read_text().splitlines():
   r=json.loads(l);out[(r['instance_id'],r['mutant_id'])]=r
 return out
old=rows(backup/'mutation');new=rows(source);assert all(new.get(k)==v for k,v in old.items()),'Previously completed rows changed'
s=json.loads((root/'state.json').read_text());s['jobs'][switch['job']]['planned_concurrency_change']=True;s['evaluation_cpu_budget']=128;s['last_adapt']=time.time();(root/'state.json').write_text(json.dumps(s,indent=2))
f=root/'frozen/config.json';previous=f.read_text();c=json.loads(previous);assert c['coddy_eval_workers']==28;c.update(coddy_eval_workers=32,evaluation_max_cpu_budget=128);f.write_text(json.dumps(c,indent=2))
record=dict(time=time.time(),workers_before=28,workers_after=32,cpu_budget=128,preserved_pairs=len(old),current_pairs=len(new),resource_guard_unchanged=True,official_code_unchanged=True,timeout_profile=c['timeout_profile'],config_sha256=hashlib.sha256(f.read_bytes()).hexdigest())
(backup/'configuration-change.json').write_text(json.dumps(record,indent=2))
with (root/'events.jsonl').open('a') as h:h.write(json.dumps(dict(kind='requested_concurrency_increase',**record))+'\n')
r=subprocess.run(json.loads((root/'service-command.json').read_text()),capture_output=True,text=True);print(r.stdout,r.stderr,flush=True); assert r.returncode==0
print(json.dumps(record),flush=True)
