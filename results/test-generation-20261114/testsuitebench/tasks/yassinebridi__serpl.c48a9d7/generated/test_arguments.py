import pytest


def assert_error(p, fragment):
    assert p.returncode == 2
    assert p.stdout == b''
    text = p.stderr.decode('utf-8')
    assert text.endswith('\n')
    assert fragment in text
    assert "For more information, try '--help'." in text


@pytest.mark.parametrize('arg,shown', [
    ('-v', "unexpected argument '-v' found"),
    ('--HELP', "unexpected argument '--HELP' found"),
    ('--Version', "unexpected argument '--Version' found"),
    ('--hel', "unexpected argument '--hel' found"),
    ('--badflag', "unexpected argument '--badflag' found"),
    ('extra', "unexpected argument 'extra' found"),
], ids=['lower-v', 'upper-help', 'capital-version', 'help-prefix', 'unknown-long', 'positional'] )
def test_unknown_and_case_sensitive_arguments(run_prog, arg, shown):
    assert_error(run_prog(arg), shown)


@pytest.mark.parametrize('arg,suggestion,usage', [
    ('--Version', "tip: a similar argument exists: '--version'", 'Usage: executable --version'),
    ('--hel', "tip: a similar argument exists: '--help'", 'Usage: executable --help'),
    ('--proj', "tip: a similar argument exists: '--project-root'", 'Usage: executable --project-root <PATH>'),
], ids=['version-suggestion', 'help-suggestion', 'project-suggestion'])
def test_close_long_option_suggestions(run_prog, arg, suggestion, usage):
    p = run_prog(arg)
    assert_error(p, f"unexpected argument '{arg}' found")
    text = p.stderr.decode()
    assert suggestion in text and usage in text


def test_missing_empty_duplicate_project_root_errors(run_prog, tmp_path):
    for args in [('--project-root',), ('-p',), ('--project-root=',), ('-p=',)]:
        p = run_prog(*args)
        assert_error(p, "a value is required for '--project-root <PATH>' but none was supplied")
    for args in [('-p', str(tmp_path), '-p', str(tmp_path)),
                 ('-pfoo', '--project-root=bar')]:
        p = run_prog(*args)
        assert_error(p, "the argument '--project-root <PATH>' cannot be used multiple times")


@pytest.mark.parametrize('arg,value,usage', [
    ('--help=foo', 'foo', 'Usage: executable --help'),
    ('--version=bar', 'bar', 'Usage: executable --version'),
], ids=['help-equals-value', 'version-equals-value'])
def test_flags_reject_equals_values(run_prog, arg, value, usage):
    p = run_prog(arg)
    assert_error(p, f"unexpected value '{value}' for")
    assert usage in p.stderr.decode()


def test_value_token_is_consumed_before_flag_parsing(run_prog):
    p = run_prog('--project-root', '--version')
    assert_error(p, "a value is required for '--project-root <PATH>' but none was supplied")
    p = run_prog('--badflag', '--help')
    assert_error(p, "unexpected argument '--badflag' found")
    p = run_prog('--', '--badflag')
    assert_error(p, "unexpected argument '--badflag' found")


def test_project_root_path_spellings_are_accepted_and_ui_attempted(run_prog, tmp_path):
    for args in [('-p', str(tmp_path)), ('-p' + str(tmp_path),),
                 ('-p=' + str(tmp_path),), ('--project-root', str(tmp_path)),
                 ('--project-root=' + str(tmp_path),)]:
        p = run_prog(*args, cwd=tmp_path)
        assert p.returncode == 1
        assert p.stdout == b''
        assert 'serpl error: Something went wrong' in p.stderr.decode('utf-8', errors='replace')

