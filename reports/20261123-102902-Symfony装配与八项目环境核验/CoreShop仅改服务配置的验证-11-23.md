# CoreShop 六项隔离诊断
北京时间 2026-11-23 10:54:01。六份 PHP 字节相同，服务片段已单独冻结。六条都消除了原先 Symfony 编译服务容器时的错误。原先有明确日志的三条（购物车类别、配送国家、配送商品变体）均到达步骤绑定阶段，出现 undefined_steps。

原先日志截断的三条中，商品特殊价格规则已进入步骤，出现 No such method: fail。另两条支付规则在载入构造函数时出现了新的、可以区分的 PHP TypeError。项目 PaymentBundle/DependencyInjection/Configuration.php 将 payment_provider_rule 工厂配置为 Factory，生成构造函数要求另一具体类 PimcoreFactory。即使指定正确的服务名也不能满足这个 PHP 类型。两者都实现 Resource/Factory/FactoryInterface，生成代码对该依赖只调用 createNew()。

这两份诊断副本的第二次实验只将构造声明和 import 改成相应接口，保留首轮 YAML、业务方法及全部断言，并用单独 run-id 验证。完成记录另列。
