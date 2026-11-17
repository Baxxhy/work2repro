from pathlib import Path
import json,csv,hashlib,re,collections,ast
OUT=Path(__file__).resolve().parent
repo=next((p for p in OUT.parents if (p/'results/test-generation-20261114').exists()),None)
if repo is None:repo=next(p for p in OUT.parents if (p/'publication/work2repro').exists())/'publication/work2repro'
b=repo/'results/test-generation-20261114';arts=json.loads((b/'task-artifacts.json').read_text())
rows=[];gen=[]
for a in arts:
 iid=a['instance_id'];bench=a['benchmark'];safe=iid if bench=='testsuitebench' else hashlib.sha256(iid.encode()).hexdigest()[:20];p=b/bench/'tasks'/safe
 f=p/'trajectory-excerpt.json';d=json.loads(f.read_text());ev=d.get('events',[])
 commands=[e.get('item',{}) for e in ev if e.get('type')=='item.completed' and e.get('item',{}).get('type')=='command_execution']
 messages=[e['item']['text'] for e in ev if e.get('item',{}).get('type')=='agent_message']
 files=[]
 for ff in sorted((p/'generated').rglob('*')):
  if ff.is_file():files.append({'path':str(ff.relative_to(repo)),'sha256':hashlib.sha256(ff.read_bytes()).hexdigest()})
 rows.append(dict(benchmark=bench,instance_id=iid,generated_files=len(files),file_hashes=json.dumps(files,ensure_ascii=False),trajectory=str(f.relative_to(repo)),trace_sha256=hashlib.sha256(f.read_bytes()).hexdigest(),complete_trace=d.get('complete_trace'),completed_command_count=len(commands),command_nonzero=sum(c.get('exit_code') not in (0,None) for c in commands),last_agent_message=re.sub(r'/root/[^\s)\]]+','[实验目录]',messages[-1]) if messages else '',note='命令计数基于发布节选，不代表完整调用次数'))
 if bench=='req2test' and not files:
  msg=messages[-1] if messages else ''
  gen.append(dict(instance_id=iid,observed_reason='API测试与表单提示契约不匹配' if 'editing_catalog_promotion' in iid else 'Agent表示未能重建所需准备及业务上下文',actual_status='没有交付接受范围内的文件',agent_final_message=re.sub(r'/root/[^\s)\]]+','[实验目录]',msg),confidence='Agent自述与未交付结果一致；信息客观不可得尚未证实'))
for name,data in [('325条代码与轨迹索引-11-17.csv',rows),('15条未交付原因与轨迹-11-17.csv',gen)]:
 with (OUT/name).open('w') as f:w=csv.DictWriter(f,fieldnames=list(data[0]),lineterminator='\n');w.writeheader();w.writerows({k:'\n'.join(line.rstrip() for line in str(v).split('\n')) if isinstance(v,str) else v for k,v in row.items()} for row in data)
print('all tasks indexed',len(rows),'generation failures',len(gen))
