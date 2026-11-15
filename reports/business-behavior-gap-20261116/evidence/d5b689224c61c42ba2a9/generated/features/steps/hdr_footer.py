from behave import given, then, register_type
from docx import Document


def parse_bool(value):
    return value == "True"


register_type(Bool=parse_bool)


@given("a _Footer object {with_or_no} footer definition as {name}")
def given_footer(context, with_or_no, name):
    footer = Document().sections[0].footer
    if with_or_no == "with a":
        footer.is_linked_to_previous = False
    elif with_or_no != "with no":
        raise AssertionError("unexpected footer definition qualifier: %s" % with_or_no)
    setattr(context, name, footer)


@then("{name}.is_linked_to_previous is {value:Bool}")
def then_footer_linked_to_previous(context, name, value):
    footer = getattr(context, name)
    actual = footer.is_linked_to_previous
    assert actual is value, "expected %s, got %s" % (value, actual)
