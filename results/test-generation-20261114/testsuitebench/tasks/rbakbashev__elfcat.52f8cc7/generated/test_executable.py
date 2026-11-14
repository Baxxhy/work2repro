import struct
import subprocess
from pathlib import Path

import pytest


E = Path('/workspace/executable')
USAGE = 'Usage: elfcat <filename>\nWrites <filename>.html to CWD.\n'
GOLDEN = Path(__file__).with_name('canonical-minimal32.html').read_bytes()


def invoke(cwd, *args):
    return subprocess.run([str(E), *map(str, args)], cwd=cwd, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True)


def elf(bits=32, endian='<', *, typ=2, machine=3, entry=0, osabi=0, abiver=0,
        version=1, flags=0, phoff=None, phnum=0, phentsize=None,
        shoff=None, shnum=0, shentsize=None, shstr=0, tail=b''):
    cls = 1 if bits == 32 else 2
    ident = b'\x7fELF' + bytes([cls, 1 if endian == '<' else 2, version, osabi, abiver]) + b'\0' * 7
    if bits == 32:
        phoff = 52 if phoff is None else phoff
        shoff = 52 if shoff is None else shoff
        phentsize = 32 if phentsize is None else phentsize
        shentsize = 40 if shentsize is None else shentsize
        hdr = struct.pack(endian+'HHIIIIIHHHHHH', typ,machine,1,entry,phoff,shoff,flags,52,phentsize,phnum,shentsize,shnum,shstr)
    else:
        phoff = 64 if phoff is None else phoff
        shoff = 64 if shoff is None else shoff
        phentsize = 56 if phentsize is None else phentsize
        shentsize = 64 if shentsize is None else shentsize
        hdr = struct.pack(endian+'HHIQQQIHHHHHH', typ,machine,1,entry,phoff,shoff,flags,64,phentsize,phnum,shentsize,shnum,shstr)
    return ident + hdr + tail


def report(tmp_path, name, data):
    p = tmp_path / name
    p.write_bytes(data)
    result = invoke(tmp_path, name)
    assert result.returncode == 0 and result.stdout == '' and result.stderr == ''
    return (tmp_path / (Path(name).name + '.html')).read_text()


def test_help_and_version_are_exact_and_quiet(tmp_path):
    for arg, expected in [('-h', USAGE), ('--help', USAGE), ('-v', 'elfcat 0.1.10\n'), ('--version', 'elfcat 0.1.10\n')]:
        p = invoke(tmp_path, arg)
        assert (p.returncode, p.stdout, p.stderr) == (0, expected, '')
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('args', [(), ('x','y'), ('--help','extra'), ('--version','extra')], ids=['none','two','help-extra','version-extra'])
def test_arity_errors(tmp_path, args):
    p = invoke(tmp_path, *args)
    assert (p.returncode, p.stdout, p.stderr) == (1, USAGE, '')
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize('name', ['missing', '-'])
def test_read_errors_are_reported_without_output_file(tmp_path, name):
    p = invoke(tmp_path, name)
    assert p.returncode == 1 and p.stdout == ''
    assert p.stderr == f'Failed to read file "{name}": No such file or directory (os error 2)\n'
    assert not (tmp_path / (name + '.html')).exists()


def test_directory_read_error(tmp_path):
    (tmp_path/'dir').mkdir()
    p = invoke(tmp_path, 'dir')
    assert p.returncode == 1 and p.stdout == ''
    assert p.stderr == 'Failed to read file "dir": Is a directory (os error 21)\n'


@pytest.mark.parametrize('data, message', [
    (b'', "Failed to parse ELF: file is smaller than ELF header's e_ident\n"),
    (b'X'*16, 'Failed to parse ELF: mismatched magic: not an ELF file\n'),
    (b'\x7fELF'+bytes([3])+b'\0'*11, 'Failed to parse ELF: Unknown bitness: 3\n'),
    (b'\x7fELF'+bytes([1,3])+b'\0'*10, 'Failed to parse ELF: Unknown endianness: 3\n'),
    (b'\x7fELF'+bytes([1,1])+b'\0'*10, "Failed to parse ELF: file is smaller than ELF file header\n"),
], ids=['short-ident','magic','class','data','short-header'])
def test_identification_parse_errors(tmp_path, data, message):
    (tmp_path/'bad').write_bytes(data)
    p = invoke(tmp_path, 'bad')
    assert p.returncode == 1 and p.stdout == '' and p.stderr == message
    assert not (tmp_path/'bad.html').exists()


def test_minimal32_complete_serialization_vector(tmp_path):
    data = bytes.fromhex('7f454c460101010000000000000000000200030001000000008004083400000000000000000000003400200001002800000000000100000000000000008004080080040810000000100000000500000004000000')
    (tmp_path/'minimal32.elf').write_bytes(data)
    p = invoke(tmp_path, 'minimal32.elf')
    assert (p.returncode, p.stdout, p.stderr) == (0, '', '')
    assert (tmp_path/'minimal32.elf.html').read_bytes() == GOLDEN


def test_literal_names_basename_and_output_replacement(tmp_path):
    (tmp_path/'inputs').mkdir()
    (tmp_path/'inputs'/'quo\'te').write_bytes(elf())
    out = report(tmp_path, "inputs/quo'te", elf())
    assert "<title>quo'te</title>" in out
    assert "inputs/quo'te" in out
    assert not (tmp_path/'inputs'/'quo\'te.html').exists()
    target = tmp_path/'dots.v1.elf'
    target.write_bytes(elf())
    old = tmp_path/'dots.v1.elf.html'
    old.write_text('stale trailing content')
    p = invoke(tmp_path, 'dots.v1.elf')
    assert p.returncode == 0 and p.stdout == '' and p.stderr == ''
    assert b'stale trailing content' not in old.read_bytes()


def test_symlink_uses_link_name(tmp_path):
    (tmp_path/'real.bin').write_bytes(elf())
    (tmp_path/'alias.elf').symlink_to(tmp_path/'real.bin')
    out = report(tmp_path, 'alias.elf', elf())
    assert '<title>alias.elf</title>' in out and 'alias.elf.html' in str(tmp_path)


def test_metadata_endianness_types_and_numeric_tooltips(tmp_path):
    out = report(tmp_path, 'be', elf(64, '>', typ=0xff00, machine=62, entry=0x10000000, flags=0x1234, osabi=3, abiver=2))
    assert 'Processor-specific use' in out and 'x86-64' in out and 'Linux' in out
    assert 'Uncommon ABI version(!)' in out and '0x10000000' in out
    assert '0x1234' in out and "title='4660'" in out
    assert '00 02' in out and '00 3e' in out
    assert 'fileinfo_e_flags' in out


def test_html_template_dump_and_interaction_contract(tmp_path):
    out = report(tmp_path, 'template', elf())
    assert out.startswith("<!doctype html>\n<html>\n  <head>\n")
    assert out.endswith('    </script>\n  </body>\n</html>\n')
    for token in ["id='offsets'", "id='bytes'", "id='ascii'", "id='sticky_table'", "id='arrowhead'", "id='arrows'",
                  'function highlightClasses(primaryClass, secondaryClass)', 'function showIfMatches(cl, prefix, newPrefix, indirect = false)',
                  'function hidePreviousTables()', 'populateOffsets(columns)', 'let fileLen = 84', 'ELF Identification',
                  'font-family: monospace;', 'The leftmost column shows offsets within the file.']:
        assert token in out
    assert out.count('<html>') == out.count('</html>') == 1


def test_program_and_section_tables_decode_fields(tmp_path):
    ph = struct.pack('<IIIIIIII', 1, 0, 0x8048000, 0, 4, 8, 5, 0x1000)
    sh = struct.pack('<IIIIIIIIII', 0, 1, 6, 0x8048000, 84, 4, 0, 0, 4, 0)
    data = elf(phoff=52, phnum=1, shoff=84, shnum=1, tail=ph+sh+b'abcd')
    out = report(tmp_path, 'tables', data)
    for token in ["id='info_phdr0'", "id='info_segment0'", "id='info_shdr0'", "id='info_section0'",
                  "<td>LOAD</td>", '<td>RX</td>', 'bin_phdr0 phdr', 'bin_shdr0 shdr',
                  'bin_segment0 segment', 'bin_section0 section hover', 'PROGBITS', '<td>WAX</td>']:
        assert token in out


def test_section_names_and_strings_are_rendered(tmp_path):
    names = b'\0.text\0.shstrtab\0'
    base_off = 52
    shoff = base_off + len(names)
    null = bytes(40)
    text = struct.pack('<IIIIIIIIII', 1,1,6,0,base_off,4,0,0,1,0)
    strings = struct.pack('<IIIIIIIIII', 7,3,0,0,base_off,len(names),0,0,1,0)
    data = elf(shoff=shoff, shnum=3, shstr=2, tail=names+null+text+strings)
    out = report(tmp_path, 'strings', data)
    assert '<td>.text</td>' in out and '<td>.shstrtab</td>' in out
    assert '.text' in out and '.shstrtab' in out


@pytest.mark.parametrize('bits, length', [(32,84),(64,120)], ids=['elf32','elf64'])
def test_truncated_nonempty_program_table_panics_without_report(tmp_path, bits, length):
    data = elf(bits, phoff=length-1, phnum=1, tail=b'')
    (tmp_path/'panic').write_bytes(data)
    p = invoke(tmp_path, 'panic')
    assert p.returncode == 101 and p.stdout == '' and p.stderr
    assert not (tmp_path/'panic.html').exists()


def test_zero_entrypoint_and_size_formatting(tmp_path):
    out = report(tmp_path, 'zero', elf(entry=0))
    assert "<td title='0'>0x0</td>" in out
    data = elf() + b'X' * (1024-52)
    out = report(tmp_path, 'kilobyte', data)
    assert '1.0 KiB (1024 B)' in out


def test_ascii_column_escapes_input_metacharacters(tmp_path):
    data = elf() + b'<>&\"\'\x20'
    out = report(tmp_path, 'ascii', data)
    assert '&lt;&gt;&amp;&quot;&apos;.' in out
