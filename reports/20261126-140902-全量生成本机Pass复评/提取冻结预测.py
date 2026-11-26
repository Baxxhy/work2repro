import hashlib, io, json, sys, tarfile
from collections import Counter
from pathlib import Path
base=Path('/root/lby-docker/req2test/user/runs')
names=['req2test-medium-full-20261123','req2test-medium-recovery313-20261126']
settle=Path('/root/Baxxhy/work2/reproductions/req2test')/names[1]
lineage=json.loads((settle/'final-lineage.json').read_text())
reference={j['instance_id']:j for line in (settle/'final-instances.jsonl').read_text().splitlines() if (j:=json.loads(line))}
assert len(lineage)==2051 and set(lineage)==set(reference)
inputs={}
for name in names:
 for f in (base/name/'input').glob('*.jsonl'):
  inputs[name+'-'+f.stem]={j['instance_id']:j for line in f.read_text().splitlines() if (j:=json.loads(line))}
def put(t,name,raw):
 item=tarfile.TarInfo(name); item.size=len(raw); t.addfile(item,io.BytesIO(raw))
with tarfile.open(mode='w|gz',fileobj=sys.stdout.buffer) as t:
 manifest=[]; merged=[]
 for i,v in sorted(lineage.items()):
  path=Path(v['source']).resolve(strict=True); rel=path.relative_to(base)
  assert rel.parts[0] in names and rel.parts[1]=='generation' and path.name=='predictions.jsonl'
  raw=path.read_bytes(); row=json.loads(raw)
  assert row==inputs[v['official_run']][i] and row['instance_id']==i and row['view']=='th' and row['model_name_or_path']=='codex-gpt-6-luna-medium'
  put(t,str(rel),raw); merged.append(raw.rstrip(b'\r\n')+b'\n')
  manifest.append(dict(instance_id=i,path=str(rel),sha256=hashlib.sha256(raw).hexdigest(),official_run=v['official_run']))
 put(t,'predictions.jsonl',b''.join(merged))
 put(t,'manifest.json',json.dumps(manifest,ensure_ascii=False).encode())
 for n in ['final-lineage.json','final-instances.jsonl','final-pass-at-1.json']:
  put(t,n,(settle/n).read_bytes())
