import collections
import csv
import json
from pathlib import Path

here = Path(__file__).resolve().parent
baseline = here.parent / '20261118-010456-Req2Test全量尾项恢复与统计修正'
authors = json.loads((here / '作者Luna项目指标-11-18.json').read_text())
with (baseline / '逐任务状态与排除原因-11-18.csv').open() as stream:
    scored = [row for row in csv.DictReader(stream) if row['disposition'] == 'scored']
outcomes = ('pass', 'generation_failure', 'compilation_failure',
            'binding_failure', 'execution_failure', 'assertion_failure')
data = collections.defaultdict(collections.Counter)
for row in scored:
    data[row['project']][row['outcome']] += 1
assert len(scored) == 2031 and len(data) == len(authors) == 8
with (here / '项目差距与失败阶段-11-18.csv').open('w', newline='') as stream:
    writer = csv.writer(stream, lineterminator='\n')
    writer.writerow(['project', 'local_pass_denominator', *outcomes,
                     'local_pass_pct', 'paper_pass_count', 'paper_pass_denominator',
                     'paper_pass_pct', 'gap_pp'])
    for cell in authors:
        project = cell['project']
        counts = data[project]
        assert set(counts) <= set(outcomes)
        total = counts.total()
        local = 100 * counts['pass'] / total
        author = 100 * cell['values']['pass_at_1']
        assert abs(author - 100 * cell['pass'] / cell['pass_den']) < 1e-9
        writer.writerow([project, total, *(counts[k] for k in outcomes),
                         f'{local:.4f}', cell['pass'], cell['pass_den'],
                         f'{author:.4f}', f'{author - local:.4f}'])
totals = sum(data.values(), collections.Counter())
assert totals == dict(zip(outcomes, (527, 268, 398, 201, 75, 562)))
print(totals)
