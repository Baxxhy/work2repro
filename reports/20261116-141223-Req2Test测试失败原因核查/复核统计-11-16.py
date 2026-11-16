"""Recompute counts from the frozen evidence without running any benchmark."""
from pathlib import Path
from collections import Counter
import csv
import hashlib
import json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
summary = json.loads((HERE / "统计与口径-11-16.json").read_text())
rows = list(csv.DictReader((HERE / "逐任务失败原因-11-16.csv").open()))
assert len(rows) == len({row["instance_id"] for row in rows}) == 160
comparisons = set(summary["compared_ids"])
counts = Counter()
verified_files = 0
for row in rows:
    evidence = json.loads((HERE / row["evidence_file"]).read_text())
    assert evidence["item_id"] == row["instance_id"]
    assert evidence["official_result"]["engine_outcome"] == evidence["outcome"]
    if row["scored"] == "True":
        counts[row["observed_category"]] += 1
    if evidence["outcome"] == "failed" and not evidence["population_exclusion"]:
        assert row["observed_category"] == ("检查结果不符" if row["instance_id"] in comparisons else "步骤运行异常")
        assert any(step.get("error") for step in evidence["per_step"])
    for item in evidence["generated_files"]:
        file = ROOT / "results/test-generation-20261114/req2test/tasks" / row["artifact_id"] / "generated" / item["path"]
        assert hashlib.sha256(file.read_bytes()).hexdigest() == item["sha256"], file
        verified_files += 1
assert dict(counts) == summary["categories"]
assert sum(counts.values()) == 159
assert counts["通过"] == 44
assert sum(counts.values()) - counts["通过"] == 115
for name, expected in summary["source_sha256"].items():
    assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected
print(json.dumps({"tasks": len(rows), "scored": 159, "failed": 115, "categories": counts, "generated_files_sha256_verified": verified_files}, ensure_ascii=False, indent=2))
