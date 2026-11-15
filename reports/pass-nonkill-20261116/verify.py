"""Verify fixed evidence joins and hashes without invoking the benchmark."""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT.parents[1] / 'publication/work2repro/results/test-generation-20261114'
manifest = json.loads((ROOT / 'manifest.json').read_text())

def read(path):
    return json.loads(path.read_text())

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

assert sha(SOURCE / 'reports/req2test-per-task.jsonl') == manifest['source_sha256']
assert len({x['instance_id'] for x in manifest['nonkill']}) == 24
assert len({x['instance_id'] for x in manifest['controls']}) == 10
assert not {x['instance_id'] for x in manifest['nonkill']} & {x['instance_id'] for x in manifest['controls']}
operators = []
cache_hashes = {}
survivor_count = 0
control_count = 0
for group in ['nonkill', 'controls']:
    for case in manifest[group]:
        directory = ROOT / 'evidence' / case['artifact']['artifact_id']
        task = read(directory / 'task.json')
        execution = read(directory / 'execution.json')
        assert task['instance_id'] == case['instance_id'] == execution['item_id']
        assert execution['outcome'] == 'passed'
        records = read(directory / 'mutation-results.json')
        by_mutant = {record['mutant_id']: record for record in records}
        assert len(by_mutant) == len(records)
        execution_hashes = {hashlib.sha256(item['code'].encode()).hexdigest() for item in execution['produced_files']}
        for generated in case['artifact']['generated_files']:
            assert sha(directory / 'generated' / generated['path']) == generated['sha256']
            assert generated['sha256'] in execution_hashes
        if group == 'nonkill':
            mutants = read(directory / 'surviving-mutants.json')
            reference = read(directory / 'reference-kills.json')
            ids = {mutant['id'] for mutant in mutants}
            assert ids == {row['mutant_id'] for row in reference if row['gold_outcome'] == 'killed'}
            assert len(ids) == case['n_scored'] - case['n_killed']
            assert all(by_mutant[mid]['outcome'] == 'passed' for mid in ids)
            survivor_count += len(ids)
        else:
            mutants = read(directory / 'control-mutants.json')
            assert {row['id'] for row in mutants} == set(by_mutant)
            assert len(mutants) == case['n_scored'] + case['n_dropped']
            assert case['kill_complete']
            control_count += len(mutants)
        for operator, count in sorted(Counter(row['operator'] for row in mutants).items()):
            operators.append(dict(instance_id=case['instance_id'],project=case['project'],group=group,
                                  operator=operator,count=count))
        for path in sorted(directory.rglob('*')):
            if path.is_file():
                cache_hashes[str(path.relative_to(ROOT))] = sha(path)
assert survivor_count == 833
assert control_count == 787
with (ROOT / 'mutation_operator_counts.csv').open('w', newline='') as stream:
    writer = csv.DictWriter(stream, fieldnames=list(operators[0]))
    writer.writeheader()
    writer.writerows(operators)
required = ['PASS_NONKILL_CASE_ANALYSIS.md','KILL_COMPLETE_CONTROL_ANALYSIS.md',
            'FAILURE_MECHANISM_DATABASE.csv','CROSS_PROJECT_FINDINGS.md','RESEARCH_PROBLEM_UPDATE.md']
assert all((ROOT / name).stat().st_size > 0 for name in required)
with (ROOT / 'FAILURE_MECHANISM_DATABASE.csv').open() as stream:
    database = list(csv.DictReader(stream))
assert len(database) == 24
assert {row['instance_id'] for row in database} == {row['instance_id'] for row in manifest['nonkill']}
# Hash prior reports for future preservation checks. The fixed publication hash
# and generated-file hashes above are the available historical reference hashes.
protected = {}
prior = ROOT.parent / 'problem-discovery-20261116'
for name in ['TASK_INVENTORY.csv','PROBLEM_DISCOVERY_REPORT.md','FAILURE_CASE_DATABASE.csv',
             'CROSS_BENCHMARK_ANALYSIS.md','REPRESENTATIVE_CASES.md',
             'RELATED_WORK_GAP_ANALYSIS.md','RESEARCH_PROBLEM_CANDIDATES.md']:
    path = prior / name
    if path.exists():
        protected[str(path)] = sha(path)
preservation = ROOT / 'protected-report-hashes.json'
if preservation.exists():
    assert read(preservation) == protected
else:
    preservation.write_text(json.dumps(protected,indent=2)+'\n')
(ROOT / 'evidence-hashes.json').write_text(json.dumps(cache_hashes,indent=2)+'\n')
result = dict(status='passed',nonkill_cases=24,control_cases=10,surviving_pairs=833,
              control_mutant_pairs=787,generated_hashes_match_publication=True,
              published_metrics_hash_matches=True,prior_reports_checked=len(protected),
              evidence_files=len(cache_hashes),new_benchmark_execution=False,
              limitation='Reference kill labels available; per-mutant gold stack traces not retrieved. Semantic causal explanations were not intervention-tested.')
(ROOT / 'verification.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
