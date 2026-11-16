"""Step definitions for adding document sections."""

from behave import given, when, then
from docx import Document


@given("a single-section Document object with headers and footers as document")
def given_document_with_headers_and_footers(context):
    document = Document()
    assert len(document.sections) == 1, "a new document should have one section"

    # Materialize the six header/footer variants on the existing section.  This
    # gives the added section actual prior header/footer definitions to inherit.
    original_section = document.sections[0]
    for name in (
        "header",
        "even_page_header",
        "first_page_header",
        "footer",
        "even_page_footer",
        "first_page_footer",
    ):
        getattr(original_section, name)

    context.document = document


@when("I execute section = document.add_section()")
def when_add_section(context):
    context.section = context.document.add_section()


@then("section.header.is_linked_to_previous is True")
def then_header_linked_to_previous(context):
    assert context.section.header.is_linked_to_previous is True


@then("section.even_page_header.is_linked_to_previous is True")
def then_even_page_header_linked_to_previous(context):
    assert context.section.even_page_header.is_linked_to_previous is True


@then("section.first_page_header.is_linked_to_previous is True")
def then_first_page_header_linked_to_previous(context):
    assert context.section.first_page_header.is_linked_to_previous is True


@then("section.footer.is_linked_to_previous is True")
def then_footer_linked_to_previous(context):
    assert context.section.footer.is_linked_to_previous is True


@then("section.even_page_footer.is_linked_to_previous is True")
def then_even_page_footer_linked_to_previous(context):
    assert context.section.even_page_footer.is_linked_to_previous is True


@then("section.first_page_footer.is_linked_to_previous is True")
def then_first_page_footer_linked_to_previous(context):
    assert context.section.first_page_footer.is_linked_to_previous is True
