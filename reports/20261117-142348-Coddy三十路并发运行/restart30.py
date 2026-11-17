from pathlib import Path
import json,subprocess,shutil,time,os
root=Path('/root/Baxxhy/work2/reproductions/req2test/req2test-eval2051-resume-20261117-v1')
job='0a897a9eb3f649969cf8c10803ce8564';jp=root/'jobs'/job
assert (jp/'exit.json').exists()
subprocess.run(['systemctl','stop',root.name],check=True)
backup=root/'parallel30-inventory180';backup.mkdir()
for f in ['state.json','frozen/config.json']:shutil.copy2(root/f,backup/Path(f).name)
wrapper=Path('/root/lby-docker/req2test/recovery-control-20261113-v1/parallel30-20261117')
shutil.copytree(wrapper,backup/'wrapper-before')
shutil.copy2('/tmp/inventory_batch.py',wrapper/'inventory_batch.py')
source=Path('/root/lby-docker/req2test/user/benchmark/runs/req2test-eval2051-resume-20261117-v1-coddy-agent/coddy-agent/th')
for name in ['mutation','mutation-raw','mutation.done.json']:
    if (source/name).exists():shutil.move(str(source/name),str(backup/name))
(source/'mutation').mkdir();os.chown(source/'mutation',1001,1001)
for f in (jp/'resource-start-checkpoint').glob('*.jsonl'):
    dst=source/'mutation'/f.name;shutil.copy2(f,dst);os.chown(dst,1001,1001)
s=json.loads((root/'state.json').read_text())
s['jobs'][job].update(state='finished',returncode=2,failure_reason='30s inventory timeout under full mutation load')
s['projects']['coddy-agent']='pending';s['evaluation_cpu_budget']=120;s['last_adapt']=time.time()
(root/'state.json').write_text(json.dumps(s,indent=2))
cfg=json.loads((root/'frozen/config.json').read_text());cfg.update(coddy_eval_workers=30,evaluation_max_cpu_budget=120)
(root/'frozen/config.json').write_text(json.dumps(cfg,indent=2))
with (root/'events.jsonl').open('a') as f:f.write(json.dumps(dict(time=time.time(),kind='inventory_transport_budget',workers=30,inventory_timeout=180,test_timeout=600,forward_deadline_preserved=True,failed_job=job))+'\n')
r=subprocess.run(json.loads((root/'service-command.json').read_text()),capture_output=True,text=True)
print(r.stdout,r.stderr);assert r.returncode==0
