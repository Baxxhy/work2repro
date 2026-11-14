import os
import re
import socket
from pathlib import Path


def out(result):
    assert result.stderr == b""
    assert result.returncode == 0
    return result.stdout.decode("utf-8")


def test_help_and_version(invoke):
    h = invoke("--help")
    assert h.returncode == 0 and not h.stderr
    help_text = h.stdout.decode()
    assert help_text.startswith("Usage: executable [OPTIONS] [PATHS]...")
    for section in ("Arguments:", "Options:", "Detail view:", "Grid view:", "Presentation:", "Filtering:", "Sorting:"):
        assert section in help_text
    assert "--det" in help_text and "--grid" in help_text and "[PATHS]..." in help_text
    v = invoke("--version")
    assert v.returncode == 0 and not v.stderr
    text = v.stdout.decode()
    assert re.fullmatch(r"pls (?=[^\n]*\d)(?=[^\n]*\.)[^\n]+\n", text)


def test_default_hidden_listing_and_empty_result(invoke, tmp_path):
    (tmp_path / "plain").touch()
    (tmp_path / ".hidden").touch()
    (tmp_path / ".DS_Store").touch()
    (tmp_path / ".git").mkdir()
    got = out(invoke())
    assert "plain" in got and ".hidden" in got
    assert ".DS_Store" not in got and ".git" not in got
    empty = tmp_path / "empty"
    empty.mkdir()
    assert out(invoke(empty)) == ""


def test_dot_alignment_icons_suffixes_and_unicode(invoke, tmp_path):
    for name in (".config", "..dotdot", "normal.txt", "日本語", "café", "😀"):
        (tmp_path / name).touch()
    aligned = out(invoke("--icon=false", "--suffix=false"))
    assert ".config\n" in aligned and "..dotdot\n" in aligned
    assert " normal.txt\n" in aligned
    assert all(n in aligned for n in ("日本語", "café", "😀"))
    plain = out(invoke("--icon=false", "--suffix=false", "--align=false"))
    assert "normal.txt\n" in plain and " normal.txt\n" not in plain
    icon = out(invoke("--sort=name"))
    assert "" in icon and "" not in icon  # no directories in this fixture


def test_direct_operands_order_and_lexical_spelling(invoke, tmp_path):
    (tmp_path / "one.txt").touch()
    (tmp_path / "two.txt").touch()
    (tmp_path / "dir").mkdir()
    (tmp_path / "dir" / "kid").touch()
    got = out(invoke("--sort=name", "./two.txt", "dir", "./one.txt"))
    assert got.index("./two.txt") < got.index("./one.txt")
    assert "dir:\n" in got and "kid" in got
    assert got.index("./two.txt") < got.index("dir:") < got.index("./one.txt") or got.index("./two.txt") < got.index("./one.txt") < got.index("dir:")


def test_directory_sections_and_path_errors(invoke, tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir(); b.mkdir(); (a / "x").touch()
    got = out(invoke("a", "b"))
    assert "\na:\n" in got and "\nb:\n" in got
    missing = out(invoke("absent", "a", "gone"))
    assert "absent:\n\terror: No such file or directory (os error 2)\n" in missing
    assert "gone:\n\terror: No such file or directory (os error 2)\n" in missing
    assert "a:" in missing


def test_symlink_lstat_targets_and_direct_link(invoke, tmp_path):
    (tmp_path / "target.txt").write_text("ok")
    (tmp_path / "link.txt").symlink_to("target.txt")
    (tmp_path / "broken").symlink_to("missing")
    (tmp_path / "cycle1").symlink_to("cycle2")
    (tmp_path / "cycle2").symlink_to("cycle1")
    got = out(invoke("--sort=name"))
    assert "link.txt@" in got and "target.txt" in got
    assert "broken@" in got and "missing" in got
    assert "cycle1@" in got and "cycle2@" in got
    hidden = out(invoke("--sym=false", "--suffix=false"))
    assert "link.txt" in hidden and "target.txt" not in hidden
    direct = out(invoke("link.txt"))
    assert direct.count("link.txt") == 1


def test_types_regex_and_importance(invoke, tmp_path):
    (tmp_path / "alpha.txt").touch(); (tmp_path / "test[1].txt").touch()
    (tmp_path / ".dot").touch(); (tmp_path / "folder").mkdir()
    assert "alpha.txt" in out(invoke("--only", "(?i)ALPHA"))
    assert "test[1].txt" in out(invoke("--only=test\\["))
    selected = out(invoke("--typ=file", "--exclude=\\.txt$"))
    assert ".dot" in selected and "alpha.txt" not in selected
    assert "folder" not in out(invoke("--typ=file"))
    assert "folder" in out(invoke("--typ=none", "--typ=dir"))
    baseline = out(invoke("--imp=1"))
    assert "alpha.txt" in baseline and ".dot" not in baseline
    assert ".dot" in out(invoke("--imp=0"))


def test_detail_columns_permissions_and_units(invoke, tmp_path):
    f = tmp_path / "sample.txt"; f.write_bytes(b"a" * 1536); f.chmod(0o4755)
    empty = tmp_path / "zero"; empty.touch()
    got = out(invoke("--det=typ", "--det=oct", "--det=size", "--sort=name"))
    assert "T" in got and "SUGO" in got and "Size" in got and "Name" in got
    assert "f" in got and "4755" in got and "1.5 KiB" in got
    no_units = out(invoke("--det=size", "--unit=none"))
    assert "1536 B" in no_units
    standard_empty = tmp_path / "emptydir"; standard_empty.mkdir()
    assert out(invoke("--det=std", standard_empty)) == "Link# T Permissions User Group Size Modified Name\n"
    no_header = out(invoke("--det=typ", "--header=false"))
    assert not no_header.startswith("T Name") and "f" in no_header


def test_detail_order_sets_and_size_directory_blank(invoke, tmp_path):
    (tmp_path / "f").touch(); (tmp_path / "dir").mkdir()
    out_text = out(invoke("--det=std", "--det=none", "--det=size", "--det=blocks"))
    assert out_text.splitlines()[0].startswith("Size") and "Blocks" in out_text.splitlines()[0]
    lines = out(invoke("--det=size", "--sort=name")).splitlines()
    assert any("dir/" in line and not re.search(r"\d+\.\d+", line) for line in lines[1:])


def test_sort_name_extension_size_and_type(invoke, tmp_path):
    for n in ("z.txt", "A.txt", "a.txt", ".hidden", "b.rs", "file.tar.gz"):
        (tmp_path / n).touch()
    by_name = out(invoke("--icon=false", "--suffix=false", "--sort=name"))
    names = [line.strip() for line in by_name.splitlines()]
    assert names == sorted(names)
    by_ext = out(invoke("--icon=false", "--suffix=false", "--sort=ext", "--sort=name"))
    assert by_ext.index(".hidden") < by_ext.index("file.tar.gz") < by_ext.index("b.rs") < by_ext.index("A.txt")
    (tmp_path / "large").write_bytes(b"123456789")
    sizes = out(invoke("--sort=size", "--icon=false", "--suffix=false"))
    assert sizes.index(".hidden") < sizes.index("large")


def test_collapse_relationship_and_grid(invoke, tmp_path):
    for n in ("Cargo.toml", "Cargo.lock", "lib.rs", "README.md"):
        (tmp_path / n).touch()
    collapsed = out(invoke("--sort=name"))
    assert "Cargo.toml" in collapsed and "└─" in collapsed and "Cargo.lock" in collapsed
    flat = out(invoke("--collapse=false", "--sort=name"))
    assert "└─" not in flat
    grid = out(invoke("--grid=true", "--collapse=true", "--icon=false", "--suffix=false", env={"PLS_COLUMNS": "15"}))
    assert "└─" not in grid and "Cargo.lock" in grid


def test_grid_width_and_direction(invoke, tmp_path):
    for i in range(1, 21):
        (tmp_path / f"file{i}.txt").touch()
    narrow = out(invoke("--grid=true", env={"PLS_COLUMNS": "15"}))
    assert len(narrow.splitlines()) == 20
    wide = out(invoke("--grid=true", env={"PLS_COLUMNS": "100"}))
    assert len(wide.splitlines()) <= 4
    down = out(invoke("--grid=true", "--down=true", env={"PLS_COLUMNS": "40"}))
    assert len(down.splitlines()) > 0 and all(f"file{i}.txt" in down for i in range(1, 21))


def test_custom_configuration_merge_and_recoverable_yaml_error(invoke, tmp_path):
    (tmp_path / "alpha").touch()
    (tmp_path / ".pls.yml").write_text("icons:\n  custom: '🔥'\nspecs:\n  - pattern: '^alpha$'\n    icons: [custom]\n", encoding="utf-8")
    got = out(invoke("--icon=true", "--suffix=false"))
    assert "🔥" in got
    (tmp_path / ".pls.yml").write_text("icons:\n  bad: [unclosed\n", encoding="utf-8")
    err = out(invoke())
    assert ".:\n\terror: did not find expected ',' or ']'" in err
    assert "in .pls.yml YAML file" in err


def test_validation_errors(invoke):
    for args in (("--unit=invalid",), ("--icon=TRUE",), ("--det=invalid",), ("--typ=invalid",), ("--sort=invalid",), ("--only=[a-z",), ("--exclude=[invalid",), ("--unknown-flag",)):
        result = invoke(*args)
        assert result.returncode == 2
        assert result.stdout == b""
        assert result.stderr
    assert b"[possible values: binary, decimal, none]" in invoke("--unit=invalid").stderr
    imp = invoke("--imp=999")
    assert imp.returncode == 2 and b"999 is not in -128..=127" in imp.stderr
    neg = invoke("--imp", "-2")
    assert neg.returncode == 2 and b"unexpected argument" in neg.stderr


def test_unsupported_reverse_sort_compatibility(invoke, tmp_path):
    (tmp_path / "x").touch()
    for key in ("inode_", "nlinks_"):
        result = invoke(f"--sort={key}")
        assert result.returncode != 0
        assert b"panicked at src/enums/sort_field.rs" in result.stderr
        assert b"internal error: entered unreachable code: src/enums/sort_fields.rs / impl SortField / cmp_time" in result.stderr


def test_many_entries_and_filename_limits(invoke, tmp_path):
    long_name = "n" * 255
    (tmp_path / long_name).touch()
    for i in range(120):
        (tmp_path / f"entry{i:03}.txt").touch()
    got = out(invoke("--icon=false", "--suffix=false", "--sort=name"))
    assert long_name in got
    assert sum(1 for line in got.splitlines() if "entry" in line) == 120
