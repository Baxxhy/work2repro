from behave import given, then
from docx import Document


@given("a latent style having priority of {setting}")
def given_latent_style_with_priority(context, setting):
    """Create a latent-style exception with either no priority or a known one."""
    latent_styles = Document().styles.latent_styles
    context.latent_style = latent_styles.add_latent_style("Normal")
    if setting != "no setting":
        context.latent_style.priority = int(setting)


@then("latent_style.priority is {value}")
def then_latent_style_priority_is(context, value):
    expected = None if value == "None" else int(value)
    assert context.latent_style.priority == expected, (
        "expected priority %r, got %r"
        % (expected, context.latent_style.priority)
    )
