# 检索与审阅记录

采用CCF文献检索、问题评审和人话写作技能。目标为ICSE/FSE/ASE/ISSTA/TSE/TOSEM类软件工程研究的问题确认，当前判断为阶段性研究方向选择。

公开检索词包括LLM test generation、requirements-based mutation、test oracle、specification coverage、repository-level generation、test repair、TestPilot、TELPA、CoverUp、TaRGET。检索日期2026-11-16。以作者论文、arXiv和机构页面核查，排除只有二手搜索摘要支持的结论。

18个纳入条目包括需求基准、生成与修复方法、评价实证和经典预言/需求覆盖研究。发现2410.19794实际为DiffGAN图像网络差分测试，排除其作为LLM单元变异生成的引用。媒体评论和论坛讨论未作为研究结论来源。RESTestBench正文含DOI占位符，因此引用真实arXiv记录，不复制占位DOI。

近邻优先级最高为Req2Test、RESTestBench、PBMT和充分性准则实证。其共同提示已有工作已研究行为充分性和需求相关变异。TELPA、CoverUp、TestPilot用于确定已解决的上下文/覆盖问题。TaRGET、TestART用于约束对修复的推断。SWT-Bench提供真实缺陷双版本评价思路。

重点正文阅读覆盖Req2Test任务定义与度量、RESTestBench构造及评价条件。其他条目的描述限于已读摘要和相关正文信息。没有以未读实验表构造数值排名。题录由arXiv页面citation元数据提取，15条arXiv加3条经典作者来源，共18条；题名采用实际页面当前版本。

证据审阅复用上一轮冻结产物。核心例子逐条读取需求、生成代码、已有结果及既有参考解释。新报告将需求缺口、存活标签、完整传播分开，最后一项全部保持待验证。当前无第二位独立标注者。

仍需扩展的阅读为近邻论文的完整消融、需求标注可靠性及实验有效性威胁。这限制新颖性判断强度，未据此宣称现有方法已经无法解决本文案例。
