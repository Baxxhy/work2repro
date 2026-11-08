"""Read subscription limits without inference; resume incomplete samples after recovery."""
import json,time,os,subprocess,datetime,fcntl
from pathlib import Path
from codex_luna_bridge import CodexRPC,Audit,app_server_command
ROOT=Path('/root/Baxxhy/work2/reproductions/testupdater')
WATCH=ROOT/'runs/quota-monitor';WATCH.mkdir(exist_ok=True)
lock=(WATCH/'lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
def status(state,**kw):
 d={'state':state,'time':datetime.datetime.now(datetime.timezone.utc).isoformat(),**kw}
 p=WATCH/'status.json';tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(d,indent=2));tmp.replace(p);print(json.dumps(d),flush=True)
def limits():
 p=WATCH/str(time.time_ns());p.mkdir()
 rpc=CodexRPC(app_server_command('codex'),Path('/tmp/testupdater-quota-monitor'),p/'fatal.json',Audit(p/'audit.jsonl'))
 try:
  rpc.start();return rpc.call('account/rateLimits/read',{},timeout=30)
 finally:rpc._terminate()
def exhausted(value):
 if isinstance(value,dict):
  if isinstance(value.get('usedPercent'),(int,float)) and value['usedPercent']>=100:return True
  return any(exhausted(v) for v in value.values())
 return isinstance(value,list) and any(exhausted(v) for v in value)
prev=ROOT/'runs/recovery5-20261105'
while True:
 try:
  state=json.loads((prev/'status.json').read_text())
  if state['state']=='running':status('experiment_running',run=str(prev));time.sleep(300);continue
  # Resume missing records only. Existing method/script outcomes remain for separate audit.
  pending=0
  for ds in ['updates4j','prbench']:
   for f in (prev/'input'/ds).glob('*.json'):
    pending+=sum(not (prev/ds/f.stem/'samples'/f'{i:04d}.json').exists() for i,_ in enumerate(json.loads(f.read_text())))
  if not pending:status('finished',run=str(prev),note='All selected samples have records; script errors need separate review.');break
  value=limits();(WATCH/'limits.json').write_text(json.dumps(value,indent=2))
  if exhausted(value):status('waiting_for_quota',pending=pending);time.sleep(300);continue
  # Reuse the verified launcher, preserving previous runs and selecting only unfinished rows.
  stamp=datetime.datetime.now().strftime('%Y%m%d-%H%M%S');new=ROOT/'runs'/('quota-resume-'+stamp)
  source=Path('/tmp/tu_resume2.py').read_text().replace("prev=r/'runs/recovery-20261105'",'prev=Path('+repr(str(prev))+')').replace("out=r/'runs/recovery2-20261105'",'out=Path('+repr(str(new))+')')
  source=source.replace("if p.exists() and json.loads(p.read_text()).get('execution_status')!='harness_error':continue",'if p.exists():continue')
  launch=WATCH/'launch.py';launch.write_text(source)
  status('resuming',pending=pending,run=str(new))
  result=subprocess.run(['python3',str(launch)],timeout=180)
  if result.returncode==0:prev=new
  else:status('connection_retry',pending=pending)
 except Exception as e:status('monitor_retry',error=str(e)[:300])
 time.sleep(300)
