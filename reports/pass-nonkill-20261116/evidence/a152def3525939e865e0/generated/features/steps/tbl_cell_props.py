from behave import given, when, then

from docx import Document
from docx.shared import Inches


def _width_setting(value):
    """Convert the width phrases used by the feature into Length values."""
    value = value.strip()
    if value == "no explicit setting":
        return None
    if value == "1 inch":
        return Inches(1)
    if value == "2 inches":
        return Inches(2)
    raise AssertionError("unexpected width setting %r" % value)


@given("a table cell having a width of {width_setting}")
def given_table_cell_width(context, width_setting):
    document = Document()
    context.cell = document.add_table(rows=1, cols=1).cell(0, 0)
    initial_width = _width_setting(width_setting)
    if initial_width is not None:
        context.cell.width = initial_width


@when("I set the cell width to {new_setting}")
def set_cell_width(context, new_setting):
    context.cell.width = _width_setting(new_setting)


@then("the reported width of the cell is {reported_width}")
def check_reported_cell_width(context, reported_width):
    expected = _width_setting(reported_width)
    actual = context.cell.width
    assert actual == expected, "expected width %r, got %r" % (expected, actual)
