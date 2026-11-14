import json
from pathlib import Path

import pytest

from conftest import write


def test_config_url_diagnostics(invoke):
    r = invoke("--config", "bare.hcl", "schema", "inspect")
    assert r.returncode == 1 and r.stderr.decode().startswith("Error: missing scheme for config file. Did you mean file://bare.hcl?")
    u = invoke("--config", "http://example.com/x", "schema", "inspect")
    assert u.returncode == 1 and u.stderr.decode().startswith('Error: unsupported config file driver "http"')


def test_config_missing_environment(invoke, tmp_path):
    cfg = write(tmp_path / "atlas.hcl", "# empty config\n")
    r = invoke("schema", "inspect", "--config", f"file://{cfg}", "--env", "absent")
    assert r.returncode == 1 and 'env "absent" not defined in config file' in r.stderr.decode()


def test_fmt_is_idempotent_and_preserves_comments(invoke, tmp_path):
    f = write(tmp_path / "schema.hcl", '// top\ntable   "single" {schema=schema.public}\n')
    r = invoke("schema", "fmt", str(f))
    assert r.returncode == 0 and str(f) in r.stdout.decode()
    expected = '// top\ntable "single" { schema = schema.public }\n'
    assert f.read_text() == expected
    again = invoke("schema", "fmt", str(f))
    assert again.returncode == 0 and again.stdout == b""


def test_fmt_directory_nonrecursive_and_ignores_other_files(invoke, tmp_path):
    d = tmp_path / "dir"; d.mkdir()
    h = write(d / "a.hcl", 'table   "x" {foo=bar}\n')
    txt = write(d / "b.txt", 'table   "x" {foo=bar}\n')
    nested = d / "nested"; nested.mkdir(); write(nested / "c.hcl", 'table   "x" {foo=bar}\n')
    r = invoke("schema", "fmt", str(d))
    assert r.returncode == 0 and str(h) in r.stdout.decode()
    assert txt.read_text() == 'table   "x" {foo=bar}\n'
    assert (nested / "c.hcl").read_text() == 'table   "x" {foo=bar}\n'


@pytest.mark.parametrize("shell, prefix, marker", [
    ("bash", "# bash completion V2 for atlas", "__atlas_init_completion"),
    ("zsh", "#compdef atlas", "_atlas"),
    ("fish", "# fish completion for atlas", "__atlas_perform_completion"),
    ("powershell", "# powershell completion for atlas", "__atlasCompleterBlock"),
])
def test_completion_scripts(invoke, shell, prefix, marker):
    r = invoke("completion", shell)
    assert r.returncode == 0 and r.stderr == b""
    out = r.stdout.decode()
    assert out.startswith(prefix) and marker in out and len(out) > 1000


def test_bash_no_descriptions_completion_mode(invoke):
    r = invoke("completion", "bash", "--no-descriptions")
    assert r.returncode == 0 and 'requestComp="${words[0]} __completeNoDesc ${args[*]}"' in r.stdout.decode()


def test_community_feature_unavailable_and_help(invoke):
    r = invoke("schema", "test")
    assert r.returncode == 1 and r.stdout == b"" and "Abort: 'atlas schema test' is not supported" in r.stderr.decode()
    h = invoke("schema", "test", "--help")
    assert h.returncode == 0 and h.stderr == b"" and "not supported by the community version" in h.stdout.decode()


def test_first_advanced_notice_persisted_and_disabled(invoke, tmp_path):
    home = tmp_path / "home"
    r = invoke("schema", "inspect", "--url", "sqlite://file?mode=memory", cwd=tmp_path)
    assert r.returncode == 0
    state = home / ".atlas" / "local-community.json"
    assert state.exists()
    payload = json.loads(state.read_text())
    assert "v1.us" in payload
    quiet_home = tmp_path / "quiet-home"
    q = invoke("schema", "inspect", "--url", "sqlite://file?mode=memory", cwd=tmp_path, env={"HOME": str(quiet_home), "ATLAS_NO_UPGRADE_SUGGESTIONS": "1"})
    assert q.returncode == 0 and not (quiet_home / ".atlas" / "local-community.json").exists()
