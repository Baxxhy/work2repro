#!/bin/sh
set +e
cd /workspace/eval
python3 -m pytest -q --junitxml=/workspace/eval/results.xml
status=$?
# pytest writes the report even when tests fail; synthesize a valid report if startup failed.
if [ ! -s /workspace/eval/results.xml ]; then
  printf '%s\n' '<?xml version="1.0" encoding="utf-8"?><testsuites><testsuite name="pytest" tests="1" errors="1"><testcase name="pytest-startup"><error message="pytest did not produce a report"/></testcase></testsuite></testsuites>' > /workspace/eval/results.xml
fi
exit "$status"
