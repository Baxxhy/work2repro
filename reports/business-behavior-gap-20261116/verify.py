"""Validate extraction and reports without executing benchmark tests."""
import csv
import hashlib
import json
import re
from pathlib import Path
ROOT=Path(__file__).resolve().parent
OLD=ROOT.parent/'pass-nonkill-20261116'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
checks={}
old=read(OLD/'evidence-hashes.json')
assert all(sha(OLD/name)==digest for name,digest in old.items())
checks['old_evidence_hashes_unchanged']=len(old)
old_reports=read(OLD/'protected-report-hashes.json')
assert all(sha(Path(name))==digest for name,digest in old_reports.items())
checks['earlier_discovery_reports_unchanged']=len(old_reports)
m=read(ROOT/'manifest.json');a=read(ROOT/'annotations.json')
assert len(m['nonkill'])==20 and len(m['controls'])==15
ids=[r['instance_id'] for r in m['nonkill']+m['controls']]
assert len(set(ids))==35 and not set(ids).intersection(m['excluded_prior_ids'])
files=0
for group in ['nonkill','controls']:
 for r in m[group]:
  k=hashlib.sha256(r['instance_id'].encode()).hexdigest()[:20];d=ROOT/'evidence'/k
  assert k in a['new' if group=='nonkill' else 'controls']
  e=read(d/'execution.json');task=read(d/'task.json')
  assert e['outcome']=='passed' and task['instance_id']==r['instance_id']
  assert r['passed'] and r['mutation_status']=='scored' and r['n_scored']>0
  assert bool(r['kill_complete'])==(group=='controls')
  prediction=read(d/'prediction.json');pred=next(p for p in prediction if p['instance_id']==r['instance_id'])
  for f in pred['files']:
   assert (d/'generated'/f['path']).read_text()==f['content'];files+=1
  for f in e['produced_files']:
   assert (d/'generated'/f['file_path']).read_text()==f['code']
  mutants=read(d/'mutation-results.json');surv=read(d/'surviving-mutants.json');gold=read(d/'reference-kills.json')
  assert len({x['mutant_id'] for x in mutants})==len(mutants)
  passed={x['mutant_id'] for x in mutants if x['outcome']=='passed'}
  assert {x['id'] for x in surv}==passed and len(passed)==r['n_scored']-r['n_killed']
  assert passed <= {x['mutant_id'] for x in gold if x['gold_outcome']=='killed'}
  assert read(ROOT/'gold-execution'/f'{k}.json')['record']['item_id']==r['instance_id']
checks['new_tasks_verified']=35;checks['prediction_and_execution_files_match']=files
pairs=list(csv.DictReader((ROOT/'MUTANT_LEVEL_EVIDENCE.csv').open()))
assert len(pairs)==833 and len({(r['instance_id'],r['mutant_id']) for r in pairs})==833
for r in pairs:
 assert r['gold_outcome']=='killed' and r['candidate_outcome']=='passed'
checks['old_pairs_verified']=833
for d in (ROOT/'cases').iterdir():
 c=read(d/'case.json')
 for f in c['artifact']['generated_files']:
  assert sha(d/'generated/eval'/f['path'])==f['sha256']
checks['tsb_generated_matches_published_hashes']=6
reports=['BUSINESS_BEHAVIOR_GAP_ANALYSIS.md','MUTANT_LEVEL_EVIDENCE.csv','CROSS_PROJECT_VALIDATION.md','TSB_CROSS_VALIDATION.md','RESEARCH_MOTIVATION_CANDIDATES.md']
for name in reports:
 assert (ROOT/name).stat().st_size>100
for name in [x for x in reports if x.endswith('.md')]:
 for path in re.findall(r'\]\((/root/[^)]+)\)',(ROOT/name).read_text()):
  assert Path(path).exists(),path
checks['deliverables_present']=reports
checks['new_benchmark_execution']=False
checks['semantic_verification']='manual single-reviewer; per-mutant failing trace unavailable; no intervention'
checks['status']='passed'
(ROOT/'verification.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n')
hashes={str(p.relative_to(ROOT)):sha(p) for p in sorted(ROOT.rglob('*')) if p.is_file() and p.name not in ['evidence-hashes.json'] and '__pycache__' not in p.parts}
(ROOT/'evidence-hashes.json').write_text(json.dumps(hashes,indent=2)+'\n')
print(json.dumps(checks,ensure_ascii=False,indent=2))
