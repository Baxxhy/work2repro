"""Export task status, unchanged-code comparisons, and log signatures."""
from collections import Counter
import csv
import json
from pathlib import Path
import re
import sys
import time

root = Path(sys.argv[1])
cfg = json.loads((root/'frozen/config.json').read_text())
runtime = Path(cfg['req_output'])
previous = json.loads((root/'frozen/replays.json').read_text())
patterns = {
    'service_binding': r'Cannot autowire|ServiceNotFoundException|non.existent service|cannot be autowired',
    'compiler_or_api': r'cannot find symbol|incompatible types|undefined:|declared and not used|call to undefined|cannot use .+ as .+ in',
    'harness_protocol': r'RuntimeRefused|witness is incomplete|foreign/duplicate status|missing Run start or terminal exit',
    'host_resources': r"can.t start new thread|resource temporarily unavailable|no space left on device|failed to create new OS thread",
    'transport': r'cannot connect to the docker daemon|failed to download|could not transfer artifact|network is unreachable',
    'cleanup_panic': r'(?s)panic: .{0,1800}testing\.\(\*common\)\.runCleanup',
    'fixture_path': r'fixture not found|fixture_consumed',
}
fields = ['instance_id','project','stage','before','after','status','generation_reason','log_signals','group']

def dump(path,data):
    tmp=path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    tmp.replace(path)

def collect():
    state=json.loads((root/'state.json').read_text())
    result={}
    for key,g in state['groups'].items():
        folder=Path(cfg['req_home'])/'benchmark/runs'/g['run']/g['project']/'th'
        f=folder/'exec.jsonl'
        captures={}
        for log in sorted((runtime/'diagnostics'/key).glob('*.json'),key=lambda p:p.stat().st_mtime):
            try:
                data=json.loads(log.read_text())
            except (FileNotFoundError,ValueError):
                continue
            captures[data['instance_id']]=data
        outcomes={}
        if f.exists():
            for line in f.read_text().splitlines():
                value=json.loads(line)
                outcomes[value['item_id']]=value
        for iid in g['ids']:
            execution=outcomes.get(iid,{})
            capture=captures.get(iid,{})
            texts=[str(execution.get('metadata',{})),str(execution.get('stdout_tail',''))]
            if capture.get('outcome')==execution.get('outcome'):
                texts.extend(str(row.get('stdout') or row.get('stdout_tail') or '')
                             for row in capture.get('runs',[]))
            signatures=[name for name,pattern in patterns.items() if any(re.search(pattern,x,re.I) for x in texts)]
            result[iid]=dict(after=execution.get('outcome',''),status=g['state'],group=g['run'],
                             log_signals='|'.join(signatures))
    inventory=[]
    for iid,row in previous.items():
        inventory.append(dict(instance_id=iid,project=row['project'],stage='replay_old_tests',
                              before=row['outcome'],**result.get(iid,dict(status='pending'))))
    for t in state['tasks'].values():
        inventory.append(dict(instance_id=t['id'],project=t['project'],stage='regenerate',
                              before='no_files_returned',generation_reason=t.get('reason',''),
                              **result.get(t['id'],dict(status=t['gen']))))
    assert len(inventory)==len({r['instance_id'] for r in inventory})==308
    path=root/'diagnostic-comparison.csv'
    tmp=path.with_suffix('.csv.tmp')
    with tmp.open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fields,lineterminator='\n')
        writer.writeheader()
        writer.writerows(inventory)
    tmp.replace(path)
    matched=Counter((r['stage'],r['before'],r.get('after') or 'no_row') for r in inventory)
    dump(root/'diagnostic-summary.json',dict(
        tasks=len(inventory),terminal=(root/'completion.json').is_file(),
        transitions=[dict(stage=s,before=b,after=a,count=n) for (s,b,a),n in sorted(matched.items())],
        pending_or_missing_rows=sum(not r.get('after') for r in inventory)))

deadline=time.time()+48*3600
while True:
    collect()
    if (root/'completion.json').exists() or time.time()>=deadline:
        break
    time.sleep(60)
