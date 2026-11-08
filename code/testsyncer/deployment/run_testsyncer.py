"""Run official TestSyncer prompts with the existing Luna and execution adapters."""
import argparse
import concurrent.futures
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path('/root/Baxxhy/work2/reproductions/testsyncer')
TU = ROOT.parent / 'testupdater'
MUMU = ROOT.parent / 'mumutestup'

def run_project(filename, output, limit, dataset):
    sys.path.insert(0, str(TU / 'runtime'))
    sys.path.insert(0, str(TU / 'deployment'))
    import pipeline
    import pipeline_helper as helper
    import run_testupdater as execution
    from langchain_core.messages import HumanMessage

    execution.ROOT = ROOT
    execution.DATA_ROOT = ROOT / 'datasets'
    pipeline.gen_info = lambda *args, **kwargs: None

    def testsyncer_main(input_file, output_folder, process_continue=True):
        rows = json.loads((ROOT / 'datasets' / dataset / input_file).read_text())
        if limit:
            rows = rows[:limit]
        project_output = Path(output) / dataset / Path(filename).stem
        destination = project_output / output_folder / input_file
        destination.parent.mkdir(parents=True, exist_ok=True)
        results = json.loads(destination.read_text()) if destination.exists() else []
        classpath = str(ROOT / 'official/AnalysisTool/target/classes') + ':' + (ROOT / 'classpath.txt').read_text().strip()
        for index in range(len(results), len(rows)):
            row = rows[index]
            pipeline.gen_info()  # Reset execution evidence through the shared adapter hook.
            sample_dir = project_output / 'prompts' / f'{index:04d}'
            sample_dir.mkdir(parents=True, exist_ok=True)
            row['method'] = 'TestSyncer'
            try:
                old_repo = ROOT / 'old-repos' / row['repo_name']
                new_repo = ROOT / 'repos' / row['repo_name']
                for repo, commit in [(old_repo, row['commit_src']), (new_repo, row['commit_tgt'])]:
                    subprocess.run(['git', '-C', str(repo), 'checkout', '--detach', '--force', commit], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                focal = row['_testsyncer_focal']
                request = {
                    'old_project': str(old_repo), 'new_project': str(new_repo),
                    'old_file': str(old_repo / focal['b_focal_method_path']),
                    'new_file': str(new_repo / focal['a_focal_method_path']),
                    'old_method': row['prod_code_src'], 'new_method': row['prod_code_tgt'],
                    'old_test': row['test_code_src'],
                }
                (sample_dir / 'input.json').write_text(json.dumps(request))
                with (sample_dir / 'analysis.log').open('w') as log:
                    subprocess.run([str(MUMU / 'toolchains/jdk17/bin/java'), '-Xmx4g', '-cp', classpath, 'experiment.PRBenchPrompt', str(sample_dir / 'input.json'), str(sample_dir / 'prompt.txt')], check=True, stdout=log, stderr=subprocess.STDOUT, timeout=900)
                prompt = (sample_dir / 'prompt.txt').read_text()
                response = pipeline.model.invoke([HumanMessage(content=prompt)]).content
                (sample_dir / 'response.txt').write_text(response)
                code = helper.extract_code(response)
                imports = re.findall(r'^\s*import\s+[^;]+;', code, flags=re.MULTILINE)
                code = re.sub(r'^\s*import\s+[^;]+;\s*', '', code, flags=re.MULTILINE).strip()
                row['test_gen'] = code
                row['imports_gen'] = '\n'.join(imports)
                returncode, errors, tests = pipeline.build_test(row)
                row['test_pass'] = returncode == 0
                row['build_pass'] = returncode == 0 or bool(tests)
                row['execution_errors'] = errors
            except Exception as error:
                row['exception_while_gen_tests'] = repr(error)
            results.append(row)
            pipeline.write_json(str(destination), results)

    pipeline.main = testsyncer_main
    return execution.worker(dataset, filename, output, limit)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--smoke', action='store_true')
    parser.add_argument('--dataset', choices=['prbench', 'updates4j'], default='prbench')
    args = parser.parse_args()
    files = sorted((ROOT / 'datasets' / args.dataset).glob('*.json'))
    if args.smoke:
        files = [p for p in files if ('nfe' in p.name or 'ormlite' in p.name)] if args.dataset == 'prbench' else [p for p in files if 'acme4j' in p.name]
    args.output.mkdir(parents=True, exist_ok=True)
    state = {'state': 'running', 'pid': os.getpid(), 'started_at': time.time(), 'method': 'TestSyncer', 'model': 'gpt-6-luna', 'reasoning_effort': 'medium', 'selected': len(files) if args.smoke else sum(len(json.loads(p.read_text())) for p in files), 'projects': []}
    status = args.output / 'status.json'
    status.write_text(json.dumps(state, indent=2))
    with concurrent.futures.ProcessPoolExecutor(max_workers=10, max_tasks_per_child=1) as pool:
        futures = [pool.submit(run_project, p.name, str(args.output), 1 if args.smoke else None, args.dataset) for p in files]
        for future in concurrent.futures.as_completed(futures):
            try:
                state['projects'].append(future.result())
            except Exception as error:
                state['projects'].append({'state': 'worker_error', 'error': repr(error)})
            status.write_text(json.dumps(state, indent=2))
    state['state'] = 'finished' if all(p['state'] == 'finished' for p in state['projects']) else 'finished_with_errors'
    status.write_text(json.dumps(state, indent=2))

if __name__ == '__main__':
    main()
