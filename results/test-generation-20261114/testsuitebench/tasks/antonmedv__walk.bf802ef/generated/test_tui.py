import os
import time
from pathlib import Path

import pytest


def finish(t, key=b"q"):
    t.send(key)
    deadline = time.monotonic() + 2
    while t.proc.poll() is None and time.monotonic() < deadline:
        t.read_for(.1)
    assert t.proc.poll() is not None, "TUI did not exit promptly"
    return t.text


def make_listing(root):
    (root / "aaa_file.txt").write_text("alpha\n")
    (root / "bbb_dir").mkdir()
    (root / "ccc_file.txt").write_text("charlie\n")
    (root / "ddd_dir").mkdir()
    (root / ".hidden").write_text("hidden\n")
    (root / "has space!.txt").write_text("space\n")
    try:
        (root / "zzz_symlink").symlink_to(root / "bbb_dir", target_is_directory=True)
    except OSError:
        pass


def test_start_path_listing_sorted_and_hidden_visible(tmp_path, terminal_factory):
    make_listing(tmp_path)
    t = terminal_factory(args=(str(tmp_path),), rows=30, cols=100)
    screen = t.read_for(.5)
    assert f"\n{tmp_path}\n" in screen
    order = [screen.find(n) for n in [".hidden", "aaa_file.txt", "bbb_dir/", "ccc_file.txt", "ddd_dir/", "has space!.txt"]]
    assert all(i >= 0 for i in order)
    assert order == sorted(order)
    finish(t)


def test_dir_only_and_hide_hidden_compose(tmp_path, terminal_factory):
    make_listing(tmp_path)
    t = terminal_factory(args=("--dir-only", "--hide-hidden", str(tmp_path)))
    screen = t.read_for(.5)
    assert "bbb_dir/" in screen and "ddd_dir/" in screen
    assert "aaa_file.txt" not in screen and ".hidden" not in screen
    finish(t)


def test_relative_start_path_and_exit_with_cd(tmp_path, terminal_factory):
    (tmp_path / "child").mkdir()
    t = terminal_factory(args=("child",), cwd=str(tmp_path))
    assert f"\n{tmp_path}/child\n" in t.read_for(.4)
    finish(t)
    assert t.proc.stdout is None  # terminal output was attached to the PTY


def test_enter_and_backspace_navigate_and_q_returns_current_path(tmp_path, terminal_factory):
    child = tmp_path / "child"
    child.mkdir()
    (child / "leaf").write_text("x")
    t = terminal_factory(args=(str(tmp_path),))
    t.read_for(.3)
    t.send("\r")
    assert f"\n{child}\n" in t.read_for(.3)
    t.send("\x7f")
    assert f"\n{tmp_path}\n" in t.read_for(.3)
    t.send("q")
    deadline = time.monotonic() + 2
    while t.proc.poll() is None and time.monotonic() < deadline:
        t.read_for(.1)
    assert t.proc.returncode == 0
    assert str(tmp_path).encode() + b"\r\n" in bytes(t.data)


def test_vim_navigation_and_unbound_key_do_not_exit(tmp_path, terminal_factory):
    make_listing(tmp_path)
    t = terminal_factory(args=(str(tmp_path),))
    t.read_for(.3)
    t.send("z123")
    assert t.proc.poll() is None
    t.send("jjkkhl")
    assert t.proc.poll() is None
    finish(t, b"\x03")


def test_runtime_hidden_toggle_and_empty_state(tmp_path, terminal_factory):
    (tmp_path / ".only").write_text("x")
    t = terminal_factory(args=(str(tmp_path),))
    screen = t.read_for(.3)
    assert ".only" in screen
    screen = t.send(".")
    assert "No files" in screen
    finish(t)


def test_help_view_toggle_and_empty_directory(tmp_path, terminal_factory):
    t = terminal_factory(args=(str(tmp_path),))
    screen = t.read_for(.3)
    assert "No files" in screen
    screen = t.send("?")
    for text in ["help", "arrows, hjkl  Move cursor", "ctrl+c        Exit without cd", "?             Show help"]:
        assert text in screen
    screen = t.send("?")
    assert str(tmp_path) in screen and "No files" in screen
    finish(t)


def test_explicit_fuzzy_search_header_matching_and_backspace(tmp_path, terminal_factory):
    (tmp_path / "config-file.txt").write_text("x")
    (tmp_path / "other.txt").write_text("x")
    t = terminal_factory(args=(str(tmp_path),))
    t.read_for(.3)
    screen = t.send("/con")
    assert f"{tmp_path}/con" in screen
    assert "config-file.txt" in screen
    t.send("\x7f")
    screen = t.read_for(.2)
    assert f"{tmp_path}/co" in screen
    finish(t)


def test_fuzzy_default_accepts_printable_query_and_exits_after_timeout(tmp_path, terminal_factory):
    (tmp_path / "config-file.txt").write_text("x")
    t = terminal_factory(args=("--fuzzy", str(tmp_path)))
    t.read_for(.3)
    screen = t.send("con")
    assert f"{tmp_path}/con" in screen
    assert "config-file.txt" in screen
    screen = t.read_for(2.4)
    assert f"\n{tmp_path}\n" in screen
    finish(t)


def test_preview_shows_directory_children_and_border_flag(tmp_path, terminal_factory):
    (tmp_path / "adir").mkdir()
    ((tmp_path / "adir") / "inside.txt").write_text("preview text")
    t = terminal_factory(args=("--preview", "--with-border", str(tmp_path)))
    screen = t.read_for(.5)
    assert "adir/" in screen
    assert "inside.txt" in screen
    assert "│" in screen
    finish(t)


def test_file_text_preview_tracks_selection(tmp_path, terminal_factory):
    (tmp_path / "aaa.txt").write_text("first readable line\n")
    (tmp_path / "bbb.txt").write_text("second readable line\n")
    t = terminal_factory(args=("--preview", str(tmp_path)))
    screen = t.read_for(.4)
    assert "first readable line" in screen
    screen = t.send("j")
    assert "second readable line" in screen
    finish(t)


@pytest.mark.parametrize("flags", [("--icons",), ("--preview", "--icons")], ids=["icons", "icons-preview"])
def test_icons_visible_when_enabled(tmp_path, terminal_factory, flags):
    (tmp_path / "folder").mkdir()
    (tmp_path / "file.txt").write_text("x")
    t = terminal_factory(args=(*flags, str(tmp_path)))
    screen = t.read_for(.4)
    assert "" in screen and "" in screen
    finish(t)


def test_nonexistent_start_path_renders_error_box_and_can_quit(tmp_path, terminal_factory):
    missing = tmp_path / "not-here"
    t = terminal_factory(args=(str(missing),))
    screen = t.read_for(.4)
    assert f"\n{missing}\n" in screen
    assert "╭" in screen and f"open {missing}: no such file or directory" in screen
    finish(t)


def test_regular_file_start_path_renders_not_directory_error(tmp_path, terminal_factory):
    f = tmp_path / "ordinary.txt"
    f.write_text("x")
    t = terminal_factory(args=(str(f),))
    screen = t.read_for(.4)
    assert f"readdirent {f}: not a directory" in screen
    finish(t)


def test_status_expression_and_padding_render_as_last_line(tmp_path, terminal_factory):
    (tmp_path / "item").write_text("x")
    t = terminal_factory(args=(str(tmp_path),), env={
        "WALK_STATUS_BAR": 'PadLeft(PadRight("X", 5), 10) + "!"'
    })
    screen = t.read_for(.4)
    assert "         X!" in screen
    finish(t)


def test_status_size_and_mode_functions(tmp_path, terminal_factory):
    (tmp_path / "item").write_bytes(b"123456")
    t = terminal_factory(args=(str(tmp_path),), env={
        "WALK_STATUS_BAR": 'Size() + " " + Mode()'
    })
    screen = t.read_for(.4)
    assert "6B -rw" in screen
    finish(t)


def test_symlink_directory_navigation_preserves_link_path(tmp_path, terminal_factory):
    target = tmp_path / "target"
    target.mkdir()
    (target / "inside").write_text("x")
    link = tmp_path / "link"
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks unavailable")
    t = terminal_factory(args=(str(tmp_path),))
    t.read_for(.3)
    t.send("\r")
    screen = t.read_for(.3)
    assert f"\n{link}\n" in screen and "inside" in screen
    finish(t)
