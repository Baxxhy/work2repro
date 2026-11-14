from behave import given, when, then
from docx import Document


@given("a document having known styles")
def given_document_having_known_styles(context):
    context.document = Document()
    context.styles = context.document.styles
    context.latent_styles = context.styles.latent_styles


@when("I delete a latent style")
def when_delete_a_latent_style(context):
    # The default document template supplies a non-empty, known collection of
    # latent style exceptions. Retain the name so the deletion can be checked
    # through the collection's name-based lookup.
    context.latent_style = next(iter(context.latent_styles))
    context.deleted_latent_style_name = context.latent_style.name
    context.latent_styles_before_delete = len(context.latent_styles)
    context.latent_style.delete()


@then("the document has one fewer latent styles")
def then_document_has_one_fewer_latent_styles(context):
    actual = len(context.document.styles.latent_styles)
    expected = context.latent_styles_before_delete - 1
    assert actual == expected, "expected %d latent styles, got %d" % (expected, actual)


@then("the deleted latent style is not in the latent styles collection")
def then_deleted_latent_style_is_not_in_collection(context):
    try:
        context.document.styles.latent_styles[context.deleted_latent_style_name]
    except KeyError:
        return
    assert False, "deleted latent style %r is still in the collection" % (
        context.deleted_latent_style_name,
    )
