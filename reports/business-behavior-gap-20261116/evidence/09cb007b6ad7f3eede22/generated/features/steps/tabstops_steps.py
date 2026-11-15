from behave import given, then
from docx import Document
from docx.shared import Inches


@given("a tab_stops having {count:d} tab stops")
def given_tab_stops_having_count(context, count):
    paragraph = Document().add_paragraph()
    context.tab_stops = paragraph.paragraph_format.tab_stops
    for index in range(count):
        context.tab_stops.add_tab_stop(Inches(index + 1))


@then("len(tab_stops) is {count:d}")
def then_len_tab_stops_is_count(context, count):
    actual = len(context.tab_stops)
    assert actual == count, "expected %d tab stops, got %d" % (count, actual)
