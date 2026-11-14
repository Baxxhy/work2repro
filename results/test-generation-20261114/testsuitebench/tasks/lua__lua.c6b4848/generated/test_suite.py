import os
import subprocess
from pathlib import Path

import pytest

E = Path(os.environ.get("LUA_EXE", "/workspace/executable"))
VERSION = "Lua 5.5.1  Copyright (C) 1994-2026 Lua.org, PUC-Rio\n"


def run(*args, input=None, env=None, cwd=None):
    merged = os.environ.copy()
    if env:
        merged.update(env)
    return subprocess.run([str(E), *map(str, args)], input=input, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          env=merged, cwd=cwd, timeout=15)


@pytest.mark.parametrize("source,expected", [
    ("print(_VERSION)", "Lua 5.5\n"),
    ("print(1+2, 'x')", "3\tx\n"),
    ("-- only comment\n", ""),
    ("print(0 and 'bad' or 'ok')", "ok\n"),
], ids=["compat-version", "print-tabs", "comment-only", "truth-and-short-circuit"])
def test_basic_language(source, expected):
    p = run("-e", source)
    assert (p.returncode, p.stdout, p.stderr) == (0, expected, "")


def test_version_is_single_and_precedes_actions():
    p = run("-e", "io.write('ok')", "-v", "-v")
    assert p.returncode == 0 and p.stdout == VERSION + "ok" and p.stderr == ""


def test_invalid_option_suppresses_earlier_actions():
    p = run("-v", "-h")
    assert p.returncode == 1 and p.stdout == ""
    assert "unrecognized option '-h'" in p.stderr and "Available options are:" in p.stderr


def test_separated_dash_prefixed_e_argument_is_missing():
    p = run("-e", "--[=[comment]=]")
    assert p.returncode == 1 and "'-e' needs argument" in p.stderr


def test_concatenated_e_and_e_equals_semantics():
    p = run("-eio.write('x')")
    assert (p.returncode, p.stdout, p.stderr) == (0, "x", "")
    p = run("-e=oops")
    assert p.returncode == 1 and "syntax" in p.stderr


def test_options_run_in_order_and_share_globals():
    p = run("-e", "x=12", "-e", "io.write(x)")
    assert (p.returncode, p.stdout, p.stderr) == (0, "12", "")


def test_script_arguments_and_varargs(tmp_path):
    script = tmp_path / "args.lua"
    script.write_text("print(arg[0], arg[1], arg[2], select('#', ...), ...)")
    p = run(str(script), "-x", "hello world")
    assert p.returncode == 0 and p.stdout == f"{script}\t-x\thello world\t2\t-x\thello world\n"


def test_script_shebang_and_line_number(tmp_path):
    script = tmp_path / "shebang.lua"
    script.write_text("#!/usr/bin/env lua\nerror('bad')\n")
    p = run(str(script))
    assert p.returncode == 1 and ":2: bad" in p.stderr


def test_stdin_explicit_and_automatic_error_status():
    explicit = run("-", input="error('stdinbad')")
    automatic = run("-E", input="error('stdinbad')")
    assert explicit.returncode == 1 and "stdin:1: stdinbad" in explicit.stderr
    assert automatic.returncode == 0 and "stdin:1: stdinbad" in automatic.stderr


def test_double_dash_treats_dash_as_filename():
    p = run("--", "-")
    assert p.returncode == 1 and "cannot open -" in p.stderr


def test_env_init_precedence_and_ignore(tmp_path):
    env = {"LUA_INIT_5_5": "io.write('new')", "LUA_INIT": "io.write('old')"}
    p = run("-e", "io.write('!')", env=env)
    assert p.returncode == 0 and p.stdout == "new!"
    p = run("-E", "-e", "io.write(os.getenv('LUA_INIT_5_5') and 'env' or 'none')", env=env)
    assert p.returncode == 0 and p.stdout == "env"


def test_warning_enable_and_control():
    p = run("-W", "-e", "warn('a',3)")
    assert p.returncode == 0 and p.stdout == "" and p.stderr == "Lua warning: a3\n"
    p = run("-W", "-e", "warn('@off'); warn('quiet')")
    assert p.returncode == 0 and p.stderr == ""


def test_runtime_error_keeps_prior_stdout():
    p = run("-e", "io.write('before'); error('boom'); io.write('after')")
    assert p.returncode == 1 and p.stdout == "before"
    assert "(command line):1: boom" in p.stderr and "stack traceback:" in p.stderr


@pytest.mark.parametrize("source,expected", [
    ("print(-7//3, -7%3)", "-3\t2\n"),
    ("print(1<<3, -1>>63)", "8\t1\n"),
    ("print(type(3), type(3.0), 9223372036854775807)", "integer\tfloat\t9223372036854775807\n"),
    ("local x=0; for i=1,3 do x=x+i end; print(x)", "6\n"),
], ids=["floor-modulo", "bit-shifts", "integer-float-types", "numeric-for"])
def test_core_operators(source, expected):
    p = run("-e", source)
    assert (p.returncode, p.stdout, p.stderr) == (0, expected, "")


def test_closures_and_multireturn():
    p = run("-e", "local function f() local x=1; return function() x=x+1; return x end end; local g=f(); print(g(),g()); local a,b= (function() return 3,4 end)(); print(a,b)")
    assert p.returncode == 0 and p.stdout == "2\t3\n3\t4\n"


def test_tables_metamethods_and_iterators():
    src = "local t={2,3}; local s=0; for _,v in ipairs(t) do s=s+v end; local x=setmetatable({}, {__index=function(_,k) return k end}); print(s,x.hello,select(1,ipairs{})==select(1,ipairs{}))"
    p = run("-e", src)
    assert p.returncode == 0 and p.stdout == "5\thello\ttrue\n"


def test_string_patterns_and_bytes():
    p = run("-e", "print(string.sub('abc',-2), string.gsub('hello world','%w+',function(w) return #w end), #string.char(65,0,66))")
    assert p.returncode == 0 and p.stdout == "bc\t5 5\t3\n"


def test_utf8_extended_encoding_and_offset():
    p = run("-e", "local s='A€🙂'; local a,b=utf8.offset(s,4); print(#utf8.char(0x110000),a,b,utf8.len(s))")
    assert p.returncode == 0 and p.stdout == "4\t9\t9\t3\n"


def test_coroutine_yield_resume_and_close():
    p = run("-e", "local c=coroutine.create(function(x) local y=coroutine.yield(x+1); return y+1 end); print(coroutine.resume(c,4)); print(coroutine.resume(c,8),coroutine.status(c))")
    assert p.returncode == 0 and p.stdout == "true\t5\ntrue\t9\tdead\n"


def test_package_preload_require_cache():
    src = "local n=0; package.preload.zz=function() n=n+1; return {v=n} end; local a=require('zz'); local b=require('zz'); print(a.v,b.v,n)"
    p = run("-e", src)
    assert p.returncode == 0 and p.stdout == "1\t1\t1\n"


def test_math_deterministic_random_sequence():
    p = run("-e", "math.randomseed(12345); print(math.random(),math.random(),math.random(10),math.random(5,15))")
    assert p.returncode == 0 and p.stdout == "0.87460442174732167\t0.40364110609593384\t7\t15\n"


def test_io_file_roundtrip(tmp_path):
    target = tmp_path / "data.bin"
    src = f"local f=assert(io.open({str(target)!r},'wb')); f:write('A\\0B'); f:close(); local g=assert(io.open({str(target)!r},'rb')); local s=g:read('*a'); g:close(); print(#s,string.byte(s,2))"
    p = run("-e", src)
    assert p.returncode == 0 and p.stdout == "3\t0\n"


def test_os_date_and_difftime():
    p = run("-e", "local t=os.date('!*t',0); print(t.year,t.month,t.day,t.wday,t.yday,os.difftime(50,0))", env={"TZ": "UTC", "LC_ALL": "C"})
    assert p.returncode == 0 and p.stdout == "1970\t1\t1\t5\t1\t50.0\n"


def test_load_syntax_eof_and_protected_call():
    p = run("-e", "local f,e=load('return 1 +','custom'); print(f==nil,e:match('unexpected symbol near <eof>')~=nil); print(pcall(function() error() end))")
    assert p.returncode == 0 and p.stdout == "true\ttrue\nfalse\t(command line):1: <no error object>\n"


def test_os_exit_status():
    p = run("-e", "os.exit(7)")
    assert p.returncode == 7

