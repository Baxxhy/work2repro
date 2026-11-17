from pathlib import Path
import sys,json,subprocess,unittest,copy
repo=Path('/root/lby-docker/req2test/user/repo');sys.path[:0]=[str(repo),str(repo/'benchmark'),'/root/lby-docker/req2test/recovery-control-20261113-v1/recorder-compat-20261117-v1']
from r2t.go import registry,runtime
from recorder_compat import install,corrected,OLD,NEW

class RecordedFailures(unittest.TestCase):
 def test_support_change_is_confined_to_passed_recorder(self):
  before=registry.support_files();install();after=registry.support_files(); key='_bench/go/support/harness.go'
  self.assertEqual(set(before),set(after))
  self.assertEqual(after[key].replace(NEW,OLD,1),before[key])
  self.assertEqual({k for k in before if before[k]!=after[k]},{key})
 def test_actual_saved_failures_obey_existing_crash_rule(self):
  root=Path('/root/lby-docker/req2test/user/benchmark/runs/req2test-eval2051-resume-20261117-v1-coddy-agent/coddy-agent/th/mutation-raw/a5')
  count=0
  for f in sorted(root.glob('*.go-evidence/*/native/1/context.json')):
   n=f.parent; context=json.loads(f.read_text());raw=(n/'native.jsonl').read_bytes();source=(n/'feature.feature').read_text();mapping=json.loads((n/'plan.json').read_text())['map'];stdout=(n/'stdout.txt').read_text()
   completed=subprocess.CompletedProcess([],1,stdout,'')
   with self.subTest(path=str(n)):
    self.assertEqual(runtime._go_crash(completed,context),('kill','go_parent_failnow'))
    with self.assertRaises(registry.GodogRefused):registry.read_crash_prefix(raw,context=context,feature_source=source,source_map=mapping,hook_failure=True)
    events=[json.loads(l) for l in raw.splitlines()]
    self.assertEqual([x['event'] for x in events],['interposed','run_started','feature','pickle','status'])
    self.assertEqual(events[-1]['status'],'passed')
    # The new recorder emits no Passed event when Defined never started it.
    prefix=b''.join(raw.splitlines(keepends=True)[:-1])
    self.assertEqual(registry.read_crash_prefix(prefix,context=context,feature_source=source,source_map=mapping,hook_failure=True),4)
    with self.assertRaises(registry.GodogRefused):registry.read_runtime_native(prefix,context=context,feature_source=source,source_map=mapping,exit_code=1,hook_failure=True)
    with self.assertRaises(registry.GodogRefused):registry.read_crash_prefix(prefix[:-1],context=context,feature_source=source,source_map=mapping,hook_failure=True)
    count+=1
  self.assertEqual(count,3)

if __name__=='__main__':unittest.main(verbosity=2)
