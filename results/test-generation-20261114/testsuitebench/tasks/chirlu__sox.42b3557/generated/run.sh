#!/bin/sh
cd /workspace/eval
python3 -m pytest -q --junitxml=/workspace/eval/results.xml
status=$?
if [ ! -s /workspace/eval/results.xml ] || ! python3 -c 'import xml.etree.ElementTree as ET; ET.parse("/workspace/eval/results.xml")' >/dev/null 2>&1; then
  cat > /workspace/eval/results.xml <<'XML'
<testsuites><testsuite name="eval" tests="1" failures="0" errors="1" skipped="0"><testcase classname="runner" name="pytest_runner"><error message="pytest did not produce valid JUnit XML" /></testcase></testsuite></testsuites>
XML
fi
exit "$status"
