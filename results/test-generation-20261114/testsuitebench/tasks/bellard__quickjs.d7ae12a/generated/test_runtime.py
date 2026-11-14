import os
import subprocess
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
EXE = Path('/workspace/executable')


def run(*args, cwd=None, input_text=None):
    return subprocess.run([str(EXE), *map(str, args)], cwd=cwd or EVAL_DIR,
                          input=input_text, text=True, capture_output=True, timeout=20)


def ev(src, *opts):
    return run(*opts, '-e', src)


def test_help_exact_text_and_status():
    p = run('--help')
    assert p.returncode == 1 and p.stderr == ''
    assert p.stdout.startswith('QuickJS version 2025-09-13\nusage: qjs ')
    assert p.stdout.endswith('    --strip-source    strip the source code\n-q  --quit         just instantiate the interpreter and quit\n')


def test_eval_multiline_and_alias():
    p = run('--eval', 'let a=20;\nprint(a*2)')
    assert (p.returncode, p.stdout, p.stderr) == (0, '40\n', '')


def test_empty_and_file_arguments(tmp_path):
    f = tmp_path / 'arg.js'
    f.write_text('print(scriptArgs.length, scriptArgs[0], scriptArgs[1], scriptArgs[2])', encoding='utf-8')
    p = run(str(f), 'alpha', '--', '-x', cwd=tmp_path)
    assert p.returncode == 0 and p.stdout == f'{4} {f} alpha --\n'
    empty = tmp_path / 'empty.mjs'
    empty.write_text('', encoding='utf-8')
    p = run(str(empty), cwd=tmp_path)
    assert (p.returncode, p.stdout, p.stderr) == (0, '', '')


def test_missing_source_fails():
    p = run('absent-file.js')
    assert p.returncode != 0 and p.stderr


def test_missing_option_values():
    p = run('-e')
    assert p.returncode == 2 and p.stderr == 'qjs: missing expression for -e\n'
    p = run('-I')
    assert p.returncode == 1 and p.stderr == 'expecting filename'
    p = run('--memory-limit')
    assert p.returncode == 1 and p.stderr == 'expecting memory limit'
    p = run('--stack-size')
    assert p.returncode == 1 and p.stderr == 'expecting stack size'


def test_unknown_option_reports_help():
    p = run('--definitely-unknown')
    assert p.returncode == 1 and "qjs: unknown option '--definitely-unknown'" in p.stderr
    assert p.stdout.startswith('QuickJS version 2025-09-13')


def test_quit_skips_inline_evaluation():
    p = run('-q', '-e', 'throw new Error("should not run")')
    assert (p.returncode, p.stdout, p.stderr) == (0, '', '')


def test_dump_report_and_bundled_flags():
    p = run('-qd')
    assert p.returncode == 0 and p.stderr == ''
    for field in ('QuickJS memory usage', 'JSRuntime', 'JSContext', 'memory allocated', 'atoms', 'objects'):
        assert field in p.stdout
    assert 'Instantiation times (ms):' in p.stdout


def test_dump_trace_composition():
    p = run('-dTq')
    assert p.returncode == 0 and 'QuickJS memory usage' in p.stdout
    assert any(line.startswith('A ') and ' -> H' in line for line in p.stdout.splitlines())


def test_memory_suffix_validation():
    for suffix in ('m', 'X'):
        p = run('--memory-limit', '1' + suffix, '-q')
        assert p.returncode == 1 and f'qjs: invalid suffix: {suffix}' in p.stderr
    p = run('--memory-limit', '1.5M', '-e', 'print(3)')
    assert (p.returncode, p.stdout, p.stderr) == (0, '3\n', '')


def test_small_memory_limit_context_failure():
    p = run('--memory-limit', '10K', '-q')
    assert p.returncode == 2 and p.stdout == '' and p.stderr == 'qjs: cannot allocate JS context'


def test_includes_share_globals_and_preserve_order(tmp_path):
    a, b = tmp_path/'a.js', tmp_path/'b.js'
    a.write_text('var shared=5; print("a")', encoding='utf-8')
    b.write_text('shared += 2; print("b")', encoding='utf-8')
    p = run('-I', a, '--include', b, '-e', 'print(shared)', cwd=tmp_path)
    assert (p.returncode, p.stdout, p.stderr) == (0, 'a\nb\n7\n', '')


def test_sloppy_and_strict_semantics():
    p = ev('madeGlobal=4; print(madeGlobal)')
    assert (p.returncode, p.stdout) == (0, '4\n')
    p = run('--strict', '-e', 'madeGlobal=4')
    assert p.returncode == 1 and 'ReferenceError' in p.stderr


def test_module_autodetection_and_script_forcing(tmp_path):
    f = tmp_path/'m.js'
    f.write_text('export const x=3; print(x)', encoding='utf-8')
    p = run(str(f), cwd=tmp_path)
    assert (p.returncode, p.stdout, p.stderr) == (0, '3\n', '')
    p = run('--script', str(f), cwd=tmp_path)
    assert p.returncode == 1 and 'SyntaxError' in p.stderr


def test_lexical_numeric_unicode_regex_and_template():
    p = ev('let π=0x10+0b10+0o7+1_000; print(π, `x${π}`, /a+/.test("aaa"), "😀".length)')
    assert (p.returncode, p.stdout, p.stderr) == (0, '1025 x1025 true 2\n', '')


def test_lexical_syntax_error_has_location():
    p = ev('let x = "unterminated')
    assert p.returncode == 1 and 'SyntaxError' in p.stderr and '<cmdline>' in p.stderr


def test_scopes_eval_and_closures():
    p = ev('function make(){let x=2; return ()=>++x} let f=make(); print(f(),f(), eval("1+2"))')
    assert (p.returncode, p.stdout, p.stderr) == (0, '3 4 3\n', '')


def test_value_conversion_and_short_circuit():
    p = ev('let n=0; let x=null; print(typeof 1n, Object.is(-0,0), NaN===NaN, (x ?? (n++,7)), n, (0 || (n++,8)), n)')
    assert (p.returncode, p.stdout, p.stderr) == (0, 'bigint false false 7 1 8 2\n', '')


def test_symbol_property_and_explicit_conversion():
    p = ev('let s=Symbol("k"), o={[s]:3}; print(o[s], String(s), Object.keys(o).length, Object.getOwnPropertySymbols(o).length)')
    assert (p.returncode, p.stdout, p.stderr) == (0, '3 Symbol(k) 0 1\n', '')


def test_operators_and_bigint():
    p = ev('print(2**3**2, -1>>>0, (1<<33), 12345678901234567890n+10n)')
    assert (p.returncode, p.stdout, p.stderr) == (0, '512 4294967295 2 12345678901234567900\n', '')


def test_destructuring_defaults_spread_and_iterator_cleanup():
    p = ev('let [a=7,...b]=[undefined,2,3]; let o={x:1,...{y:2}}; print(a,b.join(","),o.x,o.y)')
    assert (p.returncode, p.stdout, p.stderr) == (0, '7 2,3 1 2\n', '')
    src = 'let c=0,it={[Symbol.iterator](){return {next(){return {done:false,get value(){throw 9}}},return(){c++;return {}}}}}; try{let [x]=it}catch(e){print(e,c)}'
    p = ev(src)
    assert (p.returncode, p.stdout, p.stderr) == (0, '9 0\n', '')


def test_functions_arguments_bind_and_classes():
    p = ev('function f(a){arguments[0]=8;return a}; let B=function(x){this.x=x}.bind(null,4); class A{m(){return 2}} print(f(1),new B().x,new A().m())')
    assert (p.returncode, p.stdout, p.stderr) == (0, '8 4 2\n', '')


def test_control_flow_finally_and_arbitrary_throw():
    p = ev('let s=""; try{throw null}catch(e){s+=String(e)}finally{s+="!"}; for(let i=0;i<5;i++){if(i===2)continue;s+=i}; print(s)')
    assert (p.returncode, p.stdout, p.stderr) == (0, 'null!0134\n', '')


def test_object_descriptors_prototypes_and_freeze():
    p = ev('let p={x:2},o=Object.create(p); Object.defineProperty(o,"y",{value:3,enumerable:true}); Object.freeze(o); print(o.x,Object.keys(o).join(","),Object.isFrozen(o),Reflect.set(o,"z",4))')
    assert (p.returncode, p.stdout, p.stderr) == (0, '2 y true false\n', '')


def test_array_holes_methods_and_length():
    p = ev('let a=[1,,3]; a[4]=5; print(a.length,0 in a,1 in a,a.map(x=>x*2).join(","),a.includes(undefined))')
    assert (p.returncode, p.stdout, p.stderr) == (0, '5 true false 2,,6,,10 true\n', '')
    p = ev('let a=[1,,3]; print(a)')
    assert p.stdout == '[ 0: 1, 2: 3 ]\n'


def test_string_unicode_and_normalization():
    p = ev('let s="😀e\\u0301"; print(s.length,[...s].length,s.normalize("NFC").length,"  x  ".trim())')
    assert (p.returncode, p.stdout, p.stderr) == (0, '4 3 3 x\n', '')


def test_regex_captures_and_replacement():
    p = ev('let m=/(?<a>x)(y)/.exec("xy"); print(m[0],m.groups.a,"abc".replace(/b/,"[$&]"),RegExp.escape("abc"))')
    assert (p.returncode, p.stdout, p.stderr) == (0, 'xy x a[b]c \\x61bc\n', '')


def test_number_math_and_formatting():
    p = ev('print(Number.isNaN(NaN), isNaN("x"), (1/(-0)), Math.imul(0xffffffff,5), (0.1+0.2).toFixed(1))')
    assert (p.returncode, p.stdout, p.stderr) == (0, 'true true -Infinity -5 0.3\n', '')


def test_iterators_generators_and_promise_jobs():
    p = ev('function* g(){yield 1;return 2}; let i=g(); print(i.next().value,i.next().value,i.next().done); Promise.resolve(4).then(x=>print(x)); print("sync")')
    assert (p.returncode, p.stdout, p.stderr) == (0, '1 2 true\nsync\n4\n', '')


def test_json_parse_stringify_and_reviver():
    p = ev('let o=JSON.parse("{\\"a\\":1,\\"b\\":[true,null]}",(k,v)=>k==="a"?v+1:v); print(JSON.stringify(o),JSON.stringify([undefined,NaN]))')
    assert (p.returncode, p.stdout, p.stderr) == (0, '{"a":2,"b":[true,null]} [null,null]\n', '')


def test_date_and_error_hierarchy():
    p = ev('let d=new Date("2020-01-02T00:00:00Z"); print(d.toISOString(),new TypeError("x") instanceof Error, new Date(NaN).toString())')
    assert (p.returncode, p.stdout, p.stderr) == (0, '2020-01-02T00:00:00.000Z true Invalid Date\n', '')


def test_std_presence_and_order():
    p = ev('print(typeof std,typeof os)', '--std')
    assert (p.returncode, p.stdout, p.stderr) == (0, 'object object\n', '')
    p = ev('print("readFile" in std, typeof std.readFile, Object.keys(std).slice(0,4).join(","),Object.keys(os).slice(0,3).join(","))', '--std')
    assert (p.returncode, p.stdout, p.stderr) == (0, 'false undefined Error,SEEK_CUR,SEEK_END,SEEK_SET O_APPEND,O_CREAT,O_EXCL\n', '')


def test_sprintf_and_environment():
    p = ev('print(std.sprintf("%04d %.1f %s",7,2.25,"ok"),std.getenv("EVAL_SUITE_MISSING")===undefined)', '--std')
    assert (p.returncode, p.stdout, p.stderr) == (0, '0007 2.2 ok true\n', '')


def test_std_file_io_roundtrip(tmp_path):
    f = tmp_path/'data.txt'
    code = 'let f=std.open('+repr(str(f))+',"w+"); f.puts("hello"); f.seek(0, std.SEEK_SET); print(f.getline()); print(f.close())'
    p = run('--std', '-e', code, cwd=tmp_path)
    assert (p.returncode, p.stdout, p.stderr) == (0, 'hello\n0\n', '')
    assert f.read_text() == 'hello\n'


def test_os_filesystem_api(tmp_path):
    code = 'let p="f.txt", fd=os.open(p,os.O_WRONLY|os.O_CREAT,0o600); let b=new Uint8Array([65,66]); print(fd>=0,os.write(fd,b.buffer,0,2)); print(os.close(fd)); print(os.stat(p)[0].size); print(os.remove(p))'
    p = run('--std', '-e', code, cwd=tmp_path)
    assert p.returncode == 0 and p.stderr == ''
    assert p.stdout.splitlines() == ['true 2', '0', '2', '0']


def test_std_file_url_is_not_loaded():
    p = ev('print(std.urlGet("file:///etc/passwd"))', '--std')
    assert (p.returncode, p.stdout, p.stderr) == (0, 'null\n', '')


def test_unhandled_rejection_switch():
    p = run('-e', 'Promise.reject("test error")')
    assert p.returncode == 1 and 'Possibly unhandled promise rejection: "test error"' in p.stderr
    p = run('--no-unhandled-rejection', '-e', 'Promise.reject("test error")')
    assert p.returncode == 0 and p.stderr == ''


def test_module_relative_import_once(tmp_path):
    lib=tmp_path/'lib.js'; main=tmp_path/'main.js'
    lib.write_text('globalThis.counter=(globalThis.counter||0)+1; export let n=counter;', encoding='utf-8')
    main.write_text('import {n} from "./lib.js"; import {n as m} from "./lib.js"; print(n,m,globalThis.counter)', encoding='utf-8')
    p=run(str(main),cwd=tmp_path)
    assert (p.returncode,p.stdout,p.stderr)==(0,'1 1 1\n','')


def test_interactive_decl_continuation_regression():
    p = run('-i', input_text='let x=40\nx+2\n\\q\n')
    assert p.returncode == 0 and p.stderr == ''
    assert p.stdout.count('qjs > ') == 2
    assert 'SyntaxError: invalid number literal' in p.stdout and '42' not in p.stdout


def test_stress_large_arrays_and_bigints():
    p = ev('let a=Array.from({length:100000},(_,i)=>i); print(a.length,a[99999],(1n<<200n).toString(16).length)')
    assert (p.returncode, p.stdout, p.stderr) == (0, '100000 99999 51\n', '')
