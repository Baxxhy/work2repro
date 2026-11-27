import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

base = Path(__file__).resolve().parent
data = json.loads((base / '评分材料.json').read_text())
implementation = (base / 'solution.py').read_text()
tests = (base / 'test_solution.py').read_text()
reference = data['S3']['reference']
versions = {'AI': implementation, 'official_reference': reference}
for key, row in data.items():
    source = reference
    changes = [line for line in row['mutant_patch'].splitlines()
               if line.startswith(('-', '+')) and not line.startswith(('---','+++'))]
    old = '\n'.join(line[1:] for line in changes if line.startswith('-'))
    new = '\n'.join(line[1:] for line in changes if line.startswith('+'))
    assert source.count(old) == 1
    versions['official_mutant_' + key] = source.replace(old, new)
results = {}
for name, source in versions.items():
    with tempfile.TemporaryDirectory() as tmp:
        dest = Path(tmp)
        (dest/'solution.py').write_text(source)
        (dest/'test_solution.py').write_text(tests)
        run = subprocess.run([sys.executable, 'test_solution.py','-v'], cwd=tmp,
                             capture_output=True, text=True, timeout=20)
        results[name] = {'exit': run.returncode, 'log': run.stderr}
def get_function(source):
    ns = {}
    exec(source,ns)
    return ns['unescape']
ai, gold = map(get_function, (implementation, reference))
deltas = []
for i in range(128):
    s = '\\' + chr(i)
    if ai(s) != gold(s):
        deltas.append({'input':s, 'AI':ai(s), 'reference':gold(s)})
def keyword_probe(f):
    try:
        return f(s=r'\.')
    except TypeError as e:
        return str(e)
res = {'unittests': results, 'ascii_diff': deltas,
       'keyword_s': {n:keyword_probe(get_function(v)) for n,v in versions.items()}}
(base/'结果.json').write_text(json.dumps(res, ensure_ascii=False, indent=2)+'\n')
print({name:r['exit'] for name,r in results.items()}, deltas, res['keyword_s'])
