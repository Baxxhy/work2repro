import json
import pathlib
import sys

from conftest import make_book, run_mdbook


def executable_script(path, text):
    path.write_text("#!/usr/bin/env python3\n" + text)
    path.chmod(0o755)


def test_links_include_ranges_and_playground(tmp_path):
    root = make_book(tmp_path / "book", chapters={"chapter_1.md": "# Chapter\n\n{{#include parts.txt:2:3}}\n\n{{#playground demo.rs editable}}\n"})
    (root / "src" / "parts.txt").write_text("first\nsecond\nthird\nfourth\n")
    (root / "src" / "demo.rs").write_text("fn main() { println!(\"ok\"); }\n")
    p = run_mdbook("build", root)
    assert p.returncode == 0, p.stderr
    html = (root / "book" / "index.html").read_text()
    assert "second\nthird" in html
    assert "println" in html and "language-rust" in html


def test_links_cycle_warns_without_failing(tmp_path):
    root = make_book(tmp_path / "book", chapters={"chapter_1.md": "# Chapter\n\n{{#include recursive.txt}}\n"})
    (root / "src" / "recursive.txt").write_text("{{#include recursive.txt}}\n")
    p = run_mdbook("build", root)
    assert p.returncode == 0
    assert "Stack depth exceeded in chapter_1.md. Check for cyclic includes" in p.stderr


def test_custom_preprocessor_supports_and_transforms_book(tmp_path):
    root = make_book(tmp_path / "book")
    script = root / "processor.py"
    executable_script(script, '''import json,sys
if sys.argv[1:] == ['supports','html']: sys.exit(0)
ctx,book=json.load(sys.stdin)
book['sections'][0]['Chapter']['content'] += "\\nTRANSFORMED"
json.dump(book,sys.stdout)
''')
    import json as json_module
    import sys as sys_module
    (root / "book.toml").write_text("[preprocessor.transform]\ncommand=" + json_module.dumps(sys_module.executable + " " + str(script)) + "\n")
    # Renderer process cwd differs from the book root; preprocessors use process cwd.
    p = run_mdbook("build", root, cwd=tmp_path)
    assert p.returncode == 0, p.stderr
    assert "TRANSFORMED" in (root / "book" / "index.html").read_text()


def test_custom_preprocessor_book_root_relative_executable_is_not_rebased(tmp_path):
    root = make_book(tmp_path / "book", config="[preprocessor.transform]\ncommand='./processor.py'\n")
    executable_script(root / "processor.py", "import sys\nsys.exit(0)\n")
    p = run_mdbook("build", root, cwd=tmp_path)
    assert p.returncode == 0, p.stderr
    assert "wasn't found" in p.stderr


def test_preprocessor_dependency_cycle_fails(tmp_path):
    config = "[preprocessor.a]\nbefore=['b']\ncommand='python3 a.py'\n[preprocessor.b]\nbefore=['a']\ncommand='python3 b.py'\n"
    root = make_book(tmp_path / "book", config=config)
    # An ordering cycle is rejected before processor execution.
    p = run_mdbook("build", root)
    assert p.returncode == 101 and "Cyclic dependency detected in preprocessors" in p.stderr
