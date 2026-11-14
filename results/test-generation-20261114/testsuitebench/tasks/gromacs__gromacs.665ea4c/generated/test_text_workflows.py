import pytest

from test_interface import run


def gro_one():
    return ('one atom\n'
            '    1\n'
            '    1ALA      CA    1   1.000   1.000   1.000\n'
            '   3.00000   3.00000   3.00000\n')


def test_editconf_explicit_path_and_transform(tmp_path):
    source = tmp_path / 'in.gro'
    target = tmp_path / 'nested' / 'renamed.gro'
    target.parent.mkdir()
    source.write_text(gro_one())
    p = run('editconf', '-f', source, '-o', target, '-translate', '0.5', '0.5', '0.5', cwd=tmp_path)
    assert p.returncode == 0, p.stderr
    assert target.exists()
    lines = target.read_text().splitlines()
    assert lines[1].strip() == '1'
    # GRO coordinates use nanometers and fixed three decimal places.
    assert lines[2][20:44].split() == ['1.500', '1.500', '1.500']
    assert 'Translating 1 atoms (out of 1) by 0.5 0.5 0.5 nm' in p.stdout


def test_editconf_default_output_and_invalid_box_type(tmp_path):
    (tmp_path / 'in.gro').write_text(gro_one())
    p = run('editconf', '-f', 'in.gro', cwd=tmp_path)
    assert p.returncode == 0 and (tmp_path / 'out.gro').exists()
    p = run('editconf', '-f', 'in.gro', '-bt', 'invalid_box', cwd=tmp_path)
    assert p.returncode != 0
    assert 'Invalid value: invalid_box.' in p.stderr
    assert 'Allowed values: triclinic, cubic, dodecahedron, octahedron.' in p.stderr


def test_genconf_lattice_atom_count_and_bad_dimensions(tmp_path):
    source, target = tmp_path / 'a.gro', tmp_path / 'replicated.gro'
    source.write_text(gro_one())
    p = run('genconf', '-f', source, '-o', target, '-nbox', '2', '1', '2', cwd=tmp_path)
    assert p.returncode == 0, p.stderr
    assert int(target.read_text().splitlines()[1]) == 4
    p = run('genconf', '-f', source, '-o', target, '-nbox', '0', '1', '1', cwd=tmp_path)
    assert p.returncode != 0 and 'Fatal error:' in p.stderr
    assert 'Number of boxes (-nbox) should be larger than zero' in p.stderr


def test_analyze_statistics_and_numeric_average_output(tmp_path):
    source, average = tmp_path / 'values.xvg', tmp_path / 'average.xvg'
    source.write_text('0 1\n1 2\n2 3\n3 4\n4 5\n')
    p = run('analyze', '-f', source, '-av', average, cwd=tmp_path)
    assert p.returncode == 0, p.stderr
    assert 'SS1' in p.stdout and '3.000000e+00' in p.stdout
    rows = average.read_text().splitlines()
    assert len(rows) == 5
    assert all(row.strip() and not row.lstrip().startswith(('#', '@')) for row in rows)
    assert rows[0].split() == ['0', '1']


def test_analyze_regression_and_autocorrelation(tmp_path):
    source, ac = tmp_path / 'line.xvg', tmp_path / 'ac.xvg'
    source.write_text('0 1\n1 2\n2 3\n3 4\n4 5\n')
    p = run('analyze', '-f', source, '-regression', '-ac', ac, cwd=tmp_path)
    assert p.returncode == 0, p.stderr
    assert 'Minimizing residual chi2 = Sum_i w_i [f(x_i) - y_i]2' in p.stdout
    assert 'Chi2                    = 0' in p.stdout
    assert 'S (Sqrt(Chi2/(n-2))     = 0' in p.stdout
    data = [line.split() for line in ac.read_text().splitlines() if line.strip() and not line.startswith(('#', '@'))]
    assert len(data) == 3
    assert [float(r[1]) for r in data] == pytest.approx([1, .5, -.16667], abs=1e-4)


def test_sigeps_known_conversion_and_plot(tmp_path):
    out = tmp_path / 'potential.xvg'
    p = run('sigeps', '-c6', '0.001', '-cn', '1e-6', '-sigfac', '0.5', '-o', out, cwd=tmp_path)
    assert p.returncode == 0, p.stderr
    for phrase in ('c6    =  1.00000e-03, c12    =  1.00000e-06',
                   'sigma =      0.31623, epsilon =      0.25000',
                   'Van der Waals minimum at 0.354954, V = -0.25'):
        assert phrase in p.stdout
    assert '@    title "Potential"' in out.read_text()
    numeric = [l.split() for l in out.read_text().splitlines() if l.strip() and not l.startswith(('#', '@'))]
    assert numeric and float(numeric[0][0]) == pytest.approx(0.158114, abs=1e-5)


def test_sigeps_inverse_and_general_power_label(tmp_path):
    p = run('sigeps', '-sig', '0.3', '-eps', '1.0', cwd=tmp_path)
    assert p.returncode == 0 and 'c6    =  2.91600e-03, c12    =  2.12576e-06' in p.stdout
    p = run('sigeps', '-c6', '0.001', '-cn', '1e-6', '-pow', '10', cwd=tmp_path)
    assert p.returncode == 0 and 'c10    =' in p.stdout
    assert 'Fit of Lennard Jones (10-6) to Buckingham:' in p.stdout


def test_xpm2ps_renders_supplied_matrix_and_checks_gradient(tmp_path):
    matrix = tmp_path / 'small.xpm'
    eps = tmp_path / 'render.eps'
    matrix.write_text('''/* XPM */
static char *gromacs_xpm[] = {
"4 4 2 1",
"a c #FFFFFF",
"b c #000000",
"aaaa",
"abbb",
"abba",
"aaaa"
};
''')
    p = run('xpm2ps', '-f', matrix, '-o', eps, '-size', '200', cwd=tmp_path)
    assert p.returncode == 0, p.stderr
    assert eps.read_text().startswith('%!PS-Adobe-2.0 EPSF-1.2')
    assert 'Matrix 0 is 4 x 4' in p.stderr
    assert 'Set the x-size of the box to 50.000' in p.stdout
    assert 'Set the y-size of the box to 50.000' in p.stdout
    p = run('xpm2ps', '-f', matrix, '-o', eps, '-gradient', '1.5', '0.5', '0', cwd=tmp_path)
    assert p.returncode == 1 and 'RGB value 1.5 out of range (0.0-1.0)' in p.stderr


def test_make_ndx_interactive_selection(tmp_path):
    source, out = tmp_path / 'structure.gro', tmp_path / 'groups.ndx'
    source.write_text('three atoms\n    3\n'
                      '    1ALA      CA    1   0.000   0.000   0.000\n'
                      '    1ALA       C    2   0.100   0.000   0.000\n'
                      '    2GLY       N    3   0.200   0.000   0.000\n'
                      '   3.00000   3.00000   3.00000\n')
    p = run('make_ndx', '-f', source, '-o', out, cwd=tmp_path, stdin='q\n')
    assert p.returncode == 0, p.stderr
    assert 'Analysing residue names:' in p.stdout
    content = out.read_text()
    assert '[ System ]' in content and '1 2 3' in content


def test_help_for_commands_with_special_documented_formatting():
    p = run('disre', '-h')
    assert p.returncode == 0
    for option in ('-ds', '-da', '-dn', '-dm', '-dr'):
        assert option in p.stdout
    assert p.stdout.count('xvgr/xmgr file') >= 5
    p = run('filter', '-h')
    assert '-nf     <int>' in p.stdout and '-ol     [<.xtc/.trr/...>]' in p.stdout
    p = run('xpm2ps', '-h')
    assert '-f      [<.xpm>]' in p.stdout
