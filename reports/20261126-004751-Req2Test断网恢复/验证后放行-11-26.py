"""Release the frozen recovery queue after a valid Medium canary."""
import json
from pathlib import Path
import sys


def read_json(path):
    return json.loads(path.read_text())


run = Path(sys.argv[1])
config = read_json(run / 'frozen/config.json')
state = read_json(run / 'state.json')
key = config['canary_task_key']
task = state['tasks'][key]
jobs = [job for job in state['jobs'].values() if job.get('phase') == 'gen_req' and job.get('key') == key]
job = max(jobs, key=lambda item: item['start'], default={})
outcome = job.get('generation_outcome', {})
proof = dict(instance_id=task['id'], state=task['gen'], reason=task.get('reason'),
             attempts=task['gen_attempts'], upstream_requests=job.get('api_requests', 0),
             upstream_error_codes=[error['status'] for error in job.get('api_errors', [])],
             outcome={field: outcome.get(field) for field in (
                 'kind', 'reason', 'prediction_valid', 'turn_completed', 'n_files', 'llm_calls')})
print(json.dumps(proof))
if task['gen'] in {'pending', 'running'}:
    raise SystemExit(75)
if (task['gen'] != 'finished' or not outcome.get('prediction_valid')
        or not outcome.get('turn_completed') or not proof['upstream_requests']):
    raise SystemExit('Canary did not produce a valid prediction and terminal model response')
predictions = [json.loads(line) for line in Path(task['prediction']).read_text().splitlines() if line.strip()]
if (len(predictions) != 1 or predictions[0]['instance_id'] != task['id']
        or predictions[0]['model_name_or_path'] != 'codex-gpt-6-luna-medium'):
    raise ValueError('Canary prediction does not match the frozen model and task')
temporary = run / '.release-generation.tmp'
temporary.write_text(json.dumps(proof, indent=2) + '\n')
temporary.replace(run / 'release-generation')
