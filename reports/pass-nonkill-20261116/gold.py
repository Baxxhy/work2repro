import pathlib,json,tarfile,subprocess,io,shutil
root=pathlib.Path(__file__).resolve().parent;home=pathlib.Path('/root/lby-docker/req2test/user');manifest=json.loads((root/'manifest.json').read_text())
for project in sorted({x['project'] for x in manifest['nonkill']+manifest['controls']}):
 kit=next((home/'benchmark/kits'/project).iterdir());dirs=[]
 for d in sorted((root/'evidence').iterdir()):
  c=json.loads((d/'metrics.json').read_text())
  if c['project']==project:dirs.append(d)
 wanted={};missing=[]
 for d in dirs:
  side=json.loads((d/'reference-sidecars.json').read_text());paths=set()
  for s in side:
   record=s['record']
   if isinstance(record,dict) and record.get('item_id')==json.loads((d/'metrics.json').read_text())['instance_id']:
    paths.update(record.get('files',[]));paths.update([record['feature_file']] if record.get('feature_file') else [])
  wanted[d]=paths
 # Read only listed text members from existing archives or gold trees.
 for d,paths in wanted.items():
  for rel in paths:
   for prefix in ['exec/release/gold/tree','exec/release/gold_tree','exec/gold-tests','exec/seed/checked-v2','exec/seed']:
    src=kit/prefix/rel
    if src.is_file():
     target=d/'reference'/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,target);break
 archives=list((kit/'exec').glob('gold/*.tar'))+list((kit/'exec').glob('gold/*.tar.zst'))+list((kit/'exec').glob('release/gold/gold-*.tar.zst'))
 for arc in archives:
  if 'checked-v2' not in arc.name and any('checked-v2' in a.name for a in archives):continue
  raw=io.BytesIO(subprocess.check_output(['zstd','-dc',str(arc)])) if arc.suffix=='.zst' else None
  with tarfile.open(fileobj=raw,name=None if raw else str(arc),mode='r:') as tar:
   for member in tar:
    if not member.isfile() or member.size>2000000:continue
    for d,paths in wanted.items():
     for rel in paths:
      if member.name.lstrip('./')==rel or member.name.endswith('/'+rel):
       dest=d/'reference'/rel;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(tar.extractfile(member).read())
 for d,paths in wanted.items():
  found=[rel for rel in paths if (d/'reference'/rel).exists()];(d/'reference-extraction.json').write_text(json.dumps(dict(requested=sorted(paths),found=found,missing=sorted(paths-set(found))),indent=2));print(project,d.name,len(found),len(paths),flush=True)
