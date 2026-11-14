import os
import subprocess
from pathlib import Path

import pytest


EXE = Path('/workspace/executable')
COMMANDS = '''analyze anaeig angle awh bar bundle check chi cluster clustsize confrms convert-tpr convert-trj covar current density densmap dielectric dipoles disre dos dssp dump dyecoupl editconf eneconv enemat energy filter genconf genion genrestr grompp gyrate gyrate-legacy h2order hbond helix helixorient hydorder densorder lie make_edi make_ndx mdmat mindist msd nmeig nmens nmr nmtraj order pdb2gmx polystat potential principal rama rdf rms rmsdist rmsf rotacf rotmat saltbr sasa sham sigeps solvate sorient spatial spol tcaf traj trjcat trjconv trjorder vanhove velacc wham wheel xpm2ps'''.split()


def run(*args, cwd=None, stdin='', env=None):
    e = os.environ.copy()
    e['GMX_MAXBACKUP'] = '-1'
    if env:
        e.update(env)
    return subprocess.run([str(EXE), *map(str, args)], cwd=cwd, input=stdin,
                          text=True, capture_output=True, env=e, timeout=15)


@pytest.mark.parametrize('args,banner', [([], True), (['-h'], True), (['help'], False)])
def test_general_help(args, banner):
    p = run(*args)
    assert p.returncode == 0
    assert p.stdout.startswith('SYNOPSIS')
    assert 'gmx [-[no]h] [-[no]quiet] [-[no]version] [-[no]copyright]' in p.stdout
    assert 'Other options:' in p.stdout
    assert 'Additional help is available on the following topics:' in p.stdout
    assert "To access the help, use 'gmx help <topic>'." in p.stdout
    assert 'DESCRIPTION' not in p.stdout
    assert (':-) GROMACS - executable' in p.stderr) is banner


def test_general_and_topic_help_details():
    p = run('help', 'commands')
    assert p.returncode == 0 and p.stdout.startswith('LIST OF AVAILABLE COMMANDS')
    assert 'Usage: gmx [<options>] <command> [<args>]' in p.stdout
    for row in ('energy               Writes energies to xvg files and display averages',
                'anaeig               Analyze eigenvectors/normal modes',
                'mdrun                Perform a simulation',
                "For help on a command, use 'gmx help <command>'."):
        assert row in p.stdout
    p = run('help', 'selections')
    assert p.returncode == 0 and p.stdout.startswith('SELECTION SYNTAX AND USAGE')
    for phrase in ('Selections are used to select atoms/molecules/residues for analysis',
                   'each selection evaluates to a set of positions', 'selections can be dynamic',
                   'Available subtopics:', 'arithmetic   Arithmetic expressions in selections',
                   'cmdline      Specifying selections from command line'):
        assert phrase in p.stdout


def test_global_options_and_unknowns():
    p = run('-version')
    assert p.returncode == 0 and 'GROMACS' in p.stdout and '2027.0-dev' in p.stdout
    for term in ('Executable:', 'Precision:', 'MPI:', 'OpenMP:', 'GPU:', 'SIMD:', 'FFT:', 'compiler', 'build'):
        assert term.lower() in p.stdout.lower()
    p = run('--version')
    assert p.returncode == 0 and '2027.0-dev' in p.stdout
    p = run('-quiet', '-version')
    assert p.returncode == 0 and p.stderr == '' and p.stdout.startswith(':-) GROMACS - executable')
    p = run('-quiet')
    assert p.returncode == 0 and 'Additional help is available' in p.stdout and not p.stderr
    p = run('-help')
    assert p.returncode != 0 and 'Invalid command-line options' in p.stderr
    assert 'Unknown command-line option -help' in p.stderr
    assert 'src/gromacs/commandline/cmdlineparser.cpp' in p.stderr
    p = run('not-a-command')
    assert p.returncode != 0 and "'not-a-command' is not a GROMACS command." in p.stderr
    assert 'src/gromacs/commandline/cmdlinemodulemanager.cpp' in p.stderr
    assert 'https://manual.gromacs.org/current/user-guide/run-time-errors.html' in p.stderr
    p = run('help', 'not-a-topic')
    assert p.returncode == 2 and "No help available for 'not-a-topic'" in p.stderr


@pytest.mark.parametrize('command', COMMANDS, ids=COMMANDS)
def test_each_command_has_help(command):
    p = run(command, '-h')
    assert p.returncode == 0
    assert 'SYNOPSIS' in p.stdout and 'DESCRIPTION' in p.stdout and 'OPTIONS' in p.stdout
    assert f'gmx {command}' in p.stdout


@pytest.mark.parametrize('command', COMMANDS, ids=COMMANDS)
def test_double_dash_help_is_rejected(command):
    p = run(command, '--help')
    assert p.returncode == 1 and p.stdout == ''
    assert f'GROMACS - gmx {command}' in p.stderr
    assert 'Error in user input:' in p.stderr
    assert 'Invalid command-line options' in p.stderr
    assert 'Unknown command-line option --help' in p.stderr


def test_selected_command_help_contracts():
    checks = {
        'energy': ['gmx energy [-f [<.edr>]] [-f2 [<.edr>]] [-s [<.tpr>]]',
                   'gmx energy extracts energy components from an energy file',
                   'Average, RMSD, and drift are calculated', 'Options to specify input files:',
                   'Options to specify output files:', 'Other options:'],
        'mdrun': ['gmx mdrun [-s [<.tpr>]]', 'Molecular Dynamics simulations'],
        'convert-tpr': ['by modifying the number of steps'],
        'convert-trj': ['gmx convert-trj converts trajectory files between different formats.'],
        'genconf': ['gmx genconf [-f [<.gro/.g96/...>]]', 'multiplies a given coordinate file'],
        'velacc': ['momentum autocorrelation function'],
        'xpm2ps': ['XPixelMap'],
    }
    for cmd, phrases in checks.items():
        p = run('help', cmd)
        assert p.returncode == 0
        for phrase in phrases:
            assert phrase in p.stdout
    for cmd in ('energy', 'check', 'lie'):
        p = run(cmd, '-h')
        assert p.returncode == 0 and 'OPTIONS' in p.stdout
    p = run('help', 'sham')
    assert '-[no]time' in p.stdout
    p = run('help', 'rmsdist')
    assert 'Trajectory' in p.stdout and 'Structure+mass(db)' in p.stdout


@pytest.mark.parametrize('command', ['editconf', 'genconf', 'eneconv', 'energy', 'gyrate-legacy',
                                     'grompp', 'lie', 'mdmat', 'msd', 'rms', 'sasa', 'velacc'])
def test_missing_explicit_trajectory_input_has_parser_diagnostic(command, tmp_path):
    missing = tmp_path / 'absent.xtc'
    p = run(command, '-f', missing, cwd=tmp_path)
    assert p.returncode != 0 and 'Error in user input:' in p.stderr
    assert 'Invalid command-line options' in p.stderr
    assert 'In command-line option -f' in p.stderr
    assert f"File '{missing}' does not exist or is not accessible." in p.stderr
    assert 'The file could not be opened.' in p.stderr
    assert 'Reason: No such file or directory' in p.stderr


def test_default_input_diagnostic_and_current_reports_both_defaults(tmp_path):
    p = run('lie', cwd=tmp_path)
    assert p.returncode != 0 and 'Invalid input values' in p.stderr
    assert 'In option f' in p.stderr
    assert "default file 'ener' does not exist or is not accessible." in p.stderr
    assert 'The following extensions were tried to complete the file name:' in p.stderr
    p = run('current', cwd=tmp_path)
    assert p.returncode != 0
    assert p.stderr.index('In option f') < p.stderr.index('In option s')
