# 分析输入

`prbench.json` 包含 571 条 Java 样本，`updates4j.json` 包含 195 条 Java 样本。

每条保存本次分析需要的前后版本、测试路径、旧测试、开发者参考测试和被测方法。字段 `sample_id` 用于与 `results/per-sample.csv` 和各方法输出关联。

- `aCommit` 和 `bCommit` 分别是变化后、变化前提交。
- `aSource.code` 是开发者更新后的参考测试，`bSource.code` 是旧测试。
- `focal_method` 保存被测方法、源码位置及前后代码。
- `index` 是本次运行中项目内的零基样本序号。

这些是本次复现与分析用的适配输入。原始数据及数据挖掘方法可在 MuMuTestUp、TestUpdater 作者仓库查阅。
