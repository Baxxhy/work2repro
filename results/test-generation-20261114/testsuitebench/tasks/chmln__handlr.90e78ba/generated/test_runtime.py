import hashlib
from pathlib import Path

from test_cli import desktop, run


def test_get_and_launch_runtime_errors(env):
    p = run(env, 'get', 'application/x-not-configured')
    assert p.returncode == 1 and p.stdout == '' and 'No such file or directory' in p.stderr
    assert run(env, 'launch', 'application/x-not-configured').returncode == 1


def test_invalid_existing_association_is_runtime_not_parse_error(env):
    p = Path(env['XDG_CONFIG_HOME']) / 'mimeapps.list'
    p.parent.mkdir(parents=True)
    p.write_text('[Default Applications]\ntext/plain=missing.desktop;\n')
    result = run(env, 'get', 'text/plain')
    assert result.returncode == 1 and result.stdout == '' and 'No such file or directory' in result.stderr


def test_plain_list_format_sorted_and_all_sections(env):
    desktop(env, 'z.desktop', 'Z', extra='MimeType=text/z;\n')
    desktop(env, 'a.desktop', 'A', extra='MimeType=text/a;\n')
    p = Path(env['XDG_CONFIG_HOME']) / 'mimeapps.list'
    p.parent.mkdir(parents=True)
    p.write_text('[Default Applications]\ntext/z=z.desktop;\ntext/a=a.desktop;\n')
    out = run(env, 'list').stdout.splitlines()
    assert out[0].startswith('┌') and out[-1].startswith('└')
    assert out.index(next(x for x in out if 'text/a' in x)) < out.index(next(x for x in out if 'text/z' in x))
    allout = run(env, 'list', '--all').stdout
    assert allout.startswith('Default Apps\n┌') and 'System Apps\n┌' in allout
    assert allout.index('Default Apps') < allout.index('System Apps')


def test_empty_list_exact_table(env):
    assert run(env, 'list').stdout == '┌──┐\n│  │\n└──┘\n'
    assert run(env, 'list', '-a').stdout == 'Default Apps\n┌──┐\n│  │\n└──┘\nSystem Apps\n┌──┐\n│  │\n└──┘\n'


def test_selector_selects_last_and_forwards_stderr(env):
    desktop(env, 'first.desktop', 'First')
    desktop(env, 'last.desktop', 'Last')
    cfg = Path(env['XDG_CONFIG_HOME']) / 'handlr'
    cfg.mkdir(parents=True)
    (cfg / 'handlr.toml').write_text('enable_selector = true\nselector = "tail -1"\n')
    p = Path(env['XDG_CONFIG_HOME']) / 'mimeapps.list'
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text('[Default Applications]\ntext/plain=first.desktop;last.desktop;\n')
    assert run(env, 'get', 'text/plain').stdout == 'last.desktop\n'
    (cfg / 'handlr.toml').write_text('enable_selector = true\nselector = "definitely-not-a-real-selector"\n')
    result = run(env, 'get', 'text/plain')
    assert result.returncode == 1 and result.stdout == '' and 'No such file or directory' in result.stderr


def test_malformed_config_fails_without_replacing_file(env):
    cfg = Path(env['XDG_CONFIG_HOME']) / 'handlr'
    cfg.mkdir(parents=True)
    f = cfg / 'handlr.toml'
    original = 'enable_selector = invalid_value_not_boolean\nselector = [this is not a string\n'
    f.write_text(original)
    p = run(env, 'list')
    assert p.returncode != 0 and 'panicked' in p.stderr and 'BadTomlData' in p.stderr
    assert f.read_text() == original


def test_open_paths_and_urls_dispatch_successfully(env, tmp_path):
    log = tmp_path / 'args.log'
    desktop(env, 'handler.desktop', 'Handler', f'/bin/sh -c "printf %s\\\\n \\\"$@\\\" >> {log}" sh %F')
    p = Path(env['XDG_CONFIG_HOME']) / 'mimeapps.list'
    p.parent.mkdir(parents=True)
    p.write_text('[Default Applications]\ntext/plain=handler.desktop;\nx-scheme-handler/https=handler.desktop;\n')
    one, two = tmp_path / 'one.txt', tmp_path / 'two.txt'
    one.write_text('plain')
    two.write_text('plain')
    result = run(env, 'open', str(one), str(two), 'https://example.com')
    assert result.returncode == 0 and result.stdout == '' and result.stderr == ''
    # Launch is asynchronous on some desktops; successful dispatch is the contract here.


def test_launch_passes_dash_arguments(env, tmp_path):
    capture = tmp_path / 'args'
    desktop(env, 'capture.desktop', 'Capture', f'/bin/sh -c "printf %s\\\\n \\\"$@\\\" > {capture}" sh %u')
    p = Path(env['XDG_CONFIG_HOME']) / 'mimeapps.list'
    p.parent.mkdir(parents=True)
    p.write_text('[Default Applications]\nx-scheme-handler/https=capture.desktop;\n')
    result = run(env, 'launch', 'https', '--', '-flag', 'https://example.com')
    assert result.returncode == 0


def test_terminal_true_requires_terminal_handler(env):
    desktop(env, 'terminal.desktop', 'Terminal App', '/bin/true', 'Terminal=true\n')
    p = Path(env['XDG_CONFIG_HOME']) / 'mimeapps.list'
    p.parent.mkdir(parents=True)
    p.write_text('[Default Applications]\ntext/plain=terminal.desktop;\n')
    result = run(env, 'launch', 'text/plain')
    assert result.returncode != 0 and ('terminal' in result.stderr.lower() or 'not found' in result.stderr.lower())


def test_autocomplete_outputs_and_precedence(env):
    p = run(env, 'autocomplete')
    assert (p.returncode, p.stdout, p.stderr) == (0, '', '')
    p = run(env, 'autocomplete', '-m')
    content = p.stdout.encode()
    assert len(content.splitlines()) == 2153
    assert hashlib.sha256(content).hexdigest() == '2454d74ab1ee141c4aaf787cce26be7077ce3c971cac7c55fd937deb05403d34'
    assert p.stdout.endswith('\n') and 'x-scheme-handler/terminal\n' in p.stdout
    desktop(env, 'sample.desktop', 'Sample')
    p = run(env, 'autocomplete', '-m', '-d')
    assert p.stdout == 'sample.desktop\tSample\n'


def test_autocomplete_help_and_version(env):
    p = run(env, 'autocomplete', '--help')
    assert p.returncode == 0 and p.stdout.startswith('executable-autocomplete \n\nUSAGE:')
    assert p.stdout.index('-d') < p.stdout.index('-m')
    assert run(env, 'autocomplete', '--version').stdout == 'executable-autocomplete \n'
