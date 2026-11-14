#!/bin/sh
set +e
cd /workspace/eval
pytest -q --junitxml=/workspace/eval/results.xml
status=$?
if [ ! -s /workspace/eval/results.xml ]; then
  printf '%s\n' '<?xml version="1.0" encoding="utf-8"?><testsuites><testsuite name="runner" tests="1" errors="1"><testcase classname="runner" name="pytest"><error message="pytest failed to produce JUnit XML"/></testcase></testsuite></testsuites>' > /workspace/eval/results.xml
fi
exit "$status"
