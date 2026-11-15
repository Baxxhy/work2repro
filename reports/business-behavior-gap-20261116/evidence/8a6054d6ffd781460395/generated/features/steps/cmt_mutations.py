"""Step definitions for comment mutation scenarios."""

from behave import given, when, then
from docx import Document


@given("a Comments object with {count:d} comments")
def given_comments_object(context, count):
    """Create a real document-backed Comments collection."""
    document = Document()
    context.comments = document.comments
    assert len(context.comments) == count, (
        "expected %d comments, got %d" % (count, len(context.comments))
    )


@when('I assign comment = comments.add_comment(author="John Doe", initials="JD")')
def when_add_comment_with_author_and_initials(context):
    context.comment = context.comments.add_comment(author="John Doe", initials="JD")


@then('comment.author == "John Doe"')
def then_comment_author_is_john_doe(context):
    assert context.comment.author == "John Doe", (
        "expected author 'John Doe', got %r" % context.comment.author
    )


@then('comment.initials == "JD"')
def then_comment_initials_are_jd(context):
    assert context.comment.initials == "JD", (
        "expected initials 'JD', got %r" % context.comment.initials
    )
