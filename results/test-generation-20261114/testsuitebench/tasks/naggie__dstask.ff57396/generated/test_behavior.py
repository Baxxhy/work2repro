import json
import os
import re
import subprocess
import uuid

from conftest import json_tasks


def create(app, *args):
    r = app["run"]("add", *args)
    assert r.returncode == 0, r.stderr.decode("utf-8", "replace")
    return r


def test_repo_init_and_git_backed_task_shape(app):
    r = create(app, "First", "task", "+Work", "+work", "P1", "project:Web")
    assert r.stdout.decode().startswith("Added 1: First task")
    assert "Add a remote repository with:" in r.stdout.decode()
    tasks = json_tasks(app["run"]("show-open"))
    assert len(tasks) == 1
    t = tasks[0]
    assert set(t) >= {"uuid", "status", "id", "summary", "notes", "tags", "project", "priority", "created", "resolved", "due"}
    assert t["id"] == 1 and t["summary"] == "First task"
    assert t["status"] == "pending" and t["tags"] == ["work"]
    assert t["project"] == "web" and t["priority"] == "P1" and t["notes"] == ""
    assert re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}", t["uuid"])
    assert app["git"]("status", "--porcelain").stdout == b""
    assert app["git"]("ls-files").stdout.decode().strip().endswith(t["uuid"] + ".yml")
    assert (app["repo"] / ".git/dstask/ids.bin").stat().st_size > 0


def test_repo_selection_isolation_and_invalid_directory(app):
    create(app, "one")
    second = app["tmp"] / "other repo"
    r = app["run"]("show-open", more_env={"DSTASK_GIT_REPO": second})
    assert r.returncode == 0 and r.stdout == b"[]"
    assert second.exists()
    ordinary = app["tmp"] / "ordinary"
    ordinary.mkdir()
    r = app["run"]("add", "x", more_env={"DSTASK_GIT_REPO": ordinary})
    assert r.returncode == 1 and b"Failed to create directory in git repository" in r.stderr


def test_help_version_and_completion_need_no_repository(app):
    v = app["run"]("version", "ignored")
    assert v.returncode == 0 and v.stderr == b""
    assert v.stdout == b"Version: Unknown\nGit commit: Unknown\nBuild date: Unknown\n"
    h = app["run"]("help")
    assert h.returncode == 0 and not h.stdout and b"Usage: dstask" in h.stderr
    c = app["run"]("bash-completion")
    assert c.returncode == 0 and not c.stderr and c.stdout.startswith(b"# wire bash completions")


def test_internal_completions_empty_repo(app):
    r = app["run"]("_completions", "dstask")
    assert r.returncode == 0
    assert r.stdout.splitlines()[:5] == [b"next", b"add", b"rm", b"remove", b"template"]
    assert r.stdout.splitlines()[-4:] == [b"P0", b"P1", b"P2", b"P3"]


def test_add_parser_handles_note_separator_and_data_verbatim(app):
    summary = "Quoted 'text' 日本語 $HOME ; echo nope"
    note = "P0 +not-a-tag / slash\nsecond line ☕"
    create(app, summary, "/", note)
    t = json_tasks(app["run"]("show-open"))[0]
    assert t["summary"] == summary and t["notes"] == note
    assert t["priority"] == "P2" and t["tags"] == []
    assert app["run"]("git", "status", "--porcelain").stdout == b""


def test_operator_first_wins_and_long_unicode_summary(app):
    create(app, "P1", "P2", "P3", "project:foo", "project:bar", "A" * 5000 + "界")
    t = json_tasks(app["run"]("show-open"))[0]
    assert t["priority"] == "P1" and t["project"] == "foo"
    assert t["summary"] == "P2 P3 project:bar " + "A" * 5000 + "界"


def test_tags_preserve_allowed_punctuation_and_unicode(app):
    create(app, "punctuation", "+A-B", "+a_b", "+a.b", "+a@b", "+日本語")
    t = json_tasks(app["run"]("show-open"))[0]
    assert t["tags"] == ["a-b", "a.b", "a@b", "a_b", "日本語"]


def test_double_dash_is_removed_anywhere_and_bypasses_context(app):
    assert app["run"]("context", "+blocked").returncode == 0
    r = app["run"]("add", "hello", "--", "world")
    assert r.returncode == 0
    t = json_tasks(app["run"]("show-open", "--"))[0]
    assert t["summary"] == "hello world" and t["tags"] == []


def test_add_and_log_validation_and_due(app):
    r = app["run"]("add")
    assert r.returncode == 1 and b"task description or template required" in r.stderr
    r = app["run"]("log")
    assert r.returncode == 1 and b"task description required" in r.stderr
    r = app["run"]("add", "bad", "due.before:2026-12-01")
    assert r.returncode == 1 and b"cannot use date filter with add command" in r.stderr
    create(app, "Due item", "due:2026-12-31")
    t = json_tasks(app["run"]("show-open"))[0]
    assert t["due"].startswith("2026-12-31T00:00:00")
    log = app["run"]("log", "Finished", "P0")
    assert log.returncode == 0 and b"Logged Finished" in log.stdout
    done = json_tasks(app["run"]("show-resolved"))
    assert len(done) == 1 and done[0]["id"] == 0 and done[0]["status"] == "resolved"


def test_lifecycle_preserves_uuid_and_ids_and_resolution_releases_id(app):
    create(app, "alpha")
    original = json_tasks(app["run"]("show-open"))[0]
    assert app["run"]("start", "1", "work note").returncode == 0
    active = json_tasks(app["run"]("show-active"))[0]
    assert active["id"] == 1 and active["uuid"] == original["uuid"]
    assert active["notes"] == "\nwork note"
    noop = app["run"]("start", "1")
    assert noop.returncode == 0 and b"No changes detected" in noop.stdout
    assert app["run"]("stop", "1").returncode == 0
    assert json_tasks(app["run"]("show-paused"))[0]["id"] == 1
    assert app["run"]("done", "1").returncode == 0
    resolved = json_tasks(app["run"]("show-resolved"))[0]
    assert resolved["id"] == 0 and resolved["uuid"] == original["uuid"]
    create(app, "replacement")
    assert json_tasks(app["run"]("show-open"))[0]["id"] == 1


def test_invalid_edges_and_checklist_block_resolution(app):
    create(app, "checklist", "/", "- [ ] unfinished")
    r = app["run"]("done", "1")
    assert r.returncode == 1 and b"refusing to resolve task with incomplete tasklist" in r.stderr
    create(app, "other")
    r = app["run"]("stop", "2")
    assert r.returncode == 1 and b"invalid state transition: pending -> paused" in r.stderr


def test_modify_normalization_noop_errors_and_notes_newline(app):
    create(app, "modify me", "+tag1", "+tag2", "+tag3", "/", "note")
    r = app["run"]("modify", "1", "-tag2", "-tag3", "+tag4", "+TAG5", "P0")
    assert r.returncode == 0 and r.stdout.startswith(b"\nModified 1:")
    t = json_tasks(app["run"]("show-open"))[0]
    assert t["tags"] == ["tag1", "tag3", "tag4", "tag5"]
    assert t["notes"] == "note\n" and t["priority"] == "P0"
    r = app["run"]("modify", "1")
    assert r.returncode == 1 and b"no operations specified" in r.stderr
    r = app["run"]("modify", "99", "+x")
    assert r.returncode == 1 and b"no open task with ID 99 exists" in r.stderr


def test_context_persists_filters_and_double_dash_bypasses(app):
    create(app, "work item", "+work")
    create(app, "home item", "+home")
    assert app["run"]("context", "+WORK").stdout == b""
    ctx = app["run"]("context")
    assert ctx.stdout.strip() == b"+work"
    listing = json_tasks(app["run"]("show-open"))
    assert [x["summary"] for x in listing] == ["work item"]
    assert b"home item" in app["run"]("show-open", "--").stdout
    assert b"Active context" not in app["run"]("show-open").stdout
    r = app["run"]("context", "free", "text")
    assert r.returncode == 1 and b"context cannot contain text" in r.stderr
    assert app["run"]("context", "none").stdout == b""


def test_environment_context_overrides_and_blocks_context_mutation(app):
    create(app, "work", "+work")
    create(app, "home", "+home")
    r = app["run"]("show-open", more_env={"DSTASK_CONTEXT": "+HOME"})
    assert len(json.loads(r.stdout)) == 1 and json.loads(r.stdout)[0]["summary"] == "home"
    assert b"Active context" not in r.stdout
    r = app["run"]("context", "none", more_env={"DSTASK_CONTEXT": "+home"})
    assert r.returncode == 1 and b"setting context not allowed" in r.stderr


def test_id_query_order_aliases_and_silent_missing_ids(app):
    create(app, "one", "P2")
    create(app, "two", "P2")
    ids = [x["id"] for x in json_tasks(app["run"]("2", "1", "show-next"))]
    assert ids == [1, 2]
    assert json_tasks(app["run"]("next", "999")) == []
    assert app["run"]("SHOW-OPEN").returncode == 0
    r = app["run"]("next", "1", "+x")
    assert r.returncode == 1 and b"operators not valid when addressing task by ID" in r.stderr


def test_note_raw_output_alias_and_operator_rejection(app):
    create(app, "notes", "/", "raw\nnotes ☃")
    r = app["run"]("notes", "1")
    assert r.returncode == 0 and r.stdout == "raw\nnotes ☃".encode()
    r = app["run"]("note", "1", "+bad")
    assert r.returncode == 1 and b"operators not valid in this context" in r.stderr


def test_template_conversion_copy_and_separation(app):
    create(app, "base", "+seed", "project:demo", "/", "template note")
    assert app["run"]("template", "1").returncode == 0
    templates = json_tasks(app["run"]("show-templates"))
    assert len(templates) == 1 and templates[0]["id"] == 1
    assert json_tasks(app["run"]("show-open")) == []
    r = app["run"]("add", "template:1", "copy", "-seed", "+extra")
    assert r.returncode == 0
    t = json_tasks(app["run"]("show-open"))[0]
    assert t["id"] == 2 and t["summary"] == "copy" and t["tags"] == ["extra"]
    assert t["project"] == "demo" and t["notes"] == "template note\n"
    assert len({templates[0]["uuid"], t["uuid"]}) == 2


def test_remove_commits_and_releases_id(app):
    create(app, "delete me")
    r = app["run"]("rm", "1", "mistake")
    assert r.returncode == 0 and b"Removed: 1: delete me" in r.stdout
    assert json_tasks(app["run"]("show-open")) == []
    assert app["git"]("log", "-1", "--pretty=%s").stdout.startswith(b"Removed: 1: delete me")
    create(app, "reuse")
    assert json_tasks(app["run"]("show-open"))[0]["id"] == 1


def test_queries_search_due_and_tag_project_lists(app):
    create(app, "Alpha needle", "+work", "project:One", "P0", "due:2026-05-10", "/", "hidden phrase")
    create(app, "Beta", "+home", "project:One", "P2")
    assert len(json_tasks(app["run"]("next", "+WORK", "needle"))) == 1
    assert len(json_tasks(app["run"]("next", "hidden", "phrase"))) == 1
    assert len(json_tasks(app["run"]("next", "due.on:2026-05-10"))) == 1
    assert app["run"]("show-tags").stdout.splitlines() == [b"home", b"work"]
    projects = json.loads(app["run"]("show-projects").stdout)
    assert projects[0]["name"] == "one" and projects[0]["taskCount"] == 2 and projects[0]["priority"] == "P0"
    assert app["run"]("show-unorganised").stdout == b"[]"


def test_json_schema_timestamps_and_empty_lists(app):
    assert app["run"]("show-open").stdout == b"[]"
    create(app, "time check")
    t = json_tasks(app["run"]("next"))[0]
    assert t["created"].endswith("Z") and t["resolved"] == "0001-01-01T00:00:00Z"
    assert t["due"] == "0001-01-01T00:00:00Z"
    assert t["status"] == "pending" and t["priority"] == "P2"


def test_malformed_records_are_skipped_and_status_inferred(app):
    create(app, "good")
    bad = app["repo"] / "pending"
    (bad / "invalid-uuid-short.yml").write_text("summary: bad\n")
    (bad / (str(uuid.uuid4()) + ".yml")).write_text("summary: [broken\n")
    r = app["run"]("show-open")
    assert r.returncode == 0 and len(json.loads(r.stdout)) == 1
    assert b"filename does not encode UUID invalid-uuid-short.yml (wrong length)" in r.stderr
    assert b"failed to unmarshal" in r.stderr


def test_git_command_and_undo_use_revert_history(app):
    create(app, "undo target")
    before = app["git"]("rev-list", "--count", "HEAD").stdout
    assert app["run"]("undo", "nonsense").returncode == 0
    r = app["run"]("undo", "1")
    assert r.returncode == 0
    after = app["git"]("rev-list", "--count", "HEAD").stdout
    assert int(after) == int(before) + 1
    assert json_tasks(app["run"]("show-open")) == []
    assert app["run"]("git", "status", "--porcelain").returncode == 0
