from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path


CATEGORIES = ("official_pass", "mixed_feature_tests", "other_recorded_failure", "unclassified")
CASES = {
    "django__django-14751": "20250722_agentless_claude-4-sonnet",
    "scikit-learn__scikit-learn-26786": "20250722_agentless_deepseek_r1_0528",
}


def records(path):
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def classify(row):
    feature = row["F2P"]
    regression = row["P2P"]
    for tests in (feature, regression):
        for outcome in ("success", "failure"):
            assert isinstance(tests[outcome], list)
    if row["resolved"] is True:
        return "official_pass"
    assert row["resolved"] is False
    if feature["success"] and feature["failure"]:
        return "mixed_feature_tests"
    if feature["failure"] or regression["failure"]:
        return "other_recorded_failure"
    return "unclassified"


def write_table(path, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0], delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def audit(dataset, submissions, destination):
    tasks = records(dataset)
    metadata = {task["instance_id"]: task for task in tasks}
    assert len(tasks) == len(metadata)
    runs = sorted(submissions.glob("*/evaluation_details.jsonl"))
    assert runs, "expected evaluation/verified/<submission>/evaluation_details.jsonl"
    raw = Counter()
    groups = defaultdict(list)
    examples = {}
    for run in runs:
        rows = records(run)
        ids = [r["instance_id"] for r in rows]
        assert len(set(ids)) == len(ids) and set(ids) <= metadata.keys()
        for row in rows:
            task_id = row["instance_id"]
            raw["records"] += 1
            patch = row.get("model_patch")
            if not isinstance(patch, str) or not patch.strip():
                raw["no_patch_text"] += 1
                continue
            if row.get("applied") is not True:
                raw["patch_not_marked_applied"] += 1
                continue
            group = classify(row)
            raw[group] += 1
            digest = sha(patch)
            groups[(task_id, digest)].append((group, run.parent.name))
            if CASES.get(task_id) == run.parent.name:
                examples[task_id] = {
                    "submission": run.parent.name, "sha256": digest,
                    "status": group, "F2P_success_count": len(row["F2P"]["success"]),
                    "F2P_failure_count": len(row["F2P"]["failure"]),
                    "F2P_success": sorted(row["F2P"]["success"]),
                    "F2P_failure": sorted(row["F2P"]["failure"]),
                }
    task_counts = defaultdict(Counter)
    unique = Counter()
    index = []
    for (task_id, digest), observations in sorted(groups.items()):
        statuses = {s for s, _ in observations}
        status = next(iter(statuses)) if len(statuses) == 1 else "conflict"
        unique[status] += 1
        task_counts[task_id][status] += 1
        index.append({"instance_id": task_id, "sha256": digest, "status": status,
                      "n_submissions": len(observations),
                      "submissions": "|".join(sorted(name for _, name in observations))})

    task_rows = []
    projects = defaultdict(Counter)
    for task_id, meta in sorted(metadata.items()):
        counts = task_counts[task_id]
        any_fail = counts["mixed_feature_tests"] + counts["other_recorded_failure"]
        positive_negative = int(bool(counts["official_pass"] and any_fail))
        positive_mixed = int(bool(counts["official_pass"] and counts["mixed_feature_tests"]))
        row = {"instance_id": task_id, "repo": meta["repo"], "applied_distinct": counts.total(),
               **{k: counts[k] for k in (*CATEGORIES, "conflict")},
               "with_pass_and_failure": positive_negative, "with_pass_and_mixed": positive_mixed,
               "pull_request": meta["html_url"]}
        task_rows.append(row)
        pr = projects[meta["repo"]]
        pr["tasks"] += 1
        for key in ("applied_distinct", *CATEGORIES, "conflict", "with_pass_and_failure", "with_pass_and_mixed"):
            pr[key] += row[key]
    project_rows = [{"repo": name, **dict(counts)} for name, counts in sorted(projects.items())]
    summary = {
        "dataset_sha256": hashlib.sha256(dataset.read_bytes()).hexdigest(),
        "submissions": len(runs), "tasks": len(tasks), "repos": len(projects),
        "possible_records": len(runs) * len(tasks), "raw": dict(raw),
        "distinct_patches_by_task": len(groups), "distinct_labels": dict(unique),
        "tasks_with_applied": sum(bool(r["applied_distinct"]) for r in task_rows),
        "tasks_with_pass_and_failure": sum(r["with_pass_and_failure"] for r in task_rows),
        "tasks_with_pass_and_mixed": sum(r["with_pass_and_mixed"] for r in task_rows),
        "mixed_w_pass_totals": {k: sum(r[k] for r in task_rows if r["with_pass_and_mixed"])
                                for k in ("official_pass", "mixed_feature_tests", "other_recorded_failure")},
        "repos_with_pass_and_mixed": sum(bool(r["with_pass_and_mixed"]) for r in project_rows),
    }
    assert sum(raw[k] for k in CATEGORIES) == sum(r["n_submissions"] for r in index)
    assert len(index) == sum(r["applied_distinct"] for r in task_rows)
    destination.mkdir(parents=True, exist_ok=True)
    write_table(destination / "逐需求候选.tsv", task_rows)
    write_table(destination / "项目分布.tsv", project_rows)
    write_table(destination / "候选版本索引.tsv", index)
    pilot = [
        {"stage": "development" if r["repo"] in {"django/django", "scikit-learn/scikit-learn"} else "reserved",
         **{k: r[k] for k in ("instance_id", "repo", "official_pass", "mixed_feature_tests",
                               "other_recorded_failure", "pull_request")}}
        for r in task_rows if r["with_pass_and_mixed"]
    ]
    write_table(destination / "首轮19条需求.tsv", pilot)
    # Keep the two case witnesses independently locatable without copying source or diffs.
    for task_id, ex in examples.items():
        if task_id == "django__django-14751":
            ex["F2P_success"] = [t for t in ex["F2P_success"] if "scriptable" in t]
    assert examples.keys() == CASES.keys()
    for name, content in (("核验摘要.json", summary), ("两个实例的执行证据.json", examples)):
        (destination / name).write_text(json.dumps(content, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("dataset", type=Path)
    parser.add_argument("submissions", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    audit(args.dataset, args.submissions, args.destination)
