from pathlib import Path

from behave import given, then
from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph


@given("a Document object with paragraphs and tables")
def given_document_with_paragraphs_and_tables(context):
    fixture = (
        Path(__file__).parent
        / "test_files"
        / "blk-paras-and-tables.docx"
    )
    context.document = Document(str(fixture))


@then("document.iter_inner_content() produces the block-items in document order")
def then_document_inner_content_in_document_order(context):
    items = list(context.document.iter_inner_content())

    expected_types = [
        Table,
        Paragraph,
        Table,
        Paragraph,
        Table,
        Paragraph,
    ]
    actual_types = [type(item) for item in items]
    assert actual_types == expected_types, (
        "got block-item types %r" % [item.__class__.__name__ for item in items]
    )

    # The fixture has paragraphs and tables interleaved, so checking their
    # distinguishing contents also verifies that iteration preserves order.
    paragraph_texts = [item.text for item in items if isinstance(item, Paragraph)]
    assert paragraph_texts == [
        "Lorem ipsum dolor sit amet, consectetur adipiscing elit.",
        "Donec semper facilisis metus finibus malesuada.",
        "",
    ], "paragraphs were not yielded in document order: %r" % paragraph_texts
