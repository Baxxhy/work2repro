from behave import given, then
from docx import Document
from docx.enum.table import WD_ROW_HEIGHT_RULE


@given("a table row having height rule {state}")
def given_row_with_height_rule(context, state):
    document = Document()
    table = document.add_table(rows=1, cols=1)
    context.row = table.rows[0]

    if state == "automatic":
        context.row.height_rule = WD_ROW_HEIGHT_RULE.AUTO
    elif state == "at least":
        context.row.height_rule = WD_ROW_HEIGHT_RULE.AT_LEAST
    elif state != "no explicit setting":
        raise AssertionError("unknown height-rule state: %s" % state)


@then("row.height_rule is {value}")
def then_row_height_rule_is(context, value):
    expected = None if value == "None" else WD_ROW_HEIGHT_RULE[value]
    actual = context.row.height_rule
    assert actual == expected, "expected %r, got %r" % (expected, actual)
