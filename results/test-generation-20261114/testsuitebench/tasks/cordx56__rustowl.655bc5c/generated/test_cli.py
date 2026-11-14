import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
EXE = Path('/workspace/executable')
FIX = ROOT / 'exact-output'
TOP_HELP = ("Usage: executable [OPTIONS] [COMMAND]\n\nCommands:\n  check        Check availability\n  clean        Remove artifacts from the target directory\n  toolchain    Install or uninstall the toolchain\n  completions  Generate shell completions\n  help         Print this message or the help of the given subcommand(s)\n\nOptions:\n  -V, --version   Print version\n  -q, --quiet...  Suppress output\n      --stdio     Use stdio to communicate with the LSP server\n  -h, --help      Print help\n").encode()
CHECK_HELP = ("Check availability\n\nUsage: executable check [OPTIONS] [path]\n\nArguments:\n  [path]  The path of a file or directory to check availability\n\nOptions:\n      --all-targets   Run the check for all targets instead of current only\n      --all-features  Run the check for all features instead of the current active ones only\n  -h, --help          Print help\n").encode()
CLEAN_HELP = ("Remove artifacts from the target directory\n\nUsage: executable clean\n\nOptions:\n  -h, --help  Print help\n").encode()
TOOL_HELP = ("Install or uninstall the toolchain\n\nUsage: executable toolchain [COMMAND]\n\nCommands:\n  install    Install the toolchain\n  uninstall  Uninstall the toolchain\n  help       Print this message or the help of the given subcommand(s)\n\nOptions:\n  -h, --help  Print help\n").encode()
INSTALL_HELP = ("Install the toolchain\n\nUsage: executable toolchain install [OPTIONS]\n\nOptions:\n      --path <path>             Runtime directory path to install RustOwl toolchain\n      --skip-rustowl-toolchain  Install Rust toolchain only\n  -h, --help                    Print help\n").encode()
UNINSTALL_HELP = ("Uninstall the toolchain\n\nUsage: executable toolchain uninstall\n\nOptions:\n  -h, --help  Print help\n").encode()
COMPLETION_HELP = ("Generate shell completions\n\nUsage: executable completions <SHELL>\n\nArguments:\n  <SHELL>\n          The shell to generate completions for\n\n          Possible values:\n          - bash:       Bourne Again `SHell` (bash)\n          - elvish:     Elvish shell\n          - fish:       Friendly Interactive `SHell` (fish)\n          - powershell: `PowerShell`\n          - zsh:        Z `SHell` (zsh)\n          - nushell:    Nushell\n\nOptions:\n  -h, --help\n          Print help (see a summary with '-h')\n").encode()


def run(*args, cwd=None, home=None, env=None, timeout=20):
    e = os.environ.copy()
    e.update({'RUST_LOG': 'off'})
    if home is not None:
        e['HOME'] = str(home)
    if env:
        e.update(env)
    return subprocess.run([str(EXE), *args], cwd=cwd, env=e, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, timeout=timeout)


def succeeds(p, out=b''):
    assert p.returncode == 0
    assert p.stdout == out
    assert p.stderr == b''


def fixture(relative):
    return (FIX / relative).read_bytes()


@pytest.mark.parametrize('args,expected', [
    (['--version'], b'RustOwl v1.0.0-rc.1\n'), (['-V'], b'RustOwl v1.0.0-rc.1\n'),
    (['-q', '--version'], b'v1.0.0-rc.1\n'), (['--quiet', '-V'], b'v1.0.0-rc.1\n'),
    (['-qV'], b'v1.0.0-rc.1\n'), (['-Vq'], b'v1.0.0-rc.1\n'),
    (['-qqqV'], b'v1.0.0-rc.1\n'), (['-Vqqq'], b'v1.0.0-rc.1\n'), (['-qqVq'], b'v1.0.0-rc.1\n'),
], ids=['long-version','short-version','quiet-long','quiet-short','combined-qv','combined-vq','repeated-before','repeated-after','mixed-combined'])
def test_version_forms(args, expected):
    succeeds(run(*args), expected)


def test_version_clean_special_route():
    succeeds(run('--version', 'clean'))


@pytest.mark.parametrize('args', [['--help'], ['-h'], ['help'], ['--help','--version'], ['--version','--help'], ['-qq','--stdio','--help','--bogus']], ids=['long','short','pseudo','help-first','version-first','help-over-invalid'])
def test_top_help(args):
    succeeds(run(*args), TOP_HELP)


@pytest.mark.parametrize('args,expected', [
    (['check','--help'], CHECK_HELP), (['check','-h'], CHECK_HELP), (['help','check'], CHECK_HELP),
    (['clean','--help'], CLEAN_HELP), (['clean','-h'], CLEAN_HELP), (['help','clean'], CLEAN_HELP),
    (['toolchain','--help'], TOOL_HELP), (['help','toolchain'], TOOL_HELP),
    (['toolchain','install','--help'], INSTALL_HELP), (['help','toolchain','install'], INSTALL_HELP),
    (['toolchain','uninstall','--help'], UNINSTALL_HELP), (['help','toolchain','uninstall'], UNINSTALL_HELP),
    (['completions','--help'], COMPLETION_HELP), (['help','completions'], COMPLETION_HELP),
], ids=['check-long','check-short','help-check','clean-long','clean-short','help-clean','toolchain-long','help-toolchain','install-long','help-install','uninstall-long','help-uninstall','completions-long','help-completions'])
def test_command_help(args, expected):
    succeeds(run(*args), expected)


def test_toolchain_bare_is_silent_noop():
    succeeds(run('toolchain'))


@pytest.mark.parametrize('shell', ['bash','elvish','fish','powershell','zsh','nushell'], ids=['bash','elvish','fish','powershell','zsh','nushell'])
def test_completion_is_exact_golden(shell, tmp_path):
    before = list(tmp_path.iterdir())
    p = run('-q','completions',shell,home=tmp_path,env={'RUSTOWL_CACHE':str(tmp_path/'cache'),'RUSTOWL_CACHE_DIR':str(tmp_path/'cache-dir')})
    succeeds(p, fixture(f'completions/{shell}.golden'))
    assert list(tmp_path.iterdir()) == before


@pytest.mark.parametrize('args,rel', [
    (['check','--unknown'],'errors/attributed/check_unknown.golden'),
    (['check','--unknown-flag'],'errors/attributed/check_unknown_flag.golden'),
    (['check',''],'errors/attributed/check_empty_path.golden'),
    (['check','--all-feature'],'errors/attributed/check_all_feature.golden'),
    (['check','--all-target'],'errors/attributed/check_all_target.golden'),
    (['check','--all-features','--all-targets','--unknown'],'errors/attributed/check_active_flags_unknown.golden'),
    (['check','-q'],'errors/attributed/check_quiet_after.golden'),
    (['completions',''],'errors/attributed/completions_empty_shell.golden'),
    (['completions'],'errors/output_format/completions_missing_arg.golden'),
    (['completions','--all-targets'],'errors/attributed/completions_check_flag.golden'),
    (['completions','ba$h'],'errors/attributed/completions_ba_dollar_h.golden'),
    (['completions','fihs'],'errors/attributed/completions_fihs.golden'),
    (['completions','PowerShell'],'errors/attributed/completions_PowerShell.golden'),
    (['completions','Nushell'],'errors/attributed/completions_Nushell.golden'),
    (['toolchain','install','--path','/tmp/runtime','--unknown-option'],'errors/attributed/toolchain_install_mixed_unknown.golden'),
    (['toolchain','install','--path','/tmp/one','--path','/tmp/two'],'errors/attributed/toolchain_install_path_repeated.golden'),
    (['--version','extra'],'errors/attributed/version_extra.golden'),
    (['-V','-V'],'errors/error_messages/version_short_repeated.golden'),
    (['check|grep'],'errors/error_messages/check_pipe_grep.golden'),
    (['help','unknown'],'errors/attributed/help_unknown.golden'),
    (['help','check','--unknown'],'errors/attributed/help_check_unknown.golden'),
    (['completions','bash','-q'],'errors/attributed/completions_bash_quiet_after.golden'),
    (['toolchain','instal'],'errors/attributed/toolchain_instal.golden'),
    (['toolchain','uninsta'],'errors/attributed/toolchain_uninsta.golden'),
    (['check','--invalid-flag'],'errors/output_format/check_invalid_flag.golden'),
    (['completions','unknown_shell'],'errors/shells/unknown_shell.golden'),
    (['completions','BASH'],'errors/shells/BASH.golden'),
    (['completions','Bash'],'errors/shells/Bash.golden'),
    (['completions','123'],'errors/shells/123.golden'),
    (['completions','bas'],'errors/shells/bas.golden'),
    (['completions','bas h'],'errors/shells/bas_space_h.golden'),
    (['completions','bash;'],'errors/shells/bash_semicolon.golden'),
    (['completions','/bin/bash'],'errors/shells/bin_bash.golden'),
    (['completions','bash🐚'],'errors/shells/bash_emoji.golden'),
    (['completions','bash\ntab'],'errors/shells/bash_newline_tab.golden'),
    (['completions','雪x'],'errors/shells/snow_x.golden'),
    (['toolchain','install','--path'],'errors/toolchain/install_path_missing.golden'),
    (['toolchain','install','--path='],'errors/toolchain/install_path_missing.golden'),
    (['toolchain','install','--path',''],'errors/toolchain/install_path_missing.golden'),
    (['toolchain','install','--skip-rustowl-toolchain=yes'],'errors/toolchain/install_skip_value.golden'),
], ids=[f'case-{i:02}' for i in range(40)])
def test_mapped_parser_diagnostics(args, rel):
    p = run(*args)
    assert p.returncode == 2
    assert p.stdout == b''
    assert p.stderr == fixture(rel)


@pytest.mark.parametrize('args,rel', [
    (['completions','BASH'],'errors/shells/BASH.golden'),
    (['completions','Bash'],'errors/shells/Bash.golden'),
    (['completions','bas'],'errors/shells/bas.golden'),
    (['completions','bas h'],'errors/shells/bas_space_h.golden'),
    (['completions','bash;'],'errors/shells/bash_semicolon.golden'),
    (['completions','123'],'errors/shells/123.golden'),
    (['completions','/bin/bash'],'errors/shells/bin_bash.golden'),
    (['completions','bash🐚'],'errors/shells/bash_emoji.golden'),
    (['completions','bash\ntab'],'errors/shells/bash_newline_tab.golden'),
    (['completions','雪x'],'errors/shells/snow_x.golden'),
], ids=['uppercase','mixed-case','partial','space','punctuation','numeric','path','emoji','newline','unicode'])
def test_shell_rejections(args, rel):
    p = run(*args)
    assert (p.returncode, p.stdout, p.stderr) == (2, b'', fixture(rel))
