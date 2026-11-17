"""Track official per-task completion; do not change scores or outcomes."""
INFRA = frozenset({'harness_error','scenario_not_found','fixture_consumed'})

def apply_project_status(tasks, project, rows, disclosure):
    expected = {t['id']:t for t in tasks.values() if t.get('benchmark')=='req2test' and t.get('project')==project}
    actual={}
    for row in rows:
        iid=row['item_id']
        if iid in actual: raise ValueError('Duplicate official instance: '+iid)
        actual[iid]=row
    if set(actual)!=set(expected):raise ValueError('Official task population mismatch')
    excluded=set(disclosure.get('infrastructure_excluded',[]))|set(disclosure.get('baseline_infrastructure',[]))
    outside=disclosure.get('outside_ladder_excluded',{})
    if not excluded.issubset(expected) or not set(outside).issubset(expected):raise ValueError('Unknown excluded instance')
    for iid,t in expected.items():
        row=actual[iid];outcome=row['outcome'];blocked=iid in excluded or outcome in INFRA
        t.update(evaluation='infra_blocked' if blocked else 'finished',official_outcome=outcome)
        if blocked:t['evaluation_reason']='official_'+outcome if outcome in INFRA else 'official_baseline_infrastructure'
        else:t.pop('evaluation_reason',None)
        if iid in outside:t['official_score_exclusion']=outside[iid]
        else:t.pop('official_score_exclusion',None)
    return 'infra_blocked' if any(t['evaluation']=='infra_blocked' for t in expected.values()) else 'finished'
