"""Steps for setting table alignment."""

from behave import given, when, then
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT


_ALIGNMENTS = {
    "inherited": None,
    "None": None,
    "WD_TABLE_ALIGNMENT.LEFT": WD_TABLE_ALIGNMENT.LEFT,
    "WD_TABLE_ALIGNMENT.RIGHT": WD_TABLE_ALIGNMENT.RIGHT,
    "WD_TABLE_ALIGNMENT.CENTER": WD_TABLE_ALIGNMENT.CENTER,
}


@given("a table having {alignment} alignment")
def given_table_alignment(context, alignment):
    document = Document()
    context.table = document.add_table(rows=1, cols=1)
    context.table.alignment = _ALIGNMENTS[alignment]


@when("I assign {value} to table.alignment")
def assign_table_alignment(context, value):
    context.table.alignment = _ALIGNMENTS[value]


@then("table.alignment is {value}")
def check_table_alignment(context, value):
    expected = _ALIGNMENTS[value]
    actual = context.table.alignment
    assert actual == expected, "expected %r, got %r" % (expected, actual)
