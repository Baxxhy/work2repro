import pathlib,json,shutil,hashlib
root=pathlib.Path(__file__).resolve().parent
selection=json.loads((root/'selection.json').read_text())
home=pathlib.Path('/root/lby-docker/req2test/user')
reqrun=home/'benchmark/runs/req2test-recovery8-20261113-v1'
index=[]
def copy(source,dest):
 if source.is_file():
  dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest)
  index.append(dict(source=str(source),destination=str(dest.relative_to(root)),bytes=dest.stat().st_size,sha256=hashlib.sha256(dest.read_bytes()).hexdigest()))
for n,case in enumerate(selection,1):
 d=root/'cases'/f'{n:02d}';d.mkdir(parents=True,exist_ok=True)
 iid=case['instance_id'];a=case['artifact']
 (d/'case.json').write_text(json.dumps(case,indent=2))
 if case['benchmark']=='testsuitebench':
  src=pathlib.Path(a['original_record'])
  for p in src.glob('*.test_eval.json'):copy(p,d/'official-test-eval.json')
  for p in src.glob('*.failure_matrix.csv'):copy(p,d/'failure-matrix.csv')
  for p in (src/'tests_untar').rglob('*'):
   if p.is_file() and p.suffix in ('.py','.sh','.txt','.json','.toml','.cfg','.md'):copy(p,d/'generated'/p.relative_to(src/'tests_untar'))
  spec=pathlib.Path('/root/Baxxhy/work2/benchmarks/testsuitebench/ground_truth/spec')
  for p in spec.glob(iid+'*'):
   if p.is_file():copy(p,d/'requirements'/p.name)
 else:
  copy(pathlib.Path(a['original_record']),d/'prediction.jsonl')
  if a.get('original_trace'):copy(pathlib.Path(a['original_trace']),d/'generation-trace.jsonl')
  project=case['metrics']['project']
  for line in (home/'tasks'/(project+'.eval.jsonl')).read_text().splitlines():
   row=json.loads(line)
   if row['instance_id']==iid:(d/'task.json').write_text(json.dumps(row,indent=2))
  source=reqrun/project/'th'
  for name in ['exec.jsonl','instances.jsonl','mutation.baseline.jsonl']:
   p=source/name
   if p.exists():
    rows=[json.loads(l) for l in p.read_text().splitlines() if l.strip()]
    rows=[r for r in rows if r.get('instance_id',r.get('item_id'))==iid]
    (d/name).write_text(''.join(json.dumps(r)+'\n' for r in rows))
  mutations=[]
  for p in sorted((source/'mutation').glob('*.jsonl')):
   for line in p.read_text().splitlines():
    if line.strip():
     row=json.loads(line)
     if row.get('instance_id',row.get('item_id'))==iid:mutations.append(row)
  (d/'mutation-records.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in mutations))
 print('EXTRACTED',n,iid,flush=True)
(root/'extraction-index.json').write_text(json.dumps(index,indent=2))
