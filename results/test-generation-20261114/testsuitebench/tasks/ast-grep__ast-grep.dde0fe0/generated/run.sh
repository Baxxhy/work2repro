#!/bin/sh
cd /workspace/eval
python3 -m pytest -q --junitxml=/workspace/eval/results.xml
status=$?
if [ ! -s /workspace/eval/results.xml ]; then
  cat > /workspace/eval/results.xml <<'XML'
<testsuites><testsuite name="pytest" tests="1" errors="1"><testcase classname="runner" name="pytest"><error message="pytest did not produce a report">pytest invocation failed</error></testcase></testsuite></testsuites>
XML
fi
exit "$status"
