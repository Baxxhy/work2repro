"""Start only after the published freeze has been verified."""
import hashlib,json,os,shutil,socket,subprocess,sys,time
from pathlib import Path
d=Path(__file__).resolve().parent
name='req2test-b-incremental-20261123'
h=Path('/root/lby-docker/req2test/user')
base=Path('/root/Baxxhy/work2/reproductions/req2test')
old=base/'req2test-paired80-20261123-b'; root=base/name
o=h/'runs'/name
def read(p):return json.loads(p.read_text())
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False)+'\n')
freeze=read(d/'清单与配置核验-11-23.json')
reuse={r['instance_id']:r for r in freeze['reuse']}
pending={r['instance_id']:r for r in freeze['pending']}
assert len(reuse)==80 and len(pending)==1971 and not set(reuse)&set(pending)
for r in reuse.values():
 assert hashlib.sha256(Path(r['prediction']).read_bytes()).hexdigest()==r['prediction_sha256']
assert not root.exists() and not o.exists()
with socket.socket() as probe:probe.bind(('127.0.0.1',18243))
manifest={r['instance_id']:r for f in (h/'tasks').glob('*.eval.jsonl') for l in f.open() if (r:=json.loads(l))}
assert set(manifest)==set(reuse)|set(pending)
root.mkdir();(root/'jobs').mkdir();(root/'frozen').mkdir()
shutil.copytree(old/'control',root/'control',ignore=shutil.ignore_patterns('__pycache__'))
for p in [o,o/'manifests',o/'manifests/items',o/'input',o/'generation']:p.mkdir()
os.chown(o/'generation',1001,1001)
shutil.copyfile(h/'runs'/old.name/'agent.py',o/'agent.py')
assert hashlib.sha256((o/'agent.py').read_bytes()).hexdigest()==freeze['adapter_sha256']
tasks={}
for i in sorted(pending,key=lambda x:hashlib.sha256(x.encode()).digest()):
 safe=hashlib.sha256(i.encode()).hexdigest()[:20]
 write(o/'manifests/items'/(safe+'.jsonl'),manifest[i])
 tasks['req:'+i]=dict(id=i,project=pending[i]['project'],safe=safe,benchmark='req2test',gen='pending',evaluation='pending',gen_attempts=0)
cfg=read(old/'frozen/config.json');cfg.update(req_output=str(o),gateway_port=18243,run_id=name,req_run_id=name,codex_version='0.153.4',reasoning='high',arm='b')
write(root/'frozen/config.json',cfg);shutil.copyfile(old/'frozen/config.parent.json',root/'frozen/config.parent.json')
write(root/'frozen/replays.json',{i:dict(project=r['project'],prediction=r['prediction'],outcome=r['first_outcome']) for i,r in reuse.items()})
write(root/'state.json',dict(tasks=tasks,jobs={},groups={},block=None,cooldown_until=0,generation_cap=8,evaluation_cpu_budget=8,request_retries=0,events_429=0,generation_completions=[],started=time.time()))
p=root/'control/supervise_diagnostic.py'
src=p.read_text().replace('summary=dict(total=80','summary=dict(total=2051,reused=80,new_total=1971').replace('str(min(2,len(selected)))','"1"').replace("len(running('eval_diagnostic'))>=2","len(running('eval_diagnostic'))>=1")
src=src.replace("j['generation_outcome'] = outcome","if j.get('usage'):\n                atomic(Path(j['path'])/'usage.json',j.pop('usage'))\n            j['generation_outcome'] = outcome")
p.write_text(src)
cmd=[a.replace(str(old),str(root)).replace('--unit='+old.name,'--unit='+name) for a in read(old/'service-command.json')]
write(root/'service-command.json',cmd)
subprocess.run(cmd,check=True)
