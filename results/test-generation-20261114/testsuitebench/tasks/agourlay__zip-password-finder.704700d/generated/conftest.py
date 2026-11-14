import binascii
import struct
import zlib
from pathlib import Path
import pytest

def _zipcrypto_archive(path, entries, password):
    key0, key1, key2 = 0x12345678, 0x23456789, 0x34567890
    def update_keys(byte):
        nonlocal key0, key1, key2
        key0 = zlib.crc32(bytes([byte]), key0) & 0xffffffff
        key1 = ((key1 + (key0 & 0xff)) * 134775813 + 1) & 0xffffffff
        key2 = zlib.crc32(bytes([(key1 >> 24) & 0xff]), key2) & 0xffffffff
    def encrypt(data):
        out = bytearray()
        for byte in data:
            temp = key2 | 2
            out.append(byte ^ (((temp * (temp ^ 1)) >> 8) & 0xff))
            update_keys(byte)
        return bytes(out)
    payload, central = bytearray(), bytearray()
    for name, content, encrypted in entries:
        name_b = name.encode(); content = content.encode() if isinstance(content, str) else content
        crc = binascii.crc32(content) & 0xffffffff
        c = zlib.compressobj(wbits=-15); compressed = c.compress(content) + c.flush()
        flags, data = (1 if encrypted else 0), compressed
        if encrypted:
            key0, key1, key2 = 0x12345678, 0x23456789, 0x34567890
            for b in password.encode(): update_keys(b)
            data = encrypt(bytes((i * 17 + 3) & 255 for i in range(11)) + bytes([crc >> 24]) + compressed)
        offset = len(payload)
        payload += struct.pack('<IHHHHHIIIHH',0x04034b50,20,flags,8,0,0,crc,len(data),len(content),len(name_b),0)+name_b+data
        central += struct.pack('<IHHHHHHIIIHHHHHII',0x02014b50,20,20,flags,8,0,0,crc,len(data),len(content),len(name_b),0,0,0,0,0,offset)+name_b
    cdoff=len(payload); payload+=central
    payload+=struct.pack('<IHHHHIIH',0x06054b50,0,0,len(entries),len(entries),len(central),cdoff,0)
    Path(path).write_bytes(payload)

@pytest.fixture
def zip_factory(tmp_path):
    def make(entries,password='x',name='sample.data'):
        p=tmp_path/name; _zipcrypto_archive(p,entries,password); return p
    return make

@pytest.fixture
def exe():
    return Path('/workspace/executable')
