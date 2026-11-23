"""Run official developer controls in six projects on a frozen stratified sample."""
import csv
import hashlib
import json
from pathlib import Path
import sys
import traceback

from req2test import evaluate, predictions

home = Path.home()
bench = home / 'benchmark'
work = Path(__file__).parent
projects = ['algorand-sdk', 'python-docx', 'e-petitions', 'prestashop', 'kapua', 'coddy-agent']
socket = 'unix:///run/user/1001/req2test-docker-10156f49/docker.sock'
def lines(p):
    return [json.loads(s) for s in p.read_text().splitlines() if s.strip()]

def select():
    dataset = {x['instance_id']: x for x in lines(bench/'data/dataset-v1.1/eval.jsonl')}
    selection = []
    for proj in projects:
        src = bench/'runs'/f'req2test-paired80-20261123-a-regenerated-{proj}'/proj/'th/exec.jsonl'
        pool = []
        for row in lines(src):
            iid = row['item_id']
            profile = tuple(sorted(row['bench_meta'].get('dependency_profile') or []))
            typ = (dataset[iid]['test_level_class'], profile)
            rank = hashlib.sha256(('r2t-env-20261123:'+iid).encode()).hexdigest()
            pool.append((rank, typ, iid))
        assert len({v[2] for v in pool})==10
        pool.sort()
        used = set()
        order = []
        for item in pool:
            if item[1] not in used:
                order.append(item)
                used.add(item[1])
        order.extend(item for item in pool if item not in order)
        for rank,(level,profile),iid in order[:3]:
            selection.append(dict(project=proj,instance_id=iid,level=level,dependencies=','.join(profile) or 'undeclared',rank=rank))
    return selection

csvpath = work/'six-project-sample.csv'
if sys.argv[1:] == ['freeze']:
    selection = select()
    with csvpath.open('x') as f:
        writer=csv.DictWriter(f,list(selection[0]));writer.writeheader();writer.writerows(selection)
    sys.exit()
rows=list(csv.DictReader(csvpath.open()))
problems=[]
for project in sys.argv[1:] or projects:
    assert project in projects
    ids = [r['instance_id'] for r in rows if r['project']==project]
    assert len(set(ids))==3
    try:
        run_id=f'r2t-di-1123-{work.name[:15]}-gold-{project}'
        print('BEGIN',project,run_id,flush=True)
        result=evaluate.evaluate(None, run_id=run_id, project=project, split='eval', view='th', workers=1, metrics='exec', instances=ids,
              predictions=predictions.from_gt(project,ids,view='th'),docker_host=socket)
        print('END',project,[(x['instance_id'],x['engine_outcome']) for x in result['instances']],flush=True)
    except Exception:
        problems.append(project);traceback.print_exc()
if problems:
    raise SystemExit('Blocked: '+','.join(problems))
