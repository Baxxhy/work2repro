"""在已发布复现资料上复核计数，默认写本目录，--check 只比较结果。"""

import argparse
import csv
import json
import math
import re
from collections import Counter
from pathlib import Path
from statistics import mean


HERE = Path(__file__).resolve().parent
DATA = Path("data/test-generation-20261114")
RESULT = Path("results/test-generation-20261114")
FINAL = Path("reports/20261120-161942-Req2Test最终结算")
REVIEW = Path("reports/20261116-091532-全案例比例复核")
BUSINESS = Path("reports/20261116-100400-全量复核与三项痛点")
VIEW = Path("reports/20261117-103800-两个Benchmark输入可见性核对")
PAIR = Path("reports/20261123-102902-Symfony装配与八项目环境核验")
QUEUE = Path("reports/20261123-172610-Medium断网任务恢复")


def locate_repo():
    for parent in HERE.parents:
        for root in (parent, parent / "publication/work2repro"):
            if (root / FINAL / "逐任务指标-11-20.jsonl").is_file():
                return root
    raise FileNotFoundError("请在完整档案仓库运行，或使用 --root 指定仓库")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def jsonl_rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def csv_rows(path):
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def unique(rows, field="instance_id"):
    keys = {r[field] for r in rows}
    assert len(keys) == len(rows)
    return keys


def count_values(rows, field):
    return dict(sorted(Counter(r[field] for r in rows).items()))


def audited_tsb(root):
    rows = csv_rows(root / RESULT / "reports/tsb-per-task.csv")
    task_ids = unique(rows)
    assert len({i.rsplit(".", 1)[0] for i in task_ids}) == len(rows)
    summary = read_json(root / RESULT / "reports/tsb-official-summary.json")
    validity = [float(r["validity_rate"]) for r in rows]
    mutation = [float(r["mutation_score"]) for r in rows]
    assert math.isclose(mean(validity), summary["average_validity_rate"])
    assert math.isclose(mean(mutation), summary["average_mutation_score"])
    assert len(rows) == summary["validity_denominator"] == summary["mutation_denominator"]
    views = read_json(root / VIEW / "TSB生成视图记录-11-17.json")
    assert unique(views, "id") == task_ids
    info = [r["metadata"]["info"] for r in views]
    spec_prompts = sum(
        "The workspace contains a program specification." in r["codex_shell_command"]
        and r["image"].endswith(":task_cleanroom_codex") for r in info
    )
    return {
        "tasks_and_unique_repositories": len(rows),
        "mean_validity": mean(validity),
        "mean_mutation_score": mean(mutation),
        "validity_ge_80pct": sum(v >= .8 for v in validity),
        "validity_ge_80pct_and_mutation_le_25pct": sum(
            v >= .8 and m <= .25 for v, m in zip(validity, mutation)
        ),
        "zero_validity": validity.count(0),
        "zero_mutation": mutation.count(0),
        "same_tasks_zero_validity_and_mutation": sum(
            v == m == 0 for v, m in zip(validity, mutation)
        ),
        "cleanroom_and_spec_prompt_metadata": spec_prompts,
    }


def audited_final(root):
    rows = jsonl_rows(root / FINAL / "逐任务指标-11-20.jsonl")
    all_ids = unique(rows)
    summary = read_json(root / FINAL / "summary.json")
    excluded = set(summary["population"]["excluded"])
    assert excluded <= all_ids and all(r["view"] == "th" for r in rows)
    population = [r for r in rows if r["instance_id"] not in excluded]
    projects = {}
    for project in sorted({r["project"] for r in population}):
        group = [r for r in population if r["project"] == project]
        eligible = [r for r in group if not r["exclusion"]]
        passed = [r for r in eligible if r["passed"]]
        complete = sum(r["kill_complete"] for r in passed)
        assert all(r["mutation_status"] == "scored" for r in passed)
        assert all(r["recall"] is None for r in eligible if not r["passed"])
        row = {
            "population": len(group),
            "pass_and_recall_denominator": len(eligible),
            "pass": len(passed),
            "complete": complete,
            "pass_incomplete": len(passed) - complete,
            "pass_at_1": len(passed) / len(eligible),
            "mutation_recall": sum(r["recall"] for r in passed) / len(eligible),
            "kill_complete_at_1": complete / len(group),
        }
        official = summary["modes"]["leaderboard"]["cells"][project + "/th"]
        for name in ("pass_at_1", "kill_complete_at_1", "mutation_recall"):
            assert math.isclose(row[name], official[name])
        projects[project] = row
    macro = {
        k: mean(r[k] for r in projects.values())
        for k in ("pass_at_1", "kill_complete_at_1", "mutation_recall")
    }
    for k, value in macro.items():
        assert math.isclose(value, summary["modes"]["leaderboard"]["mean"]["th"][k]["value"])
    replacements = {
        r["id"]
        for name in ("限流中断任务-11-18.json", "历史启动异常任务-11-18.json")
        for r in read_json(root / FINAL / name) if r.get("kind") != "unresolved"
    }
    return {
        "queued_unique": len(rows),
        "outside_population": len(excluded),
        "population": len(population),
        "pass_and_recall_denominator_sum": sum(r["pass_and_recall_denominator"] for r in projects.values()),
        "exclusion_by_kind_in_population": count_values([r for r in population if r["exclusion"]], "exclusion"),
        "outcomes_in_population": count_values(population, "outcome"),
        "passed": sum(r["pass"] for r in projects.values()),
        "kill_complete": sum(r["complete"] for r in projects.values()),
        "passed_incomplete": sum(r["pass_incomplete"] for r in projects.values()),
        "replaced_generation_interruptions": len(replacements),
        "passed_after_replacement": sum(r["passed"] for r in rows if r["instance_id"] in replacements),
        "leaderboard_project_macro": macro,
        "projects": projects,
    }


def audited_subset(root):
    rows = jsonl_rows(root / RESULT / "reports/req2test-per-task.jsonl")
    view_rows = jsonl_rows(root / DATA / "req2test-tasks.jsonl")
    assert unique(view_rows) == unique(rows) and all(r["view"] == "th" for r in view_rows)
    excluded = read_json(root / RESULT / "reports/req2test-denominators-and-exclusions.json")["official_population"]["excluded"]
    eligible = [r for r in rows if r["instance_id"] not in excluded]
    passed = [r for r in eligible if r["passed"]]
    reviewed = csv_rows(root / REVIEW / "44条通过任务逐项复核-11-16.csv")
    business = csv_rows(root / BUSINESS / "八条业务缺口与主机制-11-16.csv")
    assert unique(reviewed) == unique(passed) and unique(business) <= unique(reviewed)
    final = {r["instance_id"]: r for r in jsonl_rows(root / FINAL / "逐任务指标-11-20.jsonl")}
    assert unique(rows) <= final.keys()
    metrics = ("outcome", "n_scored", "n_killed")
    unchanged = sum(all(r[k] == final[r["instance_id"]][k] for k in metrics) for r in rows)
    projects = {}
    for p in sorted({r["project"] for r in rows}):
        projects[p] = {
            "reviewed_pass": sum(r["project"] == p for r in reviewed),
            "business_gap": sum(r["project"] == p for r in business),
        }
    return {
        "fixed": len(rows), "population": len(eligible), "reviewed_pass": len(reviewed),
        "fixed_ids_also_in_nov20_full": len(rows),
        "same_outcome_n_scored_n_killed_as_nov20": unchanged,
        "reviewed_groups": count_values(reviewed, "group"),
        "review_categories": count_values(reviewed, "classification"),
        "business_gaps": len(business),
        "business_gap_group": count_values(business, "group"),
        "project_count_with_business_gap": len({r["project"] for r in business}),
        "projects": projects,
        "business_gap_ids": {r["instance_id"]: r["pain"] for r in business},
    }


def audited_survivors(root):
    pairs = csv_rows(root / "reports/business-behavior-gap-20261116/MUTANT_LEVEL_EVIDENCE.csv")
    scoped = {(r["instance_id"], r["mutant_id"]) for r in pairs}
    assert len(scoped) == len(pairs)
    assert all(r["gold_outcome"] == "killed" and r["candidate_outcome"] == "passed" for r in pairs)
    return {
        "tasks": len({r["instance_id"] for r in pairs}),
        "task_mutant_pairs": len(pairs),
        "project_mutants": len({(r["project"], r["mutant_id"]) for r in pairs}),
        "per_project_pairs": count_values(pairs, "project"),
        "explicit_requirement_support": count_values(pairs, "requirement_relevance"),
        "candidate_baseline_covers_changed_start_line": count_values(pairs, "candidate_baseline_mutation_start_line_covered"),
        "reference_baseline_covers_changed_start_line": count_values(pairs, "gold_baseline_mutation_start_line_covered"),
    }


def audited_pairs(root):
    rows = read_json(root / PAIR / "八十项配对与注册异常交叉统计-11-23.json")["rows"]
    unique(rows, "id")
    eligible = [r for r in rows if not r["population_exclusion"]]
    paired = Counter(("A" if r["A_pass"] else "") + ("B" if r["B_pass"] else "") or "none" for r in eligible)
    discordant = paired["A"] + paired["B"]
    p_exact = 2 * sum(math.comb(discordant, j) for j in range(min(paired["A"], paired["B"]) + 1)) / 2**discordant
    repaired = csv_rows(root / PAIR / "十条装配问题最终对照-11-23.csv")
    controls = csv_rows(root / PAIR / "八项目原始测试环境对照-11-23.csv")
    queue = csv_rows(root / QUEUE / "全量任务-11-23.csv")
    network = read_json(root / QUEUE / "断网恢复清单-11-23.json")
    assert len(set(network)) == len(network) and set(network) <= unique(queue)
    assert unique(repaired) <= unique(controls)
    return {
        "paired": len(rows), "paired_population": len(eligible), "contingency": dict(paired),
        "two_sided_exact_mcnemar_p": p_exact,
        "wiring_diagnoses": len(repaired), "diagnostic_outcomes": count_values(repaired, "diagnostic_final"),
        "original_project_control_outcomes": count_values(controls, "official"),
        "next_queue_manifest_only": len(queue), "network_recovery_manifest_only": len(network),
    }


# Conservative public-text screen. The labels below summarize a manual read of
# the sentence and its surrounding specification. Exact hits must still agree.
ORDER = re.compile(
    r"\b(?:order(?:ing)?|sequence)\b[^.\n;:]{0,44}?\b"
    r"(?:may vary|may differ|can vary|can differ|need not be stable|"
    r"(?:is|are) (?:unspecified|undefined|nondeterministic|non-deterministic|arbitrary|unstable|irrelevant|immaterial|unimportant)|"
    r"(?:is|are) not (?:guaranteed|specified|significant|semantically significant|fixed|stable|required|prescribed)|does not matter)\b",
    re.IGNORECASE,
)
ORDER_LABELS = {
    "alecthomas__chroma.8d04def": ("output", "不可序列化的各 lexer 各有一条告警，先后可变"),
    "ast-grep__ast-grep.dde0fe0": ("output", "跨文件结果顺序可变，各文件仍须按查询语义输出"),
    "boyter__scc.515f91c": ("output", "按数值排序的 JSON 文件数组允许换序，仍需按文件核对数据"),
    "burntsushi__ripgrep.3b7fd44": ("output", "默认输出允许换序，显式按路径排序后另有要求"),
    "cweill__gotests.2a672c5": ("output", "不同文件间输出允许交换，同一文件的输出仍须连续"),
    "direnv__direnv.02040c7": ("output", "导出的环境变量语句允许换序，绑定的变量和值须正确"),
    "hush-shell__hush.560c33a": ("output", "字典的迭代和显示顺序未规定"),
    "ismaelgv__rnr.fc0733b": ("output", "相同深度无依赖的操作允许换序，有依赖的操作和深度另受约束"),
    "jhspetersson__fselect.c3559ca": ("output", "可用函数列表要求成员齐全，允许换序"),
    "multiprocessio__dsq.c3ae0ba": ("output", "JSON 对象键序可变，结果行顺序服从 SQL"),
    "noborus__trdsql.d8c5ff6": ("output", "列举配置数据库时每个数据库一行，允许换序"),
    "oppiliappan__eva.41ae245": ("output", "计算器帮助各组内允许换序，组标题和空行仍有布局要求"),
    "segmentio__chamber.5f93f5f": ("output", "标签表行顺序可变，键值对应关系不变"),
    "sharkdp__fd.40d8eb3": ("parallel_or_callback", "限于明确并行的功能或调用下游程序时传递的批量参数，普通目录输出规定顺序"),
    "stranger6667__jsonschema.d52e881": ("input_equality", "JSON 输入对象键序不影响深度相等，数组顺序影响判定"),
    "tomnomnom__gron.88a6234": ("output", "关闭排序后对象成员允许换序，根、父子、流记录次序仍受约束"),
}


def screen(root):
    all_specs = sorted((root / DATA / "testsuitebench-specifications").glob("*/spec.md"))
    rows = []
    for spec in all_specs:
        lines = [n for n, line in enumerate(spec.read_text(encoding="utf-8").splitlines(), 1) if ORDER.search(line)]
        if lines:
            task_id = spec.parent.name
            kind, detail = ORDER_LABELS[task_id]
            rows.append({"instance_id": task_id, "spec_lines": lines, "kind": kind, "中文判读": detail})
    assert unique(rows) == set(ORDER_LABELS)
    return {"public_specs": len(all_specs), "matched_projects": len(rows), "labels": count_values(rows, "kind"), "matches": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = args.root or locate_repo()
    result = {
        "testsuitebench": audited_tsb(root),
        "req2test_final_2026_11_20": audited_final(root),
        "req2test_fixed_160": audited_subset(root),
        "req2test_fixed_surviving_pairs": audited_survivors(root),
        "paired_80_and_later_queue": audited_pairs(root),
        "public_text_order_screen": screen(root),
    }
    output = HERE / "逐任务复算结果-11-24.json"
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.check:
        assert output.read_text(encoding="utf-8") == rendered
    else:
        output.write_text(rendered, encoding="utf-8")
    print(f"{output.name} 已核对")


if __name__ == "__main__":
    main()
