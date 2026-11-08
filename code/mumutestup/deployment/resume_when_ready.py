"""One-shot startup gate: resume the existing run once the model is ready."""
import hashlib
import json
import os
from pathlib import Path
import time
import urllib.request

ROOT = Path('/root/Baxxhy/work2/reproductions/mumutestup')
RUN = ROOT / 'runs/qwen27b-full'
TRANSITION = RUN / 'hardware-transitions/tp4-to-tp2-20261030/transition.json'
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
deadline = time.monotonic() + 2400
while True:
    try:
        with opener.open('http://127.0.0.1:8000/health', timeout=3) as response:
            if response.status == 200:
                break
    except Exception:
        pass
    if time.monotonic() >= deadline:
        raise TimeoutError('Model startup did not finish; experiment was not started.')
    time.sleep(10)

transition = json.loads(TRANSITION.read_text())
for relative, expected in transition['finished_sha256'].items():
    actual = hashlib.sha256((RUN / relative).read_bytes()).hexdigest()
    if actual != expected:
        raise RuntimeError(f'Completed sample changed before resume: {relative}')
transition.update(resume_started_at=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                  resume_pid=os.getpid(), completed_records_verified=len(transition['finished_sha256']),
                  monitoring='No ongoing monitoring; user requested background execution only.')
TRANSITION.write_text(json.dumps(transition, indent=2) + '\n')
print(json.dumps({'resume_pid': os.getpid(), 'preserved': len(transition['finished_sha256'])}), flush=True)
os.execv('/bin/bash', ['bash', str(ROOT / 'deployment/start_full.sh'), '--resume'])
