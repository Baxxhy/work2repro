"""Offline publication audit; no model calls, Docker, or benchmark reruns."""
import collections
import csv
import hashlib
import json
import math
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
TAG='test-generation-20261114'
R=ROOT/'results'/TAG

def read(path):return json.loads(path.read_text())
def near(a,b):assert math.isclose(a,b,rel_tol=1e-10,abs_tol=1e-12),(a,b)

audit=read(R/'export-integrity.json')
for f in audit['files']:
    p=ROOT/f['path']
    assert p.is_file(),p
    assert p.stat().st_size==f['bytes'],p
    assert hashlib.sha256(p.read_bytes()).hexdigest()==f['sha256'],p
    for pattern in [rb'eyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}',rb'sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{35,}',rb'(?:gh[opusr]_|github_pat_)[A-Za-z0-9_]{30,}',rb'-----BEGIN (?:OPENSSH |RSA |EC )?PRIVATE KEY-----']:
        for match in re.finditer(pattern,p.read_bytes()):
            fixture=(f['path']=='data/test-generation-20261114/testsuitebench-specifications/sirwart__ripsecrets.34c9e03/spec.md'
                     and match.group() in (b'ghp_'+b'A'*36,b'gho_'+b'B'*36))
            assert fixture, f'Potential credential requires review: {p}'
tasks=read(R/'task-artifacts.json')
assert len(tasks)==325
assert len({(t['benchmark'],t['instance_id']) for t in tasks})==325
assert collections.Counter(t['benchmark'] for t in tasks)=={'testsuitebench':165,'req2test':160}
for t in tasks:
    folder=(R/'testsuitebench/tasks'/t['instance_id']) if t['benchmark']=='testsuitebench' else R/'req2test/tasks'/t['artifact_id']
    assert (folder/'trajectory-excerpt.json').is_file()
    trace=read(folder/'trajectory-excerpt.json')
    assert trace['complete_trace'] is False
    for f in t['generated_files']:
        assert hashlib.sha256((folder/'generated'/f['path']).read_bytes()).hexdigest()==f['sha256']
tsb=list(csv.DictReader((R/'reports/tsb-per-task.csv').open()))
assert len(tsb)==len({x['instance_id'] for x in tsb})==165
assert {x['instance_id'] for x in tsb}=={x['instance_id'] for x in tasks if x['benchmark']=='testsuitebench'}
summary=read(R/'reports/tsb-official-summary.json')
near(sum(float(x['validity_rate']) for x in tsb)/165,summary['average_validity_rate'])
near(sum(float(x['mutation_score']) for x in tsb)/165,summary['average_mutation_score'])
assert summary['infrastructure_unfinished']==[]
req=[json.loads(x) for x in (R/'reports/req2test-per-task.jsonl').read_text().splitlines()]
inputs=[json.loads(x) for x in (ROOT/'data'/TAG/'req2test-tasks.jsonl').read_text().splitlines()]
assert len(req)==len({x['instance_id'] for x in req})==160
assert {x['instance_id'] for x in req}=={x['instance_id'] for x in inputs}
assert set(collections.Counter(x['project'] for x in inputs).values())=={20}
ex=read(R/'reports/req2test-denominators-and-exclusions.json')['official_population']['excluded']
assert len(ex)==1 and len(req)-len(ex)==159
cells=read(R/'reports/req2test-per-project.json')
assert len(cells)==8 and sum(c['n'] for c in cells)==159
for cell in cells:
    rows=[x for x in req if x['project']==cell['project'] and x['instance_id'] not in ex]
    assert len(rows)==cell['n']
    near(sum(x['passed'] for x in rows)/len(rows),cell['pass_at_1'])
    near(sum(x['kill_complete'] for x in rows)/len(rows),cell['kill_complete_at_1'])
head=read(R/'reports/req2test-official-summary.json')['modes']['leaderboard']['mean']['th']
for key in ['pass_at_1','kill_complete_at_1','api_f1','coverage_j','mutation_recall']:
    near(sum(c[key] for c in cells)/8,head[key]['value'])
integrity=read(R/'reports/recovery-integrity.json')
assert integrity['unchanged_official_scores_verified']==152
assert integrity['all_infrastructure_recoveries_resolved'] is True
assert integrity['model']=='gpt-6-luna' and integrity['reasoning']=='medium'
completion=read(R/'completion.json')
assert completion['all_ids_accounted_for'] and completion['all_required_evaluations_complete']
print(f'PASS: {len(audit["files"])} exported files verified; 165 TSB + 160 Req2Test IDs; 159 Req scored; official metric arithmetic agrees.')
