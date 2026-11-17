import unittest
from project_status import apply_project_status
class StatusTests(unittest.TestCase):
 def make(self,n=4):return {str(i):dict(id=str(i),project='p',benchmark='req2test',evaluation='infra_blocked') for i in range(n)}
 def test_one_blocker_does_not_block_whole_project(self):
  t=self.make();r=[dict(item_id=str(i),outcome='harness_error' if i==2 else 'failed') for i in range(4)]
  self.assertEqual(apply_project_status(t,'p',r,{'infrastructure_excluded':['2']}),'infra_blocked')
  self.assertEqual([t[str(i)]['evaluation'] for i in range(4)],['finished','finished','infra_blocked','finished'])
 def test_no_output_is_completed_generation_result(self):
  t=self.make(1);self.assertEqual(apply_project_status(t,'p',[dict(item_id='0',outcome='no_files_returned')],{}),'finished')
 def test_outside_ladder_is_explicit_completed_exclusion(self):
  t=self.make(1);apply_project_status(t,'p',[dict(item_id='0',outcome='passed_but_nonzero_exit')],{'outside_ladder_excluded':{'0':'passed_but_nonzero_exit'}});self.assertEqual(t['0']['evaluation'],'finished');self.assertEqual(t['0']['official_score_exclusion'],'passed_but_nonzero_exit')
 def test_missing_population_rejected_before_mutation(self):
  t=self.make();before=repr(t)
  with self.assertRaises(ValueError):apply_project_status(t,'p',[],{})
  self.assertEqual(repr(t),before)
 def test_duplicate_rejected(self):
  with self.assertRaises(ValueError):apply_project_status(self.make(1),'p',[dict(item_id='0',outcome='passed')]*2,{})
 def test_other_project_unchanged(self):
  t=self.make(1);t['other']=dict(id='x',project='other',benchmark='req2test',evaluation='finished');apply_project_status(t,'p',[dict(item_id='0',outcome='fixture_consumed')],{});self.assertEqual(t['other']['evaluation'],'finished')
class EvidenceDirectoryTests(unittest.TestCase):
 def test_metadata_does_not_occupy_official_capture_directory(self):
  import tempfile
  from pathlib import Path
  from recovery_hooks import reserve_capture
  with tempfile.TemporaryDirectory() as tmp:
   folder,capture=reserve_capture(Path(tmp),'project/feature:28')
   (folder/'selected-context.json').write_text('{}')
   self.assertEqual(list(capture.iterdir()),[])
   self.assertNotEqual(folder,capture)
if __name__=='__main__':unittest.main(verbosity=2)
