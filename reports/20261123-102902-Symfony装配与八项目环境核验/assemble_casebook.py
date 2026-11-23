from pathlib import Path
import csv,json
import yaml

d=Path(__file__).parent
def j(s):return json.loads((d/s).read_text())
trace={r['id']:r for r in j('任务视图与生成轨迹证据-11-23.json')}
changes={r['id']:r for r in j('诊断变更及原件校验-11-23.json')}
with (d/'十条装配问题最终对照-11-23.csv').open() as f:ab=list(csv.DictReader(f))
cause={
'category_condition.feature:23':('container','构造函数请求容器接口，缺少具体绑定','购物车规则'),
'country_condition.feature:30':('ruleValidationProcessor','YAML 只绑定了承运商仓库，未绑定配送规则处理器','配送国家'),
'product_variant_condition.feature:43':('validationProcessor','YAML 绑定了工厂和商品，未绑定配送规则处理器','配送商品变体'),
'customer_condition.feature:17':('paymentProviderRuleFactory','多种工厂没有唯一类型映射；生成的具体工厂类也与实际对象不兼容','支付规则客户条件'),
'product_condition.feature:29':('ruleFactory','多种工厂没有唯一类型映射；生成的具体工厂类也与实际对象不兼容','支付规则商品条件'),
'timespan_condition.feature:12':('productRepository','多种资源仓库没有唯一类型映射','商品限时价格'),
'province_unique_fields_validation.feature:21':('adminApiClient','通用 API 客户端接口同时有后台和商店实现','后台编辑省份'),
'editing_catalog_promotion.feature:132':('adminApiClient','通用 API 客户端接口同时有后台和商店实现','后台编辑促销'),
'subscribing_newsletter_during_registration.feature:11':('client','通用 API 客户端接口同时有后台和商店实现','商店注册并订阅'),
'removing_locale.feature:14':('responseChecker','YAML 使用了不存在的响应检查器名称','后台移除语言')}
rows=[]
for r in ab:
    iid=r['instance_id'];param,why,scenario=cause[iid.split('/')[-1]]
    change=changes[iid]
    cfg=next(iter(yaml.safe_load(change['yaml_after'])['services'].values()))
    rows.append(dict(project=r['project'],arm=r['arm'],instance_id=iid,scenario=scenario,submitted_yaml=bool(change['yaml_before']),root_parameter='$'+param,cause=why,
                     service_binding=cfg['arguments']['$'+param],php_change=r['constructor_interface']=='yes',after=r['diagnostic_final'],post_di_error=r['first_step_error'],trace=trace[iid]['generation_log_sha256'],
                     php=change['php_path'],original_php_sha256=change['php_sha256'],final_log=r['full_stdout_relative'],final_log_sha256=r['full_stdout_sha256']))
with (d/'逐任务装配原因与修复-11-23.csv').open('w') as f:
    w=csv.DictWriter(f,list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
print(len(rows))
