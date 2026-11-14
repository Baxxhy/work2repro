#!/bin/sh
set +e
cd /workspace/eval
pytest -q --junitxml=/workspace/eval/results.xml
status=$?
if [ ! -s /workspace/eval/results.xml ]; then
  printf '%s\n' '<testsuites><testsuite name="fallback"><testcase name="pytest_runner"><error message="pytest did not create results.xml"/></testcase></testsuite></testsuites>' > /workspace/eval/results.xml
fi
exit "$status"
