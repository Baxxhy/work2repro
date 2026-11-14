def test_decode_primitive_format_and_aliases(invoke, wordhex):
    w=wordhex
    assert invoke("decode","params","-t","uint","-t","int","-t","invalid_type",w(42)+w(0)+w(1)).stdout == "uint256 2a\nint256 0\nuint8 1\n"
    assert invoke("decode","params","-t","bool",w(2)).stdout == "bool false\n"
    assert invoke("decode","params","-t","address",w(int("1234567890",16))).stdout == "address "+"0"*30+"1234567890\n"
    assert invoke("decode","params","-t","bytes2","ab"+"0"*62).stdout == "bytes2 ab\n"
    assert invoke("decode","params","-t","uint256","A"*62+"2A").stdout == "uint256 2a\n"

def test_decode_nested_and_dynamic(invoke, wordhex):
    w=wordhex
    assert invoke("decode","params","-t","uint256[]",w(32)+w(2)+w(10)+w(20)).stdout == "uint256[] [a,14]\n"
    assert invoke("decode","params","-t","string",w(32)+w(3)+"6869"+"0"*60).stdout == "string hi\n"
    assert invoke("decode","params","-t","bytes",w(32)+w(0)).stdout == "bytes \n"
    assert invoke("decode","params","-t","string",w(32)+w(1)+"ff").stdout == "string �\n"
    assert invoke("decode","params","-t","(uint8,bool)",w(3)+w(1)).stdout == "(uint8,bool) (3,true)\n"

def test_decode_empty_extra_and_hex(invoke, wordhex):
    r=invoke("decode","params","")
    assert r.returncode == 0 and not r.stdout and not r.stderr
    r=invoke("decode","params","-t","uint256","")
    assert r.returncode == 1 and not r.stdout and "failed to decode empty bytes" in r.stderr
    assert invoke("decode","params","-t","uint256",wordhex(4)+wordhex(7)).stdout == "uint256 4\n"
    for data, phrase in [("0x00","Invalid character"),("0","Odd number of digits"),("gg","Invalid character")]:
        r=invoke("decode","params",data)
        assert r.returncode == 1 and not r.stdout and phrase in r.stderr
    for data in ["", "00"]:
        r=invoke("decode","params","-t","bool",data)
        assert r.returncode == 1 and "Invalid data" in r.stderr

def test_function_encode_selectors_and_input_counts(invoke, abi_file, wordhex):
    abi=abi_file([
      {"type":"function","name":"transfer","inputs":[{"name":"to","type":"address"},{"name":"n","type":"uint256"}],"outputs":[]},
      {"type":"function","name":"totalSupply","inputs":[],"outputs":[{"name":"","type":"uint256"}]},
      {"type":"function","name":"empty","inputs":[],"outputs":[]},
    ])
    addr="0"*24+"1234567890abcdef1234567890abcdef12345678"
    assert invoke("encode","function",abi,"transfer","-p",addr,"-p","0"*62+"2a").stdout == "a9059cbb"+wordhex(int(addr,16))+wordhex(42)+"\n"
    assert invoke("encode","function",abi,"totalSupply():(uint256)").stdout == "18160ddd\n"
    assert len(invoke("encode","function",abi,"empty()").stdout.strip()) == 8
    r=invoke("encode","function",abi,"transfer","-p",addr)
    assert r.returncode == 1 and "Invalid data" in r.stderr

def test_function_decode_and_lookup(invoke, abi_file, wordhex):
    abi=abi_file([{"type":"function","name":"f","inputs":[],"outputs":[{"name":"x","type":"uint256"}]},
                  {"type":"function","name":"empty","inputs":[],"outputs":[]}])
    assert invoke("decode","function",abi,"f",wordhex(31)).stdout == "uint256 1f\n"
    assert invoke("decode","function",abi,"empty","").returncode == 0
    r=invoke("decode","function",abi,"f","")
    assert r.returncode == 1 and "failed to decode empty bytes" in r.stderr
    r=invoke("encode","function",abi,"missing(bool)")
    assert r.returncode == 1 and "Invalid name: missing" in r.stderr
    r=invoke("encode","function",abi,"f(bool)")
    assert r.returncode == 1 and "invalid function signature " in r.stderr

def test_log_decode_static_and_topics(invoke, abi_file, wordhex):
    abi=abi_file([{"type":"event","name":"E","anonymous":False,"inputs":[
      {"name":"who","type":"address","indexed":True},{"name":"value","type":"uint256","indexed":False}]}])
    sig=wordhex(0)
    addr="0"*24+"1234567890abcdef1234567890abcdef12345678"
    topic=wordhex(int(addr,16))
    r=invoke("decode","log",abi,"E","-l",sig,"-l",topic,wordhex(9))
    assert r.returncode == 0 and r.stdout == "who "+addr+"\nvalue 9\n"
    r=invoke("decode","log",abi,"E","-l","0x"+sig,"-l",topic,"0x"+wordhex(9))
    assert r.returncode == 1 and "Invalid character" in r.stderr
    r=invoke("decode","log",abi,"E","-l","12",wordhex(9))
    assert r.returncode == 1 and "Invalid input length" in r.stderr
