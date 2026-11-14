import json
from pathlib import Path

from test_cli import desktop, run


def mimefile(env):
    p = Path(env['XDG_CONFIG_HOME']) / 'mimeapps.list'
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def test_set_add_unset_canonical_and_persistent(env):
    desktop(env, 'one.desktop', 'One')
    desktop(env, 'two.desktop', 'Two')
    assert run(env, 'set', 'TEXT/PLAIN', 'one.desktop').returncode == 0
    assert run(env, 'add', 'text/plain', 'two.desktop').returncode == 0
    p = mimefile(env)
    assert p.read_text() == '[Added Associations]\n\n[Default Applications]\ntext/plain=one.desktop;two.desktop;\n'
    assert run(env, 'get', 'text/plain').stdout == 'one.desktop\n'
    assert run(env, 'set', 'text/plain', 'two.desktop').returncode == 0
    assert p.read_text().endswith('text/plain=two.desktop;\n')
    assert run(env, 'unset', 'text/plain').returncode == 0
    assert run(env, 'unset', 'text/plain').returncode == 0
    assert p.read_text() == ''


def test_canonical_sort_and_preserve_other_rows_and_added(env):
    for n in ('a','b','c'):
        desktop(env, f'{n}.desktop', n)
    p = mimefile(env)
    p.write_text('[Added Associations]\ntext/zzz=c.desktop;\n\n[Default Applications]\ntext/z=b.desktop;\ntext/a=a.desktop;\n')
    assert run(env, 'set', 'text/m', 'c.desktop').returncode == 0
    assert p.read_text() == '[Added Associations]\ntext/zzz=c.desktop;\n\n[Default Applications]\ntext/a=a.desktop;\ntext/m=c.desktop;\ntext/z=b.desktop;\n'


def test_add_duplicate_serialized_but_deduplicated_display(env):
    desktop(env, 'same.desktop', 'Same')
    run(env, 'add', 'text/plain', 'same.desktop')
    run(env, 'add', 'text/plain', 'same.desktop')
    assert 'same.desktop;same.desktop;' in mimefile(env).read_text()
    assert run(env, 'get', 'text/plain').stdout == 'same.desktop\n'
    assert run(env, 'list').stdout.count('same.desktop') == 1


def test_exact_wildcard_precedence_and_unset_reveals_wildcard(env):
    desktop(env, 'wild.desktop', 'Wild')
    desktop(env, 'exact.desktop', 'Exact')
    p = mimefile(env)
    p.write_text('[Default Applications]\ntext/*=wild.desktop;\ntext/html=exact.desktop;\n')
    assert run(env, 'get', 'text/html').stdout == 'exact.desktop\n'
    run(env, 'unset', 'text/html')
    assert run(env, 'get', 'text/html').stdout == 'wild.desktop\n'


def test_added_association_priority_and_added_wildcard_not_fallback(env):
    desktop(env, 'added.desktop', 'Added')
    p = mimefile(env)
    p.write_text('[Added Associations]\ntext/plain=added.desktop;\ntext/*=added.desktop;\n')
    assert run(env, 'get', 'text/plain').stdout == 'added.desktop\n'
    p.write_text('[Added Associations]\ntext/*=added.desktop;\n')
    assert run(env, 'get', 'text/html').returncode == 1


def test_parsing_case_duplicates_comments_bad_headers_and_invalid_rows(env):
    desktop(env, 'ok.desktop', 'OK')
    p = mimefile(env)
    p.write_text('#comment\n[default applications]\ntext/plain=ok.desktop;\n[Default Applications] \ntext/html=ok.desktop;\n[Default Applications]\ntext/plain=ok.desktop;ok.desktop;\ninvalid=ok.desktop;\n')
    assert run(env, 'get', 'text/plain').stdout == 'ok.desktop\n'
    out = run(env, 'list').stdout
    assert out.count('text/plain') == 1 and 'invalid' not in out and 'text/html' not in out


def test_json_get_and_exec_expansion(env):
    desktop(env, 'tool.desktop', '工具 "One"', '/usr/bin/test-app --title="My App" %u')
    run(env, 'set', 'text/plain', 'tool.desktop')
    p = run(env, 'get', '--json', 'text/plain')
    assert p.returncode == 0 and p.stderr == ''
    assert json.loads(p.stdout) == {'handler':'tool.desktop','name':'工具 "One"','cmd':'/usr/bin/test-app --title=My App'}
    assert list(json.loads(p.stdout)) == ['handler','name','cmd']
    desktop(env, 'vim.desktop', 'Vim', 'vim %u')
    run(env, 'set', 'text/html', 'vim.desktop')
    assert json.loads(run(env, 'get', 'text/html', '--json').stdout)['cmd'] == 'vim '


def test_mime_normalization_parameters_and_extensions(env):
    desktop(env, 'app.desktop')
    assert run(env, 'set', 'APPLICATION/VND.Example+JSON', 'app.desktop').returncode == 0
    assert 'application/vnd.example+json=' in mimefile(env).read_text()
    assert run(env, 'get', 'application/vnd.example+json').stdout == 'app.desktop\n'
    assert run(env, 'set', '.txt', 'app.desktop').returncode == 0
    assert run(env, 'get', 'text/plain').stdout == 'app.desktop\n'
    assert run(env, 'unset', 'text/plain; charset=utf-8').returncode == 0
    assert run(env, 'get', 'text/plain').returncode == 0


def test_invalid_mime_inputs_and_missing_handler(env):
    for value in ('.', '.xyzzy_unknown_ext_12345', 'text', 'text/', '/', 'text//plain', 'text/plain/extra', 'invalid@mime', 'text /plain', 'text/ plain'):
        p = run(env, 'get', value)
        assert p.returncode == 2 and 'Invalid value for' in p.stderr
    p = run(env, 'set', 'text/plain', 'nonexistent.desktop')
    assert p.returncode == 2 and "no handlers found for 'nonexistent.desktop'" in p.stderr


def test_desktop_validation_and_filename_roundtrip(env):
    desktop(env, 'Ünicode-name_2.desktop', ' 名称 ')
    assert run(env, 'set', 'text/plain', 'Ünicode-name_2.desktop').returncode == 0
    assert run(env, 'get', 'text/plain').stdout == 'Ünicode-name_2.desktop\n'
    assert 'Ünicode-name_2.desktop\t 名称 \n' in run(env, 'autocomplete', '-d').stdout
    bad = Path(env['XDG_DATA_HOME']) / 'applications' / 'bad.desktop'
    bad.write_text('[Desktop Entry]\nname=Bad\nexec=/bin/true\n')
    p = run(env, 'set', 'text/html', 'bad.desktop')
    assert p.returncode == 2 and 'malformed desktop entry at ' in p.stderr
    assert run(env, 'set', 'text/html', '../evil.desktop').returncode == 2


def test_large_number_of_mappings(env):
    for i in range(35):
        desktop(env, f'h{i}.desktop', f'H{i}')
    for i in range(35):
        assert run(env, 'set', f'application/x-item{i:02}', f'h{i}.desktop').returncode == 0
    for i in range(35):
        assert run(env, 'get', f'application/x-item{i:02}').stdout == f'h{i}.desktop\n'
