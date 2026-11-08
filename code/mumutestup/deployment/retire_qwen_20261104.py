#!/usr/bin/env python3
"""Remove only the explicitly retired Qwen deployment, preserving results."""
import json
import os
from pathlib import Path
import signal
import shutil
import subprocess
import time


def main():
    root = Path('/root/Baxxhy/work2/reproductions/mumutestup')
    weights = Path('/root/Baxxhy/model/Qwen3.5-27B')
    report_path = root / 'deployment/qwen-retirement-20261104.json'
    if report_path.exists():
        print(report_path.read_text())
        return
    matches = []
    for path in Path('/proc').glob('[0-9]*/cmdline'):
        try:
            args = path.read_bytes().replace(b'\0', b' ').decode(errors='replace')
            pid = int(path.parent.name)
            if 'vllm serve ' + str(weights) in args:
                matches.append((pid, os.getpgid(pid)))
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            pass
    if len(matches) > 1 or any(pid != pgid for pid, pgid in matches):
        raise RuntimeError('Unexpected Qwen process ownership; refusing broad stop')
    before = subprocess.run(['nvidia-smi', '--query-gpu=index,memory.used', '--format=csv,noheader'], capture_output=True, text=True).stdout
    record = {'requested_at': time.time(), 'weights_path': str(weights), 'processes': matches,
              'gpu_before': before, 'preserved': ['runs', 'CPU all-MiniLM-L6-v2 embedding service', 'shared vLLM environment', 'other GPU workloads']}
    if weights.exists():
        if weights.is_symlink() or weights.resolve() != weights:
            raise RuntimeError('Unexpected weights symlink')
        record['files'] = [{'path': str(p.relative_to(weights)), 'bytes': p.stat().st_size}
                           for p in weights.rglob('*') if p.is_file()]
        record['weight_bytes'] = sum(x['bytes'] for x in record['files'])
    else:
        record['weight_bytes'] = 0
    # Persist intent and exact scope before stopping/deleting anything.
    report_path.with_suffix('.pending.json').write_text(json.dumps(record, indent=2)+'\n')
    for pid, pgid in matches:
        os.killpg(pgid, signal.SIGTERM)
        deadline = time.monotonic() + 30
        while Path(f'/proc/{pid}').exists() and time.monotonic() < deadline:
            time.sleep(.5)
        if Path(f'/proc/{pid}').exists():
            # Re-check the executable identity rather than trusting a reused PID.
            current = Path(f'/proc/{pid}/cmdline').read_bytes().replace(b'\0', b' ').decode(errors='replace')
            if 'vllm serve ' + str(weights) not in current:
                raise RuntimeError('Qwen process identity changed')
            os.killpg(pgid, signal.SIGKILL)
            record['forced_kill'] = True
    if weights.exists():
        shutil.rmtree(weights)
    for name in ('serve-qwen35-mumutestup.sh', 'start_full.sh'):
        entry = root / 'deployment' / name
        if entry.exists():
            entry.rename(entry.with_name(name + '.retired-20261104'))
    pidfile = root / 'deployment/qwen35-server.pid'
    if pidfile.exists():
        pidfile.rename(pidfile.with_name(pidfile.name + '.retired-20261104'))
    record['finished_at'] = time.time()
    record['weights_removed'] = not weights.exists()
    record['gpu_after'] = subprocess.run(['nvidia-smi', '--query-gpu=index,memory.used', '--format=csv,noheader'], capture_output=True, text=True).stdout
    report_path.write_text(json.dumps(record, indent=2)+'\n')
    print(json.dumps({k: record.get(k) for k in ('weights_removed', 'weight_bytes', 'processes', 'forced_kill', 'gpu_before', 'gpu_after')}), flush=True)


if __name__ == '__main__':
    main()
