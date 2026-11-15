#!/usr/bin/env bash
set -u
cd /workspace/eval

# pytest's JUnit reporter writes a complete report even when collected tests fail.
python3 -m pytest -q -o junit_logging=none --junitxml=/workspace/eval/results.xml "$@"
status=$?
if [ ! -s /workspace/eval/results.xml ] || ! python3 -c 'import xml.etree.ElementTree as E; E.parse("/workspace/eval/results.xml")' >/dev/null 2>&1; then
  cat > /workspace/eval/results.xml <<'XML'
<?xml version="1.0" encoding="utf-8"?>
<testsuites><testsuite name="eval" tests="1" errors="1" failures="0" skipped="0"><testcase classname="runner" name="pytest"><error message="pytest did not produce a JUnit report" /></testcase></testsuite></testsuites>
XML
fi
exit "$status"
