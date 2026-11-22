"""Prepare an isolated run using the original queue and official evaluator."""
from collections import Counter
import csv
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys

BASE = Path('/root/Baxxhy/work2/reproductions/req2test')
OLD = BASE / 'req2test-eval2051-resume-20261117-v1'
arm=sys.argv[2]
assert arm in ('a','b')
NAME='req2test-paired80-20261123-'+arm
ROOT = BASE / NAME

def save(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')

def own(path):
    os.chown(path, 1001, 1001)

source = Path(sys.argv[1])
rows = list(csv.DictReader((source/'冻结任务-11-23.csv').open()))
assert len({r['instance_id'] for r in rows})==80 and set(Counter(r['project'] for r in rows).values())=={10}
for unit in (OLD.name, NAME):
    check = subprocess.run(['systemctl','is-active',unit],capture_output=True,text=True)
    assert check.stdout.strip() == 'inactive', (unit, check.stdout)
cfg = json.loads((OLD/'frozen/config.json').read_text())
out = Path(cfg['req_home'])/'runs'/NAME
assert not ROOT.exists() and not out.exists()
with socket.socket() as probe:
    probe.bind(('127.0.0.1', (18241 if arm=="a" else 18242)))
state_old = json.loads((OLD/'state.json').read_text())
tasks_old = {t['id']:t for t in state_old['tasks'].values()}
tasks, replays = {}, {}
for row in rows:
    iid = row['instance_id']
    old = tasks_old[iid]
    assert row['project'] == old['project']
    tasks['req:'+iid] = dict(id=iid,project=old['project'],safe=old['safe'],benchmark='req2test',gen='pending',evaluation='pending',gen_attempts=0)
manifests = {}
for task in tasks.values():
    for candidate in [OLD, BASE/'req2test-eval2051-20261115-v1']:
        path = Path(json.loads((candidate/'frozen/config.json').read_text())['req_output'])/'manifests/items'/(task['safe']+'.jsonl')
        if path.is_file():
            data = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
            assert len(data)==1 and data[0]['instance_id']==task['id'] and data[0]['view']=='th'
            manifests[task['safe']] = path
            break
    assert task['safe'] in manifests, task['id']
for iid, row in replays.items():
    value = json.loads(Path(row['prediction']).read_text().splitlines()[0])
    assert value['instance_id']==iid and value['files'], iid
(ROOT/'frozen').mkdir(parents=True)
(ROOT/'jobs').mkdir()
shutil.copytree(OLD/'control',ROOT/'control',ignore=shutil.ignore_patterns('__pycache__'))
shutil.copy2(source/'supervise_diagnostic.py',ROOT/'control/supervise_diagnostic.py')
shutil.copy2(OLD/'frozen/config.parent.json',ROOT/'frozen/config.parent.json')
for d in (out, out/'manifests',out/'manifests/items',out/'generation',out/'input',out/'diagnostics'):
    d.mkdir()
    own(d)
for safe, path in manifests.items():
    dest=out/'manifests/items'/(safe+'.jsonl')
    shutil.copyfile(path,dest)
    own(dest)
    dest.chmod(0o644)
cfg.update(run_id=NAME, req_run_id=NAME, req_output=str(out), gateway_port=(18241 if arm=="a" else 18242),
           req_generation_timeout=3600)
cfg['arm']=arm
adapter=out/'agent.py'
adapter.write_text((source/'agent.py').read_text())
ctrl=ROOT/'control/controller.py'
if arm=='b':
    raw=ctrl.read_text()
    assert raw.count("get('effort')!='medium'")==1
    ctrl.write_text(raw.replace("get('effort')!='medium'", "get('effort')!='high'"))
save(ROOT/'frozen/config.json', cfg)
save(ROOT/'frozen/replays.json', replays)
save(ROOT/'state.json', dict(tasks=tasks, jobs={}, block=None, cooldown_until=0,
    generation_cap=3, evaluation_cpu_budget=16, request_retries=0,
    events_429=0, generation_completions=[], started=__import__('time').time(), groups={}))
service = json.loads((OLD/'service-command.json').read_text())
service = [a.replace(str(OLD),str(ROOT)).replace('--unit='+OLD.name,'--unit='+NAME)
           .replace('/control/controller.py','/control/supervise_diagnostic.py') for a in service]
save(ROOT/'service-command.json',service)
subprocess.run(service,check=True)
print(json.dumps(dict(unit=NAME+'.service',root=str(ROOT),output=str(out),
                      replay=0,regenerate=80,original_config='witness + extended evaluator; generation 3600 s'),ensure_ascii=False))
