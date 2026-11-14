import os
import subprocess
from pathlib import Path
import pytest

EXE = Path('/workspace/executable')

def run(args=(), data=b'', *, env=None, cwd=None, timeout=8):
    e = os.environ.copy()
    e['NO_COLOR'] = ''
    if env:
        e.update(env)
    return subprocess.run([str(EXE), *map(str,args)], input=data, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, env=e, cwd=cwd, timeout=timeout)

def ok(p):
    assert p.returncode == 0, (p.returncode, p.stderr)
    assert p.stderr == b''

def plain(data=b'ABC', *args):
    p=run(['--color=never',*args],data)
    ok(p)
    return p.stdout.decode()

def test_version_aliases():
    for arg in ('-V','--version'):
        p=run([arg], b'ignored'); ok(p); assert p.stdout == b'hexyl 0.16.0\n'

def test_help_short_and_long_contract():
    a=run(['--help']); b=run(['-h']); ok(a); ok(b)
    long=a.stdout.decode(); short=b.stdout.decode()
    assert long.startswith('A command-line hex viewer') and long.endswith('\n')
    assert 'Usage: executable [OPTIONS] [FILE]' in long
    for name in ('--length','--skip','--block-size','--no-squeezing','--color','--border','--plain','--no-characters','--characters','--character-table','--color-scheme','--no-position','--display-offset','--panels','--group-size','--endianness','--base','--terminal-width','--print-color-table','--include','--completion','--help','--version'):
        assert name in long and name in short
    assert 'Print help (see more with' in short and len(short)<len(long)

def test_help_short_circuits_later_tokens_but_not_prior_errors():
    p=run(['--help','--invalid','/missing']); ok(p); assert b'Usage:' in p.stdout
    p=run(['--invalid','/missing','--help']); assert p.returncode==2 and not p.stdout and b"unexpected argument '--invalid' found" in p.stderr

def test_option_end_marker_literal_missing_path(tmp_path):
    p=run(['--','--help'],cwd=tmp_path); assert p.returncode==1 and p.stderr==b'Error: No such file or directory (os error 2)\n'

def test_standard_view_snapshot():
    expected='''┌────────┬─────────────────────────┬─────────────────────────┬────────┬────────┐
│00000000│ 30 31 32 33 34 35 36 37 ┊ 38 39 61 62 63 64 65 0a │01234567┊89abcde_│
└────────┴─────────────────────────┴─────────────────────────┴────────┴────────┘\n'''
    assert plain(b'0123456789abcde\n')==expected

def test_partial_panel_snapshot():
    assert plain(b'abc')=='┌────────┬─────────────────────────┬─────────────────────────┬────────┬────────┐\n│00000000│ 61 62 63                ┊                         │abc     ┊        │\n└────────┴─────────────────────────┴─────────────────────────┴────────┴────────┘\n'

def test_default_panels_and_explicit_panels():
    assert plain(bytes(range(16))).count('│000000')==1
    assert plain(bytes(range(16)),'--panels=1').count('│000000')==2
    assert plain(b'A','--panels=3').count('┊')==4

def test_no_characters_and_no_position_snapshots():
    assert plain(b'ABC','--no-characters')=='┌────────┬─────────────────────────┬─────────────────────────┐\n│00000000│ 41 42 43                ┊                         │\n└────────┴─────────────────────────┴─────────────────────────┘\n'
    assert plain(b'ABC','--no-position').startswith('┌─────────────────────────')

def test_plain_layout_exact():
    assert plain(b'XYZ','--plain')=='  58 59 5a                                           \n'
    assert 'XYZ' not in plain(b'XYZ','--plain','--characters')

def test_empty_input_and_zero_length():
    p=run(['--color=never'],b''); ok(p); assert 'No content' in p.stdout.decode()
    assert 'No content' in plain(b'ABC','-n','0')

def test_numeric_bases_fixed_width():
    for base, fragment in [('2','01000001'),('8','101'),('10','065'),('16','41')]:
        assert fragment in plain(b'A','--base='+base,'--panels=1')
    assert '01000001' in plain(b'ABC','-b','binary','--panels=1')

def test_grouping_and_little_endian():
    d=bytes(range(8))
    assert '0001 0203 0405 0607' in plain(d,'--group-size=2','--panels=1')
    assert '0100 0302 0504 0706' in plain(d,'--group-size=2','-e','--panels=1')
    assert '00010203 04050607' in plain(d,'-g','4','--panels=1')
    assert '0001020304050607' in plain(d,'-g','8','--panels=1')

def test_skip_length_and_display_offset(tmp_path):
    f=tmp_path/'data'; f.write_bytes(bytes(range(64)))
    s=plain(b'',str(f),'-s','3','-n','5','--panels=1')
    assert '03 04 05 06 07' in s and '00000003' in s
    s=plain(b'',str(f),'--skip=0x10','--display-offset=0x20','--panels=1')
    assert '00000030' in s and '10 11' in s
    assert '00 01' in plain(b'',str(f),'--display-offset=20','--panels=1')

def test_negative_skip_regular_and_pipe_failure(tmp_path):
    f=tmp_path/'tail'; f.write_bytes(b'abcdef')
    assert '64 65 66' in plain(b'',str(f),'--skip=-3','--panels=1')
    p=run(['--color=never','--skip=-1'],b'abc'); assert p.returncode==1 and b'Failed to jump' in p.stderr

def test_skip_past_eof_and_length_is_maximum(tmp_path):
    f=tmp_path/'x'; f.write_bytes(b'abc')
    assert 'No content' in plain(b'',str(f),'--skip=99')
    assert '61 62 63' in plain(b'',str(f),'--length=100','--panels=1')

def test_block_units_and_hex_block_size_quirk():
    assert '10 11' in plain(bytes(range(40)),'--block-size=16','--skip=1block','--panels=1')
    assert '00 01 02 03 04 05 06 07' in plain(bytes(range(20)),'--block-size=8','--length=1block','--panels=1')
    p=run(['--block-size=0x10'],b'abc'); ok(p); assert p.stdout==b''

def test_count_units_and_aliases():
    assert '00 01 02 03' in plain(bytes(range(20)),'--length=4','--panels=1')
    for flag in ('--length','--bytes','-c','-l'):
        assert plain(b'abcdef',flag+'=2','--panels=1').count(' 0') >= 1

def test_count_parse_errors_have_envelopes():
    cases=[('','no character data found'),('+','no digits found after sign'),('0x+1',"found '+' sign after hex prefix"),('kB','valid unit'),('1xyz','invalid unit'),('1.5','invalid unit ".5"'),('9223372036854775808','failed to parse integer part')]
    for value, phrase in cases:
        p=run(['--skip='+value]); assert p.returncode==1 and phrase.encode() in p.stderr

def test_bad_block_size_direct_errors():
    for val, phrase in [('0','block size argument must be positive'),('0x0','block size argument must be positive'),('0x+','no digits found after sign')]:
        p=run(['--block-size='+val]); assert p.returncode==1 and phrase.encode() in p.stderr
    p=run(['--block-size=1block']); assert p.returncode==1 and b"can not use 'block(s)'" in p.stderr

def test_invalid_base_diagnostics():
    p=run(['--base=3']); assert p.returncode==1 and b'Valid bases are 2, 8, 10, and 16.' in p.stderr
    p=run(['--base=wat']); assert p.returncode==1 and b'Valid bases are "b", "o", "d", and "x".' in p.stderr

def test_cli_grammar_errors_and_enum_choices():
    p=run(['-n']); assert p.returncode==2 and b"value is required for '--length <N>'" in p.stderr
    p=run(['--unknown']); assert p.returncode==2 and b"unexpected argument '--unknown' found" in p.stderr
    p=run(['a','b']); assert p.returncode==2
    for arg, choices in [('--color=bad',b'always, auto, never, force'),('--group-size=3',b'1, 2, 4, 8'),('--completion=nope',b'bash')]:
        p=run([arg]); assert p.returncode==2 and b'possible values' in p.stderr and choices in p.stderr

def test_panels_terminal_width_calculation():
    for width, count in [(1,1),(60,1),(80,2),(150,4),(200,5),(500,14)]:
        p=run(['--color=never','--terminal-width='+str(width)],b'A'); ok(p)
        assert p.stdout.count('┊')==2*(count-1)
    p=run(['--panels=2','--terminal-width=100']); assert p.returncode==2

def test_panels_invalid_and_negative_token():
    p=run(['--panels=abc']); assert p.returncode==1 and b'failed to parse `--panels`' in p.stderr
    p=run(['--panels','-1']); assert p.returncode==2 and p.stderr.startswith(b"error: unexpected argument '-1' found")

def test_directory_missing_file():
    p=run(['/not/a/real/path']); assert p.returncode==1 and p.stderr==b'Error: No such file or directory (os error 2)\n'
    p=run(['/workspace']); assert p.returncode==1 and b"is a directory" in p.stderr

def test_ascii_border_and_borderless_layout():
    s=plain(b'ABC','--border=ascii','--panels=1'); assert s.startswith('+--------+') and '|' in s
    s=plain(b'Hello World','--border=none'); assert not any(c in s for c in '┌┐│└┘') and s.endswith('\n')

def test_character_tables_default_and_ascii():
    data=bytes([0,9,10,11,12,13,32,65,127,128,255])
    s=plain(data,'--panels=2'); assert '⋄_ _•__ A•××' in s
    a=plain(data,'--character-table=ascii','--panels=2'); assert '.......A...' in a

def test_braille_table_mapping():
    s=plain(bytes([1,2,4,8,16,32,64,128,11,12,127,255]),'--character-table=braille','--panels=2')
    assert '⠁⠈⠂⠐⠄ @⢀' in s and '⠙⠒⡿⣿' in s

def test_codepage_437_and_1047_tables():
    assert 'ﬀ' in plain(b'\xff','--character-table=codepage-437','--panels=1')
    assert 'HELLO WO' in plain(bytes.fromhex('c8c5d3d3d640e6d6d9d3c4'),'--character-table=codepage-1047','--panels=2')

def test_squeezing_uniform_only_and_disabled():
    s=plain(b'X'*32); assert s.count('\n')==5 and '\n│*       │' in s and '00000020' in s
    assert '*' not in plain(b'1234567812345678','--panels=1')
    assert '*' not in plain(b'X'*32,'--no-squeezing')

def test_squeeze_nonuniform_repeated_rows():
    row=b'DATA1___'*4
    assert '*' not in plain(row*2,'--panels=4')

def test_include_stdin_exact_and_empty():
    p=run(['--include'],b'ABCD'); ok(p); assert p.stdout==b'  0x41, 0x42, 0x43, 0x44\n'
    for args in (['--include'],['--include','--length=0'],['--include','--skip=9']):
        p=run(args,b''); ok(p); assert p.stdout==b'\n'

def test_include_named_file_exact_and_identifier(tmp_path):
    f=tmp_path/'small.txt'; f.write_bytes(b'Hello')
    p=run(['--include',str(f)]); ok(p)
    assert p.stdout==b'unsigned char small_txt[] = {\n  0x48, 0x65, 0x6c, 0x6c, 0x6f\n};\nunsigned int small_txt_len = 5;\n'
    g=tmp_path/'a-b.c +é'; g.write_bytes(b'')
    p=run(['--include',str(g)]); ok(p); assert 'a_b_c__é_len = 0;' in p.stdout.decode()

def test_include_conflicts_with_explicit_endianness():
    for arg in ('--endianness=big','-e'):
        p=run(['--include',arg]); assert p.returncode==2 and b'cannot be used with' in p.stderr

def test_color_modes_and_no_color():
    for args, env, colored in [(['--color=never'],{},False),(['--color=always'],{},True),(['--color=always'],{'NO_COLOR':'1'},False),(['--color=force'],{'NO_COLOR':'1'},True)]:
        p=run([*args,'--panels=1'],b'A',env=env); ok(p); assert (b'\x1b[' in p.stdout)==colored

def test_color_categories_and_overrides():
    p=run(['--color=force','--panels=1'],bytes([0,65,32,1,128])); ok(p)
    for code in (b'\x1b[90m',b'\x1b[36m',b'\x1b[32m',b'\x1b[33m'):
        assert code in p.stdout
    p=run(['--color=force','--panels=1'],b'A',env={'HEXYL_COLOR_ASCII_PRINTABLE':'blue'}); ok(p); assert b'\x1b[34m' in p.stdout
    p=run(['--color=force','--panels=1'],b'A',env={'HEXYL_COLOR_ASCII_PRINTABLE':'#aBcD09'}); ok(p); assert b'\x1b[38;2;171;205;9m' in p.stdout

def test_gradient_color_examples():
    p=run(['--color=force','--color-scheme=gradient','--plain','--panels=1'],bytes([1,2,9,32,72,127,128,144,224,240,255])); ok(p)
    for seq in (b'\x1b[38;2;255;000;255m',b'\x1b[38;2;250;000;255m',b'\x1b[38;2;000;128;255m',b'\x1b[38;2;000;181;201m',b'\x1b[38;2;064;128;000m',b'\x1b[38;2;255;048;000m',b'\x1b[38;2;255;255;249m'):
        assert seq in p.stdout

def test_color_table_exact_ending():
    p=run(['--print-color-table']); ok(p); assert p.stdout.startswith(b'hexyl color reference:\n\x1b[90m') and p.stdout.endswith(b'\x1b[39m') and not p.stdout.endswith(b'\n')

def test_completion_shells_prefix_and_content():
    prefixes={'bash':b'_hexyl() {\n    local i cur prev opts cmd\n', 'zsh':b'#compdef hexyl\n\nautoload -U is-at-least\n', 'fish':b"complete -c hexyl -s n", 'elvish':b'\nuse builtin;\nuse str;\n', 'powershell':b'\nusing namespace System.Management.Automation\n'}
    for shell,prefix in prefixes.items():
        p=run(['--completion='+shell]); ok(p); assert p.stdout.startswith(prefix) and len(p.stdout.splitlines())>=20
        for word in (b'hexyl',b'length',b'skip',b'color',b'help',b'version'): assert word in p.stdout

def test_completion_invalid_choice():
    p=run(['--completion=tcsh']); assert p.returncode==2 and b'possible values' in p.stderr
