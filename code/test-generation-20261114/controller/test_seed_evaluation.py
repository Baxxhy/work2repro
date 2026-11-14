import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from seed_evaluation import seed_evaluations


class ReuseEvidenceTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.home=self.root/'user'
        self.old=self.home/'benchmark/runs/old/project/th'
        self.old.mkdir(parents=True)
        self.out=self.root/'output'
        self.out.mkdir()
        self.parent=self.root/'old-predictions.jsonl'
        self.preds=[dict(instance_id=i,files=[dict(code='old',file_path='t.py')]) for i in ['keep','recover','diagnostic']]
        self.write(self.parent,self.preds)
        self.write(self.out/'predictions.jsonl',self.preds)
        self.write(self.old/'exec.jsonl',[dict(item_id=i,outcome='passed') for i in ['keep','recover','diagnostic']])
        self.write(self.old/'mutation/w0.jsonl',[dict(instance_id=i,mutant_id='m',outcome='failed') for i in ['keep','recover','diagnostic']])
        self.write(self.old/'mutation.baseline.jsonl',[dict(instance_id=i,**{'class':'passed'}) for i in ['keep','recover','diagnostic']])
        self.cfg=dict(req_home=str(self.home),parent_req_run_id='old',parent_predictions=str(self.parent),req_output=str(self.out),recovery_ids=['recover'],diagnostic_evaluation_ids=['diagnostic'])
        self.state=dict(tasks={i:dict(benchmark='req2test',project='project',id=i) for i in ['keep','recover','diagnostic']},project_run_ids={'project':'new'})
        self.dest=self.home/'benchmark/runs/new/project/th'
        self.chown=patch('seed_evaluation.os.chown')
        self.chown.start();self.addCleanup(self.chown.stop)

    def write(self,path,rows):
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(''.join(json.dumps(x)+'\n' for x in rows))

    def test_keeps_diagnostic_score_and_excludes_recovered_candidate(self):
        original=(self.old/'exec.jsonl').read_bytes()
        seed_evaluations(self.root,self.cfg,self.state)
        rows=[json.loads(x) for x in (self.dest/'exec/raw/w_reused.jsonl').read_text().splitlines()]
        self.assertEqual({x['item_id'] for x in rows},{'keep','diagnostic'})
        mutation=[json.loads(x) for x in (self.dest/'mutation/reused-w0.jsonl').read_text().splitlines()]
        self.assertEqual({x['instance_id'] for x in mutation},{'keep','diagnostic'})
        self.assertFalse((self.dest/'predictions.sha256').exists())
        self.assertFalse((self.dest/'mutation.done.json').exists())
        self.assertEqual((self.old/'exec.jsonl').read_bytes(),original)

    def test_rejects_changed_candidate_outside_recovery(self):
        changed=copy.deepcopy(self.preds);changed[0]['files'][0]['code']='changed'
        self.write(self.out/'predictions.jsonl',changed)
        with self.assertRaisesRegex(AssertionError,'outside approved recovery'):
            seed_evaluations(self.root,self.cfg,self.state)

    def test_can_resume_after_successful_seed(self):
        seed_evaluations(self.root,self.cfg,self.state)
        original=(self.dest/'exec/raw/w_reused.jsonl').read_bytes()
        seed_evaluations(self.root,self.cfg,self.state)
        self.assertEqual((self.dest/'exec/raw/w_reused.jsonl').read_bytes(),original)


if __name__=='__main__':unittest.main()
