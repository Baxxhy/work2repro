"""Launch recovery only after both smoke samples actually execute target tests."""
import json,time,subprocess,os
from pathlib import Path
r=Path('/root/Baxxhy/work2/reproductions/testupdater');out=r/'runs/recovery-20261105';smoke=r/'runs/recovery-smoke-20261105'
for _ in range(120):
 p=smoke/'status.json'
 if p.exists():
  state=json.loads(p.read_text())
  if state['state']!='running':break
 time.sleep(15)
else:raise SystemExit('Smoke timeout; recovery not launched')
rows=[json.loads(p.read_text()) for p in smoke.glob('*/*/samples/*.json')]
if len(rows)!=2 or any(d.get('exception_while_gen_tests') or not any(e.get('matched',0)>0 for e in d.get('execution_evidence',[])) for d in rows):raise SystemExit('Smoke verification failed; recovery not launched')
env=os.environ.copy();env['TU_RECOVERY_DATA']=str(out/'input')
p=subprocess.Popen(['bash',str(r/'deployment/start.sh'),'--output',str(out),'--workers','10'],env=env,stdout=(out/'console.log').open('a'),stderr=subprocess.STDOUT,start_new_session=True)
(out/'recovery.pid').write_text(str(p.pid));print('recovery started',p.pid,flush=True)
