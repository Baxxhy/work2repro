"""Wait for the recovery run, then settle the complete original population."""
import collections
import json
from pathlib import Path
import subprocess
import sys
import time

ARCHIVE = Path(__file__).resolve().parent
RUN = ARCHIVE.parent.parent / 'reproductions/req2test/req2test-medium-recovery313-20261126'
UNIT = 'req2test-medium-recovery313-20261126.service'


def read_json(path):
    return json.loads(path.read_text())


def main():
    completion = RUN / 'completion.json'
    while not completion.is_file():
        state = subprocess.run(['systemctl', 'show', UNIT, '-p', 'ActiveState', '--value'],
                               text=True, capture_output=True, check=True).stdout.strip()
        if state in {'failed', 'inactive'} and not completion.is_file():
            raise RuntimeError(f'Recovery stopped before completion: {state}')
        time.sleep(30)
    summary = read_json(completion)
    expected = set(read_json(RUN / 'recovery-ids.json'))
    observed = set(read_json(RUN / 'result_comparison.json'))
    missing = sorted(expected - observed)
    unexpected = sorted(observed - expected)
    bad_groups = {key: value['state'] for key, value in summary['evaluation_groups'].items()
                  if value['state'] != 'finished'}
    if missing or unexpected or bad_groups:
        evidence = dict(expected=len(expected), observed=len(observed), missing=missing, unexpected=unexpected,
                        generation=summary['generation'], blocked_groups=bad_groups)
        (RUN / 'recovery-result-check.json').write_text(json.dumps(evidence, indent=2) + '\n')
        raise RuntimeError(f'Recovery cannot settle: {len(missing)} missing, '
                           f'{len(unexpected)} unexpected, {len(bad_groups)} unfinished groups')
    subprocess.run([sys.executable, str(ARCHIVE / '结算全量-11-26.py')], check=True)
    final = read_json(RUN / 'final-pass-at-1.json')
    if final['total'] != 2051:
        raise ValueError('Unexpected full settlement count')
    summary = dict(recovered=len(observed), full_total=final['total'],
                   execution_passes=collections.Counter(
                       x['after'] for x in read_json(RUN / 'result_comparison.json').values())['passed'],
                   official_macro_pass_at_1=final['official_macro'])
    (RUN / 'recovery-result-check.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
