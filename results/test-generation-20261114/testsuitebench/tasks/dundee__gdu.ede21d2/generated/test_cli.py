import json
import os
import re
import subprocess
from pathlib import Path

import pytest


E = Path(__file__).resolve().parent.parent / "executable"


def run(*args, cwd=None, stdin=None, timeout=10):
    return subprocess.run([str(E), *map(str, args)], cwd=cwd, input=stdin,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          timeout=timeout)


def listing(root, *flags, cwd=None):
    p = run("-n", "-c", root, *flags, cwd=cwd)
    assert p.returncode == 0, p.stderr.decode(errors="replace")
    assert b"\x1b[" not in p.stdout
    return p.stdout.decode()


def row_names(out):
    return [line[12:] for line in out.splitlines()]


@pytest.fixture
def tree(tmp_path):
    root = tmp_path / "sample"
    root.mkdir()
    (root / "small").write_bytes(b"a" * 10)
    (root / "large").write_bytes(b"b" * 5000)
    (root / "emptydir").mkdir()
    (root / "sub").mkdir()
    (root / "sub" / "nested.txt").write_bytes(b"nested")
    (root / ".secret").write_bytes(b"hidden")
    (root / "space name-λ").write_bytes(b"unicode")
    return root


def test_help_documents_public_flags_and_exact_descriptions():
    p = run("--help")
    assert p.returncode == 0
    text = p.stdout.decode()
    for s in ("Pretty fast disk usage analyzer written in Go.",
              "gdu [directory_to_scan] [flags]", "Flags:",
              "--config-file string            Read config from file (default is $HOME/.gdu.yaml)",
              '-l, --log-file string               Path to a logfile (default "/dev/null")'):
        assert s in text
    options = ["--archive-browsing", "--collapse-path", "--config-file", "--db",
               "--depth", "--enable-profiling", "--exclude-type", "--follow-symlinks",
               "--help", "--ignore-dirs", "--ignore-dirs-pattern", "--ignore-from",
               "--input-file", "--log-file", "--max-age", "--max-cores", "--min-age",
               "--mouse", "--no-color", "--no-cross", "--no-delete", "--no-hidden",
               "--no-prefix", "--no-progress", "--no-spawn-shell", "--no-unicode",
               "--non-interactive", "--output-file", "--read-from-storage", "--reverse-sort",
               "--sequential", "--show-annexed-size", "--show-apparent-size", "--show-disks",
               "--show-in-kib", "--show-item-count", "--show-mtime", "--show-relative-size",
               "--si", "--since", "--summarize", "--top", "--type", "--until",
               "--version", "--write-config"]
    assert all(x in text for x in options)


def test_version_exact_shape():
    p = run("-v")
    assert p.returncode == 0
    lines = p.stdout.decode().splitlines()
    assert len(lines) == 3 and all(lines)
    assert [x.split("\t", 1)[0] for x in lines] == ["Version:", "Built time:", "Built user:"]


@pytest.mark.parametrize("args,fragment", [
    (("--wat",), "Error: unknown flag: --wat"),
    (("--depth",), "Error:"),
    (("--depth=abc",), 'Error: invalid argument "abc" for "--depth" flag: strconv.ParseInt: parsing "abc": invalid syntax'),
])
def test_flag_errors(args, fragment):
    p = run(*args)
    assert p.returncode == 1 and fragment in p.stderr.decode()
    assert not p.stdout


def test_missing_paths_are_stat_errors_with_absolute_path(tmp_path):
    p = run("missing", "-n", cwd=tmp_path)
    assert p.returncode == 1
    assert p.stderr.decode() == f"Error: stat {tmp_path / 'missing'}: no such file or directory\n"
    for name in ("help", "version", "list", "show", "add", "remove"):
        q = run(name, "-n", cwd=tmp_path)
        assert q.returncode == 1 and "stat " in q.stderr.decode()
        assert "unknown command" not in q.stderr.decode()


def test_empty_root_and_single_file(tree, tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    assert listing(empty) == ""
    assert listing(tree / "small") == ""


def test_plain_listing_shape_names_and_directory_status(tree):
    out = listing(tree)
    lines = out.splitlines()
    assert len(lines) == 6
    assert all(len(x) >= 13 and x[11] == " " for x in lines)
    assert "/sub" in row_names(out)
    assert "/emptydir" in row_names(out)
    assert "space name-λ" in row_names(out)
    assert "small" in row_names(out) and "large" in row_names(out)
    assert "nested.txt" not in out and ".secret" in out


def test_size_units_and_prefix_modes(tree):
    out = listing(tree)
    assert "KiB" in out and "large" in out
    si = listing(tree, "--si")
    assert "kB" in si
    kib = listing(tree, "-k")
    assert all("KiB" in row for row in kib.splitlines())
    exact = listing(tree, "--no-prefix")
    assert all(re.search(r"\s\d+ ", row) for row in exact.splitlines())
    p = run("-n", "--no-prefix", "--si", tree)
    assert p.returncode == 1 and p.stderr.decode() == "Error: --no-prefix and --si cannot be used at once\n"


def test_ordering_reverse_and_natural_name_ties(tmp_path):
    root = tmp_path / "ties"
    root.mkdir()
    for n in ("file1", "file2", "file10"):
        (root / n).write_bytes(b"x")
    assert row_names(listing(root)) == ["file10", "file2", "file1"]
    assert row_names(listing(root, "--reverse-sort")) == ["file1", "file2", "file10"]


def test_apparent_size_sparse_and_order_stays_disk_based(tmp_path):
    root = tmp_path / "sparse"
    root.mkdir()
    (root / "tiny_alloc").write_bytes(b"x" * 200)
    with (root / "sparse_big").open("wb") as f:
        f.seek(2_000_000)
        f.write(b"x")
    (root / "sparse_big").chmod(0o644)
    default = listing(root)
    apparent = listing(root, "-a")
    assert row_names(default) == row_names(apparent)
    assert "MiB" in apparent and "KiB" in default


def test_summary_depth_and_precedence(tree):
    summary = listing(tree, "-s")
    assert len(summary.splitlines()) == 1
    assert summary.rstrip().endswith(" sample")
    depth1 = listing(tree, "--depth", "1")
    assert str(tree) in depth1 and "/sub" in depth1 and "nested.txt" not in depth1
    depth2 = listing(tree, "--depth=2")
    assert "nested.txt" in depth2
    assert len(listing(tree, "--depth", "0").splitlines()) == len(listing(tree).splitlines())
    assert run("-n", "--depth", "-1", tree).returncode == 0
    top = listing(tree, "--top", "1", "--depth", "2", "-s")
    assert len(top.splitlines()) == 1 and "large" in top


def test_top_ranks_by_apparent_size_even_when_reverse(tmp_path):
    root = tmp_path / "top"
    root.mkdir()
    for name, n in (("one", 1), ("hundred", 100), ("thousand", 1000), ("two_thousand", 2000)):
        (root / name).write_bytes(bytes([65]) * n)
    out = listing(root, "--top", "2", "--reverse-sort")
    assert len(out.splitlines()) == 2
    assert "two_thousand" in out.splitlines()[0]
    assert "thousand" in out.splitlines()[1]


def test_hidden_literal_and_regex_ignores(tree):
    out = listing(tree, "-H")
    assert ".secret" not in out
    assert listing(tree, "-i", "small,large").find("small") == -1
    assert "small" not in listing(tree, "-i", "small", "-i", "large")
    assert "sub" not in listing(tree, "-I", "sub")
    assert "sub" in listing(tree, "-I", "sub,nomatch")
    assert "sub" not in listing(tree, "-I", "nomatch,sub")
    p = run("-n", "-I", "[unclosed", tree)
    assert p.returncode == 1 and "error parsing regexp" in p.stderr.decode()


def test_exclude_and_allow_type_lists(tree):
    assert "nested.txt" in listing(tree, "-T", "txt") or "/sub" in listing(tree, "-T", "txt")
    (tree / "readme.TXT").write_text("ok")
    assert "readme.TXT" in listing(tree, "-T", ".txt")
    out = listing(tree, "-E", "txt")
    assert "readme.TXT" not in out and "/sub" not in out
    both = listing(tree, "-T", "txt", "-E", "txt")
    assert "/sub" in both


@pytest.mark.parametrize("option,value", [("--max-age", "not-a-duration"), ("--min-age", "-7d"),
                                            ("--until", "2020-02-30"), ("--since", "not-a-date")],
                         ids=["max-age-invalid", "min-age-negative", "until-invalid-date", "since-invalid-date"])
def test_invalid_time_filters(option, value, tree):
    p = run("-n", option + "=" + value, tree)
    assert p.returncode == 1 and p.stderr.decode().startswith("Error: invalid time filter:")


def test_time_filters_select_recent_leaf(tmp_path):
    root = tmp_path / "ages"
    root.mkdir()
    old, new = root / "old", root / "new"
    old.write_text("old")
    new.write_text("new")
    os.utime(old, (1_000_000_000, 1_000_000_000))
    out = listing(root, "--max-age", "7d")
    assert "new" in out and "old" not in out


def test_symlink_policy_hardlinks_and_specials(tmp_path):
    root = tmp_path / "links"
    root.mkdir()
    target = root / "target"
    target.write_bytes(b"hello")
    os.link(target, root / "hard")
    (root / "filelink").symlink_to("target")
    (root / "broken").symlink_to("missing")
    (root / "dirlink").symlink_to(root, target_is_directory=True)
    os.mkfifo(root / "pipe")
    default = listing(root)
    assert "@" in default and "filelink" in default and "broken" in default
    assert "dirlink" in default
    assert "H" in default
    followed = listing(root, "-L")
    assert "broken" not in followed and "dirlink" not in followed
    assert "filelink" in followed
    assert "pipe" in default


def test_export_import_json_and_errors(tree, tmp_path):
    exported = tmp_path / "scan.json"
    p = run("-n", "-o", exported, tree)
    assert p.returncode == 0 and not p.stdout
    doc = json.loads(exported.read_text())
    assert isinstance(doc, list) and len(doc) >= 4
    assert doc[2]["progname"] == "gdu" and doc[2]["timestamp"] > 0
    assert doc[3][0]["name"] == str(tree)
    imported = listing("-f", exported)
    assert "large" in imported and "/sub" in imported
    assert len(listing("-f", exported, "--top", "1").splitlines()) > 1
    p = run("-f", "missing.json")
    assert p.returncode == 1 and "Error: opening input file:" in p.stderr.decode()
    p = run("-o", "-", tree)
    assert p.returncode == 0 and json.loads(p.stdout)[0:2] == [1, 2]
    p = run("-f", exported, "-o", "-")
    assert p.returncode == 1 and "reading analysis is not possible while exporting" in p.stderr.decode()


def test_import_top_level_and_structural_diagnostics():
    for data, phrase in (("", "EOF"), ("{}", "JSON file does not contain top level array"),
                         ("[1,2]", "top level array must have at least 4 items"),
                         ("[1,2,{},[]]", "directory name is not a string")):
        p = run("-f", "-", "-n", stdin=data)
        assert p.returncode == 1 and phrase.lower() in p.stderr.decode().lower()


def test_log_file_and_log_stdout(tree, tmp_path):
    log = tmp_path / "scan.log"
    p = run("-n", "-l", log, tree)
    assert p.returncode == 0 and log.exists()
    text = log.read_text()
    assert 'time="' in text and "level=" in text and "Analyzing path:" in text
    p = run("-n", "-l", "-", tree)
    assert p.returncode == 0 and b"Analyzing path:" in p.stdout and b"large" in p.stdout
    p = run("-n", "-l", tmp_path / "absent" / "log", tree)
    assert p.returncode == 1 and p.stderr.decode().startswith("Error: opening log file: open ")


def test_config_override_and_write_config(tree, tmp_path):
    config = tmp_path / "config.yaml"
    config.write_text('ignore-dirs: [small]\nno-hidden: true\n')
    out = listing(tree, "--config-file", config)
    assert "small" not in out and ".secret" not in out
    out = listing(tree, "--config-file", config, "-i", "")
    assert "small" in out
    p = run("-n", "--config-file", config, "--write-config", tree)
    assert p.returncode == 0
    doc = config.read_text()
    assert "style:" in doc and "sorting:" in doc


def test_disk_mode_table_and_export_conflict():
    p = run("-n", "-d")
    assert p.returncode == 0
    text = p.stdout.decode()
    for h in ("Device", "Size", "Used", "Free", "Used%", "Mount point"):
        assert h in text
    rows = [x for x in text.splitlines() if x.startswith("/dev/")]
    assert rows
    p = run("-n", "-d", "-o", "-")
    assert p.returncode != 0
    assert p.stderr.decode() == "Error: loading mount points: exporting devices list is not supported\n"
