from pathlib import Path
import json,collections,sys,datetime
r=Path(sys.argv[1] if len(sys.argv)>1 else '/root/Baxxhy/work2/reproductions/testupdater/runs/luna-full-20261105')
out={'checked_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'run':str(r)}
if (r/'status.json').exists():out.update(json.loads((r/'status.json').read_text()));out['process_alive']=Path('/proc',str(out.get('pid'))).exists()
for ds in ['updates4j','prbench']:
 states=[];counts=collections.Counter()
 for p in sorted((r/ds).glob('*/status.json')):states.append(json.loads(p.read_text()))
 for p in (r/ds).glob('*/samples/*.json'):counts[json.loads(p.read_text()).get('execution_status','unknown')]+=1
 out[ds]={'projects':states,'results':dict(counts),'completed':sum(counts.values())}
print(json.dumps(out,ensure_ascii=False,indent=2))
