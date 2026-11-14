import json

from conftest import config, json_findings, write_go


def rule_config(tmp_path, name, fields=""):
    return config(tmp_path, f'[rule.{name}]\n{fields}')


def test_error_rules_report_categories(invoke, tmp_path):
    source = write_go(tmp_path, "p.go", 'package p\nimport "errors"\nfunc f() (error, int) { return errors.New("Bad."), 1 }\n')
    cfg = config(tmp_path, '[rule.error-return]\n[rule.error-strings]\n')
    findings = json_findings(invoke("-config", cfg, "-formatter", "json", source, cwd=tmp_path))
    messages = {f["RuleName"]: f["Failure"] for f in findings}
    assert "error should be the last type when returning multiple items" in messages["error-return"]
    assert "error strings should not be capitalized" in messages["error-strings"]


def test_range_rule_reports_replacement_header(invoke, tmp_path):
    source = write_go(tmp_path, "p.go", "package p\nfunc f(m map[int]int) { for k, _ := range m { _ = k } }\n")
    cfg = rule_config(tmp_path, "range")
    findings = json_findings(invoke("-config", cfg, "-formatter", "json", source, cwd=tmp_path))
    assert len(findings) == 1
    assert "should omit 2nd value from range" in findings[0]["Failure"]
    assert "for k := range" in findings[0]["ReplacementLine"]


def test_complexity_limit_is_strictly_exceeded(invoke, tmp_path):
    source = write_go(tmp_path, "p.go", "package p\nfunc f(a,b,c int) {}\n")
    cfg = rule_config(tmp_path, "argument-limit", "arguments = [2]\n")
    findings = json_findings(invoke("-config", cfg, "-formatter", "json", source, cwd=tmp_path))
    assert len(findings) == 1
    assert "max 2 but got 3" in findings[0]["Failure"]
    assert findings[0]["Position"]["Start"]["Column"] == 1


def test_line_length_counts_physical_line_characters(invoke, tmp_path):
    source = write_go(tmp_path, "p.go", "package p\n// " + "x" * 45 + "\n")
    cfg = rule_config(tmp_path, "line-length-limit", "arguments = [40]\n")
    findings = json_findings(invoke("-config", cfg, "-formatter", "json", source, cwd=tmp_path))
    assert any("line is 48 characters, out of limit 40" in f["Failure"] for f in findings)


def test_import_rules_handle_dot_duplicate_alias_and_blocklist(invoke, tmp_path):
    source = write_go(tmp_path, "p.go", 'package p\nimport (\n . "fmt"\n fmt "fmt"\n "crypto/md5"\n)\n')
    cfg = config(tmp_path, '[rule.dot-imports]\n[rule.duplicated-imports]\n[rule.redundant-import-alias]\n[rule.imports-blocklist]\narguments = ["crypto/.*"]\n')
    findings = json_findings(invoke("-config", cfg, "-formatter", "json", source, cwd=tmp_path))
    names = {f["RuleName"] for f in findings}
    assert {"dot-imports", "duplicated-imports", "redundant-import-alias", "imports-blocklist"} <= names


def test_context_rules_report_bad_order_and_basic_key(invoke, tmp_path):
    source = write_go(tmp_path, "p.go", 'package p\nimport "context"\nfunc f(x int, ctx context.Context) { _ = context.WithValue(ctx, "key", x) }\n')
    cfg = config(tmp_path, '[rule.context-as-argument]\n[rule.context-keys-type]\n')
    findings = json_findings(invoke("-config", cfg, "-formatter", "json", source, cwd=tmp_path))
    assert any("context.Context should be the first parameter" in f["Failure"] for f in findings)
    assert any("should not use basic type" in f["Failure"] for f in findings)


def test_unreachable_code_reports_first_dead_statement(invoke, tmp_path):
    source = write_go(tmp_path, "p.go", "package p\nfunc f() { return; println(1); println(2) }\n")
    cfg = rule_config(tmp_path, "unreachable-code")
    findings = json_findings(invoke("-config", cfg, "-formatter", "json", source, cwd=tmp_path))
    assert len(findings) == 1
    assert findings[0]["Failure"] == "unreachable code after this statement"


def test_increment_rule_not_reported_below_confidence(invoke, tmp_path):
    source = write_go(tmp_path, "p.go", "package p\nfunc f() { i := 0; i += 1; _ = i }\n")
    cfg = config(tmp_path, 'confidence = 0.9\n[rule.increment-decrement]\n')
    assert json_findings(invoke("-config", cfg, "-formatter", "json", source, cwd=tmp_path)) is None


def test_unsecure_url_exempts_local_addresses(invoke, tmp_path):
    source = write_go(tmp_path, "p.go", 'package p\nvar a = "http://example.com"\nvar b = "http://localhost/path"\nvar c = "http://127.0.0.1/"\n')
    cfg = rule_config(tmp_path, "unsecure-url-scheme")
    findings = json_findings(invoke("-config", cfg, "-formatter", "json", source, cwd=tmp_path))
    assert len(findings) == 1
    assert 'prefer secure protocol https over http in "http://example.com"' in findings[0]["Failure"]


def test_go_version_gates_slices_sort_rule(invoke, tmp_path):
    source = write_go(tmp_path, "p.go", 'package p\nimport "sort"\nfunc f(x []int) { sort.Ints(x) }\n')
    cfg = config(tmp_path, 'goVersion = "1.21"\n[rule.use-slices-sort]\n')
    findings = json_findings(invoke("-config", cfg, "-formatter", "json", source, cwd=tmp_path))
    assert len(findings) == 1
    assert findings[0]["Failure"] == "replace sort.Ints by slices.Sort"


def test_struct_tag_invalid_field_is_finding(invoke, tmp_path):
    source = write_go(tmp_path, "p.go", 'package p\ntype T struct { X int `json:"x,bogus"` }\n')
    cfg = rule_config(tmp_path, "struct-tag")
    findings = json_findings(invoke("-config", cfg, "-formatter", "json", source, cwd=tmp_path))
    assert len(findings) == 1
    assert 'unknown option "bogus" in json tag' in findings[0]["Failure"]


def test_add_constant_reports_repeated_magic_literals(invoke, tmp_path):
    source = write_go(tmp_path, "p.go", "package p\nfunc f(x int) int { return x * 42 + 100 }\n")
    cfg = rule_config(tmp_path, "add-constant", 'arguments = [{allowInts = "0,1"}]\n')
    findings = json_findings(invoke("-config", cfg, "-formatter", "json", source, cwd=tmp_path))
    assert len(findings) == 2
    assert {"avoid magic numbers like '42', create a named constant for it", "avoid magic numbers like '100', create a named constant for it"} == {f["Failure"] for f in findings}


def test_directive_only_recognizes_exact_lowercase_line_comment(invoke, tmp_path):
    source = write_go(tmp_path, "p.go", "package p\n// revive:disable:increment-decrement\nfunc f() { i := 0; i += 1; _ = i }\n")
    cfg = rule_config(tmp_path, "increment-decrement")
    findings = json_findings(invoke("-config", cfg, "-formatter", "json", source, cwd=tmp_path))
    assert len(findings) == 1


def test_crlf_unicode_and_long_lines_are_read(invoke, tmp_path):
    source = tmp_path / "unicode.go"
    source.write_bytes("package p\r\n// café 世界 ".encode("utf-8") + b"x" * 10000 + b"\r\nvar invalid_name int\r\n")
    cfg = rule_config(tmp_path, "var-naming")
    findings = json_findings(invoke("-config", cfg, "-formatter", "json", source, cwd=tmp_path))
    assert len(findings) == 1
    assert findings[0]["Position"]["Start"]["Line"] == 3


def test_invalid_utf8_is_reported_as_parser_finding(invoke, tmp_path):
    source = tmp_path / "binary.go"
    source.write_bytes(b"\xff\xfe")
    findings = json_findings(invoke("-formatter", "json", source, cwd=tmp_path))
    assert any("illegal UTF-8 encoding" in f["Failure"] for f in findings)
