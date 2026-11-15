import pathlib,json,gzip,difflib
root=pathlib.Path(__file__).resolve().parent
hub=pathlib.Path('/root/Baxxhy/work2/datasets/testsuitebench/huggingface/hub')
mut=next((hub/'datasets--eth-sri--tsb-mutants/snapshots').iterdir())
ref=next((hub/'datasets--eth-sri--tsb-reference_impl/snapshots').iterdir())/'implementation'
for p in sorted((root/'cases').glob('*/official-test-eval.json')):
 d=p.parent;iid=json.loads((d/'case.json').read_text())['instance_id'];report=json.loads(p.read_text())
 ground=next(x for x in report['binary_results'] if x['role']=='ground_truth')
 valid={t['name'] for t in ground['test_results'] if t['status']=='passed'}
 survivors=[];controls=[]
 for b in report['binary_results']:
  if b['role']=='ground_truth':continue
  killed=any(t['name'] in valid and t['status'] in ('failure','failed','error') for t in b['test_results'])
  (controls if killed else survivors).append(b['binary_id'])
 metadata=json.loads((mut/iid/'mutants.json').read_text());sources=json.loads((mut/iid/'sources.json').read_text())
 chosen=set(survivors[:3]+controls[:1]);entries=[x for x in metadata['mutants'] if x['id'] in chosen]
 (d/'mutant-selection.json').write_text(json.dumps(dict(rule='first three surviving binary IDs plus first killed control, ordered as official report; provisional test-level selection',reference_passed_tests=sorted(valid),survivors=survivors,killed_controls=controls,selected=entries),indent=2))
 for m in entries:
  patches=[]
  for name,digest in sources['overlays'].get(m['id'],{}).items():
   blob=mut/iid/'.artifacts/sources'/digest[:2]/(digest+'.gz')
   if not blob.exists():blob=mut/iid/'.artifacts/sources'/(digest+'.gz')
   if not blob.exists():continue
   text=gzip.open(blob,'rt',errors='replace').read();base=ref/iid/name
   original=base.read_text(errors='replace') if base.is_file() else ''
   patches.extend(difflib.unified_diff(original.splitlines(True),text.splitlines(True),fromfile='reference/'+name,tofile=m['id']+'/'+name))
  (d/(m['id']+'.patch')).write_text(''.join(patches))
 print('MUTANT_EVIDENCE',d.name,len(entries),flush=True)
