"""Steps for accessing collections exposed by a document."""

from behave import given, then
from docx import Document
from docx.styles.styles import Styles


@given("a document having styles")
def given_document_having_styles(context):
    context.document = Document()


@then("document.styles is a Styles object")
def then_document_styles_is_styles_object(context):
    styles = context.document.styles
    assert isinstance(styles, Styles), (
        "document.styles should be a Styles object, got %s" % type(styles).__name__
    )
