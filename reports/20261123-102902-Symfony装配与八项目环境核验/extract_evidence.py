"""Index only execution outcomes, official environment checks, and log checksums."""
from pathlib import Path
from collections import Counter
from functools import lru_cache
import hashlib
import json
import re
import sys

work=Path(sys.argv[1])
runs=Path.home()/'benchmark/runs'
prefix='r2t-di-'
def load(p):
    return json.loads(p.read_text())
def lines(p):
    return [json.loads(row) for row in p.open() if row.strip()]
def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()
def picked_error(raw):
    for step in raw.get('per_step') or []:
        if step.get('result') == 'failed' and step.get('error'):
            msg=' '.join(step['error'].split())
            # Retain only the diagnostic headline, not arbitrary program output.
            if msg.startswith('{'):
                try:
                    body=json.loads(msg)
                    return 'HTTP %s %s'%(body.get('status'),body.get('detail','')[:80])
                except ValueError: pass
            return msg.split('Stack trace:')[0].split(' in /')[0][:360]
    return None
def di_header(log):
    sample=' '.join(log.read_text().split())
    for pattern in (r'Cannot autowire service ".+?(?= You should| Did you mean|\s{2,}|$)',r'The service ".{0,350}?non-existent service ".{1,200}?"',r'(?:Type error:|TypeError:|ArgumentCountError:|RuntimeException:).{0,270}'):
        m=re.search(pattern,sample)
        if m: return m.group()[:450]
    return None
def extract(d):
    result=[]
    for f in sorted(d.glob('*/th/instances.jsonl')):
        project=f.parent.parent.name;engine_exec=f.with_name('exec.jsonl')
        raw={r['item_id']:r for r in lines(engine_exec)}
        artifacts=work/'full-logs'/d.name; pointers={}
        for m in artifacts.glob('*/*/meta.json'):
            meta=load(m)
            p=m.with_name('stdout.log')
            if p.is_file():
                pointers[meta['item_id']]=dict(log=str(p.relative_to(work)),sha256=sha(p),stdout_complete=meta['stdout_complete'],di_error=di_header(p) if meta['outcome'] in ('container_error','no_scenario_ran') else None)
        for y in lines(f):
            z=raw[y['instance_id']]
            result.append(dict(id=y['instance_id'],project=project,official=y['outcome'],engine=y['engine_outcome'],passed=y['passed'],exit=z.get('exit_codes'),steps=dict(Counter(s['result'] for s in z.get('per_step') or [])),step_error=picked_error(z),rejected=z.get('rejected_files'),
                               exec_log=str(engine_exec.relative_to(runs)),exec_sha256=sha(engine_exec),**pointers.get(y['instance_id'],{})))
    return result
if __name__=='__main__':
    evidence={}
    diagnostic_dirs = list(runs.glob('r2t-di-*'+work.name[:15]+'-*'))
    original_gold = [runs/('req2test-paired80-gold-1123-'+project) for project in ('sylius', 'coreshop')]
    for p in sorted(diagnostic_dirs + original_gold):
        r=extract(p)
        if not r:continue
        envs=[]
        for e in p.glob('*/th/env.json'):
            v=load(e);record=Path(v['record']);env=load(record);checks=env['qualification']['checks'];gold=checks.get('gold_control',{});wk=gold.get('workers',{})
            envs.append(dict(project=v['project'],nonce=v['nonce'],checks={k:val for k,val in checks.items() if k in ('harden','probe','reset-probe')},gold_id=gold.get('item'),gold_outcomes={k:z['outcome'] for k,z in wk.items()},qualification_log=str(record.parent/'qualification'),engine_log_sha256=sha(record.with_name('engine.log')) if record.with_name('engine.log').exists() else None))
        evidence[p.name]=dict(rows=r,envs=envs)
    print(json.dumps(evidence,indent=2,ensure_ascii=False))
