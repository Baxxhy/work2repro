"""Import only unchanged per-instance evidence into a new official run.

No old identity or completion marker is copied. The official evaluate command
creates the new prediction identity and recomputes behaviour, plans and scoring.
"""
import hashlib
import json
import os
from pathlib import Path


def rows(path):
    path=Path(path)
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()] if path.exists() else []


def write_rows(path, data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():
        assert rows(path)==data, f'Refuse overwriting different seeded evidence: {path}'
        return
    path.write_text(''.join(json.dumps(x,sort_keys=True)+'\n' for x in data))
    os.chown(path,1001,1001)


def seed_evaluations(root, cfg, state):
    root=Path(root); home=Path(cfg['req_home'])
    old=home/'benchmark/runs'/cfg['parent_req_run_id']
    old_pred={x['instance_id']:x for x in rows(cfg['parent_predictions'])}
    new_pred={x['instance_id']:x for x in rows(Path(cfg['req_output'])/'predictions.jsonl')}
    # Log-only checks have their own runs; keep their original baseline scores.
    excluded=set(cfg['recovery_ids'])
    tasks=[t for t in state['tasks'].values() if t['benchmark']=='req2test']
    assert set(new_pred)=={t['id'] for t in tasks}
    evidence=[]
    for project,run_id in state['project_run_ids'].items():
        ids={t['id'] for t in tasks if t['project']==project}
        reuse=ids-excluded
        for iid in reuse:
            assert old_pred[iid]==new_pred[iid], f'Prediction changed outside approved recovery: {iid}'
        source=old/project/'th'
        dest=home/'benchmark/runs'/run_id/project/'th'
        marker=dest/'reused-evidence.json'
        expected_marker=dict(source=str(source),reused_ids=sorted(reuse))
        if marker.exists():
            assert json.loads(marker.read_text())==expected_marker
            evidence.append(dict(project=project,**expected_marker,destination=str(dest)))
            continue
        assert not (dest/'predictions.sha256').exists(), 'Evaluation started before evidence seeding'
        dest.mkdir(parents=True,exist_ok=True)
        old_rows=rows(source/'exec.jsonl')
        selected=[x for x in old_rows if x['item_id'] in reuse]
        assert {x['item_id'] for x in selected}==reuse
        # Native final_rows reads w*.jsonl; the suffix also preserves the
        # predetermined original record after any diagnostic replay rows.
        write_rows(dest/'exec/raw/w_reused.jsonl',selected)
        for p in sorted((source/'mutation').glob('*.jsonl')):
            selected_rows=[x for x in rows(p) if x.get('instance_id',x.get('item_id')) in reuse]
            if selected_rows:write_rows(dest/'mutation'/('reused-'+p.name),selected_rows)
        baseline=[x for x in rows(source/'mutation.baseline.jsonl') if x.get('instance_id',x.get('item_id')) in reuse]
        if baseline:write_rows(dest/'mutation.baseline.jsonl',baseline)
        for parent in [dest.parent.parent,dest.parent,dest,dest/'exec',dest/'exec/raw',dest/'mutation']:
            if parent.exists():os.chown(parent,1001,1001)
        evidence.append(dict(project=project,reused_ids=sorted(reuse),reevaluate_ids=sorted(ids-reuse),
                             source=str(source),destination=str(dest),
                             source_exec_sha256=hashlib.sha256((source/'exec.jsonl').read_bytes()).hexdigest()))
        marker.write_text(json.dumps(expected_marker,indent=2));os.chown(marker,1001,1001)
    (root/'evaluation-reuse-provenance.json').write_text(json.dumps(evidence,indent=2))
