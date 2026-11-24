"""按文章给出的三个文件位置下载后，可离线复核公开数据的数量与分布。"""
import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path, PurePosixPath
from zipfile import ZipFile


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def webtest_stats(path):
    with ZipFile(path) as archive:
        cases, errors = set(), set()
        for entry in archive.namelist():
            parts = PurePosixPath(entry).parts
            if len(parts) != 4:
                continue
            _, project, folder, name = parts
            name = PurePosixPath(name)
            if folder == "test_cases" and name.suffix == ".yaml":
                cases.add((project, name.stem))
            if folder == "bugs" and name.suffix == ".js":
                errors.add((project, name.stem))
    return {
        "ZIP_SHA256": digest(path),
        "需求数": len(cases),
        "错误数": len(errors),
        "对应项目和文件名匹配的对数": len(cases & errors),
        "逐项目配对数量": dict(sorted(Counter(p for p, _ in cases & errors).items())),
    }


def e2edev_stats(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    by_req = Counter((r["id"], r["req_id"]) for r in rows)
    project_counts = Counter(r["id"] for r in rows)
    distinct_tests = {(r["id"], r["req_id"], r["test_id"]) for r in rows}
    paired = sum(bool(r["excutable_test_test_case"].strip() and
                      r["excutable_test_step_code"].strip()) for r in rows)
    return {
        "CSV_SHA256": digest(path),
        "数据行": len(rows),
        "项目数": len(project_counts),
        "独立需求数": len(by_req),
        "独立场景数": len(distinct_tests),
        "场景和步骤代码同时非空的数据行": paired,
        "按每条需求的场景数量分布": dict(sorted(Counter(by_req.values()).items())),
        "包含多个场景的需求数": sum(n > 1 for n in by_req.values()),
        "逐项目场景数": dict(sorted(project_counts.items())),
    }


def tdd_stats(path):
    issues = [line for line in path.read_text().splitlines() if line.strip()]
    repo_counts = Counter()
    for issue in issues:
        match = re.fullmatch(r"(.+__.+)-(\d+)", issue)
        if not match:
            raise ValueError(f"无效任务标识 {issue!r}")
        repo_counts[match.group(1)] += 1
    return {
        "清单_SHA256": digest(path),
        "任务行数": len(issues),
        "唯一任务数": len(set(issues)),
        "仓库数": len(repo_counts),
        "各仓库任务数": dict(repo_counts.most_common()),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("webtest_zip", type=Path)
    parser.add_argument("e2edev_csv", type=Path)
    parser.add_argument("tdd_ids", type=Path)
    files = parser.parse_args()
    results = {
        "WebTestPilot": webtest_stats(files.webtest_zip),
        "E2EDev": e2edev_stats(files.e2edev_csv),
        "TDD-Bench-Verified": tdd_stats(files.tdd_ids),
    }
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
