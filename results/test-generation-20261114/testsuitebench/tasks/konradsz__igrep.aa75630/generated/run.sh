#!/bin/sh
cd /workspace/eval
python3 -m pytest -q --junitxml=/workspace/eval/results.xml
status=$?
if [ ! -s /workspace/eval/results.xml ]; then
  cat > /workspace/eval/results.xml <<'XML'
<?xml version="1.0" encoding="utf-8"?>
<testsuites><testsuite name="suite-setup" tests="1" failures="1" errors="0" skipped="0"><testcase classname="suite-setup" name="pytest"><failure message="pytest did not produce a report" /></testcase></testsuite></testsuites>
XML
fi
exit "$status"
