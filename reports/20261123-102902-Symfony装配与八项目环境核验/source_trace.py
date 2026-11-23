"""Extract provenance, collection and tool-check evidence without copying credentials or whole sessions."""
import json,re,hashlib
from pathlib import Path
h=Path('/root/lby-docker/req2test/user')
base=Path('/root/Baxxhy/work2/reproductions/req2test')
out=[]
for d in sorted(base.glob('req2test-paired80-20261123-?')):
    state=json.loads((d/'state.json').read_text())
    ids={json.loads(l)['instance_id'] for f in (h/'runs'/d.name/'input').glob('*-audit-*.jsonl') for l in f.open()}
    for t in state['tasks'].values():
        iid=t['id']
        if iid not in ids:continue
        project=t['project'];r=h/'benchmark/runs'/f'{d.name}-regenerated-{project}'/project/'th/exec.jsonl'
        row=next(x for x in map(json.loads,r.open()) if x['item_id']==iid)
        pred=Path(t['prediction'])
        log=pred.parent/'workspaces/0000.log'
        m=json.loads((h/'runs'/d.name/'manifests/items'/(t['safe']+'.jsonl')).read_text())
        messages=[]; checks=[]
        for n,l in enumerate(log.open(),1):
            try: event=json.loads(l)
            except ValueError:continue
            item=event.get('item',{})
            if event.get('type')!='item.completed':continue
            cmd=item.get('command','')
            if item.get('type')=='command_execution' and re.search(r'\bphp\s+-l\b|vendor/bin/behat\b|debug:(?:container|autowiring)\b',cmd):
                # Discard echoed source code and multi-line file writes.
                if len(cmd)<1800 and '<<' not in cmd:
                    checks.append(dict(line=n,exit=item.get('exit_code'),command=cmd))
            if item.get('type')=='agent_message':
                sentences=re.split(r'(?<=[.!?])\s+',re.sub(r'\[[^\]]+\]\([^)]+\)', '[test file]',item.get('text','')))
                for s in sentences:
                    if re.search(r'syntax|verified it parses|did not run|couldn.t run|didn.t run|not run|not verified|not yet.*run|assumes|not.*complete|unable|not.*verified',s,re.I):
                        messages.append(dict(line=n,excerpt=s[:650]))
        out.append(dict(id=iid,project=project,arm=d.name[-1],generation_log=str(log),generation_log_sha256=hashlib.sha256(log.read_bytes()).hexdigest(),
                         generation_attempts=t['gen_attempts'],wiring_hint=[s for s in m['placement']['rules'] if 'autowir' in s or 'behat_services' in s],submitted_files=[f['file_path'] for f in row['produced_files']],
                         rejected=row['rejected_files'],registered_contexts=row.get('registered_contexts'),correction_flag=row.get('autowired_services'),messages=messages,checks=checks))
assert len(out)==10
print(json.dumps(out,ensure_ascii=False,indent=2))
