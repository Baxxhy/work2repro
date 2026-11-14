import json
import os
from pathlib import Path

import pytest


def test_version_help_and_parser(run):
    v = run(["--version"])
    assert v.returncode == 0 and v.stdout == b"DataSurgeon: https://github.com/Drew-Alleman/DataSurgeon 1.2.8\n" and not v.stderr
    h = run(["-h"])
    assert h.returncode == 0 and b"Usage: executable [OPTIONS]" in h.stdout and b"--email" in h.stdout
    assert not any(x in h.stdout for x in (b"Commands:", b"Subcommands:", b"[COMMAND]", b"<COMMAND>"))
    assert run(["--bogus"]).returncode == 2
    assert run(["--bogus"]).stdout == b""
    for opt, label in [("-f", "--file <file>"), ("-o", "--output <output>"),
                       ("--filter", "--filter <filter>"), ("--drop", "--drop <drop>")]:
        p = run([opt]); assert p.returncode == 2 and label.encode() in p.stderr and b"For more information" in p.stderr
    assert run(["--bogus", "--help"]).returncode == 0
    assert run(["--", "--help"]).returncode == 2


def test_stdin_banner_suppress_and_empty(run):
    p = run([], b"")
    assert p.returncode == 0 and p.stdout.startswith(b"[*] Reading standard input.")
    assert run(["-S"], b"").stdout == b""
    assert run(["-S", "-e"], b"nothing here\n").stdout == b""


def test_email_output_format_and_clusters(run):
    s = "User.Name+tag@subdomain.domain.co.uk"
    p = run(["-eCSl"], f"{s}\n".encode())
    assert p.returncode == 0 and p.stdout == f"{s}, line: 1\n".encode()
    p = run(["-e", "--hide", "--display", "--line", "-S"], f"{s}\n".encode())
    assert p.stdout == f"file:  {s}, line: 1\n".encode()
    assert run(["-e", "-C", "-S"], b"@domain.com user@sub_domain.com user@x.local\n").stdout == b""
    assert run(["-e", "-CT", "-S"], b"a@example.com and b@example.org\n").stdout == b"email: a@example.com\nemail: b@example.org\n"


@pytest.mark.parametrize("selector,payload,expected", [
    ("-i", "255.255.255.255", "255.255.255.255"),
    ("-i", "999.999.999.999", None),
    ("-6", "2001:db8::1", "2001:db8"),
    ("-m", "Aa:Bb:Cc:Dd:Ee:Ff", "Aa:Bb:Cc:Dd:Ee:Ff"),
    ("-p", "123-456-7890", None),
    ("-p", "+1-212-555-1234", "212-555-1234"),
    ("-c", "4532-1234-5678-9012", "4532-1234-5678-9012"),
    ("-s", "000-45-6789", "000-45-6789"),
    ("-b", "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"),
    ("-a", "aws_access_key_id=AKIAIOSFODNN7EXAMPLE", "aws_access_key_id=AKIAIOSFODNN7EXAMPLE"),
    ("-g", '"private_key_id": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"', '"private_key_id": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"'),
    ("-d", "prefix _s._t.d IN SRV 1 1 1 h suffix", "prefix _s._t.d IN SRV 1 1 1 h suffix"),
])
def test_extractor_examples(run, selector, payload, expected):
    p = run([selector, "-C", "-S"], (payload + "\n").encode())
    assert p.returncode == 0
    if expected is None:
        assert p.stdout == b""
    else:
        names = {"-i":"ip_address", "-6":"ipv6_address", "-m":"mac_address", "-p":"phone_number", "-c":"credit_card", "-s":"social_security", "-b":"bitcoin_wallet", "-a":"aws_keys", "-g":"google", "-d":"srv_dns"}
        assert p.stdout.decode() == f"{names[selector]}: {expected}\n"


def test_hash_boundaries_and_url_filename(run):
    valid = "a" * 32
    assert run(["-H", "-C", "-S"], (valid+" "+"b"*33+"\n").encode()).stdout == f"hashes: {valid}\n".encode()
    p = run(["-u", "-C", "-S"], b"https://api.example.com:8443/path now\n")
    assert p.stdout == b"url: https://api.example.com\n"
    assert run(["-F", "-C", "-S"], b"document.pdf\n").stdout == b"files: document.pdf\n"
    assert run(["-F", "-C", "-S"], b"mail user@example.com 1.2.3.4\n").stdout == b""


def test_filters_drops_and_first_survivor(run):
    p = run(["-e", "-C", "-S", "--filter", "(?i)@EXAMPLE\\.COM", "--drop", "^short"], b"short@x.io long@example.com\n")
    assert p.stdout == b"email: long@example.com\n"
    p = run(["-c", "-C", "-S", "--drop", "3456"], b"4532123456789012 and 5425233430109903\n")
    assert p.stdout == b"credit_card: 5425233430109903\n"
    assert run(["-e", "-C", "-S", "--drop", ".*"], b"a@example.com\n").stdout == b""
    for regex, reason in [("[unclosed", "unclosed character class"), ("(?invalid)", "unrecognized flag")]:
        p = run(["-e", "--filter", regex, "--ignore"], b"a@example.com\n")
        assert p.returncode == 101 and b"regex parse error" in p.stderr and reason.encode() in p.stderr


def test_thorough_record_pairs_and_duplicate_handling(run):
    p = run(["-e", "-T", "-S"], b"a@example.com then b@example.org\n")
    assert p.stdout == b"email: a@example.com then b@example.org\nemail: a@example.com\nemail: a@example.com then b@example.org\nemail: b@example.org\n"
    p = run(["-e", "-CT", "-S"], b"a@example.com a@example.com\n")
    assert p.stdout == b"email: a@example.com\n"


def test_files_directory_lines_and_invalid_utf8(run, tmp_path):
    f = tmp_path / "input"
    f.write_bytes(b"before@example.com\ninvalid\xffx@example.com\nnull\x00x@example.com\nafter@example.org")
    p = run(["-f", f, "-e", "-C", "-l"], cwd=tmp_path)
    assert p.stdout == b"email, before@example.com, line: 1\nemail, x@example.com, line: 2\nemail, after@example.org, line: 3\n"
    tree = tmp_path / "tree"; (tree / "a" / "b" / "c" / "d" / "e").mkdir(parents=True)
    (tree / ".hidden").write_text("one@example.com\n", encoding="utf-8")
    (tree / "a" / "b" / "c" / "d" / "e" / "plain").write_text("two@example.org\n", encoding="utf-8")
    p = run(["--directory", tree, "-e", "-C", "-T", "-S"], cwd=tmp_path)
    assert b"one@example.com" in p.stdout and b"two@example.org" in p.stdout


def test_output_append_csv_timing_and_failures(run, tmp_path):
    f = tmp_path / "source"; f.write_text("x@example.com\n", encoding="utf-8")
    out = tmp_path / "records.csv"
    assert run(["-f", f, "-e", "-C", "-o", out]).returncode == 0
    assert out.read_text() == "content_type, data\nemail, x@example.com\n"
    run(["-f", f, "-e", "-C", "-o", out])
    assert out.read_text().count("content_type, data") == 2
    p = run(["-f", f, "-t"]); assert b"[*] Time elapsed: 00h:00m:00s\n" in p.stdout
    p = run(["-f", tmp_path / "missing"]); assert p.returncode == 1 and p.stdout == f"[-] File not found: {tmp_path / 'missing'}\n".encode() and not p.stderr
    p = run(["-f", f, "-e", "-o", tmp_path / "absent" / "out"])
    assert p.returncode == 1 and b"Failed to open output file:" in p.stdout


def test_plugin_pipeline_and_remove(run, envdir, tmp_path):
    plugin_file = envdir / ".DataSurgeon" / "plugins.json"
    plugin_file.write_text(json.dumps([{"content_type":"numbers", "arg_long_name":"numbers", "help_message":"numbers", "regex":"number=(\\d+)", "version":"1", "source_url":"https://example.test/repo/", "extra":1}]), encoding="utf-8")
    p = run(["--numbers", "-C", "-S"], b"number=123\n")
    assert p.stdout == b"numbers: number=123\n"
    p = run(["--remove", "http://example.test/repo"])
    assert p.returncode == 1 and p.stdout == b"[*] Removed plugin: http://example.test/repo\n"
    assert json.loads(plugin_file.read_text()) == []
