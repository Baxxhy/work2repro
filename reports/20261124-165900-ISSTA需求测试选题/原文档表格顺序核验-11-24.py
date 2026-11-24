"""Inspect a locked Word fixture and replay its actual tables at the frozen assertion."""
import argparse
import hashlib
import io
import json
import runpy
import sys
import xml.etree.ElementTree as ET
from itertools import permutations
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile


def inspect_fixture(data):
    with ZipFile(io.BytesIO(data)) as office_file:
        document = ET.fromstring(office_file.read("word/document.xml"))
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    body = document.find("w:body", ns)
    assert body is not None
    sequence = []
    tables = []
    for block in body:
        kind = block.tag.rsplit("}", 1)[-1]
        if kind == "p":
            sequence.append("paragraph")
        if kind == "tbl":
            sequence.append("table")
            rows = block.findall("w:tr", ns)
            cells = [
                ["".join(cell.itertext()).strip() for cell in row.findall("w:tc", ns)]
                for row in rows
            ]
            # Canonical JSON retains the row/cell association, using text visible in
            # the office document. The full fixture is kept in the benchmark kit.
            digest = hashlib.sha256(json.dumps(cells, ensure_ascii=False).encode()).hexdigest()
            tables.append({"row_count": len(rows), "cell_counts": [len(r) for r in cells],
                           "cell_text_sha256": digest})
    return {"fixture_sha256": hashlib.sha256(data).hexdigest(), "body_sequence": sequence,
            "table_details_in_order": tables,
            "number_of_distinct_table_contents": len({r["cell_text_sha256"] for r in tables})}


def replay(data, root):
    import docx
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    helpers = runpy.run_path(str(Path(__file__).with_name("已有断言反例核验-11-24.py")))
    repo = root if root is not None else helpers["locate_repo"]()
    source = repo / helpers["REQ"] / helpers["ORDER_KEY"] / "generated/features/steps/blk_iter_inner_content.py"
    check = helpers["load_leaf"](source, helpers["DOC_FN"], {"Table": Table, "Paragraph": Paragraph})
    original = list(docx.Document(io.BytesIO(data)).iter_inner_content())
    table_positions = [i for i, item in enumerate(original) if isinstance(item, Table)]
    assert len(table_positions) == 3
    results = []
    for order in permutations(range(3)):
        blocks = original.copy()
        for pos, ref in zip(table_positions, order):
            blocks[pos] = original[table_positions[ref]]
        observation = SimpleNamespace(iter_inner_content=lambda: iter(blocks))
        accepted = helpers["accepts"](check, SimpleNamespace(document=observation))
        results.append({"table_order": [index + 1 for index in order], "allowed": order == (0, 1, 2),
                        "frozen_assertion_accepts": accepted})
    return {"parser_version": docx.__version__, "original_assertion_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "replayed_orders": results}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path)
    args = parser.parse_args()
    data = sys.stdin.buffer.read()
    result = {**inspect_fixture(data), **replay(data, args.root)}
    print(json.dumps(result, indent=2, ensure_ascii=False))
