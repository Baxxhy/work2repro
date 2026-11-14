import os
import subprocess
from pathlib import Path

BIN = Path('/workspace/executable')
EVAL = Path(__file__).parent


def run(*args, data=b'', cwd=None, env=None, timeout=10):
    e = os.environ.copy()
    e.update({'TERM': 'dumb'})
    if env:
        e.update(env)
    return subprocess.run([str(BIN), *map(str, args)], input=data, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, cwd=cwd or EVAL, env=e, timeout=timeout)


def test_empty_stdin_is_silent():
    p = run()
    assert (p.returncode, p.stdout, p.stderr) == (0, b'', b'')


def test_version_exact():
    p = run('--version')
    assert (p.returncode, p.stdout, p.stderr) == (0, b'ov version dev rev:HEAD\n', b'')


def test_help_short_long_and_precedence():
    a, b = run('-h'), run('--help', 'not-a-real-file')
    assert a.returncode == b.returncode == 0
    assert a.stdout == b.stdout and a.stdout.endswith(b'\n') and b.stderr == b''
    assert b'ov is a feature rich pager(such as more/less).' in a.stdout
    assert b'--force-screen' in a.stdout and b'--wrap[=true|false]' in a.stdout
    assert b'\x1b' not in a.stdout


def test_help_takes_precedence_after_positional():
    p = run('missing-file', '--help')
    assert p.returncode == 0 and p.stderr == b'' and p.stdout.startswith(b'ov is a feature rich pager')


def test_list_modes_default():
    p = run('--list-view-modes')
    assert (p.returncode, p.stdout, p.stderr) == (0, b'general\n', b'')


def test_help_key_plain_text():
    p = run('--help-key')
    assert p.returncode == 0 and p.stderr == b'' and p.stdout.startswith(b'ov is a feature rich pager\n Key')
    for fragment in (b'\tGeneral', b'\tMoving', b'[Escape], [q]', b'[ctrl+f]                       * follow mode toggle'):
        assert fragment in p.stdout


def test_redirected_bytes_unchanged_for_display_flags(tmp_path):
    payload = b'\x00\talpha  \r\n\x1b[31mred\x1b[0m\x7f\x08\x0c\nlast  '
    f = tmp_path / 'input bytes.txt'
    f.write_bytes(payload)
    options = ['--plain', '--raw', '--converter=align', '--tab-width=4', '--line-number', '--wrap=false',
               '--header=2', '--section-delimiter=^#', '--column-mode', '--column-delimiter=,',
               '--pattern=x', '--filter=x', '--multi-color=ERROR,WARNING', '--ruler=2', '--memory-limit=1',
               '--memory-limit-file=1', '--skip-lines=1', '--caption=hello', '--status-line=false']
    p = run(*options, str(f))
    assert p.returncode == 0 and p.stdout == payload and p.stderr == b''


def test_stdin_preserved_under_display_flags():
    payload = b'\n\nno newline\t  '
    p = run('-n', '-c', '--filter=nomatch', '-F', '-X', '-a=0', '-b=-4', data=payload)
    assert p.returncode == 0 and p.stdout == payload and p.stderr == b''


def test_only_first_operand_copied(tmp_path):
    a, b = tmp_path / 'a', tmp_path / 'b'
    a.write_bytes(b'first\x00')
    b.write_bytes(b'second')
    p = run(str(a), str(b))
    assert (p.returncode, p.stdout, p.stderr) == (0, b'first\x00', b'')


def test_dash_reads_stdin():
    p = run('-', data=b'from stdin\n')
    assert (p.returncode, p.stdout, p.stderr) == (0, b'from stdin\n', b'')


def test_glob_expands_lexically_and_unmatched_errors(tmp_path):
    (tmp_path / 'b.txt').write_bytes(b'B')
    (tmp_path / 'a.txt').write_bytes(b'A')
    p = run('*.txt', cwd=tmp_path)
    assert (p.returncode, p.stdout, p.stderr) == (0, b'A', b'')
    q = run('no-match-*.txt', cwd=tmp_path)
    assert q.returncode == 1 and b'no-match-*.txt' in q.stderr


def test_open_errors_and_symlink_targets(tmp_path):
    absent = run(str(tmp_path / 'absent'))
    assert absent.returncode == 1 and b'Error: open ' in absent.stderr and b'no such file or directory' in absent.stderr
    broken = tmp_path / 'broken'
    broken.symlink_to(tmp_path / 'absent-target')
    assert b'no such file or directory' in run(str(broken)).stderr
    x, y = tmp_path / 'x', tmp_path / 'y'
    x.symlink_to(y); y.symlink_to(x)
    assert b'too many levels of symbolic links' in run(str(x)).stderr


def test_directory_write_error(tmp_path):
    p = run(str(tmp_path))
    assert (p.returncode, p.stderr) == (1, b'Error: write /dev/stdout: copy_file_range: is a directory\n')


def test_invalid_cli_arguments():
    cases = [(['--nonexistent-flag'], b'unknown flag: --nonexistent-flag'), (['-Z'], b"unknown shorthand flag: 'Z'"),
             (['--column-delimiter'], b'flag needs an argument: --column-delimiter'),
             (['-H', 'foo'], b'invalid argument "foo" for "-H, --header" flag'),
             (['-T', 'foo'], b'invalid argument "foo" for "-T, --watch" flag'),
             (['--incsearch=maybe'], b'invalid argument "maybe" for "--incsearch" flag'),
             (['--wrap=maybe'], b'invalid argument "maybe" for "-w, --wrap" flag'),
             (['--memory-limit=abc'], b'invalid argument "abc" for "--memory-limit" flag: strconv.ParseInt: parsing "abc": invalid syntax')]
    for args, msg in cases:
        p = run(*args)
        assert p.returncode == 1 and msg in p.stderr, (args, p.stderr)
        assert b'Error:' in p.stderr


def test_boolean_repetition_last_value_and_short_forms(tmp_path):
    f = tmp_path / 'v'
    f.write_bytes(b'v\n')
    for args in (['--wrap', '--wrap=false'], ['-cf', '-d;', '-H-1'], ['--incsearch=false', '--incsearch=true']):
        p = run(*args, str(f))
        assert p.returncode == 0 and p.stdout == b'v\n' and p.stderr == b''


def test_negative_display_values_are_safe():
    p = run('--skip-lines=-9', '--memory-limit=-2', '--tab-width=-1', data=b'a\nb')
    assert (p.returncode, p.stdout, p.stderr) == (0, b'a\nb', b'')


def test_completion_invalid_value():
    p = run('--completion=invalid')
    assert p.returncode == 1 and b'requires one of the arguments bash/zsh/fish/powershell' in p.stderr


def test_completion_shell_prefixes():
    prefixes = {
        'bash': b'# bash completion for ov                                   -*- shell-script -*-\n\n__ov_debug()',
        'zsh': b'#compdef ov\ncompdef _ov ov\n\n# zsh completion for ov                                   -*- shell-script -*-\n\n__ov_debug()',
        'fish': b'# fish completion for ov                                   -*- shell-script -*-\n\nfunction __ov_debug',
        'powershell': b'# powershell completion for ov                                   -*- shell-script -*-\n\nfunction __ov_debug',
    }
    for shell, prefix in prefixes.items():
        p = run('--completion=' + shell)
        assert p.returncode == 0 and p.stderr == b'' and p.stdout.startswith(prefix)
        assert len(p.stdout.splitlines()) >= 30
        if shell == 'powershell':
            assert b'filter __ov_escapeStringWithSpecialChars' in p.stdout and b'[scriptblock]${__ovCompleterBlock}' in p.stdout
        elif shell == 'bash':
            for name in (b'__ov_init_completion', b'__ov_index_of_word', b'__ov_contains_word'):
                assert name in p.stdout[:p.stdout.find(b'\n', p.stdout.find(b'__ov_contains_word') + 1) + 1]
        elif shell == 'fish':
            assert b'function __ov_perform_completion' in p.stdout
        else:
            assert b'_ov()' in p.stdout


def test_config_diagnostics_do_not_stop_version(tmp_path):
    bad = tmp_path / 'bad.yaml'
    bad.write_text('General: [\n')
    p = run('--config', str(bad), '--version')
    assert p.returncode == 0 and p.stdout == b'ov version dev rev:HEAD\n'
    assert p.stderr.startswith(b'failed to read config file: While parsing config:')
    no_ext = tmp_path / 'config'
    no_ext.write_text('')
    q = run('--config=' + str(no_ext), '--version')
    assert q.returncode == 0 and b'Unsupported Config Type' in q.stderr


def test_explicit_unknown_mode_falls_back_without_losing_bytes(tmp_path):
    f = tmp_path / 'mode.txt'
    f.write_bytes(b'mode\n')
    p = run('--view-mode=does-not-exist', str(f))
    assert p.returncode == 0 and p.stdout == b'mode\n'


def test_large_stream_and_unterminated_line_are_exact(tmp_path):
    # Cross the documented 10,000-line storage boundary and include a very long line.
    payload = b'row\n' * 10001 + b'x' * (500 * 1024) + b'\nend'
    f = tmp_path / 'large'
    f.write_bytes(payload)
    p = run('--memory-limit-file=1', str(f), timeout=20)
    assert p.returncode == 0 and p.stdout == payload and p.stderr == b''


def test_compressed_file_redirected_output_is_raw(tmp_path):
    import gzip
    raw = gzip.compress(b'expanded text\n')
    f = tmp_path / 'compressed.data'
    f.write_bytes(raw)
    for flags in ([], ['--skip-extract'], ['--skip-extract', '--column-mode', '--align', '--memory-limit=1']):
        p = run(*flags, str(f))
        assert p.returncode == 0 and p.stdout == raw and p.stderr == b''


def test_file_operand_paths_with_spaces_and_dot(tmp_path):
    f = tmp_path / '.name with spaces'
    f.write_bytes(b'ok\n')
    p = run(str(f))
    assert (p.returncode, p.stdout, p.stderr) == (0, b'ok\n', b'')


def test_quit_if_one_screen_keeps_all_bytes(tmp_path):
    payloads = [b'', b'one line', b'\x00\n\n', '雪🙂'.encode(), b'x\r\n']
    for index, payload in enumerate(payloads):
        f = tmp_path / ('small-' + str(index))
        f.write_bytes(payload)
        p = run('--quit-if-one-screen', str(f))
        assert p.returncode == 0 and p.stdout == payload and p.stderr == b''


def test_argument_delimiter_and_long_option_equals_value(tmp_path):
    f = tmp_path / 'input'
    f.write_bytes(b'a,b\n')
    p = run('--column-mode', '--column-delimiter=,', '--jump-target=-1', '--hscroll-width=.5', '--header=0', str(f))
    assert (p.returncode, p.stdout, p.stderr) == (0, b'a,b\n', b'')


def test_config_mode_names_preserve_declaration_order(tmp_path):
    cfg = tmp_path / 'ov.yaml'
    cfg.write_text('Mode:\n  first:\n    Header: 1\n  second:\n    WrapMode: false\n')
    p = run('--config', str(cfg), '--list-view-modes')
    assert (p.returncode, p.stdout, p.stderr) == (0, b'general\nfirst\nsecond\n', b'')


def test_debug_config_reports_selected_path(tmp_path):
    cfg = tmp_path / 'debug.yaml'
    cfg.write_text('Debug: true\n')
    p = run('--config', str(cfg), '--version')
    assert p.returncode == 0 and p.stdout == b'ov version dev rev:HEAD\n'
    assert ('Using config file: ' + str(cfg)).encode() in p.stderr


def test_cli_flags_override_environment_and_yaml_for_output_behavior(tmp_path):
    cfg = tmp_path / 'env.yaml'
    cfg.write_text('Debug: true\n')
    p = run('--config', str(cfg), '--debug=false', '--version', env={'OV_DEBUG': 'false'})
    assert p.returncode == 0 and p.stdout == b'ov version dev rev:HEAD\n'
    assert p.stderr == b''
