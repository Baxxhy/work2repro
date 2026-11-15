"""Step definitions for footer inheritance behavior."""

from behave import given, then
from docx import Document


@given("a _Footer object with a footer definition as footer")
def given_footer_with_definition(context):
    document = Document()
    section = document.sections[0]
    footer = section.footer
    footer.paragraphs[0].text = "Footer content"

    context.document = document
    context.footer = footer


@given("the next _Footer object with no footer definition as footer_2")
def given_next_footer_without_definition(context):
    section = context.document.add_section()
    context.footer_2 = section.footer


@then("footer_2.paragraphs[0].text == footer.paragraphs[0].text")
def then_footer_content_inherited(context):
    assert (
        context.footer_2.paragraphs[0].text == context.footer.paragraphs[0].text
    ), "next footer did not inherit the previous footer's paragraph text"


@then("footer_2.is_linked_to_previous is True")
def then_footer_is_linked_to_previous(context):
    assert context.footer_2.is_linked_to_previous is True, (
        "next footer should be linked to the previous section"
    )
