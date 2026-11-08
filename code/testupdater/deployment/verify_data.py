from pathlib import Path
import json,subprocess,collections
r=Path('/root/Baxxhy/work2/reproductions/testupdater');rows=[]
for dataset in ['updates4j','prbench']:
 for f in sorted((r/'datasets'/dataset).glob('*.json')):
  ds=json.loads(f.read_text());repo=r/'repos'/ds[0]['repo_name'];errors=[]
  for i,d in enumerate(ds):
   if not (repo/'.git').exists():errors.append({'index':i,'error':'clone_not_ready'});continue
   proc=subprocess.run(['git','-C',str(repo),'show',d['commit_tgt']+':'+d['changed_test'].split('#')[0]],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
   if proc.returncode:errors.append({'index':i,'error':'target_missing'});continue
   if proc.stdout.count(d['test_code_tgt'])!=1:errors.append({'index':i,'error':'reference_not_unique','count':proc.stdout.count(d['test_code_tgt'])})
  row={'dataset':dataset,'project':ds[0]['repo_name'],'count':len(ds),'errors':errors};rows.append(row);print(json.dumps(row),flush=True)
(r/'data-verification.json').write_text(json.dumps(rows,indent=2))
