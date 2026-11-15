from behave import given, then
from docx import Document
from docx.shared import Inches
from docx.table import Table
from docx.text.paragraph import Paragraph


@given("a Footer object with paragraphs and tables")
def footer_with_paragraphs_and_tables(context):
    document = Document()
    footer = document.sections[0].footer

    # The footer's required initial paragraph is useful as the first item.
    first_paragraph = footer.paragraphs[0]
    first_paragraph.add_run("first")
    table = footer.add_table(rows=1, cols=1, width=Inches(1))
    table.cell(0, 0).text = "middle"
    last_paragraph = footer.add_paragraph("last")

    context.footer = footer
    context.expected_footer_items = [first_paragraph, table, last_paragraph]


@then("footer.iter_inner_content() produces the block-items in document order")
def footer_iter_inner_content_in_document_order(context):
    actual = list(context.footer.iter_inner_content())
    expected = context.expected_footer_items

    assert len(actual) == len(expected), (
        "expected %d block-items, got %d" % (len(expected), len(actual))
    )
    assert [type(item) for item in actual] == [Paragraph, Table, Paragraph], (
        "expected paragraph, table, paragraph; got %r"
        % [type(item).__name__ for item in actual]
    )
    assert all(actual_item._element is expected_item._element
               for actual_item, expected_item in zip(actual, expected)), (
        "footer block-items were not yielded in document order"
    )
