from pathlib import Path
import json,csv,hashlib,shutil,subprocess,time,collections
root=Path('/root/Baxxhy/work2/reproductions/req2test/req2test-eval2051-resume-20261117-v1');backup=root/'tail-recovery-20261118-v1';out=backup/'delivery-20261118';out.mkdir(exist_ok=True)
assert subprocess.check_output(['systemctl','show',root.name,'-p','ActiveState','--value'],text=True).strip()=='inactive'
assert json.loads((backup/'coddy-evidence-v2/exit.json').read_text())['returncode']==0
cfg=json.loads((root/'frozen/config.json').read_text());state=json.loads((root/'state.json').read_text());canonical=Path(cfg['req_home'])/'benchmark/runs'/cfg['req_run_id'];summary=json.loads((canonical/'summary.json').read_text());cells=summary['modes']['leaderboard']['cells'];mean=summary['modes']['leaderboard']['mean']['th'];assert mean['complete'] and len(cells)==8
manifest={t['id'] for t in state['tasks'].values()};rows=[];mutation_audit={};exec_audit={};affected=set()
for disclosure in summary['disclosures'].values():affected.update(disclosure.get('infrastructure_excluded',[]))
assert len(affected)==4

def table(folder):
 result={}
 for f in folder.glob('*.jsonl'):
  for line in f.read_text().splitlines():
   row=json.loads(line);key=(row['instance_id'],row['mutant_id']);
   if key in result:assert result[key]==row,'Conflicting duplicate mutation row'
   result[key]=row
 return result
for project in state['project_run_ids']:
 p=canonical/project/'th';project_rows=[json.loads(l) for l in (p/'instances.jsonl').read_text().splitlines() if l.strip()];rows+=project_rows
 old={r['item_id']:r for r in map(json.loads,(backup/'projects'/project/'exec.jsonl').read_text().splitlines())};new={r['item_id']:r for r in map(json.loads,(p/'exec.jsonl').read_text().splitlines())};assert set(old)==set(new)
 assert all(old[i]==new[i] for i in old if i not in affected),'Completed task execution changed'
 assert all(old[i]['produced_files']==new[i]['produced_files'] for i in old),'Generated tests changed'
 before=table(backup/'projects'/project/'mutation');after=table(p/'mutation');assert before==after,'Completed mutation rows changed'
 done=json.loads((p/'mutation.done.json').read_text());assert done['pairs']==len(after)
 mutation_audit[project]=dict(pairs=len(after),complete=True,unchanged=True)
 exec_audit[project]=dict(tasks=len(new),unchanged_completed=sum(i not in affected for i in old),generation_bytes_unchanged=True)
assert len(rows)==len(manifest)==2051;ids=[r['instance_id'] for r in rows];assert len(set(ids))==2051 and set(ids)==manifest
rows.sort(key=lambda r:r['instance_id'])
shutil.copy2(canonical/'summary.json',out/'Req2Test官方全量汇总-11-18.json');shutil.copy2(canonical/'report.md',out/'Req2Test官方全量报告-11-18.md')
(out/'Req2Test全量逐任务指标-11-18.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
pop=summary['population']['excluded'];outside={i:v for d in summary['disclosures'].values() for i,v in d.get('outside_ladder_excluded',{}).items()}
with (out/'逐任务状态与排除原因-11-18.csv').open('w',newline='') as f:
 fields=['instance_id','project','outcome','engine_outcome','passed','kill_complete','api_f1','coverage_j','recall','disposition','exclusion_reason'];w=csv.DictWriter(f,fields,lineterminator='\n');w.writeheader()
 for r in rows:
  iid=r['instance_id'];kind='population_excluded' if iid in pop else ('infrastructure_excluded' if iid in affected else ('outside_ladder_excluded' if iid in outside else 'scored'))
  reason=pop.get(iid,outside.get(iid,'')) or (r.get('engine_outcome','') if iid in affected else '')
  w.writerow({**{k:r.get(k) for k in fields if k in r},'disposition':kind,'exclusion_reason':reason})
with (out/'各项目指标与分母-11-18.csv').open('w',newline='') as f:
 fields=['project','manifest_tasks','protocol_population','pass_denominator','kill_complete_denominator','infrastructure_excluded','outside_ladder_excluded','passes','kill_complete','Pass@1','KillComplete@1','API_F1','Coverage_J','Mutation_R'];w=csv.DictWriter(f,fields,lineterminator='\n');w.writeheader()
 for key,c in cells.items():
  project=c['project'];d=summary['disclosures'].get(key,{});w.writerow(dict(project=project,manifest_tasks=exec_audit[project]['tasks'],protocol_population=c['n'],pass_denominator=c['n']-c['excluded'],kill_complete_denominator=c['n'],infrastructure_excluded=len(d.get('infrastructure_excluded',[])),outside_ladder_excluded=len(d.get('outside_ladder_excluded',{})),passes=c['passes'],kill_complete=c['kill_complete'],**{'Pass@1':c['pass_at_1'],'KillComplete@1':c['kill_complete_at_1'],'API_F1':c['api_f1'],'Coverage_J':c['coverage_j'],'Mutation_R':c['mutation_recall']}))
checks=dict(time=time.time(),all_manifest_ids_have_results=True,manifest_total=2051,missing=[],extra=[],official_summary_complete=True,protocol_population=sum(c['n'] for c in cells.values()),population_excluded=len(pop),infrastructure_excluded=len(affected),outside_ladder_excluded=len(outside),pass_denominator_total=sum(c['n']-c['excluded'] for c in cells.values()),kill_complete_denominator_total=sum(c['n'] for c in cells.values()),completed_executions_preserved=sum(x['unchanged_completed'] for x in exec_audit.values()),all_generation_bytes_preserved=True,mutations=mutation_audit,projects=exec_audit,headline=mean,normal_success_for_every_task=False)
(out/'全量完整性与结果保护核对-11-18.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n')
(out/'运行配置摘要-11-18.json').write_text(json.dumps({k:cfg.get(k) for k in ['model','reasoning','codex_version','req_commit','req_task_count','req_generation_timeout','req_llm_call_budget','timeout_profile','recorder_profile','recovery_profile','coddy_eval_workers','eval_worker_max']},indent=2)+'\n')
# Preserve final logs and concise per-case native evidence, without large caches.
for source,name in [(root/'jobs/3ad7b05c87e24f9f9df636e4d5996a1b/job.log','PrestaShop尾项补跑日志-11-18.txt'),(backup/'coddy-evidence-v2/job.log','Coddy尾项补跑日志-11-18.txt')]:shutil.copy2(source,out/name)
diags=Path(cfg['req_output'])/'evaluation-diagnostics/tail-native';evidence=[]
for d in diags.glob('*'):
 if not (d/'capture').exists():continue
 context=json.loads((d/'selected-context.json').read_text());record=dict(instance_id=context['instance_id'])
 for n in d.glob('capture/*'):
  for name,key in [('stdout.txt','stdout'),('native.jsonl','native')]:
   if (n/name).exists():record[key]=(n/name).read_text()
 if (d/'exception.json').exists():record['exception']=json.loads((d/'exception.json').read_text())
 evidence.append(record)
(out/'Coddy两条原生执行证据-11-18.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(checks,ensure_ascii=False,indent=2));print('EXPORT',out)
