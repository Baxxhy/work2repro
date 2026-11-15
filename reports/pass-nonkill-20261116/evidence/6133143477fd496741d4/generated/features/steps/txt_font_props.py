"""Steps for the font-property scenarios."""

from behave import given, then
from docx import Document


@given("a font having typeface name {name}")
def given_font_having_typeface_name(context, name):
    """Create a run font, optionally assigning an explicit typeface."""
    paragraph = Document().add_paragraph()
    context.font = paragraph.add_run().font
    if name != "not specified":
        context.font.name = name


@then("font.name is {value}")
def then_font_name_is(context, value):
    expected = None if value == "None" else value
    assert context.font.name == expected, (
        "expected font.name %r, got %r" % (expected, context.font.name)
    )
