"""Check public evidence without an evaluator, engine checkout, or any model API."""
import csv
import json
import math
from collections import Counter
from pathlib import Path
d=Path(__file__).resolve().parent
def load(name):
    return json.loads((d/name).read_text())
def rows(name):
    with (d/name).open() as f:return list(csv.DictReader(f))
paired=load('八十项配对与注册异常交叉统计-11-23.json')
assert len({v['id'] for v in paired['rows']})==80
assert len({v['project'] for v in paired['rows']})==8
original=paired['all']
assert (original['n'],original['A_pass'],original['B_pass'])==(79,30,39)
n=original['only_a']+original['only_b']
assert abs(original['p']-min(1,2*sum(math.comb(n,k) for k in range(min(original['only_a'],original['only_b'])+1))/2**n))<1e-12
final=rows('十条装配问题最终对照-11-23.csv')
assert len({r['instance_id'] for r in final})==10 and {r['first'] for r in final}=={'container_error'}
assert Counter(r['diagnostic_final'] for r in final)=={'failed':6,'undefined_steps':4}
assert all(json.loads(r['step_counts']) and r['exit_codes']=='[1]' for r in final)
env=rows('八项目原始测试环境对照-11-23.csv')
sample=rows('六项目环境对照清单-11-23.csv')
assert len(sample)==18 and set(Counter(x['project'] for x in sample).values())=={3}
assert len(env)==28 and len({r['instance_id'] for r in env})==28
assert set(r['instance_id'] for r in env)=={r['instance_id'] for r in final}|{r['instance_id'] for r in sample}
ref=rows('普通候选通道对照-11-23.csv')
assert {r['instance_id'] for r in ref}=={r['instance_id'] for r in final} and len(ref)==10
for r in env+ref:
    assert r['engine'] and len(r['exec_sha256'])==64 and r['official']
    if r['engine']=='passed':
        assert r['official']=='pass' and json.loads(r['exit_codes'])==[0] and json.loads(r['steps']).get('passed',0)>0
identity=load('八项目评测环境身份-11-23.json')
assert len(identity)==8 and all(all(v['matches'].values()) for v in identity.values())
assert all(x['A']['workers']==x['B']['workers']==2 and x['gold']['workers']==1 for x in (v['records'] for v in identity.values()))
print('Verified 80 paired IDs, 79 scored, 10 DI interventions, 28 official developer controls, 10 ordinary-candidate controls, and 8 evaluator identity records.')
