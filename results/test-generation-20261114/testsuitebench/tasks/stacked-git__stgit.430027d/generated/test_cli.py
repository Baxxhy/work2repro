import os
import re
import subprocess
from pathlib import Path

import pytest


STG = Path(os.environ.get("STG_EXECUTABLE", "/workspace/executable"))


def run(args, cwd=None, env=None, input=None):
    e = os.environ.copy()
    e.update({"GIT_AUTHOR_NAME": "Test User", "GIT_AUTHOR_EMAIL": "test@example.com",
              "GIT_COMMITTER_NAME": "Test User", "GIT_COMMITTER_EMAIL": "test@example.com",
              "GIT_EDITOR": "true", "LC_ALL": "C.UTF-8"})
    if env:
        e.update(env)
    p = subprocess.run([str(STG), *map(str, args)], cwd=cwd, env=e, input=input,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")


def git(cwd, *args, input=None):
    p = subprocess.run(["git", *args], cwd=cwd, input=input, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, check=True)
    return p.stdout.decode("utf-8", "replace").strip()


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, "init", "-q", "-b", "master")
    git(tmp_path, "config", "user.name", "Test User")
    git(tmp_path, "config", "user.email", "test@example.com")
    (tmp_path / "base.txt").write_text("base\n")
    git(tmp_path, "add", "base.txt")
    git(tmp_path, "commit", "-qm", "base")
    return tmp_path


def patch(repo, name, file_name=None, content=None):
    file_name = file_name or name + ".txt"
    (repo / file_name).write_text(content if content is not None else name + "\n")
    rc, out, err = run(["new", "-m", name, name, "--", file_name], repo)
    assert rc == 0, (out, err)


def init(repo):
    rc, out, err = run(["init"], repo)
    assert rc == 0, (out, err)


def test_global_help_and_versions():
    rc, out, err = run(["--help"])
    assert rc == 0 and "Maintain a stack of patches" in out and "Administration commands:" in out and err == ""
    rc, short, err = run(["-h"])
    assert rc == 0 and "Usage: stg [OPTIONS] <command> [...]" in short and err == ""
    rc, version, err = run(["--version", "garbage"])
    assert rc == 0 and version.startswith("Stacked Git 2.5.5\n") and "git version " in version and err == ""
    rc, short, err = run(["version", "--short"])
    assert rc == 0 and short == "stg 2.5.5\n"


def test_global_argument_errors_and_help(repo):
    rc, out, err = run(["--invalid-flag"], repo)
    assert rc == 1 and out == "" and err.startswith("error: unexpected argument '--invalid-flag' found")
    rc, out, err = run(["nonexistent_subcmd"], repo)
    assert rc == 1 and out == "" and "unrecognized subcommand 'nonexistent_subcmd'" in err and "similar subcommand exists: 'next'" in err
    rc, out, err = run(["-C"], repo)
    assert rc == 1 and out == "" and err == "error: a value is required for '-C <path>' but none was supplied\n\nFor more information, try '--help'.\n"
    rc, out, err = run(["-C=missing", "--version"], repo)
    assert rc == 0 and out.startswith("Stacked Git") and err == ""
    rc, out, err = run(["series", "--color=invalid"], repo)
    assert rc == 1 and out == "" and "invalid" in err and "possible values: auto, always, ansi, never" in err
    rc, out, err = run([])
    assert rc == 1 and out == "" and "Usage: stg" in err
    rc, out, err = run(["--color=auto"])
    assert rc == 1 and out == "" and "requires a subcommand" in err
    rc, out, err = run(["version", "extra"])
    assert rc == 1 and out == "" and "extra" in err and "Usage: stg version" in err


def test_global_color_and_subcommand_help(repo):
    init(repo)
    rc, out, err = run(["series", "--color", "always"], repo)
    assert rc == 0 and "\x1b[" in out
    rc, out, err = run(["--color", "never", "series"], repo)
    assert rc == 0 and "\x1b[" not in out
    rc, out, err = run(["diff", "--help"])
    assert rc == 0 and "Usage: stg diff" in out and err == ""
    rc, out, err = run(["help", "diff"])
    assert rc == 0 and "Usage: stg diff" in out


def test_init_persists_git_ref_and_rejects_repeat(repo):
    before = git(repo, "rev-parse", "HEAD")
    init(repo)
    assert (repo / ".git/refs/stacks").exists()
    assert git(repo, "show-ref", "--verify", "refs/stacks/master")
    assert git(repo, "rev-parse", "HEAD") == before
    rc, out, err = run(["init"], repo)
    assert rc == 2 and out == "" and err == "error: StGit stack already initialized for branch `master`\n"
    rc, out, err = run(["series"], repo)
    assert (rc, out, err) == (0, "", "")


def test_repository_discovery_uninitialized_and_subdirectory(repo):
    rc, out, err = run(["series"], repo)
    assert (rc, out, err) == (0, "", "")
    sub = repo / "sub"
    sub.mkdir()
    rc, out, err = run(["series"], sub)
    assert (rc, out, err) == (0, "", "")
    rc, out, err = run(["series"], "/tmp")
    assert rc == 2 and out == "" and err == "error: Could not find a git repository in '.' or in any of its parents\n"


def test_new_series_locators_and_commit_metadata(repo):
    init(repo)
    rc, out, err = run(["new", "-m", "Hello World", "--name", "patch1", "--", "base.txt"], repo)
    assert rc == 0 and out == "> patch1 (new)\n" and err == ""
    assert git(repo, "show", "-s", "--format=%s", "HEAD") == "Hello World"
    assert git(repo, "show", "HEAD:base.txt") == "base"
    rc, out, err = run(["series", "--description", "--author", "--commit-id=8"], repo)
    assert rc == 0 and "Test User # Hello World" in out and re.search(r"[+>] [0-9a-f]{8} patch1", out)
    assert run(["top"], repo)[:2] == (0, "patch1\n")
    assert run(["id", "patch1"], repo)[1].strip() == git(repo, "rev-parse", "HEAD")
    assert run(["name", "{base}"], repo)[1] == "{base}\n"


def test_apply_pop_goto_and_dirty_state(repo):
    init(repo)
    patch(repo, "p1")
    patch(repo, "p2")
    rc, out, err = run(["pop"], repo)
    assert rc == 0 and out == "- p2\n> p1\n" and err == ""
    assert "- p2" in run(["series"], repo)[1]
    rc, out, err = run(["push"], repo)
    assert rc == 0 and out == "+ p2\n> p2\n"
    rc, out, err = run(["goto", "p2"], repo)
    assert rc == 0 and out == "> p2\n"
    (repo / "p2.txt").write_text("local\n")
    rc, out, err = run(["pop"], repo)
    assert rc == 2 and out == "" and "error: worktree not clean" in err


def test_unapply_selected_middle_preserves_order(repo):
    init(repo)
    for n in ("p1", "p2", "p3"):
        patch(repo, n)
    rc, out, err = run(["pop", "p2"], repo)
    assert rc == 0 and out == "- p2..p3\n> p3\n" and err == ""
    assert run(["series"], repo)[1] == "+ p1\n> p3\n- p2\n"


def test_rename_hide_unhide_clean(repo):
    init(repo)
    patch(repo, "p1")
    patch(repo, "p2")
    rc, out, err = run(["rename", "p2", "renamed"], repo)
    assert rc == 0 and "p2 => renamed\n" in out and err == ""
    rc, out, err = run(["hide", "p1"], repo)
    assert rc == 0 and "! p1\n" in out
    assert run(["series", "--all"], repo)[1].endswith("! p1\n")
    rc, out, err = run(["unhide", "p1"], repo)
    assert rc == 0 and "- p1\n" in out
    rc, out, err = run(["clean"], repo)
    assert rc == 0


def test_inspection_diff_files_show(repo):
    init(repo)
    patch(repo, "p1", "base.txt", "base\nchanged\n")
    assert run(["files"], repo)[1] == "M base.txt\n"
    assert run(["files", "--bare"], repo)[1] == "base.txt\n"
    rc, out, err = run(["show", "--stat", "p1"], repo)
    assert rc == 0 and "commit " in out and "Author: Test User" in out and "base.txt" in out
    (repo / "base.txt").write_text("base\nchanged\nlocal\n")
    rc, out, err = run(["diff"], repo)
    assert rc == 0 and "+local" in out
    rc, out, err = run(["status"], repo)
    assert rc == 0 and " M base.txt" in out


def test_patch_name_validation_and_duplicate(repo):
    init(repo)
    rc, out, err = run(["new", "-m", "x", "invalid..name"], repo)
    assert rc == 1 and out == "" and "invalid patch name 'invalid..name'" in err
    patch(repo, "valid")
    rc, out, err = run(["new", "-m", "x", "valid"], repo)
    assert rc == 2 and out == "" and err == "error: patch `valid` already exists\n"


def test_transaction_log_undo_redo(repo):
    init(repo)
    patch(repo, "p1")
    rc, out, err = run(["log", "--number", "1"], repo)
    assert rc == 0 and "new: p1" in out
    rc, out, err = run(["undo"], repo)
    assert rc == 0 and run(["series"], repo)[1] == ""
    rc, out, err = run(["redo"], repo)
    assert rc == 0 and "p1" in run(["series"], repo)[1]


def test_refresh_captures_changes_and_dirty_state(repo):
    init(repo)
    patch(repo, "p1")
    (repo / "base.txt").write_text("base\nworktree\n")
    rc, out, err = run(["refresh"], repo)
    assert rc == 0 and err == "" and out.splitlines()[-2:] == ["& p1", "> p1"]
    assert git(repo, "status", "--short") == ""
    (repo / "base.txt").write_text("base\nstaged\n")
    git(repo, "add", "base.txt")
    (repo / "p1.txt").write_text("p1\nworktree\n")
    rc, out, err = run(["refresh"], repo)
    assert rc == 2 and out == "" and "the index is dirty" in err


def test_fold_stages_diff_without_rewriting_head(repo, tmp_path):
    init(repo)
    patch(repo, "p1")
    head = git(repo, "rev-parse", "HEAD")
    diff = tmp_path / "change.diff"
    diff.write_text("diff --git a/base.txt b/base.txt\nindex df967b9..0000000 100644\n--- a/base.txt\n+++ b/base.txt\n@@ -1 +1,2 @@\n base\n+folded\n")
    rc, out, err = run(["fold", diff], repo)
    assert rc == 0 and out == "" and err == ""
    assert git(repo, "rev-parse", "HEAD") == head
    assert git(repo, "status", "--short") == "M  base.txt"


def test_squash_and_uncommit_helpful_error(repo):
    init(repo)
    patch(repo, "p1")
    patch(repo, "p2")
    rc, out, err = run(["squash", "p1"], repo)
    assert rc == 2 and out == "" and err == "error: need at least two patches\n"
    rc, out, err = run(["squash", "--name", "p2", "--message", "combined", "p1", "p2"], repo)
    assert rc == 2 and out == "" and err == "error: patch name `p2` already taken\n"
    rc, out, err = run(["uncommit", "--number", "-1"], repo)
    assert rc != 0 and out == ""


def test_pick_noapply_preserves_dirty_worktree(repo):
    init(repo)
    base = git(repo, "rev-parse", "HEAD")
    git(repo, "switch", "-qc", "source-branch", base)
    (repo / "source.txt").write_text("source\n")
    git(repo, "add", "source.txt")
    git(repo, "commit", "-qm", "Source patch")
    source = git(repo, "rev-parse", "HEAD")
    git(repo, "switch", "-q", "master")
    (repo / "local.txt").write_text("local\n")
    rc, out, err = run(["pick", "--noapply", source], repo)
    assert rc == 0 and out == "- Source-patch\n" and err == ""
    assert (repo / "local.txt").read_text() == "local\n"
    assert "- Source-patch" in run(["series"], repo)[1]


def test_export_import_round_trip(repo, tmp_path):
    init(repo)
    patch(repo, "p1", "base.txt", "base\nexported\n")
    outdir = tmp_path / "out"
    rc, out, err = run(["export", "--dir", outdir], repo)
    assert rc == 0 and err == "" and (outdir / "series").exists() and (outdir / "p1").exists()
    other = tmp_path / "other"
    other.mkdir()
    git(other, "init", "-q", "-b", "master")
    git(other, "config", "user.name", "Test User")
    git(other, "config", "user.email", "test@example.com")
    (other / "base.txt").write_text("base\n")
    git(other, "add", "base.txt")
    git(other, "commit", "-qm", "base")
    init(other)
    rc, out, err = run(["import", str(outdir / "p1")], other)
    assert rc == 0 and out == "> p1 (new)\n" and err == ""
    assert git(other, "show", "HEAD:base.txt") == "base\nexported"


def test_branch_protection_and_metadata(repo):
    init(repo)
    rc, out, err = run(["branch", "--protect"], repo)
    assert rc == 0 and out == err == ""
    rc, out, err = run(["new", "-m", "allowed", "p"], repo)
    assert rc == 0 and out == "> p (new)\n"
    rc, out, err = run(["branch", "--list"], repo)
    assert rc == 0 and "master" in out and "p" in out


def test_completion_lists_and_nested_help():
    rc, out, err = run(["completion", "list", "commands"])
    assert rc == 0 and out.startswith("branch\nclean\ncommit\ncompletion\n") and out.endswith("unhide\nversion\nhelp\n")
    rc, aliases, err = run(["completion", "list", "aliases"])
    assert rc == 0 and aliases == "add\nmv\nresolved\nrm\nstatus\n"
    rc, help_text, err = run(["completion", "fish", "--help"])
    assert rc == 0 and help_text.startswith("Generate fish shell completion script")


def test_completion_generators_and_man_pages(tmp_path):
    rc, bash, err = run(["completion", "bash"])
    assert rc == 0 and bash.startswith("# -*- shell-script -*-\n#\n# SPDX-License-Identifier: GPL-2.0-only\n")
    assert "complete" in bash and "stg" in bash
    rc, fish, err = run(["completion", "fish"])
    assert rc == 0 and fish.startswith("# SPDX-License-Identifier: GPL-2.0-only") and "complete -c stg" in fish
    rc, zsh, err = run(["completion", "zsh"])
    assert rc == 0 and zsh.startswith("#compdef stg") and "_stg" in zsh
    man = tmp_path / "man"
    rc, out, err = run(["completion", "man", "--output", man])
    assert rc == 0 and out == "" and err == ""
    pages = list(man.glob("stg-*.txt"))
    assert len(pages) == 45
    version = (man / "stg-version.txt").read_text()
    assert version.startswith("stg-version(1)\n") and "Print version information and exit" in version


def test_git_aliases_and_global_working_directory(repo):
    sub = repo / "nested"
    sub.mkdir()
    (sub / "alias.txt").write_text("alias\n")
    rc, out, err = run(["add", "nested/alias.txt"], repo)
    assert rc == 0 and out == "" and err == ""
    rc, out, err = run(["status"], repo)
    assert rc == 0 and out == "A  nested/alias.txt\n"
    rc, out, err = run(["-C", str(repo), "status"], Path("/tmp"))
    assert rc == 0 and out == "A  nested/alias.txt\n"


def test_series_selection_and_validation(repo):
    init(repo)
    for n in ("p1", "p2", "p3"):
        patch(repo, n)
    assert run(["series", "--count"], repo)[1] == "3\n"
    assert run(["series", "--reverse"], repo)[1] == "> p3\n+ p2\n+ p1\n"
    assert run(["series", "--short=2"], repo)[1] == "+ p2\n> p3\n"
    rc, out, err = run(["series", "p3", "p1", "p3"], repo)
    assert rc == 2 and out == "" and err == "error: `p1` not contiguous with preceding range `p3`\n"
    rc, out, err = run(["series", "--all", "--applied"], repo)
    assert rc == 1 and out == "" and "cannot be used" in err
