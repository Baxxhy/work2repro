"""Step definitions for font property scenarios."""

from behave import given, when, then
from docx import Document


def _font_value(text):
    """Convert the feature's textual representation to a font name."""
    return None if text == "None" else text


@given("a font having typeface name {name}")
def given_font_having_typeface_name(context, name):
    document = Document()
    run = document.add_paragraph().add_run("text")
    run.font.name = None if name == "not specified" else name
    context.font = run.font


@when("I assign {value} to font.name")
def assign_font_name(context, value):
    context.font.name = _font_value(value)


@then("font.name is {value}")
def font_name_is(context, value):
    expected = _font_value(value)
    actual = context.font.name
    assert actual == expected, "expected font.name %r, got %r" % (expected, actual)
