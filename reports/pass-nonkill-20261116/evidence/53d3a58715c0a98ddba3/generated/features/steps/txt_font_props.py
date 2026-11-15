from behave import given, then

from docx import Document
from docx.dml.color import ColorFormat


@given("a font")
def given_a_font(context):
    paragraph = Document().add_paragraph()
    context.font = paragraph.add_run().font


@then("font.color is a ColorFormat object")
def then_font_color_is_color_format(context):
    color = context.font.color
    assert isinstance(color, ColorFormat), (
        "font.color should be a ColorFormat object, got %r" % type(color)
    )
