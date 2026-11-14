from behave import given, when, then
from docx import Document


def _value_for(prop_name, text):
    """Convert an Examples-table value to the type used by the property."""
    if prop_name.startswith("default_to_"):
        return text.strip().lower() == "true"
    return int(text.strip())


@given("a latent styles object with known defaults")
def given_latent_styles_with_known_defaults(context):
    context.document = Document()
    context.latent_styles = context.document.styles.latent_styles


@when("I assign {new_value} to latent_styles.{prop_name}")
def assign_latent_style_default(context, new_value, prop_name):
    setattr(context.latent_styles, prop_name, _value_for(prop_name, new_value))


@then("latent_styles.{prop_name} is {value}")
def check_latent_style_default(context, prop_name, value):
    actual = getattr(context.latent_styles, prop_name)
    expected = _value_for(prop_name, value)
    assert actual == expected, (
        "latent_styles.%s was %r, expected %r" % (prop_name, actual, expected)
    )
