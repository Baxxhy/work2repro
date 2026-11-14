import json
import os
import pathlib
import subprocess
import tempfile

EXE = pathlib.Path('/workspace/executable')


def run(*args, data=None, cwd=None):
    return subprocess.run([str(EXE), *map(str, args)], input=data, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          cwd=cwd, timeout=5)


def json_scan(*args):
    p = run('--json-output', *args)
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout), p


def payload(tree, unit='bytes'):
    return json.dumps({'schema-version':'2024-11-02','pdu':'0.21.1','unit':unit,'tree':tree}, separators=(',', ':'))


def test_version_and_help_contract():
    p = run('--version')
    assert (p.returncode, p.stdout, p.stderr) == (0, 'pdu 0.21.1\n', '')
    p = run('-V')
    assert (p.returncode, p.stdout, p.stderr) == (0, 'pdu 0.21.1\n', '')
    p = run('--help')
    assert p.returncode == 0 and p.stderr == ''
    assert p.stdout.startswith('Summarize disk usage of the set of files, recursively for directories.\n')
    assert 'Usage: executable [OPTIONS] [FILES]...' in p.stdout and 'Examples:' in p.stdout
    p = run('-h')
    assert p.returncode == 0 and p.stderr == ''
    assert all(s in p.stdout for s in ('Usage: executable [OPTIONS] [FILES]...', 'Options:', 'Examples:', '--help'))


def test_parse_errors_and_value_validation():
    p = run('--bytes-format=invalid')
    assert p.returncode == 2 and p.stdout == ''
    assert p.stderr.strip() == "error: invalid value 'invalid' for '--bytes-format <BYTES_FORMAT>'\n  [possible values: plain, metric, binary]\n\nFor more information, try '--help'."
    p = run('--quantity=invalid')
    assert p.returncode == 2 and "[possible values: apparent-size, block-size, block-count]" in p.stderr
    for opt, val in [('--max-depth', '0'), ('--max-depth', '-1'), ('--threads', '0'), ('--threads', '-5'), ('--min-ratio', '-0.5'), ('--min-ratio', '1.0'), ('--min-ratio', 'abc')]:
        p = run(f'{opt}={val}')
        assert p.returncode == 2 and p.stdout == '' and 'invalid value' in p.stderr
    p = run('--max-depth', '-1')
    assert p.returncode == 2 and "unexpected argument '-1' found" in p.stderr and 'to pass' in p.stderr
    p = run('--definitely-invalid', '--help')
    assert p.returncode == 2 and p.stdout == '' and "unexpected argument '--definitely-invalid' found" in p.stderr


def test_repeated_flags_and_width_conflict():
    for args, option in [(('-p','-p'), '--progress'), (('-s','-s'), '--silent-errors')]:
        p = run('--json-output', *args, '--max-depth=1', '.')
        assert p.returncode == 2 and f"the argument '{option}' cannot be used multiple times" in p.stderr
    p = run('--total-width=100', '--column-width', '30', '50')
    assert p.returncode == 2 and "cannot be used with '--column-width" in p.stderr
    p = run('--column-width', '20')
    assert p.returncode == 2 and '2 values required' in p.stderr


def test_option_terminator_and_paths_named_like_commands():
    with tempfile.TemporaryDirectory() as td:
        root = pathlib.Path(td)
        (root/'add').write_bytes(b'abc')
        (root/'--no-such-flag').write_bytes(b'12345')
        d, _ = json_scan('--', root/'--no-such-flag')
        assert d['tree']['name'] == str(root/'--no-such-flag') and d['tree']['size'] == 5
        d, _ = json_scan(root/'add')
        assert d['tree']['name'] == str(root/'add')


def test_single_file_and_missing_path_results():
    with tempfile.TemporaryDirectory() as td:
        f = pathlib.Path(td)/'a file.txt'; f.write_bytes(b'hello')
        d, _ = json_scan('--quantity=apparent-size', f)
        assert d['tree'] == {'name': str(f), 'size': 5, 'children': []}
        missing = pathlib.Path(td)/'gone'
        p = run('--json-output', missing)
        assert p.returncode == 0 and json.loads(p.stdout)['tree'] == {'name':str(missing),'size':0,'children':[]}
        assert '[error] symlink_metadata' in p.stderr
        p = run('--json-output', '--silent-errors', missing)
        assert p.returncode == 0 and p.stderr == '' and json.loads(p.stdout)['tree']['size'] == 0
        chart = run(missing)
        assert chart.returncode == 0 and f'0    ┌──{missing}' in chart.stdout


def test_recursive_totals_depth_ratio_and_sorting():
    with tempfile.TemporaryDirectory() as td:
        root = pathlib.Path(td)/'root'; (root/'sub').mkdir(parents=True)
        (root/'small').write_bytes(b'x')
        (root/'sub'/'big').write_bytes(b'abcdefghij')
        d, _ = json_scan('--quantity=apparent-size', '--min-ratio=0', root)
        t = d['tree']; assert t['name'] == str(root) and t['size'] >= 11
        assert [x['name'] for x in t['children']] == ['sub', 'small']
        d, _ = json_scan('--quantity=apparent-size', '--max-depth=1', '--min-ratio=0', root)
        assert d['tree']['size'] == t['size'] and d['tree']['children'] == []
        d, _ = json_scan('--quantity=apparent-size', '--max-depth=2', '--min-ratio=0', root)
        assert d['tree']['children'] and all(not n['children'] for n in d['tree']['children'])
        d, _ = json_scan('--quantity=apparent-size', '--no-sort', '--min-ratio=0', root)
        assert [x['name'] for x in d['tree']['children']] == ['small', 'sub']


def test_synthetic_roots_order_and_duplicate_policy():
    with tempfile.TemporaryDirectory() as td:
        a=pathlib.Path(td)/'a'; b=pathlib.Path(td)/'b'; a.write_bytes(b'a'); b.write_bytes(b'bbbb')
        d,_=json_scan('--quantity=apparent-size', a,b)
        assert d['tree']['name']=='(total)' and [x['name'] for x in d['tree']['children']]==[str(b),str(a)]
        d,_=json_scan('--quantity=apparent-size','--no-sort',b,a)
        assert [x['name'] for x in d['tree']['children']]==[str(b),str(a)]
        d,_=json_scan('--quantity=apparent-size',a,a)
        assert len(d['tree']['children'])==2
        d,_=json_scan('--quantity=apparent-size','--deduplicate-hardlinks',a,a)
        assert d['tree']['name']==str(a)


def test_quantity_and_json_units():
    with tempfile.TemporaryDirectory() as td:
        root=pathlib.Path(td); f=root/'allocated'; f.write_bytes(b'z'*8192)
        app,_=json_scan('--quantity=apparent-size',f)
        blocks,_=json_scan('--quantity=block-count',f)
        size,_=json_scan('--quantity=block-size',f)
        assert app['unit']=='bytes' and app['tree']['size']==8192
        assert blocks['unit']=='blocks' and blocks['tree']['size']>=16
        assert size['unit']=='bytes' and size['tree']['size']>=8192
        assert run('--quantity=apparent-size','-bplain',f).returncode==0


def test_symlinks_are_leaves_and_names_round_trip():
    with tempfile.TemporaryDirectory() as td:
        root=pathlib.Path(td); target=root/'target'; target.mkdir(); (target/'payload').write_bytes(b'x'*40)
        link=root/'link'; link.symlink_to(target, target_is_directory=True)
        broken=root/'broken'; broken.symlink_to(root/'missing')
        weird=root/"雪 'quote' -- space"; weird.write_bytes(b'abc')
        d,_=json_scan('--quantity=apparent-size','--min-ratio=0',root)
        kids={x['name']:x for x in d['tree']['children']}
        assert kids['link']['children']==[] and kids['broken']['children']==[]
        assert kids[weird.name]['name']==weird.name
        assert kids['link']['size']==len(str(target))
        d,_=json_scan('--quantity=apparent-size',link)
        assert d['tree']['children']==[]


def test_chart_format_depth_direction_and_bars():
    tree={'name':'root','size':100,'children':[{'name':'big','size':70,'children':[{'name':'leaf','size':40,'children':[]}]},{'name':'tiny','size':5,'children':[]}]}
    p=run('--json-input',data=payload(tree))
    assert p.returncode==0 and p.stdout.endswith('\n') and '│' in p.stdout and '█' in p.stdout
    lines=p.stdout.splitlines(); assert lines[-1].rstrip().endswith('root')
    q=run('--json-input','--top-down',data=payload(tree))
    assert q.stdout.splitlines()[0].rstrip().endswith('root')
    assert q.stdout != p.stdout
    assert '▒' in p.stdout or '░' in p.stdout
    r=run('--json-input','--align-right',data=payload(tree))
    assert r.stdout!=p.stdout


def test_chart_width_and_size_formats():
    tree={'name':'root','size':104857600,'children':[{'name':'large.bin','size':104857600,'children':[]}]}
    data=payload(tree)
    p=run('--json-input','--bytes-format=binary',data=data)
    assert p.returncode==0 and p.stdout.count('100.0M')==2
    q=run('--json-input','--bytes-format=metric',data=data)
    assert '104.9M' in q.stdout
    r=run('--json-input','--bytes-format=plain','--total-width=80',data=data)
    assert all(len(line)==80 for line in r.stdout.splitlines())
    s=run('--json-input','--column-width','30','17',data=payload({'name':'root','size':10,'children':[{'name':'x','size':5,'children':[]}]}))
    assert s.returncode==0 and '┌──x' in s.stdout


def test_json_input_ignores_scan_filters_but_validates_schema():
    tree={'name':'test','size':1000,'children':[{'name':'small','size':9,'children':[]}]}
    data=payload(tree)
    for opts in [(),('--max-depth=1',),('--max-depth=2','--min-ratio=0.01')]:
        p=run('--json-input',*opts,data=data)
        assert p.returncode==0 and 'small' in p.stdout
    p=run('--json-input','--json-output',data=data)
    assert p.returncode==0 and '"tree"' not in p.stdout and 'test' in p.stdout
    p=run('--json-input','--quantity=apparent-size',data=data)
    assert p.returncode==2 and 'cannot be used with' in p.stderr
    p=run('--json-input','file',data=data)
    assert p.returncode==4 and 'Arguments exist alongside --json-input' in p.stderr
    for raw, msg in [(b'', 'expected value'),(b'{}','missing field `schema-version`')]:
        p=run('--json-input',data=raw.decode())
        assert p.returncode==3 and p.stdout=='' and '[error] DeserializationFailure:' in p.stderr and msg in p.stderr


def test_json_input_recursive_size_validation():
    bad={'name':'test','size':100,'children':[{'name':'child1','size':200,'children':[]}]}
    p=run('--json-input',data=payload(bad))
    assert p.returncode==5 and p.stdout=='' and 'ExcessiveChildren' in p.stderr and '"test" (Bytes(100))' in p.stderr
    bad={'name':'root','size':1000,'children':[{'name':'parent','size':500,'children':[{'name':'child','size':600,'children':[]}]}]}
    p=run('--json-input',data=payload(bad,'blocks'))
    assert p.returncode==5 and '"root/parent" (Blocks(500))' in p.stderr


def test_hardlink_json_details_summary_and_omission():
    with tempfile.TemporaryDirectory() as td:
        root=pathlib.Path(td); a=root/'a'; a.write_bytes(b'123456789012345678'); b=root/'b'; os.link(a,b); c=root/'c'; os.link(a,c)
        d,_=json_scan('--quantity=apparent-size','--deduplicate-hardlinks',root)
        assert 'shared' in d
        detail=d['shared']['details'][0]
        assert detail['size']==18 and detail['links']==3 and set(detail['paths'])=={str(a),str(b),str(c)}
        assert d['shared']['summary']=={'inodes':1,'exclusive_inodes':1,'all_links':3,'detected_links':3,'exclusive_links':3,'shared_size':18,'exclusive_shared_size':18}
        d,_=json_scan('--quantity=apparent-size','--dedupe-links','--omit-json-shared-details',root)
        assert 'details' not in d['shared'] and 'summary' in d['shared']
        d,_=json_scan('--quantity=apparent-size','-H','--omit-json-shared-summary',root)
        assert 'summary' not in d['shared'] and 'details' in d['shared']
        d,_=json_scan('--quantity=apparent-size','-H','--omit-json-shared-details','--omit-json-shared-summary',root)
        assert 'shared' not in d


def test_hardlink_dedup_and_footer():
    with tempfile.TemporaryDirectory() as td:
        root=pathlib.Path(td); a=root/'a'; a.write_bytes(b'x'*18); os.link(a,root/'b'); os.link(a,root/'c')
        plain,_=json_scan('--quantity=apparent-size',root)
        dedup,_=json_scan('--quantity=apparent-size','-H',root)
        assert plain['tree']['size']-dedup['tree']['size']==36
        p=run('--quantity=apparent-size','--bytes-format=plain','--deduplicate-hardlinks',root)
        assert 'Hardlinks detected!' in p.stdout and 'Number of shared inodes:' in p.stdout and 'Total number of links:' in p.stdout and 'Total shared size: 18' in p.stdout
        q=run('--quantity=apparent-size',root)
        assert 'Hardlinks detected!' not in q.stdout


def test_progress_and_thread_choices_preserve_json():
    with tempfile.TemporaryDirectory() as td:
        root=pathlib.Path(td); (root/'a').write_bytes(b'a'*13); (root/'b').write_bytes(b'b'*29)
        baseline,_=json_scan('--quantity=apparent-size',root)
        for threads in ('auto','max','1','2','4','64'):
            p=run('--json-output','--progress',f'--threads={threads}','--quantity=apparent-size',root)
            assert p.returncode==0 and json.loads(p.stdout)==baseline


def test_json_output_is_compact_ordered_and_has_no_newline():
    with tempfile.TemporaryDirectory() as td:
        root=pathlib.Path(td); f=root/'é " x'; f.write_bytes(b'abc')
        p=run('--json-output','--quantity=apparent-size',f)
        assert p.returncode==0 and p.stdout.endswith('}') and not p.stdout.endswith('\n')
        d=json.loads(p.stdout)
        assert list(d)==['schema-version','pdu','unit','tree']
        assert list(d['tree'])==['name','size','children'] and d['tree']['name']==str(f)


def test_unicode_deep_and_wide_tree_support():
    with tempfile.TemporaryDirectory() as td:
        root=pathlib.Path(td)
        for i in range(155):
            (root/f'file {i:03d} “雪”.dat').write_bytes(bytes([i % 256]))
        d,_=json_scan('--quantity=apparent-size','--min-ratio=0',root)
        assert len(d['tree']['children'])==155
        names={n['name'] for n in d['tree']['children']}
        assert 'file 000 “雪”.dat' in names
        # Deep scans must complete without relying on recursive display depth.
        chain=root/'deep'
        chain.mkdir()
        cur=chain
        for i in range(28):
            cur=cur/f'n{i}'; cur.mkdir()
        (cur/'end').write_bytes(b'z')
        d,_=json_scan('--quantity=apparent-size','--max-depth=inf',chain)
        node=d['tree']; levels=0
        while node['children']:
            node=node['children'][0]; levels += 1
        assert levels >= 29


def test_zero_size_ratio_and_alias_options():
    with tempfile.TemporaryDirectory() as td:
        root=pathlib.Path(td); (root/'empty').write_bytes(b'')
        p=run('--json-output','--quantity=apparent-size','--min-ratio=0',root)
        assert p.returncode==0
        d=json.loads(p.stdout)
        assert d['tree']['size']==0 and len(d['tree']['children'])==1
        for args in [('--depth=1',),('-d','1',)]:
            p=run('--json-output','--quantity=apparent-size',*args,root)
            assert p.returncode==0 and json.loads(p.stdout)['tree']['children']==[]
        p=run('--json-output','--quantity=apparent-size','--width=80',root)
        assert p.returncode==0
        p=run('--json-output','--quantity=apparent-size','--no-errors',root/'absent')
        assert p.returncode==0 and p.stderr==''


def test_ratio_filtering_and_missing_synthetic_root():
    with tempfile.TemporaryDirectory() as td:
        root=pathlib.Path(td); valid=root/'valid'; valid.write_bytes(b'x'*100); missing=root/'missing'
        p=run('--json-output','--quantity=apparent-size',missing,valid)
        d=json.loads(p.stdout)
        assert d['tree']['name']=='(total)' and [n['name'] for n in d['tree']['children']]==[str(valid)]
        assert '[error]' in p.stderr
        p=run('--json-output','--quantity=apparent-size','--min-ratio=0',missing,valid)
        assert len(json.loads(p.stdout)['tree']['children'])==2
        p=run('--json-output','--quantity=apparent-size','--min-ratio=NaN',valid)
        assert p.returncode==0 and json.loads(p.stdout)['tree']['size']>0


def test_hardlink_outside_selection_and_overlap_normalization():
    with tempfile.TemporaryDirectory() as td:
        root=pathlib.Path(td); sub=root/'sub'; sub.mkdir(); f=sub/'f'; f.write_bytes(b'payload'); outside=root/'outside'; os.link(f,outside)
        d,_=json_scan('--quantity=apparent-size','--deduplicate-hardlinks',sub)
        assert d['shared']['summary']['detected_links']==1
        assert d['shared']['summary']['all_links']==2 and d['shared']['summary']['exclusive_inodes']==0
        d,_=json_scan('--quantity=apparent-size','--deduplicate-hardlinks',root,sub)
        assert d['tree']['name']==str(root)
        assert d['tree']['children']


def test_link_counts_not_directory_structural_links_and_footer_cases():
    with tempfile.TemporaryDirectory() as td:
        root=pathlib.Path(td); a=root/'a'; a.write_bytes(b'one'); os.link(a,root/'b')
        d,_=json_scan('--quantity=apparent-size','-H',root)
        assert d['shared']['summary']['inodes']==1
        assert d['shared']['summary']['all_links']==2
        p=run('--quantity=apparent-size','-H',root)
        assert 'No files have links outside this tree' in p.stdout
        # A selected path observes one of two links, yielding a partial group.
        partial,_=json_scan('--quantity=apparent-size','-H',a)
        assert partial['shared']['summary']['detected_links']==1
        assert partial['shared']['summary']['exclusive_inodes']==0
        out=run('--quantity=apparent-size','-H',a)
        assert 'All hardlinks within this tree have links without' in out.stdout
