from conftest import config, json_findings, write_go


def test_empty_directory_and_ordinary_findings_default_status(invoke):
    result = invoke()
    assert result.returncode == 0
    assert result.stdout == result.stderr == b""


def test_explicit_absolute_file_and_symlink_are_analyzed(invoke, tmp_path):
    source = write_go(tmp_path, "source.go", "package p\nfunc f() { i := 0; i += 1; _ = i }\n")
    cfg = config(tmp_path, '[rule.increment-decrement]\n')
    absolute = invoke("-config", cfg, "-formatter", "json", source, cwd=tmp_path)
    assert absolute.returncode == 0
    findings = json_findings(absolute)
    assert any("should replace i += 1 with i++" in f["Failure"] for f in findings)
    link = tmp_path / "link.go"
    link.symlink_to(source)
    linked = json_findings(invoke("-config", cfg, "-formatter", "json", link, cwd=tmp_path))
    assert linked


def test_directory_and_recursive_patterns_union_results(invoke, tmp_path):
    write_go(tmp_path, "one.go", "package p\nfunc f() { i := 0; i += 1; _ = i }\n")
    write_go(tmp_path, "sub/two.go", "package p\nfunc g() { i := 0; i += 1; _ = i }\n")
    cfg = config(tmp_path, '[rule.increment-decrement]\n')
    direct = json_findings(invoke("-config", cfg, "-formatter", "json", ".", cwd=tmp_path))
    recursive = json_findings(invoke("-config", cfg, "-formatter", "json", "./...", cwd=tmp_path))
    assert len(direct) == 2
    assert len(recursive) == 2


def test_explicit_build_tag_file_still_linted(invoke, tmp_path):
    source = write_go(tmp_path, "tagged.go", "// +build linux\n\npackage p\nfunc f() { i := 0; i += 1; _ = i }\n")
    cfg = config(tmp_path, '[rule.increment-decrement]\n')
    findings = json_findings(invoke("-config", cfg, "-formatter", "json", source, cwd=tmp_path))
    assert findings and findings[0]["Position"]["Start"]["Line"] == 4


def test_explicit_config_disables_implicit_rules_and_empty_config(invoke, tmp_path):
    source = write_go(tmp_path, "p.go", "package p\nfunc f() { i := 0; i += 1; _ = i }\n")
    empty = config(tmp_path, "ignoreGeneratedHeader = false\n")
    assert json_findings(invoke("-config", empty, "-formatter", "json", source, cwd=tmp_path)) is None


def test_configured_rule_reports_structured_fields(invoke, tmp_path):
    source = write_go(tmp_path, "p.go", "package p\nfunc f() { i := 0; i += 1; _ = i }\n")
    cfg = config(tmp_path, '[rule.increment-decrement]\nseverity = "error"\n')
    finding = json_findings(invoke("-config", cfg, "-formatter", "json", source, cwd=tmp_path))[0]
    for field in ("Severity", "Failure", "RuleName", "Category", "Position", "Confidence", "ReplacementLine"):
        assert field in finding
    assert finding["Severity"] == "error"
    assert finding["RuleName"] == "increment-decrement"
    assert finding["Position"]["Start"]["Line"] == 2
    assert finding["Position"]["Start"]["Offset"] >= 0
    assert finding["Confidence"] == 0.8


def test_exclusion_wins_and_empty_exclusion_is_noop(invoke, tmp_path):
    source = write_go(tmp_path, "x.go", "package p\nfunc f() { i := 0; i += 1; _ = i }\n")
    cfg = config(tmp_path, '[rule.increment-decrement]\n')
    excluded = invoke("-config", cfg, "-formatter", "json", "-exclude", "x.go", source, cwd=tmp_path)
    assert json_findings(excluded) is None
    included = invoke("-config", cfg, "-formatter", "json", "-exclude", "", source, cwd=tmp_path)
    assert json_findings(included)


def test_exact_exclusion_does_not_normalize_equivalent_spelling(invoke, tmp_path):
    source = write_go(tmp_path, "x.go", "package p\nfunc f() { i := 0; i += 1; _ = i }\n")
    cfg = config(tmp_path, '[rule.increment-decrement]\n')
    result = invoke("-config", cfg, "-formatter", "json", "-exclude", "./x.go", "x.go", cwd=tmp_path)
    assert json_findings(result)


def test_open_file_limits_do_not_change_analysis(invoke, tmp_path):
    source = write_go(tmp_path, "x.go", "package p\nfunc f() { i := 0; i += 1; _ = i }\n")
    cfg = config(tmp_path, '[rule.increment-decrement]\n')
    counts = []
    for limit in ("0", "1", "3", "999999"):
        result = invoke("-config", cfg, "-formatter", "json", "-max_open_files", limit, source, cwd=tmp_path)
        counts.append(len(json_findings(result)))
    assert counts == [1, 1, 1, 1]


def test_config_validation_precedes_target_resolution(invoke, tmp_path):
    bad = config(tmp_path, '[rule.not-a-real-rule]\n')
    result = invoke("-config", bad, "/not/a/real/target.go", cwd=tmp_path)
    assert result.returncode == 1
    assert b"cannot find rule: not-a-real-rule" in result.stderr
    assert result.stdout == b""


def test_bad_toml_reports_parser_detail(invoke, tmp_path):
    bad = config(tmp_path, 'severity = "warning"\nconfidence = this\n')
    result = invoke("-config", bad, cwd=tmp_path)
    assert result.returncode == 1
    assert b"cannot parse the config file" in result.stderr
    assert b"expected value" in result.stderr


def test_nonexistent_absolute_target_is_fatal_stderr_only(invoke, tmp_path):
    result = invoke("/this/path/does/not/exist.go", cwd=tmp_path)
    assert result.returncode == 1
    assert b"cannot import absolute path" in result.stderr
    assert result.stdout == b""


def test_invalid_go_is_a_validity_finding(invoke, tmp_path):
    source = write_go(tmp_path, "empty.go", "")
    result = invoke("-formatter", "json", source, cwd=tmp_path)
    findings = json_findings(result)
    assert any(f["Category"] == "validity" and "expected 'package', found 'EOF'" in f["Failure"] for f in findings)


def test_non_go_target_is_a_validity_finding(invoke, tmp_path):
    source = tmp_path / "notes.txt"
    source.write_text("not go", encoding="utf-8")
    findings = json_findings(invoke("-formatter", "json", source, cwd=tmp_path))
    assert any("invalid file" in f["Failure"] for f in findings)


def test_unreadable_explicit_config_has_stable_error(invoke, tmp_path):
    result = invoke("-config", "/nonexistent/path/config.toml", cwd=tmp_path)
    assert result.returncode == 1
    assert result.stderr == b"cannot read the config file\n"


def test_xdg_config_precedes_home_config(invoke, tmp_path):
    xdg = tmp_path / "xdg"
    home = tmp_path / "home"
    xdg.mkdir()
    home.mkdir()
    (xdg / "revive.toml").write_text("confidence = this\n", encoding="utf-8")
    (home / "revive.toml").write_text("", encoding="utf-8")
    result = invoke(env={"XDG_CONFIG_HOME": xdg, "HOME": home}, cwd=tmp_path)
    assert result.returncode == 1
    assert b"cannot parse the config file" in result.stderr


def test_discovered_home_config_used_when_xdg_candidate_missing(invoke, tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    (home / "revive.toml").write_text("[rule.increment-decrement]\n", encoding="utf-8")
    source = write_go(tmp_path, "p.go", "package p\nfunc f() { i := 0; i += 1; _ = i }\n")
    result = invoke("-formatter", "json", source, cwd=tmp_path, env={"XDG_CONFIG_HOME": tmp_path / "missing-xdg", "HOME": home})
    assert json_findings(result)
