import json,tarfile,gzip,difflib,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parent
hub=Path('/root/Baxxhy/work2/datasets/testsuitebench/huggingface/hub')
mut=next((hub/'datasets--eth-sri--tsb-mutants/snapshots').iterdir())
ref=next((hub/'datasets--eth-sri--tsb-reference_impl/snapshots').iterdir())/'implementation'
for d in sorted((ROOT/'cases').iterdir()):
 iid=json.loads((d/'case.json').read_text())['instance_id']
 (d/'requirements').mkdir(exist_ok=True)
 shutil.copyfile(Path('/root/Baxxhy/work2/benchmarks/testsuitebench/ground_truth/spec')/iid/'spec.md',d/'requirements/spec.md')
 sources=json.loads((mut/iid/'sources.json').read_text())
 selected=json.loads((d/'mutant-selection.json').read_text())['selected']
 wanted={name for m in selected for name in sources['overlays'].get(m['id'],{})}
 original={}
 with tarfile.open(ref/(iid+'.tar.gz')) as tar:
  for member in tar:
   if not member.isfile():continue
   for name in wanted:
    if member.name==name or member.name.endswith('/'+name):original[name]=tar.extractfile(member).read().decode(errors='replace')
 missing=wanted-original.keys()
 (d/'reference-source-audit.json').write_text(json.dumps(dict(archive=str(ref/(iid+'.tar.gz')),found=sorted(original),added_files=sorted(missing)),indent=2))
 for name in missing:original[name]=''
 for m in selected:
  patches=[]
  for name,digest in sources['overlays'].get(m['id'],{}).items():
   blob=mut/iid/'.artifacts/sources'/digest[:2]/(digest+'.gz')
   if not blob.exists():blob=mut/iid/'.artifacts/sources'/(digest+'.gz')
   text=gzip.open(blob,'rt',errors='replace').read()
   patches.extend(difflib.unified_diff(original[name].splitlines(True),text.splitlines(True),fromfile='reference/'+name,tofile=m['id']+'/'+name))
  (d/(m['id']+'.patch')).write_text(''.join(patches))
 print(iid,len(wanted),'source files based on existing reference archive',flush=True)
