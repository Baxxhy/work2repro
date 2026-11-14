import os
import subprocess
from pathlib import Path

EXE = "/workspace/executable"

def run(*args, cwd=None, timeout=5):
    return subprocess.run([EXE, *map(str, args)], cwd=cwd, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)

def source(tmp_path, text, name="sample.go"):
    p = tmp_path / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p

def check(tmp_path, text, *flags, name="sample.go"):
    p = source(tmp_path, text, name)
    return run("check", *flags, str(p))

def test_no_args_unknown_and_case_sensitive():
    r = run()
    assert (r.returncode, r.stdout, r.stderr) == (0, "", "no args provided")
    r = run("Help")
    assert r.returncode == 0 and '"Help" unknown command, did you mean "help"?' in r.stdout
    assert r.stderr == 'no such command "Help"\n'

def test_help_and_version_exact():
    r = run("version", "ignored")
    assert r.returncode == 0 and r.stdout == "go-critic version: v0.0.0-SNAPSHOT\n\n" and r.stderr == ""
    r = run("help", "ignored")
    assert r.returncode == 0 and "go-critic <command> [arguments...]" in r.stdout and r.stdout.endswith("Version: v0.0.0-SNAPSHOT\n\n")

def test_doc_registry_and_exact_docs():
    r = run("doc")
    assert r.returncode == 0 and r.stderr == ""
    names = [line.split()[0] for line in r.stdout.splitlines() if line and not line.startswith(" ")]
    assert len(names) >= 100 and names[0] == "appendAssign" and names[-1] == "zeroByteRepeat"
    for checker, tag, phrase in [("appendAssign", "[diagnostic]", "Detects suspicious append result assignments."),
                                 ("badRegexp", "[diagnostic experimental]", "Detects suspicious regexp patterns."),
                                 ("builtinShadow", "[style opinionated]", "predeclared identifiers"),
                                 ("rangeExprCopy", "[performance]", "copy big objects")]:
        d = run("doc", checker)
        assert d.returncode == 0 and d.stdout.startswith(f"{checker} checker documentation\nURL: https://github.com/go-critic/go-critic/checkers\nTags: {tag}\n\n")
        assert phrase in d.stdout

def test_doc_argument_errors():
    r = run("doc", "notAName")
    assert r.returncode == 1 and r.stdout == '' and r.stderr == 'checker with name "notAName" not found\n'
    r = run("doc", "a", "b")
    assert r.returncode == 1 and r.stderr == "expected 0 or 1 positional arguments\n"

def test_empty_or_invalid_targets_are_silent(tmp_path):
    (tmp_path / "lonely.go").write_text('package p\nfunc f(){ x:=[]int{}; _=x[:] }\n')
    for args in [("-enable=unslice",), ("missing.go", "lonely.go"), ("",), ("lonely.txt",), (".",), ("./...",)]:
        r = run("check", *args, cwd=tmp_path)
        assert (r.returncode, r.stdout, r.stderr) == (0, "", "")

def test_unslice_and_location_format(tmp_path):
    r = check(tmp_path, 'package p\nfunc f(){ x:=[]int{}; _=x[:] }\n')
    assert r.returncode == 1 and r.stdout == "" and "./sample.go:2:" in r.stderr and "unslice: could simplify x[:] to x" in r.stderr
    r = check(tmp_path, 'package p\nfunc f(){ x:=[]int{}; _=x[:] }\n', "-shorterErrLocation=false")
    assert str(tmp_path / "sample.go") in r.stderr

def test_enable_disable_and_empty_selection(tmp_path):
    code = 'package p\nfunc f(){ x:=1; x=x+1; _=x }\n'
    r = check(tmp_path, code, "-enable=assignOp")
    assert r.returncode == 1 and "assignOp:" in r.stderr and "++" in r.stderr
    r = check(tmp_path, code, "-enable=assignOp", "-disable=assignOp")
    assert r.returncode == 1 and r.stderr == "init checkers: empty checkers set selected\n"
    r = check(tmp_path, code, "-enable=unknown")
    assert r.returncode == 1 and "empty checkers set selected" in r.stderr

def test_assign_op_and_duplicate_expression(tmp_path):
    r = check(tmp_path, 'package p\nfunc f(x int){ x = x + 1; _ = x == x }\n', "-enable=assignOp,dupSubExpr")
    assert r.returncode == 1 and "replace `x = x + 1` with `x++`" in r.stderr
    assert "dupSubExpr: suspicious identical x and x for `==` operator" in r.stderr

def test_bad_condition_and_unslice_can_coexist(tmp_path):
    r = check(tmp_path, 'package p\nfunc f(x int){ _ = x < 3 && x > 10; a:=[]int{}; _=a[:] }\n')
    assert "badCond:" in r.stderr and "condition is always false" in r.stderr and "unslice:" in r.stderr

def test_append_checks(tmp_path):
    r = check(tmp_path, 'package p\nfunc f(){ xs:=[]int{}; ys:=[]int{}; xs=append(ys,1); xs=append(ys,2) }\n', "-enable=appendAssign,appendCombine")
    assert "appendAssign: append result not assigned to the same slice" in r.stderr

def test_flag_and_map_key_diagnostics(tmp_path):
    r = check(tmp_path, 'package p\nimport "flag"\nfunc f(){ _=flag.Bool("-verbose",false,""); _=map[string]int{"bar ":1} }\n', "-enable=flagName,mapKey")
    assert 'flag name "-verbose" should not start with a hyphen' in r.stderr
    assert 'suspicious whitespace in "bar " key' in r.stderr

def test_comment_and_codegen_rules(tmp_path):
    r = check(tmp_path, '// generated file - do not edit\npackage p\n//missing space\nfunc f(){}\n', "-enable=codegenComment,commentFormatting")
    assert "comment should match" in r.stderr and "put a space between" in r.stderr
    r = check(tmp_path, '// Code generated by tool. DO NOT EDIT.\npackage p\n//go:generate echo hi\n', "-enable=codegenComment")
    assert r.returncode == 0 and r.stderr == ""

def test_generated_and_test_file_filters(tmp_path):
    g = source(tmp_path, '// Code generated by tool. DO NOT EDIT.\npackage p\nfunc f(){ x:=[]int{}; _=x[:] }\n', "gen.go")
    r = run("check", "-enable=unslice", str(g))
    assert r.returncode == 0 and r.stderr == ""
    r = run("check", "-enable=unslice", "-checkGenerated", str(g))
    assert "unslice:" in r.stderr
    t = source(tmp_path, 'package p\nfunc f(){ x:=[]int{}; _=x[:] }\n', "sample_test.go")
    assert run("check", "-enable=unslice", "-checkTests=false", str(t)).stderr == ""
    assert "unslice:" in run("check", "-enable=unslice", "-checkTests=true", str(t)).stderr

def test_exit_code_flags_and_verbose(tmp_path):
    p = source(tmp_path, 'package p\nfunc f(){ x:=[]int{}; _=x[:] }\n')
    r = run("check", "-enable=unslice", "-exitCode", "7", str(p))
    assert r.returncode == 7 and "unslice:" in r.stderr
    r = run("check", "-enable=unslice", "-exitCode=0", str(p))
    assert r.returncode == 0 and "unslice:" in r.stderr
    r = run("check", "-v", str(p))
    assert r.returncode == 1 and "debug: unslice is enabled" in r.stderr and "checking \"command-line-arguments\" package (1 files)" in r.stderr

def test_style_transformations(tmp_path):
    r = check(tmp_path, 'package p\nfunc f(){ a:=1; b:=2; tmp:=a; a=b; b=tmp; _=a }\n', "-enable=valSwap")
    assert "can re-write as `a, b = b, a`" in r.stderr
    r = check(tmp_path, 'package p\nfunc f(){ _ = *new(int); _ = (*new(int)) }\n', "-enable=newDeref")
    assert "replace `*new(int)` with `0`" in r.stderr

def test_performance_thresholds(tmp_path):
    code = 'package p\ntype Big [16]int\nfunc f(x Big){ a:= [64]int{}; for _, v := range a { _=v }; _=x }\n'
    r = check(tmp_path, code, "-enable=hugeParam,rangeExprCopy,rangeValCopy")
    assert "hugeParam:" in r.stderr and "rangeExprCopy:" in r.stderr and "rangeValCopy:" in r.stderr
    r = check(tmp_path, code, "-enable=hugeParam,rangeExprCopy,rangeValCopy", "-@hugeParam.sizeThreshold=999999999", "-@rangeExprCopy.sizeThreshold=999999999", "-@rangeValCopy.sizeThreshold=999999999")
    assert r.returncode == 0 and r.stderr == ""

def test_regexp_simplify_and_bad_regexp(tmp_path):
    code = 'package p\nimport "regexp"\nfunc f(){ _=regexp.MustCompile("[aa]"); _=regexp.MustCompile("[0-9]") }\n'
    r = check(tmp_path, code, "-enable=badRegexp,regexpSimplify")
    assert "badRegexp:" in r.stderr and "duplicated in [aa]" in r.stderr
    assert "regexpSimplify:" in r.stderr and "\\d" in r.stderr

def test_experimental_selected_and_opinionated(tmp_path):
    code = 'package p\nfunc f(){ len:=10; _=len; x:=1; _=x > 5 || x == 5 }\n'
    r = check(tmp_path, code, "-enable=builtinShadow,boolExprSimplify")
    assert "builtinShadow: shadowing of predeclared identifier: len" in r.stderr
    assert "boolExprSimplify:" in r.stderr

def test_misc_selected_checkers(tmp_path):
    code = 'package p\nimport "strings"\nfunc f(s string){ _=strings.Contains("prefix_",s); _=strings.Contains(s,s); _=s[len(s)] }\n'
    r = check(tmp_path, code, "-enable=argOrder,dupArg,offBy1")
    assert "argOrder: \"prefix_\" and s arguments order looks reversed" in r.stderr
    assert "dupArg: suspicious duplicated args in strings.Contains" in r.stderr
    assert "offBy1:" in r.stderr

def test_more_selected_checkers(tmp_path):
    code = 'package p\nfunc f(x int){ if x==5 && x==10 { }; if x==1 {} else if x==2 {} else if x==3 {}; switch true { default: }; switch x { case 1:; case 1: } }\n'
    r = check(tmp_path, code, "-enable=badCond,ifElseChain,switchTrue,dupCase", "-@ifElseChain.minThreshold=2")
    assert "badCond:" in r.stderr and "ifElseChain: rewrite if-else to switch statement" in r.stderr
    assert "switchTrue:" in r.stderr and "dupCase:" in r.stderr

def test_opinionated_type_and_block_rules(tmp_path):
    code = 'package p\nfunc f(a int, b int, c int) (int, int) { { println(a) }; return a,b }\n'
    r = check(tmp_path, code, "-enable=paramTypeCombine,unnamedResult,unnecessaryBlock")
    assert "paramTypeCombine:" in r.stderr and "unnamedResult:" in r.stderr and "unnecessaryBlock:" in r.stderr
