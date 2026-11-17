"""Call the unchanged official CLI; retain pre-truncation evaluator logs only."""
import fcntl
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from req2test.execute import ensure_engine_path

# One coordinator owns a run's mutable evaluation output at a time.
# Keep the descriptor alive until all forked workers exit.
if '--run-id' in sys.argv:
    run_id = sys.argv[sys.argv.index('--run-id') + 1]
    lock_dir = Path(os.environ['REQ2TEST_HOME']) / 'evaluation-locks'
    lock_dir.mkdir(parents=True, exist_ok=True)
    run_lock = (lock_dir / (hashlib.sha256(run_id.encode()).hexdigest() + '.lock')).open('a+')
    try:
        fcntl.flock(run_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit('Evaluation run is already owned by another coordinator')

ensure_engine_path()
from inventory_batch import install
install()
from r2t.bench import runner
from r2t.bench.harness import RunResult

# The engine supports keeping full stdout, but the public evaluate verb does
# not expose its keep-artifacts flag. Enable the additive stdout field only
# in the separate exec-only diagnostic runs; the official scoring row is
# still returned byte-for-byte by the original _record implementation.
if '--metrics' in sys.argv and sys.argv[sys.argv.index('--metrics')+1]=='exec':
    original_to_json=RunResult.to_json
    def with_full_stdout(self, keep_stdout=False):
        return original_to_json(self, keep_stdout=True)
    RunResult.to_json=with_full_stdout

original_record = runner._record


def logged_record(iid, item, produced, generation_seconds, result, *args, **kwargs):
    row = original_record(iid, item, produced, generation_seconds, result, *args, **kwargs)
    target = Path(os.environ['R2T_RECOVERY_DIAGNOSTICS'])
    target.mkdir(parents=True, exist_ok=True)
    payload = dict(instance_id=iid, outcome=row.get('outcome'),
                   index_errors=result.get('index_errors'),
                   runs=[{k:v for k,v in run.items() if k in ('stdout','stdout_tail','outcome','exit_code','wall_seconds')}
                         for run in result.get('runs',[])])
    name = hashlib.sha256(iid.encode()).hexdigest()[:20] + f'-{os.getpid()}-{time.time_ns()}.json'
    (target/name).write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    return row


runner._record = logged_record
from req2test.cli import main
raise SystemExit(main())
