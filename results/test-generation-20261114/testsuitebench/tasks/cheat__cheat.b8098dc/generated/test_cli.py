import os
import subprocess
from pathlib import Path

from conftest import sheet


def test_version_without_config(envbox):
    r = envbox['run']('--version', overrides={'CHEAT_CONFIG_PATH': '/missing'})
    assert (r.returncode, r.stdout, r.stderr) == (0, b'5.1.0\n', b'')


def test_help_and_init_without_config(envbox):
    r = envbox['run']('--help', overrides={'CHEAT_CONFIG_PATH': '/missing'})
    assert r.returncode == 0 and r.stdout.startswith(b'cheat allows you') and b'Flags:\n' in r.stdout
    r = envbox['run']('--init', overrides={'CHEAT_CONFIG_PATH': '/missing'})
    assert r.returncode == 0 and r.stdout.startswith(b'---\n')
    assert b'name: personal' in r.stdout and b'name: work' in r.stdout


def test_argument_errors_are_exact(envbox):
    for args, message in [(['--mystery'], b'unknown flag: --mystery\n'),
                          (['--tag'], b'flag needs an argument: --tag\n'),
                          (['-s'], b"flag needs an argument: 's' in -s\n'),
                          (['a', 'b'], b'accepts at most 1 arg(s), received 2\n')]:
        r = envbox['run'](*args)
        assert r.returncode == 1 and r.stdout == b'' and r.stderr == message


def test_config_precedence_and_directory_listing(envbox, tmp_path):
    a, b = tmp_path / 'one', tmp_path / 'two'
    a.mkdir(); b.mkdir()
    envbox['config']([('first', a, False, []), ('second', b, True, [])])
    r = envbox['run']('--directories')
    assert r.returncode == 0
    assert r.stdout == f'first:  {a}\nsecond: {b}\n'.encode()
    assert envbox['run']('--conf').stdout == str(envbox['conf']).encode() + b'\n'


def test_missing_config_prompt_eof(envbox):
    r = envbox['run']('--list', overrides={'CHEAT_CONFIG_PATH': '/definitely/missing'}, input=b'')
    assert r.returncode == 1 and b'failed to create config: failed to prompt: EOF' in r.stderr


def test_listing_brief_regex_and_duplicate_instances(envbox, tmp_path):
    p1, p2 = tmp_path / 'a', tmp_path / 'b'; p1.mkdir(); p2.mkdir()
    sheet(p1, 'same', 'old', b'tags: [z]')
    sheet(p2, 'same', 'new', b'tags: [a]')
    sheet(p2, 'docker/compose', 'd', b'tags: [network]')
    envbox['config']([('one', p1, False, []), ('two', p2, False, [])])
    r = envbox['run']('--list')
    assert r.returncode == 0 and r.stdout.count(b'same') == 2
    assert r.stdout.index(b'docker/compose') < r.stdout.index(b'same')
    b = envbox['run']('--brief', 'DOCKER')
    assert b.returncode == 0 and b'file:' not in b.stdout and b'docker/compose' in b.stdout
    assert envbox['run']('--list', '[invalid').returncode == 1
    miss = envbox['run']('--list', 'absent')
    assert miss.returncode == 2 and miss.stdout == b''


def test_view_precedence_all_and_no_match(envbox, tmp_path):
    p1, p2 = tmp_path / 'low', tmp_path / 'high'; p1.mkdir(); p2.mkdir()
    sheet(p1, 'x', 'lower\n'); sheet(p2, 'x', '\n  padded  \n')
    envbox['config']([('first', p1, False, []), ('second', p2, False, [])])
    assert envbox['run']('x').stdout == b'\n  padded  \n'
    assert envbox['run']('--all', 'x').stdout == b'x (first)\n\tlower\n\nx (second)\n\tpadded\n'
    r = envbox['run']('nested/nope')
    assert r.returncode == 2 and r.stdout == b"No cheatsheet found for 'nested/nope'.\n"


def test_frontmatter_body_exact_and_tag_filter(envbox):
    sheet(envbox['root'], 'raw', b'ignored', b'tags: [Linux]\nsyntax: 42')
    (envbox['root'] / 'raw').write_bytes(b'---\nsyntax: 42\ntags: [Linux]\n---\n  body\n')
    envbox['config']([('test', envbox['root'], False, ['OS'])])
    assert envbox['run']('raw').stdout == b'  body\n'
    assert envbox['run']('--brief', '--tag', 'Linux,OS').returncode == 0
    assert b'Linux,OS' in envbox['run']('--brief').stdout
    assert envbox['run']('--brief', '--tag', 'linux').returncode == 2


def test_tags_sorted_and_search_paragraph_rendering(envbox):
    (envbox['root'] / 's').write_bytes(b'---\ntags: [unix, Linux]\n---\nneedle first\ncontinued\n\nneedle second')
    envbox['config']([('test', envbox['root'], False, ['UNIX'])])
    assert envbox['run']('--tags').stdout == b'Linux\nUNIX\nunix\n'
    r = envbox['run']('--search', 'needle')
    assert r.returncode == 0 and r.stdout == b's (test)\n\tneedle first\n\tcontinued\n\t\n\tneedle second'
    assert envbox['run']('--search', 'none').stdout == b''
    assert envbox['run']('--regex', '--search', 'NEEDLE').stdout == b''


def test_regex_search_semantics_and_errors(envbox):
    sheet(envbox['root'], 'a', 'ssh user\n')
    envbox['config']()
    assert envbox['run']('--regex', '--search', r'ssh\s+user').stdout.endswith(b'\tssh user')
    for pattern in [r'(\w+) \1', 'ssh(?= user)']:
        r = envbox['run']('--regex', '--search', pattern)
        assert r.returncode == 1 and r.stdout == b'' and r.stderr.startswith(b'failed to compile regexp:')


def test_title_validation_remove_and_readonly(envbox, tmp_path):
    envbox['config']()
    for title in ['', '../escape', '/absolute', '~x', '.hidden']:
        r = envbox['run']('--rm', title)
        assert r.returncode == 1 and r.stderr.startswith(b'invalid cheatsheet name:')
    sheet(envbox['root'], 'gone', 'data')
    assert envbox['run']('--rm', 'gone').returncode == 0
    assert not (envbox['root'] / 'gone').exists()
    sheet(envbox['root'], 'locked', 'data')
    envbox['config']([('test', envbox['root'], True, [])])
    r = envbox['run']('--rm', 'locked')
    assert r.returncode == 1 and r.stderr == b"cheatsheet 'locked' is read-only.\n"


def test_edit_new_target_is_not_precreated(envbox):
    envbox['config']()
    r = envbox['run']('--edit', 'deep/path_new')
    assert r.returncode == 0 and not (envbox['root'] / 'deep/path_new').exists()


def test_colorize_flag_and_config_are_distinct(envbox):
    body = b'# C\ngit commit -m "Initial commit"\n'
    sheet(envbox['root'], 'x', body)
    envbox['config'](colorize='true')
    assert envbox['run']('x').stdout == body
    r = envbox['run']('--colorize', 'x')
    assert r.returncode == 0 and r.stdout != body and b'\x1b[' in r.stdout


def test_raw_binary_and_large_sheet(envbox):
    raw = b'first\x00\x01\xff\n' + b'x' * 1_300_000
    sheet(envbox['root'], 'huge', raw)
    envbox['config']()
    r = envbox['run']('huge')
    assert r.returncode == 0 and r.stdout == raw
    assert envbox['run']('--brief').returncode == 0


def test_symlink_file_and_hidden_rules(envbox, tmp_path):
    sheet(envbox['root'], '.hidden', 'no')
    (envbox['root'] / '.dir').mkdir()
    sheet(envbox['root'] / '.dir', 'visible', 'yes')
    real = sheet(envbox['root'], 'source', 'link')
    (envbox['root'] / 'alias').symlink_to(real)
    (envbox['root'] / 'note.txt').write_text('no')
    envbox['config']()
    out = envbox['run']('--brief').stdout
    assert b'.hidden' not in out and b'.dir/visible' in out and b'alias' in out and b'note.txt' not in out


def test_cwd_cheatpath_is_discovered(envbox, tmp_path):
    cwd = tmp_path / 'a' / 'b'; cwd.mkdir(parents=True)
    cheat = tmp_path / '.cheat'; cheat.mkdir()
    sheet(cheat, 'fromcwd', 'yes')
    envbox['config']()
    assert b'cwd:' in envbox['run']('--directories', cwd=cwd).stdout
    assert envbox['run']('fromcwd', cwd=cwd).stdout == b'yes'


def test_completion_shell_validation(envbox):
    assert envbox['run']('--completion', 'bash').returncode == 0
    for shell in ('Bash', '', 'zsh '):
        r = envbox['run']('--completion', shell)
        assert r.returncode == 1 and r.stdout == b'' and b'unsupported shell:' in r.stderr


def test_update_non_git_is_skipped(envbox):
    envbox['config']()
    r = envbox['run']('--update')
    assert r.returncode == 0 and r.stdout == b'test: skipped (not a git repository)\n'
