"""Collect official outputs and check every full-eval ID without rescoring."""
import collections,csv,hashlib,json,pathlib,shutil,sys
root=pathlib.Path(sys.argv[1]);cfg=json.loads((root/'frozen/config.json').read_text());state=json.loads((root/'state.json').read_text())
out=root/'reports';out.mkdir(exist_ok=True)
official=pathlib.Path(cfg['req_home'])/'benchmark/runs'/cfg['req_run_id']
for source,target in [('summary.json','req2test-official-summary.json'),('report.md','req2test-official-report.md')]:
 if (official/source).exists():shutil.copy2(official/source,out/target)
summary=json.loads((official/'summary.json').read_text())
cells=summary.get('modes',{}).get('leaderboard',{}).get('cells',{})
(out/'req2test-per-project.json').write_text(json.dumps(cells,indent=2))
(out/'req2test-denominators-and-exclusions.json').write_text(json.dumps(dict(manifest_total=cfg['req_task_count'],population=summary.get('population'),cells=cells,disclosures=summary.get('disclosures')),indent=2))
rows=[];seen=set();counts=collections.Counter()
for p in sorted(official.glob('*/th/instances.jsonl')):
 for line in p.read_text().splitlines():
  if not line.strip():continue
  row=json.loads(line);iid=row['instance_id'];assert iid not in seen,iid
  seen.add(iid);rows.append(row);counts[p.parent.parent.name]+=1
(out/'req2test-per-task.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
ids={t['id'] for t in state['tasks'].values()}
audit=dict(unique_ids=len(seen),manifest_total=len(ids),missing=sorted(ids-seen),extra=sorted(seen-ids),per_project=dict(counts))
(out/'req2test-scored-id-audit.json').write_text(json.dumps(audit,indent=2))
reused=json.loads((root/'frozen/current-generation-reuse.json').read_text())
for entry in reused:
 assert hashlib.sha256(pathlib.Path(entry['prediction']).read_bytes()).hexdigest()==entry['sha256']
assert not audit['missing'] and not audit['extra'],audit
print(json.dumps(dict(all_ids_accounted_for=True,official_rows=len(rows),reused_generations=len(reused)),indent=2))
