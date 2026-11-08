"""Read actual task status without interpreting quality thresholds as test passes."""
from pathlib import Path
import argparse,json,collections,datetime
p=argparse.ArgumentParser();p.add_argument('run_dir',type=Path);a=p.parse_args();root=a.run_dir
out={'time':datetime.datetime.now(datetime.timezone.utc).isoformat(),'run_dir':str(root),'results':{},'workers':[]}
if (root/'status.json').exists():
 d=json.loads((root/'status.json').read_text());out['state']=d['state'];out['pid']=d.get('pid');out['process_alive']=Path('/proc',str(d.get('pid'))).exists()
if (root/'run-manifest.json').exists():
 d=json.loads((root/'run-manifest.json').read_text());out['selected_count']=d['selected_count'];out['configured_workers']=d['workers']
counts=collections.Counter()
for f in root.glob('projects/*/*/samples/*.json'):
 d=json.loads(f.read_text());counts[d.get('test_status',d.get('state','unknown'))]+=1
out['results']=dict(counts)
for f in root.glob('projects/*/*/progress.json'):
 d=json.loads(f.read_text());project='/'.join(f.parts[-3:-1]);out['workers'].append({'project':project,'state':d['state'],'pid':d.get('pid'),'alive':Path('/proc',str(d.get('pid'))).exists(),'sample_id':d.get('sample_id'),'completed':d.get('completed'), 'statuses':d.get('statuses')})
print(json.dumps(out,ensure_ascii=False,indent=2))
