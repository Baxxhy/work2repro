import datetime as dt

from behave import given, then

from docx import Document


@given("a Comment object")
def given_comment_object(context):
    document = Document()
    context.comment = document.comments.add_comment(text="A comment")

    # Use a fixed authored date so the timestamp check is deterministic.
    context.expected_timestamp = dt.datetime(
        2024, 5, 17, 12, 34, 56, tzinfo=dt.timezone.utc
    )
    context.comment._comment_elm.date = context.expected_timestamp


@then("comment.timestamp is the date and time the comment was authored")
def then_comment_timestamp_is_authored_datetime(context):
    assert context.comment.timestamp == context.expected_timestamp, (
        "got %r, expected %r"
        % (context.comment.timestamp, context.expected_timestamp)
    )
