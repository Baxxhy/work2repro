def test_abi_loading_and_metadata(invoke, abi_file, wordhex):
    abi=abi_file([
      {"type":"constructor","inputs":[]},
      {"type":"function","name":"f","constant":True,"stateMutability":"view","inputs":[],"outputs":[{"name":"","type":"uint256"}]},
    ])
    assert invoke("decode","function",abi,"f",wordhex(7)).stdout == "uint256 7\n"
    missing=invoke("encode","function","/workspace/eval/missing.json","f")
    assert missing.returncode == 1 and "No such file or directory" in missing.stderr
    badfile=abi_file([], "bad.json")
    open(badfile,"w").write("{ invalid json")
    r=invoke("encode","function",badfile,"f")
    assert r.returncode == 1 and "Serialization error" in r.stderr
    assert r.stderr.count("invalid") >= 1 and "Caused by:" in r.stderr

def test_function_signatures_duplicates_and_types(invoke, abi_file):
    abi=abi_file([
      {"type":"function","name":"f","inputs":[{"name":"x","type":"bool"}],"outputs":[]},
      {"type":"function","name":"f","inputs":[{"name":"x","type":"uint256"}],"outputs":[]},
    ])
    r=invoke("encode","function",abi,"f")
    assert r.returncode == 1 and "More than one function found" in r.stderr
    r=invoke("encode","function",abi,"f(bool)","-p","true")
    assert r.returncode == 0
    r=invoke("encode","function",abi,"f(bool)","-p","true","-p","not parsed")
    assert r.returncode == 0
    r=invoke("encode","function",abi,"f( bool )","-p","true")
    assert r.returncode == 1 and "invalid function signature" in r.stderr

def test_decode_log_signature_hash(invoke, abi_file, wordhex):
    abi=abi_file([{"type":"event","name":"Transfer","anonymous":False,"inputs":[
      {"name":"from","type":"address","indexed":True},
      {"name":"to","type":"address","indexed":True},
      {"name":"value","type":"uint256","indexed":False}]}])
    sig="ddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
    a="0"*24+"a94f5374fce5edbc8e2a8697c15331677e6ebf0b"
    b="0"*24+"5a0b54d5dc17e0aadc383d2db43b0a0d3e029c4c"
    topics=["0"*24+a[-40:],"0"*24+b[-40:]]
    r=invoke("decode","log",abi,"Transfer(address, address, uint256)","-l",sig,"-l",topics[0],"-l",topics[1],wordhex(100))
    assert r.returncode == 0
    assert r.stdout == "from "+a[-40:]+"\nto "+b[-40:]+"\nvalue 64\n"
    r=invoke("decode","log",abi,"Transfer(","")
    assert r.returncode == 1 and not r.stdout

def test_missing_arguments_and_option_parsing(invoke):
    for args, markers in [
      (("encode","function"),("<abi-path>","<function-name-or-signature>")),
      (("decode","function"),("<abi-path>","<function-name-or-signature>","<data>")),
      (("decode","log"),("<abi-path>","<event-name-or-signature>","<data>")),
    ]:
        r=invoke(*args)
        assert r.returncode == 1 and not r.stdout and "The following required arguments were not provided:" in r.stderr
        for m in markers:
            assert m in r.stderr
    for args, phrase in [
      (("encode","params","-v","bool"),"requires 2 values"),
      (("encode","params","--nonexistent"),"Found argument"),
      (("decode","params","-t"),"requires a value"),
    ]:
        r=invoke(*args)
        assert r.returncode == 1 and not r.stdout and phrase in r.stderr and "For more information try --help" in r.stderr
