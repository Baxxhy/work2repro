"""Step definitions for comment metadata properties."""

from behave import given, then
from docx import Document


@given("a Comment object")
def given_a_comment_object(context):
    """Create a real Comment through the public document API."""
    context.comment_author = "Jane Doe"
    context.comment = Document().comments.add_comment(
        author=context.comment_author
    )


@then("comment.author is the author of the comment")
def then_comment_author_is_author(context):
    assert context.comment.author == context.comment_author, (
        "expected author %r, got %r"
        % (context.comment_author, context.comment.author)
    )
