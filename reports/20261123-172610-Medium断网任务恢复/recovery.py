import csv,json,hashlib,os,shutil,subprocess,time
from pathlib import Path
d=Path(__file__).resolve().parent
base=Path('/root/Baxxhy/work2/reproductions/req2test')
p=base/'req2test-medium-full-20261123'
r=base/'req2test-medium-network260-1123'
def load(f):return json.loads(f.read_text())
def save(f,v):f.write_text(json.dumps(v))
def eligible(s):
 tasks={}
 for k,t in s['tasks'].items():
  if t['gen']!='infra_blocked' or t['reason']!='network_interruption':continue
  jobs=[j for j in s['jobs'].values() if j['key']==k and j['phase']=='gen_req']
  if len(jobs)==2 and all(j['generation_outcome']['reason']=='network_interruption' and not j['generation_outcome']['turn_completed'] and not j['generation_outcome']['prediction_valid'] for j in jobs) and not any(Path(t['prediction']).parent.parent.glob('*/predictions.jsonl')):
   tasks[k]=t
 return tasks
s=load(p/'state.json');tasks=eligible(s)
assert len(tasks)==260
cfg=load(p/'frozen/config.json');src=Path(cfg['req_output']);o=src.parent/r.name
r.mkdir();(r/'jobs').mkdir();shutil.copytree(p/'control',r/'control')
shutil.copytree(p/'frozen',r/'frozen')
for f in (o,o/'input',o/'generation',o/'manifests',o/'manifests/items'):f.mkdir()
os.chown(o/'generation',1001,1001);shutil.copyfile(src/'agent.py',o/'agent.py')
for k,t in list(tasks.items()):
 f=Path('manifests/items')/(t['safe']+'.jsonl');shutil.copyfile(src/f,o/f)
 tasks[k]={a:t[a] for a in ('id','safe','project','benchmark')}
 tasks[k].update(gen='pending',evaluation='pending',gen_attempts=0)
save(r/'recovery-ids.json',sorted(t['id'] for t in tasks.values()))
cfg.update(run_id=r.name,req_run_id=r.name,req_output=str(o),gateway_port=18245)
save(r/'frozen/config.json',cfg)
s=load(p/'state.json')
s.update(tasks=tasks,jobs={},groups={},block=None,cooldown_until=0,request_retries=0,events_429=0,generation_completions=[],started=time.time(),generation_cap=8)
save(r/'state.json',s)
sup=r/'control/supervise_diagnostic.py'
sup.write_text(sup.read_text().replace("t['gen_attempts']<2","t['gen_attempts']<1").replace('total=2051,reused=0,new_total=2051','total=260,reused=0,new_total=260'))
# One additional attempt per ID, after the primary generation slots drain.
while True:
 s=load(p/'state.json')
 if not any(t['gen'] in ('pending','running') for t in s['tasks'].values()):break
 time.sleep(30)
assert tasks.keys()<=eligible(s).keys()
# The official evaluator must also remain serial across both runs.
while not (p/'completion.json').exists():time.sleep(30)
cmd=[a.replace(p.name,r.name) for a in load(p/'service-command.json')]
subprocess.run(cmd,check=True)
while not (r/'completion.json').exists():time.sleep(30)
subprocess.run(['python3',str(d/'merge.py')],check=True)
