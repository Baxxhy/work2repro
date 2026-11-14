from pathlib import Path

from behave import given, then
from docx import Document
from docx.settings import Settings


@given("a document having {settings_part} settings part")
def given_document_having_settings_part(context, settings_part):
    if settings_part == "no":
        fixture = Path(__file__).parent / "test_files" / "set-no-settings-part.docx"
        context.document = Document(str(fixture))
    elif settings_part == "a":
        context.document = Document()
    else:
        raise AssertionError("unexpected settings-part variant: %s" % settings_part)


@then("document.settings is a Settings object")
def then_document_settings_is_settings_object(context):
    settings = context.document.settings
    assert isinstance(settings, Settings), (
        "document.settings is %s, not Settings" % type(settings).__name__
    )
