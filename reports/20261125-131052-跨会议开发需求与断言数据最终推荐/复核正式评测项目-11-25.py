"""核验 RepoGenesis 固定版本的评测目录、论文表三与井字棋的末尾断言。"""

import argparse
import ast
import csv
import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path


def key(name):
    return re.sub(r"[^a-z0-9]", "", name.lower())


def table_three(pdf):
    extracted = subprocess.check_output(
        ["pdftotext", "-f", "3", "-l", "3", "-raw", str(pdf), "-"], text=True
    )
    table = extracted.split("Table 3:", 1)[1]
    row = re.compile(r"^(.+?) (Python|Java) (.+?) (\d+) (\d+) (?:-|[.\dk]+) (.+)$")
    total = re.search(r"(?m)^Total 2 9 Stacks (\d+)\s+(\d+)\s+-", table)
    assert total
    values = {}
    for line in table.splitlines():
        result = row.fullmatch(line)
        if result:
            name, _, _, endpoints, tests, _ = result.groups()
            ident = key(name) if name != "UserManagement Lite" else key("UserManagement_2")
            values[ident] = (int(endpoints), int(tests))
    return values, tuple(map(int, total.groups()))


def match_result(check, outcome):
    """只解释固定源码末尾用到的断言表达式。"""
    def value(node):
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.List):
            return [value(item) for item in node.elts]
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id == "data":
            return outcome[value(node.slice)]
        if isinstance(node, ast.Call) and ast.unparse(node.func) == "data.get":
            return outcome.get(value(node.args[0]))
        raise ValueError(ast.dump(node))

    assert isinstance(check, ast.Compare) and len(check.ops) == len(check.comparators) == 1
    left, right = value(check.left), value(check.comparators[0])
    if isinstance(check.ops[0], ast.In):
        return left in right
    if isinstance(check.ops[0], ast.Eq):
        return left == right
    raise ValueError(ast.dump(check))


def replay_game_end(file):
    tree = ast.parse(file.read_text())
    method = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "test_make_moves_and_win")
    moves = next(ast.literal_eval(n.value) for n in method.body if isinstance(n, ast.Assign)
                 and ast.unparse(n.targets[0]) == "moves")
    assert [tuple(m) for m in moves] == [("X", 0, 0), ("O", 1, 0), ("X", 0, 1), ("O", 1, 1), ("X", 0, 2)]
    first, branch = method.body[-2:]
    assert isinstance(first, ast.Assert) and isinstance(branch, ast.If)
    assert len(branch.body) == 1 and isinstance(branch.body[0], ast.Assert) and not branch.orelse
    variants = []
    for status, winner in [("finished", "X"), ("draw", None), ("finished", "O")]:
        outcome = {"status": status, "winner": winner}
        accepts = match_result(first.test, outcome) and (
            not match_result(branch.test, outcome) or match_result(branch.body[0].test, outcome)
        )
        variants.append({**outcome, "原末尾断言放行": accepts})
    assert [item["原末尾断言放行"] for item in variants] == [True, True, False]
    return {"输入的五步落子": moves, "三个判定": variants, "测试文件SHA256": hashlib.sha256(file.read_bytes()).hexdigest()}


def audit(repo, pdf, out):
    metadata = ast.parse((repo / "eval_harness/constants.py").read_text())
    projects = next(ast.literal_eval(n.value) for n in metadata.body if isinstance(n, ast.AnnAssign)
                    and isinstance(n.target, ast.Name) and n.target.id == "REPO_SPECS")
    paper_rows, total = table_three(pdf)
    assert {key(name) for name in projects} == set(paper_rows)
    rows = []
    browser = re.compile(r"\b(selenium|webdriver|playwright|puppeteer|chromedriver|geckodriver|cypress|capybara)\b", re.I)
    for name, spec in sorted(projects.items()):
        lang = spec["lang"]
        input_dir = "repo_readme_verified_python_no_t" if lang == "python" else "repo_readme_verified_java_no_t_with_p"
        readme = Path(input_dir) / name / "README.md"
        test_dir = Path("repo") / name / ("tests" if lang == "python" else "src/test")
        extension = ".py" if lang == "python" else ".java"
        sources = sorted((repo / test_dir).rglob("*" + extension))
        assert (repo / readme).is_file() and sources
        with_driver = [p for p in sources if browser.search(p.read_text(encoding="utf-8-sig"))]
        endpoints, tests = paper_rows[key(name)]
        rows.append((name, lang, endpoints, tests, str(readme), str(test_dir), len(sources), len(with_driver)))
    with (out / "正式评测项目清单-11-25.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(["项目", "语言", "论文项目行API数", "论文项目行测试数", "需求路径", "参考测试目录", "测试与辅助源码文件", "含浏览器驱动标识的文件"])
        writer.writerows(rows)
    summary = {
        "仓库版本": "54a1dd49a51eb12666f7c394f1879c02df5b91b8",
        "正式论文PDF_SHA256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
        "公开项目按语言": dict(Counter(r[1] for r in rows)),
        "已读需求文档数": len(rows),
        "已读测试与辅助源码文件": sum(r[6] for r in rows),
        "浏览器驱动标识命中文件数": sum(r[7] for r in rows),
        "论文表三底行_API与测试": total,
        "论文表三逐行加总_API与测试": [sum(r[2] for r in rows), sum(r[3] for r in rows)],
        "五步连续落子后原测试末尾判定": replay_game_end(repo / "repo/Tic-Tac-Toe/tests/test_game_api.py"),
    }
    (out / "项目计数与断言核验-11-25.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo", type=Path)
    parser.add_argument("paper_pdf", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    audit(args.repo, args.paper_pdf, args.output_dir)
