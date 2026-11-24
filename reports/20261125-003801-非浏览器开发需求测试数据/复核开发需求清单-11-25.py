"""用作者固定版本的三份公开数据生成逐项选型清单。参数依次见说明文档。"""
import argparse
import ast
import csv
import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import quote

DEV = "https://github.com/open-compass/DevEval/blob/bb593c1f9c535ff0dde0c9f4807d58c9566c3a6c/benchmark_data/"
DOC = "https://huggingface.co/datasets/Doc2Feat-bench/Doc2Feat-bench_Verified/blob/b162f36089eae2ff9e3501cd2afa00f202ebb7f5/test/data.jsonl"
CLASS = "https://github.com/FudanSELab/ClassEval/blob/eaeac44d0d5dcd8a95feec50726d66fedc73a98f/data/ClassEval_data.json"
LIBS_TOOLS = {"astropy/astropy", "pydata/xarray", "scikit-learn/scikit-learn",
              "pylint-dev/pylint", "pytest-dev/pytest"}
PRESENTATION = {"pydata__xarray-5126", "pydata__xarray-7052",
                "astropy__astropy-9266", "astropy__astropy-11843"}
WEB_PROJECTS = {"javascript/listen-now-frontend", "javascript/login-registration"}
BROWSER_DRIVERS = re.compile(
    r"selenium|webdriver|playwright|webbrowser|puppeteer|chromedriver|geckodriver|phantomjs",
    re.IGNORECASE,
)
COLUMNS = ["数据集", "项目", "条目标识", "本轮选择", "需求或数据入口", "参考材料", "核对内容"]


def dev_rows(root):
    for conf in sorted(root.glob("*/*/repo_config.json")):
        record = json.loads(conf.read_text())
        project_dir = conf.parent
        project = project_dir.relative_to(root).as_posix()
        prd = project_dir / record["PRD"]
        if not prd.is_file():
            raise ValueError(f"缺少 PRD {prd}")
        names = list(record["coarse_acceptance_test_prompt"])
        tests = [n for n in names if (project_dir / n).is_file()]
        if not tests:
            raise ValueError(f"缺少可核对的参考验收入口 {project}")
        selected = project not in WEB_PROJECTS
        if selected:
            sources = "\n".join((project_dir / n).read_text(errors="replace") for n in tests)
            if BROWSER_DRIVERS.search(sources + "\n" + record["acceptance_test_script"]):
                raise ValueError(f"需复核浏览器依赖 {project}")
        yield ["DevEval", project, project, "入选" if selected else "排除网页前端",
               DEV + quote(prd.relative_to(root).as_posix()), DEV + quote(project + "/" + tests[0]),
               " | ".join(tests)]


def doc_rows(path):
    with path.open() as stream:
        for line in stream:
            task = json.loads(line)
            ident = task["instance_id"]
            if not all(task.get(k) for k in ("doc_changes", "test_patch", "FAIL2PASS", "feature_patch")):
                raise ValueError(f"缺少功能评测字段 {ident}")
            selected = task["repo"] in LIBS_TOOLS and ident not in PRESENTATION
            if selected and BROWSER_DRIVERS.search(task["test_patch"] + " " + " ".join(task["FAIL2PASS"])):
                raise ValueError(f"需复核选中条目的测试入口 {ident}")
            test_files = re.findall(r"^diff --git a/.+? b/(.+)$", task["test_patch"], re.M)
            yield ["Doc2Feat-Verified", task["repo"], ident, "入选" if selected else "未列入首批",
                   DOC, task["html_url"], " | ".join(test_files)]


def class_rows(path):
    for task in json.loads(path.read_text()):
        if not (task["skeleton"] and task["methods_info"] and task["test"]):
            raise ValueError(f"缺少类规格或测试 {task['task_id']}")
        ast.parse(task["test"])
        if BROWSER_DRIVERS.search(task["test"]):
            raise ValueError(f"需复核参考测试 {task['task_id']}")
        yield ["ClassEval", task["class_name"], task["task_id"], "入选", CLASS, CLASS,
               "、".join(m["method_name"] for m in task["methods_info"])]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("deveval_benchmark_data", type=Path)
    parser.add_argument("doc2feat_jsonl", type=Path)
    parser.add_argument("classeval_json", type=Path)
    parser.add_argument("output_csv", type=Path)
    a = parser.parse_args()
    rows = [*dev_rows(a.deveval_benchmark_data), *doc_rows(a.doc2feat_jsonl), *class_rows(a.classeval_json)]
    with a.output_csv.open("w", encoding="utf-8", newline="") as out:
        writer = csv.writer(out, lineterminator="\n")
        writer.writerow(COLUMNS)
        writer.writerows(rows)
    print(dict(Counter((row[0], row[3]) for row in rows)))


if __name__ == "__main__":
    main()
