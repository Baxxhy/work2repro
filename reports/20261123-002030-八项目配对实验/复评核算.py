import json,csv,sys,math
from pathlib import Path
from collections import Counter
from req2test.report import population_exclusions
base=Path.home()/'benchmark/runs'
pop=population_exclusions('1.1')['excluded']
ab=[]; audit=[]
def rows(f):return list(map(json.loads,f.open()))
for arm in 'ab':
    scored={}
    for f in sorted(base.glob('*paired80-20261123-'+arm+'-regenerated-*/*/th/instances.jsonl')):
        project=f.parent.parent.name
        orig={x['item_id']:x for x in rows(f.with_name('exec.jsonl'))}
        for x in rows(f):
            i=x['instance_id']
            if x['engine_outcome']=='container_error':
                pattern=f.parents[2].name.replace('regenerated','audit')+'*/'+project+'/th/instances.jsonl'
                matches=[(g,y) for g in base.glob(pattern) for y in rows(g) if y['instance_id']==i]
                assert len(matches)==1,(i,matches)
                g,y=matches[0]; e=next(z for z in rows(g.with_name('exec.jsonl')) if z['item_id']==i)
                gold=base/('req2test-paired80-gold-1123-'+project)/project/'th/exec.jsonl'
                z=next(z for z in rows(gold) if z['item_id']==i)
                audit.append(dict(arm=arm,project=project,id=i,first=x['engine_outcome'],replay=y['engine_outcome'],official=y['outcome'],gold=z['outcome'],exit_first=orig[i]['exit_codes'],exit_replay=e['exit_codes'],exit_gold=z['exit_codes'],first_file=str(f.parent/'exec'/'raw'),replay_file=str(g.parent/'exec'/'raw'),gold_file=str(gold.parent/'exec/raw'),detail=' '.join(e['stdout_tail'].split())[:300]))
                x=y
            assert i not in scored
            scored[i]=x
    assert len(scored)==80
    ab.append({i:x for i,x in scored.items() if i not in pop and x['outcome']!='infrastructure_excluded'})
a,b=ab;c=Counter((a[i]['passed'],b[i]['passed']) for i in a.keys()&b.keys());n=c[1,0]+c[0,1]
assert len(audit)==10
print(json.dumps(dict(audit=audit,results=[dict(den=len(s),passed=sum(x['passed'] for x in s.values()),projects={p:[sum(x['passed'] for x in s.values() if x['project']==p),sum(x['project']==p for x in s.values())] for p in sorted({x['project'] for x in s.values()})}) for s in ab],pairs={str(k):v for k,v in c.items()},p=min(1,2*sum(math.comb(n,k) for k in range(min(c[1,0],c[0,1])+1))/2**n)),indent=2))
