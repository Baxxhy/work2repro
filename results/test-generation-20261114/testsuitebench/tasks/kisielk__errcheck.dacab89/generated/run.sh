#!/bin/sh
cd /workspace/eval
pytest -q --junitxml=/workspace/eval/results.xml
status=$?
if [ ! -s /workspace/eval/results.xml ]; then
  printf '%s\n' '<testsuites><testsuite name="pytest" tests="1" failures="1"><testcase name="pytest"><error message="pytest did not produce results.xml"/></testcase></testsuite></testsuites>' > /workspace/eval/results.xml
fi
exit "$status"
