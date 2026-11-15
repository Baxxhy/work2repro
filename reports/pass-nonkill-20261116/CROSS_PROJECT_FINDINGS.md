# 跨项目现象与反例

## 固定范围

160条发布子集，官方计分159条，本次语义对象为其中24条执行通过且非KillComplete任务。10条成功对照从该子集的20条KillComplete中固定选择。24条覆盖8个项目、Python/Java/Go/PHP/Ruby五种语言，以及behave/Cucumber/Godog/Behat等框架。本次没有针对生成策略做干预。

## 项目分布

|项目|Pass非Kill|明确需求缺口观察|可联系代表性存活的缺口|参考范围/路径差异|存活解释未定|
|---|---:|---:|---:|---:|---:|
|algorand-sdk|1|0|0|1|0|
|coddy-agent|4|1|1|2|1|
|coreshop|1|1|1|0|0|
|e-petitions|2|1|0|1|1|
|kapua|2|1|1|1|0|
|prestashop|1|0|0|1|0|
|python-docx|12|1|1|10|1|
|sylius|1|1|1|0|0|
|合计|24|6|5|16|3|

“明确需求缺口观察”允许与“存活解释未定”重叠，e-petitions的相似请愿案例属于两列。后三个原因列采用互斥主判断，总计24。16条参考范围差异仅确认额外路径/观察存在，单条内仍可能有尚未逐一解释的变异体。[机器统计](project_mechanism_counts.csv)

## 反复出现的现象

### 需求要求的生产行为或观察边界被替代

CoreShop使用本地数组和匿名order。coddy ask-mode让自定义runner直接写文件，并用常量工具集和输入mode作为检查对象。Sylius直接检查共享order的currency，省略需求规定的管理员读取视角。三条来自三个项目、两种语言、两个框架，各自有明确代码证据及代表性存活路径。它们共同说明需求中的业务行为或可观察结果可能被测试自身构造的值替代。

这些实例的具体机制分别为业务对象替身、代理执行与自证式断言、观察边界收缩。当前证据只支持共享现象，尚不能推断相同模型内部原因，也不能将三条归为同一种修复需求。[逐任务分析的02、06、24节](PASS_NONKILL_CASE_ANALYSIS.md)

### 断言遗漏需求中的特定约束

coddy ask-mode的工具集与transcript检查未依赖真实观测。Kapua将指定异常类型和消息弱化成任意KapuaException。e-petitions将标题和签名数的行内关系弱化成全页分别存在。三条来自Go、Java、Ruby及Godog、Cucumber，支持“明确结果约束在实现断言时被弱化”的跨项目现象。e-petitions的存活因果链尚未证实，计数时只记观察到的断言缺口。[逐项分类](FAILURE_MECHANISM_DATABASE.csv)

### 参考测试的准备与接收者选择影响KillComplete

python-docx有10条采用不同对象获得路径或接收者来源。典型是生成直接保留add_table返回值，参考经document.tables检索，或生成使用run.font、参考使用style.font。其他项目也有对应差异，包括Kapua的按名查询、coddy的配置加载与额外目录、e-petitions的debate_outcome关联、PrestaShop的创建命令与URL处理、Algorand的整体响应比较。

16条涉及6个项目、五种语言。该现象在不同框架上反复出现，但广度包含参考执行依赖、输入构造与额外断言三种情形。它支持在语义归因前核对gold pool与需求关系，无法推出这些变异无效，也不能据此更改官方分数。[833对存活修改](surviving_mutant_pairs.csv)

### 必要准备状态没有真正建立

python-docx的add_section案例只有header/footer代理对象，没有已有定义。删除原有引用的变异因此存活。此类C机制目前只有一个充分明确的案例。cell-width的“未显式设置”条件有可疑之处，证据尚不足，未计入确认数量。暂不宣称这一机制跨项目普遍存在。[逐任务分析的15、18节](PASS_NONKILL_CASE_ANALYSIS.md)

## 反例与争议

- python-docx成功对照latent-style属性测试直接构造Document并精确读写属性，113/113。程序化构造本身不能解释失败。
- Algorand空composer对照76/76，却只检查发生异常，没有比较给定错误文本。KillComplete与全部需求约束得到验证之间存在边界。
- font.color非Kill案例只断言ColorFormat类型，恰好符合该场景唯一Then。不能因没有颜色值断言就判为断言薄弱。
- 保存文档案例有save和重新加载断言。固定路径可能留下旧文件，但缺少逐变异文件状态，保留INSUFFICIENT_EVIDENCE。
- coddy subagents HTTP的cwd差异可以解释一个存活，后台池的三个存活未能确认。该任务继续列为整体原因未定。
- e-petitions相似请愿的行关联缺失已确定，但其存活列表没有提供足够证据把两者直接相连。

## 可支持的结论范围

当前可以确认需求验证问题真实存在，并观察到跨项目重复表现。当前无法估计这类问题在全部2051条的发生率，无法比较不同模型发生率，也无法解释所有833个存活的动态因果。16条参考路径差异与6条需求缺口采用不同证据口径，后续统计必须继续保留这种区分。
