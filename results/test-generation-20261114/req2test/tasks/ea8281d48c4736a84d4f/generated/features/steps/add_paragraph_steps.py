"""Step definitions for adding paragraph text through the low-level API."""

from pathlib import Path

from behave import given, when, then
from docx import Document


_TEXT = "This text was added to a paragraph."
_SAVE_PATH = Path(__file__).resolve().parents[1] / "_scratch" / "add-paragraph.docx"


@given("a document")
def given_a_document(context):
    context.document = Document()
    context.paragraph = None
    context.run = None


@when("I add a paragraph")
def when_i_add_a_paragraph(context):
    context.paragraph = context.document.add_paragraph()


@when("I add a run to the paragraph")
def when_i_add_a_run_to_the_paragraph(context):
    context.run = context.paragraph.add_run()


@when("I add text to the run")
def when_i_add_text_to_the_run(context):
    context.run.add_text(_TEXT)


@when("I save the document")
def when_i_save_the_document(context):
    context.document.save(str(_SAVE_PATH))


@then("the document contains the text I added")
def then_document_contains_text_i_added(context):
    saved_document = Document(str(_SAVE_PATH))
    assert _TEXT in [run.text for paragraph in saved_document.paragraphs
                     for run in paragraph.runs], (
        "saved document does not contain the text added to the run"
    )
