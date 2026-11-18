from pathlib import Path
from collections import Counter, defaultdict
import json
import re

root = Path('/root/Baxxhy/work2/reproductions')
base = root / 'req2test'
current = base / 'req2test-eval2051-resume-20261117-v1'
runs = [root/'testsuitebench/full-baseline-20261111-v1', base/'req2test-recovery8-20261113-v1',
        base/'req2test-eval2051-20261115-v1', current]
official = Path('/root/lby-docker/req2test/user/benchmark/runs')/current.name
tasks = json.loads((current/'state.json').read_text())['tasks']
reuse = {str(Path(x['prediction'])):x for x in json.loads((current/'frozen/prior-generation-reuse.json').read_text())}
by_output = {}
by_job = {}
for run in runs:
    for job in json.loads((run/'state.json').read_text())['jobs'].values():
        if job['phase'] != 'gen_req':
            continue
        path = Path(job['path'])
        by_job[str(path)] = job
        spec = path/'spec.json'
        if spec.exists():
            argv = json.loads(spec.read_text())['argv']
            if '-o' in argv:
                by_output[str(Path(argv[argv.index('-o')+1])/'predictions.jsonl')] = job

execs = {row['item_id']:row for folder in official.glob('*/th')
         for row in map(json.loads,(folder/'exec.jsonl').open())}
diagnostics = Path('/root/lby-docker/req2test/user/runs')/current.name/'evaluation-diagnostics'
# Match diagnostics to the final official outcome, retaining older records only for corroboration.
error_patterns = {
 'host_resource': r"can't start new thread|resource temporarily unavailable|no space left on device|out of memory|failed to create new OS thread|too many open files",
 'docker_transport': r"cannot connect to the docker daemon|error during connect|context deadline exceeded.*docker|connection reset by peer|error response from daemon",
 'missing_dependency': r"could not resolve dependencies|could not transfer artifact|failed to download|network is unreachable|temporary failure in name resolution",
 'service_injection': r"cannot autowire|non.existent service|ServiceNotFoundException|has a dependency on|cannot be autowired|NotInstantiable",
 'compile_or_api': r"undefined (?:method|function|constant)|class.{0,100}not found|cannot find symbol|incompatible types|type mismatch",
}
signals = defaultdict(set)
for path in diagnostics.glob('*.json'):
    row = json.loads(path.read_text())
    iid = row.get('instance_id')
    if iid not in execs or row.get('outcome') != execs[iid]['outcome']:
        continue
    if row.get('outcome') not in {'container_error','parse_or_compile_error','solution_error','no_scenario_ran'}:
        continue
    for run in row.get('runs',[]):
        snippet = str(run.get('stdout') or run.get('stdout_tail') or '')
        signals[iid].update(k for k,p in error_patterns.items() if re.search(p,snippet,re.I))

result = []
for t in tasks.values():
    iid = t['id']
    pred = t['prediction']
    previous = reuse.get(pred)
    source = str(Path(previous['source_prediction'])) if previous else pred
    job = by_job.get(previous['source_job']) if previous else by_output.get(source)
    trace = Path(source).parent/'workspaces/0000.log'
    stop = None
    calls = None
    terminal = Counter()
    trace_status = []
    if job:
        log = Path(job['path'])/'job.log'
        log = log.read_text(errors='replace') if log.exists() else ''
        parsed = re.findall(r'\[\d+\] (exit \d+|timed out|stopped at the budget) after (\d+) LLM call\(s\)',log)
        if parsed:
            stop, call_count = parsed[-1]
            calls = int(call_count)
        if trace.exists():
            for line in trace.open(errors='replace'):
                if not any(x in line for x in ('turn.completed','turn.failed','"type":"error"','"type": "error"')):
                    continue
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                kind = event.get('type')
                if kind not in ('turn.completed','turn.failed','error'):
                    continue
                terminal[kind] += 1
                if kind in ('turn.failed','error'):
                    message = str(event.get('error') or event.get('message',''))
                    trace_status.extend(re.findall(r'(?<!\d)(?:429|502|503|504)(?!\d)',message))
        generation_issue = next((name for name,pat in (
            ('thread_start',r"can't start new thread"),
            ('view_read',r'is damaged \(empty file\)'),
            ('launch_transport',r'Resource temporarily unavailable|No space left on device|could not reach the provider|no such file or directory.*bwrap'),
        ) if re.search(pat,log,re.I)),None)
    else:
        generation_issue = None
    e = execs[iid]
    snippet = str(e.get('stdout_tail',''))+str(e.get('per_step',''))
    if e['outcome'] in {'container_error','parse_or_compile_error','solution_error','no_scenario_ran'}:
        signals[iid].update(k for k,p in error_patterns.items() if re.search(p,snippet,re.I))
    result.append(dict(id=iid,project=t['project'],outcome=e['outcome'],generation=t['gen'],
                       generation_reason=t.get('reason'),job=job['id'] if job else None,
                       reused=bool(previous),stop=stop,calls=calls,trace_exists=trace.is_file(),
                       terminal=dict(terminal),trace_http=sorted(set(trace_status)),
                       gateway_http=[a['status'] for a in job.get('api_errors',[])] if job else [],
                       generation_issue=generation_issue,exec_signals=sorted(signals[iid]),
                       returncode=job.get('returncode') if job else None))
mutation = []
for f in official.glob('*/th/mutation/*.jsonl'):
    for row in map(json.loads,f.open()):
        if row['outcome'] not in ('passed','failed') or row.get('retried_infrastructure'):
            mutation.append({k:row[k] for k in ('instance_id','mutant_id','outcome','retried_infrastructure') if k in row})
print(json.dumps(dict(tasks=result,mutation_exception_rows=mutation),ensure_ascii=False))
