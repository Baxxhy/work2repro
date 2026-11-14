import os
import subprocess
from pathlib import Path

import pytest

EVAL = Path(__file__).resolve().parent
EXE = Path('/workspace/executable')
if not EXE.exists():
    EXE = EVAL.parent / 'executable'


def run(*args, input=None, env=None, timeout=5):
    e = os.environ.copy()
    if env:
        e.update(env)
    return subprocess.run([str(EXE), *map(str, args)], input=input, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, env=e, timeout=timeout)


def lua(code, *args, **kw):
    return run('-e', code, *args, **kw)


def text(p):
    return p.stdout.decode('utf-8', 'replace')


def err(p):
    return p.stderr.decode('utf-8', 'replace')


def test_empty_stdin_and_noop_chunks():
    assert run(input=b'').returncode == 0
    for source in ('', ' \n\t', '-- comment\n', '--[[ comment ]]'):
        p = lua('io.write("ok")' if source == '' else source)
        assert p.returncode == 0 and p.stderr == b''


def test_help_text_and_precedence():
    p = run('--help', '-e', 'print(1)')
    assert p.returncode == 1 and p.stdout == b''
    s = err(p)
    assert s.startswith(f'usage: {EXE} [options]...'.replace('/workspace/executable', str(EXE)))
    for item in ('Available options:', '-e chunk', '-l name', '-b ...', '-j cmd', '-O[opt]', '-i', '-v', '-E', '--', '-         Execute stdin'):
        assert item in s
    assert '\x1b[' not in s and s.endswith('\n')


def test_help_alias_and_invalid_options_use_usage():
    for arg in ('-h', '--help', '-itail', '-vtail', '-x', '-e', '-l', '-j'):
        p = run(arg)
        assert p.returncode == 1 and p.stdout == b'' and err(p).startswith('usage:')


def test_version_shape_and_continues_processing():
    p = run('-v')
    assert p.returncode == 0 and p.stderr == b''
    line = text(p)
    assert line.endswith('\n') and line.count('\n') == 1
    for s in ('LuaJIT 2.1.', 'Copyright', 'Mike Pall', 'https://luajit.org'):
        assert s in line
    import re
    assert re.search(r'LuaJIT 2\.1\.\d+', line) and re.search(r'20\d\d', line)
    q = run('-v', '-e', 'print("x")')
    assert q.returncode == 0 and text(q).startswith(line) and text(q).endswith('x\n')


def test_chunks_joined_order_globals_and_scope():
    p = run('-e', 'x=4; local z=8; print("a")', '-ey=x+1', '-e', 'print(y, z)')
    assert p.returncode == 0 and text(p) == 'a\n5\tnil\n'


def test_argument_table_and_file_script_args(tmp_path):
    script = tmp_path / 'args.lua'
    script.write_text('print(arg[-2],arg[-1],arg[0],arg[1],arg[2])')
    p = run('-e', 'x=1', '-e', 'y=2', str(script), 'first', '-tail')
    assert p.returncode == 0 and text(p) == f'-e\ty=2\t{script}\tfirst\t-tail\n'


def test_stdin_marker_and_double_dash_stop_options():
    p = run('-', '-v', input=b'print(arg[1])')
    assert p.returncode == 0 and text(p) == '-v\n'
    q = run('--', '-h')
    assert q.returncode != 0 and 'cannot open -h' in err(q)


def test_missing_script_after_preprocessing_keeps_output():
    p = run('-e', 'print("before")', '/definitely/not/a/real/script.lua')
    assert p.returncode != 0 and text(p) == 'before\n'
    assert 'cannot open /definitely/not/a/real/script.lua' in err(p)


def test_stdin_batch_shebang_and_os_exit_status():
    p = run(input=b'#!/usr/bin/env lua\nprint("stdin")')
    assert p.returncode == 0 and text(p) == 'stdin\n'
    q = lua('print("x"); os.exit(5)')
    assert q.returncode == 5 and text(q) == 'x\n'


def test_interactive_banner_precedes_chunk_and_prompt():
    p = run('-i', '-e', 'print("chunk")', input=b'')
    s = text(p)
    assert p.returncode == 0 and s.startswith('LuaJIT 2.1.')
    assert s.index('chunk\n') < s.index('JIT:') < s.index('> ')


def test_lua_init_and_environment_ignore():
    p = run('-e', 'print("chunk")', env={'LUA_INIT': 'print("init")', 'EVAL_EMPTY': ''})
    assert p.returncode == 0 and text(p).startswith('init\nchunk\n')
    q = run('-E', '-e', 'print(os.getenv("EVAL_EMPTY"), os.getenv("NO_SUCH_EVAL_VAR"))',
            env={'LUA_INIT': 'print("bad")', 'EVAL_EMPTY': ''})
    assert q.returncode == 0 and text(q) == '\tnil\n'
    assert run('-Etail', input=b'').returncode == 0


def test_lua_grammar_escapes_precedence_and_goto():
    src = r'''local s="a\0\x42\u{1F600}"; local t={2,3,a=4,["b"]=5,};
local x=-2^2; local y="a".."b".."c"; local z=0b101+0x1p1
local n=0; goto done; n=99; ::done:: print(#s,string.byte(s,1,3),x,y,z,t.a,t.b)'''
    p = lua(src)
    assert p.returncode == 0 and text(p) == '7\t97\t0\t66\t-4\tabc\t7\t4\t5\n'


def test_values_closures_varargs_and_recursion():
    p = lua('''local function pair() return 2,nil,4 end
local a,b,c,d=1,pair(); local function maker() local x=0; return function() x=x+1; return x end,function() return x end end
local inc,get=maker(); local function fact(n) if n==0 then return 1 end return n*fact(n-1) end
print(a,b,c,d,inc(),get(),fact(8),select("#",1,nil,3))''')
    assert p.returncode == 0 and text(p) == '1\t2\tnil\t4\t1\t1\t40320\t3\n'


def test_base_functions_and_error_values():
    p = lua('''local a,b,c=assert(true,1,nil); print(a,b,c,tonumber("ff",16),tonumber("0b11"),select("#",1,nil),unpack({1,nil,3}))
local ok,e=pcall(function() error({x=1},0) end); print(ok,type(e),_VERSION)''')
    assert p.returncode == 0 and text(p).startswith('true\t1\tnil\t255\t3\t2\t1\tnil\t3\nfalse\ttable\tLua 5.1\n')


def test_table_metamethods_raw_and_iteration():
    p = lua('''local backing={x=3}; local t=setmetatable({}, {__index=backing,__newindex=backing,__add=function(a,b)return a.x+b end,__tostring=function()return "T" end,__len=function()return 99 end})
t.y=4; local sum=t+2; local n=0; for k,v in pairs({10,20,a=30}) do n=n+v end
print(t.x,t.y,rawget(t,"x"),sum,tostring(t),#t,n)''')
    assert p.returncode == 0 and text(p) == '3\t4\tnil\t5\tT\t0\t60\n'


def test_runtime_errors_protected_and_traceback():
    p = lua('local x=nil; print(x+5)')
    assert p.returncode != 0 and "attempt to perform arithmetic on local 'x' (a nil value)" in err(p)
    assert 'stack traceback:' in err(p)
    q = lua('local ok,e=pcall(function() local x=nil; return x.."s" end); print(ok,string.find(e,"attempt to concatenate",1,true)~=nil)')
    assert q.returncode == 0 and text(q) == 'false\ttrue\n'


def test_string_patterns_and_binary():
    p = lua('local s="a\\0B"; print(#s,string.byte(s,2),string.gsub("ab12","%d","x"),string.match("abc123","(%a+)%d+"),string.reverse(s))')
    assert p.returncode == 0 and p.stdout == b'3\t0\tabxx\t2\tabc\tB\x00a\n'


def test_load_compile_environment_and_dump():
    p = lua('local f,e=load("return x*2","chunk","t",{x=10}); print(f(),e); local b=string.dump(function() return 7 end); print(loadstring(b)())')
    assert p.returncode == 0 and text(p) == '20\tnil\n7\n'
    q = lua('local f,e=load("local x = "); print(f==nil,string.find(e,"unexpected symbol near",1,true)~=nil)')
    assert q.returncode == 0 and text(q) == 'true\ttrue\n'


def test_coroutines_and_gc():
    p = lua('local c=coroutine.create(function(x) local y=coroutine.yield(x+1); return y+1 end); local a,b=coroutine.resume(c,4); local d,e=coroutine.resume(c,8); print(a,b,d,e,coroutine.status(c),coroutine.isyieldable()); collectgarbage("collect"); print(type(gcinfo()))')
    assert p.returncode == 0 and text(p) == 'true\t5\ttrue\t9\tdead\tfalse\nnumber\n'


def test_io_binary_and_write_return(tmp_path):
    f = tmp_path / 'binary.dat'
    code = f'''local f=assert(io.open({str(f)!r},"wb")); local r=f:write("a\\0b"); f:close(); local g=assert(io.open({str(f)!r},"rb")); local s=g:read("*a"); g:close(); io.write(type(r),"|",#s,"|",string.byte(s,2))'''
    p = lua(code)
    assert p.returncode == 0 and p.stdout == b'boolean|3|0'


def test_os_date_and_env():
    p = lua('print(os.difftime(9,4),os.date("!%Y-%m-%d",0),os.setlocale(nil,"numeric"),os.getenv("EVAL_X"))', env={'EVAL_X':'yes'})
    assert p.returncode == 0 and text(p) == '5\t1970-01-01\tC\tyes\n'


def test_package_preload_cache_and_searchpath(tmp_path):
    p = lua('package.preload.zz=function(n) count=(count or 0)+1; return {name=n} end; local a=require("zz"); local b=require("zz"); print(a==b,count,a.name,package.config:sub(1,5))')
    assert p.returncode == 0 and text(p) == 'true\t1\tzz\t/\t;\t?\t!\t-\n'


def test_debug_upvalue_and_bit_library():
    p = lua('local x=3; local function f() return x end; local n,v=debug.getupvalue(f,1); local bit=require("bit"); print(n,v,bit.tohex(bit.bnot(0)),bit.tobit(2.5),bit.rshift(-1,1))')
    assert p.returncode == 0 and text(p) == 'x\t3\tffffffff\t2\t2147483647\n'


def test_ffi_types_memory_and_error():
    p = lua('local ffi=require("ffi"); ffi.cdef[[typedef struct { int x; double y; } point;]]; local p=ffi.new("point",{x=3,y=2.5}); local a=ffi.new("int[3]",{4,5,6}); print(type(p),p.x,p.y,a[0],a[2],ffi.sizeof("int"),ffi.os,ffi.arch)')
    assert p.returncode == 0 and text(p).startswith('cdata\t3\t2.5\t4\t6\t4\tLinux\tx64\n')
    q = lua('local f=pcall(function() require("ffi").typeof() end); local ok,e=pcall(function() require("ffi").typeof() end); print(ok,string.find(e,"C type expected, got no value",1,true)~=nil)')
    assert q.returncode == 0 and text(q) == 'false\ttrue\n'


def test_string_buffer_roundtrip():
    p = lua('local b=require("string.buffer"); local x=b.new():put("ab",3,"\\0c"); local a,c=x:get(2,2); local y=x:get(); local z=b.encode({a=1,[2]="v",x="\\0"}); local t=b.decode(z); print(a,c=="3\\0",#y,t.a,t[2],#t.x)')
    assert p.returncode == 0 and text(p) == 'ab\ttrue\t1\t1\tv\t1\n'


def test_jit_status_controls_and_profile_validation():
    p = lua('local s={jit.status()}; local n=#s; jit.off(); local q={jit.status()}; jit.on(); print(s[1],n,q[1],q[2],jit.security("prng"),type(require("jit.util").ircalladdr(1)),type(require("jit.profile").dumpstack("f",16)))')
    assert p.returncode == 0 and text(p) == 'true\t14\tfalse\tSSE3\t1\tnumber\tstring\n'
    q = lua('local ok,e=pcall(function() require("jit.profile").dumpstack(nil,"f",16) end); print(ok,string.find(e,"bad argument #1 to \'dumpstack\'",1,true)~=nil)')
    assert q.returncode == 0 and text(q) == 'false\ttrue\n'


def test_cli_jit_and_optimization_levels():
    p = run('-joff','-O2','-e','local s={jit.status()}; print(s[1],s[2],s[3],s[4],s[5],s[6],s[7],s[8],s[9])')
    assert p.returncode == 0 and text(p) == 'false\tSSE3\tSSE4.1\tBMI2\tfold\tcse\tdce\tnarrow\tloop\n'
    q = run('-Oinvalid')
    assert q.returncode == 1 and q.stdout == b'' and 'unknown or malformed optimization flag' in err(q)
    r = run('-jmissing')
    assert r.returncode == 1 and r.stdout == b'' and 'unknown luaJIT command or jit.* modules not installed' in err(r)


def test_bytecode_cli_spellings_rejected_without_artifacts(tmp_path):
    target = tmp_path / 'out.bc'
    for args in (('-bl',),('-bs','-e','print(1)',str(target)),('-be','print(1)'),('-b','-e','print(1)'),('-b','-','-'),('-bd','-e','print(1)'),('-bg','no.lua')):
        p = run(*args, input=b'')
        assert p.returncode == 1 and p.stdout == b''
        assert err(p) == f'{EXE}: unknown luaJIT command or jit.* modules not installed\n'
    assert not target.exists()


def test_parser_diagnostics_no_traceback():
    cases = [('syntax error', "'=' expected near 'error'"), ('local x =', "unexpected symbol near '<eof>'"),
             ('function foo(', "<name> or '...' expected near '<eof>'"), ('local x = [[unfinished', "unfinished long string near '<eof>'")]
    for source, message in cases:
        p = run('-e', source)
        assert p.returncode != 0 and p.stdout == b''
        diagnostic = err(p)
        assert f'{EXE}: (command line):1:' in diagnostic and message in diagnostic
        assert 'stack traceback:' not in diagnostic


def test_runtime_error_has_traceback_and_exit_is_only_status_override():
    p = lua('error("boom")')
    assert p.returncode != 0 and 'boom' in err(p) and 'stack traceback:' in err(p)
    assert lua('os.exit(3)').returncode == 3
