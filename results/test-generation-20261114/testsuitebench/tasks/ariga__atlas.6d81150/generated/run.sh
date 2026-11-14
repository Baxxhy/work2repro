#!/bin/sh
set +e
cd /workspace/eval || exit 2
python3 -m pytest -q --junitxml=/workspace/eval/results.xml
status=$?
if [ ! -s /workspace/eval/results.xml ]; then
  python3 - <<'PY'
from xml.etree.ElementTree import Element, SubElement, ElementTree
root = Element("testsuites")
suite = SubElement(root, "testsuite", name="pytest-runner", tests="1", failures="0", errors="1", skipped="0")
case = SubElement(suite, "testcase", classname="pytest", name="runner")
SubElement(case, "error", message="pytest did not produce JUnit XML").text = "pytest did not produce JUnit XML"
ElementTree(root).write("/workspace/eval/results.xml", encoding="utf-8", xml_declaration=True)
PY
fi
exit "$status"
