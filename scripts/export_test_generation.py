"""Export the completed baselines without credentials, caches or hidden answers."""
import csv
import hashlib
import io
import json
import os
import re
import shutil
import tarfile
from pathlib import Path, PurePosixPath

BASE=Path('/root/Baxxhy/work2')
RUN=BASE/'reproductions/req2test/req2test-recovery8-20261113-v1'
OUT=BASE/'test-generation-export-20261115-v2'
TAG='test-generation-20261114'
assert not OUT.exists(), OUT
OUT.mkdir()
state=json.loads((RUN/'state.json').read_text())
cfg=json.loads((RUN/'frozen/config.json').read_text())
assert json.loads((RUN/'completion.json').read_text())['all_required_evaluations_complete']
assert json.loads((RUN/'reports/recovery-integrity.json').read_text())['unchanged_official_scores_verified']==152
secrets=[]
for p in [Path('/root/.codex/auth.json'),Path(cfg['req_home'])/'.codex/auth.json']:
    if not p.exists():continue
    def collect(x,key=''):
        if isinstance(x,dict):
            for k,v in x.items():collect(v,k)
        elif isinstance(x,str) and len(x)>15 and re.search('token|api_key|secret',key,re.I):secrets.append(x)
    collect(json.loads(p.read_text()))

def put(path,data):
    path=OUT/path;path.parent.mkdir(parents=True,exist_ok=True)
    if isinstance(data,str):data=data.encode()
    for secret in secrets:
        assert secret.encode() not in data, f'Credential detected in {path}'
    assert b'-----BEGIN OPENSSH PRIVATE KEY-----' not in data, path
    assert b'-----BEGIN RSA PRIVATE KEY-----' not in data, path
    path.write_bytes(data)

def js(path,data):put(path,json.dumps(data,ensure_ascii=False,indent=2)+'\n')
def copy(src,dst):put(dst,Path(src).read_bytes())
def sha(data):return hashlib.sha256(data).hexdigest()
def short(x):
    if isinstance(x,str) and len(x)>4000:return x[:4000]+'\n[TRUNCATED: full original retained on experiment server]'
    if isinstance(x,list):return [short(v) for v in x]
    if isinstance(x,dict):return {k:short(v) for k,v in x.items()}
    return x

res=Path('results')/TAG;data=Path('data')/TAG;code=Path('code')/TAG;env=Path('environment')/TAG
for p in sorted((RUN/'reports').iterdir()):
    if p.is_file():copy(p,res/'reports'/p.name)
copy(RUN/'completion.json',res/'completion.json')
copy(RUN/'resources.jsonl',res/'resources.jsonl')
copy(RUN/'events.jsonl',res/'events.jsonl')
copy(RUN/'evaluation-reuse-provenance.json',res/'evaluation-reuse-provenance.json')
copy(RUN/'frozen/parallelism-20261114-amendment.json',env/'parallelism-amendment.json')
for name in ['controller.py','job.py','final_report.py','generation_outcome.py','seed_evaluation.py','recovery_validation.py','test_generation_outcome.py']:
    if (RUN/'control'/name).exists():copy(RUN/'control'/name,code/'controller'/name)
copy('/root/lby-docker/req2test/agent/req_agent.py',code/'req_agent.py')
copy(cfg['diagnostic_eval_wrapper'],code/'diagnostic_eval.py')
for name in ['config.json','config.parent.json','selected-ids.txt','selection.json','req-official-population.yml']:
    if (RUN/'frozen'/name).exists():copy(RUN/'frozen'/name,env/name)
copy(RUN/'frozen/req-tasks.jsonl',data/'req2test-tasks.jsonl')
copy(RUN/'frozen/prompts/tsb.txt',data/'testsuitebench-prompt.txt')
copy(Path(cfg['req_home'])/'configuration-notes.md',env/'req2test-setup-notes.md')
for repo,name in [(Path(cfg['tsb_repo']),'testsuitebench'),(Path(cfg['req_home'])/'repo','req2test')]:
    copy(repo/'LICENSE',code/'upstream-licenses'/name/'LICENSE')
    for f in ['pyproject.toml','uv.lock','requirements.txt']:
        if (repo/f).exists():copy(repo/f,env/name/f)
for name in ['tsb-diff.patch','req2test-diff.patch','final-transport.Dockerfile','tsb-final-environment-diff.patch','dependency-version-policy.json','codex-cache-reuse.json','node-version-preservation.json']:
    for root in [BASE/'reproductions/testsuitebench/tsb-recovery-20261113-v1/frozen',RUN/'frozen']:
        if (root/name).exists():copy(root/name,code/'patches'/name);break

preds={x['instance_id']:x for x in map(json.loads,(Path(cfg['req_output'])/'predictions.jsonl').read_text().splitlines())}
copy(Path(cfg['req_output'])/'predictions.jsonl',res/'req2test/predictions.jsonl')
manifest=[];counts={'testsuitebench':0,'req2test':0}
for t in state['tasks'].values():
    bench=t['benchmark'];iid=t['id'];safe=t['safe']
    if bench=='tsb':
        counts['testsuitebench']+=1
        folder=Path(t['official_report']).parent
        task=res/'testsuitebench/tasks'/iid
        copy(Path(cfg['tsb_repo'])/'ground_truth/spec'/iid/'spec.md',data/'testsuitebench-specifications'/iid/'spec.md')
        kept=[]
        with tarfile.open(folder/'tests.tar.gz') as archive:
            for member in archive.getmembers():
                parts=PurePosixPath(member.name).parts
                if not member.isfile() or not parts or parts[0]!='eval' or '..' in parts:continue
                if any(x in parts for x in ['__pycache__','.pytest_cache','.git']):continue
                if parts[-1].endswith('.pyc') or member.name=='eval/results.xml':continue
                raw=archive.extractfile(member).read()
                destination=task/'generated'/PurePosixPath(*parts[1:])
                put(destination,raw)
                if member.mode & 0o111:(OUT/destination).chmod(0o755)
                kept.append(dict(path=str(PurePosixPath(*parts[1:])),sha256=sha(raw)))
        p=folder/(iid+'.traj.json');traj=json.loads(p.read_text())
        js(task/'trajectory-excerpt.json',dict(original_record=str(p),complete_trace=False,string_limit=4000,
           model=traj['info'].get('model'),reasoning=traj['info'].get('reasoning'),
           exit_status=traj['info'].get('exit_status'),usage=traj.get('usage'),events=short(traj.get('codex_events',[]))))
        record=dict(benchmark='testsuitebench',instance_id=iid,generated_files=kept,original_record=str(folder),official_report=t['official_report'],generation_status=t['gen'],evaluation_status=t['evaluation'])
    else:
        counts['req2test']+=1;task=res/'req2test/tasks'/safe;pred=preds[iid];kept=[]
        for f in pred['files']:
            path=PurePosixPath(f.get('file_path',f.get('path','')))
            assert path.parts and not path.is_absolute() and '..' not in path.parts,(iid,str(path))
            raw=f['content'].encode();put(task/'generated'/path,raw);kept.append(dict(path=str(path),sha256=sha(raw)))
        prediction=Path(t['prediction']);log=prediction.parent/'workspaces/0000.log'
        if not log.exists():log=Path(t['source_prediction']).parent/'workspaces/0000.log'
        events=[];nonjson=[]
        for line in log.read_text(errors='replace').splitlines():
            try:events.append(short(json.loads(line)))
            except ValueError:nonjson.append(line[:1000])
        js(task/'trajectory-excerpt.json',dict(original_record=str(log),complete_trace=False,string_limit=4000,events=events,other_output=nonjson[:20]))
        record=dict(benchmark='req2test',instance_id=iid,artifact_id=safe,generated_files=kept,original_record=str(prediction),original_trace=str(log),generation_status=t['gen'],evaluation_status=t['evaluation'])
    manifest.append(record)
assert counts=={'testsuitebench':165,'req2test':160},counts
js(res/'task-artifacts.json',manifest)
js(env/'versions.json',dict(agent='Codex CLI',cli_version='0.160.0',model='gpt-6-luna',reasoning='medium',
 testsuitebench_commit=cfg['tsb_commit'],req2test_commit=cfg['req_commit'],
 testsuitebench_references={k:cfg[k] for k in ['tsb_mutants','tsb_reference','tsb_tests']},
 req2test_dataset_revision='0dfb049d5c9bfd0d8c98d23c22af7d02ee6865a3',
 req2test_source='https://github.com/code-philia/Req2Test-Bench',testsuitebench_source='https://github.com/eth-sri/testsuitebench'))
checks=[]
for p in sorted(OUT.rglob('*')):
    if p.is_file():checks.append(dict(path=str(p.relative_to(OUT)),sha256=sha(p.read_bytes()),bytes=p.stat().st_size))
js(res/'export-integrity.json',dict(tasks=counts,files=checks,credentials_found=0,complete_raw_traces_on_server=True))
print(json.dumps(dict(output=str(OUT),tasks=counts,files=len(checks),bytes=sum(x['bytes'] for x in checks))))
