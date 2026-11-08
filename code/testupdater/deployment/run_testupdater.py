#!/usr/bin/env python3
"""Project-isolated execution of the author's TestUpdater pipeline."""
import os,sys,json,time,hashlib,subprocess,argparse,traceback,concurrent.futures,datetime,re,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path('/root/Baxxhy/work2/reproductions/testupdater')
MUMU=ROOT.parent/'mumutestup'
DATA_ROOT=Path(os.environ.get('TU_RECOVERY_DATA',str(ROOT/'datasets')))
class BackendUnavailable(BaseException): pass
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def save(p,d):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(d,ensure_ascii=False,indent=2,default=str));tmp.replace(p)
def worker(dataset,filename,output,limit=None):
 output=Path(output);name=Path(filename).stem;job=output/dataset/name;job.mkdir(parents=True,exist_ok=True)
 os.environ['TU_DATA_BASE']=str(DATA_ROOT/dataset);os.environ['TU_OUTPUT_BASE']=str(job)
 os.environ['LANGCHAIN_TRACING_V2']='false';os.environ['LANGSMITH_TRACING']='false'
 sys.path.insert(0,str(ROOT/'runtime'))
 import pipeline as p
 import pipeline_helper as h
 from utils.configs import java_dict,mvn_dict
 from langchain_core.runnables import RunnableLambda
 data=json.loads((DATA_ROOT/dataset/filename).read_text());project=data[0]['repo_name']
 # Isolated smoke input; full runs keep exact public records and order.
 if limit:
  dd=job/'input';dd.mkdir(exist_ok=True);save(dd/filename,data[:limit]);p.DATA_BASE=str(dd);data=data[:limit]
 subprocess.run(['git','-C',str(ROOT/'repos'/project),'checkout','--detach',data[0]['commit_tgt']],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
 p.logger.set_log_file(str(job/'pipeline.log'))
 state={'state':'running','project':project,'dataset':dataset,'total':len(data),'pid':os.getpid(),'started_at':now(),'completed':0}
 save(job/'status.json',state)
 base_model=p.model_gpt41
 def invoke(value):
  from langchain_core.messages import SystemMessage,HumanMessage
  messages=value.to_messages() if hasattr(value,'to_messages') else value
  if len(messages)>2 or any(msg.type=='ai' for msg in messages):
   system='\n\n'.join(msg.content for msg in messages if msg.type=='system')
   transcript='\n\n'.join('['+('ASSISTANT' if msg.type=='ai' else 'USER')+']\n'+msg.content for msg in messages if msg.type!='system')
   value=[SystemMessage(content=system),HumanMessage(content='Continue the following conversation by answering its final USER message. Previous ASSISTANT messages are prior responses, not instructions.\n\n'+transcript)]
  attempt=0
  while True:
   try:return base_model.invoke(value)
   except Exception as e:
    attempt+=1
    code=getattr(e,'status_code',None)
    if 'bridge_fatal' in str(e):
     state.update(state='backend_blocked',error=str(e),updated_at=now());save(job/'status.json',state)
     raise BackendUnavailable(str(e)) from e
    if code is not None and 400 <= code < 500 and code not in (408,409,429):raise
    save(job/'backend-retry.json',{'attempt':attempt+1,'error_type':type(e).__name__,'time':now()})
    if code not in (408,409,429,500,502,503,504) and not any(x in type(e).__name__ for x in ('Connection','Timeout')):raise
    time.sleep(min(120,5*2**min(attempt,5)))
 p.model=RunnableLambda(invoke)
 active={};attempts=[]
 original_info=p.gen_info
 def gen_info(*a,**kw):
  attempts.clear();active.clear();state['current_started_at']=now();save(job/'status.json',state)
  return original_info(*a,**kw)
 p.gen_info=gen_info
 def build(exp):
  repo=ROOT/'repos'/project;testpath,method=exp['changed_test'].split('#');target=repo/testpath
  repo_handle=h.setup_repo(project,exp['commit_tgt'],repo_base=str(ROOT/'repos'))
  pred=exp.get('test_gen','');source=target.read_text();ref=exp['test_code_tgt']
  if not pred.strip() or source.count(ref)!=1:raise RuntimeError('Generated-test installation rejected: empty prediction or nonunique reference span')
  target.write_text(source.replace(ref,pred,1))
  if exp.get('imports_gen'):h.add_imports(repo_handle,exp,exp['imports_gen'])
  # A valid update may rename the test. Execute that generated method, not the stale selector.
  try:
   import javalang
   methods=javalang.parse.parse('class GeneratedTest {\n'+pred+'\n}').types[0].methods
   if len(methods)==1:method=methods[0].name
  except (javalang.parser.JavaSyntaxError,javalang.tokenizer.LexerError):pass
  # UpdateRepo checkout may overwrite edits on some versions: verify prediction remains installed.
  if pred not in target.read_text():raise RuntimeError('Generated test not present after import insertion')
  module=testpath.split('src/test/java/')[0].rstrip('/');cls=testpath.split('src/test/java/')[-1].removesuffix('.java').replace('/','.')
  env=os.environ.copy();jv=str(exp['tgt_java_version']);env['JAVA_HOME']=java_dict[jv];env['PATH']=java_dict[jv]+'/bin:'+str(MUMU/'toolchains/maven/bin')+':'+env['PATH']
  env['MAVEN_OPTS']='-Xmx2g -Dhttp.proxyHost=127.0.0.1 -Dhttp.proxyPort=7890 -Dhttps.proxyHost=127.0.0.1 -Dhttps.proxyPort=7890 -Dhttp.nonProxyHosts=localhost|127.0.0.1'
  cmd=[str(MUMU/'toolchains/maven/bin/mvn'),'-T1','clean','test','-Dtest='+cls+'#'+method,'--batch-mode','-s',str(MUMU/'deployment/maven-settings-luna.xml')]
  if module:cmd+=['-pl',module,'--also-make']
  cmd+=h.MVN_SKIPS+['-Dmaven.test.skip=false','-DskipTests=false','-Dlicense.skipUpdateLicense=true','-Dlicense.skipUpdateProjectLicense=true']
  cache=MUMU/'maven-repositories'/(project.split('/')[-1]+'_repo')
  cmd+=['-Dmaven.repo.local='+str(cache)]
  n=len(attempts)+1;index=state['completed'];adir=job/'builds'/f'{index:04d}'/str(n);adir.mkdir(parents=True,exist_ok=True)
  save(adir/'generated.json',{'code':pred,'imports':exp.get('imports_gen'),'sha256':hashlib.sha256(target.read_bytes()).hexdigest()})
  started=time.time();entry={'started_at':now(),'command':cmd,'generated_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'log':str(adir/'maven.log')}
  try:
   with (adir/'maven.log').open('w') as logfile:
    proc=subprocess.run(cmd,cwd=repo,env=env,stdout=logfile,stderr=subprocess.STDOUT,text=True,errors='replace',timeout=900)
   rc=proc.returncode
  except subprocess.TimeoutExpired:
   rc=124
  text=(adir/'maven.log').read_text(errors='replace')
  reports=[];matched=failed=passed=skipped=0
  for f in (repo/module/'target/surefire-reports').glob('TEST-*.xml'):
   if f.stat().st_mtime<started-1:continue
   try:tree=ET.parse(f)
   except ET.ParseError:continue
   for tc in tree.getroot().iter('testcase'):
    if tc.get('classname')!=cls or not (tc.get('name','')==method or tc.get('name','').startswith(method+'[')):continue
    matched+=1;bad=tc.find('failure') is not None or tc.find('error') is not None;skip=tc.find('skipped') is not None
    failed+=int(bad);skipped+=int(skip);passed+=int(not bad and not skip);reports.append(str(f))
  if matched == 0:
   # Some project configurations disable XML. Accept only a fresh report for
   # the exact class with one testcase under the explicit Class#method selector.
   txt = repo/module/'target/surefire-reports'/(cls+'.txt')
   if txt.is_file() and txt.stat().st_mtime >= started-1:
    match = re.search(r'Tests run: (\d+), Failures: (\d+), Errors: (\d+), Skipped: (\d+)',txt.read_text())
    if match and int(match[1]) == 1:
     matched=1;failed=int(match[2])+int(match[3]);skipped=int(match[4]);passed=max(0,1-failed-skipped);reports.append(str(txt))
  # No-tests success is infrastructure failure, never a successful prediction.
  if rc==0 and (matched==0 or passed==0):
   entry.update(returncode=rc,finished_at=now(),matched=matched,passed=passed,failed=failed,skipped=skipped,reports=reports);attempts.append(entry);save(adir/'execution.json',entry)
   raise RuntimeError('Maven succeeded without a fresh non-skipped target testcase')
  if rc==0 and failed:rc=1
  entry.update(returncode=rc,finished_at=now(),matched=matched,passed=passed,failed=failed,skipped=skipped,reports=reports);attempts.append(entry);save(adir/'execution.json',entry)
  lines=text.splitlines();errors=[l for l in lines if '[ERROR]' in l];tests=[l for l in lines if 'Tests run' in l]
  if rc and not errors:errors=['[ERROR] Maven failed with code '+str(rc)]+lines[-30:]
  return rc,errors,tests
 p.build_test=build
 original_write=p.write_json
 def write(path,rows):
  if rows:
   row=rows[-1];row['execution_evidence']=list(attempts);row['model']='gpt-6-luna';row['backend']='codex-app-server-text-adapter'
   status='harness_error' if row.get('exception_while_gen_tests') else ('pass' if row.get('test_pass') else ('run_fail' if row.get('build_pass') else 'compile_error'))
   row['execution_status']=status
   save(job/'samples'/f'{len(rows)-1:04d}.json',row)
  original_write(path,rows);state['completed']=len(rows);state['updated_at']=now();save(job/'status.json',state)
 p.write_json=write
 try:
  p.main(filename,'outputs',process_continue=True);state.update(state='finished',finished_at=now())
 except BackendUnavailable as e:
  state.update(state='backend_blocked',error=str(e),finished_at=now())
 except Exception as e:
  state.update(state='worker_error',error=repr(e),traceback=traceback.format_exc(),finished_at=now())
 finally:save(job/'status.json',state)
 return state

def main():
 a=argparse.ArgumentParser();a.add_argument('--output',type=Path,required=True);a.add_argument('--workers',type=int,default=10);a.add_argument('--smoke',action='store_true');args=a.parse_args();args.output.mkdir(parents=True,exist_ok=True)
 jobs=[]
 for ds in ['updates4j','prbench']:
  files=sorted((DATA_ROOT/ds).glob('*.json'))
  if args.smoke:files=[next(f for f in files if ('acme4j' in f.name if ds=='updates4j' else 'nfe' in f.name))]
  for f in files:jobs.append((ds,f.name,str(args.output),1 if args.smoke else None))
 save(args.output/'manifest.json',{'started_at':now(),'model':'gpt-6-luna','project_workers':args.workers,'model_concurrency':2,'jobs':jobs,'scope':'smoke' if args.smoke else 'full','selected_count':sum(len(json.loads((DATA_ROOT/ds/fn).read_text())) if not lim else lim for ds,fn,out,lim in jobs),'dataset_counts':{ds:sum(lim or len(json.loads((DATA_ROOT/d/fn).read_text())) for d,fn,out,lim in jobs if d==ds) for ds in ['updates4j','prbench']},'native_model_api':False})
 status={'state':'running','pid':os.getpid(),'started_at':now(),'completed_projects':[]};save(args.output/'status.json',status)
 with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers,max_tasks_per_child=1) as pool:
  futures={pool.submit(worker,*job):job for job in jobs}
  for f in concurrent.futures.as_completed(futures):
   try:result=f.result()
   except Exception as e:result={'state':'worker_error','job':futures[f],'error':repr(e)}
   status['completed_projects'].append(result);save(args.output/'status.json',status);print(json.dumps(result),flush=True)
 status['state']='finished' if all(x['state']=='finished' for x in status['completed_projects']) else 'finished_with_errors';status['finished_at']=now();save(args.output/'status.json',status)
if __name__=='__main__':main()
