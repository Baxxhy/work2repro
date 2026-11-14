import json, os, signal, subprocess, sys, time
from pathlib import Path
p = Path(sys.argv[1])
s = json.loads(p.read_text())
os.chdir(s['cwd'])
env = os.environ.copy()
env.update(s.get('env', {}))
start = time.time()
try:
    proc = subprocess.Popen(s['argv'], env=env)
    def stop(sig, frame):
        proc.send_signal(sig)
    signal.signal(signal.SIGTERM, stop)
    rc = proc.wait()
    result = {'returncode': rc, 'started': start, 'finished': time.time()}
except BaseException as exc:
    result = {'returncode': 255, 'started': start, 'finished': time.time(), 'error': repr(exc)}
out = p.parent/'exit.json'
tmp = out.with_suffix('.tmp')
tmp.write_text(json.dumps(result))
tmp.replace(out)
raise SystemExit(result['returncode'])
