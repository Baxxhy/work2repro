# 相关研究阶段性核对

本轮完成低成本初筛，论文全文与具体实验设置的逐项复核仍待进行。以下内容限定于已读取的论文摘要与作者资料。

TestSuiteBench 作者报告规格到应用测试套件的缺陷检出差距，并观察到相关输入组合缺失。该结果支持调查组合覆盖，当前复现还需要具体输入和存活变异体证据。不能直接将作者观察作为本次全部任务的标注。[TestSuiteBench](https://arxiv.org/abs/2610.13065)

Req2Test-Bench 作者报告执行通过与 KillComplete 的差距，并指出准备条件与隐含预期可能存在信息不足。当前 Algorand 和 python-docx 的显式断言案例仍需要逐个解释存活变异体。是否体现同一局限待核实。[Req2Test-Bench](https://arxiv.org/abs/2610.36584)

测试预言问题已有系统综述，判断观察结果是否符合预期属于成熟研究议题。当前需要明确需求信息、准备路径和观察点的具体约束，才能判断现有成果的适用范围。[Barr 等，2015](https://discovery.ucl.ac.uk/id/eprint/1471263/)

EvoSuite 作者资料介绍了覆盖目标与自动断言生成，其生成断言概括已有实现行为。变异驱动测试与预言生成也已有研究。隐藏实现、业务场景接线以及需求给出的预期能否直接由这些技术解决，需进一步研究条件匹配，当前没有足够证据宣称现有方法无法解决。[EvoSuite](https://www.evosuite.org/evosuite/)、[Mutation-driven Generation of Unit Tests and Oracles](https://www.evosuite.org/wp-content/papercite-data/pdf/tse12_mutation.pdf)

研究空间暂保留为待验证问题。当前未完成充分的跨项目语义确认、全部反例分析或现有方法的同任务实验。
