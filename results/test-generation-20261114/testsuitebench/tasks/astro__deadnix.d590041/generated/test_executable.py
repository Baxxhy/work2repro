import json
import os
import pathlib
import subprocess
import tempfile

import pytest


EXE = pathlib.Path('/workspace/executable')


def run(args=(), cwd=None, env=None):
    e = os.environ.copy()
    e.pop('NO_COLOR', None)
    if env:
        e.update(env)
    return subprocess.run([str(EXE), *map(str, args)], cwd=cwd, env=e,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def put(root, name, text):
    p = root / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding='utf-8')
    return p


def records(proc):
    return [json.loads(line) for line in proc.stdout.decode().splitlines()]


def test_help_and_version_are_exact():
    p = run(['--help'])
    assert p.returncode == 0 and p.stderr == b''
    assert p.stdout.decode().startswith('Find dead code in .nix files\n\nUsage:')
    assert p.stdout.endswith(b'\n')
    assert '  -h, --hidden' in p.stdout.decode()
    v = run(['-V'])
    assert (v.returncode, v.stdout, v.stderr) == (0, b'deadnix 1.3.1\n', b'')
    assert run(['--version']).stdout == v.stdout


@pytest.mark.parametrize('args,fragment', [
    (['--output-format'], "a value is required for '--output-format <OUTPUT_FORMAT>'"),
    (['-o', 'xml'], "invalid value 'xml' for '--output-format <OUTPUT_FORMAT>'"),
    (['--bogus'], "unexpected argument '--bogus'"),
    (['--output-format', 'json', '-o', 'json'], 'cannot be used multiple times'),
    (['--exclude'], "a value is required for '--exclude <EXCLUDES>...'"),
    (['--exclude', 'x', '--exclude', 'y'], 'cannot be used multiple times'),
], ids=['format-missing','format-invalid','unknown','format-repeat','exclude-missing','exclude-repeat'])
def test_cli_validation(args, fragment):
    p = run(args)
    assert p.returncode == 2
    assert fragment in p.stderr.decode()


def test_operand_names_options_and_default_scan(tmp_path):
    put(tmp_path, 'check', 'let gone = 1; in false')
    put(tmp_path, 'scan.nix', 'let gone = 1; in false')
    p = run(['-o', 'json', 'check', '--', 'scan.nix'], cwd=tmp_path)
    assert p.returncode == 0
    assert [r['file'] for r in records(p)] == ['scan.nix']
    p = run(['-o', 'json'], cwd=tmp_path)
    assert len(records(p)) == 1 and records(p)[0]['file'].endswith('scan.nix')


def test_extensions_mixed_paths_and_missing_non_nix(tmp_path):
    put(tmp_path, 'A.NIX', 'let x = 1; in false')
    put(tmp_path, 'b.Nix', 'let y = 1; in false')
    put(tmp_path, 'ignore.txt', 'bad')
    p = run(['-o', 'json', 'ignore.txt', 'missing.txt', 'A.NIX', 'b.Nix'], cwd=tmp_path)
    rs = records(p)
    assert [r['file'] for r in rs] == ['missing.txt', 'A.NIX', 'b.Nix']
    assert 'No such file or directory' in rs[0]['results'][0]['message']


def test_directory_order_hidden_recursion_and_explicit_hidden(tmp_path):
    put(tmp_path, 'tree/z.nix', 'let z = 0; in false')
    put(tmp_path, 'tree/a/a.nix', 'let a = 0; in false')
    put(tmp_path, 'tree/.hidden.nix', 'let h = 0; in false')
    put(tmp_path, 'tree/.deep/x.nix', 'let x = 0; in false')
    p = run(['-o','json','tree'], cwd=tmp_path)
    assert [r['file'] for r in records(p)] == ['tree/a/a.nix', 'tree/z.nix']
    p = run(['-o','json','-h','tree'], cwd=tmp_path)
    assert len(records(p)) == 4
    p = run(['-o','json','tree/.hidden.nix'], cwd=tmp_path)
    assert len(records(p)) == 1


def test_json_shapes_order_locations_and_reachability(tmp_path):
    pth = put(tmp_path, 'loc.nix', 'let\n  dead1 = dead2;\n  dead2 = dead3;\n  dead3 = 42;\nin false')
    p = run(['-o','json',pth])
    r = records(p)[0]
    assert set(r) == {'file','results'}
    assert [(x['line'],x['column'],x['endColumn'],x['message']) for x in r['results']] == [
        (2,3,8,'Unused let binding: dead1'), (3,3,8,'Unused let binding: dead2'),
        (4,3,8,'Unused let binding: dead3')]
    put(tmp_path,'live.nix','let a = b + 1; b = c + 1; c = 1; in a')
    assert run(['-o','json',tmp_path/'live.nix']).stdout == b''


def test_lexical_context_strings_comments_selectors_and_shadowing(tmp_path):
    src = 'let name = "world"; foo = 1; dead = 2; in "# foo ${name}" + (let foo = 3; in foo)'
    pth = put(tmp_path,'lex.nix',src)
    r = records(run(['-o','json',pth]))[0]['results']
    assert [x['message'] for x in r] == ['Unused let binding: foo','Unused let binding: dead']
    put(tmp_path,'sel.nix','{ bar, foo }: bar.foo')
    assert [x['message'] for x in records(run(['-o','json',tmp_path/'sel.nix']))[0]['results']] == ['Unused lambda pattern: foo']


def test_lambda_patterns_aliases_inherit_and_attr_paths(tmp_path):
    pth=put(tmp_path,'forms.nix','args@{ used, unused, ... }: used + args.other')
    r=records(run(['-o','json',pth]))[0]['results']
    assert [(x['column'],x['endColumn'],x['message']) for x in r] == [(14,20,'Unused lambda pattern: unused')]
    pth=put(tmp_path,'inh.nix','let inherit (grave) a b c; in false')
    assert [x['message'] for x in records(run(['-o','json',pth]))[0]['results']] == [f'Unused let binding: {x}' for x in 'abc']
    pth=put(tmp_path,'path.nix','let foo.alive = 1; foo.dead = 2; in false')
    r=records(run(['-o','json',pth]))[0]['results']
    assert [(x['column'],x['message']) for x in r] == [(5,'Unused let binding: foo'),(20,'Unused let binding: foo')]


def test_flags_compose_and_underscore_policy(tmp_path):
    pth=put(tmp_path,'flags.nix','_x: { _m, a, ... }@_alias: let _v = 1; in false')
    base=[x['message'] for x in records(run(['-o','json',pth]))[0]['results']]
    assert base == ['Unused lambda pattern: _m','Unused lambda pattern: a','Unused lambda pattern: _alias','Unused let binding: _v']
    assert records(run(['-o','json','-lL',pth]))[0]['results'] == [
        {'column':21,'endColumn':27,'line':1,'message':'Unused lambda pattern: _alias'},
        {'column':33,'endColumn':35,'line':1,'message':'Unused let binding: _v'}]
    pth=put(tmp_path,'used.nix','let _x = 1; in _x')
    assert records(run(['-o','json','-W',pth]))[0]['results'][0]['message']=='Used let binding: _x'
    assert run(['-o','json','-W','-_',pth]).stdout == b''


def test_skip_pragma_only_next_physical_line(tmp_path):
    pth=put(tmp_path,'skip.nix','let\n # deadnix: skip\n first = 1;\n # deadnix: skip\n second = 2;\n # explanation\n third = 3;\nin false')
    names=[x['message'] for x in records(run(['-o','json',pth]))[0]['results']]
    assert names == ['Unused let binding: first','Unused let binding: third']


def test_output_modes_quiet_fail_and_color(tmp_path):
    pth=put(tmp_path,'dead.nix','let x = 1; in false')
    p=run([pth]); out=p.stdout.decode()
    assert 'Warning: Unused declarations were found.' in out and 'Unused let binding: x' in out
    assert b'\x1b[' in p.stdout
    p=run([pth],env={'NO_COLOR':''}); assert b'\x1b[' not in p.stdout and 'Unused let binding: x' in p.stdout.decode()
    p=run(['-f','-q',pth]); assert p.returncode==1 and p.stdout==p.stderr==b''
    p=run(['-q','-f','-o','json',pth]); assert p.returncode==1 and p.stdout==b''
    p=run(['-o','json','-q',pth]); assert p.stdout==b''


def test_filesystem_and_parser_errors_are_per_file(tmp_path):
    bad=put(tmp_path,'bad.nix','')
    good=put(tmp_path,'good.nix','let x = 1; in false')
    p=run(['-o','json',bad,'missing.nix',good])
    rs=records(p)
    assert p.returncode==0 and len(rs)==3
    assert 'unexpected end of file' in rs[0]['results'][0]['message']
    assert rs[1]['file']=='missing.nix' and 'No such file' in rs[1]['results'][0]['message']
    assert rs[2]['file']==str(good)
    p=run([bad]); assert b'Error parsing file' in p.stderr and p.returncode==0


def test_parse_error_details_and_continue(tmp_path):
    cases=[('let','unexpected end of file'),('let x = ; in alive','unexpected TOKEN_SEMICOLON'),
           ('let x = @@@; in x','unexpected TOKEN_AT at 8..9')]
    paths=[]
    for i,(s,_) in enumerate(cases): paths.append(put(tmp_path,f'e{i}.nix',s))
    for pth,(_,msg) in zip(paths,cases):
        rr=records(run(['-o','json',pth]))[0]['results']
        assert any(msg in x['message'] for x in rr)


def test_exclusion_canonical_and_explicit_override(tmp_path):
    put(tmp_path,'d/a.nix','let x = 1; in false')
    put(tmp_path,'d/sub/b.nix','let y = 1; in false')
    p=run(['-o','json','--exclude',tmp_path/'d/sub','--',tmp_path/'d'],cwd=tmp_path)
    assert len(records(p))==1
    p=run(['-o','json','--exclude',tmp_path/'d/a.nix','--',tmp_path/'d/a.nix'])
    assert len(records(p))==1


def test_edit_let_inherit_and_whole_let(tmp_path):
    cases=[('let dead = 42; alive = 23; in alive','let alive = 23; in alive'),
           ('let dead1 = 1; dead2 = 2; alive = 4; in alive','let alive = 4; in alive'),
           ('let dead = 42; in alive','alive'),
           ('let inherit dead1 dead2 alive; in alive','let inherit alive; in alive'),
           ('let inherit (x) dead; alive = true; in alive','let alive = true; in alive'),
           ('let outer = let inner = 1; in 2; in 3','3')]
    for i,(src,want) in enumerate(cases):
        pth=put(tmp_path,f'e{i}.nix',src)
        p=run(['-e',pth]); assert p.returncode==0
        assert pth.read_text(encoding='utf-8')==want


def test_edit_lambda_patterns_and_fail_status(tmp_path):
    cases=[('dead: false','_dead: false'),('{ bar, foo }: bar','{ bar }: bar'),
           ('alive@{ dead ? true, ... }: alive','alive@{ ... }: alive'),
           ('dead@{ ... }: false','{ ... }: false'),('{ ... }@dead: false','{ ... }: false'),
           ('dead1@{ dead2, alive, ... }: alive','{ alive, ... }: alive')]
    for i,(src,want) in enumerate(cases):
        pth=put(tmp_path,f'l{i}.nix',src)
        p=run(['-e','-f','-q',pth]); assert p.returncode==1
        assert pth.read_text(encoding='utf-8')==want


def test_edit_skips_pragma_and_never_edits_malformed(tmp_path):
    pth=put(tmp_path,'pragma.nix','let\n # deadnix: skip\n a = 1;\n b = 2;\nin false')
    run(['-e',pth]); assert pth.read_text(encoding='utf-8')=='let\n # deadnix: skip\n a = 1;\nin false'
    bad=put(tmp_path,'bad.nix','let x = ; in x')
    before=bad.read_bytes(); run(['-e',bad]); assert bad.read_bytes()==before


def test_symlink_file_and_broken_link(tmp_path):
    real=put(tmp_path,'real.nix','let x = 1; in false')
    link=tmp_path/'alias.nix'; link.symlink_to(real)
    broken=tmp_path/'broken.nix'; broken.symlink_to(tmp_path/'absent.nix')
    p=run(['-o','json',link,broken]); rs=records(p)
    assert [r['file'] for r in rs]==[str(link),str(broken)]
    assert 'No such file' in rs[1]['results'][0]['message']
