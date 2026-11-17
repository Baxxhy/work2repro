"""Run upstream replay tests with fixture helper text rebased to this recorder.

Fixture recordings and assertions are unchanged. Three Go-compiler tests need
an installed host Go toolchain and are separately covered by native validation.
"""
import sys,json,unittest,os
from pathlib import Path
from unittest.mock import patch
repo=Path('/root/lby-docker/req2test/user/repo');sys.path[:0]=[str(repo),str(repo/'benchmark'),'/root/lby-docker/req2test/recovery-control-20261113-v1/recorder-compat-20261117-v1']
from recorder_compat import install,OLD,NEW
install()
original_bytes=Path.read_bytes;original_text=Path.read_text

def rebase(path,raw):
 if '/r2t/go/fixtures/' not in str(path) or path.suffix!='.json':return raw
 try:x=json.loads(raw)
 except (ValueError,UnicodeDecodeError):return raw
 if isinstance(x,dict) and isinstance(x.get('helper_source'),str) and OLD.decode() in x['helper_source']:
  x['helper_source']=x['helper_source'].replace(OLD.decode(),NEW.decode(),1)
  out=json.dumps(x)
  return out.encode() if isinstance(raw,bytes) else out
 return raw

def read_bytes(p):return rebase(p,original_bytes(p))
def read_text(p,*a,**kw):return rebase(p,original_text(p,*a,**kw))
exclude={'r2t.go.runtime_selftest.DiagnosticProducerTests.test_real_parser_scaffold_frames_and_unattributed_compiler_failure','r2t.go.runtime_selftest.SensitivityOverlayTests.test_real_compiler_accepts_every_supplied_combination','r2t.go.measurement_selftest.RecorderTests.test_step_splits_an_entry_and_orders_last'}
names=['r2t.go.runtime_selftest','r2t.go.mutation_runtime_selftest','r2t.go.measurement_selftest','r2t.go.execution_selftest']
def flatten(s):
 for t in s:
  if isinstance(t,unittest.TestSuite):yield from flatten(t)
  else:yield t
with patch.object(Path,'read_bytes',read_bytes),patch.object(Path,'read_text',read_text):
 tests=list(flatten(unittest.defaultTestLoader.loadTestsFromNames(names)));selected=tests if os.environ.get('INCLUDE_NATIVE_GO')=='1' else [t for t in tests if t.id() not in exclude]
 print('Selected',len(selected),'excluded host-Go tests',[t.id() for t in tests if t not in selected],flush=True)
 result=unittest.TextTestRunner(verbosity=1).run(unittest.TestSuite(selected))
sys.exit(not result.wasSuccessful())
