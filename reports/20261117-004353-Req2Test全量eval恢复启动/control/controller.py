import collections, datetime, fcntl, hashlib, http.server, json, math, os, re
import shutil, signal, socket, sqlite3, subprocess, sys, threading, time, urllib.request, urllib.error, uuid
from pathlib import Path
from generation_outcome import inspect_req_generation
from seed_evaluation import seed_evaluations

ROOT=Path(sys.argv[1]).resolve()
CFG=json.loads((ROOT/'frozen/config.json').read_text())
CFG['req_census_counts']=json.loads((ROOT/'frozen/config.parent.json').read_text())['req_project_counts']
TSB=Path(CFG['tsb_repo']); RH=Path(CFG['req_home']); RR=RH/'repo'
RROOT=Path(CFG['req_output']); STATE=ROOT/'state.json'
LOCK=threading.RLock(); STOP=False
def atomic(path,data):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.tmp')
    with tmp.open('w') as out:out.write(json.dumps(data,indent=2));out.flush();os.fsync(out.fileno())
    tmp.replace(path)
def event(kind,**kw):
    with LOCK:
        with (ROOT/'events.jsonl').open('a') as f:f.write(json.dumps(dict(time=time.time(),kind=kind,**kw))+'\n')
def resources():
    mem={k:int(v.split()[0])*1024 for k,v in (x.split(':',1) for x in Path('/proc/meminfo').read_text().splitlines())}
    return dict(time=time.time(),available_gib=round(mem['MemAvailable']/2**30,2),load=os.getloadavg()[0],
                disk_free_gib=round(shutil.disk_usage(ROOT).free/2**30,2))
def alive(pid):
    try:return Path(f'/proc/{pid}/stat').read_text().split()[2]!='Z'
    except (FileNotFoundError,ProcessLookupError):return False
def text(path):
    try:
        with open(path,'rb') as f:f.seek(max(0,os.fstat(f.fileno()).st_size-160000));return f.read().decode(errors='replace')
    except FileNotFoundError:return ''

if STATE.exists(): S=json.loads(STATE.read_text())
else:
    tasks=json.loads((ROOT/'frozen/tasks.json').read_text())
    S=dict(tasks=tasks,jobs={},builds={},projects={},generation_cap=8,evaluation_cpu_budget=8,
           stage_since=time.time(),stage_done=0,best_rate=0,last_adapt=time.time(),cooldown_until=0,
           gate='pending',block=None,started=time.time(),generation_completions=[],events_429=0,
           request_retries=0,usage={},req_gate_id=next(k for k,t in tasks.items() if t['benchmark']=='req2test'),
           full_req_merged=False,final_report_done=False)
    for k,t in tasks.items():
        t.update(gen='pending',evaluation='pending',gen_attempts=0,eval_attempts=0)
        if t['benchmark']=='tsb':S['builds'][k]='pending'
        else:S['projects'].setdefault(t['project'],'pending')

class Gateway(http.server.BaseHTTPRequestHandler):
    protocol_version='HTTP/1.1'
    def log_message(self,*a):pass
    def do_POST(self):
        token=self.path.split('/')[1] if '/' in self.path else ''
        with LOCK:
            job=next((j for j in S['jobs'].values() if j.get('token')==token and j['phase']=='gen_req'),None)
        if not job or not self.path.endswith('/responses'):
            self.send_error(403);return
        if job.get('state')!='running':
            self.send_error(403);return
        deadline=time.time()+290
        while True:
            with LOCK:
                blocked=S.get('block');delay=S.get('cooldown_until',0)-time.time()
            if blocked:
                self.send_error(403,'Provider authentication or quota blocked; queue saved');return
            if delay<=0:break
            if time.time()>=deadline:
                self.send_response(429);self.send_header('Retry-After',str(max(1,int(delay))))
                self.send_header('Connection','close');self.send_header('Content-Length','0');self.end_headers();return
            time.sleep(min(1,delay))
        body=self.rfile.read(int(self.headers.get('Content-Length',0)))
        try:
            request=json.loads(body)
            if request.get('model')!='gpt-6-luna' or request.get('reasoning',{}).get('effort')!='medium':
                self.send_error(400,'Frozen model/reasoning mismatch');return
            request['store']=False;request['stream']=True
            sample=Path(job['path'])/'first-provider-request.json'
            if not sample.exists():atomic(sample,request)
            auth=json.loads(Path('/root/.codex/auth.json').read_text())['tokens']
            hdr={'Authorization':'Bearer '+auth['access_token'],'Content-Type':'application/json',
                 'Accept':'text/event-stream','ChatGPT-Account-Id':auth['account_id'],
                 'Originator':'codex_cli_rs','User-Agent':'codex_cli_rs/0.160.0'}
            req=urllib.request.Request('https://chatgpt.com/backend-api/codex/responses',
                    data=json.dumps(request).encode(),headers=hdr,method='POST')
            with LOCK: job['api_requests']=job.get('api_requests',0)+1
            try: response=urllib.request.urlopen(req,timeout=300)
            except urllib.error.HTTPError as exc:response=exc
            code=response.status
            self.send_response(code);self.send_header('Content-Type',response.headers.get('Content-Type','text/event-stream'))
            self.send_header('Connection','close')
            if response.headers.get('Retry-After'):self.send_header('Retry-After',response.headers['Retry-After'])
            self.end_headers()
            if code>=400:
                data=response.read(); self.wfile.write(data)
                msg=data.decode(errors='replace')
                with LOCK:
                    job.setdefault('api_errors',[]).append({'status':code,'message':msg[:500]})
                    if code in (401,403) or re.search('usage_limit_reached|insufficient_quota|quota_exceeded',msg,re.I):
                        S['block']={'kind':'authentication_or_quota','status':code,'time':time.time(),'job':job['id']}
                        event('provider_block',status=code,job=job['id'])
                    elif code==429:
                        try: delay=float(response.headers.get('Retry-After','60'))
                        except ValueError:
                            try:
                                from email.utils import parsedate_to_datetime
                                delay=max(1,parsedate_to_datetime(response.headers['Retry-After']).timestamp()-time.time())
                            except Exception:delay=60
                        S['events_429']+=1;S['cooldown_until']=max(S['cooldown_until'],time.time()+max(1,delay))
                        S['generation_cap']=max(2,S['generation_cap']//2);event('rate_limit',retry_after=delay)
                return
            pending=b''
            while True:
                chunk=response.read1(65536)
                if not chunk:break
                self.wfile.write(chunk);self.wfile.flush();pending+=chunk
                lines=pending.split(b'\n');pending=lines.pop()
                for line in lines:
                    if line.startswith(b'data: '):
                        try:
                            ev=json.loads(line[6:]);usage=ev.get('response',{}).get('usage')
                            if usage:
                                with LOCK:
                                    job.setdefault('usage',[]).append(usage)
                        except (ValueError,TypeError):pass
        except (BrokenPipeError,ConnectionResetError):pass
        except BaseException as exc:
            event('gateway_network_error',job=job['id'] if job else None,error=type(exc).__name__)
            with LOCK:
                S['request_retries']+=1
                S.setdefault('network_error_times',[]).append(time.time())
            try:self.send_error(502,'Upstream connection interrupted')
            except OSError:pass
        finally:self.close_connection=True

class GatewayServer(http.server.ThreadingHTTPServer):
    request_queue_size=128
    daemon_threads=True

def req_env():
    return dict(HOME=str(RH),REQ2TEST_HOME=str(RH/'benchmark'),XDG_RUNTIME_DIR='/run/user/1001',
        DBUS_SESSION_BUS_ADDRESS='unix:path=/run/user/1001/bus',
        PATH='/root/lby-docker/req2test/tools:/root/lby-docker/req2test/agent/bin:'+str(RH/'venv/bin')+':/usr/bin:/usr/sbin:/bin:/sbin',
        HTTP_PROXY='http://127.0.0.1:7890',HTTPS_PROXY='http://127.0.0.1:7890',
        DOCKER_HOST='unix:///run/user/1001/req2test-docker-10156f49/docker.sock')
def user_cmd(argv,extra=None):
    pid=subprocess.check_output(['systemctl','show','user@1001.service','-p','MainPID','--value'],text=True).strip()
    env=req_env();env.update(extra or {})
    return ['nsenter','-t',pid,'-m','--','runuser','-u','r2tbench','--','env']+[k+'='+v for k,v in env.items()]+argv
def tsb_env():
    return dict(PATH=str(ROOT/'bin')+':/root/Baxxhy/work2/reproductions/testsuitebench/bin:/root/Baxxhy/work2/.runtime/uv/bin:/usr/bin:/usr/sbin:/bin:/sbin',
        DOCKER_HOST='unix:///run/mutate-docker.sock',HF_HOME='/root/Baxxhy/work2/datasets/testsuitebench/huggingface',
        PROGRAMBENCH_DOCKER_EXECUTABLE=str(ROOT/'bin/docker'),PROGRAMBENCH_CODEX_AUTH='login')
def launch(phase,key,argv,cwd,env=None,cost=0,token=None):
    uid=uuid.uuid4().hex;d=ROOT/'jobs'/uid;d.mkdir()
    spec=dict(argv=argv,cwd=str(cwd),env=env or {})
    atomic(d/'spec.json',spec)
    log=(d/'job.log').open('ab')
    p=subprocess.Popen(['/usr/bin/python3',str(ROOT/'control/job.py'),str(d/'spec.json')],
            stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    log.close()
    job=dict(id=uid,phase=phase,key=key,pid=p.pid,path=str(d),state='running',start=time.time(),cost=cost)
    if token:job['token']=token
    S['jobs'][uid]=job
    atomic(d/'job.json',job)
    atomic(STATE,S)
    event('job_started',id=uid,phase=phase,key=key,pid=p.pid,argv=argv)
    return job
def running(phase=None):
    return [j for j in S['jobs'].values() if j['state']=='running' and (phase is None or j['phase']==phase)]
def gen_count():return sum(j['phase'].startswith('gen_') for j in running())
def eval_cost():return sum(j['cost'] for j in running() if j['phase'].startswith('eval_'))
def req_path(t):return RROOT/'generation'/t['safe']
def pred_path(t):return Path(t.get('prediction',str(req_path(t)/'attempt-1/predictions.jsonl')))
def failure_prediction(t,path):
    atomicrow={'instance_id':t['id'],'model_name_or_path':'codex-gpt-6-luna-medium','view':'th','files':[],'status':'no_output'}
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(atomicrow)+'\n');os.chown(path,1001,1001)
def merge_req():
    seen=set();out=[]
    for t in S['tasks'].values():
        if t['benchmark']!='req2test':continue
        p=pred_path(t)
        rows=[json.loads(x) for x in p.read_text().splitlines() if x.strip()] if p.exists() else []
        if not rows:
            rows=[dict(instance_id=t['id'],model_name_or_path='codex-gpt-6-luna-medium',view='th',files=[],status='no_output')]
        if len(rows)!=1 or rows[0]['instance_id']!=t['id'] or t['id'] in seen:raise RuntimeError('Prediction uniqueness violation')
        seen.add(t['id']);out.append(rows[0])
    p=RROOT/'predictions.jsonl';tmp=p.with_suffix('.tmp');tmp.write_text(''.join(json.dumps(x)+'\n' for x in out));tmp.replace(p);os.chown(p,1001,1001)
    S['full_req_merged']=True;event('req_predictions_merged',count=len(out))

def merge_project_output(project,run_id):
    canonical=RH/'benchmark/runs'/CFG['req_run_id']
    source=RH/'benchmark/runs'/run_id/project
    target=canonical/project
    canonical.mkdir(parents=True,exist_ok=True);os.chown(canonical,1001,1001)
    if run_id!=CFG['req_run_id'] and not target.exists():
        # Same filesystem: atomic rename avoids copying large evaluation evidence.
        # Preserve the original per-project run as a symlink to the canonical tree.
        source.rename(target)
        source.symlink_to(target,target_is_directory=True)
        event('official_project_merged',project=project,source=str(source),target=str(target))

def parallel_eval_allocation(project,r):
    active=running('eval_req_project')
    if len(active)>=S.get('project_parallelism',2):return None
    per={'python-docx':2,'algorand-sdk':4,'kapua':6,'e-petitions':6,
         'coreshop':6,'sylius':6,'prestashop':6,'coddy-agent':18}[project]
    base=2 if project in ('coreshop','sylius','prestashop') else 0
    # Available memory already reflects running pools. Reserve only their
    # unmaterialized startup allocation, plus headroom for running generators.
    reserved=sum(max(0,j.get('memory_reservation_gib',0)-j.get('observed_memory_gib',0)) for j in active)
    headroom=16+min(16,gen_count()/2)
    mem=r['available_gib']-reserved-headroom
    cpu=S['evaluation_cpu_budget']-eval_cost()
    desired=CFG.get('coddy_eval_workers',2) if project=='coddy-agent' else min(CFG.get('eval_worker_max',4),max(1,S['evaluation_cpu_budget']//8))
    workers=min(desired,max(0,int((mem-base)//per)),cpu//4)
    if workers<1 or r['load']>80:return None
    return workers,workers*4,base+workers*per

def job_done(j,result):
    rc=result['returncode'];phase=j['phase'];key=j['key'];log=text(Path(j['path'])/'job.log')
    j.update(state='finished',returncode=rc,end=time.time())
    event('job_finished',id=j['id'],phase=phase,key=key,returncode=rc,seconds=j['end']-j['start'])
    t=S['tasks'].get(key)
    if phase=='build':
        tries=sum(x['phase']=='build' and x['key']==key for x in S['jobs'].values())
        S['builds'][key]='done' if rc==0 else ('pending' if tries<2 else 'blocked')
        if rc!=0 and re.search(r'SSLEOFError|UNEXPECTED_EOF|Bad Gateway|registry-1\.docker\.io.{0,300}EOF|auth\.docker\.io.{0,300}EOF|connection (?:reset|refused)|TLS handshake timeout',log,re.I):
            now=time.time()
            S['build_network_failures']=S.get('build_network_failures',0)+1
            S['build_cap']=2;S['build_cooldown_until']=now+1800
            S.setdefault('build_not_before',{})[key]=now+120
            event('build_network_backoff',key=key,attempt=tries,cap=2,retry_after=120,cooldown_until=now+1800)
        if rc!=0 and tries>=2:t.update(gen='infra_blocked',evaluation='infra_blocked',reason='image_build_failed')
        return
    if phase=='gen_req':
        outcome=inspect_req_generation(pred_path(t), j['path'], t['id'])
        if not outcome['turn_completed'] and any(e.get('status') in (401,403) or re.search('usage_limit_reached|insufficient_quota|quota_exceeded',e.get('message',''),re.I) for e in j.get('api_errors',[])):
            outcome.update(kind='infrastructure',reason='provider_authentication_or_quota')
        j['generation_outcome']=outcome
        atomic(Path(j['path'])/'generation-outcome.json',outcome)
        t['generation_result']=j['path']
        if outcome['kind']=='infrastructure':
            if t['gen_attempts']<2 and not S['block']:
                t.update(gen='pending',evaluation='pending',not_before=time.time()+60,reason=outcome['reason'])
                S['request_retries']+=1
                event('bounded_infrastructure_retry',key=key,attempt=t['gen_attempts'],reason=outcome['reason'])
            else:
                t.update(gen='infra_blocked',evaluation='infra_blocked',reason=outcome['reason'])
        else:
            t['gen']='finished' if outcome['kind']=='result' else 'failed'
            t['evaluation']='pending'
            t['reason']=outcome['reason']
            if not outcome['prediction_valid']:failure_prediction(t,pred_path(t))
            S['generation_completions'].append(time.time())
        return
    if phase.startswith('gen_'):
        complete=(ROOT/'tsb-generation'/t['id']/'tests.tar.gz').exists() if phase=='gen_tsb' else pred_path(t).exists()
        infra=not complete and re.search(r'code.mode.host.{0,80}missing|bwrap:|unrecognized (?:argument|option)|unexpected argument|could not reach the provider|connection refused|failed to (?:connect|start)|network is unreachable|EAI_AGAIN|invalid_grant',log,re.I)
        if phase=='gen_req' and not complete and re.search(r'after 0 LLM call\(s\)',log):infra=True
        if not complete and any(e['status'] in (400,404,405,502,503) for e in j.get('api_errors',[])):infra=True
        auth=re.search(r'usage_limit_reached|insufficient_quota|quota_exceeded|authentication token.{0,50}expired|401 Unauthorized',log,re.I)
        auth=auth or any(e.get('status') in (401,403) or re.search(r'usage_limit_reached|insufficient_quota|quota_exceeded',e.get('message',''),re.I) for e in j.get('api_errors',[]))
        if auth:S['block']={'kind':'authentication_or_quota','job':j['id'],'time':time.time()}
        if complete:
            t['gen']='finished';t['generation_result']=j['path'];S['generation_completions'].append(time.time())
        elif infra and t['gen_attempts']<2 and not auth:
            t['gen']='pending';t['not_before']=time.time()+60;S['request_retries']+=1
        elif infra or auth:
            t.update(gen='infra_blocked',evaluation='infra_blocked',reason='generation_infrastructure_failure')
        else:
            t.update(gen='failed',reason='official_budget_or_generation_failure',generation_result=j['path'])
            S['generation_completions'].append(time.time())
        if phase=='gen_req' and t['gen'] in ('finished','failed'):
            if not complete:failure_prediction(t,pred_path(t))
            if key==S['req_gate_id']:S['gate']='needs_evaluation'
        if phase=='gen_tsb' and t['gen']=='failed':t['evaluation']='not_applicable_no_suite'
        # Real usage from the official trajectory, not estimated prices.
        if phase=='gen_tsb':
            traj=ROOT/'tsb-generation'/t['id']/(t['id']+'.traj.json')
            if traj.exists():
                shutil.copy2(traj,Path(j['path'])/'official-trajectory.json')
                try:
                    d=json.loads(traj.read_text());t['usage']=d.get('usage',d.get('info',{}).get('usage',{}))
                except ValueError:pass
        return
    if phase=='eval_tsb':
        report=ROOT/'tsb-generation'/t['id']/(t['id']+'.test_eval.json')
        errors=[int(x) for x in re.findall(r'binary_errors=(\d+)',log)]
        if rc==0 and report.exists() and not any(errors):t.update(evaluation='finished',official_report=str(report))
        elif t['eval_attempts']<3:
            t['evaluation']='pending';t['eval_not_before']=time.time()+60
        else:t.update(evaluation='infra_blocked',reason='official_evaluation_failed')
        return
    if phase=='eval_req_diagnostic':
        tries=sum(x['phase']==phase and x['key']==key for x in S['jobs'].values())
        S['diagnostic_projects'][key]='finished' if rc==0 else ('pending' if tries<2 else 'infra_blocked')
        event('diagnostic_evaluation_terminal',project=key,state=S['diagnostic_projects'][key],baseline_scores_unchanged=True)
        return
    if phase=='eval_req_gate':
        root=RH/'benchmark/runs'/(CFG['req_gate_run_id']+'-'+S['tasks'][key]['safe']+'-a'+str(S['tasks'][key]['gen_attempts']))
        if rc==0 and (root/'summary.json').exists():
            S['gate']='passed';S['stage_since']=time.time();S['last_adapt']=time.time()
            S['stage_done']=len(S['generation_completions']);S['best_rate']=0
            event('req_gate_passed',score_independent=True)
        else:
            S['gate']='blocked';t=S['tasks'][S['req_gate_id']]
            t.update(gen='infra_blocked',evaluation='infra_blocked',reason='first_official_evaluation_infrastructure')
        return
    if phase=='eval_req_project' and j.get('requires_cached_rescore'):
        S['projects'][key]='pending'
        event('original_evidence_rescore_needed',project=key,diagnostic_execution=str(j['path']))
        return
    if phase=='eval_req_project':
        project=key;tries=sum(x['phase']==phase and x['key']==key for x in S['jobs'].values())
        run_id=j.get('official_run_id',CFG['req_run_id'])
        report=RH/'benchmark/runs'/run_id/'summary.json'
        infrastructure=[]
        if report.exists():
            try:
                disclosure=json.loads(report.read_text()).get('disclosures',{}).get(project+'/th',{})
                infrastructure=disclosure.get('infrastructure_excluded',[])+disclosure.get('baseline_infrastructure',[])
            except (ValueError,TypeError):pass
        if rc==0 and not infrastructure:
            merge_project_output(project,run_id)
            S['projects'][project]='infra_blocked' if any(t['project']==project and t['gen']=='infra_blocked' for t in S['tasks'].values()) else 'finished'
            for task in S['tasks'].values():
                if task['benchmark']=='req2test' and task['project']==project and task['id'] in j.get('eval_ids',[]):task['evaluation']='finished'
        elif tries<3:S['projects'][project]='pending'
        else:
            S['projects'][project]='infra_blocked'
            for task in S['tasks'].values():
                if task['benchmark']=='req2test' and task['project']==project:task['evaluation']='infra_blocked'
        return
    if phase=='final_req_report':
        S['final_report_done']=rc==0
        if rc!=0 and sum(x['phase']==phase for x in S['jobs'].values())>=3:S['final_report_blocked']=True

def poll():
    for j in list(running()):
        p=Path(j['path'])/'exit.json'
        if p.exists():job_done(j,json.loads(p.read_text()))
        elif not alive(j['pid']):job_done(j,dict(returncode=255))
        elif j['phase']=='gen_req':
            t=S['tasks'][j['key']]
            trace=pred_path(t).parent/'workspaces/0000.log'
            if not trace.exists():continue
            events=[]
            for line in trace.read_text(errors='replace').splitlines():
                try:events.append(json.loads(line))
                except ValueError:pass
            progress=sum(x.get('type')=='item.completed' for x in events)
            errors=[x for x in events if x.get('type')=='error' and re.search('Reconnecting|Connection failed|error sending request',str(x),re.I)]
            if progress!=j.get('watchdog_progress'):
                j['watchdog_progress']=progress;j['last_agent_progress']=time.time();j.pop('network_stall_since',None)
            if len(errors)>=3 and not any(x.get('type')=='turn.completed' for x in events):
                j.setdefault('network_stall_since',time.time())
                if time.time()-j['network_stall_since']>=120 and not j.get('network_abort_sent'):
                    atomic(Path(j['path'])/'infrastructure-abort.json',dict(reason='continuous_network_errors_without_agent_progress',error_events=len(errors),stall_seconds=120))
                    j['network_abort_sent']=True
                    event('bounded_network_abort',job=j['id'],key=j['key'])
                    try:os.killpg(j['pid'],signal.SIGTERM)
                    except ProcessLookupError:pass


def schedule(r):
    if not S.get('evaluation_seeded'):
        seed_evaluations(ROOT,CFG,S)
        S['evaluation_seeded']=True
        atomic(STATE,S)
    gen_ok=not S['block'] and time.time()>=S['cooldown_until'] and r['available_gib']>=24 and r['disk_free_gib']>=180 and r['load']<100
    if gen_ok:
        # Earlier completed projects enter evaluation while later projects generate.
        # Isolated per-ID views, output files and runtime state are the official ones.
        for k,t in sorted(S['tasks'].items(),key=lambda kv:kv[1]['n']):
            if gen_count()>=S['generation_cap']:break
            if t['gen']!='pending' or time.time()<t.get('not_before',0):continue
            t['gen_attempts']+=1;t['gen']='running'
            out=req_path(t)/('attempt-'+str(t['gen_attempts']));out.mkdir(parents=True,exist_ok=True)
            os.chown(out,1001,1001);os.chown(out.parent,1001,1001)
            t['prediction']=str(out/'predictions.jsonl')
            token=uuid.uuid4().hex
            argv=[str(RH/'venv/bin/python'),'/root/lby-docker/req2test/agent/req_agent.py',
                '--agent','codex','--model','baseline/gpt-6-luna','--tasks',str(RROOT/'manifests/items'/(t['safe']+'.jsonl')),
                '-o',str(out),'--model-name','codex-gpt-6-luna-medium','--workers','1','--timeout',str(CFG['req_generation_timeout'])]
            cmd=user_cmd(argv,dict(BASELINE_GATEWAY_URL=f'http://127.0.0.1:{CFG["gateway_port"]}/{token}',BASELINE_GATEWAY_KEY='local-transport-not-a-provider-secret'))
            launch('gen_req',k,cmd,RR,token=token)
    if r['available_gib']<24 or r['load']>80:return
    for project in ['python-docx','algorand-sdk','e-petitions','kapua','coreshop','prestashop','sylius','coddy-agent']:
        if S['projects'][project]!='pending':continue
        tt=[t for t in S['tasks'].values() if t['project']==project]
        if not all(t['gen'] in ('finished','failed','infra_blocked') for t in tt):continue
        allocation=parallel_eval_allocation(project,r)
        if allocation is None:continue
        prepared=prepare_project_predictions(project)
        if prepared is None:
            S['projects'][project]='infra_blocked';continue
        predictions,ids,is_full=prepared
        workers,cost,memory=allocation
        run_id=S['project_run_ids'][project]
        argv=[str(RH/'venv/bin/python'),CFG['diagnostic_eval_wrapper'],'evaluate','--predictions',str(predictions),
              '--split','eval','--project',project,'--workers',str(workers),'--run-id',run_id]
        if not is_full:argv+=['--instances',str(ids)]
        job=launch('eval_req_project',project,user_cmd(argv,dict(R2T_RECOVERY_DIAGNOSTICS=str(RROOT/'evaluation-diagnostics'))),RR,cost=cost)
        job.update(official_run_id=run_id,memory_reservation_gib=memory,workers=workers,eval_ids=[t['id'] for t in tt if t['gen'] in ('finished','failed')])
        S['projects'][project]='running'
        for t in tt:
            if t['id'] in job['eval_ids'] and t['evaluation']!='finished':t['evaluation']='running'
        event('parallel_evaluation_started',project=project,workers=workers,cpu_budget=cost,memory_reservation_gib=memory,run_id=run_id,full_project=is_full)
    if all(t['gen'] in ('finished','failed','infra_blocked') for t in S['tasks'].values()) and not S['full_req_merged']:
        # Missing infrastructure results remain missing in the canonical file.
        rows=[]
        for t in S['tasks'].values():
            if t['gen'] in ('finished','failed'):rows.extend(json.loads(x) for x in pred_path(t).read_text().splitlines() if x.strip())
        assert len(rows)==len({x['instance_id'] for x in rows})
        p=RROOT/'predictions.jsonl';p.write_text(''.join(json.dumps(row)+'\n' for row in rows));os.chown(p,1001,1001)
        S['full_req_merged']=True
        event('req_predictions_merged',count=len(rows),infrastructure_missing=len(S['tasks'])-len(rows))
    if all(x in ('finished','infra_blocked') for x in S['projects'].values()) and not S['final_report_done'] and not S.get('final_report_blocked') and not running('final_req_report'):
        argv=[str(RH/'venv/bin/req2test'),'report','--run-id',CFG['req_run_id']]
        launch('final_req_report','report',user_cmd(argv),RR)

def recover_quota_if_ready():
    block=S.get('block')
    if not block or block.get('kind')!='authentication_or_quota':return
    job=S['jobs'].get(block.get('job'),{})
    resets=[]
    for err in job.get('api_errors',[]):
        try:
            detail=json.loads(err.get('message','')).get('error',{})
            if detail.get('type')=='usage_limit_reached' and detail.get('resets_at'):
                resets.append(int(detail['resets_at']))
        except (ValueError,TypeError):pass
    if not resets:return
    reset=max(resets);due=reset+60
    S['quota_resume_at']=due
    checks=S.setdefault('quota_window_checks',[])
    if time.time()<due or any(x['reset_at']==reset for x in checks):return
    check=dict(reset_at=reset,checked_at=time.time(),status='checking')
    checks.append(check);atomic(STATE,S)  # At most one usage check per returned window, including restarts.
    try:
        auth=json.loads(Path('/root/.codex/auth.json').read_text())['tokens']
        req=urllib.request.Request('https://chatgpt.com/backend-api/wham/usage',headers={
            'Authorization':'Bearer '+auth['access_token'],'ChatGPT-Account-Id':auth['account_id'],
            'User-Agent':'codex_cli_rs/0.160.0'})
        with urllib.request.urlopen(req,timeout=20) as response:
            rate=json.loads(response.read(100000)).get('rate_limit',{})
        check.update(status='available' if rate.get('allowed') is True and rate.get('limit_reached') is False else 'still_blocked',
                     primary_used_percent=rate.get('primary_window',{}).get('used_percent'),
                     secondary_used_percent=rate.get('secondary_window',{}).get('used_percent'))
        if check['status']!='available':
            event('quota_window_still_blocked',check=check);return
        restored=[]
        for key,t in S['tasks'].items():
            if t['benchmark']!='req2test' or t['gen']!='infra_blocked' or t['gen_attempts']>=2:continue
            attempts=[j for j in S['jobs'].values() if j['phase']=='gen_req' and j['key']==key]
            last=max(attempts,key=lambda j:j['start']) if attempts else {}
            if not any('usage_limit_reached' in e.get('message','') for e in last.get('api_errors',[])):continue
            last['failure_classification']='provider_quota_interruption'
            t.update(gen='pending',evaluation='pending');t.pop('reason',None);restored.append(key)
        S['block']=None;S['generation_cap']=8;S['cooldown_until']=time.time()
        S['stage_since']=time.time();S['last_adapt']=time.time()
        S['stage_done']=len(S['generation_completions']);S['best_rate']=0
        S['request_retries']+=len(restored);S['quota_resume_at']=None
        event('quota_window_resumed',check=check,restored_tasks=restored,generation_cap=8)
    except Exception as exc:
        check.update(status='check_failed',error=type(exc).__name__)
        event('quota_window_check_failed',check=check)

def adapt(r):
    now=time.time();done=len(S['generation_completions'])
    network_recent=sum(x>now-60 for x in S.get('network_error_times',[]))
    pressure=r['available_gib']<24 or r['load']>90 or r.get('memory_pressure_full',0)>2
    if (pressure or network_recent>=3) and now-S.get('last_network_down',0)>=60:
        old=S['generation_cap'];S['generation_cap']=max(1,old//2)
        S['cooldown_until']=max(S['cooldown_until'],now+60);S['last_network_down']=now;S['last_adapt']=now
        S['stage_since']=now;S['stage_done']=done
        event('concurrency_down',old=old,new=S['generation_cap'],network_recent=network_recent,resources=r)
        return
    if now-S['last_adapt']<180:return
    elapsed=now-S['stage_since'];n=done-S['stage_done'];rate=n/max(elapsed,1)
    old=S['generation_cap'];last_rate=S.get('best_rate',0)
    if n>=4 and last_rate and rate<last_rate*.70 and gen_count()>=old*.75:
        S['generation_cap']=max(1,old//2)
        event('throughput_concurrency_down',old=old,new=S['generation_cap'],rate=rate)
    elif old<32 and n>=4 and r['available_gib']>36 and r['load']<64 and network_recent==0 and now>S['cooldown_until']+120 and not S['block']:
        if old<16 or not last_rate or rate>last_rate*1.10:
            S['generation_cap']=min(32,16 if old<16 else 32)
            event('concurrency_up',old=old,new=S['generation_cap'],throughput=rate,resources=r)
    if S['generation_cap']!=old:
        S['stage_since']=now;S['stage_done']=done;S['best_rate']=rate
    eval_finished=sum(j['phase']=='eval_req_project' and j.get('returncode')==0 for j in S['jobs'].values())
    desired=8
    if eval_finished>=1 and r['available_gib']>36 and r['load']<64:desired=16
    if eval_finished>=2 and r['available_gib']>48 and r['load']<64:desired=32
    if r['available_gib']<24:desired=4
    if S['evaluation_cpu_budget']!=desired:event('evaluation_budget_changed',old=S['evaluation_cpu_budget'],new=desired)
    S['evaluation_cpu_budget']=desired;S['project_parallelism']=2
    S['last_adapt']=now


def report(r):
    evaluation_projects={}
    for j in running('eval_req_project'):
        run_id=j.get('official_run_id',CFG['req_run_id'])
        folder=RH/'benchmark/runs'/run_id/j['key']/'th'
        info=dict(workers=j.get('workers',j['cost']//4),cpu_budget=j['cost'],official_run_id=run_id,
                  memory_reservation_gib=j.get('memory_reservation_gib',48 if j['key']=='coddy-agent' else j['cost']))
        plan=folder/'mutation.plan.json'
        if plan.exists():
            try:info['mutation_pairs_total']=json.loads(plan.read_text()).get('pairs')
            except (ValueError,OSError):pass
        checkpoints=list((folder/'mutation').glob('w*.jsonl'))
        if checkpoints:
            pairs=set()
            for checkpoint in checkpoints:
                for line in checkpoint.read_text().splitlines():
                    try:
                        row=json.loads(line);pairs.add((row['instance_id'],row['mutant_id']))
                    except (ValueError,KeyError):pass
            info['mutation_pairs_done']=len(pairs)
            info['checkpoint_age_seconds']=round(time.time()-max(p.stat().st_mtime for p in checkpoints),1)
        evaluation_projects[j['key']]=info
    counts={}
    for b in ('tsb','req2test'):
        tt=[t for t in S['tasks'].values() if t['benchmark']==b]
        counts[b]=dict(total=len(tt),generation=dict(collections.Counter(t['gen'] for t in tt)),evaluation=dict(collections.Counter(t['evaluation'] for t in tt)))
    usage=collections.Counter()
    for j in S['jobs'].values():
        for u in j.get('usage',[]):
            for k in ('input_tokens','output_tokens','total_tokens'):usage[k]+=u.get(k,0)
            usage['cached_input_tokens']+=u.get('input_tokens_details',{}).get('cached_tokens',0)
            usage['reasoning_output_tokens']+=u.get('output_tokens_details',{}).get('reasoning_tokens',0)
    total_usage=usage.copy()
    total_usage.update(S.get('prior_known_token_usage',{}))
    for t in S['tasks'].values():
        if t['benchmark']=='tsb':
            for k,v in t.get('usage',{}).items():
                if isinstance(v,(int,float)):total_usage[k]+=v
    progress=dict(updated=time.time(),run_id=CFG['run_id'],tasks=counts,active_generation=gen_count(),generation_cap=S['generation_cap'],reused_generations=S.get('reused_generations',0),reused_official_evaluations=S.get('reused_official_evaluations',0),
        active_evaluation_cpu_budget=eval_cost(),evaluation_cpu_budget=S['evaluation_cpu_budget'],image_build_cap=S.get('build_cap',2),
        req_gate=S['gate'],block=S['block'],rate_limits=S['events_429'],network_retries=S['request_retries'],
        build_network_failures=S.get('build_network_failures',0),build_cooldown_until=S.get('build_cooldown_until',0),
        quota_resume_at=S.get('quota_resume_at'),quota_window_checks=S.get('quota_window_checks',[]),
        evaluation_projects=evaluation_projects,project_parallelism=S.get('project_parallelism',1),
        resources=r,diagnostic_projects=S['diagnostic_projects'],known_gateway_usage=dict(usage),known_total_token_usage=dict(total_usage),real_cost=None,projects=S['projects'],active_benchmark=S.get('active_benchmark','tsb'))
    atomic(ROOT/'progress.json',progress);atomic(STATE,S)
    db.execute('INSERT OR REPLACE INTO state VALUES(1,?,?)',(time.time(),json.dumps(S)));db.commit()
    with (ROOT/'resources.jsonl').open('a') as f:f.write(json.dumps(dict(**r,generation=gen_count(),generation_cap=S['generation_cap'],evaluation_cpu=eval_cost()))+'\n')

def finalize():
    if not all(t['gen'] in ('finished','failed','infra_blocked') and t['evaluation'] in ('finished','infra_blocked') for t in S['tasks'].values()):return False
    if not S['final_report_done'] and not S.get('final_report_blocked'):return False
    audit=[dict(key=k,**t) for k,t in S['tasks'].items()]
    atomic(ROOT/'final-task-audit.json',audit)
    atomic(ROOT/'failures-and-unfinished.json',[t for t in audit if t['gen']!='finished' or t['evaluation']!='finished'])
    with (ROOT/'final-report.log').open('a') as log:
        rc=subprocess.run([str(RH/'venv/bin/python'),str(ROOT/'control/final_report.py'),str(ROOT)],cwd=RR,stdout=log,stderr=subprocess.STDOUT).returncode
    if rc!=0:
        S['final_audit_attempts']=S.get('final_audit_attempts',0)+1
        if S['final_audit_attempts']<3:return False
    complete=rc==0 and all(t['gen']!='infra_blocked' and t['evaluation']=='finished' for t in audit)
    atomic(ROOT/'completion.json',dict(all_ids_accounted_for=True,all_required_evaluations_complete=complete,total=len(audit),generated_and_evaluated=sum(t['evaluation']=='finished' for t in audit),time=time.time()))
    event('queues_terminal',all_ids_accounted_for=True,all_required_evaluations_complete=complete)
    return True


def prepare_project_predictions(project):
    tt=[t for t in S['tasks'].values() if t['project']==project]
    ready=[t for t in tt if t['gen'] in ('finished','failed')]
    if not ready:return None
    rows=[];seen=set()
    for t in ready:
        data=[json.loads(x) for x in pred_path(t).read_text().splitlines() if x.strip()]
        assert len(data)==1 and data[0]['instance_id']==t['id'] and t['id'] not in seen
        seen.add(t['id']);rows.append(data[0])
    out=RROOT/'evaluation-inputs';out.mkdir(exist_ok=True);os.chown(out,1001,1001)
    p=out/(project+'.jsonl');content=''.join(json.dumps(row)+'\n' for row in rows)
    if p.exists():assert p.read_text()==content,'Never change predictions after evaluation starts'
    else:p.write_text(content);os.chown(p,1001,1001)
    ids=out/(project+'.ids');ids.write_text('\n'.join(sorted(seen))+'\n');os.chown(ids,1001,1001)
    return p,ids,len(ready)==len(tt)

lock=(ROOT/'controller.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
db=sqlite3.connect(ROOT/'queue.sqlite');db.execute('PRAGMA journal_mode=WAL');db.execute('CREATE TABLE IF NOT EXISTS state(id INTEGER PRIMARY KEY,updated REAL,payload TEXT)')
server=GatewayServer(('127.0.0.1',CFG['gateway_port']),Gateway)
threading.Thread(target=server.serve_forever,daemon=True).start()
event('controller_started',pid=os.getpid(),config_sha256=hashlib.sha256((ROOT/'frozen/config.json').read_bytes()).hexdigest())
while True:
    try:
        with LOCK:
            poll();recover_quota_if_ready();r=resources();adapt(r);schedule(r);report(r)
            if finalize():break
    except BaseException as exc:
        event('controller_exception',error=repr(exc));print(repr(exc),flush=True)
    time.sleep(10)
