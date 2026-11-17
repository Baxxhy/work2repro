from pathlib import Path
import json,collections
p=Path('/root/Baxxhy/work2/reproductions/req2test/req2test-eval2051-resume-20261117-v1/concurrency-recovery-20261117-135859/mutation-raw')
rows=[]
def messages(x):
 if isinstance(x,dict):
  for k,v in x.items():
   if k=='message' and isinstance(v,str):yield v
   elif k not in ('commands','stdout'):yield from messages(v)
 elif isinstance(x,list):
  for v in x:yield from messages(v)
for f in p.rglob('failure.json'):
 d=json.loads(f.read_text())
 rows.append(dict(path=str(f),mutant=d.get('mutation',{}).get('descriptor'),messages=[s[-400:] for s in messages(d)]))
Path('/tmp/r2t-failure-summary.json').write_text(json.dumps(rows,indent=2))
print('failures',len(rows))
