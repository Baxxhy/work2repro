"""Run unchanged predictions or DI-only variants as ordinary candidate submissions."""
from pathlib import Path
import json
import sys
from req2test import evaluate, execute

stage,project=sys.argv[1:]
work=Path(__file__).parent
bench=Path.home()/'benchmark'
path=work/(stage+'-'+project+'.jsonl')
ids=[json.loads(s)['instance_id'] for s in path.read_text().splitlines()]
assert ids and len(ids)==len(set(ids))
run_id=f'r2t-di-{work.name[:15]}-{stage}-{project}'
art=work/'full-logs'/run_id
original=execute.engine_namespace
def with_logging(argv):
    if 'run' in argv:
        argv = [*argv, '--keep-artifacts', str(art)]
    return original(argv)
execute.engine_namespace=with_logging
print('run_id',run_id,'input',path,flush=True)
evaluate.evaluate(str(path),run_id=run_id,split='eval',project=project,instances=ids,view='th',workers=1,metrics='exec',docker_host='unix:///run/user/1001/req2test-docker-10156f49/docker.sock')
