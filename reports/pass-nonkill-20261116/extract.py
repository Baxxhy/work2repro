import pathlib,json,subprocess,collections,hashlib
root=pathlib.Path(__file__).resolve().parent;manifest=json.loads((root/'manifest.json').read_text());home=pathlib.Path('/root/lby-docker/req2test/user');run=home/'benchmark/runs/req2test-recovery8-20261113-v1'
def read(p):
 if not p.exists():return []
 text=subprocess.check_output(['zstd','-dc',str(p)],text=True) if p.suffix=='.zst' else p.read_text()
 return [json.loads(l) for l in text.splitlines() if l.strip()]
def save(p,obj):
 p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,ensure_ascii=False,indent=2))
for project in sorted({x['project'] for x in manifest['nonkill']+manifest['controls']}):
 cases=[x for x in manifest['nonkill']+manifest['controls'] if x['project']==project];ids={x['instance_id'] for x in cases}
 kit=next((home/'benchmark/kits'/project).iterdir());tasks={x['instance_id']:x for x in read(home/'tasks'/(project+'.eval.jsonl')) if x['instance_id'] in ids}
 mm=json.loads(subprocess.check_output(['zstd','-dc',str(kit/'mutation/manifest.json.zst')],text=True));mutants={x['id']:x for x in mm['mutants']}
 pools=collections.defaultdict(list)
 for row in read(kit/'mutation/pools.jsonl.zst'):
  if row.get('item_id') in ids:pools[row['item_id']].append(row)
 mutation={}
 for p in sorted((run/project/'th/mutation').glob('*.jsonl')):
  for row in read(p):
   if row.get('instance_id') in ids:mutation[(row['instance_id'],row['mutant_id'])]=row
 execution={x['item_id']:x for x in read(run/project/'th/exec.jsonl') if x.get('item_id') in ids}
 # Release sidecars carry the developer test implementation and item identity.
 gold=collections.defaultdict(list)
 for p in (kit/'exec/release').rglob('*.json'):
  text=p.read_text(errors='replace')
  for iid in ids:
   if iid in text:
    try:gold[iid].append(dict(source=str(p),record=json.loads(text)))
    except ValueError:pass
 for c in cases:
  iid=c['instance_id'];key=hashlib.sha256(iid.encode()).hexdigest()[:20];d=root/'evidence'/key
  save(d/'task.json',tasks[iid]);save(d/'metrics.json',c)
  pred=read(pathlib.Path(c['artifact']['original_record']));save(d/'prediction.json',pred)
  save(d/'execution.json',execution.get(iid))
  records=[row for (item,_),row in mutation.items() if item==iid];save(d/'mutation-results.json',records)
  survivors={row['mutant_id'] for row in records if row['outcome']=='passed'}
  save(d/'surviving-mutants.json',[mutants[mid] for mid in sorted(survivors) if mid in mutants])
  save(d/'reference-kills.json',[row for row in pools[iid] if row['mutant_id'] in survivors])
  save(d/'reference-sidecars.json',gold[iid])
  for row in pred:
   for f in row['files']:
    p=d/'generated'/f['path'];p.parent.mkdir(parents=True,exist_ok=True);p.write_text(f['content'])
  print(project,key,'survivors',len(survivors),'sidecars',len(gold[iid]),flush=True)
