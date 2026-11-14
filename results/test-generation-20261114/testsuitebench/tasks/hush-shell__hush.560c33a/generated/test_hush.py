import os
import subprocess
from pathlib import Path

import pytest

EXE = Path('/workspace/executable')
if not EXE.exists():
    EXE = Path(__file__).resolve().parent.parent / 'executable'


def run(src='', *args, stdin=None, cwd=None):
    data = src.encode() if stdin is None else stdin
    return subprocess.run([str(EXE), *map(str, args)], input=data, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, cwd=cwd, timeout=15)


def ok(src='', *args, stdin=None):
    p = run(src, *args, stdin=stdin)
    assert p.returncode == 0, (p.returncode, p.stdout, p.stderr)
    assert p.stderr == b''
    return p.stdout


def test_help_exact():
    p = run('--help')
    assert p.returncode == 0 and p.stderr == b''
    assert p.stdout.startswith(b'Hush 0.1.4\n') and b'USAGE:\n    executable [FLAGS] [arguments]...' in p.stdout
    assert p.stdout.endswith(b'ARGS:\n    <arguments>...    Script and/or arguments\n')

@pytest.mark.parametrize('flag', ['-h','--help'], ids=['short-help','long-help'])
def test_help_aliases(flag):
    assert run(flag).returncode == 0

@pytest.mark.parametrize('flag', ['-V','--version'], ids=['short-version','long-version'])
def test_version(flag):
    p=run(flag)
    assert (p.returncode,p.stdout,p.stderr)==(0,b'Hush 0.1.4\n',b'')


def test_cli_unknown_and_repeated_flags():
    p=run('--not-a-flag')
    assert p.returncode==1 and p.stdout==b'' and b"wasn't expected" in p.stderr and b'USAGE:' in p.stderr
    p=run('--lex','--lex')
    assert p.returncode==1 and p.stdout==b'' and b'provided more than once' in p.stderr and b'    executable --lex' in p.stderr


def test_double_dash_and_dash_arguments():
    out=ok('std.println(std.to_string(std.args()))','--','-x')
    assert b'-x' in out


def test_empty_and_comment_sources():
    for src in ['', '  \t\r\n', '# hi\n#there', '\n# tail\n']:
        assert ok(src)==b''


def test_file_source_and_args(tmp_path):
    f=tmp_path/'s.hush'; f.write_text('std.println(std.to_string(std.args()))\n')
    p=run('', str(f), '', 'a b', 'λ')
    assert p.returncode==0 and p.stderr==b''
    assert b'"", "a b", "' in p.stdout and 'λ'.encode() in p.stdout


def test_nonexistent_positional_is_arg_and_source_stdin():
    p=run('std.println(std.len(std.args()))', 'missing-file')
    assert p.returncode==0 and p.stdout==b'1\n'


def test_lex_empty_and_tokens():
    p=run('', '--lex')
    assert p.returncode==0 and p.stdout==b'-'*50+b'\n'+b'-'*50+b'\n'
    p=run('let x = 1\n','--lex')
    assert p.returncode==0 and b'<stdin> (line 1, column 0):\tlet\n' in p.stdout
    assert b'<stdin> (line 1, column 8):\t1\n' in p.stdout


def test_ast_and_program_rendering_and_check():
    p=run('let x = 1','--ast')
    assert p.returncode==0 and b'AST for <stdin>\nlet x = 1\n' in p.stdout
    p=run('let x = 42','--program')
    assert p.returncode==0 and b'Program for <stdin>\nlet #0: auto\nlet #1: auto\n#1 = 42\n' in p.stdout
    p=run('std.println("BAD")','--check')
    assert p.returncode==0 and p.stdout==b''
    p=run('std.println("BAD")','--check','--ast')
    assert p.returncode==0 and b'AST for <stdin>' in p.stdout and b'BAD' not in p.stdout


def test_render_order_and_execution():
    p=run('std.println("RUN")','--program','--ast','--lex')
    assert p.returncode==0
    assert p.stdout.index(b'<stdin> (line') < p.stdout.index(b'AST for') < p.stdout.index(b'Program for') < p.stdout.index(b'RUN\n')


def test_lexical_and_semantic_exit_codes():
    p=run('let x = "\\q"')
    assert p.returncode==2 and p.stderr
    p=run('missing')
    assert p.returncode==2 and b"undeclared variable 'missing'" in p.stderr


def test_lexical_literals_and_operator_precedence():
    out=ok('std.println(1 + 2 * 3);') if False else ok('std.println(1 + 2 * 3)')
    assert out==b'7\n'
    assert ok("std.println('a')")==b'a\n'
    assert ok('std.println(89e10)')==b'890000000000\n'
    assert ok('let b = 65b std.println(b)')==b'65\n'


def test_literal_dictionary_and_bad_keys():
    assert ok('let d = @[name: 7,] std.println(d.name)')==b'7\n'
    for src in ['@["x": 1]', '@[1: 2]']:
        p=run(src)
        assert p.returncode==2 and b'expected identifier' in p.stderr


def test_boolean_conditions_and_short_circuit():
    assert ok('std.println(true and false) std.println(false or true)')==b'false\ntrue\n'
    p=run('if 1 then end')
    assert p.returncode==127 and b'not a boolean' in p.stderr
    assert ok('std.println(false and std.assert(false))')==b'false\n'


def test_scopes_duplicate_and_undeclared():
    assert ok('let x = 1 if true then let x = 2 std.println(x) end std.println(x)')==b'2\n1\n'
    for src, msg in [('let x = 1 let x = 2',b"duplicate variable 'x'"),('x = 1',b"undeclared variable 'x'"),('return 1',b'return statement outside function'),('break',b'break statement outside loop'),('self',b'self keyword outside function')]:
        p=run(src); assert p.returncode==2 and msg in p.stderr


def test_assignment_and_aliasing():
    assert ok('let a = [1] let b = a b[0] = 9 std.println(a[0])')==b'9\n'
    p=run('1 + 2 = 3'); assert p.returncode==2 and b'invalid assignment' in p.stderr


def test_types_equality_and_display():
    assert ok('std.println(std.type(1), std.type(1.0), std.type(nil))')==b'int\tfloat\tnil\n'
    assert ok('std.println(1 == 1.0) std.println(std.to_string([1, "x"]))')==b'false\n[ 1, "x" ]\n'


def test_integer_arithmetic_and_panics():
    assert ok('std.println(-7 / 3) std.println(-7 % 3)')==b'-2\n-1\n'
    for src, msg in [('1 / 0','division by zero'),('9223372036854775807 + 1','integer overflow')]:
        p=run(src); assert p.returncode==127 and msg.encode() in p.stderr


def test_arrays_mutation_sort_and_index():
    assert ok('let a = [3, 1, 2] std.sort(a) std.println(a) std.push(a, 4) std.println(std.pop(a))')==b'[ 1, 2, 3 ]\n4\n'
    p=run('let a = [][5]'); assert p.returncode==127 and b'out of bounds' in p.stderr


def test_dict_keys_length_contains_and_missing():
    assert ok('let d = @[] d[1] = "n" d[true] = 2 std.println(std.len(d), std.contains(d, 1), d[1])')==b'2\ttrue\tn\n'
    p=run('let d = @[] d.nope'); assert p.returncode==127


def test_functions_recursion_return_and_arity():
    assert ok('function fact(n) if n <= 1 then return 1 end return n * fact(n - 1) end std.println(fact(6))')==b'720\n'
    p=run('function f(a) return a end f()'); assert p.returncode==127 and b'incorrect amount' in p.stderr


def test_closures_share_mutable_capture():
    src='function make() let n = 0 return function() n = n + 1 return n end end let f = make() std.println(f(), f())'
    assert ok(src)==b'1\t2\n'


def test_if_expression_and_loops():
    assert ok('std.println(if false then 1 else 2 end) let i = 0 while i < 3 do i = i + 1 end std.println(i)')==b'2\n3\n'
    assert ok('let s = 0 for x in std.range(1, 4, 1) do s = s + x end std.println(s)')==b'6\n'


def test_iterators_strings_and_range():
    assert ok('let s = 0 for x in std.iter([2, 3]) do s = s + x end std.println(s)')==b'5\n'
    assert ok('let i = std.range(3, 1, 1) std.println(i().finished)')==b'true\n'
    p=run('std.iter(42)'); assert p.returncode==127 and b'expected string, array or dict' in p.stderr


def test_print_read_and_string_bytes():
    assert ok('std.print("a", 2) std.println()')==b'a\t2\n'
    assert ok('std.println(std.len("é"), std.bytes(""), std.substr("abc", 3, 0))')==b'2\t[]\t\n'
    assert ok('std.println(std.split("a,,b,", ",")) std.println(std.replace("abc", "", "X"))')==b'[ "a", "", "b", "" ]\nXaXbXcX\n'
    p=run('std.println(std.read())', stdin=b'hello\n')
    assert p.returncode==0 and p.stdout==b'hello\n\n'


def test_conversions_typecheck_and_errors():
    assert ok('std.println(std.int("-12"), std.float("1.5"), std.type(std.try_typecheck(42, "int")))')==b'-12\t1.5\tnil\n'
    assert ok('let e = std.error("bad", 1) std.println(std.has_error([e]), e.description)')==b'true\tbad\n'
    assert ok('std.assert(true) std.println(std.type(std.catch(function() std.assert(false) end)))')==b'error\n'


def test_environment_rng_and_exit(tmp_path):
    assert ok('std.export("HUSH_TEST", "v") std.println(std.env("HUSH_TEST"))')==b'v\n'
    assert ok('std.randseed(7) let x = std.rand() std.randseed(7) std.println(x == std.rand())')==b'true\n'
    p=run('std.exit(23) std.println("no")'); assert p.returncode==23 and p.stdout==b''


def test_base64_hex_json():
    assert ok('std.println(std.base64.encode("hi"), std.hex.encode("A\\0B"))')==b'aGk=\t410042\n'
    assert ok('std.println(std.base64.decode("aGk="), std.hex.decode("41"))')==b'hi\tA\n'
    assert ok('std.println(std.json.encode([1, true, "x"]))')==b'[\n  1,\n  true,\n  "x"\n]\n'
    assert ok('let v = std.json.decode("{\\"x\\":1}") std.println(v.x)')==b'1\n'


def test_regex_methods():
    assert ok('let r = std.regex("a+") std.println(r.match("caa"), r.replace("caa", "X"))')==b'true\tcX\n'
    assert ok('let r = std.regex("") std.println(r.split("ab"))')==b'[ "", "a", "b", "" ]\n'


def test_command_sync_capture_and_failure(tmp_path):
    assert ok('{ echo hello }')==b'hello\n'
    assert ok('let r = ${ echo hello } std.println(r.stdout)')==b'hello\n\n'
    p=run('let r = ${ definitely_missing_hush_command } std.println(r.description)')
    assert p.returncode==0 and b'No such file or directory' in p.stdout


def test_command_quoting_expansion_and_redirection(tmp_path):
    assert ok("${ printf '%s' 'a b' }") == b'' # captured block's stdout is not implicitly printed
    src='let r = ${ printf "%s" "hello world" } std.println(r.stdout)'
    assert ok(src)==b'hello world\n'
    out=tmp_path/'out.txt'
    p=run('{ echo hi > '+str(out)+' }')
    assert p.returncode==0 and out.read_bytes()==b'hi\n'


def test_command_error_values_and_check_suppression():
    assert ok('let e = { false } std.println(std.has_error(e))')==b'true\n'
    p=run('{ echo SHOULD_NOT_RUN }','--check')
    assert p.returncode==0 and p.stdout==b''


def test_async_command_join():
    assert ok('let a = &{ true } let r = a.join() std.println(std.type(r))')==b'nil\n'
    p=run('let a = &{ true } a.join() a.join()')
    assert p.returncode==127 and b'join' in p.stderr


def test_diagnostic_locations_and_lex_recovery():
    p=run('let x = 1\nlet x = 2')
    assert p.returncode==2 and b'line 2, column 4' in p.stderr and b"duplicate variable 'x'" in p.stderr
    p=run('let x = "\\q"','--lex')
    assert p.returncode==2 and b"invalid escape sequence '\\q'." in p.stdout


def test_documented_scale_cases():
    assert ok('let a = ['+', '.join(str(i) for i in range(10000))+'] std.println(std.len(a))')==b'10000\n'
    assert ok('function sum('+','.join('p%d'%i for i in range(100))+') return p0 + p99 end std.println(sum('+','.join(str(i) for i in range(100))+'))')==b'99\n'


def test_stdin_marker_and_preserved_arguments():
    p=run('std.println(std.len(std.args()), std.args()[0], std.args()[1])', '-', 'a b', '')
    assert p.returncode==0 and p.stdout==b'2\ta b\t\n'
    p=run('std.println("pipe")','--',stdin=b'')
    assert p.returncode==0 and p.stdout==b'pipe\n'


def test_import_relative_to_importing_file(tmp_path):
    sub=tmp_path/'sub'; sub.mkdir()
    (sub/'mod.hush').write_text('let value = 42 value\n')
    main=sub/'main.hush'; main.write_text('std.println(std.import("mod.hush"))\n')
    p=run('', str(main), cwd='/')
    assert p.returncode==0 and p.stdout==b'42\n'


def test_glob_returns_empty_for_no_match(tmp_path):
    pattern=str(tmp_path/'no-such-*.hush')
    assert ok('std.println(std.len(std.glob('+repr(pattern)+')))')==b'0\n'


def test_error_propagation_and_immutable_error_fields():
    src='function f() return std.error("problem", nil)? end std.println(std.type(f()))'
    assert ok(src)==b'error\n'
    p=run('let e = std.error("x", nil) e.description = "y"')
    assert p.returncode==127 and b'readonly' in p.stderr


def test_command_failure_does_not_set_interpreter_exit_status():
    p=run('{ false } std.println("continued")')
    assert p.returncode==0 and p.stdout==b'continued\n'


def test_command_interpolation_and_input_redirection(tmp_path):
    f=tmp_path/'input'; f.write_bytes(b'payload')
    src='let x = "value with spaces" let r = ${ printf "%s" "$x" } std.println(r.stdout)'
    assert ok(src)==b'value with spaces\n'
    p=run('let r = ${ cat < '+str(f)+' } std.println(r.stdout)')
    assert p.returncode==0 and p.stdout==b'payload\n'
