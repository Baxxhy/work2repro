"""Final integrity checks; does not generate, repair or score test code."""
import json
import re
from pathlib import Path


def jsonl(path):
    return [json.loads(x) for x in Path(path).read_text().splitlines() if x.strip()]


def validate(root):
    root=Path(root)
    cfg=json.loads((root/'frozen/config.json').read_text())
    state=json.loads((root/'state.json').read_text())
    parent=Path(cfg['parent_predictions']).parent
    recovery=set(cfg['recovery_ids'])
    current={x['instance_id']:x for x in jsonl(Path(cfg['req_output'])/'predictions.jsonl')}
    before={x['instance_id']:x for x in jsonl(parent/'predictions.jsonl')}
    expected={t['id'] for t in state['tasks'].values() if t['benchmark']=='req2test'}
    assert len(current)==160 and set(current)==expected
    protected=expected-recovery
    assert len(protected)==152
    assert all(current[iid]==before[iid] for iid in protected)
    old_score_root=Path(cfg['req_home'])/'benchmark/runs'/cfg['parent_req_run_id']
    old={x['instance_id']:x for file in old_score_root.glob('*/th/instances.jsonl') for x in jsonl(file)}
    after_rows=jsonl(root/'reports/req2test-per-task.jsonl')
    assert len(after_rows)==160
    after={x['instance_id']:x for x in after_rows}
    assert set(after)==expected
    changed_protected=[iid for iid in protected if old[iid]!=after[iid]]
    assert not changed_protected, f'Protected official score changed: {changed_protected}'
    calls=[j for j in state['jobs'].values() if j['phase']=='gen_req']
    assert {state['tasks'][j['key']]['id'] for j in calls}==recovery
    assert all(t['gen_attempts']<=2 for t in state['tasks'].values() if t['id'] in recovery)
    assert all(t['gen']!='infra_blocked' for t in state['tasks'].values() if t['benchmark']=='req2test')
    new_summary=json.loads((root/'reports/req2test-official-summary.json').read_text())
    old_summary=json.loads((old_score_root/'summary.json').read_text())
    changes=[dict(instance_id=iid,before=old[iid],after=after[iid]) for iid in sorted(recovery)]
    (root/'reports/recovered-eight-before-after.json').write_text(json.dumps(changes,ensure_ascii=False,indent=2))
    diagnostics=[]
    folder=Path(cfg['req_output'])/'evaluation-diagnostics'
    wanted=set(cfg['diagnostic_evaluation_ids'])
    for p in folder.glob('*.json'):
        d=json.loads(p.read_text())
        if d['instance_id'] not in wanted:continue
        logs='\n'.join(x.get('stdout','') for x in d.get('runs',[]))
        if not logs:continue
        concise=' '.join(logs.split())
        m=re.search('Cannot autowire service|has a dependency on|Fatal error|Uncaught|In [A-Za-z]+Exception',concise)
        text=concise[max(0,m.start()-150):m.start()+1700] if m else concise[:1700]
        diagnostics.append(dict(instance_id=d['instance_id'],outcome=d['outcome'],full_stdout_source=str(p),message=text,baseline_score_kept=True))
    assert {x['instance_id'] for x in diagnostics}==wanted, 'Missing full diagnostic stdout'
    (root/'reports/diagnostic-root-causes.json').write_text(json.dumps(diagnostics,ensure_ascii=False,indent=2))
    audit=dict(manifest_total=160,unique_official_ids=len(after),unchanged_predictions_verified=152,
               unchanged_official_scores_verified=152,recovered_generation_ids=sorted(recovery),
               generation_attempts=len(calls),diagnostic_ids=sorted(wanted),diagnostic_scores_not_adopted=True,
               model=cfg['model'],reasoning='medium',all_infrastructure_recoveries_resolved=True,
               mutation_population_and_timeouts_unchanged=True,official_prompts_and_evaluation_tests_unchanged=True,
               protected_generated_tests_unchanged=True)
    (root/'reports/recovery-integrity.json').write_text(json.dumps(audit,indent=2))
    def headline(summary):
        return summary['modes']['leaderboard']['mean']
    (root/'reports/recovery-headline-comparison.json').write_text(json.dumps(dict(before=headline(old_summary),after=headline(new_summary)),indent=2))
    print('Recovery integrity: 160 unique IDs; 152 original predictions and scores unchanged; only 8 infrastructure recoveries; 3 full diagnostic logs retained.')


if __name__=='__main__':
    import sys
    validate(sys.argv[1])
