"""Freeze saved generations from all six experiments for common execution metrics."""
import collections
import json
from pathlib import Path

ROOT = Path('/root/Baxxhy/work2/reproductions')
OUT = ROOT / 'comparison/metrics-20261108'
OUT.mkdir(parents=True, exist_ok=True)
records = {}
for method, runs in {
    'TestUpdater': ['luna-full-20261105', 'recovery-20261105', 'recovery5-20261105'] + sorted(p.name for p in (ROOT/'testupdater/runs').glob('quota-resume-*')),
    'TestSyncer': ['prbench-luna-20261107', 'updates4j-luna-20261108'],
}.items():
    directory = 'testupdater' if method == 'TestUpdater' else 'testsyncer'
    for run in runs:
        for dataset in ['prbench', 'updates4j']:
            for path in (ROOT/directory/'runs'/run/dataset).glob('*/samples/*.json'):
                data = json.loads(path.read_text())
                index = data.get('_recovery_original_index', int(path.stem))
                records[(method,dataset,data['repo_name'],index)] = (data,path)

mumu_runs = {
    'prbench': ['luna571-20261104', 'luna571-20261104/harness-recovery-20261105'],
    'updates4j': ['updates4j-fixed-v3-20261107','updates4j-acme-fixed-20261107','updates4j-env36-20261107'],
}
for dataset,runs in mumu_runs.items():
    for run in runs:
        for path in (ROOT/'mumutestup/runs'/run/'projects').glob('*/*/samples/*.json'):
            data=json.loads(path.read_text())
            records[('MuMuTestUp',dataset,data['project'],data['index'])]=(data,path)

jobs=collections.defaultdict(list)
counts=collections.Counter()
dataset_cache={}
for (method,dataset,project,index),(record,path) in sorted(records.items()):
    dataset_dir=ROOT/'mumutestup'/('upstream-luna/dataset' if dataset=='prbench' else 'datasets/updates4j')
    cache_key=(dataset,project)
    if cache_key not in dataset_cache:
        dataset_cache[cache_key]=json.loads((dataset_dir/project/'data.json').read_text())
    original_sample=dataset_cache[cache_key][index]
    sample={key:original_sample[key] for key in ['aCommit','bCommit','aPath','aSource','bSource','focal_method','tgt_java_version'] if key in original_sample}
    if method=='MuMuTestUp':
        result=record.get('result') or {}
        test_result=result.get('test_result') or {}
        case=test_result.get('test_case') or {}
        code=case.get('code','')
        imports=case.get('new_imports') or result.get('new_imports') or []
        status=record.get('test_status')
    else:
        code=record.get('test_gen','')
        imports=record.get('imports_gen') or []
        if isinstance(imports,str):imports=imports.splitlines()
        status=record.get('execution_status')
    passed=status in ['pass','coverage_loss','mutation_loss','coverage_and_mutation_loss']
    counts[(method,dataset,status)]+=1
    job={'method':method,'dataset':dataset,'project':project,'index':index,'source':str(path),'original_status':status,'original_passed':passed,'code':code,'imports':imports,'sample':sample}
    jobs[project].append(job)
for project,items in jobs.items():
    path=OUT/'jobs'/(project.replace('/','__')+'.json');path.parent.mkdir(exist_ok=True);path.write_text(json.dumps(items))
summary=[{'method':m,'dataset':d,'status':s,'count':n} for (m,d,s),n in sorted(counts.items())]
(OUT/'original-status-counts.json').write_text(json.dumps(summary,indent=2))
print('records',len(records),'projects',len(jobs),'original_passed',sum(j['original_passed'] for v in jobs.values() for j in v))
print(json.dumps(summary))
