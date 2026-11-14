def ok(invoke, *args):
    r = invoke(*args)
    assert r.returncode == 0 and not r.stderr
    return r.stdout.rstrip("\n")

def bad(invoke, args, phrase="Error:"):
    r = invoke(*args)
    assert r.returncode == 1 and not r.stdout and phrase in r.stderr
    return r.stderr

def test_elementary_words(invoke):
    z = "0" * 63
    assert ok(invoke,"encode","params","-v","bool","true") == z+"1"
    assert ok(invoke,"encode","params","-v","bool","0") == z+"0"
    assert ok(invoke,"encode","params","--lenient","-v","uint","42") == "0"*62+"2a"
    assert ok(invoke,"encode","params","--lenient","-v","int8","-129") == "f"*62+"7f"
    assert ok(invoke,"encode","params","--lenient","-v","uint8","256") == "0"*61+"100"
    assert ok(invoke,"encode","params","-v","bytes2","0xaBcD") == "abcd"+"0"*60

def test_dynamic_head_tail_and_collections(invoke):
    w=lambda n:f"{n:064x}"
    got=ok(invoke,"encode","params","-v","bool","1","-v","string","hi","-v","bool","0")
    assert got == w(1)+w(96)+w(0)+w(2)+"6869"+"0"*60
    assert ok(invoke,"encode","params","--lenient","-v","uint8[2]","[1,2]") == w(1)+w(2)
    assert ok(invoke,"encode","params","--lenient","-v","uint8[]","[1,2]") == w(32)+w(2)+w(1)+w(2)
    assert ok(invoke,"encode","params","--lenient","-v","(uint8,string)","(3,x)") == w(32)+w(3)+w(64)+w(1)+"78"+"0"*62

def test_string_bytes_empty_and_zero_length_types(invoke):
    w=lambda n:f"{n:064x}"
    assert ok(invoke,"encode","params","-v","string",'"x"') == w(32)+w(3)+"227822"+"0"*58
    assert ok(invoke,"encode","params","-v","bytes","0x") == w(32)+w(0)
    assert ok(invoke,"encode","params","-v","string[0]","[]") == ""
    assert ok(invoke,"encode","params") == ""

def test_strict_and_lenient_validation(invoke):
    bad(invoke,("encode","params","-v","uint256","42"),"Hex parsing error")
    bad(invoke,("encode","params","-v","uint256","abc"),"Odd number of digits")
    bad(invoke,("encode","params","--lenient","-v","bool","2"),"Invalid data")
    bad(invoke,("encode","params","--lenient","-v","bool","TRUE"),"Invalid data")
    bad(invoke,("encode","params","--lenient","-v","uint8","-1"),"Uint parse error")
    bad(invoke,("encode","params","--lenient","-v","uint256","0.1 wei"),"Uint parse error")
    assert ok(invoke,"encode","params","--lenient","-v","uint256","1 ether").endswith("0"*15+"de0b6b3a7640000")
    assert ok(invoke,"encode","params","--lenient","-v","uint256","0.5 ether").endswith("0"*15+"6f05b59d3b20000")
    bad(invoke,("encode","params","--lenient","-v","uint256","1 etherx"),"Uint parse error")

def test_composite_values_and_limits(invoke):
    assert ok(invoke,"encode","params","--lenient","-v","(bool,address)","(true)") == "0"*63+"1"
    bad(invoke,("encode","params","--lenient","-v","uint8[2]","[1]"),"Invalid data")
    assert ok(invoke,"encode","params","-v","bogus","0"*64) == "0"*64
    assert ok(invoke,"encode","params","-v","uint7","0"*64) == "0"*64
