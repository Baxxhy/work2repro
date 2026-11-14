import os
import pty
import select
import shutil
import struct
import subprocess
import tempfile
import time
import fcntl
import termios
import unittest


BIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "executable"))
HELP = """Usage: executable [OPTIONS]

Options:
  -n, --n <2|3|4|w|file>  use bi-(2), tri-(3), tetragrams(4), (w)ords or comma separated wordlist file. [default: 2]
  -t, --top <1-200>       use the top X ngrams ordered by usage. [default: 50]
  -c, --combi <1-200>     how many different ngrams to use in a single lesson. [default: 2]
  -r, --rep <number>      how often to repeat *each* different ngram in a lesson. [default: 3]
  -w, --wpm <number>      the wpm threshold at which the lesson is considered a success. [default: 40]
  -a, --acc <0-100>       the accuracy in percent at which the lesson is considered a success. [default: 94]
      --emu-in <layout>   your current keyboard layout. only needed if you want to emulate a different layout. see docs for supported layouts. [default: ]
      --emu-out <layout>  the layout you want to emulate. only needed if you want to emulate a different layout. see docs for supported layouts. [default: ]
      --show-ortho        show keyboard in ortholinear format
      --nokb              pass this flag to disable the keyboard layout display.
      --cat               the most important flag. don't practice alone.
  -h, --help              Print help
"""


def cli(*args):
    return subprocess.run([BIN, *map(str, args)], stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, timeout=3)


def tty_run(args, keys=b"\x1b", cols=80, wait=0.2):
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 24, cols, 0, 0))
    proc = subprocess.Popen([BIN, *args], stdin=slave, stdout=slave, stderr=slave,
                            close_fds=True)
    os.close(slave)
    out = bytearray()
    deadline = time.monotonic() + wait
    while time.monotonic() < deadline and proc.poll() is None:
        ready, _, _ = select.select([master], [], [], 0.03)
        if ready:
            try:
                out.extend(os.read(master, 65536))
            except OSError:
                break
    if proc.poll() is None and keys:
        os.write(master, keys)
    end = time.monotonic() + 1.2
    while time.monotonic() < end and proc.poll() is None:
        ready, _, _ = select.select([master], [], [], 0.04)
        if ready:
            try:
                out.extend(os.read(master, 65536))
            except OSError:
                break
    if proc.poll() is None:
        proc.kill()
    try:
        proc.wait(timeout=1)
    except subprocess.TimeoutExpired:
        pass
    try:
        while True:
            out.extend(os.read(master, 65536))
    except (OSError, BlockingIOError):
        pass
    os.close(master)
    return proc.returncode, bytes(out)


class HelpTests(unittest.TestCase):
    def test_help_long_exact(self):
        r = cli("--help")
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, HELP.encode(), b""))

    def test_help_short_exact(self):
        r = cli("-h")
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, HELP.encode(), b""))

    def test_help_precedes_later_bad_arguments(self):
        for args in (("--help", "--bogus"), ("--help", "--n", "3"), ("--n", "not-a-file", "--help")):
            with self.subTest(case=args):
                r = cli(*args)
                self.assertEqual(r.returncode, 0)
                self.assertEqual(r.stdout, HELP.encode())
                self.assertEqual(r.stderr, b"")


class ParserTests(unittest.TestCase):
    def test_unknown_option_format(self):
        r = cli("--version")
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, b"")
        self.assertEqual(r.stderr, b"error: unexpected argument '--version' found\n\nUsage: executable [OPTIONS]\n\nFor more information, try '--help'.\n")

    def test_missing_values_use_canonical_option_names(self):
        cases = [("-t", "--top <1-200>"), ("-c", "--combi <1-200>"), ("-r", "--rep <number>"),
                 ("-w", "--wpm <number>"), ("-a", "--acc <0-100>"), ("-n", "--n <2|3|4|w|file>"),
                 ("--emu-in", "--emu-in <layout>"), ("--emu-out", "--emu-out <layout>")]
        for opt, label in cases:
            with self.subTest(option=opt):
                r = cli(opt)
                self.assertEqual(r.returncode, 2)
                self.assertEqual(r.stderr, f"error: a value is required for '{label}' but none was supplied\n\nFor more information, try '--help'.\n".encode())

    def test_switch_rejects_value(self):
        r = cli("--cat=true")
        self.assertEqual(r.returncode, 2)
        self.assertIn(b"unexpected value 'true' for '--cat' found", r.stderr)

    def test_repeat_option_rejected(self):
        r = cli("--top", "2", "--top", "3")
        self.assertEqual(r.returncode, 2)
        self.assertIn(b"cannot be used multiple times", r.stderr)

    def test_positionals_and_double_dash_rejected(self):
        for args, token in [(("hello",), "hello"), (("--", "--help"), "--help"), (("--", "-n"), "-n")]:
            with self.subTest(args=args):
                r = cli(*args)
                self.assertEqual(r.returncode, 2)
                self.assertIn(f"unexpected argument '{token}' found".encode(), r.stderr)

    def test_noninteger_diagnostic(self):
        r = cli("--top=abc")
        self.assertEqual(r.returncode, 2)
        self.assertIn(b"invalid value 'abc' for '--top <1-200>': invalid digit found in string", r.stderr)

    def test_negative_separated_is_unexpected(self):
        r = cli("--acc", "-1")
        self.assertEqual(r.returncode, 2)
        self.assertIn(b"unexpected argument '-1' found", r.stderr)

    def test_short_value_spellings_and_interleaving_start_tui(self):
        for args in (("-t", "1", "-c", "1"), ("-t1", "-c=1", "--nokb"), ("--top=1", "-c", "1", "--nokb")):
            with self.subTest(args=args):
                rc, out = tty_run(list(args), wait=0.25)
                self.assertIn(b"Lesson", out)
                self.assertEqual(rc, 0)


class RangeTests(unittest.TestCase):
    def test_range_errors_exact(self):
        cases = [("--top=0", "top", 0, 200), ("-c=201", "combi", 1, 200),
                 ("--rep=0", "rep", 1, 200), ("-w=201", "wpm", 1, 200), ("--acc=101", "acc", 0, 100)]
        for arg, name, lo, hi in cases:
            with self.subTest(arg=arg):
                r = cli(arg)
                self.assertEqual(r.returncode, 1)
                self.assertEqual(r.stdout, f"Invalid argument for {name}. Use a number between {lo} and {hi}.\n".encode())
                self.assertEqual(r.stderr, b"")

    def test_first_invalid_in_documented_order(self):
        r = cli("--acc=150", "--wpm=0", "--combi=0", "--rep=0", "--top=201")
        self.assertEqual(r.stdout, b"Invalid argument for top. Use a number between 1 and 200.\n")
        r = cli("--acc=150", "--wpm=0")
        self.assertEqual(r.stdout, b"Invalid argument for wpm. Use a number between 1 and 200.\n")

    def test_emulation_pair_rule(self):
        r = cli("--emu-in=qwerty")
        self.assertEqual((r.returncode, r.stdout, r.stderr), (1, b"You need to specify both emu_in and emu_out.\n", b""))


class SourceTests(unittest.TestCase):
    def test_missing_file_echoes_path(self):
        path = "/tmp/typing-suite-missing-file"
        try: os.unlink(path)
        except FileNotFoundError: pass
        r = cli("--n", path)
        self.assertEqual((r.returncode, r.stdout, r.stderr), (1, f"File not found: {path}\n".encode(), b""))

    def test_empty_file_is_accepted_for_help(self):
        with tempfile.NamedTemporaryFile(dir=os.path.dirname(__file__)) as f:
            r = cli("--n", f.name, "--help")
            self.assertEqual((r.returncode, r.stdout), (0, HELP.encode()))

    def test_valid_modes_and_layout_pairs_reach_tui(self):
        combos = [["-n", source, "--nokb"] for source in ("2", "3", "4", "w")]
        combos += [["--emu-in", a, "--emu-out", b, "--nokb"] for a, b in (("qwerty", "qwerty"), ("qwertz", "azerty"), ("dvorak", "colemak"), ("UNKNOWN", "dvorak"))]
        combos += [["--top=1", "--combi=200", "--rep=200", "--wpm=1", "--acc=0", "--nokb"]]
        for args in combos:
            with self.subTest(args=args):
                rc, out = tty_run(args, wait=0.18)
                self.assertIn(b"Lesson", out)
                self.assertNotEqual(rc, 2)

    def test_custom_wordlist_preserves_content_and_top(self):
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=os.path.dirname(__file__)) as f:
            f.write("café,hello world,naïve\n日本語, 中文,")
            f.flush()
            rc, out = tty_run(["-n", f.name, "--top", "1", "--combi", "1", "--rep", "1", "--nokb"], wait=0.2)
        self.assertEqual(rc, 0)
        self.assertIn("café".encode(), out)
        self.assertNotIn(b"hello world", out)

    def test_nonempty_custom_file_starts_and_all_commas_do_not_crash(self):
        for content in ("alpha,beta,gamma", ",,,"):
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=os.path.dirname(__file__)) as f:
                f.write(content); f.flush()
                rc, out = tty_run(["--n", f.name, "--nokb"], wait=0.2)
            self.assertIn(b"Lesson", out)
            self.assertNotEqual(rc, 2)


class TuiTests(unittest.TestCase):
    def test_unusable_terminal_word_mode_exact_failure(self):
        r = subprocess.run([BIN, "-n", "w"], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=2)
        self.assertEqual(r.returncode, 1)
        self.assertEqual(r.stdout, b"\x1b[?1049h")
        self.assertEqual(r.stderr, b'Error: Os { code: 6, kind: Uncategorized, message: "No such device or address" }\n')

    def test_tui_draws_panel_keyboard_and_exact_single_pool_lesson(self):
        rc, out = tty_run(["--top", "1", "--combi", "1", "--rep", "3"], wait=0.25)
        self.assertEqual(rc, 0)
        self.assertIn("Lesson #1".encode(), out)
        self.assertIn("ngr rram!".replace(" ", "").encode(), out)  # title may be split by terminal positioning
        self.assertIn("need >=  40WPM".encode(), out)
        self.assertIn("th th th".encode(), out)
        self.assertIn(b"\x1b[?1049h", out)

    def test_nokb_suppresses_keyboard_but_keeps_panel(self):
        rc, out = tty_run(["--nokb"], wait=0.22)
        self.assertEqual(rc, 0)
        self.assertIn(b"Lesson #1", out)
        self.assertIn(b"need >=", out)
        self.assertNotIn("┌───┬".encode(), out)

    def test_ortholinear_and_cat_render(self):
        for args, needles in [(["--show-ortho"], ["△".encode(), "┼".encode()]), (["--cat"], ["(•༝• )".encode()])]:
            rc, out = tty_run(args, wait=0.25)
            self.assertEqual(rc, 0)
            for needle in needles: self.assertIn(needle, out)

    def test_input_error_backspace_and_completion_redraw(self):
        rc, out = tty_run(["--top", "1", "--combi", "1", "--rep", "1", "--nokb"], keys=b"xxx\x7fth \x1b", wait=0.18)
        self.assertEqual(rc, 0)
        self.assertIn(b"xxx", out)
        self.assertIn(b"Lesson #2", out)

    def test_escape_exits_cleanly(self):
        rc, out = tty_run(["--nokb"], keys=b"\x1b", wait=0.2)
        self.assertEqual(rc, 0)
        self.assertIn(b"\x1b[?1049h", out)


if __name__ == "__main__":
    unittest.main()
