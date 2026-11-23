"""Read official original instance rows and calculate paired and diagnostic strata."""
import csv
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from req2test.report import population_exclusions
from req2test.inference.run_agent import build_prompt
home=Path.home()
prefix='req2test-paired80-20261123-'
base=home/'benchmark/runs'
exclude=population_exclusions('1.1')['excluded']
project_numbers={}; byarm={}; audit=set(); manifest={}
for arm in 'ab':
    original={}
    for f in sorted(base.glob(prefix+arm+'-regenerated-*/*/th/instances.jsonl')):
        for l in f.open():
            r=json.loads(l);iid=r['instance_id']
            assert iid not in original
            original[iid]=r
            if r['engine_outcome']=='container_error':audit.add(iid)
    assert len(original)==80
    byarm[arm]=original
    manifest[arm]={}
    for f in (home/'runs'/(prefix+arm)/'manifests/items').glob('*.jsonl'):
        t=json.loads(f.read_text()); p=build_prompt(t)
        manifest[arm][t['instance_id']]=dict(view=t['view'],row_sha256=hashlib.sha256(f.read_bytes()).hexdigest(),prompt_sha256=hashlib.sha256(p.encode()).hexdigest())
assert len(audit)==10 and manifest['a']==manifest['b']
assert set(byarm['a'])==set(byarm['b'])==set(manifest['a']) and all(x['view']=='th' for x in manifest['a'].values())
rows=[]
for iid,a in sorted(byarm['a'].items()):
    b=byarm['b'][iid]
    rows.append(dict(id=iid,project=a['project'],population_exclusion=exclude.get(iid),A=a['outcome'],B=b['outcome'],A_engine=a['engine_outcome'],B_engine=b['engine_outcome'],A_pass=a['passed'],B_pass=b['passed'],in_DI=audit.__contains__(iid),**manifest['a'][iid]))
def paired(matched):
    count=Counter((r['A_pass'],r['B_pass']) for r in matched)
    both=count[True,True];only_a=count[True,False];only_b=count[False,True];neither=count[False,False]
    n=only_a+only_b
    return dict(n=len(matched),A_pass=only_a+both,B_pass=only_b+both,both=both,only_a=only_a,only_b=only_b,neither=neither,p=min(1,2*sum(math.comb(n,k) for k in range(min(only_a,only_b)+1))/2**n))
matched=[r for r in rows if not r['population_exclusion'] and all(r[k]!='infrastructure_excluded' for k in ['A','B'])]
print(json.dumps(dict(rows=rows,all=paired(matched),projects={p:paired([r for r in matched if r['project']==p]) for p in sorted({r['project'] for r in matched})},ten=paired([r for r in matched if r['in_DI']]),remaining=paired([r for r in matched if not r['in_DI']]),meta=dict(matching_prompt_and_task_hashes=len(manifest['a']),excluded_ids={r['id']:r['population_exclusion'] for r in rows if r['population_exclusion']})),ensure_ascii=False,indent=1))
