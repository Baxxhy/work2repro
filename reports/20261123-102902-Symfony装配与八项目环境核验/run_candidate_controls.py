from pathlib import Path
import subprocess, sys,json
from req2test import predictions
root=Path(__file__).parent
errors=[]
for stage in ('fixed','refcandidate'):
    for proj in ('sylius','coreshop'):
        if stage=='refcandidate':
            ids=[json.loads(l)['instance_id'] for l in (root/f'fixed-{proj}.jsonl').read_text().splitlines()]
            p=root/f'refcandidate-{proj}.jsonl'
            assert not p.exists()
            gt=predictions.from_gt(proj,ids,view='th',model_name='diagnostic-reference-candidate')
            predictions.dump(gt.values(),p)
            reread=predictions.load(p,project=proj,view='th')
            assert all(not x.ground_truth and x.files==gt[i].files for i,x in reread.items())
        res=subprocess.run([sys.executable,str(root/'replay_diagnostic.py'),stage,proj])
        if res.returncode:errors.append((stage,proj,res.returncode))
if errors:raise SystemExit(str(errors))
