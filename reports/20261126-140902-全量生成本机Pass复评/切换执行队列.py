"""Hand off one legacy lane only after its coordinator reaches the execution phase."""
import os, signal, subprocess, sys, time
from pathlib import Path
base=Path.home()/'reeval/medium-th-2051-20261126-140902'
service,*projects=sys.argv[1:]
def mainpid():
    return int(subprocess.check_output(['systemctl','--user','show',service,'-p','MainPID','--value'],text=True).strip() or 0)
def processes(pid):
    return [int(x) for x in Path(f'/proc/{pid}/task/{pid}/children').read_text().split()]
def state(pid):
    try: return Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()[0]
    except FileNotFoundError: return None
while (parent:=mainpid()) > 0:
    found=None
    for child in processes(parent):
        try: args=Path(f'/proc/{child}/cmdline').read_bytes().decode().split('\0')
        except FileNotFoundError: continue
        if 'evaluate' not in args or '--project' not in args: continue
        p=args[args.index('--project')+1]
        if p not in projects[::2]: continue
        log=base/'logs'/(p+'.log')
        if log.exists() and ' to run on ' in log.read_text(errors='replace'):
            found=(p,child); break
    if not found:
        time.sleep(3);continue
    p,child=found
    os.kill(parent,signal.SIGSTOP)
    try:
        if child not in processes(parent): continue
        if state(child) not in (None,'Z'):
            os.kill(child,signal.SIGTERM)
            while state(child) not in (None,'Z'): time.sleep(2)
        os.kill(parent,signal.SIGTERM)
    finally:
        try: os.kill(parent,signal.SIGCONT)
        except ProcessLookupError: pass
    while mainpid()==parent: time.sleep(1)
    break
os.execv('/bin/bash',['/bin/bash',str(base/'long.sh'),*projects])
