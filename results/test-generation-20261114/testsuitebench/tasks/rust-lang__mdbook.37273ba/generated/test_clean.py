import pathlib

from conftest import make_book, run_mdbook


def test_clean_removes_output_and_preserves_source(tmp_path):
    root = make_book(tmp_path / "book", config='[book]\ntitle="Keep me"\n')
    assert run_mdbook("build", root).returncode == 0
    marker = root / "other"
    marker.mkdir()
    (marker / "keep").write_text("yes")
    p = run_mdbook("clean", root)
    assert p.returncode == 0, p.stderr
    assert not (root / "book").exists()
    assert (root / "book.toml").read_text() == '[book]\ntitle="Keep me"\n'
    assert (root / "src" / "SUMMARY.md").exists()
    assert (marker / "keep").exists()
    assert p.stdout.startswith("Removed ") and p.stdout.endswith(" total\n")


def test_clean_valid_book_without_output_reports_zero(tmp_path):
    root = make_book(tmp_path / "book")
    p = run_mdbook("clean", root)
    assert p.returncode == 0 and p.stdout == "Removed 0 files\n"


def test_clean_requires_summary(tmp_path):
    p = run_mdbook("clean", tmp_path / "missing")
    assert p.returncode == 101 and "Couldn't open SUMMARY.md" in p.stderr


def test_clean_cli_relative_destination_is_relative_to_cwd(tmp_path):
    cwd = tmp_path / "cwd"
    root = make_book(cwd / "root")
    (root / "chosen").mkdir()
    (root / "chosen" / "marker").write_text("retain")
    p = run_mdbook("clean", "--dest-dir", "chosen", root, cwd=cwd)
    assert p.returncode == 0 and p.stdout == "Removed 0 files\n"
    assert (root / "chosen" / "marker").exists()


def test_clean_directory_count_and_binary_size_units(tmp_path):
    root = make_book(tmp_path / "book")
    dest = root / "book"
    (dest / "a" / "b").mkdir(parents=True)
    p = run_mdbook("clean", root)
    assert p.returncode == 0 and p.stdout == "Removed 3 directories, 12.00KiB total\n"
    dest.mkdir()
    (dest / "large").write_bytes(b"x" * (2 * 1024 * 1024))
    p2 = run_mdbook("clean", root)
    assert p2.returncode == 0 and p2.stdout == "Removed 1 file, 2.00MiB total\n"
