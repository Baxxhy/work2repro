#!/bin/sh
cd /workspace/eval || exit 2
python3 -m pytest -q --junitxml=/workspace/eval/results.xml
status=$?
if [ ! -s /workspace/eval/results.xml ]; then
  cat > /workspace/eval/results.xml <<'XML'
<testsuites><testsuite name="suite" tests="1" failures="0" errors="1" skipped="0"><testcase classname="runner" name="pytest"><error message="pytest did not produce a report" /></testcase></testsuite></testsuites>
XML
fi
exit "$status"
