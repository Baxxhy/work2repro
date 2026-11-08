"""Summarize original execution outcomes and completed common metric evaluations."""
import collections
import csv
import json
from pathlib import Path
import statistics

ROOT=Path('/root/Baxxhy/work2/reproductions/comparison/metrics-20261108')

def summarize():
    groups=collections.defaultdict(list)
    for path in (ROOT/'results').glob('*/*/*/*/*.json'):
        record=json.loads(path.read_text())
        groups[(record['method'],record['dataset'])].append(record)
    statuses=collections.defaultdict(dict)
    for entry in json.loads((ROOT/'original-status-counts.json').read_text()):
        statuses[(entry['method'],entry['dataset'])][entry['status']]=entry['count']
    output=[]
    for (method,dataset),counts in sorted(statuses.items()):
        total=sum(counts.values())
        passed=sum(counts.get(status,0) for status in ['pass','coverage_loss','mutation_loss','coverage_and_mutation_loss'])
        evaluated=[r for r in groups[(method,dataset)] if r.get('state')=='evaluated']
        line=[];branch=[];mutation=[]
        for record in evaluated:
            coverage=record['coverage']['coverage_info'];mutants=record['mutation']['mutation_info']
            if coverage.get('total_lines',0)>0:line.append(coverage['line_coverage_percentage'])
            if coverage.get('total_branches',0)>0 and coverage.get('branch_coverage_percentage') is not None:branch.append(coverage['branch_coverage_percentage'])
            if mutants.get('total_mutations',0)>0:mutation.append(mutants['kill_percentage'])
        output.append({'method':method,'dataset':dataset,'total':total,'test_pass_count':passed,'test_pass_percent':100*passed/total,'confirmed_compile_pass_count':passed+counts.get('run_fail',0),'generation_or_framework_errors':counts.get('harness_error',0),'evaluated_passed_tests':len(evaluated),'pending_passed_tests':passed-sum(r.get('original_passed',False) for r in groups[(method,dataset)]),'evaluation_errors':sum(r.get('state') in ['evaluation_error','execution_failed'] for r in groups[(method,dataset)]),'line_coverage_mean':statistics.mean(line) if line else None,'line_n':len(line),'branch_coverage_mean':statistics.mean(branch) if branch else None,'branch_n':len(branch),'mutation_score_mean':statistics.mean(mutation) if mutation else None,'mutation_n':len(mutation)})
    payload={'aggregation':'Unweighted mean across successfully evaluated passing tests. Zero-line, zero-branch or zero-mutant cases omitted from that metric with denominators shown. Partial results until pending and evaluation errors are zero. Compile-pass count is a lower bound when generation/framework errors exist.','rows':output}
    temporary=ROOT/'summary.tmp';temporary.write_text(json.dumps(payload,indent=2));temporary.replace(ROOT/'summary.json')
    with (ROOT/'summary.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(output[0]));writer.writeheader();writer.writerows(output)
    return output

if __name__=='__main__':
    print(json.dumps(summarize(),indent=2))
