from conftest import invoke


def test_lists_nested_numbering_and_start(exe):
    html = '<ol start="3"><li>Parent<ul><li>Child<ol><li>Grandchild</li></ol></li></ul></li></ol>'
    r = invoke(exe, html=html)
    assert r.returncode == 0
    assert r.stdout.decode() == "3. Parent\n  \n  - Child\n    \n    1. Grandchild\n"


def test_quotes_and_nested_quotes(exe):
    r = invoke(exe, html="<blockquote>Line 1\nLine 2</blockquote><blockquote>Outer<blockquote>Nested</blockquote></blockquote>")
    assert r.returncode == 0
    assert r.stdout.decode() == "> Line 1 Line 2\n\n> Outer\n> \n> > Nested\n"


def test_table_disabled_flattens_and_enabled_renders(exe):
    html = "<table><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>2</td></tr></table>"
    plain = invoke(exe, html=html)
    table = invoke(exe, "--plugin-table", html=html)
    assert plain.returncode == table.returncode == 0
    assert plain.stdout == b"AB12\n"
    assert table.stdout == b"| A | B |\n|---|---|\n| 1 | 2 |\n"


def test_table_padding_modes(exe):
    html = "<table><tr><th>A</th><th>B</th></tr><tr><td>X</td><td>Y</td></tr></table>"
    minimal = invoke(exe, "--plugin-table", "--opt-table-cell-padding-behavior=minimal", html=html)
    none = invoke(exe, "--plugin-table", "--opt-table-cell-padding-behavior=none", html=html)
    assert minimal.stdout == b"| A | B |\n|---|---|\n| X | Y |\n"
    assert none.stdout == b"|A|B|\n|---|---|\n|X|Y|\n"


def test_table_synthetic_header_promotion_and_empty_rows(exe):
    html = "<table><tr><td>A</td><td>B</td></tr><tr><td></td><td> </td></tr></table>"
    default = invoke(exe, "--plugin-table", "--opt-table-cell-padding-behavior=minimal", html=html)
    opts = invoke(exe, "--plugin-table", "--opt-table-header-promotion", "--opt-table-skip-empty-rows", "--opt-table-cell-padding-behavior=minimal", html=html)
    assert default.stdout == b"|   |   |\n|---|---|\n| A | B |\n|   |   |\n"
    assert opts.stdout == b"| A | B |\n|---|---|\n"


def test_table_newline_fallback_and_preserve(exe):
    html = "<table><tr><th>H</th></tr><tr><td>A\n  B<br>C</td></tr></table>"
    fallback = invoke(exe, "--plugin-table", html=html)
    preserved = invoke(exe, "--plugin-table", "--opt-table-newline-behavior=preserve", html=html)
    assert fallback.stdout == b"H\n\nA B  \nC\n"
    assert b"<br />" in preserved.stdout and b"| H" in preserved.stdout and b"A B" in preserved.stdout


def test_table_presentation_and_span_modes(exe):
    presentation = '<table role="presentation"><tr><th>A</th><th>B</th></tr><tr><td>X</td><td>Y</td></tr></table>'
    ordinary = invoke(exe, "--plugin-table", html=presentation)
    forced = invoke(exe, "--plugin-table", "--opt-table-presentation-tables", html=presentation)
    assert ordinary.stdout == b"AB\n\nXY\n"
    assert b"| A | B |" in forced.stdout
    span = "<table><tr><th colspan='2'>M</th></tr><tr><td>A</td><td>B</td></tr></table>"
    empty = invoke(exe, "--plugin-table", "--opt-table-cell-padding-behavior=minimal", html=span)
    mirror = invoke(exe, "--plugin-table", "--opt-table-cell-padding-behavior=minimal", "--opt-table-span-cell-behavior=mirror", html=span)
    assert b"| M |   |" in empty.stdout
    assert b"| M | M |" in mirror.stdout


def test_empty_legacy_compatibility(exe):
    html = "<p></p>\n<strong></strong>\n<em></em>\n<a href='https://example.com'></a>\n<ul></ul>\n<ol></ol>"
    r = invoke(exe, html=html)
    assert r.returncode == 0 and r.stdout == b"[](https://example.com)\n\n<!--THE END-->\n"


def test_adjacent_empty_list_compatibility(exe):
    r = invoke(exe, html="<p>A</p><ul><li></li></ul><ol></ol><p>B</p>")
    assert r.returncode == 0 and r.stdout == b"A\n\n<!--THE END-->\n\nB\n"
