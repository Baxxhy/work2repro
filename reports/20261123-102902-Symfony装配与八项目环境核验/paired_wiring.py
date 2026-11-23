"""Publish selected wiring declarations, not complete reference or generated code."""
import json,re
from pathlib import Path
from hashlib import sha256
root=Path.home()/'benchmark/runs'
def data(arm,project):
    d=root/f'req2test-paired80-20261123-{arm}-regenerated-{project}'/project/'th/exec.jsonl'
    return {x['item_id']:x for x in map(json.loads,d.open())}
out=[]
for project in ('coreshop','sylius'):
    a,b=data('a',project),data('b',project)
    for i in sorted(a):
        if a[i]['outcome']!='container_error' or b[i]['outcome']!='passed':continue
        row=b[i];decl=[]
        for f in row['produced_files']:
            for n,s in enumerate(f['code'].splitlines(),1):
                if (f['file_path'].endswith('behat_services.yml') and ': ' in s and '@' in s) or '#[Autowire(service:' in s:
                    decl.append(dict(path=f['file_path'],line=n,decl=s.strip(),file_sha256=sha256(f['code'].encode()).hexdigest()))
        assert decl
        out.append(dict(id=i,pass_arm='B',step_count=len(row['per_step']),bindings=decl))
assert len(out)==5
print(json.dumps(out,ensure_ascii=False,indent=2))
