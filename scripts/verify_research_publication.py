"""Offline integrity checks for the published empirical-analysis snapshot."""
import csv
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
manifest = json.loads((ROOT / 'reports/research-publication-manifest.json').read_text())
for name, expected in manifest['files'].items():
    path = ROOT / name
    assert path.is_file(), f'Missing file: {name}'
    assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, f'Hash mismatch: {name}'

study = ROOT / 'reports/business-behavior-gap-20261116'
pairs = list(csv.DictReader((study / 'MUTANT_LEVEL_EVIDENCE.csv').open()))
assert len(pairs) == 833
assert len({(row['instance_id'], row['mutant_id']) for row in pairs}) == 833
assert len({(row['project'], row['mutant_id']) for row in pairs}) == 783
selection = json.loads((study / 'manifest.json').read_text())
assert len(selection['nonkill']) == 20
assert len(selection['controls']) == 15
assert len(list((study / 'cases').glob('*/case.json'))) == 6
for name in manifest['markdown_link_adjustments']:
    path = ROOT / name
    for target in re.findall(r'\]\(([^)]+)\)', path.read_text()):
        if target.startswith(('http:', 'https:', '#', '/')):
            continue
        assert (path.parent / target.split('#', 1)[0]).exists(), f'Broken link: {name} -> {target}'
print(f"Verified {len(manifest['files'])} research files, 833 pairs, 35 new Req2Test cases and 6 TSB cases.")
