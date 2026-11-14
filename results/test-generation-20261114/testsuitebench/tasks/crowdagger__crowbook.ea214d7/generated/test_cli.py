import os
import subprocess
from pathlib import Path

EXE = Path('/workspace/executable')

def run(*args, cwd=None, input=None, env=None):
    return subprocess.run([str(EXE), *map(str,args)], cwd=cwd, input=input, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, timeout=15)

def book(tmp, text, name='test.book'):
    p=tmp/name
    p.write_text(text, encoding='utf-8')
    return p

def chapter(tmp, text, name='ch.md'):
    p=tmp/name
    p.write_text(text, encoding='utf-8')
    return p

def test_version_exact():
    r=run('--version')
    assert (r.returncode,r.stdout,r.stderr)==(0,b'crowbook 0.17.0\n',b'')

def test_help_stdout_only():
    r=run('--help')
    assert r.returncode==0 and r.stderr==b''
    assert b'USAGE:\n    executable [OPTIONS] [BOOK]' in r.stdout
    assert r.stdout.endswith(b'\n') and b'--print-template' in r.stdout

def test_help_short_circuits_later_unknown():
    assert run('--help','--bad-option').returncode==0

def test_unknown_before_help_is_parse_error():
    r=run('--bad-option','--help')
    assert r.returncode==2 and b"unexpected argument '--bad-option' found" in r.stderr and b'Usage: executable' in r.stderr

def test_no_book_exact_diagnostic():
    r=run()
    assert r.returncode==0 and r.stdout==b''
    assert r.stderr==b'CROWBOOK 0.17.0\nERROR You must pass the name of a book configuration file.\nFor more information try --help.\n\n'

def test_output_requires_format_including_short_equals():
    for arg in ('--output=x.html','-o=x.html'):
        r=run(arg)
        assert r.returncode==2 and b'the following required arguments were not provided:' in r.stderr and b'--to <to>' in r.stderr

def test_invalid_to_lists_formats():
    r=run('--to','bad')
    assert r.returncode==2 and b"invalid value 'bad' for '--to <to>'" in r.stderr
    assert b'[possible values: epub, pdf, html, tex, odt, html.dir]' in r.stderr

def test_quiet_verbose_conflict():
    r=run('--quiet','--verbose')
    assert r.returncode==2 and b"'--quiet' cannot be used with '--verbose'" in r.stderr

def test_missing_book_and_flag_filename_after_double_dash(tmp_path):
    for name,args in [('absent.book',('absent.book',)),('--strange',('--','--strange'))]:
        r=run(*args,cwd=tmp_path)
        assert r.returncode==0 and f"Could not find file '{name}' for book".encode() in r.stderr

def test_single_html_semantic_rendering(tmp_path):
    md=chapter(tmp_path, '# Hello\n\nA **bold** and *em* item.\n\n- one\n- two\n')
    out=tmp_path/'out.html'
    r=run('--single',md,'--to','html','--output',out,'--quiet')
    assert r.returncode==0 and out.exists()
    data=out.read_text()
    assert data.startswith('<!DOCTYPE html>') and data.endswith('</html>')
    assert '<h1' in data and '<b>bold</b>' in data and '<em>em</em>' in data
    assert '<ul>' in data and '<li>' in data and 'id="chapter-0"' in data

def test_single_html_escapes_text_and_hard_break(tmp_path):
    md=chapter(tmp_path, 'Fish & chips  \nnext <tag>\n')
    out=tmp_path/'x.html'
    run('--single',md,'-t','html','-o',out,'-q')
    d=out.read_text()
    assert 'Fish &amp; chips<br />' in d and '&lt;tag&gt;' in d

def test_html_output_stdout_when_dash_and_no_file_dash(tmp_path):
    md=chapter(tmp_path,'# Stdout\n')
    r=run('--single',md,'-t','html','-o','-','-q',cwd=tmp_path)
    assert r.returncode==0 and r.stdout.startswith(b'<!DOCTYPE html>')
    assert not (tmp_path/'-').exists()

def test_config_paths_relative_to_config(tmp_path):
    sub=tmp_path/'nested'; sub.mkdir()
    chapter(sub,'# From config\n','ch.md')
    p=book(sub,'title: Config\noutput.html: result.html\n+ ch.md\n')
    r=run(p,'-q',cwd=tmp_path)
    assert r.returncode==0 and (sub/'result.html').exists()
    assert 'From config' in (sub/'result.html').read_text()

def test_config_only_chapter_declarations_rejected(tmp_path):
    chapter(tmp_path,'# no\n')
    p=book(tmp_path,'+ ch.md\n')
    r=run(p)
    assert r.returncode==0 and b'Error parsing configuration file' in r.stderr and b'--single' in r.stderr

def test_stdin_config_requires_option_before_chapter(tmp_path):
    chapter(tmp_path,'# stdin chapter\n')
    bad=run('-',input=b'+ stdin-chapter.md\n',cwd=tmp_path)
    good=run('-',input=b'title: T\n+ stdin-chapter.md\n',cwd=tmp_path)
    assert bad.returncode==0 and b'Error parsing configuration file' in bad.stderr
    assert good.returncode==0 and b'<!DOCTYPE html>' in good.stdout

def test_single_stdin_frontmatter_and_multiple_headings_one_wrapper():
    r=run('--single','-','-t','html','-q',input=b'---\ntitle: Metadata title\n---\n# One\n\n# Two\n')
    d=r.stdout.decode()
    assert 'Metadata title' in d and 'id="chapter-0"' in d and 'chapter-1' not in d
    assert '<h1' in d and 'One' in d and 'Two' in d

def test_create_set_exact_content(tmp_path):
    r=run('--set','author','Exact Author','title','Exact Title','--create','a.md','missing.md','odd.book',cwd=tmp_path)
    assert r.returncode==0
    assert r.stdout==b'author: Exact Author\ntitle: Exact Title\n\n## List of chapters\n+ a.md\n+ missing.md\n+ odd.book\n'

def test_create_preserves_order_and_paths(tmp_path):
    r=run('--create','missing.md','odd.book','-q',cwd=tmp_path)
    assert r.returncode==0 and b'+ missing.md\n+ odd.book\n' in r.stdout

def test_set_unknown_key_is_operational_error(tmp_path):
    c=chapter(tmp_path,'# Ch\n'); p=book(tmp_path,'title: T\n\n+ ch.md\n')
    r=run(p,'--set','unrecognized','x')
    assert r.returncode==0 and b"unrecognized key 'unrecognized'" in r.stderr

def test_single_tex_article_headings(tmp_path):
    md=chapter(tmp_path,'# First\n\n# Second\n')
    r=run('--single',md,'-t','tex','-q')
    d=r.stdout.decode()
    assert r.returncode==0 and '\\documentclass{article}' in d
    assert '\\section{First}' in d and '\\section{Second}' in d and '\\chapter{' not in d

def test_epub_is_zip_and_has_required_entries(tmp_path):
    md=chapter(tmp_path,'# EPUB title\n\nText.\n')
    out=tmp_path/'x.epub'
    r=run('--single',md,'-t','epub','-o',out,'-q')
    assert r.returncode==0 and out.exists()
    import zipfile
    with zipfile.ZipFile(out) as z:
        assert z.namelist()[0]=='mimetype'
        assert z.read('mimetype')==b'application/epub+zip'
        names=z.namelist()
        assert any(n.endswith('.opf') for n in names) and any(n.endswith('toc.ncx') for n in names)

def test_stats_counts_unicode_and_has_total(tmp_path):
    md=chapter(tmp_path,'# H\n\nabc dé [link](https://x) `z` ![ignored](pic.png)\n')
    r=run('--single',md,'--stats','--quiet')
    assert r.returncode==0 and b'Chars/Word' in r.stdout and b'15' in r.stdout and b'4' in r.stdout and b'TOTAL:' in r.stdout

def test_list_options_catalog_shape():
    r=run('--list-options','-q')
    assert r.returncode==0 and len(r.stdout)>5000 and len(r.stdout.splitlines())>100
    for key in (b'METADATA',b'OUTPUT OPTIONS',b'RENDERING OPTIONS',b'HTML OPTIONS',b'EPUB OPTIONS',b'LATEX OPTIONS',b'proofread.repetitions'):
        if key==b'proofread.repetitions': assert key not in r.stdout
        else: assert key in r.stdout

def test_print_template_precedes_render_flags(tmp_path):
    r=run('--print-template','epub.css','-t','html','-o',tmp_path/'saved.css')
    assert r.returncode==0 and b'body {' in r.stdout and b'{{additional_code}}' in r.stdout
    assert not (tmp_path/'saved.css').exists()

def test_invalid_template_diagnostic():
    r=run('--print-template','bogus')
    assert r.returncode==0 and r.stdout==b'' and b'ERROR bogus is not a valid template name' in r.stderr

def test_odt_is_accepted_but_runtime_unknown(tmp_path):
    md=chapter(tmp_path,'# X\n')
    r=run('--single',md,'-t','odt','-q')
    assert r.returncode==0 and r.stdout==b'' and b'ERROR unknown format odt' in r.stderr
