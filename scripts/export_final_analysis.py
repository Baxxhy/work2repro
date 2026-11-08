"""Export compact final analysis inputs, outputs, metrics, and reproduction code."""
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tarfile

ROOT=Path('/root/Baxxhy/work2/reproductions')
SOURCE=ROOT/'comparison/metrics-20261108'
OUT=Path('/root/Baxxhy/work2/repro-final-analysis-20261109')
OUT.mkdir(exist_ok=True)
TOKEN=re.compile(r'(?<![A-Za-z0-9])(?:sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,}|eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)')
redactions=[]
def write_json(path,value):
 path.parent.mkdir(parents=True,exist_ok=True)
 text=json.dumps(value,ensure_ascii=False,indent=2)
 sanitized=TOKEN.sub('[REDACTED_CREDENTIAL]',text)
 if sanitized!=text:redactions.append(str(path.relative_to(OUT)))
 path.write_text(sanitized)

inputs={};outputs={};table=[]
for jobfile in sorted((SOURCE/'jobs').glob('*.json')):
 for job in json.loads(jobfile.read_text()):
  dataset=job['dataset'];method=job['method'];project=job['project'];index=job['index'];key=f'{dataset}:{project}:{index}'
  inputs[key]={'sample_id':key,'dataset':dataset,'project':project,'index':index,**job['sample']}
  metric_path=SOURCE/'results'/method/dataset/project/f'{index:04d}.json'
  metrics=json.loads(metric_path.read_text()) if metric_path.exists() else {}
  coverage=(metrics.get('coverage') or {}).get('coverage_info') or {}
  mutation=(metrics.get('mutation') or {}).get('mutation_info') or {}
  original_status=job['original_status']
  if method=='TestSyncer' and dataset=='prbench' and project=='apache/druid' and index==32:original_status='generation_failure'
  row={'sample_id':key,'method':method,'dataset':dataset,'project':project,'index':index,'generation_status':original_status,'test_passed':job['original_passed'],'metric_state':metrics.get('state','missing'),'line_coverage':coverage.get('line_coverage_percentage'),'covered_lines':coverage.get('covered_lines_count'),'total_lines':coverage.get('total_lines'),'branch_coverage':coverage.get('branch_coverage_percentage'),'covered_branches':coverage.get('covered_branches_count'),'total_branches':coverage.get('total_branches'),'mutation_score':mutation.get('kill_percentage'),'killed_mutants':len(mutation.get('killed_mutations',[])) if mutation else None,'total_mutants':mutation.get('total_mutations'),'evaluation_error':metrics.get('error') or (metrics.get('coverage') or {}).get('error_message') or ''}
  if len(row['evaluation_error'])>2000:row['evaluation_error']=row['evaluation_error'][:2000]+' [truncated; raw log retained on experiment host]'
  table.append(row)
  outputs.setdefault((method,dataset),[]).append({**row,'generated_test':job['code'],'generated_imports':job['imports'],'original_record':job['source']})
for dataset in ['prbench','updates4j']:
 write_json(OUT/'data'/f'{dataset}.json',[v for k,v in sorted(inputs.items()) if v['dataset']==dataset])
for (method,dataset),rows in outputs.items():write_json(OUT/'results'/method/f'{dataset}.json',rows)
(OUT/'results').mkdir(exist_ok=True)
with (OUT/'results/per-sample.csv').open('w',newline='') as stream:
 writer=csv.DictWriter(stream,fieldnames=list(table[0]));writer.writeheader();writer.writerows(table)
for name in ['summary.json','summary.csv','original-status-counts.json']:
 shutil.copy2(SOURCE/name,OUT/'results'/name)

roots={
 'mumutestup/deployment':ROOT/'mumutestup/deployment',
 'mumutestup/upstream-luna':ROOT/'mumutestup/upstream-luna',
 'testupdater/deployment':ROOT/'testupdater/deployment',
 'testupdater/runtime':ROOT/'testupdater/runtime',
 'testupdater/upstream/TestUpdater':ROOT/'testupdater/upstream/TestUpdater',
 'testsyncer/deployment':ROOT/'testsyncer/deployment',
 'testsyncer/official':ROOT/'testsyncer/official',
}
skip={'.git','.venv','__pycache__','target','static','data','datasets','dataset','runs','logs','repos','old-repos','models-cache','node_modules','index_data'}
for prefix,root in roots.items():
 for directory,dirs,files in os.walk(root):
  dirs[:]=[d for d in dirs if d not in skip and not d.startswith('index_data')]
  for name in files:
   source=Path(directory)/name
   if source.suffix not in ['.py','.sh','.java','.xml','.md','.yml','.yaml'] and name not in ['requirements.txt','LICENSE','LICENSE.txt','NOTICE']:continue
   if source.is_symlink():continue
   target=OUT/'code'/prefix/source.relative_to(root)
   text=source.read_text(errors='replace');clean=TOKEN.sub('[REDACTED_CREDENTIAL]',text)
   if clean!=text:redactions.append(str(target.relative_to(OUT)))
   target.parent.mkdir(parents=True,exist_ok=True);target.write_text(clean)
for source in (ROOT/'comparison').glob('*'):
 if source.suffix in ['.py','.sh']:
  target=OUT/'code/comparison'/source.name;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(TOKEN.sub('[REDACTED_CREDENTIAL]',source.read_text()))
write_json(OUT/'results/export-info.json',{'input_samples':len(inputs),'output_records':len(table),'redacted_files':redactions,'scope':'Final input/output and aggregate analysis only; raw logs and per-mutant XML remain on the experiment host.','pending_quality_evaluations':sum(r['metric_state'] in ['evaluation_error','execution_failed'] for r in table)})
archive=OUT.with_suffix('.tar.gz')
with tarfile.open(archive,'w:gz') as tar:
 for name in ['data','results','code']:tar.add(OUT/name,arcname=name)
print(json.dumps({'archive':str(archive),'bytes':archive.stat().st_size,'inputs':len(inputs),'outputs':len(table),'redactions':redactions}),flush=True)
