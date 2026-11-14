import os
import subprocess
from pathlib import Path

import pytest

BIN = Path('/workspace/executable')


def run(*args, data=None, env=None, cwd=None):
    e = os.environ.copy()
    if env:
        e.update(env)
    return subprocess.run([str(BIN), *map(str, args)], input=data, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, env=e, cwd=cwd)


def ok(p, out):
    assert p.returncode == 0, p.stderr
    assert p.stdout == out


def test_version_and_help():
    ok(run('--version'), b'0.13.0\n')
    p = run('--help')
    assert p.returncode == 0 and b'Usage:' in p.stdout and b'Commands:' in p.stdout


def test_command_chooser_stderr():
    p = run()
    assert p.returncode == 0 and not p.stdout
    assert p.stderr.startswith(b'xsv is a suite of CSV command line utilities.')
    assert p.stderr.endswith(b'\n\n')


def test_unknown_command_and_case():
    p = run('Count')
    assert p.returncode == 1 and b'expects commands in lowercase' in p.stderr
    p = run('bogus')
    assert p.returncode == 1 and b'Could not match' in p.stderr


def test_count_headers_and_no_headers():
    ok(run('count', data=b'a,b\n1,2\n3,4\n'), b'2\n')
    ok(run('count', '-n', data=b'a,b\n1,2\n'), b'2\n')
    ok(run('count', data=b''), b'0\n')
    ok(run('count', data=b'a,b\n'), b'0\n')


def test_csv_record_parsing_and_canonical_select():
    data = b'a,b\n"x,y","line1\nline2"\nq,"a""b"\n'
    ok(run('select', '2,1', data=data), b'b,a\n"line1\nline2","x,y"\n"a""b",q\n')


def test_select_selector_language():
    data = b'a,b,c\n1,2,3\n'
    ok(run('select', '3-1,2', data=data), b'c,b,a,b\n3,2,1,2\n')
    ok(run('select', '!2', data=data), b'a,c\n1,3\n')
    ok(run('select', '!', data=data), b'""\n""\n')
    ok(run('select', '-', data=data), data)


def test_select_names_duplicates_and_empty_selection():
    ok(run('select', 'x[1],x[0]', data=b'x,y,x\nA,B,C\n'), b'x,x\nC,A\n')
    ok(run('select', '', data=b'a,b\n1,2\n'), b'a,b\n1,2\n')


def test_select_invalid_selector_is_fatal():
    p = run('select', '0', data=b'a,b\n1,2\n')
    assert p.returncode == 1 and b'out of bounds' in p.stderr
    p = run('select', 'missing', data=b'a,b\n1,2\n')
    assert p.returncode == 1 and b'does not exist' in p.stderr


def test_headers_numbering_names_and_multiple_files(tmp_path):
    a, b = tmp_path/'a.csv', tmp_path/'b.csv'
    a.write_bytes(b'a,b\n1,2\n'); b.write_bytes(b'b,c\n3,4\n')
    ok(run('headers', str(a)), b'1   a\n2   b\n')
    ok(run('headers', '-j', str(a), str(b)), b'a\nb\nb\nc\n')
    ok(run('headers', '--intersect', str(a), str(b)), b'a\nb\nc\n')


def test_slice_ranges_and_header():
    d=b'h\na\nb\nc\n'
    ok(run('slice', '--start', '1', '--end', '3', data=d), b'h\nb\nc\n')
    ok(run('slice', '--len', '0', data=d), b'h\n')
    ok(run('slice', '--index', '1', data=d), b'h\nb\n')
    ok(run('slice', '-n', '--len', '2', data=d), b'h\na\n')


def test_slice_conflicting_ranges():
    p=run('slice','--start','2','--end','1',data=b'h\na\n')
    assert p.returncode==1 and b'end of the range' in p.stderr
    p=run('slice','--len','1','--end','1',data=b'h\na\n')
    assert p.returncode==1 and p.stderr==b'--end and --len cannot be used at the same time.\n'
    p=run('slice','--index','0','--len','1',data=b'h\na\n')
    assert p.returncode==1 and b'--index cannot be used' in p.stderr


def test_search_matches_fields_and_preserves_full_rows():
    d=b'a,b\nAlice,1\nBob,ALICE\nCarol,2\n'
    ok(run('search','Alice','-s','1',data=d), b'a,b\nAlice,1\n')
    ok(run('search','alice','-i','-s','1',data=d), b'a,b\nAlice,1\nBob,ALICE\n')
    ok(run('search','Alice','-vi','-s','1',data=d), b'a,b\nCarol,2\n')


def test_search_empty_multiline_and_no_match():
    d=b'a,b\n"x\ny",\nq,z\n'
    ok(run('search','^$','-s','b',data=d), b'a,b\n"x\ny",\n')
    ok(run('search','nomatch',data=d), b'a,b\n')
    ok(run('search','x\\ny',data=d), b'a,b\n"x\ny",\n')


def test_search_bad_regex():
    p=run('search','(?P<invalid',data=b'a\nx\n')
    assert p.returncode==1 and b'regex parse error' in p.stderr


def test_sort_lexical_numeric_and_reverse():
    d=b'n\n10\n2\n-1\n'
    ok(run('sort',data=d), b'n\n-1\n10\n2\n')
    ok(run('sort','-N',data=d), b'n\n-1\n2\n10\n')
    ok(run('sort','-N','-R',data=d), b'n\n10\n2\n-1\n')


def test_sort_selection_blank_lines_and_quoted_empty():
    d=b'a,b\nz,2\n\na,1\n'
    ok(run('sort','-s','2',data=d), b'a,b\na,1\nz,2\n')
    ok(run('sort','-N',data=b'a\n2\n""\n1\n'), b'a\n""\n1\n2\n')


def test_reverse_order_and_header_modes():
    ok(run('reverse',data=b'h\na\nb\n'), b'h\nb\na\n')
    ok(run('reverse','-n',data=b'a\nb\n'), b'b\na\n')
    ok(run('reverse',data=b'h\n'), b'h\n')


def test_cat_rows_columns_and_pad(tmp_path):
    a,b=tmp_path/'a',tmp_path/'b'
    a.write_bytes(b'a,b\n1,2\n3,4\n'); b.write_bytes(b'c\nx\ny\n')
    ok(run('cat','rows',str(a),str(a)), b'a,b\n1,2\n3,4\n1,2\n3,4\n')
    ok(run('cat','columns',str(a),str(b)), b'a,b,c\n1,2,x\n')
    ok(run('cat','columns','--pad',str(a),str(b)), b'a,b,c\n1,2,x\n3,4,y\n')


def test_cat_one_stdin_and_empty_first(tmp_path):
    f=tmp_path/'f'; f.write_bytes(b'h\nx\n')
    ok(run('cat','rows','-',str(f),data=b''), b'h\nx\n')
    p=run('cat','rows','-','-',data=b'')
    assert p.returncode==1 and b'At most one <stdin> input' in p.stderr


def test_fixlengths_auto_and_explicit(tmp_path):
    f=tmp_path/'ragged.csv'; f.write_bytes(b'a,b,c\n1,,\n2,3\n')
    ok(run('fixlengths',str(f)), b'a,b,c\n1,,\n2,3,\n')
    ok(run('fixlengths','--length','2',str(f)), b'a,b\n1,\n2,3\n')
    p=run('fixlengths','--length','0',str(f))
    assert p.returncode==1 and b'Length must be greater than 0' in p.stderr


def test_fixlengths_stdin_requires_length():
    p=run('fixlengths',data=b'a\n1\n')
    assert p.returncode==1 and b'<stdin> cannot be used' in p.stderr


def test_flatten_separator_and_labels():
    ok(run('flatten',data=b'a,bb\nx,y\nz,w\n'), b'a   x\nbb  y\n#\na   z\nbb  w\n')
    ok(run('flatten','--separator','',data=b'a\nx\ny\n'), b'a   x\na   y\n')
    ok(run('flatten','-n',data=b'x,y\n'), b'0   x\n1   y\n')


def test_flatten_rejects_output_option():
    p=run('flatten','-o','nowhere',data=b'a\nx\n')
    assert p.returncode==1 and p.stderr.startswith(b"Unknown flag: '-o'")


def test_table_alignment_and_options():
    ok(run('table',data=b'a,b\nx,1\nyy,22\n'), b'a   b\nx   1\nyy  22\n')
    ok(run('table','--width','4','--pad','1',data=b'a,b\nx,1\n'), b'a     b\nx     1\n')


def test_fmt_output_delimiter_quotes_and_crlf():
    d=b'a,b\nh1,ghijkl\n'
    ok(run('fmt','-t','h',data=d), b'a,b\nh"h1"h"ghijkl"\n')
    ok(run('fmt','--quote-always','--crlf',data=b'a,b\nx,y\n'), b'"a","b"\r\n"x","y"\r\n')
    p=run('fmt','--ascii',data=b'a,b\nx,y\n')
    assert p.returncode==0 and p.stdout==b'a\x1fb\x1ex\x1fy\x1e'


def test_input_custom_quote_and_no_quoting():
    ok(run('input','--quote',"'",data=b"a,b\n'hello,world',x\n"), b'a,b\n"hello,world",x\n')
    ok(run('input','--no-quoting',data=b'a\n"x"\n'), b'a\n"""x""\n')


def test_frequency_counts_nulls_selection_and_limit():
    p=run('frequency',data=b'kind\na\nb\na\n\n')
    assert p.returncode==0
    assert p.stdout.startswith(b'field,value,count\nkind,a,2\n') and b'(NULL)' in p.stdout
    p=run('frequency','--no-nulls',data=b'kind\na\n\n')
    assert p.returncode==0 and b'(NULL)' not in p.stdout
    p=run('frequency','-n','-s','2','-l','1',data=b'x,a\ny,b\nz,b\n')
    assert p.returncode==0 and p.stdout.startswith(b'field,value,count\n1,b,2\n')


def test_frequency_selected_none():
    ok(run('frequency','-s','!',data=b'a\n1\n'), b'field,value,count\n')


def test_stats_schema_numeric_and_optional():
    p=run('stats','--everything',data=b'n\n1\n2\n3\n')
    assert p.returncode==0
    assert p.stdout.startswith(b'field,type,sum,min,max,min_length,max_length,mean,stddev,median,mode,cardinality\n')
    assert b'n,Integer,6,1,3,1,1,2,0.816496580927726,2,N/A,3\n' in p.stdout


def test_stats_nulls_lengths_and_headerless_labels():
    p=run('stats','--everything',data=b'n\n1\n\n3\n')
    assert p.returncode==0 and b'n,Integer,4,1,3,0,1,2,1' in p.stdout
    p=run('stats','-n','-s','2,1',data=b'a,10\nb,20\n')
    assert p.returncode==0 and b'0,Integer,30' in p.stdout and b'1,Unicode' in p.stdout


def test_stats_empty_input_and_all_empty():
    p=run('stats','--everything',data=b'h\n')
    assert p.returncode==0 and b'h,NULL,,,,,,,N/A,0\n' in p.stdout
    p=run('stats','--everything',data=b'h\n\n\n')
    assert p.returncode==0 and b'h,NULL,,,,0,0,,,1\n' in p.stdout


def test_sample_seed_vectors_and_full_population():
    d=b'id\n'+b''.join(f'{i}\n'.encode() for i in range(1,11))
    ok(run('sample','--seed','42','5',data=d), b'id\n8\n7\n3\n10\n5\n')
    ok(run('sample','--seed','123','3',data=d), b'id\n6\n5\n9\n')
    ok(run('sample','--seed','0','3',data=d), b'id\n1\n6\n5\n')
    ok(run('sample','99',data=d), d)


def test_join_inner_left_full_and_composite(tmp_path):
    l=b'id,v\n1,L1\n2,L2\n1,L3\n'; r=b'id,w\n1,R1\n3,R3\n'
    left=tmp_path/'left.csv'; right=tmp_path/'right.csv'
    left.write_bytes(l); right.write_bytes(r)
    p=run('join','id',left,'id',right)
    assert p.returncode==0 and p.stdout==b'id,v,id,w\n1,L1,1,R1\n1,L3,1,R1\n'


def test_join_outer_modes_and_trim_nulls(tmp_path):
    l=tmp_path/'l'; r=tmp_path/'r'; l.write_bytes(b'k,v\n a ,L\n,L0\n'); r.write_bytes(b'k,w\na,R\n,R0\n')
    p=run('join','--left','--nulls','k',str(l),'k',str(r))
    assert p.returncode==0 and b'a,L,a,R' in p.stdout and b',L0,,R0' in p.stdout
    p=run('join','--full','k',str(l),'k',str(r))
    assert p.returncode==0 and b',L0,,' in p.stdout
    p=run('join','--right','k',str(l),'k',str(r))
    assert p.returncode==0 and p.stdout.startswith(b'k,v,k,w\n')


def test_join_cross_and_validation(tmp_path):
    l=tmp_path/'l'; r=tmp_path/'r'; l.write_bytes(b'a\nx\ny\n'); r.write_bytes(b'b\n1\n2\n')
    p=run('join','--cross','1',str(l),'1',str(r))
    assert p.returncode==0 and p.stdout.count(b'\n')==5
    p=run('join','--left','--right','1',str(l),'1',str(r))
    assert p.returncode==1 and b'Please pick exactly one' in p.stderr


def test_index_binary_layout_and_indexed_count_slice(tmp_path):
    f=tmp_path/'data.csv'; f.write_bytes(b'h\na\nb\n')
    p=run('index',str(f)); assert p.returncode==0
    idx=Path(str(f)+'.idx').read_bytes()
    assert len(idx)==32 and int.from_bytes(idx[-8:],'big')==3
    ok(run('count',str(f)), b'2\n')
    ok(run('slice','--index','1',str(f)), b'h\nb\n')


def test_split_chunks_header_preserved(tmp_path):
    f=tmp_path/'in.csv'; f.write_bytes(b'h\n1\n2\n3\n4\n')
    out=tmp_path/'out'
    p=run('split','--size','2',str(out),str(f)); assert p.returncode==0
    assert sorted(x.name for x in out.iterdir())==['0.csv','2.csv']
    assert (out/'0.csv').read_bytes()==b'h\n1\n2\n'
    assert (out/'2.csv').read_bytes()==b'h\n3\n4\n'


def test_split_template_and_size_errors(tmp_path):
    f=tmp_path/'in'; f.write_bytes(b'h\nx\n'); out=tmp_path/'out'
    p=run('split','--filename','part-{}.csv',str(out),str(f)); assert p.returncode==0
    assert (out/'part-0.csv').exists()
    p=run('split','--size','0',str(tmp_path/'bad'),str(f))
    assert p.returncode==1 and p.stderr==b'--size must be greater than 0.\n'


def test_partition_sanitization_collision_and_drop(tmp_path):
    f=tmp_path/'in.csv'; f.write_bytes('key,v\na-b,1\nab,2\n雪山川,3\n'.encode())
    out=tmp_path/'parts'; p=run('partition','key',str(out),str(f)); assert p.returncode==0
    assert (out/'ab.csv').read_bytes()==b'key,v\na-b,1\n'
    assert (out/'ab_1.csv').read_bytes()==b'key,v\nab,2\n'
    assert (out/'empty.csv').read_bytes()=='key,v\n雪山川,3\n'.encode()
    out2=tmp_path/'drop'; p=run('partition','--drop','key',str(out2),str(f)); assert p.returncode==0
    assert (out2/'ab.csv').read_bytes()==b'v\n1\n'


def test_partition_custom_template_and_headerless(tmp_path):
    f=tmp_path/'in'; f.write_bytes(b'a,one\nb,two\n')
    out=tmp_path/'p'; p=run('partition','-n','1','--filename','{}/data.csv',str(out),str(f))
    assert p.returncode==0 and (out/'a'/'data.csv').read_bytes()==b'a,one\n'


def test_output_redirection_and_stdin_delimiter(tmp_path):
    dest=tmp_path/'out.csv'
    p=run('select','1','--output='+str(dest),data=b'a,b\n1,2\n')
    assert p.returncode==0 and p.stdout==b'' and dest.read_bytes()==b'a\n1\n'
    ok(run('select','1','-d','\\t',data=b'a\tb\n1\t2\n'), b'a\n1\n')


def test_toggle_headers_exact_value():
    ok(run('count',data=b'a\n1\n',env={'XSV_TOGGLE_HEADERS':'1'}), b'2\n')
    ok(run('count','-n',data=b'a\n1\n',env={'XSV_TOGGLE_HEADERS':'1'}), b'1\n')
    ok(run('count',data=b'a\n1\n',env={'XSV_TOGGLE_HEADERS':'true'}), b'1\n')


def test_delimiter_validation_and_option_errors():
    p=run('count','-d','xx',data=b'a\n')
    assert p.returncode==1 and b'single ASCII character' in p.stderr
    p=run('count','--delimiter',data=b'a\n')
    assert p.returncode==1 and b'Expected argument for flag' in p.stderr
    p=run('select','--invalid-flag','1',data=b'a\n')
    assert p.returncode==1 and p.stderr.startswith(b"Unknown flag: '--invalid-flag'")


def test_missing_file_and_directory_errors(tmp_path):
    p=run('count',str(tmp_path/'missing'))
    assert p.returncode==1 and b'failed to open' in p.stderr and b'os error 2' in p.stderr
    p=run('count',str(tmp_path))
    assert p.returncode==1 and p.stderr==b'Is a directory (os error 21)\n'


def test_malformed_csv_and_ragged_error():
    p=run('count',data=b'a,b\n1\n')
    assert p.returncode==1 and b'CSV error' in p.stderr


def test_write_failure_dev_full():
    p=run('select','1','-o','/dev/full',data=b'a\nx\n')
    assert p.returncode==1 and p.stderr==b'No space left on device (os error 28)\n'


def test_u64_validation():
    p=run('slice','--len','-1',data=b'a\nx\n')
    assert p.returncode==1 and b"Could not deserialize '-1' to u64 for '--len'" in p.stderr
