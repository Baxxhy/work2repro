import os
import pathlib
import subprocess


EXE = "/workspace/executable"
HELP = """# felix v2.16.1
A simple TUI file manager with vim-like keymapping.

## Usage
`fx` => Show items in the current directory.
`fx <directory path>` => Show items in the path.
Both relative and absolute path available.

## Options
`--help` | `-h`   => Print help.
`--log`  | `-l`   => Launch the app, automatically generating a log file.
`--init`          => Returns a shell script that can be sourcedfor
                     for shell integration.

## Manual
j / <Down>         :Go down.
k / <Up>           :Go up.
<C-d>              :Go down 1/2 page.
<C-u>>             :Go up 1/2 page.
h / <Left>         :Go to the parent directory if exists.
l / <Right> / <CR> :Open item or change directory.
gg                 :Go to the top.
G                  :Go to the bottom.
z<CR>              :Go to the home directory.
z {keyword}<CR>    :Jump to a directory that matches the keyword.
                    (zoxide required)
<C-o>              :Jump backward.
<C-i>              :Jump forward.
i{file name}<CR>   :Create a new empty file.
I{dir name}<CR>    :Create a new empty directory.
o                  :Open item in a new window.
e                  :Unpack archive/compressed file.
dd                 :Delete and yank item.
yy                 :Yank item.
p                  :Put yanked item(s) from register zero
                    in the current directory.
:reg               :Show registers. To hide it, press v.
\"ayy               :Yank item to register a.
\"add               :Delete and yank item to register a.
\"Ayy               :Append item to register a.
\"Add               :Delete and append item to register a.
\"ap                :Put item(s) from register a.
V                  :Switch to the linewise visual mode.
  - y              :In the visual mode, yank selected item(s).
  - d              :In the visual mode, delete and yank selected item(s).
  - \"ay            :In the visual mode, yank items to register a.
  - \"ad            :In the visual mode, delete and yank items to register a.
  - \"Ay            :In the visual mode, append items to register a.
  - \"Ad            :In the visual mode, delete and append items to register a.
  - c              :Rename selected items in default editor.
u                  :Undo put/delete/rename.
<C-r>              :Redo put/delete/rename.
v                  :Toggle whether to show the preview.
s                  :Toggle between vertical / horizontal split in the preview mode.
<Alt-j>
 / <Alt-<Down>>    :Scroll down the preview text.
<Alt-k> 
 / <Alt-<Up>>      :Scroll up the preview text.
<BS>               :Toggle whether to show hidden items.
t                  :Toggle the sort order (name <-> modified time).
c                  :Switch to the rename mode.
/{keyword}         :Search items by a keyword.
n                  :Go forward to the item that matches the keyword.
N                  :Go backward to the item that matches the keyword.
:                  :Switch to the command line.
  - <C-r>a         :In the command line, paste item name in register a.
:cd<CR>            :Go to the home directory.
:cd {path}<CR>     :Go to the path.
:e<CR>             :Reload the current directory.
:config<CR>        :Go to the directory that contains the config file if exists.
:trash<CR>         :Go to the trash directory.
:empty<CR>         :Empty the trash directory.
:h<CR>             :Show help.
:q<CR>             :Exit.
:{command}         :Execute a command e.g. :zip test *.md
<Esc>              :Return to the normal mode.
<C-h>              :Works as Backspace after `i`, `I`, `c`, `/`, `:` and `z`.
ZZ                 :Exit without cd to last working directory
                    (if `match_vim_exit_behavior` is `false`).
ZQ                 :cd into the last working directory and exit
                    (if shell setting is ready and `match_vim_exit_behavior is `false`).

## Preview feature
By default, text files and directories can be previewed.
To preview images, you need to install chafa (>= v1.10.0).
Please see https://hpjansson.org/chafa/

## Configuration

*Both `config.yaml` and `config.yml` work.*

### Linux
config file    : $XDG_CONFIG_HOME/felix/config.yaml(config.yml)
trash directory: $XDG_DATA_HOME/felix/trash
log files      : $XDG_DATA_HOME/felix/log

### macOS
On macOS, felix looks for the config file in the following locations:

1. `$HOME/Library/Application Support/felix/config.yaml(config.yml)`
2. `$HOME/.config/felix/config.yaml`

trash directory: $HOME/Library/Application Support/felix/trash
log files      : $HOME/Library/Application Support/felix/log

### Windows
config file     : $PROFILE\\AppData\\Roaming\\felix\\config.yaml(config.yml)
trash directory : $PROFILE\\AppData\\Local\\felix\\trash
log files       : $PROFILE\\AppData\\Local\\felix\\log

For more details, visit https://github.com/kyoheiu/felix
"""


def invoke(*args, cwd=None, env=None):
    e = os.environ.copy()
    if env:
        e.update(env)
    return subprocess.run([EXE, *map(str, args)], cwd=cwd, env=e,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def test_help_is_exact_for_both_spellings():
    for arg in ("-h", "--help"):
        p = invoke(arg)
        assert (p.returncode, p.stdout.decode(), p.stderr) == (0, HELP, b"")


def test_two_and_many_argument_help_dispatch():
    for args in (("--init", "extra"), ("--", "--help"), ("path", "--help"),
                 ("--badflag", "--help"), ("one", "two", "three")):
        p = invoke(*args)
        assert p.returncode == 0 and p.stdout.decode() == HELP and p.stderr == b""


def test_unknown_option_is_literal_invalid_path(tmp_path):
    arg = "--version"
    p = invoke(arg, cwd=tmp_path)
    assert p.returncode == 0
    assert p.stdout == b"\n"
    assert p.stderr.decode() == f"Invalid path: {arg}\n`fx -h` shows help.\n"


def test_invalid_and_nondirectory_diagnostics(tmp_path):
    missing = tmp_path / "missing"
    p = invoke(missing)
    assert (p.returncode, p.stdout, p.stderr.decode()) == (0, b"\n", f"Invalid path: {missing}\n`fx -h` shows help.\n")
    f = tmp_path / "plain"
    f.write_text("x")
    p = invoke(f)
    assert (p.returncode, p.stdout, p.stderr.decode()) == (0, b"", "Path should be directory.\n`fx -h` shows help.\n")


def test_symlink_to_file_is_nondirectory(tmp_path):
    f = tmp_path / "target"
    f.write_text("x")
    link = tmp_path / "link"
    link.symlink_to(f)
    p = invoke(link)
    assert p.returncode == 0 and p.stdout == b""
    assert p.stderr == b"Path should be directory.\n`fx -h` shows help.\n"


def test_valid_directory_without_tty_draws_then_reports_reader_error(tmp_path):
    p = invoke(tmp_path)
    assert p.returncode == 0
    assert p.stdout and (b"\x1b7" in p.stdout or b"\x1b[s" in p.stdout)
    assert b"\x1b[?25l" in p.stdout
    assert any(code in p.stdout for code in (b"\x1b[?1049h", b"\x1b[?47h"))
    assert b"\x1b[2J" in p.stdout
    assert p.stdout and p.stderr == b"Failed to initialize input reader\n"


def test_argument_errors_do_not_create_log_directories(tmp_path):
    data = tmp_path / "data"
    invoke("-l", str(tmp_path / "missing"), env={"XDG_DATA_HOME": str(data)})
    assert not (data / "felix" / "log").exists()


def test_dangling_path_is_invalid(tmp_path):
    link = tmp_path / "dangling"
    link.symlink_to(tmp_path / "absent")
    p = invoke(link)
    assert p.returncode == 0 and p.stdout == b"\n"
    assert p.stderr.decode() == f"Invalid path: {link}\n`fx -h` shows help.\n"


def test_init_emits_shell_initializer():
    p = invoke("--init")
    assert p.returncode == 0 and p.stderr == b""
    out = p.stdout.decode()
    assert out.startswith('# To be eval\'ed in the calling shell\n  eval "$(\n')
    assert 'runtime_dir="$XDG_RUNTIME_DIR/felix"' in out
    assert 'runtime_dir="$TMPDIR/felix"' in out
    assert "runtime_dir=/tmp/felix" in out
    assert 'find "$runtime_dir" -type f -and -mmin +1 -delete' in out
    assert 'SHELL_PID=\\$\\$ command fx "\\$@"' in out
    assert 'cd "\\$(cat "\\$RUNTIME_DIR/\\$\\$")"' in out
    assert out.endswith('  )"\n')


def test_config_parse_error_keeps_launching(tmp_path):
    cfg = tmp_path / "cfg" / "felix"
    cfg.mkdir(parents=True)
    (cfg / "config.yaml").write_text("default: nvim\nmalformed yaml: [this is not closed\nignore_case: true\n")
    p = invoke(tmp_path, env={"XDG_CONFIG_HOME": str(tmp_path / "cfg")})
    assert p.returncode == 0
    assert p.stderr.decode() == (
        "Cannot read the config file properly.\n"
        "Error: did not find expected ',' or ']' at line 3 column 12, while parsing a flow sequence at line 2 column 17\n"
        "felix launches with default configuration.\n"
        "Failed to initialize input reader\n")


def test_duplicate_config_key_reports_parser_error(tmp_path):
    cfg = tmp_path / "cfg" / "felix"
    cfg.mkdir(parents=True)
    (cfg / "config.yml").write_text("default: vim\ndefault: nvim\n")
    p = invoke(tmp_path, env={"XDG_CONFIG_HOME": str(tmp_path / "cfg")})
    assert p.returncode == 0
    assert p.stderr.startswith(b"Cannot read the config file properly.\nError: duplicate field `default`\n")
    assert p.stderr.endswith(b"Failed to initialize input reader\n")


def test_help_does_not_contain_subcommand_language():
    p = invoke("--help")
    assert b"subcommand" not in p.stdout.lower()
    assert b"Commands:" not in p.stdout


def test_log_option_treats_second_argument_as_literal_path(tmp_path):
    p = invoke("-l", "--help", cwd=tmp_path)
    assert p.returncode == 0 and p.stdout == b"\n"
    assert p.stderr == b"Invalid path: --help\n`fx -h` shows help.\n"


def test_single_unknown_options_are_paths(tmp_path):
    for token in ("-", "--", "-H", "-L", "--INIT", "-hl", "--log=/tmp", "version"):
        p = invoke(token, cwd=tmp_path)
        assert p.returncode == 0 and p.stdout == b"\n"
        assert p.stderr == f"Invalid path: {token}\n`fx -h` shows help.\n".encode()


def test_undecodable_linux_path_has_documented_panic(tmp_path):
    if not os.name == "posix" or not pathlib.Path("/proc").exists():
        return
    bad = os.fsencode(tmp_path) + b"/bad-\xff"
    p = subprocess.run([EXE.encode(), bad], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert p.returncode == 101 and p.stdout == b""
    err = p.stderr.decode("utf-8", "replace")
    assert "Result::unwrap()" in err and "bad-\\xFF" in err
    assert err.rstrip().endswith("note: run with `RUST_BACKTRACE=1` environment variable to display a backtrace")
