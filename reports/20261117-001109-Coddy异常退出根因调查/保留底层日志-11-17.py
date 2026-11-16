import json, os, pathlib, uuid
import sys
from req2test import ENGINE_ROOT
sys.path.insert(0, str(ENGINE_ROOT))
from r2t.go import runtime
original = runtime.capture_execution
out = pathlib.Path(__file__).parent / 'native-evidence'
out.mkdir(exist_ok=True)
def observed(*args, **kwargs):
    captured = original(*args, **kwargs)
    target = out / (str(os.getpid()) + '-' + uuid.uuid4().hex)
    target.mkdir()
    completed = captured.completed
    record = {'context': captured.context if hasattr(captured, 'context') else kwargs.get('context'),
              'mutation': kwargs.get('mutation'),
              'returncode': None if completed is None else completed.returncode}
    (target / 'capture.json').write_text(json.dumps(record, default=str))
    if completed is not None:
        (target / 'stdout.txt').write_text(completed.stdout or '')
    if captured.native:
        (target / 'native.jsonl').write_bytes(captured.native)
    return captured
runtime.capture_execution = observed
from req2test.cli import main
raise SystemExit(main())
