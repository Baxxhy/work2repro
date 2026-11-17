from pathlib import Path
import json,subprocess,shutil,time
root=Path('/root/Baxxhy/work2/reproductions/req2test/req2test-eval2051-resume-20261117-v1')
job='3eb1d11d4aaf4ebebf1ccf23d5620dad'
for _ in range(120):
    if (root/'jobs'/job/'exit.json').exists():break
    time.sleep(5)
else:raise RuntimeError('Old official evaluator still running; no overlapping launch')
subprocess.run(['systemctl','stop',root.name],check=True)
backup=root/'parallel30-20261117-142348';backup.mkdir()
for f in ['state.json','frozen/config.json']:shutil.copy2(root/f,backup/Path(f).name)
pid=subprocess.check_output(['systemctl','show','user@1001.service','-p','MainPID','--value'],text=True).strip()
r=subprocess.run(['nsenter','-t',pid,'-m','--','runuser','-u','r2tbench','--','bash','-c','source /root/lby-docker/req2test/user/env.sh; exec req2test env down --project coddy-agent --nonce ecb475d7d'],capture_output=True,text=True,timeout=180)
assert r.returncode==0 or 'no live environment' in r.stderr,r.stderr
s=json.loads((root/'state.json').read_text())
s['jobs'][job]['planned_concurrency_change']=True
s['jobs'][job]['stop_reason']='User explicitly requests 30 workers with necessary isolation and inventory optimization'
s['projects']['coddy-agent']='pending';s['evaluation_cpu_budget']=120;s['last_adapt']=time.time()
(root/'state.json').write_text(json.dumps(s,indent=2))
cfg=json.loads((root/'frozen/config.json').read_text())
cfg.update(diagnostic_eval_wrapper='/root/lby-docker/req2test/recovery-control-20261113-v1/parallel30-20261117/diagnostic_eval.py',coddy_eval_workers=30,coddy_memory_reservation_gib=2,evaluation_max_cpu_budget=120)
(root/'frozen/config.json').write_text(json.dumps(cfg,indent=2))
mutation=Path(cfg['req_home'])/'benchmark/runs/req2test-eval2051-resume-20261117-v1-coddy-agent/coddy-agent/th/mutation'
pairs=set()
for f in mutation.glob('*.jsonl'):
    for line in f.read_text().splitlines():
        row=json.loads(line);pairs.add((row['instance_id'],row['mutant_id']))
record=dict(time=time.time(),kind='parallel30_start',workers=30,completed_pairs=len(pairs),inventory_helper='batched SHA256, same output',run_lock=True,official_test_timeout_unchanged=True)
(backup/'deployment.json').write_text(json.dumps(record,indent=2))
with (root/'events.jsonl').open('a') as f:f.write(json.dumps(record)+'\n')
r=subprocess.run(json.loads((root/'service-command.json').read_text()),capture_output=True,text=True)
print(r.stdout,r.stderr);assert r.returncode==0
print(json.dumps(record))
