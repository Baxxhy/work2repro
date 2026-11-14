import os
import pty
import select
import subprocess
import tempfile
import time
from pathlib import Path

import pytest

EXE = '/workspace/executable'
LANGS = 'bash, c, cpp, crystal, csharp, dart, elixir, go, groovy, haskell, java, javascript, julia, kotlin, lua, nim, perl, php, python, r, ruby, rust, swift, typescript, zig'
HELP = """Universal multi-language runner and REPL

Usage: executable [OPTIONS] [ARGS]...

Arguments:
  [ARGS]...  Positional arguments (language, code, or file)

Options:
  -V, --version      Print version information and exit
  -l, --lang <LANG>  Explicitly choose the language to execute
  -f, --file <PATH>  Execute code from the provided file path
  -c, --code <CODE>  Execute the provided code snippet
      --no-detect    Disable heuristic language detection
  -h, --help         Print help
"""

def run(*args, input=None, cwd=None, timeout=12):
    return subprocess.run([EXE, *map(str, args)], input=input, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, cwd=cwd, timeout=timeout)

def out(p): return p.stdout.decode('utf-8', 'replace')
def err(p): return p.stderr.decode('utf-8', 'replace')

def test_help_exact_and_precedes_unknown():
    for args in (('-h',), ('--help',), ('--help', '--nonesuch')):
        p = run(*args)
        assert p.returncode == 0 and out(p) == HELP and p.stderr == b''

def test_version_metadata_and_precedence():
    a, b = run('-V'), run('--version', '-c', "print('NO')")
    for p in (a, b):
        s = out(p)
        assert p.returncode == 0 and p.stderr == b''
        assert s.startswith('run-kit 0.3.2\n') and s.endswith('\n')
        for line in ['Universal multi-language runner and smart REPL', 'author: Esubalew Chekol <esubalewchekol6@gmail.com>', 'homepage: https://esubalew.et', 'repository: https://github.com/Esubaalew/run', 'license: Apache-2.0']:
            assert line in s
        for key in ('commit:', 'built:', 'rustc:'):
            assert any(x.startswith(key) and x[len(key):].strip() for x in s.splitlines())
    assert out(b) == out(a)

@pytest.mark.parametrize('arg, canonical', [('-l', '--lang <LANG>'), ('--lang', '--lang <LANG>'), ('-c', '--code <CODE>'), ('--code', '--code <CODE>'), ('-f', '--file <PATH>'), ('--file', '--file <PATH>')], ids=['short-lang','long-lang','short-code','long-code','short-file','long-file'])
def test_missing_value_errors(arg, canonical):
    p = run(arg)
    assert p.returncode == 2 and p.stdout == b''
    assert err(p) == f"error: a value is required for '{canonical}' but none was supplied\n\nFor more information, try '--help'.\n"

def test_unknown_option_exact():
    p = run('--no-such-flag')
    assert p.returncode == 2 and p.stdout == b''
    assert err(p) == "error: unexpected argument '--no-such-flag' found\n\n  tip: to pass '--no-such-flag' as a value, use '-- --no-such-flag'\n\nUsage: executable [OPTIONS] [ARGS]...\n\nFor more information, try '--help'.\n"

def test_repeated_code_exact():
    p=run('-c','x','--code','y')
    assert p.returncode == 2 and p.stdout == b''
    assert err(p)=="error: the argument '--code <CODE>' cannot be used multiple times\n\nUsage: executable [OPTIONS] [ARGS]...\n\nFor more information, try '--help'.\n"

def test_option_forms_and_execution():
    for args in (('--lang=python','--code=print(17)'), ('-lpython','-c', 'print(17)'), ('--code','print(17)','--lang','PYTHON')):
        p=run(*args)
        assert p.returncode==0 and out(p)=='17\n' and p.stderr==b''

def test_empty_and_whitespace_code_distinction():
    p=run('--code','')
    assert p.returncode==2 and "--code <CODE>" in err(p)
    p=run('--code',' \t\n')
    assert p.returncode==1 and out(p)=='' and err(p)=='Error: Inline code provided via --code must not be empty\n'

def test_semantic_conflicts_and_extra_args():
    cases=[(('--code','print(1)','--file','x'), 'Error: --code/--inline cannot be combined with --file\n'),
           (('--lang','python','--code','print(1)','py'), 'Error: Unexpected positional arguments after specifying --code\n'),
           (('--file','/not/here','extra'), 'Error: Unexpected positional arguments when --file is present\n')]
    for args, message in cases:
        p=run(*args); assert p.returncode==1 and p.stdout==b'' and err(p)==message

def test_registry_unknown_normalization_and_punctuation():
    for name in ('py_thon','py-thon','python with spaces','python;ls','cxx'):
        p=run('--lang',name,'--code','pass')
        assert p.returncode==1 and out(p)==''
        assert err(p)==f"Error: Unknown language '{name}'. Available languages: {LANGS}\n"

def test_aliases_and_case_whitespace():
    for alias in ('py','py3','python3',' PYTHON '):
        p=run('--lang',alias,'--code','print(23)')
        assert p.returncode==0 and out(p)=='23\n' and p.stderr==b''

def test_positional_code_join_and_language_token_rules():
    p=run('python','print(1 +','2)')
    assert p.returncode==0 and out(p)=='3\n'
    p=run('--lang','python','py',"print('ok')")
    assert p.returncode!=0 and 'SyntaxError' in err(p)
    p=run('python','-c',"print('a')", "print('b')")
    assert p.returncode!=0 and 'SyntaxError' in err(p) and 'Unexpected positional' not in err(p)

def test_pathlike_missing_path_is_file_not_code():
    p=run('--lang','python','./missing-special.py')
    assert p.returncode==2 and "can't open file" in err(p) and 'SyntaxError' not in err(p)

def test_file_paths_spaces_unicode_and_no_extension():
    with tempfile.TemporaryDirectory(prefix='eval ') as d:
        path=Path(d)/'snow ☃ noext'
        path.write_text("print('file-ok')")
        p=run(str(path))
        assert p.returncode==0 and out(p)=='file-ok\n' and p.stderr==b''

def test_extension_detection_case_and_explicit_override():
    with tempfile.TemporaryDirectory() as d:
        py=Path(d)/'source.PY'; py.write_text("echo file-detected\n")
        p=run(str(py)); assert p.returncode==0 and out(p)=='file-detected\n'
        p=run('--lang','python','--file',str(py)); assert p.returncode!=0 and 'SyntaxError' in err(p)
        sh=Path(d)/'source.SH'; sh.write_text("print('python override')\n")
        p=run('--lang','python','--file',str(sh)); assert p.returncode==0 and out(p)=='python override\n'

def test_no_detect_disables_extension_guess():
    with tempfile.TemporaryDirectory() as d:
        f=Path(d)/'script.sh'; f.write_text('echo should-not-run-as-shell\n')
        p=run('--no-detect',str(f)); assert p.returncode!=0 and 'SyntaxError' in err(p)

def test_inline_detection_and_precedence():
    p=run('--code','  #!/bin/bash\necho detected')
    assert p.returncode==0 and out(p)=='detected\n'
    p=run('--code','\n  import math\nprint(math.sqrt(9))')
    assert p.returncode==0 and out(p)=='3.0\n'
    p=run('--code','fn helper() {}')
    assert p.returncode==1 and out(p)=='' and 'SyntaxError: invalid syntax' in err(p)
    p=run('--code','print(6 * 7)')
    assert p.returncode==1 and 'Lua support requires' in err(p)

def test_no_detect_and_stdin_source_modes():
    p=run('--no-detect','--code','echo not-shell', input=b'')
    assert p.returncode!=0 and 'SyntaxError' in err(p)
    p=run('--lang','python','-',input=b"print('stdin-source')\n")
    assert p.returncode==0 and out(p)=='stdin-source\n'
    p=run('--lang','python',input=b"print('stdin-no-args')\n")
    assert p.returncode==0 and out(p)=='stdin-no-args\n'

def test_invalid_utf8_materialized_source_errors():
    for args in ((),('--lang','python'),('python','-')):
        p=run(*args,input=b'\xff')
        assert p.returncode==1 and out(p)==''
        assert err(p)=='Error: failed to materialize execution payload\n\nCaused by:\n    stream did not contain valid UTF-8\n'

def test_python_file_stdin_preserves_raw_bytes_diagnostic():
    p=run('--lang','python','--file','-',input=b'\xff')
    assert p.returncode==1 and p.stdout==b''
    assert err(p)=="SyntaxError: Non-UTF-8 code starting with '\\xff' in file <stdin> on line 2, but no encoding declared; see https://python.org/dev/peps/pep-0263/ for details\n"

def test_program_streams_status_and_unicode():
    p=run('--lang','python','--code',"import sys; print('out'); print('snowman:☃', file=sys.stderr); sys.exit(7)")
    assert p.returncode==7 and out(p)=='out\n' and err(p)=='snowman:☃\n'

def test_python_semantics_multiline_and_native_diagnostics():
    p=run('--lang','python','--code','def twice(x):\n    return x * 2\nprint(twice(8))')
    assert p.returncode==0 and out(p)=='16\n'
    p=run('--lang','python','--code','1 / 0')
    assert p.returncode!=0 and 'ZeroDivisionError' in err(p) and '<string>' in err(p)

def test_bash_execution_and_missing_command_status():
    p=run('--lang','bash','--code','a=(x y); printf "%s:%s\\n" "${a[0]}" "${a[1]}"')
    assert p.returncode==0 and out(p)=='x:y\n'
    p=run('--lang','bash','--code','definitely_missing_command_xyz')
    assert p.returncode==127 and '/usr/bin/bash: line 1: definitely_missing_command_xyz: command not found' in err(p)

def test_registered_missing_tool_errors_and_registry():
    expected={'java':'Java support requires the `javac` compiler', 'kotlin':'Kotlin support requires the `kotlinc` compiler','lua':'Lua support requires the `lua` executable','julia':'Julia support requires the `julia` executable','csharp':'C# support requires the `dotnet` CLI'}
    for lang, fragment in expected.items():
        p=run('--lang',lang,'--code','')
        # Empty explicit code validation precedes tool lookup; request a real snippet.
        p=run('--lang',lang,'--code','print(1)')
        assert p.returncode==1 and out(p)=='' and fragment in err(p)

def test_rust_go_perl_one_shot_engines():
    p=run('--lang','rust','--code','fn main() { println!("rust-ok"); }')
    assert p.returncode==0 and out(p)=='rust-ok\n'
    p=run('--lang','go','--code','package main\nimport "fmt"\nfunc main(){fmt.Println("go-ok")}')
    assert p.returncode==0 and out(p)=='go-ok\n'
    p=run('--lang','perl','--code','print "perl-ok\\n";')
    assert p.returncode==0 and out(p)=='perl-ok\n'

def test_positional_file_and_file_stdin():
    with tempfile.TemporaryDirectory() as d:
        f=Path(d)/'script.py'; f.write_bytes(b"print('no newline')")
        p=run(str(f)); assert p.returncode==0 and out(p)=='no newline\n'
    p=run('-f','-',input=b"print('file stdin')\n")
    assert p.returncode==0 and out(p)=='file stdin\n'

def test_help_tokens_after_positional_are_source():
    for args in (('1','--version'),('--','--help')):
        p=run(*args)
        assert p.returncode!=0 and 'SyntaxError' in err(p) and 'run-kit' not in out(p)

def repl(commands, timeout=15):
    master, slave = pty.openpty()
    proc = subprocess.Popen([EXE], stdin=slave, stdout=slave, stderr=slave, close_fds=True)
    os.close(slave)
    data = bytearray()
    try:
        os.write(master, commands.encode())
        deadline = time.monotonic() + timeout
        while proc.poll() is None and time.monotonic() < deadline:
            ready, _, _ = select.select([master], [], [], 0.1)
            if ready:
                try: data.extend(os.read(master, 65536))
                except OSError: break
        if proc.poll() is None:
            proc.kill()
            raise subprocess.TimeoutExpired([EXE], timeout)
        while True:
            try:
                ready, _, _ = select.select([master], [], [], 0)
                if not ready: break
                data.extend(os.read(master, 65536))
            except OSError: break
        return subprocess.CompletedProcess([EXE], proc.returncode, bytes(data), b'')
    finally:
        os.close(master)

def test_nonterminal_no_args_does_not_hang():
    p=run(timeout=4)
    assert p.returncode==0

def test_repl_help_switch_detection_and_exit():
    p=repl(':help\n:languages\n:lang js\n:py\n:detect off\n:detect on\n:exit\n')
    s=out(p)
    assert 'run universal REPL. Type :help for commands.\npython>>> ' in s
    assert 'Commands:\n  :help' in s and ':exit, :quit' in s
    assert f'available languages: {LANGS}' in s
    assert 'switched to javascript' in s and 'switched to python' in s
    assert 'auto-detect disabled' in s and 'auto-detect enabled' in s

def test_python_repl_state_repr_reset_and_recovery():
    p=repl("x = 40\nx + 2\n:reset\nx\n:exit\n")
    s=out(p)
    assert '42' in s and "session for 'python' reset" in s and 'NameError' in s and '[exit code ' in s

def test_bash_repl_state_reset_and_error_recovery():
    p=repl(':lang bash\nx=41\necho $x\nfalse\necho alive\n:reset\necho $x\n:exit\n')
    s=out(p)
    assert 'switched to bash' in s and '41' in s and 'alive' in s
    assert "session for 'bash' reset" in s and '[exit code 1]' in s

def test_repl_all_canonical_languages_switch_even_without_tools():
    script=''.join(f':lang {x}\n' for x in LANGS.split(', ')) + ':exit\n'
    s=out(repl(script))
    for x in LANGS.split(', '): assert f'switched to {x}' in s and f'{x}>>> ' in s

def test_repl_unknown_alias_messages_and_alias_shortcut():
    p=repl(':cxx\n:lang cxx\n:cr\n:exit\n')
    s=out(p)
    assert 'unknown command: :cxx. Type :help for help.' in s
    assert 'unsupported' in s and 'switched to crystal' in s and 'crystal>>> ' in s

def test_detection_priority_and_stdout_stderr_separation():
    # C++ signature must beat C; real toolchain execution checks selected engine.
    source='#include <iostream>\nint main(){ std::cout << "cpp"; }'
    p=run('--code',source)
    assert p.returncode==0 and out(p)=='cpp' and p.stderr==b''
    p=run('--lang','python','--code',"import sys; sys.stdout.write('A'); sys.stderr.write('B')")
    assert p.returncode==0 and out(p)=='A' and err(p)=='B'

def test_c_statement_wrapping_and_native_status():
    p=run('--lang','c','--code','#include <stdio.h>\nprintf("c-ok\\n");')
    assert p.returncode==0 and out(p)=='c-ok\n'
    p=run('--lang','c','--code','#include <stdio.h>\nint main(void) { printf("status\\n"); return 7; }')
    assert p.returncode==7 and out(p)=='status\n'

def test_cpp_translation_unit_and_inline_newline_materialization():
    p=run('--lang','cpp','--code','#include <iostream>\\nint main() { std::cout << "inline-cpp with \\\\n newlines" << std::endl; return 0; }')
    assert p.returncode==0 and out(p)=='inline-cpp with \\n newlines\n'
    p=run('--lang','cpp','--code','#include <vector>\nint main(){ std::vector<int> v{2,3}; std::cout << v[1]; }')
    assert p.returncode==0 and out(p)=='3'

def test_c_inline_marker_documented_space_before_main():
    p=run('--lang','c','--code','#include <stdio.h>\nint main () { printf("not-run"); return 0; }')
    assert p.returncode==0 and out(p)==''

def test_lossy_child_output_and_large_text():
    p=run('--lang','python','--code',"import sys; sys.stdout.buffer.write(bytes(range(256)))")
    expected=bytes(range(128)) + b'\xef\xbf\xbd'*128
    assert p.returncode==0 and p.stdout==expected
    huge='Z'*200000
    p=run('--lang','python','--code',f"print('{huge}')")
    assert p.returncode==0 and p.stdout== (huge+'\n').encode()

def test_special_argument_transport_and_current_directory():
    with tempfile.TemporaryDirectory(prefix='space [eval] ') as d:
        p=run('--lang','python','--code',"import os; print(os.getcwd())",cwd=d)
        assert p.returncode==0 and out(p)==d+'\n'
        f=Path(d)/"quote '$`☃.py"
        f.write_text("print('safe path')\n")
        p=run('--file',str(f)); assert p.returncode==0 and out(p)=='safe path\n'

def test_rust_and_go_file_stdin_documented_failures():
    rust=run('--lang','rust','--file','-',input=b'fn main() {}')
    assert rust.returncode==1 and rust.stdout==b'' and 'main function not found' in err(rust)
    go=run('-lgo','-f','-',input=b'package main\nfunc main() {}')
    assert go.returncode==1 and go.stdout==b'' and 'failed to invoke /usr/local/go/bin/go to run -' in err(go)
