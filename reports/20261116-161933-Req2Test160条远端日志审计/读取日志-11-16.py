import hashlib
import json
import multiprocessing
from pathlib import Path
import re
import sys


def inspect_task(task, connection):
    result = {'instance_id': task['instance_id'], 'artifact_id': task['artifact_id']}
    try:
        path = Path(task['original_record'])
        predictions = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        matches = [row for row in predictions if row.get('instance_id') == task['instance_id']]
        result['prediction_matches'] = len(matches)
        if len(matches) == 1:
            files = matches[0].get('files', [])
            result['actual_files'] = [{'path': f['path'], 'sha256': hashlib.sha256(f['content'].encode()).hexdigest()} for f in files]
            result['files_match'] = sorted(result['actual_files'], key=lambda x:x['path']) == sorted(task['generated_files'], key=lambda x:x['path'])
            result['prediction_metadata'] = matches[0].get('metadata')
        path = Path(task['original_trace'])
        result['trace_exists'] = path.exists()
        if path.exists():
            result['trace_bytes'] = path.stat().st_size
            with path.open('rb') as stream:
                stream.seek(max(0, result['trace_bytes'] - 160000))
                tail = stream.read().decode(errors='replace')
            result['harness_status'] = re.findall(r'^run_agent: (.*)$', tail, re.M)
            result['terminal_event_counts'] = {name: tail.count('"type":"'+name+'"') + tail.count('"type": "'+name+'"') for name in ['turn.completed','turn.failed','error']}
            result['tail'] = tail[-1800:]
        result['source'] = task['original_record']
        result['trace'] = task['original_trace']
    except Exception as error:
        result['read_error'] = type(error).__name__ + ': ' + str(error)
    connection.send(result)
    connection.close()

if __name__ == '__main__':
    payload = json.load(open(sys.argv[1]))
    for task in payload['tasks']:
        parent, child = multiprocessing.Pipe(False)
        process = multiprocessing.Process(target=inspect_task, args=(task, child), daemon=True)
        process.start()
        child.close()
        if parent.poll(20):
            try: result = parent.recv()
            except EOFError: result = {'instance_id':task['instance_id'], 'read_error':'child exited without result'}
        else:
            result = {'instance_id':task['instance_id'], 'read_error':'read exceeded 20 seconds', 'pid':process.pid}
            process.kill()
        process.join(timeout=0.2)
        parent.close()
        print(json.dumps(result, ensure_ascii=False), flush=True)
