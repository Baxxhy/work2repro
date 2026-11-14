import json
import pathlib
import re
import subprocess

import pytest


def out(p):
    return p.stdout.decode('utf-8', 'replace')


def quiet_run(game, *args, command):
    return game('-q', '-r', *args, command)


def test_help_documents_options(game):
    p = game('--help')
    s = out(p)
    assert p.returncode == 0 and p.stderr == b''
    assert s.startswith('USAGE:')
    assert 'Halite Game Environment' in s
    for option in ('-i', '--replaydirectory', '-s', '--seed', '-d', '--dimensions',
                   '-n', '--nplayers', '-r', '--noreplay', '-t', '--timeout',
                   '-o', '--override', '-q', '--quiet', '-h', '--help', '--version'):
        assert option in s


def test_version_exact(game):
    p = game('--version')
    assert p.returncode == 0 and p.stderr == b''
    assert p.stdout == b'\n/workspace/executable  version: 1.2\n\n'


def test_no_command_message(game):
    p = game('-r')
    assert p.returncode == 1
    assert out(p).splitlines() == [
        'Please provide the launch command string for at least one bot.',
        'Use the --help flag for usage details.']


@pytest.mark.parametrize('option', ['-s', '--seed', '-d', '--dimensions', '-i', '--replaydirectory'], ids=['seed-short','seed-long','dimensions-short','dimensions-long','directory-short','directory-long'])
def test_missing_option_value(game, option):
    p = game(option)
    text = (out(p) + p.stderr.decode('utf-8', 'replace'))
    assert p.returncode != 0
    assert 'PARSE ERROR' in text and option in text and 'Missing a value' in text and '--help' in text


@pytest.mark.parametrize('dims', ['abc', '10'], ids=['text','one-number'])
def test_bad_dimensions(game, dims):
    p = game('-d', dims, '-r', 'true')
    text = out(p) + p.stderr.decode('utf-8', 'replace')
    assert p.returncode == 1
    assert 'PARSE ERROR: Argument: -d (--dimensions)' in text
    assert "Couldn't read argument value" in text and '--help' in text


@pytest.mark.parametrize('n', ['0', '7', '8', '-1', 'abc'], ids=['zero','seven','eight','negative','nonnumeric'])
def test_invalid_player_count(game, botcmd, n):
    p = game('-r', '-n', n, botcmd())
    assert p.returncode != 0
    assert 'A map can only accommodate between 1 and 6 players.' in out(p)


def test_nplayers_rejects_multiple_bots(game, botcmd):
    p = game('-r', '-n', '2', botcmd(), botcmd())
    assert p.returncode != 0
    assert 'Only single-player mode enables specified n-player maps' in out(p)
    assert 'must not specify n' in out(p)


def test_quiet_lines_and_replay_off(game, botcmd):
    cmd = botcmd('empty', 'Quiet')
    p = game('-q', '-r', '-d', '3 3', '-s', '10', cmd)
    assert p.returncode == 0
    assert p.stderr == b''
    lines = out(p).split('\n')
    assert lines[0] == cmd
    assert lines[1] == '3 3'
    assert re.fullmatch(r'1 1 \d+', lines[2])
    assert lines[-2:] == [' ', ' ']
    assert 'Turn' not in out(p) and 'Init Message' not in out(p)


def test_options_after_bot_and_command_echo(game, botcmd):
    cmd = botcmd('empty', 'After')
    p = game(cmd, '-q', '-r', '-d', '3 3', '-s', '22')
    assert p.returncode == 0
    assert out(p).splitlines()[0] == cmd
    assert out(p).splitlines()[1] == '3 3'


def test_normal_output_and_seeded_replay(game, botcmd, tmp_path):
    p = game('-d', '10 10', '-s', '42', botcmd('empty', 'Normal'))
    s = out(p)
    assert p.returncode == 0 and p.stderr == b''
    assert len(s) > 200
    assert '10 10' in s and 'Init Message sent to player 1.' in s
    assert 'Init Message received from player 1, Normal.' in s
    assert 'Turn 1' in s and 'Map seed was 42' in s
    assert re.search(r'Opening a file at .*\d+-42\.hlt', s)
    assert 'Player #1, Normal, came in rank #1' in s
    files = list(tmp_path.glob('*.hlt'))
    assert len(files) == 1


def test_replay_schema(game, botcmd, tmp_path):
    p = game('-q', '-d', '5 5', '-s', '31', botcmd('empty', 'Replay'))
    assert p.returncode == 0
    fields = out(p).splitlines()
    replay_path, seed = fields[2].rsplit(' ', 1)
    assert seed == '31'
    data = json.loads((tmp_path / replay_path.removeprefix('./')).read_text(encoding='utf-8'))
    assert data['version'] == 11
    assert (data['width'], data['height'], data['num_players']) == (5, 5, 1)
    assert data['num_frames'] > 0
    assert data['player_names'] == ['Replay']
    assert len(data['productions']) == 5 and all(len(row) == 5 for row in data['productions'])
    assert len(data['frames']) == data['num_frames']
    assert len(data['moves']) == data['num_frames'] - 1
    for frame in data['frames']:
        assert len(frame) == 5 and all(len(row) == 5 for row in frame)
        assert all(len(cell) == 2 and 0 <= cell[0] <= 1 and 0 <= cell[1] <= 255
                   for row in frame for cell in row)
    assert all(len(f) == 5 and all(len(row) == 5 and all(0 <= d <= 4 for d in row)
                                   for row in f) for f in data['moves'])


def test_replay_disabled_creates_no_file(game, botcmd, tmp_path):
    p = game('-q', '-r', '-d', '3 3', '-s', '17', botcmd())
    assert p.returncode == 0
    assert not list(tmp_path.glob('*.hlt'))
    assert 'REPLAY' not in out(p)


def test_override_pairs_replace_names_and_hide_prefix(game, botcmd, tmp_path):
    p = game('-q', '-r', '-d', '3 3', '-o', botcmd('empty', 'Reported'), 'Alpha Name',
             botcmd('empty', 'Reported2'), 'Beta Name')
    assert p.returncode == 0
    lines = out(p).splitlines()
    assert lines[0] == '3 3'
    assert re.fullmatch(r'1 [12] \d+', lines[1])
    assert re.fullmatch(r'2 [12] \d+', lines[2])
    p2 = game('-q', '-r', '-d', '3 3', '--override', botcmd(), 'One', botcmd(), 'Two')
    assert p2.returncode == 0 and out(p2).splitlines()[0] == '3 3'


@pytest.mark.parametrize('args', [('-o', 'true', 'Name'), ('-o', 'true', 'A', 'true')], ids=['too-few','odd-count'])
def test_invalid_override_count(game, args):
    p = game(*args)
    assert p.returncode == 1
    assert 'Invalid number of player parameters with override switch enabled' in out(p)
    assert 'Override intended for server use only' in out(p)


def test_names_truncated_and_empty_name_survives(game, botcmd):
    long = 'ThisIsAVeryLongBotNameThatExceedsThirtyCharactersLimit'
    p = game('-q', '-r', '-d', '3 3', botcmd('empty', long))
    assert p.returncode == 0
    normal = game('-r', '-d', '3 3', botcmd('empty_name'))
    assert normal.returncode == 0 and 'Init Message received from player 1' in out(normal)


def test_invalid_move_ejects_but_engine_succeeds(game, botcmd):
    p = game('-q', '-r', '-d', '10 10', '-s', '1', botcmd('invalid', 'InvalidMoveBot'))
    assert p.returncode == 0
    lines = out(p).splitlines()
    assert re.fullmatch(r'1 1 0', lines[2])
    assert lines[3] == '1'


def test_unlaunchable_bot_is_player_failure(game):
    p = game('-q', '-r', '-d', '3 3', 'definitely-no-such-halite-bot-xyz')
    assert p.returncode == 0
    assert re.fullmatch(r'1 1 0', out(p).splitlines()[2])
    assert out(p).splitlines()[3] == '1'


def test_dimensions_automatic_and_zero_request(game, botcmd):
    for dimensions in (None, '0 0'):
        args = ['-q', '-r']
        if dimensions:
            args += ['-d', dimensions]
        p = game(*args, botcmd())
        assert p.returncode == 0
        w, h = map(int, out(p).splitlines()[1].split())
        assert 20 <= w <= 50 and 20 <= h <= 50


def test_quiet_replay_directory_and_explicit_seed(game, botcmd, tmp_path):
    replay_dir = tmp_path / 'Replays'
    replay_dir.mkdir()
    p = game('-q', '-i', str(replay_dir), '-d', '3 3', '-s', '100', botcmd())
    assert p.returncode == 0
    rec = out(p).splitlines()[2]
    assert str(replay_dir) in rec and rec.endswith(' 100')
    assert len(list(replay_dir.glob('*-100.hlt'))) == 1


def test_bad_replay_location_reports_error(game, botcmd, tmp_path):
    p = game('-q', '-i', str(tmp_path / 'missing'), '-d', '3 3', botcmd())
    text = out(p) + p.stderr.decode('utf-8', 'replace')
    assert p.returncode != 0 and 'Could not open file for replay' in text


def test_quiet_prefix_preserves_command_verbatim(game, botcmd):
    cmd1, cmd2 = botcmd('empty', 'A'), botcmd('empty', 'B')
    p = game('-q', '-r', '-d', '10 10', cmd1, cmd2)
    assert p.returncode == 0
    assert out(p).splitlines()[:3] == [cmd1, cmd2, '10 10']
    stats = out(p).splitlines()[3:5]
    assert [line.split()[0] for line in stats] == ['1', '2']
    assert {int(line.split()[1]) for line in stats} == {1, 2}


def test_timeout_mode_allows_slow_turn_bot(game, botcmd):
    p = game('-q', '-r', '-t', '-d', '3 3', botcmd('turn_sleep', 'Slow'))
    assert p.returncode == 0
    assert out(p).splitlines()[3] == ' '
