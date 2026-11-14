import pytest
from conftest import invoke


@pytest.mark.parametrize("html,want", [
    ("<p>   Leading   spaces   here </p>", "Leading spaces here\n"),
    ("<p>Line with\n newline</p>", "Line with newline\n"),
    ("<p>One</p><p>Two</p>", "One\n\nTwo\n"),
    ("<p><span>A</span><span>B</span></p>", "AB\n"),
    ("<h2>Line One<br>Line Two</h2>", "## Line One Line Two\n"),
    ("<h2>Section 2.3#</h2>", "## Section 2.3\\#\n"),
    ("<h1>Section 1.2##</h1>", "# Section 1.2#\\#\n"),
    ("<h2>Already\\#</h2>", "## Already\\\\#\n"),
    ("<h3>The <code>main()</code> <em>function</em> and <strong>setup</strong></h3>", "### The `main()` *function* and **setup**\n"),
    ("<dl><dt>Term</dt><dd>Definition</dd></dl>", "Term\n\nDefinition\n"),
    ("<summary>A</summary><summary>B</summary>", "AB\n"),
    ("<hr>", "* * *\n"),
    ("Before<br>After", "Before  \nAfter\n"),
    ("Before<br><br><br>After", "Before\n\nAfter\n"),
    ("Before<wbr>After", "BeforeAfter\n"),
    ("Before<kbd>X<strong>Y</strong></kbd>After", "Before`XY`After\n"),
    ("Before<select>X<strong>Y</strong></select>After", "BeforeXYAfter\n"),
    ("Before<head title='ATTR'>SECRET<b>nested</b></head>After", "BeforeSECRET**nested**After\n"),
    ("Before<input title='ATTR'>SECRET<b>nested</b></input>After", "BeforeSECRET**nested**After\n"),
    ("Input<input type='text'>field", "Inputfield\n"),
    ("Un<strong>freakin</strong>believable", "Un**freakin**believable\n"),
    ("<strong><em>x</em></strong>", "***x***\n"),
    ("<strong>Bold</strong><em>Italic</em><code>Code</code>", "**BoldItalic**`Code`\n"),
    ("<strong>Bold</strong> <em>Italic</em> <code>Code</code>", "**Bold** *Italic* `Code`\n"),
    ("fake **bold**", "fake \\*\\*bold\\*\\*\n"),
    ("Text before > and after", "Text before &gt; and after\n"),
    ("&amp; &quot; &apos; &#65; &#x1F600; &lt;x&gt;", "& \" ' A 😀 &lt;x&gt;\n"),
    ("Before\0After", "BeforeAfter\n"),
    ("<code> space </code>", "`space`\n"),
    ("<code>   </code>", "`   `\n"),
    ("<code>`backtick`</code>", "`` `backtick` ``\n"),
    ("<pre><code class='language-python'>def f():\n    pass</code></pre>", "```python\ndef f():\n    pass\n```\n"),
    ("<pre><code></code></pre>", "```\n```\n"),
    ("<a href='u' title='Example'>x</a>", '[x](u "Example")\n'),
    ("<img alt='x'>", "\n"),
    ("<img alt='Photo' src='photo.jpg' srcset='wrong 2x' title='Click to view'>", '![Photo](photo.jpg "Click to view")\n'),
    ("<p><strong><em>Bold then italic</strong></em></p>", "***Bold then italic***\n"),
    ("<p>Unclosed paragraph<strong>Unclosed bold<em>Nested unclosed", "Unclosed paragraph**Unclosed bold*Nested unclosed***\n"),
    ("<script>bad</script><style>bad</style><iframe>bad</iframe><noscript>bad</noscript><textarea>bad</textarea>OK", "OK\n"),
    ("<!--hidden-->A", "A\n"),
    ("<del>x</del>", "x\n"),
    ("<del><strong>x</strong></del>", "~~**x**~~\n"),
    ("<del><del>x</del></del>", "~~x~~\n"),
], ids=lambda value: str(value)[:24])
def test_core_conversion(exe, html, want):
    r = invoke(exe, html=html)
    assert r.returncode == 0 and r.stderr == b""
    assert r.stdout.decode("utf-8") == want


def test_custom_strong_delimiter(exe):
    r = invoke(exe, "--opt-strong-delimiter=__", html="<strong>x</strong><em>y</em>")
    assert r.returncode == 0 and r.stdout == b"__x__*y*\n"


def test_domain_resolution(exe):
    html = '<a href="../page">x</a><img src="/img.png">'
    r = invoke(exe, "--domain=https://example.com/path/", html=html)
    assert r.returncode == 0 and r.stdout == b"[x](https://example.com/page)![](https://example.com/img.png)\n"


def test_strike_plugin(exe):
    r = invoke(exe, "--plugin-strikethrough", html="<s>a</s><strike>b</strike>")
    assert r.returncode == 0 and r.stdout == b"~~a~~~~b~~\n"


def test_depth_and_long_content(exe):
    html = "<span>" * 120 + "deep" + "</span>" * 120
    r = invoke(exe, html=html)
    assert r.returncode == 0 and r.stdout == b"deep\n"
    r = invoke(exe, html="<p>" + "x" * 10000 + "</p>")
    assert r.returncode == 0 and r.stdout == ("x" * 10000 + "\n").encode()
