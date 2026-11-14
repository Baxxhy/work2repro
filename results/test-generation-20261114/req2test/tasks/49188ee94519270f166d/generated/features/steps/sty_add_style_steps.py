"""Step definitions for adding a style to a document."""

from behave import given, when, then

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.styles.style import BaseStyle


_STYLE_TYPES = {
    "WD_STYLE_TYPE.PARAGRAPH": WD_STYLE_TYPE.PARAGRAPH,
    "WD_STYLE_TYPE.CHARACTER": WD_STYLE_TYPE.CHARACTER,
    "WD_STYLE_TYPE.LIST": WD_STYLE_TYPE.LIST,
    "WD_STYLE_TYPE.TABLE": WD_STYLE_TYPE.TABLE,
}


def _parse_bool(value):
    return value == "True"


@given("a document having known styles")
def given_document_having_known_styles(context):
    context.document = Document()
    context.styles = context.document.styles
    context.initial_style_count = len(context.styles)


@when("I call add_style('{name}', {type}, builtin={builtin})")
def when_call_add_style(context, name, type, builtin):
    style_type = _STYLE_TYPES[type]
    builtin_value = _parse_bool(builtin)
    context.style = context.styles.add_style(name, style_type, builtin=builtin_value)
    context.style_name = name
    context.expected_style_type = style_type
    context.expected_builtin = builtin_value


@then("the document has one additional style")
def then_document_has_one_additional_style(context):
    actual = len(context.styles)
    assert actual == context.initial_style_count + 1, (
        "expected %d styles, got %d"
        % (context.initial_style_count + 1, actual)
    )


@then("styles['{name}'] is a style")
def then_styles_name_is_a_style(context, name):
    style = context.styles[name]
    assert isinstance(style, BaseStyle), "styles[%r] is not a BaseStyle" % name
    context.style = style


@then("style.type is {type}")
def then_style_type_is(context, type):
    expected = _STYLE_TYPES[type]
    assert context.style.type == expected, (
        "expected style type %r, got %r" % (expected, context.style.type)
    )


@then("style.builtin is {builtin}")
def then_style_builtin_is(context, builtin):
    expected = _parse_bool(builtin)
    assert context.style.builtin is expected, (
        "expected builtin=%r, got %r" % (expected, context.style.builtin)
    )
