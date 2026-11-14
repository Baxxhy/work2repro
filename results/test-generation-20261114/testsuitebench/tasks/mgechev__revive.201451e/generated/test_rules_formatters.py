import json
import xml.etree.ElementTree as ET

from conftest import config, json_findings, write_go


def one_rule(tmp_path, name, extra=""):
    return config(tmp_path, f'[rule.{name}]\n{extra}')


def test_package_comment_position_category_confidence_and_test_exemption(invoke, tmp_path):
    source = write_go(tmp_path, "p.go", "package p\n")
    cfg = one_rule(tmp_path, "package-comments")
    result = json_findings(invoke("-config", cfg, "-formatter", "json", source, cwd=tmp_path))
    assert len(result) == 1
    assert result[0]["Failure"] == "should have a package comment"
    assert result[0]["Category"] == "comments" and result[0]["Confidence"] == 1
    assert result[0]["Position"]["Start"]["Line"] == 1
    test_file = write_go(tmp_path, "p_test.go", "package p\n")
    assert json_findings(invoke("-config", cfg, "-formatter", "json", test_file, cwd=tmp_path)) is None


def test_detached_package_comment_has_lower_confidence(invoke, tmp_path):
    source = write_go(tmp_path, "p.go", "// Package p docs.\n\npackage p\n")
    cfg = one_rule(tmp_path, "package-comments")
    finding = json_findings(invoke("-config", cfg, "-formatter", "json", source, cwd=tmp_path))[0]
    assert finding["Failure"] == "package comment is detached; there should be no blank lines between it and the package statement"
    assert finding["Confidence"] == 0.9
    assert finding["Position"]["Start"]["Line"] == 2


def test_exported_rule_checks_non_main_declarations(invoke, tmp_path):
    source = write_go(tmp_path, "p.go", "package p\nvar X int\nfunc Hello() {}\n")
    cfg = one_rule(tmp_path, "exported")
    findings = json_findings(invoke("-config", cfg, "-formatter", "json", source, cwd=tmp_path))
    failures = [f["Failure"] for f in findings]
    assert any("exported var X should have comment or be unexported" in x for x in failures)
    assert any("exported function Hello should have comment or be unexported" in x for x in failures)


def test_var_naming_and_confidence_filter(invoke, tmp_path):
    source = write_go(tmp_path, "p.go", "package p\nvar invalid_name int\n")
    cfg = one_rule(tmp_path, "var-naming")
    finding = json_findings(invoke("-config", cfg, "-formatter", "json", source, cwd=tmp_path))[0]
    assert finding["Failure"] == "don't use underscores in Go names; var invalid_name should be invalidName"
    assert finding["Category"] == "naming" and finding["Confidence"] == 0.9
    strict = config(tmp_path, 'confidence = 1.0\n[rule.var-naming]\n')
    assert json_findings(invoke("-config", strict, "-formatter", "json", source, cwd=tmp_path)) is None


def test_rule_specific_severity_and_exit_codes(invoke, tmp_path):
    source = write_go(tmp_path, "p.go", "package p\nfunc f() { i := 0; i += 1; _ = i }\n")
    cfg = config(tmp_path, 'errorCode = 7\nwarningCode = 3\n[rule.increment-decrement]\nseverity = "error"\n')
    assert invoke("-config", cfg, source, cwd=tmp_path).returncode == 7
    assert invoke("-config", cfg, "-set_exit_status", source, cwd=tmp_path).returncode == 1
    clean = write_go(tmp_path, "clean.go", "package p\nfunc f() {}\n")
    assert invoke("-config", cfg, "-set_exit_status", clean, cwd=tmp_path).returncode == 0


def test_control_directives_apply_to_rules(invoke, tmp_path):
    source = write_go(tmp_path, "p.go", "package p\n//revive:disable:increment-decrement\nfunc a() { i := 0; i += 1; _ = i }\n//revive:enable:increment-decrement\nfunc b() { i := 0; i += 1; _ = i }\n")
    cfg = one_rule(tmp_path, "increment-decrement")
    findings = json_findings(invoke("-config", cfg, "-formatter", "json", source, cwd=tmp_path))
    assert len(findings) == 1
    assert findings[0]["Position"]["Start"]["Line"] == 5


def test_line_and_next_line_directives(invoke, tmp_path):
    source = write_go(tmp_path, "p.go", "package p\nfunc f() {\n i := 0; i += 1; _ = i //revive:disable-line:increment-decrement\n j := 0; j += 1; _ = j\n //revive:disable-next-line:increment-decrement\n k := 0; k += 1; _ = k\n m := 0; m += 1; _ = m\n}\n")
    cfg = one_rule(tmp_path, "increment-decrement")
    findings = json_findings(invoke("-config", cfg, "-formatter", "json", source, cwd=tmp_path))
    assert len(findings) == 2
    assert [f["Position"]["Start"]["Line"] for f in findings] == [4, 7]


def test_formatter_plain_unix_and_default_endings(invoke, tmp_path):
    source = write_go(tmp_path, "p.go", "package p\nfunc f() { i := 0; i += 1; _ = i }\n")
    cfg = one_rule(tmp_path, "increment-decrement")
    default = invoke("-config", cfg, source, cwd=tmp_path)
    plain = invoke("-config", cfg, "-formatter", "plain", source, cwd=tmp_path)
    unix = invoke("-config", cfg, "-formatter", "unix", source, cwd=tmp_path)
    assert default.stdout.endswith(b"\n") and not default.stdout.endswith(b"\n\n")
    assert plain.stdout.endswith(b"\n\n") and b"https://revive.run/r#increment-decrement" in plain.stdout
    assert unix.stdout.endswith(b"\n\n") and b"[increment-decrement]" in unix.stdout


def test_json_schema_and_ndjson_trailing_blank_line(invoke, tmp_path):
    source = write_go(tmp_path, "p.go", "package p\nfunc f() { i := 0; i += 1; j := 0; j -= 1; _, _ = i, j }\n")
    cfg = one_rule(tmp_path, "increment-decrement")
    result = invoke("-config", cfg, "-formatter", "json", source, cwd=tmp_path)
    findings = json.loads(result.stdout)
    assert len(findings) == 2
    ndjson = invoke("-config", cfg, "-formatter", "ndjson", source, cwd=tmp_path)
    lines = ndjson.stdout.decode().splitlines()
    assert len(lines) == 3 and lines[-1] == ""
    assert all(json.loads(line)["RuleName"] == "increment-decrement" for line in lines[:2])


def test_checkstyle_xml_fields_and_escaping(invoke, tmp_path):
    source = write_go(tmp_path, "p.go", "package p\nvar invalid_name int\n")
    cfg = one_rule(tmp_path, "var-naming")
    result = invoke("-config", cfg, "-formatter", "checkstyle", source, cwd=tmp_path)
    assert result.stdout.startswith(b'<?xml version="1.0"')
    root = ET.fromstring(result.stdout)
    error = root.find("./file/error")
    assert error is not None
    assert error.attrib["source"] == "revive/var-naming"
    assert error.attrib["severity"] == "warning"
    assert "confidence" in error.attrib["message"]


def test_sarif_result_has_location(invoke, tmp_path):
    source = write_go(tmp_path, "p.go", "package p\nfunc f() { i := 0; i += 1; _ = i }\n")
    cfg = one_rule(tmp_path, "increment-decrement")
    sarif = json.loads(invoke("-config", cfg, "-formatter", "sarif", source, cwd=tmp_path).stdout)
    assert sarif["version"] == "2.1.0"
    run = sarif["runs"][0]
    assert run["tool"]["driver"]["name"] == "revive"
    assert run["tool"]["driver"]["informationUri"] == "https://revive.run"
    result = run["results"][0]
    assert result["ruleId"] and result["message"]["text"]
    region = result["locations"][0]["physicalLocation"]["region"]
    assert region["startLine"] > 0 and region["startColumn"] > 0


def test_builtin_rules_include_documented_core_rules(invoke, tmp_path):
    source = write_go(tmp_path, "p.go", "package p\nvar invalid_name int\nfunc f() { i := 0; i += 1; _ = i }\n")
    findings = json_findings(invoke("-formatter", "json", source, cwd=tmp_path))
    names = {f["RuleName"] for f in findings}
    assert "var-naming" in names
    assert "increment-decrement" in names


def test_confidence_and_replacement_are_serialized(invoke, tmp_path):
    source = write_go(tmp_path, "p.go", "package p\nfunc f() { for k, _ := range map[int]int{} { _ = k } }\n")
    cfg = one_rule(tmp_path, "range")
    findings = json_findings(invoke("-config", cfg, "-formatter", "json", source, cwd=tmp_path))
    assert len(findings) == 1
    assert "ReplacementLine" in findings[0]
    assert "for k := range" in findings[0]["ReplacementLine"]
