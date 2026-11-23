from collections import Counter
import csv
import datetime
import json
from pathlib import Path
from zoneinfo import ZoneInfo
d=Path(__file__).parent
def readrows(name):
    with (d/name).open() as f:return list(csv.DictReader(f))
def load(name):return json.loads((d/name).read_text())
def num(rows,key='engine',val='passed'):return sum(r[key]==val for r in rows)
def doc(name):return '['+name.split('-11-23')[0]+']('+name+')'
diag=readrows('逐任务装配原因与修复-11-23.csv')
gold=readrows('八项目原始测试环境对照-11-23.csv')
ref=readrows('普通候选通道对照-11-23.csv')
counts=load('八十项配对与注册异常交叉统计-11-23.json')
assert len(diag)==len(ref)==num(ref)==10 and len(gold)==num(gold)==28
s=counts['all'];assert s['p']>0.05
totals=Counter(r['after'] for r in diag)
assert totals=={'undefined_steps':4,'failed':6}
special=counts['ten'];remaining=counts['remaining']
now=datetime.datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
text=f"""# Req2Test 八项目环境核验、装配归因与全量决策

北京时间从 2026-11-23 10:29:02 开始，{now} 完成。使用锁定版本 c0d7138、Benchmark 1.1 官方人口和原 80 个 TH 任务。本轮模型调用 0 次。

**决定：暂不启动 B 组 2,051 条全量实验。** 十项异常均已定位到生成测试的依赖装配。八项目抽检的开发者原始测试 28/28 通过。正式配对中 B 领先，但双侧精确 McNemar 检验未达到此前使用的 0.05 门槛。

## 生成的测试错在哪里

10/10 份生成回答的 PHP 上下文类都被引擎接收、注册。构造函数还需要告诉 Symfony 应注入哪一个服务。7 份没交付服务文件，2 份交付的文件漏掉了关键参数，1 份使用了不存在的服务名称。十次原会话均正常结束，每项 13–27 次模型调用。任务提示已说明如何提交注册文件。

以 Sylius 的后台省份编辑为例，后台客户端和商店客户端都实现 ApiClientInterface。A 声明了接口却未选择后台客户端，测试在第一步前就报错。给原 PHP 补上对应参数的服务名 sylius.behat.api_platform_client.admin 后，前三步通过，下一步因请求 URI 以斜杠开头而失败。B 在同一题的原始生成中交付了后台客户端绑定，七个步骤通过。

**7 条原来已定位的故障都只需修改服务配置即可越过失败点。** 另外 3 条原来被截断的错误中，两条是支付规则的工厂选择，一条是商品仓库选择。用官方 keep-artifacts 重放，完整 stdout 清楚指出了这三个参数。两个支付场景还存在第二层问题：绑定正确的工厂后，PHP 仍强制要求 PimcoreFactory，项目实际提供 Factory。只把构造声明改为它们共同实现的 FactoryInterface，即可让 Behat 执行或匹配步骤。

最终 8 条仅改服务配置，另外 2 条还修改了构造类型。所有诊断副本保留原业务步骤和断言；修复后 4 条有步骤未定义，6 条在业务步骤中失败，完整场景通过 0 条。每条的原参数、替换服务、正式与诊断结果、原 PHP 和运行日志校验均可追溯。{doc('逐任务装配原因与修复-11-23.csv')}；{doc('十条装配问题最终对照-11-23.csv')}。

## 环境是否能运行同一份测试

CoreShop 6 条、Sylius 4 条的官方 Behat 对照全部通过。额外把这十份相同的开发者测试文件和服务声明当普通候选提交，使其走与 A/B 相同的答案处理路径，仍有 {num(ref)}/{len(ref)} 通过，退出码均为 0。两条路径使用相同代码字节，在提交标记与处理规则上不同。

其余六个项目从各自的十项中按测试类型和依赖分层各取三条，新增 18/18 通过。合计八项目 28 个不同 ID，28/28 通过。CoreShop、Sylius、PrestaShop 的 MySQL 资格记录均包含通过的数据库探测和重置。任务实际调用的依赖、框架、运行脚本在这些样本上可用。八个项目分别核对了 A、B、开发者对照的镜像摘要、kit、profile、数据和引擎版本。同一项目匹配，A/B 的评测并发均为 2，对照为 1。此前一次 Sylius 数据库启动中断单独留档。抽样无法排除其他 ID、其他日期或更高并发下的环境故障。{doc('八项目原始测试环境核验-11-23.md')}；{doc('普通候选通道对照-11-23.csv')}。

## 正式 A/B 与决策依据

|配置|抽取|官方排除|通过 / 有效|合并通过率|八项目等权 Pass@1|
|---|---:|---:|---:|---:|---:|
|A · 0.160.0 / medium / 有运行包|80|1|30/79|37.97%|37.50%|
|B · 0.153.4 / high / 无运行包|80|1|39/79|49.37%|49.44%|

两组为同一条 Sylius 人口排除记录。十条装配失败保留 compilation_failure。配对结果为共同通过 {s['both']}、仅 A 通过 {s['only_a']}、仅 B 通过 {s['only_b']}、共同未通过 {s['neither']}。B 净多通过 9 项；按任务合并高 11.39 个百分点，双侧精确 McNemar p={s['p']:.6f}。

在涉及这十条故障的相同任务上，A 通过 {special['A_pass']}/10，B 通过 {special['B_pass']}/10。B 五条成功回答的实际代码都显式选择了所需服务，四条使用 YAML，一条使用 PHP 参数属性。在其余 69 项上，A 通过 {remaining['A_pass']} 项，B 通过 {remaining['B_pass']} 项。这是正式结果的分布；从结果选出的十项不能用来估计配置改变的因果效应。

**本次实验支持两项判断：这 10 条应按官方规则计分；现有 80 个任务还不足以按预设条件启动全量重跑。** 此轮未修改原基线或评分器，手工修复、开发者参考和普通候选对照均保存在不同运行目录。{doc('八十项配对与注册异常交叉统计-11-23.json')}。

## 证据入口

- 服务器完整诊断 stdout 位于 4x3090 的 `/root/lby-docker/req2test/user/runs/{d.name}/full-logs/`。公开表列出逐项相对路径与 SHA-256。原执行行和全部环境对照位于同机 `/root/lby-docker/req2test/user/benchmark/runs/`，CSV 中记录准确 run ID。
- 离线复核命令为 `python3 verify_diagnosis.py`，检查样本 ID、有效分母、配对检验、逐项对照、镜像与评分证据。
"""
(d/'八项目复核与全量决策-11-23.md').write_text(text)
