#!/bin/sh
set +e
cd /workspace/eval || exit 1
python3 -m pytest -q --junitxml=/workspace/eval/results.xml
status=$?
# Ensure the required artifact exists even if pytest itself fails before initializing its reporter.
if [ ! -s /workspace/eval/results.xml ]; then
  cat > /workspace/eval/results.xml <<'XML'
<testsuites><testsuite name="pytest" tests="1" failures="1" errors="0" skipped="0"><testcase classname="harness" name="pytest"><failure message="pytest failed before producing JUnit output" /></testcase></testsuite></testsuites>
XML
fi
exit "$status"
