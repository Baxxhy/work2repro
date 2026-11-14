#!/bin/sh
cd /workspace/eval || exit 1
python3 -m pytest -q --junitxml=/workspace/eval/results.xml
status=$?
if [ ! -s /workspace/eval/results.xml ]; then
  printf '%s\n' '<?xml version="1.0" encoding="utf-8"?><testsuites><testsuite name="fallback"><testcase name="pytest"><error message="pytest did not produce JUnit output"/></testcase></testsuite></testsuites>' > /workspace/eval/results.xml
fi
exit "$status"
