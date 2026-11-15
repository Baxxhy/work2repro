"""Steps for comment-property scenarios."""

from pathlib import Path

from behave import given, then
from docx import Document
from docx.drawing import Drawing


_TEST_FILES = Path(__file__).parent / "test_files"


@given("a Comment object containing an embedded image")
def given_comment_with_embedded_image(context):
    document = Document()
    comment = document.comments.add_comment(author="Test author")
    comment.paragraphs[0].add_run().add_picture(str(_TEST_FILES / "test.png"))
    context.comment = comment


@then("I can extract the image from the comment")
def then_extract_image_from_comment(context):
    drawings = [
        item
        for paragraph in context.comment.paragraphs
        for run in paragraph.runs
        for item in run.iter_inner_content()
        if isinstance(item, Drawing)
    ]
    assert len(drawings) == 1, f"expected one drawing, got {len(drawings)}"
    drawing = drawings[0]
    assert drawing.has_picture, "comment drawing is not a picture"

    image = drawing.image
    assert image.content_type == "image/png", image.content_type
    assert image.filename, "extracted image has no filename"
    assert len(image.sha1) == 40, f"unexpected SHA-1: {image.sha1!r}"
