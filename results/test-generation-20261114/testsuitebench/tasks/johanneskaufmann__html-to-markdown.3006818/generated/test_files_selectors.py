from conftest import invoke


def test_single_file_and_output_contract(exe, tmp_path):
    source = tmp_path / "unicode name.with.dots.data"
    source.write_text("<b>File</b>", encoding="utf-8")
    r = invoke(exe, "--input", source)
    assert r.returncode == 0 and r.stdout == b"**File**\n"
    out = tmp_path / "nested" / "result.md"
    r = invoke(exe, f"--input={source}", f"--output={out}")
    assert r.returncode == 0 and r.stdout == b"" and out.read_bytes() == b"**File**"


def test_output_overwrite_and_symlink(exe, tmp_path):
    source = tmp_path / "in"
    source.write_text("new", encoding="utf-8")
    target = tmp_path / "target"
    target.write_bytes(b"old")
    r = invoke(exe, "--input", source, "--output", target)
    assert r.returncode == 1 and target.read_bytes() == b"old" and b"already exists" in r.stderr
    r = invoke(exe, "--input", source, "--output", target, "--output-overwrite")
    assert r.returncode == 0 and target.read_bytes() == b"new"
    real = tmp_path / "real"
    real.write_bytes(b"before")
    link = tmp_path / "link"
    link.symlink_to(real)
    r = invoke(exe, "--input", source, "--output", link, "--output-overwrite")
    assert r.returncode == 0 and link.is_symlink() and real.read_bytes() == b"new"


def test_input_symlink_directory_rejection_and_long_path(exe, tmp_path):
    original = tmp_path / "actual.bin"
    original.write_text("linked", encoding="utf-8")
    link = tmp_path / "shortcut"
    link.symlink_to(original)
    r = invoke(exe, "--input", link)
    assert r.returncode == 0 and r.stdout == b"linked\n"
    r = invoke(exe, "--input", tmp_path)
    assert r.returncode == 1 and b"is a directory, not a file" in r.stderr
    longbase = "x" * 205 + ".html"
    longfile = tmp_path / longbase
    longfile.write_text("long", encoding="utf-8")
    r = invoke(exe, "--input", longfile)
    assert r.returncode == 0 and r.stdout == b"long\n"


def test_directory_output_and_glob_extension_handling(exe, tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.html").write_text("A", encoding="utf-8")
    (src / "plain").write_text("B", encoding="utf-8")
    dest = tmp_path / "dest"
    pattern = str(src / "*")
    r = invoke(exe, "--input", pattern, "--output", str(dest) + "/")
    assert r.returncode == 0
    assert (dest / "a.md").read_bytes() == b"A"
    assert (dest / "plain.md").read_bytes() == b"B"


def test_zero_match_and_multiple_input_need_directory(exe, tmp_path):
    missing = str(tmp_path / "nothing-*.html")
    r = invoke(exe, "--input", missing)
    assert r.returncode == 1 and b"no files found matching pattern" in r.stderr
    a, b = tmp_path / "a", tmp_path / "b"
    a.write_text("a"); b.write_text("b")
    r = invoke(exe, "--input", str(tmp_path / "*"))
    assert r.returncode == 1 and b"--output needs to be a directory" in r.stderr


def test_selector_include_exclude_union_and_groups(exe):
    html = '<div class="container"><p class="content one">A<b>! </b></p><p id="x" data-exclude="true">B</p><p class="content">C</p></div><p>D</p>'
    r = invoke(exe, "--include-selector", ".container .content, #x", "--exclude-selector", '[data-exclude="true"]', html=html)
    assert r.returncode == 0 and r.stdout == b"A**! **\n\nC\n"


def test_selector_invalid_empty_and_nonmatching(exe):
    for selector, message in (("", b"empty string"), ("[", b"invalid css selector")):
        r = invoke(exe, "--include-selector", selector, html="<p>X</p>")
        assert r.returncode == 1 and message in r.stderr
    r = invoke(exe, "--include-selector", "#missing", html="<p>X</p>")
    assert r.returncode == 0 and r.stdout == b"\n"
    r = invoke(exe, "--exclude-selector", ".missing", html="<p>X</p>")
    assert r.returncode == 0 and r.stdout == b"X\n"


def test_domain_last_wins_and_empty_href(exe):
    r = invoke(exe, "--domain", "https://one.example/a", "--domain", "https://two.example/base", html='<a href="">x</a>')
    assert r.returncode == 0 and r.stdout == b"[x](https://two.example)\n"
