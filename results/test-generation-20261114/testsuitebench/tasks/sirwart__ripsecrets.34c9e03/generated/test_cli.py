import os
import pathlib
import subprocess
import tempfile

EXE = os.environ.get("EXECUTABLE", "/workspace/executable")


def invoke(args=(), *, cwd=None, data=None):
    return subprocess.run([EXE, *map(str, args)], cwd=cwd, input=data,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          timeout=20)


def test_version_is_exact():
    for arg in ("--version", "-V"):
        p = invoke([arg])
        assert (p.returncode, p.stdout, p.stderr) == (0, b"ripsecrets 0.1.11\n", b"")


def test_help_forms_succeed():
    for arg in ("-h", "--help"):
        p = invoke([arg])
        assert p.returncode == 0 and p.stdout.startswith(b"A command-line tool" if arg == "-h" else b"ripsecrets searches")
        assert not p.stderr


def test_missing_additional_pattern_value():
    p = invoke(["--additional-pattern"])
    assert p.returncode == 2 and not p.stdout
    assert b"a value is required for '--additional-pattern <ADDITIONAL_PATTERNS>'" in p.stderr


def test_unknown_option_diagnostic_and_combined_short_name():
    for arg, rejected in (("--invalid-flag", b"--invalid-flag"), ("-abc", b"-a")):
        p = invoke([arg])
        assert p.returncode == 2 and not p.stdout
        assert b"error: unexpected argument '" + rejected + b"' found" in p.stderr


def test_short_option_aliases_rejected():
    for arg in ("-o", "-s", "-a", "-ab"):
        assert invoke([arg]).returncode == 2


def test_options_after_paths_and_dash_end_options():
    with tempfile.TemporaryDirectory() as td:
        root = pathlib.Path(td)
        clean = root / "clean"
        clean.write_text("ordinary\n")
        p = invoke([clean, "--only-matching"])
        assert p.returncode == 0 and not p.stdout and not p.stderr
        literal = root / "-file"
        literal.write_text("ordinary\n")
        p = invoke(["--", literal])
        assert p.returncode == 0


def test_missing_source_diagnostic_does_not_fail_clean_scan():
    with tempfile.TemporaryDirectory() as td:
        p = invoke(["absent", "-"], cwd=td, data=b"ghp_" + b"A" * 36)
        assert p.returncode == 0 and not p.stdout
        assert b"absent: No such file or directory (os error 2)" in p.stderr


def test_missing_and_secret_sources_have_mixed_status_streams():
    with tempfile.TemporaryDirectory() as td:
        f = pathlib.Path(td) / "token.txt"
        tok = "ghp_" + "A" * 36
        f.write_text(tok + "\n")
        p = invoke(["missing", f], cwd=td)
        assert p.returncode == 1 and p.stdout == f"{f}:1:{tok}\n".encode()
        assert b"missing: No such file" in p.stderr


def test_file_extensions_recursion_hidden_and_explicit_hidden():
    with tempfile.TemporaryDirectory() as td:
        root = pathlib.Path(td)
        token = "ghp_" + "A" * 36
        (root / "x.bin").write_text(token + "\n")
        nested = root / "a" / "b"
        nested.mkdir(parents=True)
        (nested / "NOEXT").write_text(token + "\n")
        (root / ".hidden").write_text(token + "\n")
        (root / ".git").mkdir()
        (root / ".git" / "config").write_text(token + "\n")
        p = invoke([root])
        assert p.returncode == 1
        assert b"x.bin:1:" in p.stdout and b"NOEXT:1:" in p.stdout
        assert b".hidden" not in p.stdout and b".git" not in p.stdout
        q = invoke([root / ".hidden"])
        assert q.returncode == 1 and b".hidden:1:" in q.stdout


def test_explicit_order_duplicate_sources_and_path_spelling():
    with tempfile.TemporaryDirectory() as td:
        root = pathlib.Path(td)
        f = root / "secret"
        tok = "ghp_" + "A" * 36
        f.write_text(tok + "\n")
        sub = root / "dir"
        sub.mkdir()
        (sub / "inside").write_text(tok + "\n")
        p = invoke(["./secret", "./dir", "./secret"], cwd=root)
        assert p.returncode == 1
        assert p.stdout.count(b"./secret:1:") == 2
        assert p.stdout.index(b"./secret") < p.stdout.index(b"./dir/inside")


def test_symlink_file_and_directory_paths():
    with tempfile.TemporaryDirectory() as td:
        root = pathlib.Path(td)
        tok = "ghp_" + "A" * 36
        (root / "real").write_text(tok + "\n")
        (root / "real-dir").mkdir()
        (root / "real-dir" / "f").write_text(tok + "\n")
        (root / "link").symlink_to(root / "real")
        (root / "dirlink").symlink_to(root / "real-dir", target_is_directory=True)
        a = invoke([root / "link"])
        b = invoke([root / "dirlink"])
        assert a.returncode == 1 and str(root / "link").encode() in a.stdout
        assert b.returncode == 1 and str(root / "dirlink" / "f").encode() in b.stdout


def test_only_matching_duplicates_and_capture_spans():
    with tempfile.TemporaryDirectory() as td:
        f = pathlib.Path(td) / "input"
        f.write_text("secret_access_key = '1W0T1eqNpAk3imtH8mJtkSf2AQ3eNMrPqe3u3Tf6'\n")
        p = invoke(["--only-matching", f])
        assert p.returncode == 1
        assert p.stdout == f"{f}:1:1W0T1eqNpAk3imtH8mJtkSf2AQ3eNMrPqe3u3Tf6\n".encode()


def test_builtin_token_families_and_exact_line_output():
    values = ["ghp_" + "A" * 36, "glpat-" + "A" * 20, "AIzaSy" + "A" * 33,
              "npm_" + "A" * 36]
    with tempfile.TemporaryDirectory() as td:
        f = pathlib.Path(td) / "input"
        payload = "  " + values[0] + " tail\n" + values[1] + "\n" + values[2] + "\n" + values[3]
        f.write_text(payload)
        p = invoke([f])
        assert p.returncode == 1
        assert p.stdout == (f"{f}:1:  {values[0]} tail\n{f}:2:{values[1]}\n{f}:3:{values[2]}\n{f}:4:{values[3]}\n").encode()


def test_generic_assignment_entropy_accept_reject():
    with tempfile.TemporaryDirectory() as td:
        f = pathlib.Path(td) / "input"
        f.write_text('aws_access_key = "AKIAN95B87AWHT6U0699"\npassword = "aaaaaaaaaaaaaaaaaaaa"\n')
        p = invoke([f])
        assert p.returncode == 1
        assert b"aws_access_key" in p.stdout and b"aaaaaaaa" not in p.stdout


def test_only_matching_separate_patterns_and_zero_length():
    with tempfile.TemporaryDirectory() as td:
        f = pathlib.Path(td) / "input"
        f.write_text("ordinary text\n")
        p = invoke(["--additional-pattern", "", "--only-matching", f])
        assert p.returncode == 1 and not p.stderr
        assert p.stdout == (f"{f}:1:\n" * 13).encode()


def test_additional_patterns_capture_filter_and_unfiltered():
    with tempfile.TemporaryDirectory() as td:
        f = pathlib.Path(td) / "input"
        f.write_text("mypattern_wrmDCcpolP3yg9l7o9dJragXbj2wFFzWgiN5FBZN\nMYTOKEN-aaaaaaaaaaaa\n")
        p = invoke(["--only-matching", "--additional-pattern", r"mypattern_(\S+)", "--additional-pattern", r"MYTOKEN-\S+", f])
        assert p.returncode == 1
        assert p.stdout == f"{f}:1:wrmDCcpolP3yg9l7o9dJragXbj2wFFzWgiN5FBZN\n{f}:2:MYTOKEN-aaaaaaaaaaaa\n".encode()


def test_invalid_regex_diagnostic():
    p = invoke(["--additional-pattern", "("])
    assert p.returncode == 2 and not p.stdout
    assert p.stderr.startswith(b"Error: regex parse error:\n") and p.stderr.rstrip().endswith(b"error: unclosed group")


def test_allowlist_phrase_suppresses_only_its_line_and_is_case_sensitive():
    with tempfile.TemporaryDirectory() as td:
        f = pathlib.Path(td) / "input"
        tok = "ghp_" + "A" * 36
        f.write_text(tok + " # pragma: allowlist secret\n" + tok + " # PRAGMA: allowlist secret\n" + tok + "\n")
        p = invoke([f])
        assert p.returncode == 1 and p.stdout.count(tok.encode()) == 2


def test_byte_lines_cr_bom_binary_and_final_line():
    with tempfile.TemporaryDirectory() as td:
        f = pathlib.Path(td) / "input"
        tok = b"ghp_" + b"A" * 36
        f.write_bytes(b"\xef\xbb\xbf  \xe2\x98\x83 " + tok + b"\r\n\xff\x00\nlast " + tok)
        p = invoke([f])
        assert p.returncode == 1
        assert p.stdout == str(f).encode() + b":1:  \xe2\x98\x83 " + tok + b"\r\n" + str(f).encode() + b":3:last " + tok + b"\n"


def test_only_lf_delimits_and_match_does_not_cross_lines():
    with tempfile.TemporaryDirectory() as td:
        f = pathlib.Path(td) / "input"
        f.write_bytes(b"clean\rghp_" + b"A" * 36 + b"\r\nclean\ngho_" + b"B" * 36 + b"\rfinal")
        p = invoke([f])
        assert p.returncode == 1 and b":1:clean\rghp_" in p.stdout and b":3:gho_" in p.stdout


def test_strict_ignore_and_literal_secret_file():
    with tempfile.TemporaryDirectory() as td:
        root = pathlib.Path(td)
        (root / ".secretsignore").write_text("ignored.txt\n[secrets]\n" + "ghp_" + "A" * 36 + "\n")
        tok = "ghp_" + "A" * 36
        f = root / "ignored.txt"
        f.write_text(tok + "\nghp_" + "B" * 36 + "\n")
        normal = invoke([f], cwd=root)
        strict = invoke(["--strict-ignore", f], cwd=root)
        assert normal.returncode == 1 and tok.encode() not in normal.stdout
        assert strict.returncode == 0 and not strict.stdout


def test_nested_secretsignore_is_not_loaded():
    with tempfile.TemporaryDirectory() as td:
        root = pathlib.Path(td)
        sub = root / "project"
        (sub / "generated").mkdir(parents=True)
        (sub / ".secretsignore").write_text("generated/\n")
        tok = "ghp_" + "A" * 36
        (sub / "generated" / "secret").write_text(tok + "\n")
        p = invoke([sub], cwd=root)
        assert p.returncode == 1 and b"generated/secret" in p.stdout


def test_invalid_ignore_glob_is_silently_ignored():
    with tempfile.TemporaryDirectory() as td:
        root = pathlib.Path(td)
        (root / ".secretsignore").write_text("[\n")
        tok = "ghp_" + "A" * 36
        (root / "input").write_text(tok + "\n")
        p = invoke(["input"], cwd=root)
        assert p.returncode == 1 and p.stdout == f"input:1:{tok}\n".encode() and not p.stderr


def test_gitignore_only_applies_inside_repository_and_explicit_override():
    with tempfile.TemporaryDirectory() as td:
        root = pathlib.Path(td)
        (root / ".gitignore").write_text("*.tmp\n")
        tok = "ghp_" + "A" * 36
        f = root / "ignored.tmp"
        f.write_text(tok + "\n")
        standalone = invoke([root])
        assert standalone.returncode == 1
        (root / ".git").mkdir()
        walked = invoke([root])
        explicit = invoke([f])
        assert walked.returncode == 0 and not walked.stdout
        assert explicit.returncode == 1


def test_install_requires_git_and_scan_flags_are_rejected():
    with tempfile.TemporaryDirectory() as td:
        p = invoke(["--install-pre-commit"], cwd=td)
        assert p.returncode == 2 and not p.stdout and p.stderr == b"Error: .git directory not found"
        (pathlib.Path(td) / ".git").mkdir()
        for args, phrase in ((["--install-pre-commit", "--strict-ignore"], b"--strict-ignore"),
                             (["--install-pre-commit", "--only-matching"], b"--only-matching")):
            p = invoke(args, cwd=td)
            assert p.returncode == 2 and not p.stdout and phrase in p.stderr


def test_install_creates_exact_executable_hook_and_precommit_d_variant():
    command = b"ripsecrets --strict-ignore `git diff --cached --name-only --diff-filter=ACM`\n"
    with tempfile.TemporaryDirectory() as td:
        root = pathlib.Path(td)
        git = root / ".git"
        (git / "hooks").mkdir(parents=True)
        p = invoke(["--install-pre-commit"], cwd=root)
        hook = git / "hooks" / "pre-commit"
        assert p.returncode == 0 and not p.stdout and not p.stderr
        assert hook.read_bytes() == command
        assert hook.stat().st_mode & 0o100
    with tempfile.TemporaryDirectory() as td:
        root = pathlib.Path(td)
        git = root / ".git"
        (git / "hooks").mkdir(parents=True)
        (git / "pre-commit.d").mkdir()
        p = invoke(["--install-pre-commit"], cwd=root)
        assert p.returncode == 0 and (git / "pre-commit.d" / "ripsecrets").read_bytes() == command


def test_install_appends_and_refuses_duplicate_hook():
    command = b"ripsecrets --strict-ignore `git diff --cached --name-only --diff-filter=ACM`\n"
    with tempfile.TemporaryDirectory() as td:
        root = pathlib.Path(td)
        git = root / ".git"
        (git / "hooks").mkdir(parents=True)
        hook = git / "hooks" / "pre-commit"
        original = b"#!/bin/sh\necho existing\n"
        hook.write_bytes(original)
        p = invoke(["--install-pre-commit"], cwd=root)
        assert p.returncode == 0 and hook.read_bytes() == original + command
        duplicate = invoke(["--install-pre-commit"], cwd=root)
        assert duplicate.returncode == 2 and not duplicate.stdout
        assert duplicate.stderr == b"Error: pre-commit hook has already been installed"
        assert hook.read_bytes() == original + command


def test_install_requires_hooks_directory():
    with tempfile.TemporaryDirectory() as td:
        (pathlib.Path(td) / ".git").mkdir()
        p = invoke(["--install-pre-commit"], cwd=td)
        assert p.returncode == 2 and not p.stdout and b"No such file or directory" in p.stderr


def test_defaults_to_current_directory_and_scans_clean_empty_files():
    with tempfile.TemporaryDirectory() as td:
        root = pathlib.Path(td)
        (root / "empty").write_bytes(b"")
        (root / "spaces").write_bytes(b" \t\n")
        p = invoke([], cwd=root)
        assert p.returncode == 0 and not p.stdout and not p.stderr


def test_url_credentials_return_password_and_jwt_case():
    with tempfile.TemporaryDirectory() as td:
        f = pathlib.Path(td) / "input"
        f.write_text("https://user:wrmDCcpolP3yg9l7o9dJragXbj2wFFzWgiN5FBZN@example.com/path\n"
                     "eyJabc.1234.defg\n eyjabc.1234.defg\n")
        p = invoke(["--only-matching", f])
        assert p.returncode == 1
        assert b":1:wrmDCcpolP3yg9l7o9dJragXbj2wFFzWgiN5FBZN\n" in p.stdout
        assert b":2:eyJabc.1234.defg\n" in p.stdout
        assert b"eyj" not in p.stdout


def test_assignment_and_secret_ignore_candidate_comparison_is_literal():
    with tempfile.TemporaryDirectory() as td:
        root = pathlib.Path(td)
        value = "1W0T1eqNpAk3imtH8mJtkSf2AQ3eNMrPqe3u3Tf6"
        (root / ".secretsignore").write_text("[secrets]\n" + value + "\n")
        f = root / "settings.json"
        f.write_text('{"secret_access_key": "' + value + '"}\n')
        p = invoke([f], cwd=root)
        assert p.returncode == 0 and not p.stdout
