#!/bin/sh
cd /workspace/eval
python3 -m pytest -q --junitxml=/workspace/eval/results.xml
status=$?
if [ ! -s /workspace/eval/results.xml ]; then
  printf '%s\n' '<?xml version="1.0" encoding="UTF-8"?><testsuites><testsuite name="fallback" tests="1" failures="1"><testcase name="pytest_runner"><failure message="pytest did not produce JUnit output"/></testcase></testsuite></testsuites>' > /workspace/eval/results.xml
fi
exit "$status"
