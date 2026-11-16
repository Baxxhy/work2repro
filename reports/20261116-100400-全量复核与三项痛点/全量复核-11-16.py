import ast,collections,csv,hashlib,json,pathlib,statistics
R=next(p for p in pathlib.Path(__file__).resolve().parents if (p/'results/test-generation-20261114/task-artifacts.json').exists())
OUT=R/'reports/20261116-100400-全量复核与三项痛点'
OUT.mkdir(parents=True,exist_ok=True)
def readcsv(p): return list(csv.DictReader((R/p).open()))
def savecsv(name,rows):
 with (OUT/name).open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator="\n");w.writeheader();w.writerows(rows)
a=json.loads((R/'results/test-generation-20261114/task-artifacts.json').read_text())
tsb=readcsv('results/test-generation-20261114/reports/tsb-per-task.csv')
req=[json.loads(s) for s in (R/'results/test-generation-20261114/reports/req2test-per-task.jsonl').read_text().splitlines()]
population=json.loads((R/'results/test-generation-20261114/reports/req2test-denominators-and-exclusions.json').read_text())['official_population']['excluded']
old=readcsv('reports/20261116-091532-全案例比例复核/44条通过任务逐项复核-11-16.csv')
review={x['instance_id']:x for x in old}
metrics={('testsuitebench',x['instance_id']):x for x in tsb}
metrics.update({('req2test',x['instance_id']):x for x in req})
ledger=[];errors=[];hashes={};functions=[]
for x in a:
 b=x['benchmark'];id=x['instance_id'];m=metrics[b,id]
 folder=R/'results/test-generation-20261114'/b/'tasks'/x.get('artifact_id',id)/'generated'
 missing=[];mismatch=[]
 for f in x['generated_files']:
  p=folder/f['path']
  if not p.is_file(): missing.append(f['path']);continue
  h=hashlib.sha256(p.read_bytes()).hexdigest();hashes[str(p.relative_to(R))]=h
  if h!=f['sha256']: mismatch.append(f['path'])
  if b=='testsuitebench' and p.suffix=='.py':
   try: tree=ast.parse(p.read_text())
   except SyntaxError as e: errors.append({'file':str(p.relative_to(R)),'error':str(e)});continue
   for n in ast.walk(tree):
    if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name.startswith('test'):
     asserts=[z for z in ast.walk(n) if isinstance(z,ast.Assert)]
     functions.append({'instance_id':id,'file':str(p.relative_to(R)),'line':n.lineno,'function':n.name,'assert_count':len(asserts),'assertions':' | '.join(ast.unparse(z.test) for z in asserts)})
 r=review.get(id,{})
 ledger.append({'benchmark':b,'instance_id':id,'generation_status':x['generation_status'],'evaluation_status':x['evaluation_status'],'result':m.get('outcome','official_evaluated'),'excluded':population.get(id,m.get('exclusion','')),'validity':m.get('validity_rate',''),'mutation_score':m.get('mutation_score',''),'kill_complete':m.get('kill_complete',''),'files':len(x['generated_files']),'missing':';'.join(missing),'hash_mismatch':';'.join(mismatch),'semantic_review':r.get('classification','尚无全需求逐项复核'),'mechanism':r.get('mechanism','')})
assert len(ledger)==325 and len({(x['benchmark'],x['instance_id']) for x in ledger})==325
savecsv('325条任务完整性与分析状态-11-16.csv',ledger)
savecsv('TSB全部测试函数断言索引-11-16.csv',functions)
core=[r for r in old if r['classification']=='明确检查缺口' and r['instance_id'] not in {'e-petitions/features/admin/admin_access.feature:12','e-petitions/features/charlie_creates_a_petition.feature:56'}]
for r in core:
 r['pain']='结果观察' if r['project']=='sylius' else ('行为触发' if r['project'] in {'coddy-agent','coreshop'} or 'doc-add-section' in r['instance_id'] else '断言约束')
savecsv('八条业务缺口与主机制-11-16.csv',core)
summary={'population':{'tsb':len(tsb),'req':len(req),'req_scored':sum(x['instance_id'] not in population and not x['exclusion'] for x in req)},'req_outcomes':dict(collections.Counter(x['outcome'] for x in req)),'req_passed':sum(x['passed'] for x in req),'req_killcomplete':sum(x['kill_complete'] for x in req),'business_gaps':len(core),'business_projects':sorted({x['project'] for x in core}),'pain_counts':dict(collections.Counter(x['pain'] for x in core)),'pass_business_gap_fraction':len(core)/44,'tsb_mean_validity':statistics.mean(float(x['validity_rate']) for x in tsb),'tsb_mean_mutation':statistics.mean(float(x['mutation_score']) for x in tsb),'tsb_high_validity_low_mutation':sum(float(x['validity_rate'])>=.8 and float(x['mutation_score'])<.1 for x in tsb),'generated_files':len(hashes),'missing_files':sum(bool(x['missing']) for x in ledger),'hash_mismatch_tasks':sum(bool(x['hash_mismatch']) for x in ledger),'ast_functions':len(functions),'ast_errors':errors,'new_model_generations':0,'new_evaluations':0,'note':'AST索引用于定位代码，不代表完成每项需求的语义标注。'}
(OUT/'统计汇总-11-16.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
(OUT/'生成文件校验值-11-16.json').write_text(json.dumps(hashes,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summary,ensure_ascii=False,indent=2))
