from pathlib import Path
import json
import subprocess

root = Path('/root/Baxxhy/work2/reproductions/testsyncer')
tu = root.parent / 'testupdater'
mumu = root.parent / 'mumutestup'
(root / 'datasets/prbench').mkdir(parents=True, exist_ok=True)
if not (root / 'runtime').exists():
    (root / 'runtime').symlink_to(tu / 'runtime', target_is_directory=True)
count = 0
for path in sorted((tu / 'datasets/prbench').glob('*.json')):
    rows = json.loads(path.read_text())
    project = rows[0]['repo_name']
    originals = json.loads((mumu / 'upstream-luna/dataset' / project / 'data.json').read_text())
    assert len(originals) == len(rows)
    for row, original in zip(rows, originals):
        assert row['commit_tgt'] == original['aCommit']
        assert row['test_code_src'] == original['bSource']['code']
        row['_testsyncer_focal'] = original['focal_method']
        assert 'b_focal_method_path' in row['_testsyncer_focal']
    (root / 'datasets/prbench' / path.name).write_text(json.dumps(rows))
    for folder in ['repos', 'old-repos']:
        destination = root / folder / project
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            subprocess.run(['git', 'clone', '--shared', str(mumu / 'repos' / project), str(destination)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    count += len(rows)
    print(project, len(rows), flush=True)
print('total', count, flush=True)
