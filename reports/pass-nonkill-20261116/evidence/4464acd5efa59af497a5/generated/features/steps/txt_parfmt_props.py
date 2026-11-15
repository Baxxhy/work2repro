"""Steps for paragraph-format properties."""

from behave import given, then
from docx import Document


@given("a paragraph format having {prop_name} set {state}")
def given_paragraph_format_with_on_off_property(context, prop_name, state):
    paragraph = Document().add_paragraph()
    context.paragraph_format = paragraph.paragraph_format

    # Assigning None removes the direct formatting, so the getter reports the
    # inherited value; True and False encode the explicit On and Off states.
    value = {"to inherit": None, "On": True, "Off": False}[state]
    setattr(context.paragraph_format, prop_name, value)


@then("paragraph_format.{prop_name} is {value}")
def then_paragraph_format_on_off_property_is(context, prop_name, value):
    expected = {"None": None, "True": True, "False": False}[value]
    actual = getattr(context.paragraph_format, prop_name)
    assert actual is expected, (
        "paragraph_format.%s was %r, expected %r" % (prop_name, actual, expected)
    )
