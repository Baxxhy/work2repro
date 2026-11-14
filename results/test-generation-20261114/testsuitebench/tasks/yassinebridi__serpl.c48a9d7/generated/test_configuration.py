import json


def cfg_env(tmp_path):
    d = tmp_path / 'cfg'
    d.mkdir()
    return d, {'SERPL_CONFIG': str(d)}


def startup(run_prog, tmp_path, env, *args):
    return run_prog(*args, cwd=tmp_path, env=env)


def test_absent_and_empty_object_config_use_defaults(run_prog, tmp_path):
    cfg, env = cfg_env(tmp_path)
    p = startup(run_prog, tmp_path, env)
    assert p.returncode == 1
    assert p.stdout == b''
    assert 'serpl error: Something went wrong' in p.stderr.decode('utf-8', errors='replace')
    (cfg / 'config.json').write_text('{}', encoding='utf-8')
    p = startup(run_prog, tmp_path, env)
    assert p.returncode == 1 and p.stdout == b''
    assert 'serpl error: Something went wrong' in p.stderr.decode('utf-8', errors='replace')


def test_empty_or_invalid_json5_is_fatal_but_info_flags_bypass_it(run_prog, tmp_path):
    cfg, env = cfg_env(tmp_path)
    for content in ('', '{ invalid'):
        (cfg / 'config.json5').write_text(content, encoding='utf-8')
        p = startup(run_prog, tmp_path, env)
        assert p.returncode != 0
        err = p.stderr.decode('utf-8', errors='replace')
        assert 'serpl error: Something went wrong' in err
        assert 'Error:' in err
        assert 'JSON' in err or 'line' in err
        for flag in ('--help', '--version'):
            q = startup(run_prog, tmp_path, env, flag)
            assert q.returncode == 0 and q.stderr == b''


def test_json5_comments_trailing_comma_and_partial_config(run_prog, tmp_path):
    cfg, env = cfg_env(tmp_path)
    (cfg / 'config.json5').write_text('{ // comment\n "keybindings": {}, }', encoding='utf-8')
    p = startup(run_prog, tmp_path, env)
    assert p.returncode == 1
    assert 'serpl error: Something went wrong' in p.stderr.decode('utf-8', errors='replace')


def test_config_file_precedence_yaml_toml_ini(run_prog, tmp_path):
    cfg, env = cfg_env(tmp_path)
    (cfg / 'config.json').write_text('{}', encoding='utf-8')
    (cfg / 'config.yaml').write_text(': : invalid yaml', encoding='utf-8')
    p = startup(run_prog, tmp_path, env)
    err = p.stderr.decode('utf-8', errors='replace')
    assert p.returncode == 1 and p.stdout == b''
    assert 'Well, this is embarrassing.' in err
    assert 'internal error: entered unreachable code' in err
    assert 'serpl error: Something went wrong' not in err

    (cfg / 'config.yaml').write_text('{}', encoding='utf-8')
    (cfg / 'config.toml').write_text('not = [ valid', encoding='utf-8')
    p = startup(run_prog, tmp_path, env)
    assert p.returncode != 0
    assert 'cfg/config.toml' in p.stderr.decode('utf-8', errors='replace')

    (cfg / 'config.toml').write_text('', encoding='utf-8')
    (cfg / 'config.ini').write_text('[broken', encoding='utf-8')
    p = startup(run_prog, tmp_path, env)
    assert p.returncode != 0
    assert 'cfg/config.ini' in p.stderr.decode('utf-8', errors='replace')


def test_json_beats_yaml_and_json_error_names_selected_path(run_prog, tmp_path):
    cfg, env = cfg_env(tmp_path)
    (cfg / 'config.json5').write_text('{"keybindings": {}}', encoding='utf-8')
    (cfg / 'config.json').write_text('{x: 1}', encoding='utf-8')
    (cfg / 'config.yaml').write_text(': : invalid yaml', encoding='utf-8')
    p = startup(run_prog, tmp_path, env)
    err = p.stderr.decode('utf-8', errors='replace')
    assert p.returncode != 0
    assert 'key must be a string at line 1 column 3 in cfg/config.json' in err


def test_keybinding_keyname_failures_use_crash_reporter(run_prog, tmp_path):
    cfg, env = cfg_env(tmp_path)
    for key in ('<Escape>', 'escape', 'Ā'):
        (cfg / 'config.json').write_text(json.dumps({'keybindings': {key: 'Quit'}}), encoding='utf-8')
        p = startup(run_prog, tmp_path, env)
        err = p.stderr.decode('utf-8', errors='replace')
        assert p.returncode != 0
        assert 'Well, this is embarrassing.' in err
        assert 'Unable to parse' in err
        if key != 'Ā':
            assert 'escape' in err.lower()


def test_unsupported_style_groups_fail_without_affecting_information_flags(run_prog, tmp_path):
    cfg, env = cfg_env(tmp_path)
    (cfg / 'config.json').write_text(json.dumps({'styles': {
        'Home': {'text': 'red'}, 'Search': {'text': 'blue'},
        'Replace': {'text': 'green'}, 'Normal': {'text': 'white'},
        'Input': {'text': 'yellow'}}}), encoding='utf-8')
    p = startup(run_prog, tmp_path, env)
    err = p.stderr.decode('utf-8', errors='replace').lower()
    assert p.returncode != 0 and 'search' in err
    assert startup(run_prog, tmp_path, env, '--version').returncode == 0


def test_valid_style_config_does_not_break_startup(run_prog, tmp_path):
    cfg, env = cfg_env(tmp_path)
    (cfg / 'config.json').write_text('{"styles":{"Normal":{"text":" bold red on blue "},"Input":{"text":"italic cyan"}}}', encoding='utf-8')
    p = startup(run_prog, tmp_path, env)
    assert p.returncode == 1
    assert 'serpl error: Something went wrong' in p.stderr.decode('utf-8', errors='replace')
