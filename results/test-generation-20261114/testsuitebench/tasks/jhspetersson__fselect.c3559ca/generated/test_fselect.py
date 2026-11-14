import csv
import hashlib
import json
import os
import pathlib
import subprocess
import zipfile

EXE = pathlib.Path('/workspace/executable')


def run(q=None, *, cwd, opts=(), args=None, env=None, input_text=None):
    argv = [str(EXE), *opts]
    argv.extend(args if args is not None else ([] if q is None else [q]))
    e = os.environ.copy()
    e['NO_COLOR'] = '1'
    if env:
        e.update(env)
    return subprocess.run(argv, cwd=cwd, env=e, input=input_text, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def tree(tmp_path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path/'a.txt').write_text('alpha\n', encoding='utf-8')
    (tmp_path/'b.bin').write_bytes(b'\x00\xff')
    (tmp_path/'sub').mkdir()
    (tmp_path/'sub'/'c.txt').write_text('ccc', encoding='utf-8')
    return tmp_path


def test_no_query_usage(tmp_path):
    p = run(cwd=tmp_path)
    assert p.returncode == 0 and p.stdout.startswith('fselect 0.10.0\n')
    assert 'Usage: fselect' in p.stdout and p.stderr == ''


def test_version_first_argument(tmp_path):
    p = run(cwd=tmp_path, args=['--some-version-suffix'])
    assert p.returncode == 0 and p.stdout.startswith('fselect 0.10.0\n')
    assert 'For more detailed instructions' not in p.stdout


def test_help_no_color_contains_sections(tmp_path):
    p = run(cwd=tmp_path, args=['--help'])
    assert p.returncode == 0 and '\x1b[' not in p.stdout
    for s in ['Path Options:', 'Regex syntax:', 'Column Options:', 'Functions:', 'Interactive mode:']:
        assert s in p.stdout


def test_query_args_concatenate_without_whitespace(tmp_path):
    (tmp_path/'empty').touch()
    p = run(cwd=tmp_path, opts=['--nocolor'], args=['select', 'name,', 'size', 'from', str(tmp_path), 'limit', '1'])
    assert (p.returncode, p.stdout, p.stderr) == (0, 'empty\t0\n', '')


def test_unknown_identifier_is_literal_and_function_token_is_not(tmp_path):
    p = run("md5 from . limit 1", cwd=tmp_path)
    assert p.returncode == 0 and p.stdout == 'md5\n'
    (tmp_path/'x.bin').touch()
    p = run("name from . where ext = bin", cwd=tmp_path)
    assert p.returncode == 0 and 'x.bin' not in p.stdout
    p = run("name from . where ext = 'bin'", cwd=tmp_path)
    assert p.stdout == 'x.bin\n'


def test_constants_alias_and_json(tmp_path):
    (tmp_path/'one').touch()
    p = run("select 'hello world' as Greeting, true as Flag from . limit 1 into json", cwd=tmp_path)
    assert p.returncode == 0
    assert json.loads(p.stdout) == [{'Flag':'true','Greeting':'hello world'}]


def test_omitted_select_and_glob_strict_eq(tmp_path):
    for n in ['FILE.TXT','File.txt','FiLe.TxT','a+b.txt','ab.txt']:
        (tmp_path/n).touch()
    p = run("name from . where name = '*.TXT' order by name", cwd=tmp_path)
    assert p.stdout.splitlines() == sorted(['FILE.TXT','File.txt','FiLe.TxT','a+b.txt','ab.txt'])
    p = run("name from . where name === '*.TXT'", cwd=tmp_path)
    assert p.stdout == ''
    p = run("name from . where name === 'FILE.TXT'", cwd=tmp_path)
    assert p.stdout == 'FILE.TXT\n'


def test_precedence_and_boolean_short_circuit(tmp_path):
    (tmp_path/'a.txt').write_bytes(b'x')
    (tmp_path/'b.bin').write_bytes(b'xx')
    p = run("name from . where size = 1 or size = 2 and ext = 'bin' order by name", cwd=tmp_path)
    assert p.stdout == 'a.txt\nb.bin\n'
    p = run("name from . where false and 1 / 0 = 1", cwd=tmp_path)
    assert p.returncode == 0 and p.stdout == '' and p.stderr == ''
    p = run("name from . where true or 1 / 0 = 1", cwd=tmp_path)
    assert p.returncode == 1 and 'Division by zero' in p.stderr


def test_arithmetic_coercion_and_errors(tmp_path):
    (tmp_path/'five').write_bytes(b'12345')
    p = run("2 + 3 * 4, (2 + 3) * 4, -size, -5, 0 - size, 5 / 2 from . limit 1", cwd=tmp_path)
    assert p.returncode == 0 and p.stdout == '14\t14\t5\t-5\t-5\t2.5\n'
    p = run('1 / 0 from .', cwd=tmp_path)
    assert p.returncode == 1 and p.stdout == '' and 'Division by zero' in p.stderr


def test_limits_offsets_order_and_grouping(tmp_path):
    for n, size in [('a',2),('b',10),('c',2)]:
        (tmp_path/n).write_bytes(b'x'*size)
    p = run('name,size from . order by size desc, name asc limit 1 offset 1', cwd=tmp_path)
    assert p.stdout == 'a\t2\n'
    p = run('ext,count(*),sum(size) from . group by ext order by sum(size) desc', cwd=tmp_path)
    assert p.stdout == '\t3\t14\n'
    p = run('count(*) from . where name = "missing"', cwd=tmp_path)
    assert p.stdout == '0\n'


def test_csv_lines_list_json_and_html(tmp_path):
    (tmp_path/'file,"name.txt').touch()
    q = "name, size from . limit 1"
    assert run(q+' into csv', cwd=tmp_path).stdout == '"file,""name.txt",0\n'
    assert run("name,size from . limit 1 into lines", cwd=tmp_path).stdout == 'file,"name.txt\n0\n'
    assert run("name from . limit 1 into list", cwd=tmp_path).stdout == 'file,"name.txt\0'
    j = run("name,is_dir from . limit 1 into json", cwd=tmp_path)
    assert json.loads(j.stdout) == [{'IsDir':'false','Name':'file,"name.txt'}]
    h = run("name from . where name = 'none' into html", cwd=tmp_path)
    assert h.returncode == 0 and '<table>' in h.stdout and '<th colspan="1">' in h.stdout
    assert not h.stdout.endswith('\n')


def test_names_paths_and_metadata(tmp_path):
    (tmp_path/'.hidden').touch(); (tmp_path/'archive.tar.gz').touch(); (tmp_path/'file.').touch()
    p = run('name,filename,ext,path,is_file,is_dir,is_empty from . order by name', cwd=tmp_path)
    rows = [x.split('\t') for x in p.stdout.splitlines()]
    assert rows == [
        ['.hidden','.hidden','','.hidden','true','false','true'],
        ['archive.tar.gz','archive.tar','gz','archive.tar.gz','true','false','true'],
        ['file.','file','','file.','true','false','true']]


def test_content_line_count_hashes_and_categories(tmp_path):
    data=b'a\r\nb\r\n'
    (tmp_path/'x.PY').write_bytes(data)
    p = run('line_count,sha1,sha256,is_source,is_text,is_binary from . limit 1', cwd=tmp_path)
    cells=p.stdout.rstrip('\n').split('\t')
    assert cells == ['2',hashlib.sha1(data).hexdigest(),hashlib.sha256(data).hexdigest(),'true','true','false']


def test_functions_and_unicode_lengths(tmp_path):
    (tmp_path/'x').touch()
    p=run("lower('ÄBC'),upper('ab'),length('🙂a'),initcap('hello.txt'),substr('abcdef',-2),locate('abc','b'),replace('aba','a','x'),trim('  x  '),coalesce('', 'ok') from . limit 1",cwd=tmp_path)
    assert p.stdout == 'äbc\tAB\t2\tHello.Txt\tef\t2\txbx\tx\tok\n'


def test_numeric_functions(tmp_path):
    (tmp_path/'x').touch()
    p=run('bin(10),hex(255),oct(8),abs(-4),sqrt(9),log(100),round(-1.5),pi() from . limit 1',cwd=tmp_path)
    cells=p.stdout.rstrip('\n').split('\t')
    assert cells[:7] == ['101','ff','10','4','3','2','-2']
    assert abs(float(cells[7])-3.141592653589793)<1e-14


def test_date_and_aggregate_behavior(tmp_path):
    for n,s in [('a.two',3),('b.two',4)]: (tmp_path/n).write_bytes(b'x'*s)
    p=run("count(*),count(ext),sum(size),avg(size),min(size),max(size),stddev_pop(size),var_pop(size) from .",cwd=tmp_path)
    cells=p.stdout.rstrip('\n').split('\t')
    assert cells[:6] == ['2','2','7','3.5','3','4']
    assert float(cells[6]) == .5 and float(cells[7]) == .25
    p=run("year('2024-02-29'),month('2024-02-29'),day('2024-02-29'),last_day('2024-02-01'),format_time(3661) from . limit 1",cwd=tmp_path)
    assert p.stdout == '2024\t2\t29\t2024-02-29\t1h,1m,1s\n'


def test_depth_multiple_roots_and_alias_context(tmp_path):
    root=tree(tmp_path/'root')
    p=run(f'name from {root} depth 1 order by name',cwd=tmp_path)
    assert p.stdout.splitlines() == ['a.txt','b.bin','sub']
    p=run(f'name from {root} mindepth 2 order by name',cwd=tmp_path)
    assert p.stdout == 'c.txt\n'
    p=run(f'name from {root} as r where r.size >= 0 order by name',cwd=tmp_path)
    assert p.returncode == 0 and len(p.stdout.splitlines()) == 4


def test_symlink_and_broken_link(tmp_path):
    d=tmp_path/'target'; d.mkdir(); (d/'child').touch()
    try:
        (tmp_path/'link').symlink_to(d, target_is_directory=True)
        (tmp_path/'broken').symlink_to(tmp_path/'missing')
    except OSError:
        return
    p=run('name,is_symlink from . order by name',cwd=tmp_path)
    assert 'link\ttrue\n' in p.stdout and 'broken\ttrue\n' in p.stdout
    p=run('path from . symlinks order by path',cwd=tmp_path)
    assert any(line.endswith('/target/child') for line in p.stdout.splitlines())


def test_regex_like_between_in(tmp_path):
    for n in ['a.txt','b.txt','c.bin']: (tmp_path/n).touch()
    assert run("name from . where name like '_.txt' order by name",cwd=tmp_path).stdout == 'a.txt\nb.txt\n'
    assert run("name from . where size between 0 and 0 order by name",cwd=tmp_path).stdout == 'a.txt\nb.txt\nc.bin\n'
    assert run("name from . where ext in {'txt','bin'} order by name",cwd=tmp_path).stdout == 'a.txt\nb.txt\nc.bin\n'


def test_parse_errors_exit_two_and_message(tmp_path):
    cases=[('select from','query: could not parse tokens at the end of the query\n'),
           ('name limit abc','query: could not parse tokens at the end of the query\n'),
           ('name into bogus','query: Unknown output format\n'),
           ('name limit 1,2 offset 1','query: Ambiguous offset specified\n')]
    for query, message in cases:
        p=run(query,cwd=tmp_path)
        assert p.returncode == 2 and p.stderr == message, query


def test_nonexistent_root_status_and_no_error(tmp_path):
    missing=tmp_path/'absent'
    p=run(f'name from {missing}',cwd=tmp_path)
    assert p.returncode == 1 and p.stdout == '' and 'could not canonicalize path' in p.stderr
    p=run(f'name from {missing}',cwd=tmp_path,opts=['--no-error'])
    assert p.returncode == 1 and p.stderr == ''


def test_invalid_root_regex_nonfatal(tmp_path):
    p=run(f"name from '{tmp_path}/[invalid' regexp",cwd=tmp_path)
    assert p.returncode == 0 and p.stdout == ''
    assert 'invalid regex in root path' in p.stderr


def test_zip_archive_members(tmp_path):
    z=tmp_path/'arc.zip'
    with zipfile.ZipFile(z,'w') as f:
        f.writestr('inside.txt','hello')
        f.writestr('folder/','')
    p=run('name,path from . archives order by path',cwd=tmp_path)
    assert p.returncode == 0 and 'inside.txt\tinside.txt\n' in p.stdout
    assert '[arc.zip]\tinside.txt\tinside.txt\n' in p.stdout


def test_config_file_extension_override_and_bad_file(tmp_path):
    data=tmp_path/'data'; data.mkdir()
    (data/'a.foo').touch(); (data/'b.png').touch()
    cfg=tmp_path/'config.toml'; cfg.write_text('is_image = [".foo"]\n')
    p=run(f'is_image from {data} order by name',cwd=tmp_path,opts=['--config',str(cfg)])
    assert p.stdout == 'true\nfalse\n'
    p=run('name from . limit 1',cwd=tmp_path,opts=['--config',str(tmp_path/'missing.toml')])
    assert p.returncode == 0 and p.stderr == 'Could not open config file. Using default settings.\n'


def test_dockerignore_and_gitignore_contract(tmp_path):
    (tmp_path/'.dockerignore').write_text('drop*\n')
    for n in ['drop.txt','keep.txt']: (tmp_path/n).touch()
    p=run('name from . order by name',cwd=tmp_path,opts=())
    # Ignore files are inactive unless the root option is specified.
    assert 'drop.txt' in p.stdout
    p=run('name from . dockerignore order by name',cwd=tmp_path)
    assert 'drop.txt' not in p.stdout and 'keep.txt' in p.stdout
    (tmp_path/'.gitignore').write_text('keep.txt\n')
    p=run('name from . gitignore order by name',cwd=tmp_path)
    assert 'keep.txt' in p.stdout


def test_interactive_repl_and_commands(tmp_path):
    p=run(cwd=tmp_path,opts=['--interactive'],input_text='pwd\nunknownword\nexit\n')
    assert p.returncode == 0 and str(tmp_path) in p.stdout and 'unknownword\n' in p.stdout
    assert p.stdout.count('query> ') >= 3
