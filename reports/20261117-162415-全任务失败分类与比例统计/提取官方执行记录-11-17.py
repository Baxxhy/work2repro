import json,pathlib,hashlib,collections
art=json.load(open('/tmp/empirical-artifacts.json'));out=[]
for a in art:
 if a['benchmark']!='testsuitebench':continue
 p=pathlib.Path(a['official_report']);d=json.loads(p.read_text());bs=d.get('binary_results',[])
 gold=next((b for b in bs if b.get('role')=='ground_truth' or b.get('binary_id')=='ground_truth'),{})
 tests=gold.get('test_results',[])
 out.append(dict(instance_id=a['instance_id'],source_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),gold={k:v for k,v in gold.items() if k!='test_results'},tests=tests,top_keys={k:v for k,v in d.items() if k!='binary_results'}))
pathlib.Path('/tmp/tsb-census-evidence.json').write_text(json.dumps(out,ensure_ascii=False));print('tasks',len(out),'test records',sum(len(x['tests']) for x in out))
