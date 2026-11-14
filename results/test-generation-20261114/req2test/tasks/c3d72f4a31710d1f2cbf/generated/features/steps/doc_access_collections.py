from pathlib import Path

from behave import given, then
from docx import Document
from docx.section import Sections


@given("a document having sections")
def given_document_having_sections(context):
    fixture_path = Path(__file__).parent / "test_files" / "doc-access-sections.docx"
    context.document = Document(str(fixture_path))


@then("document.sections is a Sections object")
def then_document_sections_is_sections_object(context):
    sections = context.document.sections
    assert isinstance(sections, Sections), (
        "document.sections should be a Sections object, got %s"
        % type(sections).__name__
    )
