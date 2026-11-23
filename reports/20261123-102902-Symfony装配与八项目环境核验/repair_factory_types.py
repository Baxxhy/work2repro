"""Only the two constructors rejected by PHP, after explicit service binding."""
import hashlib
import json
from pathlib import Path
import re
import sys
path=Path(sys.argv[1])
rows=[json.loads(l) for l in (path/'fixed-coreshop.jsonl').read_text().splitlines()]
manifest=[]
out=path/'typed-coreshop.jsonl'
with out.open('x') as dest:
    for x in rows:
        iid=x['instance_id']
        if '/payment_provider/payment_provider_rules/' not in iid:continue
        arg='paymentProviderRuleFactory' if iid.endswith('customer_condition.feature:17') else 'ruleFactory'
        php,=[f for f in x['files'] if f['path'].endswith('.php')]
        s=php['content']
        old_import=r'use CoreShop\Component\Resource\Factory\PimcoreFactory;'
        new_import=r'use CoreShop\Component\Resource\Factory\FactoryInterface;'
        old_arg=f'private PimcoreFactory ${arg},'
        new_arg=f'private FactoryInterface ${arg},'
        assert s.count(old_import)==s.count(old_arg)==1
        after=s.replace(old_import,new_import).replace(old_arg,new_arg)
        assert after.split(') {',1)[-1]==s.split(') {',1)[-1]
        php['content']=after
        manifest.append(dict(id=iid,parameter=arg,old_type=old_import[4:-1],new_type=new_import[4:-1],real_class=r'CoreShop\Component\Resource\Factory\Factory',sha256_before=hashlib.sha256(s.encode()).hexdigest(),sha256_after=hashlib.sha256(after.encode()).hexdigest()))
        dest.write(json.dumps(x,ensure_ascii=False)+'\n')
assert len(manifest)==2
(path/'typed-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
