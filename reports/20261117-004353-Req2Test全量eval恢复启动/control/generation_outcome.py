"""Classify official Req2Test attempts without using their test score."""
import json
import re
from pathlib import Path


def inspect_req_generation(prediction, job_dir, instance_id):
    prediction, job_dir = Path(prediction), Path(job_dir)
    log = (job_dir / 'job.log').read_text(errors='replace') if (job_dir / 'job.log').exists() else ''
    trace = prediction.parent / 'workspaces/0000.log'
    events = []
    if trace.exists():
        for line in trace.read_text(errors='replace').splitlines():
            try:
                event=json.loads(line)
                if isinstance(event,dict):events.append(event)
            except ValueError:
                pass
    completed = any(e.get('type') == 'turn.completed' for e in events)
    errors = [str(e.get('message', e.get('error', ''))) for e in events
              if e.get('type') in ('error', 'turn.failed')]
    network = any(re.search(r'Reconnecting|Connection failed|error sending request|network|could not reach', e, re.I) for e in errors)
    summaries = re.findall(r'\[\d+\] (exit \d+|timed out|stopped at the budget) after (\d+) LLM call\(s\)', log)
    status, calls = summaries[-1] if summaries else ('unknown', None)
    calls = int(calls) if calls is not None else None
    valid = False
    n_files = 0
    if prediction.exists():
        try:
            rows = [json.loads(x) for x in prediction.read_text().splitlines() if x.strip()]
            valid = len(rows) == 1 and rows[0].get('instance_id') == instance_id and isinstance(rows[0].get('files'), list)
            if valid:
                n_files = len(rows[0]['files'])
        except (ValueError, TypeError):
            pass
    outcome = dict(kind='generation_failure', reason='official_agent_nonzero_exit',
                   official_stop=status, llm_calls=calls, turn_completed=completed,
                   prediction_valid=valid, n_files=n_files, trace=str(trace))
    if (job_dir/'infrastructure-abort.json').exists():
        outcome.update(kind='infrastructure',reason='bounded_network_stall_abort')
        return outcome
    # A reached official call limit is a model-budget result, including an empty suite.
    if status == 'stopped at the budget' and valid:
        outcome.update(kind='result', reason='official_call_budget')
    elif status == 'timed out' and not completed and (network or calls == 0):
        outcome.update(kind='infrastructure', reason='network_stall' if network else 'startup_zero_calls')
    elif not completed and re.search(r'BlockingIOError|Resource temporarily unavailable|bwrap:|could not reach the provider|network is unreachable|EAI_AGAIN|failed to start', log, re.I):
        outcome.update(kind='infrastructure', reason='launch_or_transport_failure')
    elif status in ('exit 0', 'timed out') and valid:
        if status == 'exit 0' and not completed:
            outcome.update(kind='infrastructure', reason='missing_agent_terminal_event')
        else:
            outcome.update(kind='result', reason='normal_completion' if completed else 'official_wall_clock_budget')
    elif not valid and (prediction.exists() or status in ('exit 0', 'timed out', 'stopped at the budget')):
        outcome.update(kind='infrastructure', reason='invalid_or_missing_prediction')
    elif not completed and network:
        outcome.update(kind='infrastructure', reason='network_interruption')
    return outcome
