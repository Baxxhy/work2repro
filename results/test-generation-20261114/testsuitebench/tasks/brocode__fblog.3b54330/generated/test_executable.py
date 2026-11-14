import os
import subprocess
from pathlib import Path

BIN = Path('/workspace/executable')


def run(args=(), data=b'', env=None):
    e = os.environ.copy()
    e.pop('NO_COLOR', None)
    if env:
        e.update(env)
    return subprocess.run([str(BIN), *map(str, args)], input=data, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, env=e, timeout=15)


def custom(template, data, *args):
    return run([*args, '--main-line-format', template], data)


def test_version_exact():
    for flag in ('--version', '-V'):
        p = run([flag])
        assert (p.returncode, p.stdout, p.stderr) == (0, b'fblog 4.17.0\n', b'')


def test_help_contract():
    p = run(['--help'])
    assert p.returncode == 0 and b'Usage: executable [OPTIONS] [INPUT]' in p.stdout
    assert b'--map-level' in p.stdout and b'--placeholder-format' in p.stdout
    assert b'--generate-completions' not in p.stdout and b'SUBCOMMANDS' not in p.stdout


def test_empty_and_default_render():
    assert run(data=b'').stdout == b''
    p = run(data=b'{"timestamp":"2023-01-01T00:00:00Z","level":"info","message":"hello"}')
    assert p.returncode == 0
    assert p.stdout == b'\x1b[1m2023-01-01T00:00:00\x1b[0m \x1b[1;35m INFO\x1b[0m: hello\n'


def test_missing_fields_final_line():
    p = run(data=b'{"x":1}')
    assert p.stdout == b'\x1b[1m                   \x1b[0m \x1b[1;35mUNKNO\x1b[0m: \n'


def test_invalid_lines_passthrough_then_continue():
    p = run(data=b'not json\n[1]\n{"message":"ok"}\n', env={'NO_COLOR':'1'})
    assert p.returncode == 0
    assert p.stdout.startswith(b'\x1b[1;38;2;255;135;22m??? >\x1b[0m not json\n')
    assert b'??? >\x1b[0m [1]\n' in p.stdout and p.stdout.endswith(b': ok\n')


def test_crlf_and_whitespace_invalid():
    p = run(data=b'  \r\n{"message":"x"}\r\n')
    assert b'??? >\x1b[0m   \n' in p.stdout and p.stdout.endswith(b': x\n')


def test_prefix_trim_parse_and_invalid_first_brace():
    p = custom('{{fblog_prefix}}|{{fblog_message}}', '  svc: 🧪 {"message":"hi"}\n'.encode(), '-p')
    assert p.stdout == 'svc: 🧪|hi\n'.encode()
    p = run(['-p'], b'prefix {bad {"message":"later"}\n')
    assert b'??? >' in p.stdout and b'prefix {bad' in p.stdout


def test_recursive_flatten_and_numeric_array_order():
    p = run(['-d'], b'{"z":1,"tags":["a",null,2],"obj":{"b":true,"a":null},"x":[0,1,2,3,4,5,6,7,8,9,10,11,12]}\n')
    s = p.stdout.decode()
    assert 'obj > b' in s and 'obj > a' not in s
    assert 'tags[0]' in s and 'tags[1]: null' in s and 'tags[2]: 2' in s
    assert s.index('x[9]') < s.index('x[10]') < s.index('x[11]')


def test_additional_selection_boundaries_order():
    p = run(['-a','user','-a','arr'], b'{"user_id":"no","user":{"name":"yes"},"arr":[1,2]}\n')
    s = p.stdout.decode()
    assert 'user_id' not in s and 'user > name' in s
    assert s.index('user > name') < s.index('arr[0]') < s.index('arr[1]')


def test_dump_exclusions_exact():
    p = run(['-x','user > a'], b'{"user":{"a":1,"ab":2},"x":3}\n')
    s = p.stdout.decode()
    assert 'user > a:' not in s and 'user > ab' in s and 'x' in s


def test_templates_helpers_if_and_no_html_escape():
    p = custom('{{#if user.ok}}{{user.name}}<>&{{/if}}', b'{"user":{"ok":true,"name":"A"}}\n')
    assert p.stdout == b'A<>&\n'
    p = custom('{{bold (yellow message)}}', b'{"message":"x"}\n')
    assert p.stdout == b'\x1b[1m\x1b[33mx\x1b[0m\x1b[0m\n'


def test_custom_keys_and_raw_filter_mapping_order():
    p = custom('{{fblog_message}}|{{fblog_level}}', b'{"fallback":"F","other":"O"}\n', '-m','other')
    assert p.stdout == b'O|unknown\n'
    p = custom('{{fblog_level}}|{{level}}', b'{"level":"info"}\n', '--map-level','info=first','--map-level','info=error','-f','level == "info"','-d')
    assert p.stdout.startswith(b'error|info\n')


def test_timestamp_conversion():
    p = custom('{{fblog_timestamp}}', b'{"timestamp":"0"}\n{"timestamp":"2024-01-01T00:00:00+02:00"}\n')
    assert p.stdout == b'1970-01-01T00:00:00.000Z\n2024-01-01T00:00:00+02:00\n'


def test_filter_typed_globals_lua_dump_and_rejected_records():
    p = run(['-f','enabled and tonumber(n) > 1','--print-lua'], b'{"enabled":true,"n":"2","message":"yes"}\n{"enabled":false,"n":9}\n')
    assert p.stdout.count(b' = ') >= 5 and b': yes\n' in p.stdout
    assert b'enabled = false\n' in p.stdout


def test_filter_statements_prefix_and_filter_errors():
    p = run(['-p','-f','if keep then return true else return false end','--no-implicit-filter-return-statement'],
            b'pre {"keep":true,"message":"yes"}\nno {"keep":false,"message":"no"}\n')
    assert b'pre' in p.stdout and b'yes' in p.stdout and b'no ' not in p.stdout
    p = run(['-f','invalid syntax'], b'{"message":"first"}\n{"message":"second"}\n')
    assert p.returncode == 0 and p.stdout == b''
    assert p.stderr.count(b'Failed to apply filter expression') == 2 and b'SyntaxError' in p.stderr


def test_substitution_styles_and_original_additional():
    p = run(['-s','-a','message'], b'{"message":"hi {name} {n} {flag} {missing}","context":{"name":"Ada","n":2,"flag":false}}\n')
    s = p.stdout.decode()
    assert '\x1b[1;33mAda\x1b[0m' in s and '\x1b[1;36m2\x1b[0m' in s
    assert '\x1b[1;31mfalse\x1b[0m' in s and '\x1b[1;31mmissing\x1b[0m' in s
    assert 'hi {name} {n} {flag} {missing}' in s


def test_substitution_custom_format_implicitly_enables():
    p = run(['-F','[[key]]'], b'{"message":"[[x]]","context":{"x":"ok"}}\n')
    assert b'\x1b[1;33mok\x1b[0m' in p.stdout


def test_config_values_and_bad_types(tmp_path):
    cfg = tmp_path/'fblog.toml'
    cfg.write_text('message_keys = ["body"]\nmain_line_format = "{{fblog_message}}/{{fblog_level}}"\n[level_map]\ninfo = "debug"\n')
    p = run(['--config-file',str(cfg)], b'{"body":"configured","level":"info"}\n')
    assert p.stdout == b'configured/debug\n'
    cfg.write_text('message_keys = 7\n')
    p = run(['--config-file',str(cfg)])
    assert p.returncode != 0 and b'Could not parse config file' in p.stderr
    assert b'TOML parse error' in p.stderr and b'invalid type' in p.stderr


def test_cli_missing_operands_canonical_aliases():
    for flag, canonical in [('-a','--additional-value <additional-value>'),('-m','--message-key <message-key>'),
                            ('-t','--time-key <time-key>'),('-l','--level-key <level-key>'),
                            ('-x','--excluded-value <excluded-value>'),('-c','--context-key <context-key>'),
                            ('-F','--placeholder-format <placeholder-format>')]:
        p = run([flag])
        assert p.returncode == 2 and p.stdout == b'' and b'a value is required' in p.stderr
        assert canonical.encode() in p.stderr


def test_cli_conflicts_duplicates_map_and_input_errors(tmp_path):
    p=run(['-a','x','-x','y']); assert p.returncode == 2 and b'cannot be used with' in p.stderr
    p=run(['--print-lua','--print-lua']); assert p.returncode == 2 and b'cannot be used multiple times' in p.stderr
    p=run(['--map-level','BAD']); assert p.returncode == 2 and b"missing '='" in p.stderr
    p=run(['absent-file']); assert p.returncode != 0 and b"Can't open file: absent-file" in p.stderr
    f=tmp_path/'input'; f.write_text('{"message":"fromfile"}\n')
    assert b'fromfile' in run(['--',str(f)]).stdout


def test_completion_scripts_and_diagnostic():
    for shell in ('bash','zsh','fish'):
        p=run(['--generate-completions',shell])
        assert p.returncode == 0 and len(p.stdout)>100 and b'fblog' in p.stdout
        assert f'Generating completion file for {shell}...'.encode() in p.stderr
    p=run(['--generate-completions','fish'])
    assert b'complete -c fblog' in p.stdout
