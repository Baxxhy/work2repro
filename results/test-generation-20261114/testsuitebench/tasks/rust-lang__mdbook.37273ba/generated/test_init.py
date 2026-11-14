import pathlib
import re

from conftest import run_mdbook


def test_force_init_scaffold_and_summary(tmp_path):
    root = tmp_path / "nested book"
    p = run_mdbook("init", "--force", root)
    assert p.returncode == 0, p.stderr
    assert (root / "src" / "SUMMARY.md").read_text() == "# Summary\n\n- [Chapter 1](./chapter_1.md)\n"
    assert (root / "src" / "chapter_1.md").read_text() == "# Chapter 1\n"
    config = (root / "book.toml").read_text()
    assert '[book]\nauthors = [' in config
    assert 'language = "en"\nsrc = "src"\n' in config
    assert p.stdout.endswith("All done, no errors...\n")
    assert re.search(r"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d \[INFO\].*Creating a new book with stub content", p.stderr)


def test_force_init_title_round_trips_toml(tmp_path):
    root = tmp_path / "title"
    title = 'A "quoted"\\line\n第二'
    p = run_mdbook("init", "--force", "--title", title, root)
    assert p.returncode == 0, p.stderr
    config = (root / "book.toml").read_text()
    assert "title = " in config
    import tomllib
    assert tomllib.loads(config)["book"]["title"] == title


def test_force_init_repeated_preserves_unrelated_files(tmp_path):
    root = tmp_path / "repeat"
    root.mkdir()
    (root / "keep.txt").write_text("keep")
    assert run_mdbook("init", "--force", root).returncode == 0
    assert run_mdbook("init", "--force", root).returncode == 0
    assert (root / "keep.txt").read_text() == "keep"


def test_init_ignore_option(tmp_path):
    root = tmp_path / "ignored"
    p = run_mdbook("init", "--force", "--ignore", "git", root)
    assert p.returncode == 0, p.stderr
    assert (root / ".gitignore").read_text() == "book\n"


def test_init_explicit_empty_title_differs_from_omitted(tmp_path):
    root = tmp_path / "empty-title"
    p = run_mdbook("init", "--force", "--title", "", root)
    assert p.returncode == 0, p.stderr
    assert 'title = ""' in (root / "book.toml").read_text()


def test_init_existing_summary_preserved_and_missing_link_created(tmp_path):
    root = tmp_path / "existing"
    src = root / "src"
    src.mkdir(parents=True)
    summary = "# Summary\n\n- [Start](intro.md)\n\n- [Part](part/one.md)\n"
    (src / "SUMMARY.md").write_text(summary)
    (src / "intro.md").write_text("existing\n")
    p = run_mdbook("init", "--force", root)
    assert p.returncode == 0, p.stderr
    assert (src / "SUMMARY.md").read_text() == summary
    assert (src / "intro.md").read_text() == "existing\n"
    assert (src / "part" / "one.md").read_text() == "# Part\n"
    assert not (src / "chapter_1.md").exists()


def test_init_theme_has_real_assets(tmp_path):
    root = tmp_path / "theme-book"
    p = run_mdbook("init", "--force", "--theme", root)
    assert p.returncode == 0, p.stderr
    for name in ["index.hbs", "book.js", "highlight.js", "highlight.css", "css/chrome.css",
                 "css/general.css", "css/print.css", "css/variables.css", "favicon.png",
                 "favicon.svg", "fonts/fonts.css"]:
        assert (root / "theme" / name).is_file()
        assert (root / "theme" / name).stat().st_size > 0
    assert len(list((root / "theme" / "fonts").glob("*.woff2"))) >= 10
    assert "<!DOCTYPE HTML>" in (root / "theme" / "index.hbs").read_text()
    js = (root / "theme" / "book.js").read_text()
    assert "'use strict';" in js and "playground_text" in js

