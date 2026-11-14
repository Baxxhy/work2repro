#!/usr/bin/env bash
set +e
cd "$(dirname "$0")"
pytest -q --junitxml=/workspace/eval/results.xml
status=$?
# pytest writes JUnit XML on normal test failures. If collection/runtime setup
# prevents that, leave a valid one-suite report for the harness to consume.
if [[ ! -s /workspace/eval/results.xml ]]; then
  cat > /workspace/eval/results.xml <<'XML'
<?xml version="1.0" encoding="utf-8"?>
<testsuites><testsuite name="pytest" tests="1" failures="0" errors="1"><testcase classname="pytest" name="runner"><error message="pytest did not produce a report" /></testcase></testsuite></testsuites>
XML
fi
exit "$status"
