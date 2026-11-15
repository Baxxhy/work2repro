from behave import given, then, register_type
from docx import Document
from docx.oxml import OxmlElement


def parse_bool(value):
    return value.strip().lower() == "true"


def parse_break_count(value):
    return {"no": 0, "one": 1, "two": 2}[value.strip().lower()]


register_type(Bool=parse_bool, BreakCount=parse_break_count)


@given("a run having {count:BreakCount} rendered page breaks")
def given_run_having_rendered_page_breaks(context, count):
    document = Document()
    run = document.add_paragraph().add_run()
    for _ in range(count):
        run._r.append(OxmlElement("w:lastRenderedPageBreak"))
    context.run = run


@then("run.contains_page_break is {value:Bool}")
def then_run_contains_page_break_is(context, value):
    actual = context.run.contains_page_break
    assert actual is value, "expected %r, got %r" % (value, actual)
