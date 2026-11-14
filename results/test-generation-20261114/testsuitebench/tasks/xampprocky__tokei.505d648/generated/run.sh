#!/bin/sh
set -u
cd /workspace/eval
python3 -m pytest -q --junitxml=/workspace/eval/results.xml
status=$?
if [ ! -s /workspace/eval/results.xml ]; then
  printf '%s\n' '<?xml version="1.0" encoding="utf-8"?><testsuites><testsuite name="eval" tests="1" errors="1"><testcase name="pytest"><error message="pytest did not produce results.xml"/></testcase></testsuite></testsuites>' > /workspace/eval/results.xml
fi
exit "$status"
