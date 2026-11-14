import gzip
import bz2
import lzma
import os
import re
import subprocess
from pathlib import Path

import pytest

EXE = Path('/workspace/executable')
if not EXE.exists():
    EXE = Path(__file__).resolve().parent.parent / 'executable'


def run(*args, data=b'', cwd=None):
    return subprocess.run([str(EXE), *map(str, args)], input=data, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, cwd=cwd, timeout=15)


def ok(*args, data=b''):
    p = run(*args, data=data)
    assert p.returncode == 0, (p.returncode, p.stderr)
    assert p.stderr == b''
    return p.stdout


@pytest.mark.parametrize('flag', ['-h', '--help'], ids=['short-help', 'long-help'])
def test_help_shape(flag):
    p = run(flag)
    assert p.returncode == 0 and p.stderr == b''
    s = p.stdout.decode()
    assert 'Usage: executable [OPTIONS] [INPUT]...' in s
    assert 'Arguments:' in s and 'Options:' in s and '[INPUT]...' in s
    assert '[INPUT]...  Input files to parse, defaults to stdin' in s
    for text in ['-o, --output <OUTPUT>', '-d, --delimiter <DELIMITER>', '-L, --delim-is-literal',
                 '-I, --use-input-delim', '-D, --output-delimiter <OUTPUT_DELIMITER>',
                 '-f, --fields <FIELDS>', '-e, --exclude <EXCLUDE>',
                 '-E, --exclude-header <EXCLUDE_HEADER>', '-F, --header-field <HEADER_FIELD>',
                 '-r, --header-is-regex', '-z, --try-decompress', '-Z, --try-compress',
                 '-t, --compression-threads <COMPRESSION_THREADS>',
                 '-l, --compression-level <COMPRESSION_LEVEL>', '--no-mmap', '--crlf', '-h, --help', '-V, --version']:
        assert text in s
    if flag == '--help':
        assert '## Selection by headers' in s and '## Ordering of outputs' in s
        assert 'output delimiter' in s.lower() and '`-D`' in s
        assert len(p.stdout) > len(ok('-h'))


@pytest.mark.parametrize('flag', ['-h', '--help'], ids=['h', 'help'])
def test_help_precedence(flag):
    assert run(flag, '--definitely-invalid').returncode == 0
    p = run('--definitely-invalid', flag)
    assert p.returncode == 2 and p.stdout == b''
    assert b"error: unexpected argument '--definitely-invalid' found" in p.stderr


def test_version():
    for flag in ['-V', '--version']:
        p = run(flag)
        assert p.returncode == 0 and not p.stderr
        assert re.fullmatch(rb'hck\s+\S+\n', p.stdout)


@pytest.mark.parametrize('args', [('-f', '1'), ('-f1',), ('-f=1',), ('--fields', '1'), ('--fields=1',)], ids=['short-separated','short-joined','short-equals','long-separated','long-equals'])
def test_field_option_forms(args):
    assert ok(*args, data=b'abc') == b'abc\n'


def test_input_sources_order_and_stdin_rules(tmp_path):
    a, b = tmp_path/'a', tmp_path/'b'
    a.write_bytes(b'A\n'); b.write_bytes(b'B\n')
    assert ok(str(a), '-', str(b), data=b'S\n') == b'A\nS\nB\n'
    assert ok(str(a), data=b'IGNORED\n') == b'A\n'
    assert ok(data=b'') == b''


def test_options_between_inputs(tmp_path):
    a, b = tmp_path/'a', tmp_path/'b'
    a.write_bytes(b'a b\n'); b.write_bytes(b'c d\n')
    assert ok(str(a), '-f2', str(b)) == b'b\nd\n'


@pytest.mark.parametrize('data,expected', [(b'abc',b'abc\n'),(b'\n\n\n',b'\n\n\n'),(b'a\n\nb\n',b'a\n\nb\n')], ids=['unterminated','empty-records','interior-empty'])
def test_records(data, expected):
    assert ok('-f1', data=data) == expected


def test_bytes_nul_invalid_utf8_and_unicode():
    assert ok('-f', '1,3', '-d', ',', data=b'\xff\x00x,y,z\xfe\n') == b'\xff\x00x\tz\xfe\n'
    assert ok('-L', '-d', '💠', '-f', '2,1', data='α💠β\n'.encode()) == 'β\tα\n'.encode()


@pytest.mark.parametrize('args,data,expected', [
    ((), b'a  b\tc\n',b'a\tb\tc\n'),
    (('-d','[,;]'),b'a,b;c\n',b'a\tb\tc\n'),
    (('-d',','),b'a,,,b\n',b'a\t\t\tb\n'),
    (('-d',',+'),b'a,,,b\n',b'a\tb\n'),
    (('-d','(,|;)'),b'a,b;c\n',b'a\tb\tc\n'),
    (('-d','[0-9]+'),b'a12b3c\n',b'a\tb\tc\n'),
    (('-d','(?i)x'),b'aXbxc\n',b'a\tb\tc\n'),
    (('-d',r'\.'),b'a.b.c\n',b'a\tb\tc\n'),
    (('-d','[[:space:]]+'),b'a\tb c\n',b'a\tb\tc\n'),
], ids=['default-whitespace','class','single-comma','comma-run','group-alternation','digits','inline-case','escaped-dot','posix-space'])
def test_regex_delimiters(args,data,expected):
    assert ok(*args, data=data) == expected


@pytest.mark.parametrize('pattern,reason', [('[','unclosed character class'),('(','unclosed group')], ids=['class-error','group-error'])
def test_bad_regex_diagnostic(pattern,reason):
    p=run('-d',pattern,data=b'a\n')
    assert p.returncode == 1 and p.stdout == b''
    assert b'regex parse error' in p.stderr and pattern.encode() in p.stderr and b'^' in p.stderr and reason.encode() in p.stderr


def test_empty_matching_regex_terminates():
    assert ok('-d','.*','-f1',data=b'abc\n') == b'\n'


@pytest.mark.parametrize('delimiter,data,fields,expected', [
    ('|',b'a|b|c\n','2,1,3',b'b\ta\tc\n'),('.*',b'a.*b\n','2,1',b'b\ta\n'),
    ('::',b'a::b::c\n','2',b'b\n'),(' ',b'a b c\n','1,3',b'a\tc\n'),
    (r'\t',b'a\tb\n','2,1',b'b\ta\n'),(r'\n',b'a\nb\n','1',b'a\tb\n'),
    ('\\',b'a\\\\b\n','2,1',b'b\ta\n'),('💠','a💠b\n'.encode(),'2','b\n'.encode()),
], ids=['pipe','regex-meta','multi-byte','space','tab-escape','newline-escape','backslash','unicode'])
def test_literal_delimiters(delimiter,data,fields,expected):
    assert ok('-L','-d',delimiter,'-f',fields,data=data) == expected


def test_literal_empty_fields():
    assert ok('-L','-d',',','-f','2,4',data=b',a,b,c\n') == b'a\tc\n'
    assert ok('-L','-d',',','-f','2,3,4',data=b'a,,c,\n') == b'\tc\t\n'
    assert ok('-L','-d','long','-f1',data=b'abc\n') == b'abc\n'


@pytest.mark.parametrize('fields,expected', [
    ('2',b'b\n'),('2-4',b'b\tc\td\n'),('-3',b'a\tb\tc\n'),('3-',b'c\td\te\tf\n'),
    ('4-,1-3',b'd\te\tf\ta\tb\tc\n'),('1-2,4,6-',b'a\tb\td\tf\n'),
    ('01,2-2',b'a\tb\n'),('3,1,2',b'c\ta\tb\n'),('3,3,1,2',b'c\ta\tb\n'),
    ('3,1,3',b'c\ta\n'),('1-3,2-4',b'a\tb\tc\td\n'),('4-,1,5-8',b'd\te\tf\ta\n')
], ids=['single','closed-range','open-low','open-high','reordered-ranges','mixed','leading-zero','order','duplicate','duplicate-late','overlap','open-range-overlap'])
def test_field_selection(fields,expected):
    assert ok('-f',fields,data=b'a b c d e f\n') == expected


@pytest.mark.parametrize('fields,expected', [('3-10',b'c\td\n'),('5,100,2',b'e\tb\n'),('2-',b'\n\n'),('100',b'\n\n\n\n')], ids=['clip','missing-between','all-missing-tail','all-missing'])
def test_ragged_and_missing_fields(fields,expected):
    data = b'a b c d\n' if fields=='3-10' else b'a b c d e f g h i j\n' if fields=='5,100,2' else b'a\nb\n' if fields=='2-' else b'a b\nc d\ne f\ng h\n'
    assert ok('-f',fields,data=data) == expected


def test_empty_rows_quotes_and_crlf():
    assert ok('-f','2',data=b'\n   \na\n') == b'\n\n\n'
    assert ok('-L','-d',',','-f','1,3',data=b'"a,b",x,"c"\n') == b'"a\t"c"\n'
    assert ok('--crlf','-f','1,2',data=b'a b\r\nc d\r\n') == b'a\tb\r\nc\td\r\n'
    assert ok('-f1',data=b'a b\r\n') == b'a\n'


@pytest.mark.parametrize('args,expected', [
    (('-e','2,4'),b'a\tc\te\tf\n'),(('-e','3-'),b'a\tb\n'),
    (('-f','1-5','-e','3'),b'a\tb\td\te\n'),(('-f','3-','-e','-5'),b'f\n'),
    (('-f','2-5','-e','3-'),b'b\n'),(('-f','1-','-e','3-5'),b'a\tb\tf\n'),
], ids=['exclude-indices','exclude-open-high','include-exclude','exclude-prefix','exclude-tail','exclude-range'])
def test_numeric_exclusion(args,expected):
    assert ok(*args,data=b'a b c d e f\n') == expected


@pytest.mark.parametrize('args', [('-f','4,3','-e','2-5'),('-f','1','-e','1'),('-e','1-')], ids=['cancel-list','cancel-single','exclude-all'])
def test_cancelled_numeric_selection_has_no_records(args):
    assert ok(*args,data=b'a b\nc d\n') == b''


@pytest.mark.parametrize('fields,expected', [('2,2,2',b'b\n'),('1-3,2-4',b'a\tb\tc\td\n'),('1,2,3,4,1,2',b'a\tb\tc\td\n')], ids=['repeat','overlapping','later-repeat'])
def test_literal_selection_dedup(fields,expected):
    assert ok('-L','-d',',','-f',fields,data=b'a,b,c,d\n') == expected


@pytest.mark.parametrize('fields,expected', [('2,2,2',b'b\tb\n'),('1-2,2-3,3-4',b'a\tb\tc\tc\td\n'),('1,2-,4',b'a\tb\tc\td\td\n')], ids=['legacy-repeated-single','legacy-overlap-ranges','legacy-open-range'])
def test_literal_legacy_overlap(fields,expected):
    assert ok('-L','-d',',','-f',fields,data=b'a,b,c,d\n') == expected


def test_literal_fast_path_leading_empty_panics():
    p=run('-L','-d',',','-f','1,2,4,5',data=b',a,b,\n')
    assert p.returncode == 101 and p.stdout == b'' and b'attempted to index slice up to maximum usize' in p.stderr
    assert ok('-L','-d',',','-f','2,4,5',data=b',a,b,\n') == b'a\t\n'


@pytest.mark.parametrize('name,expected', [('city',b'city\tcity\nNYC\tLA\n'),('name',b'name\nAlice\n')], ids=['duplicate-header','single-header'])
def test_literal_header_selectors(name,expected):
    assert ok('-L','-d',',','-F',name,data=b'name,city,city\nAlice,NYC,LA\n') == expected


def test_header_order_literal_and_exactness():
    assert ok('-L','-d',',','-F','city','-F','name',data=b'name,city\nAlice,NYC\n') == b'city\tname\nNYC\tAlice\n'
    assert ok('-L','-d',',','-F',' name ',data=b'name, name ,age\nx,y,z\n') == b' name \ny\n'
    p=run('-L','-d',',','-F','^is_.*$',data=b'is_ok,x\ny,z\n')
    assert p.returncode == 1 and b'No headers matched' in p.stderr


def test_header_missing_diagnostic():
    p=run('-L','-d',',','-F','name','-F','missing',data=b'name,age\na,1\n')
    assert p.returncode == 1 and b'Header not found: missing' in p.stderr


def test_header_regex_search_order_and_patterns():
    assert ok('-L','-d',',','-r','-F','^b','-F','a',data=b'aa,bx,ab,by\n1,2,3,4\n') == b'bx\tab\tby\taa\n2\t3\t4\t1\n'
    assert ok('-r','-F','(?i)NAME',data=b'first name\tName\tusername\n1\t2\t3\n') == b'name\tName\tusername\n1\t2\t3\n'
    assert ok('-r','-F','^ST.*',data=b'STAT START stop\n1 2 3\n') == b'STAT\tSTART\n1\t2\n'


def test_header_regex_parse_time_validation():
    p=run('-r','-F','[',data=b'')
    assert p.returncode == 2 and b"invalid value '[' for '--header-field <HEADER_FIELD>'" in p.stderr
    assert b'regex parse error:' in p.stderr and b"For more information, try '--help'." in p.stderr


def test_header_exclusion_and_all_removed():
    assert ok('-L','-d',',','-E','age',data=b'name,age,city\nAlice,30,NYC\n') == b'name\tcity\nAlice\tNYC\n'
    assert ok('-L','-d',',','-r','-E','CPU','-E','^ST.*',data=b'USER,PID,%CPU,STAT,TIME\nu,p,c,s,t\n') == b'USER\tPID\tTIME\nu\tp\tt\n'
    assert ok('-L','-d',',','-F','name','-E','name',data=b'name,age\nAlice,30\n') == b'\n\n'


@pytest.mark.parametrize('args,expected', [
    (('-f','3','-F','b','-F','a'),b'b\tc\ta\n2\t3\t1\n'),
    (('-f','3','-F','PID','-F','USER'),b'PID\tCPU\tUSER\n2\t3\t1\n'),
    (('-f','1,3','-F','age'),b'name\tage\tcity\nN\tA\tC\n'),
    (('-f','4,2','-F','name'),b'name\tage\tsalary\nN\tA\tS\n'),
], ids=['merge-rank-example1','merge-rank-example2','merge-union','legacy-merge'])
def test_numeric_header_union_merge(args,expected):
    if 'PID' in args:
        data=b'USER,PID,CPU\n1,2,3\n'
    elif 'age' in args and '1,3' in args:
        data=b'name,age,city\nN,A,C\n'
    elif 'salary' in expected.decode():
        data=b'name,age,city,salary\nN,A,C,S\n'
    else:
        data=b'a,b,c,d,e\n1,2,3,4,5\n'
    assert ok('-L','-d',',',*args,data=data) == expected


def test_exclusion_after_union_original_indices():
    assert ok('-L','-d',',','-f','1-3','-F','d','-e','2','-E','d',data=b'a,b,c,d\nA,B,C,D\n') == b'a\tc\nA\tC\n'


@pytest.mark.parametrize('delimiter,expected', [('',b'ac\n'),('::',b'a::c\n'),(r'\t',b'a\tc\n'),(r'\n',b'a\nc\n'),(r'\\',b'a\\c\n')], ids=['empty','multibyte','tab','newline','escaped-slash'])
def test_output_delimiter(delimiter,expected):
    assert ok('-L','-d',',','-D',delimiter,'-f','1,3',data=b'a,b,c\n') == expected


def test_input_delimiter_reuse():
    assert ok('-L','-d',',','-I','-f','1,3',data=b'a,b,c\n') == b'a,c\n'
    assert ok('-d',',','-I','-f','1,3',data=b'a,b,c\n') == b'a\tc\n'
    assert ok('-L','-d',',','-I','-D',';', '-f','1,3',data=b'a,b,c\n') == b'a,c\n'


def test_output_files(tmp_path):
    out=tmp_path/'nested'/'out'
    p=run('-o',str(out),data=b'a b\n')
    assert p.returncode == 1 and p.stdout == b'' and b'Failed to open' in p.stderr and str(out).encode() in p.stderr
    out=tmp_path/'out'
    out.write_bytes(b'old old\n')
    p=run('-o',str(out),'-f','2',data=b'a b\n')
    assert p.returncode == 0 and not p.stdout and out.read_bytes()==b'b\n'
    assert out.stat().st_mode & 0o600 == 0o600
    assert ok('-o','-',data=b'x\n')==b'x\n'
    p=run('-o',str(tmp_path),data=b'x\n')
    assert p.returncode == 1 and b'Failed to open' in p.stderr


@pytest.mark.parametrize('ext,compressor', [('.gz',gzip.compress),('.bz2',bz2.compress),('.xz',lzma.compress)], ids=['gzip','bzip2','xz'])
def test_decompress_files(tmp_path,ext,compressor):
    path=tmp_path/('input'+ext)
    path.write_bytes(compressor(b'a b\nc d\n'))
    assert ok('-z','-f','2',str(path)) == b'b\nd\n'


def test_gzip_decompress_stdin_numeric_and_failures():
    assert ok('-z','-f','2',data=gzip.compress(b'a b\n')) == b'b\n'
    p=run('-z','-f2',data=b'a b\n')
    assert p.returncode == 1 and p.stdout == b'' and b'unexpected end of file' in p.stderr
    p=run('-z',data=b'bad')
    assert p.returncode == 1 and b'invalid gzip header' in p.stderr


def test_compressed_stdin_header_panics():
    for flag,warning in [('-F',True),('-E',False)]:
        p=run('-z',flag,'name' if flag=='-F' else 'age',data=gzip.compress(b'name age\nA 1\n'))
        assert p.returncode == 101 and p.stdout == b''
        assert b'not implemented: Header selections not supported when piping gzipped stdin' in p.stderr
        assert (b'Selections based on header fields is not currently supported on STDIN compressed data.' in p.stderr) == warning


def test_compress_output_stdout_file_and_empty(tmp_path):
    p=run('-Z',data=b'a b\n')
    assert p.returncode == 0 and not p.stderr and p.stdout.startswith(b'\x1f\x8b')
    assert gzip.decompress(p.stdout)==b'a\tb\n'
    p=run('-Z',data=b'')
    assert p.returncode==0 and p.stdout.startswith(b'\x1f\x8b') and gzip.decompress(p.stdout)==b''
    path=tmp_path/'compressed-output.gz'
    p=run('-Z','-o',str(path),data=b'a b\n')
    assert p.returncode==0 and p.stdout==b'' and gzip.decompress(path.read_bytes())==b'a\tb\n'


@pytest.mark.parametrize('level,threads', [('1','0'),('6','1'),('9','2'),('6','8')], ids=['fast-zero','default-one','best-two','eight-threads'])
def test_compression_controls(level,threads):
    p=run('-Z','-l',level,'-t',threads,data=b'payload\n')
    assert p.returncode==0 and gzip.decompress(p.stdout)==b'payload\n'


def test_decompress_process_recompress():
    p=run('-z','-Z','-f','2',data=gzip.compress(b'a b\n'))
    assert p.returncode==0 and gzip.decompress(p.stdout)==b'b\n'


@pytest.mark.parametrize('args,message', [
    (('-f','0'),'Fields and positions are numbered from 1: 0'),(('-e','0'),'Fields and positions are numbered from 1: 0'),
    (('-f','5-2'),'High end of range less than low end of range: 5-2'),
], ids=['zero-field','zero-exclusion','reversed-range'])
def test_field_list_errors(args,message):
    p=run(*args,data=b'a b\n')
    assert p.returncode==1 and p.stdout==b'' and message.encode() in p.stderr


@pytest.mark.parametrize('item', ['', 'x', '1,', ',1', '1,,2', '1--5', '1-2-3', '999999999999999999999999999999999'], ids=['empty','nonnumeric','trailing-comma','leading-comma','double-comma','extra-dash1','extra-dash2','overflow'])
def test_bad_field_items(item):
    p=run('-f',item,data=b'a\n')
    assert p.returncode==1 and p.stdout==b'' and b'Failed to parse field:' in p.stderr


def test_lone_dash_field_diagnostic():
    p=run('-f','-',data=b'a\n')
    assert p.returncode==1 and p.stdout==b''
    line=p.stderr.decode(errors='replace').strip()
    assert re.fullmatch(r'\[.* ERROR hck\] Failed to parse field:',line)


def test_missing_input_and_option_named_path(tmp_path):
    p=run('/nonexistent.csv',str(tmp_path/'valid'))
    assert p.returncode==1 and p.stdout==b'' and b'No such file or directory (os error 2)' in p.stderr
    p=run('--','--help')
    assert p.returncode==1 and b'No such file or directory' in p.stderr


@pytest.mark.parametrize('args,needle', [
    (('--definitely-invalid',),'unexpected argument'),(('-o',),'a value is required for'),
    (('-f',),'a value is required for'),(('-d',),'a value is required for'),
    (('-f','1','-f','2'),'cannot be used multiple times'),
    (('-t','notint'),"invalid value 'notint'"),(('-t','-1'),"unexpected argument '-1'"),
], ids=['unknown','missing-output','missing-fields','missing-delimiter','repeat-fields','bad-threads','negative-thread'])
def test_argument_syntax_errors(args,needle):
    p=run(*args)
    assert p.returncode==2 and p.stdout==b'' and needle.encode() in p.stderr
    if args==('-t','-1'):
        assert b"tip: to pass '-1' as a value" in p.stderr


def test_no_mmap_compatibility():
    assert ok('--no-mmap','-L','-d',',','-f','3,1','-e','2',data=b'a,b,c\n')==b'c\ta\n'
    assert ok('--no-mmap','-f','2',data=b'a b\n')==b'b\n'


def test_large_fields_columns_and_records():
    huge=b'x'*200000
    assert ok('-f','1',data=huge+b' z\n')==huge+b'\n'
    row=b' '.join([b'v']*3000)+b'\n'
    assert ok('-f','2999,3000',data=row)==b'v\tv\n'
    payload=b'a b\n'*20000
    assert ok('-f','2',data=payload)==b'b\n'*20000
