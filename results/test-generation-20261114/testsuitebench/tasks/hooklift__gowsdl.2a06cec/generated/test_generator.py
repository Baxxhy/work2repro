import os
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest


EXE = Path("/workspace/executable")


def run(tmp_path, *args, cwd=None):
    return subprocess.run(
        [str(EXE), *map(str, args)], cwd=cwd or tmp_path,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )


def wsdl(body="", ns="urn:test"):
    return f'''<?xml version="1.0"?>
<definitions xmlns="http://schemas.xmlsoap.org/wsdl/"
 xmlns:tns="{ns}" xmlns:xs="http://www.w3.org/2001/XMLSchema"
 xmlns:soap="http://schemas.xmlsoap.org/wsdl/soap/" targetNamespace="{ns}">
 <types>{body}</types>
</definitions>'''


def invoke_file(tmp_path, content=None, *args, name="in.wsdl"):
    p = tmp_path / name
    if content is not None:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    return p, run(tmp_path, *args, p)


def outputs(tmp_path, package="in", client="in.go"):
    return (tmp_path / package / client).read_text(), (tmp_path / package / ("server" + client)).read_text()


def test_no_args_help_to_stderr_with_usage():
    r = run(Path("/workspace"))
    assert r.returncode == 0
    assert r.stdout == ""
    assert r.stderr.startswith("Usage: /workspace/executable [options] myservice.wsdl\n")
    assert "-make-public" in r.stderr and "command" not in r.stderr.lower()


@pytest.mark.parametrize("flag", ["-h", "--help"] , ids=["short-help", "long-help"])
def test_help_overrides_unknown(flag, tmp_path):
    r = run(tmp_path, flag, "--unknown")
    assert r.returncode == 0 and r.stdout == ""
    assert r.stderr.startswith(f"Usage: {EXE} [options] myservice.wsdl\n")


def test_version_exact_and_valid_preflag(tmp_path):
    r = run(tmp_path, "-i", "-v")
    assert r.returncode == 0
    assert r.stdout == "🍀  v0.5.0\n" and r.stderr == ""


@pytest.mark.parametrize("args,needle", [
    (("-z",), "flag provided but not defined: -z"),
    (("-d",), "flag needs an argument: -d"),
    (("-make-public=wat",), 'invalid boolean value "wat" for -make-public'),
    (("-iv",), "flag provided but not defined: -iv"),
], ids=["unknown-flag", "missing-string-value", "bad-bool", "no-short-combining"])
def test_flag_errors_use_flag_package_exit_two(tmp_path, args, needle):
    r = run(tmp_path, *args)
    assert r.returncode == 2 and r.stdout == ""
    assert needle in r.stderr and "Usage:" in r.stderr


def test_empty_filename_is_distinct_error(tmp_path):
    r = run(tmp_path, "")
    assert r.returncode == 1
    assert r.stdout == "🍀  WSDL file is required to generate Go proxy\n"


def test_last_positional_wins_and_relative_path_is_cleaned(tmp_path):
    first = tmp_path / "first.wsdl"
    second = tmp_path / "deep space" / "second-file.wsdl"
    first.write_text("not xml")
    second.parent.mkdir()
    second.write_text(wsdl())
    r = run(tmp_path, "first.wsdl", "deep space/../deep space/second-file.wsdl")
    assert r.returncode == 0
    assert f"🍀  Reading file {second}\n" in r.stdout
    assert r.stdout.splitlines()[-1] == "🍀  Done 👍"


def test_first_positional_stops_flag_parsing(tmp_path):
    r = run(tmp_path, "first.wsdl", "-v")
    assert r.returncode == 1
    assert "Reading file" in r.stdout and "open -v" in r.stdout
    assert "Done" not in r.stdout


def test_missing_file_runtime_error_stdout_only(tmp_path):
    missing = tmp_path / "absent.wsdl"
    r = run(tmp_path, missing)
    assert r.returncode == 1 and r.stderr == ""
    lines = r.stdout.splitlines()
    assert lines[0] == f"🍀  Reading file {missing}"
    assert lines[1] == f"🍀  open {missing}: no such file or directory"


def test_http_download_and_non_200_status(tmp_path):
    seen = []
    payload = wsdl().encode()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            seen.append(self.path)
            code = 503 if self.path == "/unavailable.wsdl" else 200
            body = b"unavailable" if code != 200 else payload
            self.send_response(code)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        good = run(tmp_path, base + "/space%20name.wsdl")
        assert good.returncode == 0
        assert f"🍀  Downloading file {base}/space%20name.wsdl" in good.stdout
        assert seen[-1] == "/space%20name.wsdl"
        bad = run(tmp_path, base + "/unavailable.wsdl")
        assert bad.returncode == 1 and bad.stderr == ""
        assert f"🍀  Downloading file {base}/unavailable.wsdl" in bad.stdout
        assert "🍀  Received response code 503" in bad.stdout
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_o_same_as_wsdl_is_early_error_and_preserves_input(tmp_path):
    p = tmp_path / "same.wsdl"
    data = wsdl()
    p.write_text(data)
    r = run(tmp_path, "-o", "same.wsdl", p)
    assert r.returncode == 1
    assert r.stdout == "🍀  Output file cannot be the same WSDL file\n"
    assert p.read_text() == data


def test_non_xml_is_rejected_before_output_directory_creation(tmp_path):
    p = tmp_path / "bad.wsdl"
    p.write_text("plain text")
    r = run(tmp_path, "-d", "newdir", p)
    assert r.returncode == 1 and "🍀  EOF\n" in r.stdout
    assert not (tmp_path / "newdir").exists()


def test_empty_well_formed_document_generates_shells(tmp_path):
    p, r = invoke_file(tmp_path, "<root/>", "-p", "odd", "-o", "odd.go", name="odd.ext")
    assert r.returncode == 0
    client, server = outputs(tmp_path, "odd", "odd.go")
    assert client.startswith("// Code generated by gowsdl DO NOT EDIT.\n\npackage odd\n")
    assert "type AnyType struct" in client and "type AnyURI string" in client
    assert "func Endpoint(w http.ResponseWriter" in server


def test_output_names_and_custom_package(tmp_path):
    p = tmp_path / "input.wsdl"
    p.write_text(wsdl())
    r = run(tmp_path, "-p", "my_pkg", "-o", "custom", p)
    assert r.returncode == 0
    c = (tmp_path / "my_pkg" / "custom").read_text()
    s = (tmp_path / "my_pkg" / "servercustom").read_text()
    assert "package my_pkg" in c and "package my_pkg" in s


def test_missing_parent_output_directory_fails_with_joined_path(tmp_path):
    p = tmp_path / "in.wsdl"
    p.write_text(wsdl())
    r = run(tmp_path, "-p", "pkg", "-o", "/nested/file.go", p)
    assert r.returncode == 1
    assert "open pkg/nested/file.go: no such file or directory" in r.stdout


def test_primitive_mapping_and_simple_type_enums(tmp_path):
    schema = '''<xs:schema targetNamespace="urn:test">
      <xs:element name="Count" type="xs:int"/>
      <xs:element name="When" type="xs:dateTime"/>
      <xs:simpleType name="Status"><xs:restriction base="xs:string">
       <xs:enumeration value="Active"/><xs:enumeration value=""/>
      </xs:restriction></xs:simpleType>
      <xs:element name="state" type="tns:Status"/>
    </xs:schema>'''
    p, r = invoke_file(tmp_path, wsdl(schema))
    assert r.returncode == 0
    client, _ = outputs(tmp_path)
    assert "type Count int32" in client
    assert "type When soap.XSDDateTime" in client
    assert "func (xdt When) MarshalXML" in client
    assert 'StatusActive Status = "Active"' in client
    assert 'StatusEmptyString Status = ""' in client
    assert "type State Status" in client


def test_complex_fields_order_tags_attributes_and_keyword_names(tmp_path):
    schema = '''<xs:schema targetNamespace="urn:fields" xmlns:tns="urn:fields">
      <xs:complexType name="box"><xs:sequence>
       <xs:element name="func" type="xs:string"/><xs:element name="kids" type="xs:int" maxOccurs="unbounded"/>
      </xs:sequence><xs:attribute name="id" type="xs:long"/></xs:complexType>
      <xs:element name="Box" type="tns:box"/>
    </xs:schema>'''
    _, r = invoke_file(tmp_path, wsdl(schema))
    assert r.returncode == 0
    c, _ = outputs(tmp_path)
    assert "type box struct" in c
    assert 'Func_ string `xml:"func,omitempty" json:"func,omitempty"`' in c
    assert 'Kids []int32 `xml:"kids,omitempty" json:"kids,omitempty"`' in c
    assert 'Id int64 `xml:"urn:fields id,attr,omitempty" json:"id,omitempty"`' in c
    assert "type Box box" in c


def test_make_public_false_preserves_schema_identifier_but_fields_export(tmp_path):
    schema = '''<xs:schema targetNamespace="urn:x"><xs:complexType name="thing"><xs:sequence>
      <xs:element name="value" type="xs:string"/></xs:sequence></xs:complexType>
      <xs:element name="thingElement" type="xs:string"/></xs:schema>'''
    p = tmp_path / "in.wsdl"
    p.write_text(wsdl(schema))
    r = run(tmp_path, "-make-public=false", p)
    assert r.returncode == 0
    c, _ = outputs(tmp_path)
    assert "type thing struct" in c and "Value string" in c
    assert "type thingElement string" in c


def test_import_include_loading_order_and_declaration_order(tmp_path):
    (tmp_path / "schemas").mkdir()
    (tmp_path / "schemas" / "common.xsd").write_text('<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" targetNamespace="urn:test"><xs:element name="Common" type="xs:string"/></xs:schema>')
    (tmp_path / "schemas" / "second.xsd").write_text('<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" targetNamespace="urn:test"><xs:element name="Second" type="xs:string"/></xs:schema>')
    primary = wsdl('''<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema" targetNamespace="urn:test">
      <xs:include schemaLocation="schemas/second.xsd"/><xs:import schemaLocation="schemas/common.xsd"/>
      <xs:element name="Last" type="xs:string"/></xs:schema>''')
    p = tmp_path / "in.wsdl"
    p.write_text(primary)
    r = run(tmp_path, p)
    assert r.returncode == 0
    lines = r.stdout.splitlines()
    assert lines[1].endswith("schemas/common.xsd") and lines[2].endswith("schemas/second.xsd")
    c, _ = outputs(tmp_path)
    assert c.index("type Last string") < c.index("type Common string") < c.index("type Second string")


def test_invalid_package_is_format_error_after_read(tmp_path):
    p = tmp_path / "in.wsdl"
    p.write_text(wsdl())
    r = run(tmp_path, "-p", "invalid package name with spaces", p)
    assert r.returncode == 1
    assert r.stdout.startswith(f"🍀  Reading file {p}\n🍀  4:17: expected ';', found 'package'\n")


def test_invalid_xsd_boolean_aborts_without_output(tmp_path):
    schema = '<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"><xs:element name="A" nillable="maybe" type="xs:string"/></xs:schema>'
    p, r = invoke_file(tmp_path, wsdl(schema))
    assert r.returncode == 1
    assert 'strconv.ParseBool: parsing "maybe": invalid syntax' in r.stdout
    assert not (tmp_path / "in").exists()


def test_wsdl_operation_methods_actions_and_context(tmp_path):
    doc = '''<definitions xmlns="http://schemas.xmlsoap.org/wsdl/" xmlns:xs="http://www.w3.org/2001/XMLSchema"
      xmlns:tns="urn:op" xmlns:soap="http://schemas.xmlsoap.org/wsdl/soap/" targetNamespace="urn:op">
      <types><xs:schema targetNamespace="urn:op"><xs:element name="Ask" type="xs:string"/><xs:element name="Answer" type="xs:int"/></xs:schema></types>
      <message name="In"><part name="p" element="tns:Ask"/></message><message name="Out"><part name="p" element="tns:Answer"/></message>
      <portType name="Lookup"><operation name="Find"><input message="tns:In"/><output message="tns:Out"/></operation></portType>
      <binding name="B" type="tns:Lookup"><soap:binding/><operation name="Find"><soap:operation soapAction="urn:find"/></operation></binding>
    </definitions>'''
    _, r = invoke_file(tmp_path, doc)
    assert r.returncode == 0
    c, _ = outputs(tmp_path)
    assert "type Lookup interface" in c
    assert "Find(request *string) (*int32, error)" in c
    assert "FindContext(ctx context.Context, request *string) (*int32, error)" in c
    assert 'CallContext(ctx, "urn:find", request, response)' in c
    assert "context.Background()" in c


def test_server_embeds_wsdl_and_has_dispatch_shell(tmp_path):
    original = wsdl()
    _, r = invoke_file(tmp_path, original)
    assert r.returncode == 0
    _, s = outputs(tmp_path)
    assert "var wsdl = `" + original + "`" in s
    assert "type SOAPEnvelopeRequest struct" in s
    assert "type SOAPEnvelopeResponse struct" in s
    assert "func (service *SOAPEnvelopeRequest) call" in s
    assert 'http.MethodGet' in s and "MethodByName(name + \"Func\")" in s
    assert "func Endpoint(w http.ResponseWriter, r *http.Request)" in s


def test_deterministic_repeated_generation(tmp_path):
    p = tmp_path / "in.wsdl"
    p.write_text(wsdl('<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema"><xs:element name="A" type="xs:string"/></xs:schema>'))
    r1 = run(tmp_path, p)
    before = outputs(tmp_path)
    r2 = run(tmp_path, p)
    assert r1.returncode == r2.returncode == 0
    assert before == outputs(tmp_path)
