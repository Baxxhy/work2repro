import json, os, pathlib, subprocess
import pytest

EXE = pathlib.Path('/workspace/executable')

def run(args=(), data=None, cwd=None, env=None):
    e=os.environ.copy()
    if env:
        e.update(env)
    return subprocess.run([str(EXE), *map(str,args)], input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd, env=e)

def out(args=(), data=None, **kw):
    p=run(args,data,**kw)
    assert p.returncode == 0, (p.returncode,p.stderr)
    assert p.stderr == b''
    return p.stdout.decode()


def test_version_forms():
    for flag in ('--version','-V'):
        p=run([flag]); assert p.returncode==0 and p.stdout==b'lightningcss 1.0.0-alpha.70\n' and p.stderr==b''

def test_help_and_invalid_order():
    for flag in ('--help','-h'):
        p=run([flag]); assert p.returncode==0 and b'USAGE:' in p.stdout and p.stdout.endswith(b'\n') and not p.stderr
        p=run([flag,'--definitely-invalid']); assert p.returncode==0 and b'USAGE:' in p.stdout
        p=run(['--definitely-invalid',flag]); assert p.returncode==2 and p.stdout==b'' and b'--definitely-invalid' in p.stderr and b'USAGE:' in p.stderr and b'--help' in p.stderr

def test_unknown_and_missing_arguments():
    p=run(['--wat']); assert p.returncode!=0 and p.stdout==b'' and b"Found argument '--wat'" in p.stderr and b'-- FLAG' in p.stderr
    for args, phrase in [(['-o'],'--output-file'),(['-d'],'--output-dir'),(['-t'],'--targets'),(['--css-modules-pattern'],'--css-modules-pattern')]:
        p=run(args); assert p.returncode!=0 and p.stdout==b'' and phrase.encode() in p.stderr and b'requires a value' in p.stderr and b'--help' in p.stderr

def test_option_terminator_and_interspersed_inputs(tmp_path):
    f=tmp_path/'x.css'; f.write_text('a{color:red}')
    assert 'color: red;' in out([str(f),'--minify'])
    p=run(['--','--odd.css'],cwd=tmp_path); assert p.returncode!=0 and b'No such file' in p.stderr

def test_targets_mutually_exclusive():
    p=run(['--targets','chrome 100','--browserslist']); assert p.returncode!=0 and b'--targets' in p.stderr and b'--browserslist' in p.stderr and b'together' in p.stderr

def test_stdin_file_equivalence_and_layout(tmp_path):
    css='a { color: red; }'
    assert out(data=css)== 'a {\n  color: red;\n}\n\n'
    f=tmp_path/'a.css'; f.write_text(css)
    assert out([f]) == out(data=css)

def test_empty_whitespace_and_bom():
    assert out(data='')=='\n\n'
    assert out(data='  \n\t')=='\n\n'
    assert out(data=b'\xef\xbb\xbf.test { color: red; }').startswith('\ufeff.test {')

def test_invalid_utf8_and_missing_file(tmp_path):
    p=run(data=b'\xff'); assert p.returncode!=0 and b'valid UTF-8' in p.stderr
    p=run([tmp_path/'absent.css']); assert p.returncode==1 and b'NotFound' in p.stderr

def test_output_file_creates_parent_and_no_stdout(tmp_path):
    dest=tmp_path/'missing'/'out.css'
    p=run(['-o',dest],data='a { color: red; }')
    assert p.returncode==0 and p.stdout==b'' and p.stderr==b''
    assert dest.read_text()=='a {\n  color: red;\n}\n'
    p=run(['-o',dest,'-m'],data='a { color: red; }'); assert p.returncode==0 and dest.read_text()=='a{color:red}'

def test_multiple_input_requires_dir_and_rejects_output_file(tmp_path):
    a=tmp_path/'a.css'; b=tmp_path/'b.css'; a.write_text('a{}'); b.write_text('b{}')
    p=run([a,b]); assert p.returncode!=0 and b'Cannot output to stdout with multiple inputs' in p.stderr
    p=run(['-o',tmp_path/'x.css',a,b]); assert p.returncode!=0 and b'Cannot use the --output-file' in p.stderr

def test_output_directory_flatten_and_overwrite(tmp_path):
    src=tmp_path/'src'; src.mkdir(); (src/'a.css').write_text('a{}')
    d=tmp_path/'new'
    p=run(['-d',d,src/'a.css']); assert p.returncode==0 and not p.stdout and (d/'a.css').read_text()=='a {\n}\n'

def test_pretty_canonical_values_and_comments():
    s=out(data='/*x*/ @charset "utf-8"; .button { color: white; margin: 0px 0px 0px 0px; }')
    assert '/*x*/' not in s and '@charset' not in s and 'color: #fff;' in s and 'margin: 0;' in s

def test_minify_exact_and_stability():
    css='a { color: red; margin: 0px 0px 0px 0px; }'
    got=out(['-m'],css); assert got=='a{color:red;margin:0}\n'
    assert out(['-m'],got.rstrip('\n'))==got

def test_minify_calc_custom_property_spacing():
    s=out(['--minify'],'a{--spacing:20px;padding:calc(var(--spacing) / 2)}')
    assert 'padding:calc(var(--spacing) / 2)' in s

def test_override_and_unknown_barrier():
    s=out(data='a{color:red;color:blue;color:green;background:yellow;background:orange}')
    assert s.count('color:')==1 and 'color: green;' in s and 'background: orange;' in s
    s=out(data='a{color:red;invalid-property:value;background:blue}')
    assert s.index('color:')<s.index('invalid-property:')<s.index('background:')

def test_unicode_unknown_custom_and_important():
    s=out(data='é\u00a0.foo{--x:"✓"; color:revert-layer; width:-0px!important}')
    assert '✓' in s and '--x:' in s and 'revert-layer' in s and '!important' in s

def test_numeric_and_color_canonicalization():
    s=out(data='a{padding:1.666667%;height:123456.789em;margin:1e6px;flex-grow:123456.789;color:#ff0000}')
    for x in ('1.66667%','123457em','1000000px','flex-grow: 123457','color: red'):
        assert x in s

def test_modern_color_and_urls():
    s=out(data="a{color:rgb(255, 0, 0);background:url(./x.png)}")
    assert 'color: red;' in s and 'url("./x.png")' in s

def test_selector_and_at_rule_normalization():
    s=out(data='@media (min-width: 10px){a,b > .x:nth-child(2n + 1){color:blue}}')
    assert '@media (width >= 10px)' in s and '2n+1' in s and '#00f' in s

def test_invalid_css_is_fatal():
    p=run(data='a{color red;}'); assert p.returncode!=0

def test_error_recovery_exact():
    p=run(['--error-recovery'], 'a{color:red; broken; margin:1px} a, {x:y} b{color:blue}')
    assert p.returncode==0 and p.stdout.decode()=='a {\n  margin: 1px;\n}\n\nb {\n  color: #00f;\n}\n\n'
    assert b'Unexpected end of input' in p.stderr and b'Invalid empty selector' in p.stderr

def test_nesting_retained_and_minified():
    s=out(data='.foo{& .child{color:red}}')
    assert '& .child' in s

def test_flex_grid_order_and_shorthand():
    s=out(['-m'],'.box{display:flex;gap:1rem}')
    assert s==' .box{gap:1rem;display:flex}\n'.lstrip()

def test_animation_and_transform_serialization():
    s=out(data='a{transform:translateX(10px) rotate(45deg) scale(1.5);transition-timing-function:steps(5)}')
    assert 'translateX(10px)rotate(45deg)scale(1.5)' in s and 'steps(5, end)' in s

def test_custom_media_and_media_empty():
    s=out(data='@media{.x{color:red}}')
    assert '@media not all {' in s

def test_targets_accept_queries_and_bad_target_panics():
    p=run(['--targets','> 0.5%, last 2 versions'],data='a{color:red}'); assert p.returncode==0
    p=run(['--targets','abc'],data='a{}'); assert p.returncode==-6 and b'Nom("")' in p.stderr

def test_old_target_prefix_behavior():
    s=out(['--targets','firefox 68'],'a{user-select:none}')
    assert '-moz-user-select: none;' in s and 'user-select: none;' in s
    s=out(['--targets','firefox 69'],'a{user-select:none}')
    assert '-moz-user-select' not in s

def test_css_modules_json_and_pattern(tmp_path):
    f=tmp_path/'test.css'; f.write_text('.foo{color:red}')
    p=run([str(f),'--css-modules']); assert p.returncode==0
    doc=json.loads(p.stdout); assert set(doc)=={'code','exports'} and doc['exports']['foo']['name']=='EgL3uq_foo' and '.EgL3uq_foo' in doc['code']
    p=run([str(f),'--css-modules','--css-modules-pattern','[name]-[hash]-[local]'])
    d=json.loads(p.stdout); assert '.test-EgL3uq-foo' in d['code']

def test_css_modules_file_outputs_and_dashed_ident(tmp_path):
    src=tmp_path/'a.css'; src.write_text('.x{--foo:1;color:var(--foo)}')
    dest=tmp_path/'out.css'; p=run(['--css-modules','--css-modules-dashed-idents','-o',dest,src])
    assert p.returncode==0 and p.stdout==b'' and dest.exists() and dest.with_suffix('.json').exists()

def test_bundle_import_order_and_url_preservation(tmp_path):
    (tmp_path/'dep.css').write_text('.dep{background:url(../img.png)}')
    (tmp_path/'main.css').write_text('@import "dep.css"; .main{color:red}')
    s=out(['--bundle',tmp_path/'main.css'])
    assert '.dep {' in s and '.main {' in s and s.index('.dep')<s.index('.main') and '../img.png' in s

def test_sourcemap_requires_destination():
    p=run(['--sourcemap'],data='a{}'); assert p.returncode!=0 and b'OUTPUT_FILE' in p.stderr and b'OUTPUT_DIR' in p.stderr

def test_sourcemap_file_is_valid_json(tmp_path):
    dest=tmp_path/'out.css'; p=run(['--sourcemap','-o',dest],data='a{color:red}')
    assert p.returncode==0 and dest.exists() and pathlib.Path(str(dest)+'.map').exists()
    m=json.loads(pathlib.Path(str(dest)+'.map').read_text()); assert m['version']==3 and isinstance(m['mappings'],str) and m['sources'] and len(m['sources'])==len(m['sourcesContent'])

def test_stress_many_rules_long_selector_unicode(tmp_path):
    css=''.join(f'.x{i}{{--v:{i};color:red}}' for i in range(520))
    p=run(['-m'],css); assert p.returncode==0 and p.stdout.count(b'{')==520
    longsel=','.join('.s'+str(i) for i in range(1000))
    p=run([],longsel+'{content:"✓"}'); assert p.returncode==0 and '✓' in p.stdout.decode()
