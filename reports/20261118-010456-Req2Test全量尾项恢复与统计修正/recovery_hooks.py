"""Bounded infrastructure replay and additive evidence, never new scores."""
import functools,json,os,sys,uuid
from pathlib import Path

TARGETS={'coddy-agent/features/hooks_subagents.feature:28','coddy-agent/features/llm_limit_wait.feature:45'}

def reserve_capture(base,iid):
    folder=Path(base)/(iid.rsplit(':',1)[-1]+'-'+uuid.uuid4().hex)
    folder.mkdir(parents=True)
    capture=folder/'capture'
    capture.mkdir()
    return folder,capture

def install():
    # Official scoring classifies fixture_consumed as infrastructure. Include
    # those rows only in this explicitly authorized, bounded recovery replay.
    from req2test import execute
    execute.RETRY_OUTCOMES=execute.RETRY_OUTCOMES|{'fixture_consumed'}
    from r2t.bench import runner
    runner._RETRYABLE_OUTCOMES=runner._RETRYABLE_OUTCOMES|{'fixture_consumed'}
    from r2t.go import runtime
    from r2t.stacks import godog
    original=runtime.run_solution
    @functools.wraps(original)
    def recorded(harness,feature,scenario,solution,*args,**kwargs):
        context=runtime._context(harness,feature,scenario)
        iid='coddy-agent/'+context['feature_path']+':'+str(context['scenario_line'])
        folder=None
        if iid in TARGETS and kwargs.get('mutation') is None and kwargs.get('evidence_dir') is None:
            base=Path(os.environ['R2T_RECOVERY_DIAGNOSTICS'])/'tail-native'
            folder,capture=reserve_capture(base,iid)
            kwargs['evidence_dir']=capture
            (folder/'selected-context.json').write_text(json.dumps(dict(instance_id=iid,context=context),indent=2))
        try:return original(harness,feature,scenario,solution,*args,**kwargs)
        except BaseException as exc:
            if folder is not None:(folder/'exception.json').write_text(json.dumps(dict(type=type(exc).__name__,message=str(exc)),indent=2))
            raise
    runtime.run_solution=recorded
    for value in list(vars(godog).values()):
        if isinstance(value,type) and value.__dict__.get('run_solution') is original:value.run_solution=recorded
