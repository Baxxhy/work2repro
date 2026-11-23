# Sylius 服务装配的独立验证
北京时间 2026-11-23 10:47:12。只修复服务配置、保留生成的 PHP，4/4 从 Symfony 初始化失败进入场景；4/4 随后在业务步骤失败。开发者原始测试曾在相同四个 ID 上通过。如下结果仅供诊断。

|任务|绑定的服务|后续执行结果|
|---|---|---|
|province_unique_fields_validation:21|后台 API 客户端|请求 URI 以斜杠开头，客户端拒绝|
|removing_locale:14|正确的 ResponseCheckerInterface 服务|移除步骤收到字符串，生成的方法需要 LocaleInterface|
|editing_catalog_promotion:132|后台 API 客户端|实际请求返回 HTTP 404|
|subscribing_newsletter_during_registration:11|商店 API 客户端|请求 URI 以斜杠开头，客户端拒绝|

4 份原回答都进入了同一个 Symfony 测试框架，缺失或填错的是具体服务。仅修正这些条目可以让 Behat 执行步骤，不能解决生成代码中另外存在的参数、路由和步骤定义问题。逐任务日志校验、退出码与步骤结果见同目录 JSON。
