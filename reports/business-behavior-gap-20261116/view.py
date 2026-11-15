import json,pathlib,sys
r=pathlib.Path(__file__).resolve().parent/'evidence'
for k in sys.argv[1:]:
 d=r/k;print('\nCASE',k);t=json.loads((d/'task.json').read_text());print(t['requirement']);
 for p in (d/'generated').rglob('*'):
  if p.is_file():print('GENERATED',p.relative_to(d),p.read_text())
 for m in json.loads((d/'surviving-mutants.json').read_text())[:20]:print('MUTANT',m['id'],m['file'],m.get('start_line'),m.get('original'),'=>',m.get('mutated'))
 print('REFERENCE', [str(p.relative_to(d)) for p in (d/'reference').rglob('*') if p.is_file()])
