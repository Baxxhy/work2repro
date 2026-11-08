"""Evaluate frozen tests with shared JaCoCo/PIT settings, without model calls."""
import argparse
import collections
import concurrent.futures
import dataclasses
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import traceback

ROOT=Path('/root/Baxxhy/work2/reproductions')
MUMU=ROOT/'mumutestup'
OUT=ROOT/'comparison/metrics-20261108'

def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value,indent=2,default=lambda v:dataclasses.asdict(v) if dataclasses.is_dataclass(v) else str(v)))
    temporary.replace(path)

def evaluate_project(job_file,smoke=False):
    jobs=json.loads(Path(job_file).read_text())
    project=jobs[0]['project']
    repo=OUT/'repos'/project
    repo.parent.mkdir(parents=True,exist_ok=True)
    if not repo.exists():
        source=ROOT/'testsyncer/repos'/project
        subprocess.run(['git','clone','--shared',str(source),str(repo)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    sys.path.insert(0,str(MUMU/'upstream-luna'))
    sys.path.insert(0,str(MUMU/'deployment'))
    from java_test_executor import JavaTestExecutor
    from models import FocalMethodInfo
    from utils.sample_logger import get_sample_logger
    from run_mumu import install_execution_guards
    evidence=[]
    violations=install_execution_guards(JavaTestExecutor,evidence)
    if smoke:
        selected=[]
        for method in ['MuMuTestUp','TestUpdater','TestSyncer']:
            match=next((j for j in jobs if j['method']==method and j['original_passed']),None)
            if match:selected.append(match)
        jobs=selected
    for job in jobs:
        result_path=OUT/'results'/job['method']/job['dataset']/project/f"{job['index']:04d}.json"
        if result_path.exists():continue
        record={k:v for k,v in job.items() if k not in ['sample','code','imports']}
        record['started_at']=time.time()
        if not job['original_passed']:
            record.update(state='original_generation_failed',metrics=None)
            save(result_path,record)
            continue
        sample=job['sample']
        evidence.clear();violations.clear()
        try:
            subprocess.run(['git','-C',str(repo),'checkout','--detach','--force',sample['aCommit']],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
            target=repo/sample['aPath'];text=target.read_text();reference=sample['aSource']['code'];code=job['code']
            if not code.strip() or text.count(reference)!=1:raise ValueError('Saved test missing or reference span is ambiguous')
            text=text.replace(reference,code,1)
            for line in job['imports']:
                if line.strip() and line.strip() not in text:
                    package=re.search(r'^\s*package\s+[^;]+;',text,re.MULTILINE)
                    if package:text=text[:package.end()]+'\n'+line+'\n'+text[package.end():]
                    else:text=line+'\n'+text
            target.write_text(text)
            package=re.search(r'^\s*package\s+([\w.]+)\s*;',text,re.MULTILINE)
            class_name=(package[1]+'.' if package else '')+target.stem
            method=re.search(r'\b(?:public|protected|private)?\s*(?:final\s+)?(?:void|boolean|int|String)\s+(\w+)\s*\(',code)
            if not method:raise ValueError('Cannot determine generated method name')
            focal=sample['focal_method'];after=focal['a_focal_method_code'];before=focal['b_focal_method_code']
            info=FocalMethodInfo(name=focal['focal_method_name'],current_code=after.get('code','') if isinstance(after,dict) else after,original_code=before.get('code','') if isinstance(before,dict) else before,start_line=after.get('startLine',0) if isinstance(after,dict) else 0,end_line=after.get('endLine',0) if isinstance(after,dict) else 0,class_name=focal['focal_class_name'],source_file_path=focal['a_focal_method_path'])
            java=str(sample.get('tgt_java_version','8')).replace('1.8','8')
            executor=JavaTestExecutor(str(repo),java_version=java,maven_repo_dir=str(MUMU/'maven-repositories'/(project.split('/')[-1]+'_repo')),project_name=project,sample_id=f"{job['method']}-{job['dataset']}-{job['index']}")
            report_dir=OUT/'reports'/job['method']/job['dataset']/project/str(job['index'])
            report_dir.mkdir(parents=True,exist_ok=True)
            executor.current_iteration_dir=report_dir
            executor._mumu_maven_commands=[]
            executor._mumu_installed_test=(target,hashlib.sha256(target.read_bytes()).hexdigest())
            get_sample_logger().initialize(str(job_file),f"{job['method']}-{job['dataset']}-{job['index']}",job['index'])
            coverage=executor._run_jacoco(class_name,method[1],info,sample['aPath'])
            record['coverage']=coverage
            if coverage['status']=='SUCCESS':
                record['mutation']=executor._run_pitest(class_name,method[1],info,sample['aPath'])
                record['state']='evaluated'
            else:record['state']='execution_failed'
        except Exception as error:
            record.update(state='evaluation_error',error=repr(error),traceback=traceback.format_exc())
        record.update(evidence=list(evidence),violations=list(violations),finished_at=time.time())
        save(result_path,record)
    return {'project':project,'state':'finished','samples':len(jobs)}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--smoke',action='store_true')
    parser.add_argument('--workers',type=int,default=7)
    args=parser.parse_args()
    files=sorted((OUT/'jobs').glob('*.json'))
    if args.smoke:files=[p for p in files if p.stem=='j256__ormlite-core']
    status={'state':'running','pid':os.getpid(),'started_at':time.time(),'mode':'smoke' if args.smoke else 'full','completed_projects':[]}
    path=OUT/('smoke-status.json' if args.smoke else 'status.json');save(path,status)
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers,max_tasks_per_child=1) as pool:
        futures=[pool.submit(evaluate_project,str(p),args.smoke) for p in files]
        for f in concurrent.futures.as_completed(futures):
            try:status['completed_projects'].append(f.result())
            except Exception as error:status['completed_projects'].append({'state':'worker_error','error':repr(error)})
            save(path,status)
            from summarize_metrics import summarize
            summarize()
    status['state']='finished' if all(p['state']=='finished' for p in status['completed_projects']) else 'finished_with_errors'
    status['finished_at']=time.time();save(path,status)

if __name__=='__main__':main()
