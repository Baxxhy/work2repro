import pathlib
import tempfile
import unittest
from coddy_resource_guard import policy, restore


class ResourceGuardTests(unittest.TestCase):
    def test_pressure_policy(self):
        self.assertIsNone(policy(80,40,0,3))
        self.assertEqual(policy(15,40,0,3),30)
        self.assertIsNone(policy(64,60,22,39))
        self.assertEqual(policy(24,40,11,3),60)
        self.assertEqual(policy(80,161,0,3),120)
        self.assertEqual(policy(80,40,0,61),180)

    def test_restore_preserves_aborted_evidence_and_worker_ownership(self):
        with tempfile.TemporaryDirectory() as temp:
            root=pathlib.Path(temp)
            source=root/'benchmark/runs/example/coddy-agent/th'
            (source/'mutation').mkdir(parents=True)
            (source/'mutation/w0.jsonl').write_text('aborted attempt\n')
            (source/'mutation-raw').mkdir()
            (source/'mutation-raw/raw.json').write_text('raw evidence')
            (source/'mutation.done.json').write_text('marker')
            job=root/'job';checkpoint=job/'checkpoint';checkpoint.mkdir(parents=True)
            (job/'job.log').write_text('isolated fixture without a worker pool')
            (checkpoint/'w0.jsonl').write_text('original completed row\n')
            events=[]
            restore({'id':'test-job','path':str(job),'official_run_id':'example','resource_checkpoint':str(checkpoint)},
                    {'req_home':str(root)},lambda *args,**kwargs:events.append((args,kwargs)))
            self.assertEqual((source/'mutation/w0.jsonl').read_text(),'original completed row\n')
            self.assertEqual((job/'resource-aborted-evidence/mutation/w0.jsonl').read_text(),'aborted attempt\n')
            self.assertTrue((job/'resource-aborted-evidence/mutation-raw/raw.json').exists())
            self.assertTrue((job/'resource-aborted-evidence/mutation.done.json').exists())
            self.assertFalse((source/'mutation.done.json').exists())
            self.assertEqual((source/'mutation').stat().st_uid,1001)
            self.assertEqual((source/'mutation/w0.jsonl').stat().st_uid,1001)
            self.assertEqual(len(events),1)


if __name__=='__main__':
    unittest.main()
