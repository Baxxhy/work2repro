# 与首选问题直接相邻的 ISSTA 论文

北京时间 2026-11-24。以下四项均列在 ISSTA 2026 research papers。下表的“可以接着问”是本研究判断。可见条件差别很大，论文数字各用自己的数据和分母。[官方议程](https://conf.researchr.org/track/issta-2026/issta-2026-research-papers)

|工作|作者已经解决到哪一步|可以接着问什么|
|---|---|---|
|Du、Palepu、Jones，How Does Killing Surviving Mutants Help Detect Real Bugs with Assertion Generation?|冻结已有测试输入，只增加断言，把每次补强和真实缺陷配对。在 642 个 Defects4J 缺陷中，104 个可通过为已有通过测试新增断言暴露，63 个可通过论文的变异驱动补强检出。|最有价值的借鉴是用独立缺陷验证修改的收益。我们的生成器只能看到规格或隐藏目标的项目，能否仅用需求所给的关系找出值得修改的原断言？[作者页](https://spideruci.org/publication/du-killing-2026/)|
|Yang、Chen，SeGa，Uncovering Business Logic Bugs via Semantics-Driven Unit Test Generation，经验论文|从产品需求构建知识库，结合目标方法，抽取准备、操作、期望和语义约束。四个工业 Go 项目覆盖 60 个业务缺陷，另在六个生产仓库找到 16 个由开发者确认并修复的新问题。|有清晰业务步骤、能发现真实业务错误的需求测试已有工业成果。我们可以研究已生成的断言是否接受了违反某条关系的结果，以及局部诊断对隐藏错误有无预测力。[作者论文](https://arxiv.org/abs/2604.23509)|
|Chang 等，AdverTest，Test vs Mutant|由两个智能体分别写测试、造变异，使用覆盖与变异反馈迭代，在 Defects4J 评估。|对抗和多智能体本身已有直接先例。比较时给两边相同的可见信息，测局部反馈与等预算自建替代实现各能捕捉什么错误。[会议](https://conf.researchr.org/details/issta-2026/issta-2026-research-papers/31/Test-vs-Mutant-Adversarial-LLM-Agents-for-Robust-Unit-Test-Generation)|
|Cao 等，STARS|从程序静态分析提取可能的断言组件，再由模型组合、排序和完善，能找到单靠局部文本难推断的调用序列。作者报告其比较中的变异分数为 10.97% 和 3.97%。|这项工作可帮助找到可以读取的状态。还须判断对这个业务需求究竟该保留哪种关系，以及加强后会不会拒绝另一个同样合法的结果。[作者机构](https://cispa.de/en/research/publications/213588-stars-static-analysis-guided-assertion-synthesis-using-large-language-models)|

更早的 OASIs 已经把错放与误拒纳入同一套断言评估，使用 Java 程序、搜索、变异及人工判断。AGORA 直接在 API 返回值中注错来评判断言。这两项工作界定了“测试断言本身”这条路线的历史起点。若我们的程序只按固定模板打乱输出，再补强到能抓住自己造的错，贡献会很有限。[OASIs](https://ai.meta.com/research/publications/oasis-oracle-assessment-and-improvement-tool/) · [AGORA](https://www.javalenzuela.com/publication/2023_issta_agora/2023_issta_agora.pdf)
