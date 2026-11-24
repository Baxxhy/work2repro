"""Verify the archived evidence summaries from a full work2repro checkout."""
import csv
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote


HERE = Path(__file__).resolve().parent


def read(name):
    return json.loads((HERE / name).read_text(encoding="utf-8"))


def main():
    for name in ["逐任务证据复算-11-24.py", "已有断言反例核验-11-24.py"]:
        subprocess.run([sys.executable, HERE / name, "--check"], check=True)

    fixture = read("原文档表格顺序核验结果-11-24.json")
    assert fixture["second_kit_copy_sha256"] == fixture["fixture_sha256"]
    assert fixture["number_of_distinct_table_contents"] == 3
    rows = fixture["replayed_orders"]
    assert len({tuple(r["table_order"]) for r in rows}) == len(rows) == 6
    assert sum(r["allowed"] for r in rows) == 1 and all(r["frozen_assertion_accepts"] for r in rows)
    cases = read("逐任务复算结果-11-24.json")["req2test_fixed_160"]["business_gap_ids"]
    oracle_ids = [identifier for identifier, label in cases.items() if label == "断言约束"]
    assert len({i.split("/")[0] for i in oracle_ids}) == len(oracle_ids) == 4

    repo = HERE.parent.parent
    if HERE.parent.name == "diagnostics":
        repo = repo / "publication/work2repro"
    original = repo / "results/test-generation-20261114/req2test/tasks/0af839eba15d14e2da1b"
    trace = json.loads((original / "trajectory-excerpt.json").read_text(encoding="utf-8"))
    items = [event["item"] for event in trace["events"] if event["type"] == "item.completed"]
    target = next(item for item in items if "'paras'" in item.get("command", ""))
    raw = next(item for item in items if "from zipfile import ZipFile" in item.get("command", ""))
    assert items.index(target) < items.index(raw)
    assert target["exit_code"] == 1 and "NotImplementedError" in target["aggregated_output"]
    assert raw["exit_code"] == 0 and "word/document.xml" in raw["command"]
    table_lines = [s.rstrip() for s in raw["aggregated_output"].split("sectPr", 1)[0].splitlines()
                   if s.startswith("TABLE")]
    assert table_lines == ["TABLE", "TABLE Text beforeTableBetweenText after", "TABLE"]

    with (HERE / "核心文献索引-11-24.csv").open(encoding="utf-8", newline="") as stream:
        works = list(csv.DictReader(stream))
    assert len({w["来源ID"] for w in works}) == len(works) == 22
    assert all(w["一手来源"].startswith("https://") for w in works)

    checked_links = 0
    for doc in HERE.glob("*.md"):
        local_doc = doc
        if HERE.parent.name == "diagnostics":
            local_doc = HERE.parent.parent / "publication/work2repro/reports" / HERE.name / doc.name
        for href in re.findall(r"\]\(([^)]+)\)", doc.read_text(encoding="utf-8")):
            if href.startswith(("https:", "http:", "#")):
                continue
            target = unquote(href.split("#")[0])
            assert (local_doc.parent / target).is_file(), f"{doc.name} has a missing link {href}"
            checked_links += 1
    print(f"Verified the frozen fixture, its generation-time XML read, four oracle cases across four projects, {len(works)} core sources and {checked_links} file links.")


if __name__ == "__main__":
    main()
