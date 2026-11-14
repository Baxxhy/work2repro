import os
import subprocess
from pathlib import Path

import pytest


EXE = Path('/workspace/executable')


def invoke(tmp_path, *args, input_text=None, env=None):
    merged = os.environ.copy()
    if env:
        merged.update(env)
    return subprocess.run(
        [str(EXE), *map(str, args)], cwd=tmp_path, input=input_text,
        text=True, encoding='utf-8', errors='replace', capture_output=True,
        timeout=4, env=merged,
    )


def combined(p):
    return p.stdout + p.stderr


def test_help_options_and_precedence(tmp_path):
    for opt in ('--help', '-h', '-?'):
        p = invoke(tmp_path, opt)
        assert p.returncode == 0
        assert 'Doxygen version 1.17.0' in p.stdout
        assert 'You can use Doxygen in a number of ways:' in p.stdout
        assert p.stdout.endswith('\n')
    p = invoke(tmp_path, '--help', '--this-flag-should-not-exist')
    assert p.returncode == 0 and p.stderr == ''
    assert 'Doxygen version 1.17.0' in p.stdout


def test_no_args_matches_help_and_exact_error(tmp_path):
    help_run = invoke(tmp_path, '--help')
    p = invoke(tmp_path)
    assert p.returncode == 1
    assert p.stderr == 'error: Doxyfile not found and no input file specified!\n'
    assert p.stdout == help_run.stdout


def test_versions(tmp_path):
    short = invoke(tmp_path, '-v')
    extended = invoke(tmp_path, '-V')
    assert short.returncode == extended.returncode == 0
    assert '1.17.0' in short.stdout and '1.17.0' in extended.stdout
    assert 'sqlite3' in extended.stdout.lower()
    assert len(extended.stdout) >= len(short.stdout)


def test_developer_help_and_debug_validation(tmp_path):
    p = invoke(tmp_path, '-d')
    assert p.returncode == 0 and p.stderr == ''
    for fragment in ('Developer parameters:', '-m', '-b', '-c <file>', 'enable a debug level', 'lex:scanner'):
        assert fragment in p.stdout
    bad = invoke(tmp_path, '-d', 'bogus')
    assert bad.returncode != 0
    assert 'option "-d" has unknown debug specifier' in combined(bad)
    assert 'bogus' in combined(bad)


@pytest.mark.parametrize('opt', ['--no-such-flag', '--nonexistent-flag', '-Z'], ids=['unknown-long-a', 'unknown-long-b', 'unknown-short'])
def test_unknown_options(tmp_path, opt):
    p = invoke(tmp_path, opt)
    assert p.returncode != 0
    out = combined(p)
    assert 'error:' in out and 'Unknown option' in out and opt in out


def test_quiet_does_not_hide_parser_error(tmp_path):
    p = invoke(tmp_path, '-q', '--no-such-flag')
    assert p.returncode != 0 and 'error: Unknown option' in combined(p)


def test_bare_name_means_missing_config(tmp_path):
    p = invoke(tmp_path, 'not-a-subcommand')
    assert p.returncode != 0
    assert 'configuration file not-a-subcommand not found' in p.stderr
    assert 'Unknown option' not in combined(p)
    assert 'You can use Doxygen in a number of ways:' in p.stdout


@pytest.mark.parametrize('args,fragments', [
    (('-w',), ('error:', 'option "-w" is missing format specifier')),
    (('-w', 'bogus', 'f'), ('error:', 'Illegal format specifier', 'bogus')),
    (('-w', 'rtf'), ('error:', 'missing')),
    (('-e',), ('error:', 'option "-e" is missing format specifier')),
    (('-e', 'html', 'out'), ('error:', 'option "-e" has invalid format specifier')),
    (('-f',), ('missing',)),
], ids=['w-no-format', 'w-bad-format', 'w-no-file', 'e-no-format', 'e-bad-format', 'f-no-list'])
def test_malformed_modes(args, fragments, tmp_path):
    p = invoke(tmp_path, *args)
    assert p.returncode != 0
    for f in fragments:
        assert f in combined(p)


def test_generate_config_default_named_and_stdout(tmp_path):
    p = invoke(tmp_path, '-g')
    assert p.returncode == 0
    data = (tmp_path / 'Doxyfile').read_text(encoding='utf-8')
    assert len(data.encode()) > 1000 and data.endswith('\n')
    assert data.startswith('# Doxyfile 1.17.0')
    assert 'This file describes the settings' in data
    for key in ('DOXYFILE_ENCODING', 'PROJECT_NAME', 'OUTPUT_DIRECTORY', 'INPUT', 'RECURSIVE', 'QUIET', 'EXTRACT_ALL', 'GENERATE_HTML', 'GENERATE_LATEX'):
        assert key in data
    assert 'GENERATE_HTML' in data and 'GENERATE_LATEX' in data
    named = invoke(tmp_path, '-g', 'custom.cfg')
    assert named.returncode == 0 and (tmp_path / 'custom.cfg').is_file()
    outdir = tmp_path / 'stdout-case'
    outdir.mkdir()
    std = invoke(outdir, '-g', '-')
    assert std.returncode == 0 and std.stderr == ''
    assert std.stdout.startswith('# Doxyfile 1.17.0') and not list(outdir.iterdir())


def test_suppressed_template_and_first_action_wins(tmp_path):
    p = invoke(tmp_path, '-s', '-g', 'plain.cfg')
    assert p.returncode == 0
    data = (tmp_path / 'plain.cfg').read_text(encoding='utf-8')
    assert data and data.startswith('# Doxyfile 1.17.0')
    assert 'Project related configuration options' in data
    assert 'DOXYFILE_ENCODING' in data and '##' not in data
    q = invoke(tmp_path, '-g', 'cfgA', '-g', 'cfgB')
    assert q.returncode == 0 and (tmp_path / 'cfgA').exists() and not (tmp_path / 'cfgB').exists()


def test_update_existing_and_missing_config(tmp_path):
    p = invoke(tmp_path, '-u')
    assert p.returncode != 0
    assert 'error' in combined(p).lower() or 'not found' in combined(p).lower()
    f = tmp_path / 'mine.cfg'
    f.write_text('PROJECT_NAME = X\n', encoding='utf-8')
    p = invoke(tmp_path, '-u', 'mine.cfg')
    result = f.read_text(encoding='utf-8')
    assert p.returncode == 0 and len(result) > len('PROJECT_NAME = X\n')
    assert result.startswith('# Doxyfile 1.17.0\n')
    assert 'PROJECT_NAME' in result and 'X' in result


def test_layout_file_and_stdout(tmp_path):
    p = invoke(tmp_path, '-l')
    assert p.returncode == 0
    data = (tmp_path / 'DoxygenLayout.xml').read_text(encoding='utf-8')
    assert data.strip().startswith('<?xml') and '<doxygenlayout' in data.lower()
    p = invoke(tmp_path, '-l', 'layout.xml')
    assert p.returncode == 0 and (tmp_path / 'layout.xml').exists()
    out = tmp_path / 'stdout-layout'
    out.mkdir()
    p = invoke(out, '-l', '-')
    assert p.returncode == 0 and p.stdout.lstrip().startswith('<?xml')
    assert not list(out.iterdir())


def test_asset_generation(tmp_path):
    p = invoke(tmp_path, '-w', 'rtf', 'style.sty')
    assert p.returncode == 0 and (tmp_path / 'style.sty').stat().st_size > 0
    for fmt in ('html', 'latex'):
        d = tmp_path / fmt
        d.mkdir()
        p = invoke(d, '-w', fmt, 'header', 'footer', 'style')
        assert p.returncode == 0
        assert any(x.is_file() for x in d.iterdir())
    p = invoke(tmp_path, '-e', 'rtf', 'extensions.tex')
    assert p.returncode == 0 and (tmp_path / 'extensions.tex').is_file()


def test_emoji_file_and_stdout(tmp_path):
    p = invoke(tmp_path, '-f', 'emoji', 'emojis.txt')
    assert p.returncode == 0
    lines = (tmp_path / 'emojis.txt').read_text(encoding='utf-8').splitlines()
    assert lines[0] == ':+1:' and ':-1:' in lines[1:] and ':100:' in lines[1:]
    d = tmp_path / 'emoji-stdout'
    d.mkdir()
    p = invoke(d, '-f', 'emoji', '-')
    assert p.returncode == 0 and p.stdout.splitlines()[0] == ':+1:'
    assert not list(d.iterdir())


def test_run_default_generated_config_creates_formats_and_warns(tmp_path):
    assert invoke(tmp_path, '-g').returncode == 0
    p = invoke(tmp_path)
    assert p.returncode == 0
    assert (tmp_path / 'html').is_dir() and (tmp_path / 'latex').is_dir()
    assert 'warning:' in p.stderr.lower() or 'No files to be processed' in p.stderr


def test_run_empty_output_directory_and_disabled_formats(tmp_path):
    (tmp_path / 'in.cfg').write_text('OUTPUT_DIRECTORY = result\nGENERATE_HTML = NO\nGENERATE_LATEX = NO\nGENERATE_XML = NO\nGENERATE_MAN = NO\nGENERATE_RTF = NO\nGENERATE_DOCBOOK = NO\nGENERATE_PERLMOD = NO\nGENERATE_TREEVIEW = NO\n', encoding='utf-8')
    p = invoke(tmp_path, 'in.cfg')
    assert p.returncode == 0 and (tmp_path / 'result').is_dir()
    assert not (tmp_path / 'result' / 'html').exists()


def test_run_env_expansion_in_output_path(tmp_path):
    (tmp_path / 'env.cfg').write_text('OUTPUT_DIRECTORY = $(HOME)/out\nGENERATE_HTML = NO\nGENERATE_LATEX = NO\n', encoding='utf-8')
    home = tmp_path / 'home'
    p = invoke(tmp_path, 'env.cfg', env={'HOME': str(home)})
    assert p.returncode == 0 and (home / 'out').is_dir()


@pytest.mark.parametrize('quiet', ['YES', 'NO'], ids=['quiet-yes', 'quiet-no'])
def test_no_input_warning_survives_quiet_setting(tmp_path, quiet):
    cfg = tmp_path / 'empty.cfg'
    cfg.write_text(f'QUIET = {quiet}\nGENERATE_HTML = NO\nGENERATE_LATEX = NO\n', encoding='utf-8')
    p = invoke(tmp_path, 'empty.cfg')
    assert p.returncode == 0
    assert 'warning:' in p.stderr.lower() or 'No files to be processed' in p.stderr


def test_cli_quiet_hides_progress_but_keeps_warning(tmp_path):
    (tmp_path / 'empty.cfg').write_text('GENERATE_HTML = NO\nGENERATE_LATEX = NO\n', encoding='utf-8')
    p = invoke(tmp_path, '-q', 'empty.cfg')
    assert p.returncode == 0 and p.stdout == ''
    assert 'warning:' in p.stderr.lower() or 'No files to be processed' in p.stderr


def test_invalid_boolean_warns_and_uses_default(tmp_path):
    (tmp_path / 'badbool.cfg').write_text('QUIET = MAYBE\nGENERATE_HTML = NO\nGENERATE_LATEX = NO\n', encoding='utf-8')
    p = invoke(tmp_path, 'badbool.cfg')
    assert p.returncode == 0
    assert 'not a valid boolean value' in p.stderr
    assert 'Using the default: NO' in p.stderr


def test_missing_run_config_diagnostic_and_help(tmp_path):
    p = invoke(tmp_path, 'absent.cfg')
    assert p.returncode == 1
    assert 'error: configuration file absent.cfg not found!' in p.stderr
    assert 'You can use Doxygen in a number of ways:' in p.stdout


def test_compare_stdin_changed_setting_and_env_modes(tmp_path):
    p = invoke(tmp_path, '-x', '-', input_text='PROJECT_NAME = X\n')
    assert p.returncode == 0 and p.stderr == ''
    assert p.stdout.startswith('# Difference with default Doxyfile')
    assert 'PROJECT_NAME' in p.stdout and '= X' in p.stdout
    cfg = tmp_path / 'compare.cfg'
    cfg.write_text('OUTPUT_DIRECTORY = $(HOME)/out\n', encoding='utf-8')
    env = {'HOME': '/tmp/home'}
    expanded = invoke(tmp_path, '-x', 'compare.cfg', env=env)
    literal = invoke(tmp_path, '-x_noenv', 'compare.cfg', env=env)
    assert expanded.returncode == literal.returncode == 0
    assert '/tmp/home/out' in expanded.stdout
    assert '$(HOME)/out' in literal.stdout


def test_missing_compare_default_config(tmp_path):
    p = invoke(tmp_path, '-q', '-x')
    assert p.returncode != 0
    out = combined(p)
    assert all(x in out for x in ('error:', 'Doxyfile not found', 'no input file specified'))
