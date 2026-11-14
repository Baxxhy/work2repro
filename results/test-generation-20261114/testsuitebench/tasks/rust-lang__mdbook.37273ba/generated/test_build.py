import json
import os
import pathlib
import re
import subprocess
import sys

import pytest

from conftest import make_book, run_mdbook


def test_build_without_book_toml_uses_defaults(tmp_path):
    root = make_book(tmp_path / "book")
    p = run_mdbook("build", root)
    assert p.returncode == 0, p.stderr
    assert (root / "book" / "index.html").is_file()
    html = (root / "book" / "index.html").read_text()
    assert '<html lang="en"' in html and "Hello world." in html
    assert (root / "book" / ".nojekyll").exists()
    assert "HTML book written to" in p.stderr


def test_missing_summary_is_operational_error(tmp_path):
    p = run_mdbook("build", tmp_path / "missing")
    assert p.returncode == 101 and p.stdout == ""
    assert "Couldn't open SUMMARY.md" in p.stderr
    assert "No such file or directory (os error 2)" in p.stderr


def test_cli_root_and_dest_dir_with_spaces(tmp_path):
    root = make_book(tmp_path / "root with spaces")
    out = tmp_path / "output with spaces"
    p = run_mdbook("build", "--dest-dir", out, root)
    assert p.returncode == 0, p.stderr
    assert (out / "index.html").is_file()
    assert not (root / "book").exists()


def test_build_relative_dest_is_book_root_relative(tmp_path):
    root = make_book(tmp_path / "book")
    p = run_mdbook("build", "-d", "../out", root)
    assert p.returncode == 0, p.stderr
    assert (tmp_path / "out" / "index.html").is_file()


def test_build_is_reproducible_and_clears_stale_output(tmp_path):
    root = make_book(tmp_path / "book")
    assert run_mdbook("build", root).returncode == 0
    (root / "book" / "stale.txt").write_text("stale")
    (root / "src" / "chapter_1.md").write_text("# Changed\n\nnew body\n")
    assert run_mdbook("build", root).returncode == 0
    assert not (root / "book" / "stale.txt").exists()
    assert "new body" in (root / "book" / "index.html").read_text()


def test_build_copies_non_markdown_assets_exactly(tmp_path):
    root = make_book(tmp_path / "book")
    asset = b"\x00\x01asset\xff"
    (root / "src" / "images").mkdir()
    (root / "src" / "images" / "raw.bin").write_bytes(asset)
    p = run_mdbook("build", root)
    assert p.returncode == 0, p.stderr
    assert (root / "book" / "images" / "raw.bin").read_bytes() == asset


def test_html_chapters_toc_navigation_and_assets(tmp_path):
    summary = "# Summary\n\n[Preface](preface.md)\n\n- [One](ch1.md)\n  - [Child](nested/ch2.md)\n\n- [Two](ch3.md)\n\n[Appendix](end.md)\n"
    chapters = {"preface.md": "# Preface\n", "ch1.md": "# One\n", "nested/ch2.md": "# Child\n",
                "ch3.md": "# Two\n", "end.md": "# Appendix\n"}
    root = make_book(tmp_path / "book", summary, chapters)
    p = run_mdbook("build", root)
    assert p.returncode == 0, p.stderr
    for path in ["index.html", "preface.html", "ch1.html", "nested/ch2.html", "ch3.html", "end.html",
                 "print.html", "toc.html", "toc.js", "book.js", "css/general.css", "searchindex.js"]:
        assert (root / "book" / path).is_file(), path
    html = (root / "book" / "ch1.html").read_text()
    assert 'rel="prev"' in html and 'rel="next prefetch"' in html
    assert "MDBookSidebarScrollbox" in (root / "book" / "toc.js").read_text()
    assert 'target="_parent"' in (root / "book" / "toc.html").read_text()


def test_summary_draft_part_separator_and_flattened_toc(tmp_path):
    summary = "# Summary\n\n- [*Italic* `code`](one.md)\n- [Draft]()\n\n# Part title\n\n---\n\n- [Last](last.md)\n"
    root = make_book(tmp_path / "book", summary, {"one.md": "# One\n", "last.md": "# Last\n"})
    p = run_mdbook("build", root)
    assert p.returncode == 0, p.stderr
    assert not (root / "book" / "Draft.html").exists()
    toc = (root / "book" / "toc.html").read_text()
    assert "Italic code" in toc and "<em>Italic</em>" not in toc and "<code>code</code>" not in toc
    assert "Part title" in toc and "class=\"spacer\"" in toc
    assert "Draft" in toc


def test_duplicate_summary_paths_fail(tmp_path):
    root = make_book(tmp_path / "book", "- [One](same.md)\n- [Two](same.md)\n", {"same.md": "# Same\n"})
    p = run_mdbook("build", root)
    assert p.returncode == 101
    assert "Duplicate file in SUMMARY.md: \"same.md\"" in p.stderr


def test_create_missing_chapter_default_and_disabled(tmp_path):
    root = tmp_path / "book"
    (root / "src").mkdir(parents=True)
    (root / "src" / "SUMMARY.md").write_text("- [New Chapter](nested/new.md)\n")
    p = run_mdbook("build", root)
    assert p.returncode == 0, p.stderr
    assert (root / "src" / "nested" / "new.md").read_text() == "# New Chapter\n"
    root2 = tmp_path / "disabled"
    (root2 / "src").mkdir(parents=True)
    (root2 / "src" / "SUMMARY.md").write_text("- [New](new.md)\n")
    (root2 / "book.toml").write_text("[build]\ncreate-missing = false\n")
    p2 = run_mdbook("build", root2)
    assert p2.returncode == 101 and "Chapter file not found, new.md" in p2.stderr


def test_invalid_utf8_chapter_fails(tmp_path):
    root = make_book(tmp_path / "book")
    (root / "src" / "chapter_1.md").write_bytes(b"\xff")
    p = run_mdbook("build", root)
    assert p.returncode == 101 and "valid UTF-8" in p.stderr


def test_markdown_backend_preserves_chapter_content(tmp_path):
    content = "# Unicode Ω\n\n**exact**\n\nlast"
    root = make_book(tmp_path / "book", config="[output.markdown]\n")
    (root / "src" / "chapter_1.md").write_text(content)
    p = run_mdbook("build", root)
    assert p.returncode == 0, p.stderr
    assert (root / "book" / "chapter_1.md").read_text() == content


def test_multiple_renderers_get_separate_destinations(tmp_path):
    root = make_book(tmp_path / "book", config="[output.html]\n[output.markdown]\n")
    p = run_mdbook("build", root)
    assert p.returncode == 0, p.stderr
    assert (root / "book" / "html" / "index.html").exists()
    assert (root / "book" / "markdown" / "chapter_1.md").exists()


def test_custom_renderer_receives_context_and_cwd(tmp_path):
    root = make_book(tmp_path / "book")
    script = root / "probe.py"
    script.write_text("import json,os,sys\nx=json.load(sys.stdin)\nopen('result.json','w').write(json.dumps({'cwd':os.getcwd(),'data':x}))\n")
    import json as json_module
    import sys as sys_module
    (root / "book.toml").write_text("[output.probe]\ncommand = " + json_module.dumps(sys_module.executable + " " + str(script)) + "\n")
    p = run_mdbook("build", root)
    assert p.returncode == 0, p.stderr
    data = json.loads((root / "book" / "result.json").read_text())
    assert data["cwd"] == str((root / "book").resolve())
    ctx = data["data"]
    assert ctx["version"] == "0.5.0-alpha.1"
    assert ctx["root"] == str(root.resolve()) and ctx["destination"] == str((root / "book").resolve())
    assert ctx["book"]["sections"]


def test_missing_required_and_optional_renderer(tmp_path):
    root = make_book(tmp_path / "book", config="[output.missing]\ncommand='definitely-no-such-mdbook-command-9213'\n")
    p = run_mdbook("build", root)
    assert p.returncode == 101 and "wasn't found" in p.stderr
    (root / "book.toml").write_text("[output.missing]\ncommand='definitely-no-such-mdbook-command-9213'\noptional=true\n")
    p2 = run_mdbook("build", root)
    assert p2.returncode == 0 and "marked as optional" in p2.stderr


def test_empty_book_and_empty_markdown(tmp_path):
    root = make_book(tmp_path / "book", summary="", chapters={})
    p = run_mdbook("build", root)
    assert p.returncode == 0, p.stderr
    assert (root / "book" / "print.html").exists()
    assert (root / "book" / "toc.html").exists()


def test_reserved_print_chapter_fails(tmp_path):
    root = make_book(tmp_path / "book", "- [Print](print.md)\n", {"print.md": "# Print\n"})
    p = run_mdbook("build", root)
    assert p.returncode == 101 and "print.md is reserved" in p.stderr


def test_markdown_heading_fences_tables_tasks_and_link_rewrites(tmp_path):
    content = "# Hello Ω!\n\n~~gone~~ **bold** and *em* `code` [read](README.md#top).\n\n```rust,edition2021\nfn main() {}\n```\n\n| A | B |\n|:--|--:|\n| x | y |\n\n- [x] done\n"
    root = make_book(tmp_path / "book", chapters={"chapter_1.md": content})
    p = run_mdbook("build", root)
    assert p.returncode == 0, p.stderr
    html = (root / "book" / "index.html").read_text()
    assert 'id="hello-ω"' in html.lower()
    assert "<del>gone</del>" in html and "<strong>bold</strong>" in html
    assert "language-rust edition2021" in html
    assert "table-wrapper" in html and 'type="checkbox"' in html and 'checked=""' in html
    assert 'href="README.html#top"' in html


def test_config_metadata_rtl_search_and_cname(tmp_path):
    config = '[book]\ntitle="T & Ω"\ndescription="A <book>"\nlanguage="ar"\n[output.html]\ncname="docs.example.test"\n'
    root = make_book(tmp_path / "book", config=config)
    p = run_mdbook("build", root)
    assert p.returncode == 0, p.stderr
    html = (root / "book" / "index.html").read_text()
    assert 'lang="ar"' in html and 'dir="rtl"' in html
    assert "T &amp; Ω" in html and 'name="description"' in html
    assert (root / "book" / "CNAME").read_bytes() == b"docs.example.test\n"
    assert (root / "book" / "searchindex.js").exists()


def test_additional_css_and_js_are_copied_in_order(tmp_path):
    root = make_book(tmp_path / "book", config='[output.html]\nadditional-css=["assets/a.css", "nested/b.css"]\nadditional-js=["js/c.js"]\n')
    for rel, data in [("assets/a.css", b"a{}"), ("nested/b.css", b"b{}"), ("js/c.js", b"c")]:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    p = run_mdbook("build", root)
    assert p.returncode == 0, p.stderr
    out = root / "book"
    assert (out / "assets/a.css").read_bytes() == b"a{}"
    html = (out / "index.html").read_text()
    assert html.index("assets/a.css") < html.index("nested/b.css")
    assert (out / "js/c.js").read_bytes() == b"c"


def test_theme_override_bytes_and_head_insertion(tmp_path):
    root = make_book(tmp_path / "book")
    theme = root / "theme"
    theme.mkdir()
    (theme / "head.hbs").write_text("<meta name=\"custom\" content=\"yes\">\n")
    (theme / "css").mkdir()
    (theme / "css" / "general.css").write_bytes(b"custom-css")
    p = run_mdbook("build", root)
    assert p.returncode == 0, p.stderr
    assert (root / "book" / "css" / "general.css").read_bytes() == b"custom-css"
    assert 'name="custom" content="yes"' in (root / "book" / "index.html").read_text()


def test_redirect_and_nonmatching_redirect_fragment_error(tmp_path):
    root = make_book(tmp_path / "book", config='[output.html.redirect]\n"deprecated/guide.html"="guide.html"\n')
    p = run_mdbook("build", root)
    assert p.returncode == 0, p.stderr
    redir = (root / "book" / "deprecated" / "guide.html").read_text()
    assert 'content="0; URL=guide.html"' in redir and 'href="guide.html"' in redir
    root2 = make_book(tmp_path / "other", config='[output.html.redirect]\n"old.html#frag"="new.html#frag"\n')
    p2 = run_mdbook("build", root2)
    assert p2.returncode == 101 and "only has source paths" in p2.stderr


def test_environment_overrides_and_cli_precedence(tmp_path):
    root = make_book(tmp_path / "book", config='[book]\ntitle="from toml"\n')
    env = {"MDBOOK_BOOK__TITLE": "from env"}
    p = run_mdbook("build", root, env=env)
    assert p.returncode == 0, p.stderr
    assert "from env" in (root / "book" / "index.html").read_text()


def test_invalid_toml_is_fatal(tmp_path):
    root = make_book(tmp_path / "book", config="[book\n")
    p = run_mdbook("build", root)
    assert p.returncode == 101 and "Invalid configuration file" in p.stderr
    assert "unclosed table" in p.stderr


def test_invalid_configuration_types_fail_or_log_recoverably(tmp_path):
    root = make_book(tmp_path / "book", config="[book]\ntitle=42\n")
    p = run_mdbook("build", root)
    assert p.returncode == 101 and "expected a string" in p.stderr
    root2 = make_book(tmp_path / "other", config='[output.html]\nno-section-label="yes"\n')
    p2 = run_mdbook("build", root2)
    assert p2.returncode == 0 and "Couldn't deserialize the value" in p2.stderr


def test_index_preprocessor_readme_mapping(tmp_path):
    root = make_book(tmp_path / "book", "- [Readme](README.md)\n", {"README.md": "# Readme\n"})
    p = run_mdbook("build", root)
    assert p.returncode == 0, p.stderr
    assert (root / "book" / "index.html").exists()
    assert not (root / "book" / "README.html").exists()
