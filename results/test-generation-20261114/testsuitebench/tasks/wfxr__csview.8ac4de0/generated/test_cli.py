import os
import subprocess
from pathlib import Path

import pytest

EXE = Path('/workspace/executable')


def run(args=(), data=b'', *, cwd=None):
    return subprocess.run([str(EXE), *map(str, args)], input=data, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, cwd=cwd, timeout=15)


def ok(args=(), data=b''):
    p = run(args, data)
    assert p.returncode == 0, (p.returncode, p.stderr)
    assert p.stderr == b''
    assert p.stdout.endswith(b'\n')
    return p.stdout.decode('utf-8')


def test_version_and_alias():
    for arg in ('--version', '-V'):
        p = run([arg])
        assert (p.returncode, p.stdout, p.stderr) == (0, b'csview 1.3.4\n', b'')


def test_help_exact_and_ordered_exit():
    p = run(['--help'])
    assert p.returncode == 0 and p.stderr == b''
    assert p.stdout.startswith(b'A high performance csv viewer with cjk/emoji support.\n\nUsage: executable [OPTIONS] [FILE]\n')
    assert p.stdout.endswith(b"  -V, --version\n          Print version\n")
    assert b'\x1b' not in p.stdout
    assert run(['--help', '--unknown']).stdout == p.stdout
    assert run(['--version', '--help']).stdout == b'csview 1.3.4\n'
    assert run(['--unknown', '--help']).returncode == 2


def test_default_and_styles():
    data = b'Name,Age\nAlice,30\nBob,25\n'
    expected = '┌───────┬─────┐\n│ Name  │ Age │\n├───────┼─────┤\n│ Alice │ 30  │\n│ Bob   │ 25  │\n└───────┴─────┘\n'
    assert ok(data=data) == expected
    assert ok(['--style', 'rounded'], data) .startswith('╭')
    reinforced = ok(['--style', 'reinforced'], data)
    assert reinforced.startswith('┏') and '─' in reinforced and '━' not in reinforced
    assert ok(['--style', 'MARKDOWN'], data).startswith('| Name')


def test_ascii_ascii2_markdown_and_grid():
    data = b'a,b\n1,2\n'
    assert ok(['--style', 'ascii'], data) == '+---+---+\n| a | b |\n+---+---+\n| 1 | 2 |\n+---+---+\n'
    assert ok(['--style', 'markdown'], data) == '| a | b |\n|---|---|\n| 1 | 2 |\n'
    grid = ok(['--style', 'grid'], b'a\n1\n2\n')
    assert grid.count('├') == 2
    ascii2 = ok(['--style', 'ascii2'], data)
    assert ascii2 == '  a | b  \n ---+--- \n  1 | 2  \n'


def test_no_style_and_empty_inputs():
    assert ok(['--style', 'none'], b'Name,Age\nAlice,30\nBob,25\n') == ' Name   Age \n Alice  30  \n Bob    25  \n'
    assert ok([], b'') == '┌┐\n││\n└┘\n'
    assert ok(['--style', 'none'], b'') == '\n'
    assert ok(['--style', 'sharp'], b'a,b\n') == '┌───┬───┐\n│ a │ b │\n└───┴───┘\n'


def test_no_headers_and_headerless_one_row():
    assert ok(['-H'], b'a,b\n1,2\n') == '┌───┬───┐\n│ a │ b │\n│ 1 │ 2 │\n└───┴───┘\n'
    assert ok(['--no-headers'], b'x\n') == '┌───┐\n│ x │\n└───┘\n'


def test_numbering_and_aliases():
    data = b'item\na\nb\n'
    expected = '┌───┬──────┐\n│ # │ item │\n├───┼──────┤\n│ 1 │ a    │\n│ 2 │ b    │\n└───┴──────┘\n'
    assert ok(['-n'], data) == expected
    assert ok(['--seq'], data) == expected
    assert ok(['-H', '-n'], b'a\nb\n') == '┌───┬───┐\n│ 1 │ a │\n│ 2 │ b │\n└───┴───┘\n'


@pytest.mark.parametrize('args,delim', [
    (['-d','|'], '|'), (['-d|'], '|'), (['-d=|'], '|'),
    (['--delimiter',';'], ';'), (['--delimiter=:'], ':'),
    (['--delimiter=='], '='), (['-d',' '], ' '), (['-t'], '\t'),
], ids=['short','short-attached','short-equals','semicolon','long-equals','equals','space','tsv'])
def test_delimiter_forms(args, delim):
    data = f'a{delim}b\n1{delim}2\n'.encode()
    out = ok(args, data)
    assert '│ a │ b │' in out and '│ 1 │ 2 │' in out


def test_delimiter_byte_truncation_and_no_autodetect():
    assert 'a界b' in ok(['-d','界'], 'a界b\nx界y\n'.encode())
    output = ok(['-d','界'], b'aLb\nxLy\n')
    assert '│ a │ b │' in output
    assert '│ x │ y │' in output
    assert ok([], b'a|b\n1|2\n').count('│') == 6


def test_csv_quoting_empty_fields_unicode_and_line_endings():
    out = ok([], b'"a,b","say ""hi""",\r\n"x\ny", z,\r\n')
    assert 'a,b' in out and 'say "hi"' in out and 'x\ny' in out
    assert '\r' not in out
    assert ok([], b'\xef\xbb\xbfa,b\r\n1,2\n')
    assert ok([], b',,\n,,\n').count('│') > 0
    assert ok([], b'\n') == '┌┐\n││\n└┘\n'


def test_input_file_options_after_and_dash_filename(tmp_path):
    f = tmp_path / 'data.csv'
    f.write_bytes(b'a,b\n1,2\n')
    assert run([str(f), '-H']).returncode == 0
    assert run(['-P', str(f)]).stdout == ok([], b'a,b\n1,2\n').encode()
    special = tmp_path / '-data'
    special.write_bytes(b'x\n')
    p = run(['--', str(special)])
    assert p.returncode == 0 and 'x' in p.stdout.decode()
    assert run([], b'a,b\n1,2\n').stdout == run([str(f)]).stdout


def test_sniff_truncates_but_keeps_rows():
    out = ok(['--sniff','1'], b'h\nxx\nabcdef\n')
    assert 'abcdef' not in out and 'ab' in out
    assert out.count('│') == 8
    assert 'abcdef' in ok(['--sniff','0'], b'h\nxx\nabcdef\n')
    nohead = ok(['-H','--sniff','1'], b'xx\nabcdef\n')
    assert 'abcdef' not in nohead and 'xx' in nohead


def test_alignment_padding_indent_and_numbers():
    out = ok(['--padding','0','--header-align','right','--body-align','center','--indent','2'], b'x\na\n')
    assert out == '  ┌─┐\n  │x│\n  ├─┤\n  │a│\n  └─┘\n'
    assert ok(['-H','--padding','2','--indent','1'], b'a\n').startswith(' ┌─────┐\n')
    numbered = ok(['-n','--body-align','right'], b'h\n1\n')
    assert '│ 1 │' in numbered


def test_display_width_and_safe_truncation():
    out = ok([], 'h\n你好\n'.encode())
    assert '你好' in out
    emoji = ok([], 'h\n🙂\n'.encode())
    assert '🙂' in emoji
    assert '10' in ok(['--sniff','1'], b'h\n12\n1000\n')
    assert '12345' in ok(['--sniff','1'], b'h\n12345\nThis is long\n')


def test_embedded_newline_output():
    out = ok([], b'address\n"123 Main St\nApt 4B"\n')
    assert '123 Main St\nApt 4B' in out


def test_mismatch_is_atomic_and_diagnostic():
    p = run([], b'a,b,c\n1,2,3\n4,5\n')
    assert p.returncode == 1 and p.stdout == b''
    assert p.stderr == b'csview: CSV error: record 2 (line: 3, byte: 12): found record with 2 fields, but the previous record has 3 fields\n'


def test_invalid_utf8_is_atomic_and_diagnostic():
    p = run([], b'name,value\ntest,data\ninvalid,\xff\xfe\n')
    assert p.returncode == 1 and p.stdout == b''
    assert p.stderr == b'csview: CSV parse error: record 2 (line 3, field: 1, byte: 21): invalid utf-8: invalid UTF-8 in field 1 near byte index 0\n'


def test_cli_errors_and_help_order():
    p = run(['--unknown'])
    assert p.returncode == 2 and p.stdout == b'' and b"unexpected argument '--unknown'" in p.stderr
    assert b'Usage: executable [OPTIONS] [FILE]' in p.stderr
    assert b"tip: to pass '--nonexistent-flag' as a value" in run(['--nonexistent-flag']).stderr
    assert b"unexpected argument 'b' found" in run(['a','b']).stderr
    assert run(['--unknown','--version']).returncode == 2


@pytest.mark.parametrize('option,val,meta', [('--padding','x','--padding <PADDING>'),('--indent','x','--indent <INDENT>'),('--sniff','x','--sniff <LIMIT>')], ids=['padding','indent','sniff'])
def test_invalid_integer_values(option,val,meta):
    p = run([option,val])
    assert p.returncode == 2 and p.stdout == b''
    assert meta.encode() in p.stderr and b'invalid digit found in string' in p.stderr
    assert b'Usage:' not in p.stderr and p.stderr.endswith(b"For more information, try '--help'.\n")


def test_negative_integer_tokens_are_unexpected():
    for opt,val in [('--padding','-1'),('--indent','-2'),('--sniff','-3')]:
        p = run([opt,val])
        assert p.returncode == 2 and p.stdout == b''
        assert f"unexpected argument '{val}' found".encode() in p.stderr
        assert b'Usage: executable [OPTIONS] [FILE]' in p.stderr


def test_delimiter_and_enum_validation():
    for args, phrase in [(['-d'],b"a value is required for '--delimiter <DELIMITER>'"),(['-d',''],b"cannot parse char from empty string"),(['-d','::'],b'too many characters in string')]:
        p=run(args); assert p.returncode==2 and p.stdout==b'' and phrase in p.stderr
        assert b'Usage:' not in p.stderr
    p=run(['--style','bad'])
    assert p.returncode==2 and b"invalid value 'bad' for '--style <STYLE>'" in p.stderr
    assert all(x in p.stderr for x in (b'none',b'ascii',b'ascii2',b'sharp',b'rounded',b'reinforced',b'markdown',b'grid'))
    for opt in ('--header-align','--body-align'):
        assert run([opt,'middle']).returncode==2


def test_tsv_delimiter_conflict():
    a=run(['-t','-d',',']); b=run(['-d',';','-t'])
    assert a.returncode==2 and b.returncode==2
    assert b"cannot be used with" in a.stderr and b"Usage: executable --tsv [FILE]" in a.stderr
    assert b"cannot be used with" in b.stderr and b"Usage: executable --delimiter <DELIMITER> [FILE]" in b.stderr


def test_missing_file_and_many_rows(tmp_path):
    p=run([str(tmp_path/'missing')])
    assert p.returncode==1 and p.stdout==b''
    assert p.stderr==b'csview: No such file or directory (os error 2)\n'
    data=b'h\n'+b''.join(f'{i}\n'.encode() for i in range(1000))
    out=ok([],data)
    assert '999' in out and '1000' in out
    assert out.count('│') == 2002
