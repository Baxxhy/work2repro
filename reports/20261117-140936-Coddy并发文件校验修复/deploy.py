from pathlib import Path
import subprocess,json,shutil,time
root=Path('/root/Baxxhy/work2/reproductions/req2test/req2test-eval2051-resume-20261117-v1')
job='287e3a721a924bbfbf8bf75f8e5fc584'
assert (root/'jobs'/job/'exit.json').exists()
subprocess.run(['systemctl','stop',root.name],check=True)
backup=root/'inventory-fix-20261117-140936';backup.mkdir()
for f in ['state.json','frozen/config.json']:shutil.copy2(root/f,backup/Path(f).name)
cfg=json.loads((root/'frozen/config.json').read_text())
cfg['diagnostic_eval_wrapper']='/root/lby-docker/req2test/recovery-control-20261113-v1/inventory-recovery-20261117/diagnostic_eval.py'
(root/'frozen/config.json').write_text(json.dumps(cfg,indent=2))
s=json.loads((root/'state.json').read_text())
s['jobs'][job]['planned_concurrency_change']=True
s['jobs'][job]['stop_reason']='Deploy semantically equivalent batched integrity inventory'
s['projects']['coddy-agent']='pending'
(root/'state.json').write_text(json.dumps(s,indent=2))
with (root/'events.jsonl').open('a') as f:
 f.write(json.dumps(dict(time=time.time(),kind='inventory_batch_fix',workers=20,helper_timeout=30,test_timeout=600,previous_job=job))+'\n')
r=subprocess.run(json.loads((root/'service-command.json').read_text()),text=True,capture_output=True)
print(r.stdout,r.stderr);assert r.returncode==0
