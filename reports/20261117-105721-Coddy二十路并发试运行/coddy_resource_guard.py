"""Observe the owned evaluation pool and preserve evidence on resource backoff."""
import json
import os
from pathlib import Path
import shutil
import signal
import re
import subprocess
import time


def pressure(path):
    try:
        line=next(x for x in Path(path).read_text().splitlines() if x.startswith('full '))
        return float(next(x.split('=')[1] for x in line.split() if x.startswith('avg10=')))
    except (OSError,StopIteration,ValueError):
        return 0.0


def policy(available,load,memory_full,io_full):
    if available<16:
        return 30
    if memory_full>10 and available<32:
        return 60
    if load>160:
        return 120
    if io_full>60:
        return 180
    return None


def descendants(pid):
    try:
        children=(Path('/proc')/str(pid)/'task'/str(pid)/'children').read_text().split()
    except OSError:
        return []
    result=[]
    for child in children:
        child=int(child)
        result.append(child)
        result.extend(descendants(child))
    return result


def guard(state,cfg,root,resources,event):
    jobs=[j for j in state['jobs'].values() if j['state']=='running' and j['phase']=='eval_req_project' and j['key']=='coddy-agent']
    for job in jobs:
        if job.get('workers',0)<4 or job.get('resource_pressure_abort'):
            continue
        source=Path(cfg['req_home'])/'benchmark/runs'/job['official_run_id']/'coddy-agent/th/mutation'
        if 'resource_checkpoint' not in job:
            target=Path(job['path'])/'resource-start-checkpoint'
            target.mkdir(exist_ok=True)
            for f in source.glob('*.jsonl'):
                shutil.copy2(f,target/f.name)
            job['resource_checkpoint']=str(target)
        memory_full=pressure('/proc/pressure/memory')
        io_full=pressure('/proc/pressure/io')
        observation=dict(time=time.time(),workers=job['workers'],available_gib=resources['available_gib'],load=resources['load'],memory_full=memory_full,io_full=io_full)
        with (root/'coddy-resource-watch.jsonl').open('a') as f:
            f.write(json.dumps(observation)+'\n')
        wait=policy(resources['available_gib'],resources['load'],memory_full,io_full)
        if wait is None:
            job.pop('resource_pressure_since',None)
            continue
        since=job.setdefault('resource_pressure_since',time.time())
        if time.time()-since<wait:
            continue
        for pid in descendants(job['pid']):
            try:
                args=(Path('/proc')/str(pid)/'cmdline').read_bytes()
            except OSError:
                continue
            if args.split(b'\0')[0].endswith(b'/python') and b'diagnostic_eval.py\x00evaluate' in args:
                job['resource_pressure_abort']=observation
                job['planned_concurrency_change']=True
                cfg['coddy_eval_workers']=max(3,job['workers']//2)
                (root/'frozen/config.json').write_text(json.dumps(cfg,indent=2))
                event('coddy_resource_backoff',job=job['id'],next_workers=cfg['coddy_eval_workers'],observation=observation)
                os.kill(pid,signal.SIGTERM)
                break


def restore(job,cfg,event):
    log=(Path(job['path'])/'job.log').read_text()
    match=re.search(r'environment (e[0-9a-f]+)',log)
    if match:
        pid=subprocess.check_output(['systemctl','show','user@1001.service','-p','MainPID','--value'],text=True).strip()
        command=['nsenter','-t',pid,'-m','--','runuser','-u','r2tbench','--','bash','-c',
                 'source '+cfg['req_home']+'/env.sh; exec req2test env down --project coddy-agent --nonce '+match[1]]
        try:
            result=subprocess.run(command,text=True,capture_output=True,timeout=180)
            event('resource_pool_retired',job=job['id'],nonce=match[1],returncode=result.returncode)
        except (OSError,subprocess.TimeoutExpired) as error:
            event('resource_pool_retirement_error',job=job['id'],nonce=match[1],error=repr(error))
    source=Path(cfg['req_home'])/'benchmark/runs'/job['official_run_id']/'coddy-agent/th'
    archive=Path(job['path'])/'resource-aborted-evidence'
    archive.mkdir(exist_ok=True)
    for name in ['mutation','mutation-raw']:
        if (source/name).exists():
            shutil.move(str(source/name),str(archive/name))
    marker=source/'mutation.done.json'
    if marker.exists():
        shutil.move(str(marker),str(archive/marker.name))
    (source/'mutation').mkdir()
    os.chown(source/'mutation',1001,1001)
    for f in Path(job['resource_checkpoint']).glob('*.jsonl'):
        target=source/'mutation'/f.name
        shutil.copy2(f,target)
        os.chown(target,1001,1001)
    event('resource_attempt_archived_checkpoint_restored',job=job['id'],archive=str(archive))
