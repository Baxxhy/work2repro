import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

import pytest

EXE = Path('/workspace/executable')


def run(*args, cwd=None, env=None, timeout=30):
    e = os.environ.copy()
    if env:
        e.update(env)
    return subprocess.run([str(EXE), *map(str, args)], cwd=cwd, env=e,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          timeout=timeout)


def project(tmp_path, content=True):
    p = tmp_path / 'project'
    p.mkdir()
    if content:
        (p / 'content').mkdir()
    return p


def build(p, *args, out=None):
    return run(*args, p, *( [out] if out else []))


def test_missing_args_and_unknown_flag():
    r = run()
    assert r.returncode == 2 and r.stdout == b''
    for s in (b'error: the following required arguments were not provided:', b'<INPUT_FOLDER>', b'Usage: executable <INPUT_FOLDER> [OUTPUT_FOLDER]'):
        assert s in r.stderr
    r = run('--shortcodes')
    assert r.returncode == 2 and b'<INPUT_FOLDER>' in r.stderr
    r = run('--definitely-not-a-flag', '/tmp/x')
    assert r.returncode == 2
    assert b"error: unexpected argument '--definitely-not-a-flag' found" in r.stderr


def test_help_version_and_cli_errors():
    r = run('--help', '--bogus')
    assert r.returncode == 0 and not r.stderr
    assert r.stdout.startswith(b'Marmite is the easiest static site generator.\n\nUsage:')
    assert r.stdout.endswith(b'\n') and b'\x1b' not in r.stdout
    assert run('-V').stdout == b'marmite 0.2.7\n'
    assert run('--pagination', 'invalid', '/tmp').returncode == 2
    r = run('/nonexistent/marmite-input')
    assert r.returncode == 1 and not r.stdout
    assert b'Input folder does not exist: "/nonexistent/marmite-input"' in r.stderr


def test_build_default_site_and_metadata(tmp_path):
    p = project(tmp_path)
    r = build(p)
    assert r.returncode == 0 and not r.stdout and not r.stderr
    site = p / 'site'
    for n in ('index.html', '404.html', 'robots.txt', 'marmite.json', 'sitemap.xml', 'urls.json'):
        assert (site / n).is_file()
    assert (site / 'robots.txt').read_text() == 'User-agent: Mediapartners-Google\nDisallow:\n\nUser-agent: *\nAllow: /\n'
    m = json.loads((site / 'marmite.json').read_text())
    assert isinstance(m['timestamp'], int) and isinstance(m['elapsed_time'], (int, float))
    assert m['config']['name'] == 'Home'
    assert (site / 'index.html').read_text().startswith('<!DOCTYPE html>\n<html lang="en">')
    assert 'Welcome to Marmite | Home' in (site / 'index.html').read_text()
    assert 'Page not found | Home' in (site / '404.html').read_text()


def test_build_markdown_hierarchy_frontmatter_and_formats(tmp_path):
    p = project(tmp_path)
    (p/'content'/'nested').mkdir()
    (p/'content'/'nested'/'Deep File.md').write_text('# Nested title\n\n**bold** and *emphasis* `code`\n\n- one\n- two\n\n> quote\n\n---\n\n[link](https://example.test)\n\n```python\nprint(1)\n```')
    (p/'content'/'post.md').write_text('---\ntitle: Only Frontmatter\ndate: 2024-01-01\ntags: [Café, tech]\nauthor: Alice\n---\n')
    (p/'content'/'page.md').write_text('No heading')
    (p/'content'/'_hero.md').write_text('# Fragment')
    r = build(p)
    assert r.returncode == 0
    site = p/'site'
    assert (site/'Deep File.html').exists()
    assert (site/'only-frontmatter.html').exists()
    assert (site/'page.html').exists()
    deep = (site/'Deep File.html').read_text()
    for x in ('<strong>bold</strong>', '<em>emphasis</em>', '<code>code</code>', '<ul>', '<blockquote>', 'language-python', 'href="https://example.test"'):
        assert x in deep
    page = (site/'page.html').read_text()
    assert '<h1>No heading</h1>' in page
    assert (site/'_hero.html').exists() is False
    assert 'Café' in (site/'tag-cafe.html').read_text()


def test_markdown_gfm_html_wikilinks_and_toc(tmp_path):
    p = project(tmp_path)
    (p/'marmite.yaml').write_text('toc: true\n')
    (p/'content'/'first.md').write_text('---\ntitle: First\nslug: first\ndate: 2024-01-15\n---\n# First\n## Nested\n### Deeper\n\n| A | B |\n|---|---|\n| x | y |\n\n~~gone~~\n\n- [ ] todo\n\nFootnote[^1]\n\n[^1]: note\n\n||secret|| :smile:\n\n<div>**literal**</div>\n\n[[second]]')
    (p/'content'/'second.md').write_text('---\ntitle: Second\nslug: second\n---\n# Second')
    assert build(p).returncode == 0
    h = (p/'site'/'first.html').read_text()
    for x in ('<table>', '<del>gone</del>', 'type="checkbox"', 'footnote', 'content-toc', 'Nested', 'Deeper', 'data-wikilink="true"', '<div>**literal**</div>'):
        assert x in h


def test_config_overrides_and_validation(tmp_path):
    p = project(tmp_path)
    (p/'marmite.yaml').write_text('name: From file\nextra:\n  keep: true\n  custom: hello\n')
    r = build(p, '--name', 'CLI Name', '--colorscheme', 'nord', '--pagination', '4')
    assert r.returncode == 0
    c = json.loads((p/'site'/'marmite.json').read_text())['config']
    assert c['name'] == 'CLI Name' and c['pagination'] == 4
    assert c['extra'] == {'colorscheme': 'nord'}
    (p/'marmite.yaml').write_text('pagination: not_a_number\n')
    r = build(p)
    assert r.returncode == 1 and b'Failed to parse config YAML' in r.stderr


def test_root_fallback_and_custom_paths(tmp_path):
    p = project(tmp_path, content=False)
    for d in ('static', 'media', 'templates'):
        (p/d).mkdir()
        (p/d/'not-content.md').write_text('# From '+d)
    r = build(p)
    assert r.returncode == 0
    assert (p/'site'/'not-content.html').exists()
    p2 = tmp_path/'other'; p2.mkdir(); (p2/'articles').mkdir(); (p2/'articles'/'article.md').write_text('# Custom')
    (p2/'marmite.yaml').write_text('content_path: articles\nstatic_path: assets\n')
    assert build(p2).returncode == 0
    assert (p2/'site'/'custom.html').exists()


def test_generate_config_non_destructive_and_overrides(tmp_path):
    p = project(tmp_path)
    r = run('--generate-config', '--tagline', 'My Site', '--toc', 'true', p)
    assert r.returncode == 0 and not r.stdout and b'Config file generated' in r.stderr
    cfg = (p/'marmite.yaml').read_text()
    assert 'name: Home' in cfg and 'tagline: My Site' in cfg and 'pagination: 10' in cfg
    assert 'content_path: content' in cfg and 'toc: true' in cfg and len(cfg) > 100
    before = (p/'marmite.yaml').read_bytes()
    r = run('--generate-config', p)
    assert r.returncode == 0 and (p/'marmite.yaml').read_bytes() == before
    assert b'Config file already exists:' in r.stderr


def test_init_site_and_refuse_nonempty(tmp_path):
    p = tmp_path/'newsite'
    r = run('--init-site', p)
    assert r.returncode == 0 and not r.stdout and b'Site initialized' in r.stderr
    for rel in ('marmite.yaml','content/media','custom.css','custom.js','content/about.md','content/_404.md','content/_hero.md','content/_sidebar.example.md','content/_announce.md','content/_comments.md','content/_markdown_header.md','content/_markdown_footer.md'):
        assert (p/rel).exists()
    assert len(list((p/'content').glob('*-welcome.md'))) == 1
    welcome = next((p/'content').glob('*-welcome.md')).read_text()
    for phrase in ('# Welcome to Marmite','Edit this content','Add more content','Customize your site'):
        assert phrase in welcome
    q = tmp_path/'notempty'; q.mkdir(); (q/'keep').write_text('x')
    r = run('--init-site', q)
    assert r.returncode == 1 and b'Input folder is not empty' in r.stderr and (q/'keep').read_text() == 'x'


def test_new_post_slug_tags_page_and_editor(tmp_path):
    p = project(tmp_path)
    (p/'marmite.yaml').write_text('content_path: articles\n')
    r = run('--new', 'Hello World! Testing: Marmite & Café', '-t', 'a,b', p)
    assert r.returncode == 0
    paths = r.stdout.decode().splitlines()
    assert len(paths) == 1 and Path(paths[0]).is_absolute()
    f = Path(paths[0]); assert f.parent == p and re.match(r'\d{4}-\d\d-\d\d-\d\d-\d\d-\d\d-hello-world-testing-marmite-cafe.md', f.name)
    text = f.read_text(); assert '# Hello World! Testing: Marmite & Café' in text and 'tags: a,b' in text
    r = run('--new', 'A Page', '-p', '-t', 'x,y', p)
    assert r.returncode == 0 and Path(r.stdout.decode().strip()).name == 'a-page.md'
    assert not (p/'articles').exists()
    editor = tmp_path/'editor'; editor.write_text('#!/bin/sh\nprintf edited >> "$1"\nprintf "%s" "$1" > "$EDIT_LOG"\n'); editor.chmod(0o755)
    r = run('--new', 'Edit Me', '-e', p, env={'EDITOR':str(editor),'EDIT_LOG':str(tmp_path/'log')})
    assert r.returncode == 0 and Path((tmp_path/'log').read_text()).exists()


def test_init_templates_and_theme_scaffolding(tmp_path):
    p = project(tmp_path)
    (p/'marmite.yaml').write_text('templates_path: layouts\n')
    r = run('--init-templates', p)
    assert r.returncode == 0
    td = p/'templates'
    required = ('base.html','content.html','list.html','group.html','pagination.html','sitemap.xml','base_feeds.html','content_title.html','content_date.html','content_authors.html','comments.html','json_ld_content.html','custom_index.html.example')
    for n in required:
        assert (td/n).stat().st_size > 100
    assert not (p/'templates'/'custom_index.html').exists()
    assert len([x for x in td.rglob('*') if x.is_file()]) > 10
    before = (td/'base.html').read_bytes()
    r = run('--init-templates', p)
    assert r.returncode == 0 and (td/'base.html').read_bytes() == before
    theme = run('--start-theme', 'demo', p)
    assert theme.returncode == 0 and b"Theme 'demo' created successfully" in theme.stderr
    t = p/'demo'
    assert (t/'theme.json').is_file() and (t/'README.md').stat().st_size > 100
    meta = json.loads((t/'theme.json').read_text())
    assert all(isinstance(meta[k], str) for k in ('name','version','marmite_version','author','description')) and meta['features']
    for n in ('style.css','script.js','custom.css','custom.js','favicon.ico','robots.txt'):
        assert (t/'static'/n).exists()
    schemes = list((t/'static'/'colorschemes').glob('*.css'))
    assert len(schemes) >= 10
    for n in ('nord','dracula','gruvbox','solarized'):
        assert (t/'static'/'colorschemes'/f'{n}.css').stat().st_size > 0


def test_set_theme_local_validation(tmp_path):
    p = project(tmp_path)
    theme = tmp_path/'my-theme'; theme.mkdir()
    (theme/'theme.json').write_text(json.dumps({'name':'M','version':'1','author':'A','description':'D','features':['fast'],'tags':['dark']}))
    (p/'marmite.yaml').write_text('name: Keep\n')
    r = run('--set-theme', theme, p)
    assert r.returncode == 0 and f"Theme '{theme}' has been successfully set".encode() in r.stdout
    assert 'Features:' in r.stdout.decode() and 'Tags:' in r.stdout.decode()
    assert f'theme: {theme}' in (p/'marmite.yaml').read_text()
    r = run('--set-theme', tmp_path/'missing-theme', p)
    assert r.returncode == 0 and b'Theme folder does not exist:' in r.stderr


def test_shortcodes_report_and_transform(tmp_path):
    p = project(tmp_path)
    r = run('--shortcodes', p)
    assert r.returncode == 0
    for s in ('Shortcodes:','Enabled: true','Pattern:','Available shortcodes:','Examples based on your configuration:','  - tags: Display a list of all tags with post counts. Params: ord=desc, items=0'):
        assert s in r.stdout.decode()
    (p/'content'/'video.md').write_text('<!-- .youtube id="abc" width=400 -->')
    assert build(p).returncode == 0
    h = (p/'site'/'video.html').read_text()
    assert 'youtube.com/embed/abc' in h and 'width="400"' in h
    (p/'marmite.yaml').write_text('enable_shortcodes: false\n')
    assert build(p, out=p/'site2').returncode == 0
    assert '<!-- .youtube id="abc" width=400 -->' in (p/'site2'/'video.html').read_text()


def test_posts_streams_tags_authors_series_and_feeds(tmp_path):
    p = project(tmp_path)
    (p/'marmite.yaml').write_text('url: https://example.test\njson_feed: true\nauthors:\n  alice:\n    name: Alice\n    links:\n      - [Website, https://alice.test]\nstreams:\n  dev:\n    display_name: Development\nseries:\n  guide:\n    display_name: The Guide\n    description: Guide description\n')
    (p/'content'/'2024-01-15-first.md').write_text('---\ntitle: First\ndate: 2024-01-15\nstream: dev\ntags: [rust, tech]\nauthors: [alice, bob]\nseries: guide\ndescription: First summary\n---\nMultiple authors on this post.')
    (p/'content'/'2024-01-10-second.md').write_text('---\ntitle: Second\ndate: 2024-01-10\ntags: tech\nauthor: alice\n---\nSecond body')
    (p/'content'/'page.md').write_text('# Page')
    assert build(p).returncode == 0
    s = p/'site'
    for n in ('streams.html','dev.html','series.html','series-guide.html','authors.html','author-alice.html','tags.html','tag-tech.html','tag-rust.html','index.rss','dev.rss','tag-rust.rss','series-guide.rss','archive-2024.rss','index.json','dev.json','tag-tech.json','archive-2024.json'):
        assert (s/n).exists(), n
    rss = (s/'index.rss').read_text(); assert 'First' not in rss and rss.index('Second') < len(rss)
    assert '<source url="https://example.test">author-alice</source>' in (s/'author-alice.rss').read_text()
    assert 'The Guide' in (s/'series-guide.html').read_text() and 'Guide description' not in (s/'series-guide.html').read_text()
    feed = json.loads((s/'index.json').read_text())
    assert [x['title'] for x in feed['items']] == ['Second']
    item = json.loads((s/'dev.json').read_text())['items'][0]
    assert item['authors'][0]['name'] == 'Alice' and item['content_html'] == '<p>Multiple authors on this post.</p>\n'


def test_output_mapping_urls_and_force_timestamp(tmp_path):
    p = project(tmp_path)
    (p/'content'/'nested').mkdir()
    (p/'content'/'nested'/'2024-02-01-a.md').write_text('---\ntitle: A\ntags: [x]\n---\nBody')
    (p/'README.md').write_text('# Readme')
    (p/'marmite.yaml').write_text('file_mapping:\n  - source: README.md\n    dest: about.html\n')
    out = tmp_path/'custom-out'
    assert build(p, out=out).returncode == 0
    assert (out/'a.html').exists() and (out/'about.html').exists()
    urls = json.loads((out/'urls.json').read_text())
    assert all(k in urls for k in ('posts','pages','tags','authors','streams','series','feeds','summary'))
    first = json.loads((out/'marmite.json').read_text())['timestamp']
    time.sleep(1.05)
    assert build(p, '--force', out=out).returncode == 0
    second = json.loads((out/'marmite.json').read_text())['timestamp']
    assert second > first
    r = run('--show-urls', p)
    assert r.returncode == 0
    assert 'index' in (r.stdout.decode() + r.stderr.decode())


def test_template_precedence_theme_and_url_helpers(tmp_path):
    p = project(tmp_path)
    theme = p/'theme'; (theme/'templates').mkdir(parents=True)
    (theme/'theme.json').write_text('{}')
    (theme/'templates'/'content.html').write_text('THEME {{ content.title }}')
    (theme/'templates'/'list.html').write_text('THEME LIST')
    (p/'templates').mkdir(); (p/'templates'/'content.html').write_text('PROJECT')
    (p/'content'/'page.md').write_text('# Page')
    (p/'marmite.yaml').write_text('theme: theme\nurl: https://example.com/blog/\n')
    assert build(p, '--colorscheme', 'nord').returncode == 0
    assert (p/'site'/'page.html').read_text() == 'THEME Page'
    assert (p/'site'/'index.html').read_text() == 'THEME LIST'


def test_malformed_content_and_invalid_date(tmp_path):
    p = project(tmp_path)
    (p/'content'/'bad.md').write_text('---\ntitle: [unclosed\n---\nbody')
    (p/'content'/'good.md').write_text('# Good')
    r = build(p)
    assert r.returncode == 0 and b'Failed to process content' in r.stderr and (p/'site'/'good.html').exists()
    (p/'content'/'bad.md').unlink()
    (p/'content'/'date.md').write_text('---\ndate: not-a-valid-date-at-all\n---\nbody')
    r = build(p, out=p/'badout')
    assert r.returncode == 1 and b'Invalid date format' in r.stderr


def test_duplicate_slugs_fragments_and_symlink(tmp_path):
    p = project(tmp_path)
    (p/'content'/'one.md').write_text('---\nslug: same\n---\n# One')
    (p/'content'/'two.md').write_text('---\nslug: same\n---\n# Two')
    (p/'content'/'_part.md').write_text('# Part')
    (p/'content'/'deep').mkdir()
    target = p/'content'/'target.md'; target.write_text('# Linked Page')
    (p/'content'/'deep'/'link.md').symlink_to(target)
    r = build(p)
    assert r.returncode == 0 and b'Duplicate slug found' in r.stderr
    assert (p/'site'/'same.html').exists() and (p/'site'/'link.html').exists()
    assert not (p/'site'/'part.html').exists()


def test_gallery_config_and_shortcode(tmp_path):
    p = project(tmp_path)
    media = p/'content'/'media'/'gallery'/'demo'; media.mkdir(parents=True)
    # Tiny valid PNG fixture.
    import base64
    png = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/lN8AAAAASUVORK5CYII=')
    (media/'A.png').write_bytes(png); (media/'b.txt').write_text('ignore')
    (media/'gallery.yaml').write_text('name: Pictures\nord: desc\ncover: A.png\nimages:\n  - filename: "*.png"\n    description: "<b>Pic</b>"\n')
    (p/'content'/'gallery.md').write_text('<!-- .gallery path=demo -->')
    r = build(p)
    assert r.returncode == 0
    h = (p/'site'/'gallery.html').read_text()
    assert 'shortcode-gallery' in h and 'gallery-demo-main-image' in h and 'A.png' in h


def test_custom_template_functions_and_theme_errors(tmp_path):
    p = project(tmp_path)
    (p/'templates').mkdir()
    (p/'templates'/'list.html').write_text('{{ site.name }} {{ url_for(path="./x") }} {{ get_posts() | length }}')
    (p/'content'/'2024-01-01-post.md').write_text('# Post')
    assert build(p).returncode == 0
    assert 'Home /x 1' in (p/'site'/'index.html').read_text()
    (p/'marmite.yaml').write_text('theme: absent\n')
    r = build(p, out=p/'missingthemeout')
    assert r.returncode == 1 and b'Theme folder' in r.stderr


def test_shortcodes_and_published_urls_toggle(tmp_path):
    p = project(tmp_path)
    (p/'marmite.yaml').write_text('json_feed: false\nbuild_sitemap: false\npublish_urls_json: false\n')
    (p/'content'/'x.md').write_text('---\ntitle: X\ndate: 2024-01-01\n---\nX')
    assert build(p).returncode == 0
    for n in ('sitemap.xml','urls.json','index.json'):
        assert not (p/'site'/n).exists()
    (p/'marmite.yaml').write_text('publish_md: true\nsource_repository: https://github.com/u/r/blob/main/content/\n')
    assert build(p, out=p/'site2').returncode == 0
    assert (p/'site2'/'x.md').exists()


@pytest.mark.parametrize('flag,value,expected', [
    ('--https','true',True),('--enable-search','true',True),('--enable-related-content','false',False),
    ('--toc','true',True),('--json-feed','true',True),('--show-next-prev-links','false',False),
    ('--publish-md','true',True),('--build-sitemap','false',False),('--publish-urls-json','false',False),
    ('--enable-shortcodes','false',False),('--skip-image-resize','true',True),
], ids=['https','search','related','toc','json','nextprev','publish-md','sitemap','urls-json','shortcodes','resize'])
def test_boolean_overrides(tmp_path, flag, value, expected):
    p = project(tmp_path)
    r = build(p, flag, value)
    assert r.returncode == 0
    c = json.loads((p/'site'/'marmite.json').read_text())['config']
    key = flag[2:].replace('-', '_')
    assert c[key] is expected


def test_rss_json_feed_protocol_and_limits(tmp_path):
    p = project(tmp_path)
    (p/'marmite.yaml').write_text('url: example.com/blog/\nhttps: true\n')
    for i in range(17):
        (p/'content'/f'2024-01-{i+1:02}-p{i}.md').write_text(f'---\ntitle: P{i}\n---\nBody')
    assert build(p).returncode == 0
    rss = (p/'site'/'index.rss').read_text()
    feed = json.loads((p/'site'/'index.json').read_text())
    assert rss.startswith('<?xml') and rss.count('<item>') == 15
    assert len(feed['items']) == 15
    assert feed['home_page_url'] == 'example.com/blog/'
    assert feed['feed_url'] == 'example.com/blog//index.json'


def test_init_template_existing_file_and_invalid_theme_name(tmp_path):
    p = project(tmp_path)
    (p/'templates').write_text('preserve')
    r = run('--init-templates', p)
    assert r.returncode == 0 and (p/'templates').read_text() == 'preserve'
    r = run('--start-theme', '../bad', p)
    assert r.returncode == 0 and b"Invalid theme name: '../bad'" in r.stderr
    assert not (tmp_path/'bad').exists()


def test_theme_and_template_rendering_from_scaffold(tmp_path):
    p = project(tmp_path)
    assert run('--start-theme','starter',p).returncode == 0
    (p/'content'/'page.md').write_text('# Theme page')
    r = build(p, '--theme','starter')
    assert r.returncode == 0
    assert '<!DOCTYPE html>' in (p/'site'/'page.html').read_text()


def test_static_media_copy_and_file_output_errors(tmp_path):
    p = project(tmp_path)
    (p/'static').mkdir(); (p/'static'/'a.txt').write_text('static-data')
    (p/'content'/'x.md').write_text('# X')
    assert build(p).returncode == 0
    assert (p/'site'/'static'/'a.txt').read_text() == 'static-data'
    file = tmp_path/'notdir'; file.write_text('x')
    r = run(p, file)
    assert r.returncode == 1 and b'Unable to create output directory' in r.stderr and b'NotADirectory' in r.stderr


def test_no_panic_many_nested_files_and_source_preserved(tmp_path):
    p = project(tmp_path)
    for i in range(125):
        d = p/'content'/f'd{i%9}'/f'sub{i%4}'; d.mkdir(parents=True, exist_ok=True)
        (d/f'{i}.md').write_text(f'# Page {i}\n\nUnicode Ω 😀')
    original = (p/'content'/'d0'/'sub0'/'0.md').read_bytes()
    r = build(p, timeout=30)
    assert r.returncode == 0 and (p/'site'/'124.html').exists()
    assert (p/'content'/'d0'/'sub0'/'0.md').read_bytes() == original
