"""Idempotent statistics over immutable snapshots, without model calls."""
import collections,csv,datetime,hashlib,json,pathlib,shutil
ROOT=pathlib.Path(__file__).resolve().parent
PUB=ROOT.parents[1]/'publication/work2repro/results/test-generation-20261114'

def write_csv(path,rows,fields=None):
 fields=fields or list(rows[0])
 temporary=path.with_suffix('.tmp')
 with temporary.open('w',newline='') as f:
  writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(rows)
 temporary.replace(path)

def candidate(row):
 if row['benchmark']=='testsuitebench':
  if row.get('validity_rate',0)==0:return 'no_reference_passing_tests'
  if row.get('n_mutants_killed',0)<row.get('n_mutants',0):return 'valid_tests_with_survivors'
  return 'all_mutants_killed_control'
 if row.get('exclusion_reason'):return 'officially_excluded'
 if not row.get('passed'):return 'execution_'+row.get('outcome','unknown')
 if row.get('kill_complete'):return 'killcomplete_control'
 if row.get('n_scored',0)>row.get('n_killed',0):return 'passing_with_survivors'
 return 'passing_mutation_unresolved'

snapshot=ROOT/'snapshots'/(ROOT/'latest-snapshot.txt').read_text().strip()
data=json.loads(snapshot.read_text())
assert not data['missing_completed_rows'],data['missing_completed_rows']
backup=ROOT/'preserved-before-incremental';backup.mkdir(exist_ok=True)
for name in ['TASK_INVENTORY.csv','PROBLEM_DISCOVERY_REPORT.md','INITIAL_AUDIT.json']:
 if (ROOT/name).exists() and not (backup/name).exists():shutil.copy2(ROOT/name,backup/name)
rows=[]
for row in json.loads((PUB/'reports/tsb-official-summary.json').read_text())['summaries']:
 rows.append(dict(row,benchmark='testsuitebench',project=row['instance_id'].split('.')[0],requirement_type='complete_software_specification',evaluation_status='finished',exclusion_reason='',source='published_165'))
for row in data['rows']:
 meta=data['requirements'][row['instance_id']]
 rows.append(dict(row,benchmark='req2test',requirement_type=meta['requirement_type'],evaluation_status='finished',exclusion_reason=data['exclusions'].get(row['instance_id'],''),source=row['_source']))
keys=[r['benchmark']+'|'+r['instance_id'] for r in rows];assert len(keys)==len(set(keys))
fields=['benchmark','instance_id','project','requirement_type','evaluation_status','scored','candidate','semantic_status','passed','outcome','validity_rate','mutation_score','recall','kill_complete','n_mutants','n_mutants_killed','n_scored','n_killed','n_dropped','exclusion_reason','source']
flat=[]
for row in rows:
 item={k:row.get(k,'') for k in fields};item.update(scored=not bool(row['exclusion_reason']),candidate=candidate(row),semantic_status='unreviewed');flat.append(item)
oldpath=ROOT/'incremental_progress.json';previous=json.loads(oldpath.read_text()) if oldpath.exists() else {}
fingerprints={r['benchmark']+'|'+r['instance_id']:hashlib.sha256(json.dumps(r,sort_keys=True).encode()).hexdigest() for r in flat}
old=previous.get('row_fingerprints',{});added=sorted(set(fingerprints)-set(old));changed=sorted(k for k in set(old)&set(fingerprints) if old[k]!=fingerprints[k]);removed=sorted(set(old)-set(fingerprints));assert not removed,removed
write_csv(ROOT/'incremental_metrics.csv',flat,fields)
groups=collections.defaultdict(list)
for row in flat:
 for level,key in [('benchmark',row['benchmark']),('project',row['project']),('requirement_type',row['requirement_type'])]:groups[(row['benchmark'],level,key)].append(row)
stats=[]
for (bench,level,key),members in sorted(groups.items()):
 eligible=[x for x in members if x['scored']]
 for c,n in sorted(collections.Counter(x['candidate'] for x in members).items()):
  selected=[x for x in eligible if x['candidate']==c]
  stats.append(dict(benchmark=bench,grouping=level,group=key,candidate=c,completed_tasks=len(members),scored_tasks=len(eligible),candidate_tasks=n,candidate_scored_tasks=len(selected),fraction_of_completed=n/len(members),fraction_of_scored=len(selected)/len(eligible) if eligible else '',interpretation='observable screening category; semantic mechanism unconfirmed'))
write_csv(ROOT/'incremental_project_statistics.csv',stats)
counts={b:dict(completed=sum(r['benchmark']==b for r in flat),scored=sum(r['benchmark']==b and r['scored'] for r in flat)) for b in ['testsuitebench','req2test']}
observed=sorted({r['candidate'] for r in flat});novel=sorted(set(observed)-set(previous.get('observed_candidates',[])))
now=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()
progress=dict(updated=now,snapshot=str(snapshot.relative_to(ROOT)),counts=counts,req_eval_manifest_total=2051,req_completion_fraction=counts['req2test']['completed']/2051,controller_states=data['progress']['tasks']['req2test'],added_ids=added,changed_ids=changed,new_screening_categories=novel,observed_candidates=observed,row_fingerprints=fingerprints,semantic_confirmed=0,semantic_unknown=len(flat),model_calls=0,denominator_note='Only finished tasks with official rows. Population exclusions removed from scored denominator. TSB validity is test-level; partial validity does not imply a wholly passing suite.')
reviews=[json.loads(p.read_text()) for p in (ROOT/'semantic_batches').glob('*/*/analysis.json')]
progress['semantic_reviewed_cases']=len({r['instance_id'] for r in reviews})
progress['semantic_confirmed_failure_cases']=sum(r['evidence_level']=='已证实' and r['label']!='成功对照' for r in reviews)
progress['semantic_confirmed']=progress['semantic_confirmed_failure_cases']
progress['semantic_unknown']=len(flat)-len({r['instance_id'] for r in reviews if any(x['instance_id']==r['instance_id'] for x in flat)})
oldpath.write_text(json.dumps(progress,indent=2))
if added or changed or not (ROOT/'incremental_analysis_log.md').exists():
 with (ROOT/'incremental_analysis_log.md').open('a') as f:f.write(f'\n## {now}\n\n新增 {len(added)} 条，既有记录变化 {len(changed)} 条。当前完成及计分数量 {json.dumps(counts)}。新增筛选类别 {json.dumps(novel)}。语义原因需要单独确认。\n')
selection_path=ROOT/'semantic_selection.json'
if not selection_path.exists():
 prior=json.loads((ROOT.parent/'failure-mechanisms-20261115/selection.json').read_text());selection=[];seen=set()
 for item in prior:
  key=item['benchmark']+'|'+item['instance_id'];seen.add(key);selection.append(dict(benchmark=item['benchmark'],instance_id=item['instance_id'],stratum=item['stratum'],source='prior_40_published_baseline',analysis_status='reuse_existing_evidence; semantic_review_pending',evidence_directory=str(ROOT.parent/'failure-mechanisms-20261115/cases'/f'{len(selection)+1:02d}')))
 pools=collections.defaultdict(list)
 for r in flat:
  key=r['benchmark']+'|'+r['instance_id']
  if key not in seen and r['scored']:pools[(r['benchmark'],r['candidate'])].append(r)
 for pool in pools.values():pool.sort(key=lambda r:hashlib.sha256(('incremental-20261116|'+r['instance_id']).encode()).hexdigest())
 projects=collections.Counter()
 preferred=sorted(pools,key=lambda k:('survivors' not in k[1], 'control' not in k[1],k))
 while len(selection)<60 and any(pools.values()):
  for k in preferred:
   if not pools[k] or len(selection)>=60:continue
   r=min(pools[k],key=lambda x:projects[x['project']]);pools[k].remove(r);projects[r['project']]+=1
   selection.append(dict(benchmark=r['benchmark'],instance_id=r['instance_id'],stratum=r['candidate'],source='completed_snapshot',analysis_status='pending',evidence_directory=''))
 selection_path.write_text(json.dumps(dict(rule='retain prior 40; add 20 deterministic SHA256-ranked stratified round-robin tasks, favour underrepresented projects; purposive sample, no prevalence inference',cases=selection),indent=2))
print(json.dumps(dict(counts=counts,added=len(added),changed=len(changed),selected=len(json.loads(selection_path.read_text())['cases'])),indent=2))
