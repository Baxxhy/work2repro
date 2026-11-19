import json, csv, sys, re
from pathlib import Path
base=Path('/root/Baxxhy/work2/reproductions/req2test')
runs=sorted(base.glob('req2test-*'),reverse=True)
states={}
for run in runs:
 f=run/'state.json'
 if f.exists() and 'diagnose' not in run.name:
  states[run.name]=json.loads(f.read_text()).get('tasks',{})
w=csv.writer(sys.stdout);w.writerow(['任务','轨迹','正常结束','失败结束','写操作线索','回复含代码块','来源'])
for iid in json.loads(Path('/tmp/empty-audit-ids.json').read_text()):
 t=states['req2test-eval2051-resume-20261117-v1']['req:'+iid]
 pred=Path(t['prediction']); row=json.loads(pred.read_text().strip());assert row['instance_id']==iid and not row['files']
 candidates=[pred,t.get('source_prediction')]
 for st in states.values():
  other=st.get('req:'+iid,{})
  if str(other.get('prediction')) in [str(x) for x in candidates]:
   candidates.append(other.get('source_prediction'))
 events=[];origin=''
 for candidate in filter(None,candidates):
  q=Path(candidate); trace=q.parent/'workspaces/0000.log'
  if trace.exists() and q.is_file():
   source=json.loads(q.read_text().strip())
   if source.get('instance_id')!=iid or source.get('files'): continue
   events=[]
   for l in trace.read_text(errors='replace').splitlines():
    try: events.append(json.loads(l))
    except ValueError: pass
   if events: origin=str(trace);break
 items=[e.get('item',{}) for e in events if e.get('type')=='item.completed']
 writes=[i for i in items if i.get('type')=='file_change' or re.search(r'apply_patch|write_text\(|write_bytes\(|\btee\s|(?:cat|printf|echo)\b[^\n]*\s>\s*[^&/]|\bcp\s|\bsed -i\b',i.get('command',''))]
 w.writerow([iid,bool(events),any(e.get('type')=='turn.completed' for e in events),any(e.get('type')=='turn.failed' for e in events),len(writes),any('```' in i.get('text','') for i in items),origin])
