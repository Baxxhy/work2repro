import datetime
import json
import os
from pathlib import Path
import signal
import subprocess
import time

root = Path('/root/lby-docker/req2test/protocol-recheck-20261116-155959')
root.mkdir(exist_ok=True)
projects = ['kapua', 'coddy-agent', 'coreshop', 'sylius', 'prestashop', 'e-petitions']
state = {'started': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'timeout_seconds': 300, 'concurrency': 1, 'results': []}

def save():
    temporary = root / 'progress.tmp'
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2))
    temporary.replace(root / 'progress.json')

for project in projects:
    state['current'] = project
    save()
    session_pid = subprocess.check_output(['systemctl', 'show', 'user@1001.service', '-p', 'MainPID', '--value'], text=True).strip()
    command = ['nsenter', '-t', session_pid, '-m', '--', 'runuser', '-u', 'r2tbench', '--', 'bash', '-c',
               'source /root/lby-docker/req2test/user/env.sh; exec req2test runtime preflight --project ' + project + ' --workspace-root /root/lby-docker/req2test/user/runs/protocol-probe-20261116']
    started = time.monotonic()
    with (root / (project + '.stdout')).open('w') as stdout, (root / (project + '.stderr')).open('w') as stderr:
        process = subprocess.Popen(command, stdout=stdout, stderr=stderr, start_new_session=True)
        state['pid'] = process.pid
        save()
        timed_out = False
        try:
            exit_code = process.wait(timeout=300)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(process.pid, signal.SIGKILL)
            try:
                exit_code = process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                exit_code = None
    row = {'project': project, 'exit': exit_code, 'timed_out': timed_out, 'elapsed_seconds': round(time.monotonic() - started, 3)}
    state['results'].append(row)
    save()
    if exit_code is None:
        state['blocked'] = 'diagnostic process did not exit after kill; stop to avoid accumulating blocked processes'
        break
state['current'] = None
state['finished'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
save()
