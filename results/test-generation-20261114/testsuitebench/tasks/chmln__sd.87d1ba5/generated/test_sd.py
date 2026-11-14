import os
import subprocess
from pathlib import Path
import pytest

EXE = Path('/workspace/executable')
TIMEOUT = 5


def run(args=(), data=b'', cwd=None, env=None):
    e = os.environ.copy()
    if env:
        e.update(env)
    return subprocess.run([str(EXE), *map(str, args)], input=data, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, cwd=cwd, env=e, timeout=TIMEOUT)


def ok(args=(), data=b'', **kw):
    p = run(args, data, **kw)
    assert p.returncode == 0, (p.returncode, p.stdout, p.stderr)
    assert p.stderr == b''
    return p.stdout


@pytest.mark.parametrize('args,src,want', [
    (['help','assist'], b'I need help', b'I need assist'),
    (['-F','a.b','X'], b'a.b a0b', b'X a0b'),
    (['-s','a.b','X'], b'a.b a0b', b'X a0b'),
    (['--','--foo','-w'], b'--foo', b'-w'),
    (['foo','--','-w'], b'foo', b'-w'),
    (['--','-pattern','-replace'], b'-pattern', b'-replace'),
], ids=['positionals-help','fixed-long','fixed-legacy','dash-find','dash-replace','dash-pair'])
def test_positionals_fixed_and_double_dash(args, src, want):
    assert ok(args, src) == want


@pytest.mark.parametrize('args,expected', [(['--version'], b'sd 1.0.0\n'), (['-V'], b'sd 1.0.0\n')], ids=['long','short'])
def test_version(args, expected):
    assert ok(args) == expected


def test_help_forms_and_precedence():
    a = run(['--help']); b = run(['-h']); c = run(['a','b','--help']); d=run(['--help','--version'])
    for p in (a,b,c,d):
        assert p.returncode == 0 and not p.stderr
        assert b'sd v1.0.0' in p.stdout and b'An intuitive find & replace CLI' in p.stdout
        assert b'Usage: executable [OPTIONS] <FIND> <REPLACE_WITH> [FILES]...' in p.stdout
        assert b'Arguments:' in p.stdout and b'Options:' in p.stdout
        assert b'Commands:' not in p.stdout and b'Subcommands:' not in p.stdout
    assert len(a.stdout) > len(b.stdout)
    for phrase in [b'-p, --preview',b'-F, --fixed-strings',b'-n, --max-replacements',b'-f, --flags',b'-h, --help',b'-V, --version',b'human reviewable format',b'Treat FIND and REPLACE_WITH args as literal strings',b'[default: 0]',b'c - case-sensitive',b'e - disable multi-line matching',b'i - case-insensitive',b'm - multi-line matching',b's - make `.` match newlines',b'w - match full words only',b'The regexp or string (if using `-F`) to search for',b'Regex flags. May be combined (like `-f mc`).',b"Print help (see a summary with '-h')"]:
        assert phrase in a.stdout, phrase
    assert b"Print help (see more with '--help')" in b.stdout


@pytest.mark.parametrize('args,src,want', [
    (['\\d+','N'],b'1 22 333',b'N N N'),(['[aeiou]','X'],b'hello',b'hXllX'),
    (['cat|dog','animal'],b'cat dog',b'animal animal'),(['a.*b','X'],b'axbyyb',b'X'),
    (['<.*>','X'],b'<a><b>',b'X'),(['<.*?>','X'],b'<a><b>',b'XX'),
    (['aa','X'],b'aaaa',b'XX'),(['hello','X'],b'Hello HELLO hello',b'Hello HELLO X'),
    (['^line','X'],b'line1\nline2\nline3',b'X1\nX2\nX3'),
    (['end$','X'],b'1 end\n2 end\n3 end',b'1 X\n2 X\n3 X'),
    (['a.*b','X'],b'a\nb',b'a\nb'),(['a.*b','X','-f','s'],b'a\nb',b'X'),
    (['^line','X','-f','e'],b'line1\nline2',b'X1\nline2'),
    (['^line','X','--flags='],b'line1\nline2',b'X1\nX2'),
    (['hello','X','-f','i'],b'Hello HELLO hello',b'X X X'),
    (['hello','X','-f','ci'],b'Hello hello',b'X X'),
    (['hello','X','-f','ic'],b'Hello hello',b'Hello X'),
],ids=['digit','class','alternate','greedy','greedy-dot','lazy-dot','nonoverlap','case','line-start','line-end','dot-newline-off','dotall','anchors-off','empty-flags','flag-i','ci-order','ic-order'])
def test_regex_core(args,src,want):
    assert ok(args,src) == want


@pytest.mark.parametrize('flags,want', [('iw',b'Test TEST X'),('wi',b'X X X')], ids=['iw','wi'])
def test_word_flag_order(flags,want):
    assert ok(['test','X','-f',flags],b'Test TEST test') == want


def test_word_boundaries_unicode_and_alternation():
    src='test testing retest test_case test-test 123 test123 123test café caféx'.encode()
    assert ok(['test|123','X','-f','w'],src)==b'X Xing retest X_case X-X X XX 123test caf\xc3\xa9 caf\xc3\xa9x'
    assert ok(['test','X','-f','w'],b'testing retest test_case test-test')==b'testing retest test_case X-X'


def test_flags_fixed_and_option_forms():
    assert ok(['-F','-f','i','TEST','replaced'],b'test TEST Test')==b'replaced replaced replaced'
    assert ok(['-pF','foo','X'],b'foo')==b'X'
    assert ok(['-Fp','foo','X'],b'foo')==b'X'
    assert ok(['-fmc','^x','X'],b'X\nx')==b'X\nX'
    for args in (['-n','1','a','X'],['-n=1','a','X'],['--max-replacements','1','a','X'],['--max-replacements=1','a','X']):
        assert ok(args,b'a a a')==b'X a a'
    assert ok(['--flags','mc','^x','X'],b'X\nx')==b'X\nX'
    assert ok(['--flags=','^x','X'],b'x\nx')==b'X\nX'


@pytest.mark.parametrize('args,src,want',[
    (['(\\w+) (\\w+)','$2 $1'],b'hello world',b'world hello'),
    (['((a)(b))','$1-$2-$3'],b'ab',b'ab-a-b'),
    (['(?P<y>\\d{4})-(?P<m>\\d{2})','$m/$y'],b'2024-03',b'03/2024'),
    (['(test)','${1}abc'],b'test',b'testabc'),
    (['(x)','$0:$1:$1'],b'x x',b'x:x:x x:x:x'),
    (['x','$1/$2/$10/$99/$unknown/${}'],b'x',b'/////'),
    (['x','${'],b'x',b'${'),(['x','${1'],b'x',b'${1'),
    (['x','$$:$$$$:$$1:$'],b'x',b'$:$$:$1:$'),
],ids=['reorder','nested','named','braced-suffix','repeat','missing-groups','open-brace','incomplete-brace','dollars'])
def test_capture_expansion(args,src,want):
    assert ok(args,src)==want


@pytest.mark.parametrize('replacement,want',[(r'\n\r\t',b'\n\r\t'),(r'\\',b'\\'),(r"\'\"",b"'\""),
 (r'\x41',b'A'),(r'\u0041',b'A'),(r'\xFF',b'\xc3\xbf'),(r'\u2764',b'\xe2\x9d\xa4'),
 (r'\q\ \b\v\f',b'\\q\\ \\b\\v\\f'),(r'\xG1-\x4-\u00Z1-\u004',b'\\xG1-\\x4-\\u00Z1-\\u004'),
 ('\\',b'\\\\'),(r'prefix\x41suffix',b'prefixAuffix'),(r'hello\u263Aworld', 'hello☺orld'.encode()),
 (r'bar\u00415678',b'barA678'),(r'\xFFend', 'ÿnd'.encode()),(r'\x41X\x42',b'AB'),(r'\x41-\x42',b'AB'),(r'\x41\x42\x43',b'Ax42C')],
 ids=['simple','slash','quotes','hex','unicode-a','unicode-ff','heart','unsupported','malformed','trailing-slash','quirk-prefix','quirk-unicode','quirk-digits','quirk-ff','quirk-two','quirk-dash','quirk-adjacent'])
def test_replacement_escapes(replacement,want):
    assert ok(['x',replacement],b'x')==want


@pytest.mark.parametrize('pattern,src,want', [('',b'abc',b'XaXbXcX'),('',b'test\n',b'XtXeXsXtX\nX'),('b*',b'abc\n',b'XaXcX\nX'),('a*',b'baaabac\n',b'XbXbXcX\nX'),('^',b'test',b'START:test')], ids=['empty','empty-newline','zero-b','zero-a','anchor'])
def test_zero_width(pattern,src,want):
    repl='START:' if pattern=='^' else 'X'
    assert ok([pattern,repl],src)==want


@pytest.mark.parametrize('args', [['$1bad'],['$1Call'],['$2invalid'],['$12abc']],ids=['bad-one','bad-capital','bad-two','bad-multidigit'])
def test_ambiguous_replacement_diagnostic(args):
    repl=args[0]
    p=run(['x',repl],b'')
    assert p.returncode==1 and p.stdout==b''
    assert b'error: The numbered capture group' in p.stderr and b'hint: Use curly braces' in p.stderr
    assert repl.encode() in p.stderr and b'^' in p.stderr


def test_fixed_bypasses_ambiguity_and_replacement_interpretation():
    assert ok(['-F','foo','$1fine'],b'foo')==b'$1fine'
    assert ok(['-F','test',r'\n'],b'test test')==b'\\n \\n'
    assert ok(['-F',r'\n','X'],b'\\n')==b'X'


@pytest.mark.parametrize('pattern,reason', [('(','unclosed group'),('[z-a]','invalid character class range, the start must be <= the end'),(r'\k','unrecognized escape sequence'),('(?P<name>test)(?P<name>test)','duplicate capture group name'),('(?)','repetition operator missing expression'),('**','repetition operator missing expression'),('(?P<>test)','empty capture group name'),('(?P<incomplete','unclosed capture group name'),(r'(\w+) \1','backreferences are not supported'),('test(?=ing)','look-around, including look-ahead and look-behind, is not supported'),('(?<=test)ing','look-around, including look-ahead and look-behind, is not supported')],ids=['group','range','escape','duplicate','question','star','empty-name','open-name','backref','ahead','behind'])
def test_regex_errors(pattern,reason):
    p=run([pattern,'X'],b'')
    assert p.returncode==1 and p.stdout==b''
    assert b'error: invalid regex regex parse error:' in p.stderr
    assert pattern.encode() in p.stderr and ('error: '+reason).encode() in p.stderr


@pytest.mark.parametrize('args', [['a'],[],['a','X','--mispelled'],['find','--preveiw'],['find','--fixed-string'],['x','X','-n','abc'],['x','X','--max-replacements=-1'],['x','X','--max-replacements','18446744073709551616'],['x','X','-n'],['x','X','-f'],['x','X','-p','-p'],['x','X','-f','i','-f','m'],['x','X','-1']],ids=['one-pos','none','unknown','near-preview','near-fixed','bad-limit','negative-eq','overflow','missing-limit','missing-flags','repeat-preview','repeat-flags','negative-option'])
def test_cli_errors(args):
    p=run(args,b'')
    assert p.returncode==2 and p.stdout==b'' and p.stderr.startswith(b'error:')
    if args and args[-1]=='-1': assert b"unexpected argument '-1' found" in p.stderr
    if args and args[-1]=='-p': assert b'multiple times' in p.stderr or b'cannot be used multiple times' in p.stderr
    if args and args[-1]=='-f': assert b'multiple times' in p.stderr or b'cannot be used multiple times' in p.stderr


def test_cli_missing_unknown_and_empty_file_details(tmp_path):
    p=run([]); assert p.returncode==2 and b'<FIND>' in p.stderr and b'<REPLACE_WITH>' in p.stderr
    p=run(['find']); assert p.returncode==2 and b'<REPLACE_WITH>' in p.stderr
    p=run(['find','-w']); assert p.returncode==2 and b"unexpected argument '-w' found" in p.stderr and b"use '-- -w'" in p.stderr
    p=run(['find','--preveiw']); assert b"tip: a similar argument exists: '--preview'" in p.stderr
    p=run(['find','--fixed-string']); assert b"tip: a similar argument exists: '--fixed-strings'" in p.stderr
    f=tmp_path/'valid'; f.write_bytes(b'foo')
    p=run(['foo','bar',str(f),'']); assert p.returncode==2 and p.stdout==b'' and f.read_bytes()==b'foo'
    assert p.stderr==b"error: a value is required for '[FILES]...' but none was supplied\n\nFor more information, try '--help'.\n"


@pytest.mark.parametrize('value', ['1.5','1 2','18446744073709551616'],ids=['float','space','overflow'])
def test_invalid_limit_values(value):
    p=run(['x','X','-n',value])
    assert p.returncode==2 and b"invalid value '"+value.encode()+b"' for '--max-replacements <LIMIT>'" in p.stderr
    assert b'too large' in p.stderr if value.startswith('184') else True


@pytest.mark.parametrize('args,src,want', [
 (['a','X','-n','2'],b'a a a',b'X X a'),(['a','X','-n','999999999'],b'a a',b'X X'),
 (['^','X'],b'\r\nabc\rlf\n',b'\r\nabc\rlf\n'),(['foo','X'],b'\x00\x01foo\xff\xfe',b'\x00\x01X\xff\xfe'),
 (['café','X'],'café caféx'.encode(),'X caféx'.encode()),(['é','X'],'e\u0301 é'.encode(),'e\u0301 X'.encode()),
 (['never','X'],b'abc\x00\xff',b'abc\x00\xff'),(['.*',''],b'anything',b''),
],ids=['limit','large-limit','crlf','binary','unicode-word','unicode-accent','no-match-binary','empty-output'])
def test_bytes_unicode_and_limits(args,src,want):
    assert ok(args,src)==want


def test_large_input_and_many_matches():
    src=b'a'*210000+b' '+b'a '*30000
    got=ok(['a','Z'],src)
    assert got==b'Z'*210000+b' '+b'Z '*30000


def test_stdin_preview_and_empty_input():
    assert ok(['x','X','-p'],b'x')==b'X'
    assert ok(['x','X'],b'')==b''
    assert ok(['x','X','-p'],b'')==b''


def test_files_in_place_mode_permissions_names_and_per_source_limit(tmp_path):
    paths=[]
    for name in ['a','b','space name','ü-file','-dash']:
        p=tmp_path/name; p.write_bytes(b'a a'); p.chmod(0o640); paths.append(p)
    result=run(['a','z','-n','1',*map(str,paths)])
    assert result.returncode==0 and result.stdout==b'' and result.stderr==b''
    for p in paths: assert p.read_bytes()==b'z a' and (p.stat().st_mode&0o777)==0o640


def test_file_preview_one_and_multi(tmp_path):
    a=tmp_path/'a'; b=tmp_path/'b'; a.write_bytes(b'foo'); b.write_bytes(b'none')
    p=run(['foo','X','-p',str(a)]); assert p.returncode==0 and p.stdout==b'X' and a.read_bytes()==b'foo'
    p=run(['foo','X','-p',str(a),str(b)]); assert p.returncode==0
    assert p.stdout==f'----- FILE {a} -----\n'.encode()+b'X'+f'----- FILE {b} -----\n'.encode()+b'none'
    assert a.read_bytes()==b'foo' and b.read_bytes()==b'none'


def test_missing_file_validates_before_writing(tmp_path):
    good=tmp_path/'good'; good.write_bytes(b'foo'); missing='/nonexistent/file.txt'
    p=run(['foo','bar',str(good),missing])
    assert p.returncode==1 and p.stdout==b'' and good.read_bytes()==b'foo'
    assert p.stderr==f'error: invalid path: {missing}\n'.encode()
    p=run(['foo','bar','--','--nonexistent-flag'])
    assert p.returncode==1 and p.stderr==b'error: invalid path: --nonexistent-flag\n'


def test_directory_and_symlink(tmp_path):
    p=run(['x','y',str(tmp_path)]); assert p.returncode==1 and b'os error 19' in p.stderr
    target=tmp_path/'target'; target.write_bytes(b'foo'); link=tmp_path/'link'; link.symlink_to(target)
    p=run(['foo','longer',str(link)]); assert p.returncode==0 and link.is_symlink() and target.read_bytes()==b'longer'
    p=run(['longer','',str(link)]); assert p.returncode==0 and link.is_symlink() and target.read_bytes()==b''


def test_home_configuration_is_ignored(tmp_path):
    assert ok(['hello','X'],b'Hello hello',env={'HOME':str(tmp_path/'missing-home'),'XDG_CONFIG_HOME':str(tmp_path/'missing-xdg')})==b'Hello X'


def test_pathological_regex_terminates():
    p=run(['(a+)+b','X'],b'a'*100000)
    assert p.returncode==0 and p.stdout==b'a'*100000 and p.stderr==b''
