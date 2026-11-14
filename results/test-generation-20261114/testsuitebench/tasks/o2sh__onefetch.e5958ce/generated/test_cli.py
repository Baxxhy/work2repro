import json
import os
import pathlib
import subprocess
import tempfile

import pytest

EXE = "/workspace/executable"


def run(args=(), cwd=None):
    return subprocess.run([EXE, *map(str, args)], cwd=cwd, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def repo(tmp_path, files=None, commits=1):
    p = tmp_path
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=p, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=p, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=p, check=True)
    for name, content in (files or {"main.rs": "fn main() {}\n"}).items():
        q = p / name
        q.parent.mkdir(parents=True, exist_ok=True)
        q.write_bytes(content if isinstance(content, bytes) else content.encode())
    for i in range(commits):
        if i:
            with (p / "main.rs").open("a") as f:
                f.write(f"// commit {i}\n")
        subprocess.run(["git", "add", "-A"], cwd=p, check=True)
        subprocess.run(["git", "commit", "-qm", f"commit {i}"], cwd=p, check=True)
    return p


def payload(p, *args):
    r = run(["-o", "json", *args, "--", str(p)], cwd=p.parent)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def fields(data):
    return {next(iter(x)): next(iter(x.values())) for x in data["infoFields"]}


def test_version_and_help_are_repository_independent(tmp_path):
    r = run(["--version"], cwd=tmp_path)
    assert (r.returncode, r.stdout, r.stderr) == (0, "onefetch 2.25.0\n", "")
    h = run(["-h"], cwd=tmp_path)
    assert h.returncode == 0 and "see more with '--help'" in h.stdout and not h.stderr
    long = run(["--help", "--nonsense"], cwd=tmp_path)
    assert long.returncode == 0 and "Command-line Git information tool" in long.stdout and not long.stderr


def test_side_lists_and_precedence(tmp_path):
    p = run(["--package-managers"], cwd=tmp_path)
    assert (p.returncode, p.stdout, p.stderr) == (0, "Npm\nCargo\n", "")
    both = run(["--languages", "--package-managers"], cwd=tmp_path)
    assert both.returncode == 0 and both.stdout.startswith("ABNF\nABAP\nAda\n")
    assert len(both.stdout.splitlines()) == 117 and both.stdout.endswith("Zsh\n")


@pytest.mark.parametrize("shell,marker", [("bash", "_onefetch() {"), ("zsh", "#compdef onefetch"),
                                           ("fish", "complete -c onefetch"), ("elvish", "use builtin;"),
                                           ("powershell", "Register-ArgumentCompleter")],
                         ids=["bash", "zsh", "fish", "elvish", "powershell"])
def test_completion_modes(tmp_path, shell, marker):
    r = run(["--generate", shell], cwd=tmp_path)
    assert r.returncode == 0 and not r.stderr and r.stdout.endswith("\n") and marker in r.stdout
    assert "--disabled-fields" in r.stdout and "--number-of-authors" in r.stdout


def test_cli_rejects_invalid_values_and_dependencies(tmp_path):
    cases = [(["--number-separator", "dots"], "plain, comma, space, underscore"),
             (["--output", "xml"], "json, yaml"), (["--true-color", "sometimes"], "auto, never, always"),
             (["--ascii-colors", "16"], "0..16")]
    for args, diagnostic in cases:
        r = run(args, cwd=tmp_path)
        assert r.returncode == 2 and not r.stdout and diagnostic in r.stderr
    r = run(["--image-protocol", "kitty"], cwd=tmp_path)
    assert r.returncode == 2 and "--image <IMAGE>" in r.stderr
    r = run(["--number-of-authors", "-1"], cwd=tmp_path)
    assert r.returncode == 2 and "unexpected argument '-1'" in r.stderr


def test_repository_and_input_path_errors(tmp_path):
    notdir = tmp_path / "missing"
    r = run([notdir], cwd=tmp_path)
    assert r.returncode == 1 and not r.stdout
    assert r.stderr == f"Error: Failed to access a directory, or path is not a directory: '{notdir}'\n"
    r = run(["."], cwd=tmp_path)
    assert r.returncode == 1 and "Could not find a git repository" in r.stderr


def test_structured_schema_and_disable_options(tmp_path):
    p = repo(tmp_path / "repo")
    d = payload(p)
    assert list(d) == ["title", "infoFields"]
    f = fields(d)
    assert "ProjectInfo" in f and f["ProjectInfo"]["repoName"] == ""
    assert f["CommitsInfo"]["numberOfCommits"] == 1
    assert f["HeadInfo"]["headRefs"]["shortCommitId"] == subprocess.check_output(
        ["git", "rev-parse", "--short=7", "HEAD"], cwd=p, text=True).strip()
    disabled = fields(payload(p, "--no-title", "-d", "authors", "commits"))
    assert "AuthorsInfo" not in disabled and "CommitsInfo" not in disabled
    assert "AuthorsInfo" not in fields(payload(p, "-d", "authors"))


def test_pending_counts_staged_untracked_and_modified(tmp_path):
    p = repo(tmp_path / "repo")
    (p / "new.txt").write_text("untracked\n")
    (p / "main.rs").write_text("changed\n")
    f = fields(payload(p))
    assert f["PendingInfo"] == {"added": 1, "deleted": 0, "modified": 1}
    subprocess.run(["git", "add", "new.txt"], cwd=p, check=True)
    f = fields(payload(p))
    assert f["PendingInfo"]["added"] == 0


def test_languages_types_and_loc(tmp_path):
    p = repo(tmp_path / "repo", {"a.rs": "fn a() {}\n// comment\n\n", "b.md": "# H\ntext\n<!-- x -->\n"})
    f = fields(payload(p))
    assert f["LocInfo"]["linesOfCode"] == 1
    assert f["LanguagesInfo"]["languagesWithPercentage"] == [{"language": "Rust", "percentage": 100.0}]
    f = fields(payload(p, "--type", "prose"))
    assert f["LocInfo"]["linesOfCode"] == 3
    assert f["LanguagesInfo"]["languagesWithPercentage"][0]["language"] == "Markdown"
    f = fields(payload(p, "--type", "data"))
    assert "LocInfo" not in f and "LanguagesInfo" not in f


def test_manifest_description_dependencies_version_and_license(tmp_path):
    p = repo(tmp_path / "repo", {"Cargo.toml": '[package]\nname="manifest"\nversion="1.2.3"\ndescription="héllo"\nlicense="MIT"\n[dependencies]\nserde="1"\nregex={version="1"}\n[dev-dependencies]\ntempfile="1"\n'})
    f = fields(payload(p))
    assert f["DescriptionInfo"]["description"] == "héllo"
    assert f["DependenciesInfo"]["dependencies"] == "2 (Cargo)"
    assert f["VersionInfo"]["version"] == "1.2.3"
    assert f["LicenseInfo"]["license"] == "MIT"
    subprocess.run(["git", "tag", "release/v2"], cwd=p, check=True)
    assert fields(payload(p))["VersionInfo"]["version"] == "release/v2"


def test_size_hidden_excluded_and_churn(tmp_path):
    p = repo(tmp_path / "repo", {"keep.rs": "fn a() {}\n", "skip.rs": "fn b() {}\n", ".hidden.py": "x=1\n"}, commits=2)
    f = fields(payload(p, "--exclude", "skip.rs"))
    assert f["SizeInfo"]["fileCount"] == 3
    assert [x["filePath"] for x in f["ChurnInfo"]["file_churns"]] == ["keep.rs"]
    f = fields(payload(p, "--include-hidden"))
    assert {x["language"] for x in f["LanguagesInfo"]["languagesWithPercentage"]} == {"Rust", "Python"}
    assert fields(payload(p, "--number-of-file-churns", "0"))["ChurnInfo"]["file_churns"] == []


def test_text_mode_wraps_and_no_art_no_palette(tmp_path):
    p = repo(tmp_path / "repo")
    r = run(["--no-art", "--no-color-palette", str(p)], cwd=p.parent)
    assert r.returncode == 0 and not r.stderr
    assert r.stdout.startswith("\x1b[?7l") and r.stdout.endswith("\x1b[?7h")
    assert "Project:" not in r.stdout  # no configured origin
