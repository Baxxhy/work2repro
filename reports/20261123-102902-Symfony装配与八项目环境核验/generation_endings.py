from pathlib import Path
import json,re,sys
rows=json.loads(sys.stdin.read())
out=[]
for x in rows:
    p=Path(x['generation_log']);events=[];wiring=[];end=None;files=[]
    for n,l in enumerate(p.open(),1):
        if l.startswith('run_agent:') and 'LLM call' in l:
            end=l.strip()
        try:e=json.loads(l)
        except ValueError:continue
        item=e.get('item',{});evt=e.get('type')
        if evt in ('turn.completed','turn.failed','error'):events.append((n,evt))
        if evt=='item.completed':
            cmd=item.get('command','')
            if 'behat_services.yml' in cmd:
                write=bool(re.search(r'(?:cat\s*>|tee\s+|(?:Add|Update) File:)\s*\S*behat_services.yml',cmd))
                wiring.append(dict(line=n,write_pattern=write,exit=item.get('exit_code')))
            if item.get('type')=='file_change':
                for c in item.get('changes',[]):
                    if isinstance(c,dict) and str(c.get('path','')).endswith('behat_services.yml'):files.append(n)
    out.append(dict(id=x['id'],arm=x['arm'],official_end=end,turn_events=events,wiring_command_events=wiring,wiring_file_events=files))
print(json.dumps(out,indent=2,ensure_ascii=False))
