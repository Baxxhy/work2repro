"""Steps for the default properties of a document's latent styles."""

from behave import given, then
from docx import Document


@given("a latent styles object with known defaults")
def latent_styles_with_known_defaults(context):
    # Document() is based on python-docx's default template, whose styles.xml
    # contains the Word latent-style defaults exercised by this feature.
    context.document = Document()
    context.latent_styles = context.document.styles.latent_styles


@then("latent_styles.{prop_name} is {value}")
def latent_style_property_is(context, prop_name, value):
    expected = {"True": True, "False": False}.get(value, None)
    if expected is None:
        expected = int(value)
    actual = getattr(context.latent_styles, prop_name)
    assert actual == expected, (
        "latent_styles.%s was %r, expected %r" % (prop_name, actual, expected)
    )
