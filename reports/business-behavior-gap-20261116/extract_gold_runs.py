import json,hashlib,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parent
new=json.loads((ROOT/'manifest.json').read_text())
old=json.loads((ROOT/'previous-manifest.json').read_text())
cases=new['nonkill']+new['controls']+old['nonkill']
for project in sorted({x['project'] for x in cases}):
 ids={x['instance_id'] for x in cases if x['project']==project}
 kit=next((Path('/root/lby-docker/req2test/user/benchmark/kits')/project).iterdir())
 source=kit/'behaviour/gold_run.jsonl.zst'
 proc=subprocess.Popen(['zstd','-dc',str(source)],stdout=subprocess.PIPE,text=True)
 count=0
 for line in proc.stdout:
  row=json.loads(line)
  if row.get('item_id') in ids:
   key=hashlib.sha256(row['item_id'].encode()).hexdigest()[:20]
   dest=ROOT/'gold-execution'/f'{key}.json';dest.parent.mkdir(exist_ok=True)
   dest.write_text(json.dumps(dict(source=str(source),record=row),indent=2));count+=1
 assert proc.wait()==0
 print(project,count,len(ids),flush=True)
