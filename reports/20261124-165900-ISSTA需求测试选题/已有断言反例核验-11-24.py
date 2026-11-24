"""将手工构造的观察值送入冻结测试的原函数体。只执行叶子测试断言。"""

import argparse
import ast
import csv
import hashlib
import json
import tempfile
from collections import Counter
from itertools import permutations
from pathlib import Path
from types import SimpleNamespace


HERE = Path(__file__).resolve().parent
RESULT = Path("results/test-generation-20261114")
TSB = RESULT / "testsuitebench/tasks"
EVAL = Path("reports/20261117-162415-全任务失败分类与比例统计/TSB分类输入快照-11-17.json")
BUSINESS = Path("reports/business-behavior-gap-20261116")
REQ = Path("reports/pass-nonkill-20261116/evidence")
AST_GREP = "ast-grep__ast-grep.dde0fe0"
GRON = "tomnomnom__gron.88a6234"
ZOXIDE = "ajeetdsouza__zoxide.67ca1bc"
ORDER_KEY = "0af839eba15d14e2da1b"
HEADER_KEY = "676d56c1c72dc4237805"
AST_FN = "test_run_context_and_files_with_matches"
GRON_FN = "test_no_sort_retains_parent_before_children"
DOC_FN = "then_document_inner_content_in_document_order"


def locate_repo():
    for parent in HERE.parents:
        for path in (parent, parent / "publication/work2repro"):
            if (path / EVAL).is_file():
                return path
    raise FileNotFoundError("请用 --root 指定包含原始复现资料的仓库")


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_leaf(source, name, bindings):
    module = ast.parse(source.read_text(encoding="utf-8"))
    fn = next(node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == name)
    fn.decorator_list = []  # Behave registration is unnecessary to exercise the original assertion.
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(source), "exec"), bindings)
    return bindings[name]


def accepts(fn, *args):
    try:
        fn(*args)
    except AssertionError:
        return False
    return True


def ast_grep_checks(root):
    source = root / TSB / AST_GREP / "generated/test_cli.py"
    tests = [
        (("a.js", "b.js"), 0), (("b.js", "a.js"), 0),
        (("a.js", "a.js"), 0), (("b.js", "b.js"), 0),
        (("a.js", "c.js"), 0), (("a.js",), 0),
        (("a.js", "b.js", "a.js"), 0), (("a.js", "b.js"), 1),
    ]
    observations = []
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        for file_names, exit_code in tests:
            def invoke(args, cwd):
                # This assertion validates how many paths the frozen test actually passes.
                if cwd != directory or args != ["run", "-p", "foo()", "-l", "js", "--files-with-matches", directory]:
                    raise ValueError("原调用边界变化，需重新审查")
                output = "".join(str(cwd / name) + "\n" for name in file_names)
                return SimpleNamespace(stdout=output, stderr="", returncode=exit_code)

            fn = load_leaf(source, AST_FN, {"invoke": invoke})
            accepted = accepts(fn, directory)
            # All supplied path spellings are canonical and from one temporary directory.
            spec = exit_code == 0 and Counter(file_names) == Counter(["a.js", "b.js"])
            observations.append({
                "paths": list(file_names), "exit_code": exit_code,
                "allowed_by_spec_for_fixture": spec,
                "frozen_assertion_accepts": accepted,
                "one_literally_fixed_order_accepts": exit_code == 0 and file_names == ("a.js", "b.js"),
            })
    return {
        "instance_id": AST_GREP, "function": AST_FN, "actual_cli_path_arguments": 1,
        "observations": observations,
        "context_control": {
            "observable": ["a.js", "a.js"],
            "run_one_query_two_distinct_matching_files_allowed": False,
            "scan_two_rules_both_match_only_a_js_allowed": True,
            "basis": "Public specification lines 82 and 583. The scan control is specification-derived.",
        },
    }


def gron_checks(root):
    source = root / TSB / GRON / "generated/test_cli.py"
    root_line, parent, child, sibling = (
        "json = {};", "json.z = {};", "json.z.child = 1;", "json.a = 2;"
    )
    names = {root_line: "root", parent: "z", child: "z.child", sibling: "a"}
    observations = []
    for lines in permutations(names):
        def run(args, raw_input):
            if args != ["-m", "--no-sort"] or json.loads(raw_input) != {"z": {"child": 1}, "a": 2}:
                raise ValueError("原调用边界变化，需重新审查")
            return SimpleNamespace(returncode=0, stdout=("\n".join(lines) + "\n").encode())

        bindings = {"run": run}
        load_leaf(source, "out", bindings)
        fn = load_leaf(source, GRON_FN, bindings)
        spec = lines[0] == root_line and lines.index(parent) < lines.index(child)
        observations.append({
            "order": [names[line] for line in lines],
            "allowed_by_spec_for_fixture": spec, "frozen_assertion_accepts": accepts(fn),
        })
    return {"instance_id": GRON, "function": GRON_FN, "observations": observations}


def doc_order_checks(root):
    source = root / RESULT / "req2test" / "tasks" / ORDER_KEY / "generated/features/steps/blk_iter_inner_content.py"

    class Table:
        def __init__(self, tag):
            self.tag = tag

    class Paragraph:
        def __init__(self, text):
            self.text = text

    paragraphs = [Paragraph(text) for text in (
        "Lorem ipsum dolor sit amet, consectetur adipiscing elit.",
        "Donec semper facilisis metus finibus malesuada.", "",
    )]
    tables = [Table(name) for name in ("A", "B", "C")]
    fn = load_leaf(source, DOC_FN, {"Table": Table, "Paragraph": Paragraph})

    def run(table_order, paragraph_order):
        items = [item for pair in zip(table_order, paragraph_order) for item in pair]
        document = SimpleNamespace(iter_inner_content=lambda: iter(items))
        return accepts(fn, SimpleNamespace(document=document))

    permutations_seen = []
    for order in permutations(tables):
        permutations_seen.append({
            "table_order": [t.tag for t in order],
            "allowed_by_spec_for_fixture": list(order) == tables,
            "frozen_assertion_accepts": run(order, paragraphs),
        })
    return {
        "instance_id": "python-docx/features/blk-iter-inner-content.feature:7", "function": DOC_FN,
        "observations": permutations_seen,
        "swapped_first_two_different_paragraphs_control": {
            "allowed_by_spec_for_fixture": False,
            "frozen_assertion_accepts": run(tables, [paragraphs[1], paragraphs[0], paragraphs[2]]),
        },
    }


def archived_checks(root):
    snapshots = {r["instance_id"]: r for r in read(root / EVAL)}
    archive = {}
    for task_id, test_name in ((AST_GREP, AST_FN), (GRON, GRON_FN), (ZOXIDE, "test_usage_errors_are_status_two[bad-score]")):
        trials = snapshots[task_id]["top_keys"]["ground_truth_trials"]
        name = "test_cli." + test_name
        archive[task_id] = {
            "test_name": name,
            "reference_trials": [next(r["status"] for r in trial["test_results"] if r["name"] == name) for trial in trials],
        }
    eval_dir = root / BUSINESS / "cases/01"
    raw = read(eval_dir / "official-test-eval.json")
    stable = set.intersection(*(
        {r["name"] for r in trial["test_results"] if r["status"] == "passed"} for trial in raw["ground_truth_trials"]
    ))
    selected = {r["id"]: r for r in read(eval_dir / "mutant-selection.json")["selected"]}
    for binary in raw["binary_results"]:
        mutant = binary["binary_id"]
        if mutant in {"repo_1", "repo_2"}:
            archive[ZOXIDE][mutant] = {
                "assignment_id": selected[mutant]["assignment_id"],
                "failing_valid_tests": [
                    r["name"] for r in binary["test_results"] if r["name"] in stable and r["status"] != "passed"
                ],
            }
    for case in (HEADER_KEY, ORDER_KEY):
        evidence = root / REQ / case
        metric = read(evidence / "metrics.json")
        decisions = read(evidence / "mutation-results.json")
        archive[metric["instance_id"]] = {
            "candidate": metric["outcome"], "n_scored": metric["n_scored"], "n_killed": metric["n_killed"],
            "unique_raw_mutant_ids": len({r["mutant_id"] for r in decisions}),
        }
    hdr = "python-docx/features/doc-add-section.feature:16"
    with (root / BUSINESS / "MUTANT_LEVEL_EVIDENCE.csv").open(encoding="utf-8", newline="") as f:
        row = next(r for r in csv.DictReader(f) if r["instance_id"] == hdr)
    archive[hdr]["one_survivor"] = {k: row[k] for k in (
        "mutant_id", "file", "line", "original", "mutated", "gold_outcome", "candidate_outcome",
        "gold_baseline_mutation_start_line_covered", "candidate_baseline_mutation_start_line_covered",
    )}
    paths = [
        TSB / AST_GREP / "generated/test_cli.py", TSB / GRON / "generated/test_cli.py",
        RESULT / "req2test/tasks" / ORDER_KEY / "generated/features/steps/blk_iter_inner_content.py",
    ]
    return archive, {str(path): hashlib.sha256((root / path).read_bytes()).hexdigest() for path in paths}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = args.root or locate_repo()
    archive, hashes = archived_checks(root)
    probes = [ast_grep_checks(root), gron_checks(root), doc_order_checks(root)]
    for probe in probes:
        totals = Counter((row["allowed_by_spec_for_fixture"], row["frozen_assertion_accepts"]) for row in probe["observations"])
        probe["counts"] = {
            "legal_accepted": totals[True, True], "legal_rejected": totals[True, False],
            "illegal_accepted": totals[False, True], "illegal_rejected": totals[False, False],
        }
    result = {
        "scope": "Local replay of unmodified generated assertion bodies on synthetic outputs. No target program, model or benchmark runner was executed.",
        "generated_source_sha256": hashes, "probes": probes, "frozen_official_evidence": archive,
    }
    out = HERE / "已有断言反例结果-11-24.json"
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.check:
        assert out.read_text(encoding="utf-8") == rendered
    else:
        out.write_text(rendered, encoding="utf-8")
    for probe in probes:
        print(probe["instance_id"], probe["counts"])


if __name__ == "__main__":
    main()
