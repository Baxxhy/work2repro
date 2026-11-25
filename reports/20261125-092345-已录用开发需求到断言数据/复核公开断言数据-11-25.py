"""按公开题目 ID 复核清单。输入文件来源见同目录报告。"""

import argparse
import csv
import hashlib
import json
import re
import zipfile
from collections import Counter
from pathlib import Path


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.DictReader(file))


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect(source, previous_selection, output):
    entries = []
    evidence = {}
    expecto = read_csv(source / "expecto_ids.csv")
    assert len({(row["benchmark"], row["target_id"]) for row in expecto}) == len(expecto)
    counts = Counter(row["benchmark"] for row in expecto)
    assert counts == {"humaneval_plus": 164, "apps": 127, "defects4j": 501}
    for row in expecto:
        group = row["benchmark"]
        if group in {"humaneval_plus", "apps"}:
            entries.append(("Expecto", group, row["target_id"], "函数需求" if group == "humaneval_plus" else "编程题扩展"))
    evidence["Expecto"] = {"公开可选ID的分组": dict(counts), "清单SHA256": sha256(source / "expecto_ids.csv")}

    pbt = read_json(source / "pbt_meta.json")
    paths = {row["rfilename"] for row in pbt["siblings"]}
    problem = re.compile(r"libraries/([^/]+)/problems/([^/]+)/problem\.yaml")
    tasks = sorted(match.groups() for path in paths if (match := problem.fullmatch(path)))
    assert len({task_id for _, task_id in tasks}) == len(tasks)
    per_library = Counter(library for library, _ in tasks)
    bugs = read_csv(source / "pbt_bug_metadata.csv")
    included_bugs = 0
    for library, task_id in tasks:
        base = f"libraries/{library}/problems/{task_id}/"
        assert base + "ground_truth/pbt_test.py" in paths
        bug_ids = {r["bug_id"] for r in bugs if r["problem_id"] == task_id}
        patches = {p.removeprefix(base).removesuffix(".patch") for p in paths
                   if p.startswith(base) and re.fullmatch(r"bug_\d+\.patch", p.removeprefix(base))}
        assert patches == bug_ids and patches
        included_bugs += len(bug_ids)
        entries.append(("PBT-Bench", library, task_id, f"{len(bug_ids)} 个错误版本"))
    assert (len(tasks), len(per_library), included_bugs) == (100, 40, 365)
    evidence["PBT-Bench"] = {"版本": pbt["sha"], "任务": len(tasks), "库内任务数": dict(sorted(per_library.items())),
                             "入选任务的独立错误补丁": included_bugs, "全库元数据行数": len(bugs)}

    for dataset, name, expected in [("Doc2Feat-Verified", "Doc2Feat-Bench Verified", 55), ("DevEval", "DevEval Task 4", 20)]:
        rows = [row for row in read_csv(previous_selection) if row["数据集"] == dataset]
        chosen = [row for row in rows if row["本轮选择"] == "入选"]
        assert len(chosen) == expected and len({row["条目标识"] for row in chosen}) == expected
        for row in chosen:
            entries.append((name, row["项目"], row["条目标识"], row["参考材料"]))
        group = Counter(row["项目"] if dataset == "Doc2Feat-Verified" else row["项目"].split("/")[0] for row in chosen)
        evidence[name] = {"已审": len(rows), "选用": expected, "分布": dict(sorted(group.items()))}

    archive = source / "reqtestagent.zip"
    with zipfile.ZipFile(archive) as zfile:
        study_file = next(name for name in zfile.namelist() if name.endswith("/data/study/study100.jsonl"))
        with zfile.open(study_file) as stream:
            study = [json.loads(line) for line in stream if line.strip()]
    variants = Counter(row["task_id"] for row in study)
    kinds = Counter(row["ambiguity_type"] for row in study)
    assert len(variants) == 25 and set(variants.values()) == {4}
    assert len(kinds) == 4 and set(kinds.values()) == {25}
    for row in study:
        entries.append(("Orchid-BCB × ReqTestAgent", row["task_id"], row["instance_id"], row["ambiguity_type"]))
    evidence["ReqTestAgent"] = {"独立功能": len(variants), "四种需求变体": dict(sorted(kinds.items())),
                               "作者附件SHA256": sha256(archive)}

    assert len(entries) == len({r[:3] for r in entries})
    with (output / "已核对的公开样本标识-11-25.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(["数据", "项目或来源", "样本标识", "单位、用途或原始入口"])
        writer.writerows(sorted(entries))
    (output / "分组计数与校验-11-25.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="包含公开清单与期刊附件的目录")
    parser.add_argument("previous_selection", type=Path, help="Doc2Feat 与 DevEval 的逐项筛选 CSV")
    parser.add_argument("output", type=Path, help="存放新清单的现有目录")
    args = parser.parse_args()
    inspect(args.source, args.previous_selection, args.output)
