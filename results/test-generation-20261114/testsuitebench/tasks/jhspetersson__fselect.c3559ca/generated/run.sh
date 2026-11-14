#!/bin/sh
set +e
cd /workspace/eval
pytest -q --junitxml=/workspace/eval/results.xml
status=$?
if [ ! -s /workspace/eval/results.xml ]; then
  cat > /workspace/eval/results.xml <<'XML'
<testsuites><testsuite name="pytest" tests="1" failures="0" errors="1"><testcase classname="runner" name="pytest"><error message="pytest failed before writing its report">pytest did not produce JUnit XML</error></testcase></testsuite></testsuites>
XML
fi
exit "$status"
