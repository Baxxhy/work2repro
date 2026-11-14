#!/bin/sh
set +e
cd /workspace/eval || exit 1
pytest -q --junitxml=/workspace/eval/results.xml
status=$?
if [ ! -s /workspace/eval/results.xml ]; then
  python3 - <<'PY'
from xml.etree.ElementTree import Element, ElementTree
root = Element("testsuites")
suite = Element("testsuite", name="runner", tests="1", failures="1", errors="0", skipped="0")
case = Element("testcase", classname="runner", name="pytest-startup")
failure = Element("failure", message="pytest did not produce a report")
failure.text = "pytest exited before writing JUnit XML"
case.append(failure)
suite.append(case)
root.append(suite)
ElementTree(root).write("/workspace/eval/results.xml", encoding="utf-8", xml_declaration=True)
PY
fi
exit "$status"
