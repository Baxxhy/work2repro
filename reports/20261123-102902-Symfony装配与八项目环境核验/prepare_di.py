"""Create separate DI-only diagnostic copies. Never edit source submissions."""
import hashlib
import json
from pathlib import Path
import re
import sys
import yaml

bindings = {
    'cart/rules/category_condition.feature:23': {'container':'service_container'},
    'shipping_rules/country_condition.feature:30': {'ruleValidationProcessor':'coreshop.shipping_rule.processor'},
    'shipping_rules/product_variant_condition.feature:43': {'validationProcessor':'coreshop.shipping_rule.processor'},
    'payment_provider_rules/customer_condition.feature:17': {
        'paymentProviderRuleFactory':'coreshop.factory.payment_provider_rule','ruleValidationProcessor':'coreshop.payment_provider_rule.processor','paymentProviderRepository':'coreshop.repository.payment_provider'},
    'payment_provider_rules/product_condition.feature:29':{
        'ruleFactory':'coreshop.factory.payment_provider_rule','products':'coreshop.repository.product','providers':'coreshop.repository.payment_provider','validationProcessor':'coreshop.payment_provider_rule.processor','conditionFactory':'coreshop.factory.rule_condition'},
    'specific_price_rules/timespan_condition.feature:12':{
        'productRepository':'coreshop.repository.product','specificPriceRuleFactory':'coreshop.factory.product_specific_price_rule','validationProcessor':'coreshop.product_specific_price_rule.processor','shopperContext':r'CoreShop\Component\Core\Context\ShopperContextInterface'},
    'managing_countries/province_unique_fields_validation.feature:21':{'adminApiClient':'sylius.behat.api_platform_client.admin'},
    'managing_catalog_promotions/editing_catalog_promotion.feature:132':{'adminApiClient':'sylius.behat.api_platform_client.admin'},
    'managing_locales/removing_locale.feature:14':{'responseChecker':r'Sylius\Behat\Client\ResponseCheckerInterface'},
    'account/subscribing_newsletter_during_registration.feature:11':{'client':'sylius.behat.api_platform_client.shop'},
}
def digest(s):
    return hashlib.sha256(s.encode()).hexdigest()

def main(source, dest):
    evidence = []
    groups = {}
    for path in sorted(source.glob('req2test-paired80-20261123-?-audit-*.jsonl')):
        for line in path.read_text().splitlines():
            row=json.loads(line)
            iid=row['instance_id']
            suffix, = [s for s in bindings if iid.endswith('/'+s)]
            php, = [f for f in row['files'] if f['path'].endswith('.php')]
            c=php['content']
            cls=re.search(r'namespace ([^;]+);',c)[1]+'\\'+re.search(r'\bclass (\w+) implements',c)[1]
            y=next((f for f in row['files'] if f['path']=='behat_services.yml'),None)
            old=y['content'] if y else ''
            if not y:
                y={'path':'behat_services.yml','content':''}
                row['files'].append(y)
            doc=yaml.safe_load(old) or {'services':{}}
            service=doc['services'].setdefault(cls,{})
            args=service.setdefault('arguments',{})
            for arg,service_id in bindings[suffix].items():
                assert '$'+arg in c
                args['$'+arg]='@'+service_id
            service['autowire']=True
            y['content']=yaml.safe_dump(doc,sort_keys=False)
            row['model_name_or_path']='diagnostic-di-only'
            groups.setdefault(iid.split('/')[0],[]).append(row)
            evidence.append(dict(id=iid,source=path.name,php_path=php['path'],php_sha256=digest(c),original_row_sha256=digest(line),diagnostic_row_sha256=digest(json.dumps(row,ensure_ascii=False)),yaml_before=old,yaml_after=y['content']))
    assert len(evidence)==len(bindings)==len({x['id'] for x in evidence})
    for proj,rows in groups.items():
        with (dest/f'fixed-{proj}.jsonl').open('x') as f:
            for x in rows:f.write(json.dumps(x,ensure_ascii=False)+'\n')
    (dest/'di-manifest.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__':
    main(Path(sys.argv[1]),Path(sys.argv[2]))
