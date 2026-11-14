import json, os, pathlib, subprocess, tempfile
import pytest

EXE = '/workspace/executable'

def run(*args, cwd=None, env=None, data=None, timeout=20):
    e = os.environ.copy()
    e['HOME'] = str(pathlib.Path(cwd or '/tmp').resolve())
    e['TYPST_COLOR'] = 'never'
    if env:
        e.update(env)
    return subprocess.run([EXE, *map(str,args)], cwd=cwd, env=e, input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)

def txt(b): return b.decode('utf-8', 'replace')

def test_version_long_and_short():
    for flag in ('--version','-V'):
        p=run(flag)
        assert p.returncode==0 and p.stdout==b'typst 0.14.2 (ccc34be7)\n' and p.stderr==b''

def test_help_sections_urls_commands():
    p=run('--help'); s=txt(p.stdout)
    assert p.returncode==0 and p.stderr==b''
    assert s.startswith('Typst 0.14.2 (ccc34be7)\n\nUsage: executable [OPTIONS] <COMMAND>')
    for t in ('Commands:','Options:','Resources:','compile','watch','init','eval','fonts','completions','info','https://typst.app/docs/tutorial/','https://typst.app/docs/reference/','https://typst.app/universe/','https://forum.typst.app/','Reference documentation:','--color <COLOR>','--cert <CERT>'):
        assert t in s

def test_help_flag_precedence_and_double_dash():
    p=run('--help','--bogus'); assert p.returncode==0 and p.stdout.startswith(b'Typst ') and p.stderr==b''
    p=run('--','--help'); assert p.returncode==2 and not p.stdout and b'error:' in p.stderr

def test_compile_help_shared_alias():
    a=run('help','compile'); b=run('c','--help')
    assert a.returncode==b.returncode==0 and a.stdout==b.stdout and not a.stderr and not b.stderr
    s=txt(a.stdout)
    for t in ('Compiles an input file into a supported output format','Usage: executable compile [OPTIONS] <INPUT> [OUTPUT]','page-{0p}-of-{t}.png','--pdf-standard','--pages','--deps-format','--creation-timestamp','--timings','[possible values: pdf, png, svg, html]'):
        assert t in s

def test_help_eval_and_fonts_interfaces():
    for cmd in (('eval','--help'),('eval','-h')):
        p=run(*cmd); assert p.returncode==0 and txt(p.stdout).startswith('Evaluates a piece of Typst code, optionally in the context of a document')
        for t in ('json, yaml','--pretty','--input','--root','--font-path','--package-path','--features','--target','--in <IN>'): assert t in txt(p.stdout)
        assert '--input-file' not in txt(p.stdout)
    p=run('fonts','--help'); assert p.returncode==0 and txt(p.stdout).startswith('Lists all discovered fonts in system and custom font paths\n\nUsage: executable fonts [OPTIONS]')

def test_help_command_special_case():
    p=run('help','--help'); assert p.returncode==2 and p.stdout==b'' and txt(p.stderr).startswith("error: unrecognized subcommand '--help'")

def test_parser_errors_and_color_order():
    cases=[(('compiel',),b'compile'),(('compile','-j'),b"a value is required for '--jobs <JOBS>' but none was supplied"),(('compile','--ppi','abc','x.typ'),b"error: invalid value 'abc' for '--ppi <PPI>': invalid float literal"),(('compile','--format','wat','x.typ'),b'possible values')]
    for args, needle in cases:
        p=run(*args); assert p.returncode==2 and not p.stdout and b'error:' in p.stderr and needle in p.stderr and b"For more information, try '--help'." in p.stderr
    p=run('--color','purple','help'); assert p.returncode==0 and p.stdout.startswith(b'Typst ')
    p=run('--color','ALWAYS'); assert p.returncode==2 and b'[possible values: auto, always, never]' in p.stderr
    p=run('--color','purple','missing-command'); assert p.returncode==2 and b'unrecognized subcommand' in p.stderr

def test_missing_compile_positionals_exact():
    p=run('compile'); assert p.returncode==2 and p.stdout==b''
    assert p.stderr==b"error: the following required arguments were not provided:\n  <INPUT>\n\nUsage: executable compile <INPUT> [OUTPUT]\n\nFor more information, try '--help'.\n"
    p=run('compile','-'); assert p.returncode==2 and p.stdout==b''
    assert p.stderr==b"error: the following required arguments were not provided:\n  <OUTPUT>\n\nUsage: executable compile <INPUT> <OUTPUT>\n\nFor more information, try '--help'.\n"

def test_input_option_equals_and_repeat():
    p=run('eval','sys.inputs'); assert p.returncode==0 and p.stdout==b'{}\n'
    p=run('eval','sys.inputs','--input','x-y=a=b','--input=x-y=last')
    assert p.returncode==0 and json.loads(p.stdout)=={'x-y':'last'}
    p=run('eval','sys.inputs.at("k")','--input','k=')
    assert p.returncode==0 and p.stdout==b'""\n'

def test_eval_scalar_serialization():
    cases=[('1+2',b'3\n'),('"héllo"', '"héllo"\n'.encode()),('true',b'true\n'),('none',b'null\n'),('[1,2,3]',b'[1,2,3]\n'),('(a: 1, b: 2)',b'{"a":1,"b":2}\n'),('10pt',b'"10pt"\n'),('float.nan',b'null\n')]
    for expr,want in cases:
        p=run('eval',expr); assert p.returncode==0 and p.stdout==want and p.stderr==b''

def test_eval_pretty_yaml_and_target_validation():
    p=run('eval','[1,2]','--pretty'); assert p.returncode==0 and p.stdout==b'[\n  1,\n  2\n]\n'
    p=run('eval','3','--format','yaml'); assert p.returncode==0 and p.stdout==b'3\n\n'
    p=run('eval','1','--target','other'); assert p.returncode==2 and b'error:' in p.stderr
    p=run('eval','1','--input-file','x'); assert p.returncode==2 and b'unexpected argument' in p.stderr

def test_eval_language_errors_have_status_zero():
    for expr, phrase in [('missing_name','unknown variable'),('1 +','expected expression'),('"a" + 1','cannot add string and integer'),('1 / 0','cannot divide by zero')]:
        p=run('eval',expr); assert p.returncode==0 and p.stdout==b'' and phrase.encode() in p.stderr and p.stderr.endswith(b'\n\n')

def test_eval_unit_operators_and_calculations():
    pairs=[('50% * 20%',b'"10%"\n'),('200% / 50%',b'4.0\n'),('20pt / 5pt',b'4.0\n'),('10pt + 50%',b'"50% + 10pt"\n'),('calc.norm(p: 1, 3, 4)',b'7.0\n'),('calc.rem(-10, 3)',b'-1\n'),('calc.log(1000)',b'3.0\n'),('calc.asin(0)',b'"0deg"\n')]
    for expr,want in pairs:
        p=run('eval',expr); assert p.returncode==0 and p.stdout==want and not p.stderr

def test_eval_error_diagnostics():
    for expr, phrase in [('"x" + (1, 2)','cannot add string and array'),('-("x")','cannot apply'),('calc.sqrt(-1)','cannot take square root of negative number'),('calc.root(16, 0)','cannot take the 0th root of a number'),('calc.acosh(0.5)','value must be greater than or equal to 1'),('().sum()','cannot calculate sum of empty array'),('(a: 1).at("c")','dictionary does not contain key')]:
        p=run('eval',expr); assert p.returncode==0 and not p.stdout and phrase.encode() in p.stderr and p.stderr.endswith(b'\n\n')

def test_compile_pdf_and_alias_and_empty_document():
    with tempfile.TemporaryDirectory() as d:
        f=pathlib.Path(d)/'x.typ'; f.write_text('Hello 世界\n')
        for cmd,name in [('compile','a.pdf'),('c','b.pdf')]:
            out=pathlib.Path(d)/name; p=run(cmd,f,out,cwd=d)
            assert p.returncode==0 and p.stdout==b'' and p.stderr==b'' and out.read_bytes().startswith(b'%PDF-1.7') and len(out.read_bytes())>500
        empty=pathlib.Path(d)/'empty.typ'; empty.write_text('  \n')
        p=run('compile',empty,pathlib.Path(d)/'empty.pdf',cwd=d); assert p.returncode==0 and (pathlib.Path(d)/'empty.pdf').read_bytes().startswith(b'%PDF-')

def test_compile_pdf_standard_and_output_errors():
    with tempfile.TemporaryDirectory() as d:
        src=pathlib.Path(d)/'x.typ'; src.write_text('Hello')
        for standard,header in [('1.4',b'%PDF-1.4'),('1.5',b'%PDF-1.5'),('1.6',b'%PDF-1.6'),('1.7',b'%PDF-1.7'),('2.0',b'%PDF-2.0')]:
            out=pathlib.Path(d)/(standard+'.pdf'); p=run('compile',src,out,'--pdf-standard',standard,cwd=d); assert p.returncode==0 and out.read_bytes().startswith(header)
        p=run('compile','missing.typ',cwd=d); assert p.returncode==1 and not p.stdout and b'input file not found (searched at missing.typ)' in p.stderr
        p=run('compile',src,pathlib.Path(d)/'absent'/'x.pdf',cwd=d); assert p.returncode==1 and not p.stdout and p.stderr==b'error: failed to write PDF file (No such file or directory (os error 2))\n\n'

def test_compile_unknown_extension_and_utf8():
    with tempfile.TemporaryDirectory() as d:
        src=pathlib.Path(d)/'x.typ'; src.write_text('ok')
        p=run('compile',src,pathlib.Path(d)/'out.xyz',cwd=d); assert p.returncode==1 and not p.stdout and b'could not infer output format for path' in p.stderr and b'--format/-f' in p.stderr
        src.write_bytes(b'\xff')
        p=run('compile',src,pathlib.Path(d)/'bad.pdf',cwd=d); assert p.returncode==1 and p.stdout==b'' and p.stderr==b'error: file is not valid UTF-8\n\n'

def test_compile_svg_png_and_template():
    with tempfile.TemporaryDirectory() as d:
        src=pathlib.Path(d)/'x.typ'; src.write_text('Hello World')
        svg=pathlib.Path(d)/'out.svg'; p=run('compile',src,svg,cwd=d)
        data=svg.read_bytes(); assert p.returncode==0 and not p.stderr and data.startswith(b'<svg') and b'http://www.w3.org/2000/svg' in data and b'</svg>' in data and b'<use xlink:href=' in data and len(data)>500
        png=pathlib.Path(d)/'out.png'; p=run('compile',src,png,cwd=d); assert p.returncode==0 and png.read_bytes().startswith(b'\x89PNG\r\n\x1a\n')
        src.write_text('one\n#pagebreak()\ntwo')
        p=run('compile',src,pathlib.Path(d)/'pages-{0p}-of-{t}.png',cwd=d); assert p.returncode==0
        assert len(list(pathlib.Path(d).glob('pages-*-of-*.png'))) >= 2

def test_pages_selection_warning_and_pdf_header():
    with tempfile.TemporaryDirectory() as d:
        src=pathlib.Path(d)/'x.typ'; src.write_text('one\n#pagebreak()\ntwo\n#pagebreak()\nthree')
        out=pathlib.Path(d)/'p.pdf'; p=run('compile',src,out,'--pages','2',cwd=d)
        assert p.returncode==0 and out.read_bytes().startswith(b'%PDF-') and b'using --pages implies --no-pdf-tags' in p.stderr
        p=run('compile',src,pathlib.Path(d)/'z.pdf','--pages','99',cwd=d); assert p.returncode==0
        p=run('compile',src,pathlib.Path(d)/'bad.pdf','--pages','1-0',cwd=d); assert p.returncode!=0 and b'error:' in p.stderr

def test_dependencies_and_timings():
    with tempfile.TemporaryDirectory() as d:
        pathlib.Path(d,'main.typ').write_text('#include "part.typ"')
        pathlib.Path(d,'part.typ').write_text('Hello')
        p=run('compile','main.typ','out.pdf','--deps','deps.json',cwd=d)
        assert p.returncode==0
        dep=json.loads(pathlib.Path(d,'deps.json').read_text()); assert set(dep['inputs'])=={'main.typ','part.typ'} and dep['outputs']==['out.pdf']
        p=run('compile','main.typ','-','--deps','-',cwd=d); assert p.returncode==2 and b'cannot write both output and dependencies to stdout' in p.stderr
        p=run('compile','main.typ','timed.pdf','--timings',cwd=d); assert p.returncode==0
        trace=json.loads(pathlib.Path(d,'record-0.json').read_text()); assert isinstance(trace,list) and any(e.get('ph')=='B' for e in trace) and any(e.get('ph')=='E' for e in trace)

def test_root_and_imports():
    with tempfile.TemporaryDirectory() as d:
        root=pathlib.Path(d); (root/'sub').mkdir(); (root/'main.typ').write_text('#include "sub/part.typ"'); (root/'sub/part.typ').write_text('Hello')
        p=run('compile','main.typ','out.pdf','--root',d,cwd=d); assert p.returncode==0
        p=run('compile','main.typ','out.pdf','--root','/nonexistent/path',cwd=d); assert p.returncode==1 and p.stdout==b'' and p.stderr==b'error: root directory not found (searched at /nonexistent/path)\n'

def test_eval_file_access_blocked():
    with tempfile.TemporaryDirectory() as d:
        pathlib.Path(d,'text.txt').write_text('x')
        for extra in [('--root',d),('--root',d,'--in','context.typ')]:
            p=run('eval','read("text.txt")',*extra,cwd=d); assert p.returncode==0 and p.stdout==b'' and p.stderr==b'error: cannot access file system from here\n\n'

def test_fonts_listing_and_variants():
    p=run('fonts'); assert p.returncode==0 and p.stderr==b''
    names=txt(p.stdout).splitlines(); assert names==sorted(set(names)) and {'DejaVu Sans','DejaVu Sans Mono','DejaVu Serif','Libertinus Serif','New Computer Modern','New Computer Modern Math'} <= set(names)
    p=run('fonts','--ignore-system-fonts'); assert p.returncode==0 and set(txt(p.stdout).splitlines())=={'DejaVu Sans Mono','Libertinus Serif','New Computer Modern','New Computer Modern Math'}
    p=run('fonts','--ignore-embedded-fonts',env={'TYPST_IGNORE_SYSTEM_FONTS':'false'}); assert p.returncode==0 and set(txt(p.stdout).splitlines())=={'DejaVu Sans','DejaVu Sans Mono','DejaVu Serif'}
    p=run('fonts','--variants'); assert p.returncode==0 and 'Style: Normal' in txt(p.stdout) and 'Weight: 400' in txt(p.stdout) and 'Stretch: FontStretch(1000)' in txt(p.stdout)

def test_fonts_empty_env_path_diagnostic():
    p=run('fonts',env={'TYPST_FONT_PATHS':''}); assert p.returncode==2 and p.stdout==b'' and p.stderr==b"error: a value is required for '--font-path <DIR>' but none was supplied\n\nFor more information, try '--help'.\n"

def test_info_json_and_option_scope():
    p=run('info','--format','json'); assert p.returncode==0 and p.stderr==b''
    o=json.loads(p.stdout); assert o['version']=='0.14.2' and o['build']['commit']=='ccc34be79ab2555cd26c519b1eab45a3e9ec757a'
    assert {'build','features','fonts','packages','env'}<=set(o) and {'self-update','http-server'}<=set(o['build']['settings'])
    p=run('info'); assert p.returncode==0 and txt(p.stderr).startswith('Version 0.14.2 (') and all(x in txt(p.stderr) for x in ('Custom font paths','System fonts','Embedded fonts'))
    for flag in ('--font-path','--ignore-system-fonts'):
        p=run('info',flag,'x'); assert p.returncode==2 and txt(p.stderr).startswith("error: unexpected argument '%s' found"%flag)

def test_completions_supported_shells():
    samples={'bash':('_typst()','COMPREPLY=()'),'zsh':('#compdef typst','autoload -U is-at-least','_arguments'),'fish':('__fish_typst_global_optspecs','__fish_typst_needs_command','complete -c typst'),'powershell':("Register-ArgumentCompleter -Native -CommandName 'typst'",'CompletionResult'),'elvish':('use builtin;','fn cand','edit:completion:arg-completer[typst]')}
    for shell,needles in samples.items():
        p=run('completions',shell); s=txt(p.stdout); assert p.returncode==0 and p.stderr==b'' and all(n in s for n in needles)
    p=run('completions','unknown'); assert p.returncode==2 and b'error:' in p.stderr

def test_query_document_results_and_one_cardinality():
    with tempfile.TemporaryDirectory() as d:
        src=pathlib.Path(d)/'x.typ'; src.write_text('= First\n\n== Second')
        p=run('query',src,'heading',cwd=d); assert p.returncode==0 and b'typst query' in p.stderr
        vals=json.loads(p.stdout); assert len(vals)==2 and [v['body']['text'] if isinstance(v.get('body'),dict) else str(v.get('body')) for v in vals]
        p=run('query',src,'heading','--field','level',cwd=d); assert p.returncode==0 and json.loads(p.stdout)==[1,2]
        p=run('query',src,'heading','--field','missing','--one',cwd=d); assert p.returncode==1 and p.stdout==b'' and p.stderr==b'error: expected exactly one element, found 2\n'
        p=run('query',src,'heading','--field','missing','--one',cwd=d); assert b'expected exactly one element, found 2' in p.stderr

def test_query_missing_input_no_deprecation_warning():
    p=run('query','nonexistent.typ','heading'); assert p.returncode==1 and p.stdout==b'' and p.stderr==b'error: input file not found (searched at nonexistent.typ)\n'

def test_init_argument_validation():
    p=run('init','local/template'); assert p.returncode==1 and p.stdout==b'' and p.stderr==b"error: package specification must start with '@'\n"
    p=run('init','@local/template'); assert p.returncode==1 and p.stdout==b'' and p.stderr==b'error: please specify the desired version\n'

def test_html_gate_and_html_rendering():
    with tempfile.TemporaryDirectory() as d:
        src=pathlib.Path(d)/'x.typ'; src.write_text('= Hello World\n\nThis is a simple document with *bold* and _italic_ text.\n\n== Section 2\n\nSome more text here.')
        out=pathlib.Path(d)/'x.html'; p=run('compile',src,out,cwd=d)
        assert p.returncode==1 and not p.stdout and not out.exists() and p.stderr==b'error: html export is only available when `--features html` is passed\n = hint: html export is under active development and incomplete\n = hint: see https://github.com/typst/typst/issues/5512 for more information\n\n'
        p=run('compile',src,out,'--features','html',cwd=d); assert p.returncode==0 and b'html export is under active development and incomplete' in p.stderr
        s=out.read_text(); assert s.startswith('<!DOCTYPE html>\n<html lang="en">') and '<h2>Hello World</h2>' in s and '<strong>bold</strong>' in s and '<em>italic</em>' in s and s.endswith('</html>\n')
