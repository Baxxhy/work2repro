"""Independent queue for the diagnostic rerun. No writes to the source run."""
import sys
from pathlib import Path

control = Path(__file__).with_name('controller.py')
source = control.read_text()
split = "\nlock=(ROOT/'controller.lock')"
assert source.count(split) == 1
# Reuse the original gateway, user environment, process isolation and durable job records.
exec(compile(source.split(split)[0], str(control), 'exec'))

with (ROOT/'diagnostic.lock').open('w') as owner:
    fcntl.flock(owner, fcntl.LOCK_EX|fcntl.LOCK_NB)
    server = GatewayServer(('127.0.0.1',CFG['gateway_port']),Gateway)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    original = json.loads((ROOT/'frozen/replays.json').read_text())
    old_rows = {iid:row['outcome'] for iid,row in original.items()}
    wrapper = Path(CFG['diagnostic_eval_wrapper'])
    projects = sorted({row['project'] for row in original.values()} | {t['project'] for t in S['tasks'].values()})

    def finish(j, result):
        j.update(state='finished',returncode=result['returncode'],end=time.time())
        if j['phase'] == 'gen_req':
            t = S['tasks'][j['key']]
            outcome = inspect_req_generation(pred_path(t),j['path'],t['id'])
            statuses = {e['status'] for e in j.get('api_errors',[])}
            uncompleted = not outcome['turn_completed']
            # The gateway can receive a generic 429 that the legacy regex misses.
            if uncompleted and statuses & {401,403,429,500,502,503,504}:
                outcome.update(kind='infrastructure',reason='interrupted_provider_request')
            elif uncompleted and not outcome['prediction_valid'] and outcome['llm_calls'] in (0,None):
                outcome.update(kind='infrastructure',reason='launch_failed_before_generation')
            j['generation_outcome'] = outcome
            atomic(Path(j['path'])/'generation-outcome.json',outcome)
            if outcome['kind'] == 'infrastructure':
                if t['gen_attempts']<2 and not S['block']:
                    t.update(gen='pending', not_before=max(time.time()+120,S['cooldown_until']))
                else:
                    t['gen']='infra_blocked'
            else:
                t['gen']='finished' if outcome['prediction_valid'] else 'generation_failed'
            t['reason']=outcome['reason']
        else:
            S['groups'][j['key']].update(state='finished' if result['returncode']==0 else 'infra_blocked',returncode=result['returncode'])
        event('diagnostic_job_terminal',phase=j['phase'], key=j['key'],job=j['id'],returncode=result['returncode'])

    def eval_group(phase, project, selected):
        if not selected:
            return
        group = phase+'-'+project
        if group in S['groups'] or any(j['key']==group for j in running('eval_diagnostic')):
            return
        if len(running('eval_diagnostic'))>=2 or any(j.get('project')==project for j in running('eval_diagnostic')):
            return
        out=RROOT/'input'
        predictions=out/(group+'.jsonl')
        ids=out/(group+'.ids')
        predictions.write_text(''.join(Path(p).read_text().strip()+'\n' for p in selected.values()))
        ids.write_text('\n'.join(selected)+'\n')
        for path in (predictions,ids):
            os.chown(path,1001,1001)
            path.chmod(0o644)
        run_id=ROOT.name+'-'+group
        argv=[str(RH/'venv/bin/req2test'),'evaluate','--predictions',str(predictions),
              '--instances',str(ids),'--split','eval','--project',project,'--workers',str(min(2,len(selected))),
              '--metrics','exec','--run-id',run_id]
        job=launch('eval_diagnostic',group,user_cmd(argv),RR)
        job['project']=project
        S['groups'][group]=dict(state='running',count=len(selected),run=run_id,
                                project=project,job=job['id'],ids=list(selected))
        atomic(STATE,S)

    def results():
        results={}
        for g in S['groups'].values():
            folder=RH/'benchmark/runs'/g['run']/g['project']/'th'
            f=folder/'exec.jsonl'
            if f.is_file():
                for line in f.read_text().splitlines():
                    row=json.loads(line)
                    iid=row['item_id']
                    if iid in g['ids']:
                        results[iid]=dict(before=old_rows.get(iid,'no_files_returned'), after=row['outcome'],
                                          group=g['run'],metadata_error=(row.get('metadata') or {}).get('harness_error'))
        atomic(ROOT/'result_comparison.json',results)
        return len(results)

    while True:
        with LOCK:
            for j in running():
                exit_file=Path(j['path'])/'exit.json'
                if exit_file.is_file():
                    finish(j,json.loads(exit_file.read_text()))
                elif not alive(j['pid']):
                    finish(j,dict(returncode=255))
            recover_quota_if_ready()
            r=resources()
            if r['available_gib']>=24 and r['disk_free_gib']>=180 and r['load']<70:
                if not S['block'] and time.time()>=S['cooldown_until']:
                    for k,t in S['tasks'].items():
                        if gen_count()>=S['generation_cap']:break
                        if t['gen']!='pending' or time.time()<t.get('not_before',0):continue
                        t['gen_attempts']+=1
                        t['gen']='running'
                        out=req_path(t)/('attempt-'+str(t['gen_attempts']))
                        out.mkdir(parents=True,exist_ok=True)
                        for p in (out,out.parent):os.chown(p,1001,1001)
                        t['prediction']=str(out/'predictions.jsonl')
                        token=uuid.uuid4().hex
                        argv=[str(RH/'venv/bin/python'),str(RROOT/'agent.py'),
                              '--agent','codex','--model','baseline/gpt-6-luna','--tasks',
                              str(RROOT/'manifests/items'/(t['safe']+'.jsonl')),'-o',str(out),
                              '--model-name','codex-gpt-6-luna-'+('medium' if CFG['arm']=='a' else 'high'),'--workers','1','--timeout','3600']
                        launch('gen_req',k,user_cmd(argv,dict(PAIRED_ARM=CFG["arm"], BASELINE_GATEWAY_URL=f'http://127.0.0.1:{CFG["gateway_port"]}/{token}',
                              BASELINE_GATEWAY_KEY='local-transport-not-a-provider-secret')),RR,token=token)
                for project in projects:
                    eval_group('original',project,{i:r['prediction'] for i,r in original.items() if r['project']==project})
                for project in projects:
                    pt=[t for t in S['tasks'].values() if t['project']==project]
                    if pt and all(t['gen'] not in ('pending','running') for t in pt):
                        eval_group('regenerated',project,{t['id']:t['prediction'] for t in pt if t['gen']=='finished'})
            n=results()
            summary=dict(total=80,generation=dict(collections.Counter(t['gen'] for t in S['tasks'].values())),
                         generation_workers=gen_count(),evaluation_groups=S['groups'],observed_execution_rows=n,
                         quota=bool(S['block']),resources=r,updated=time.time())
            atomic(ROOT/'progress.json',summary)
            atomic(STATE,S)
            old_done=all('original-'+p in S['groups'] for p in {x['project'] for x in original.values()})
            gen_done=all(t['gen'] not in ('pending','running') for t in S['tasks'].values())
            new_done=all('regenerated-'+t['project'] in S['groups'] for t in S['tasks'].values() if t['gen']=='finished')
            if old_done and gen_done and new_done and not running():
                atomic(ROOT/'completion.json',summary)
                break
        time.sleep(10)
