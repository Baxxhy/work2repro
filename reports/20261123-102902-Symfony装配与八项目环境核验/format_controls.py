"""Summarize the engine's recorded rows. Do not count absent rows as failures."""
from pathlib import Path
import csv,json,sys
d=Path(__file__).parent
snapshot=json.loads(Path(sys.argv[1]).read_text())
mode=sys.argv[2]
assert mode in ('gold','refcandidate')
by_project={}
for k,v in snapshot.items():
    if mode=='gold':
        if not (k.startswith('req2test-paired80-gold-1123-') or k.startswith('r2t-di-1123-') and '-gold-' in k):continue
    elif '-refcandidate-' not in k:continue
    name=v['rows'][0]['project']
    assert name not in by_project
    by_project[name]=(k,v)
expected={'sylius':4,'coreshop':6}
if mode=='gold':
    with (d/'六项目环境对照清单-11-23.csv').open() as f:
        for r in csv.DictReader(f):
            expected[r['project']]=expected.get(r['project'],0)+1
assert set(expected)==set(by_project), (expected,by_project.keys())
rows=[]
for proj,(run,v) in sorted(by_project.items()):
    assert len(v['rows'])==expected[proj]
    env,=v['envs']
    for r in v['rows']:
        rows.append(dict(project=proj,instance_id=r['id'],run=run,engine=r['engine'],official=r['official'],exit_codes=json.dumps(r['exit']),steps=json.dumps(r['steps'],sort_keys=True),
                         step_error=r['step_error'],env_id=env['nonce'],qualified=json.dumps(env['gold_outcomes'],sort_keys=True),db_checks=json.dumps(env['checks'],sort_keys=True),exec_sha256=r['exec_sha256'],exec_log=r['exec_log'],full_stdout=r.get('log',''),stdout_sha256=r.get('sha256','')))
assert len(rows)==len({r['instance_id'] for r in rows})
file='八项目原始测试环境对照-11-23.csv' if mode=='gold' else '普通候选通道对照-11-23.csv'
with (d/file).open('w') as f:
    w=csv.DictWriter(f,rows[0].keys(),lineterminator='\n');w.writeheader();w.writerows(rows)
print(len(rows),sum(r['engine']=='passed' for r in rows),file)
