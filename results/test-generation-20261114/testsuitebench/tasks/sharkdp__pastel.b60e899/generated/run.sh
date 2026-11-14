#!/usr/bin/env bash
set -u
cd /workspace/eval

# Pytest's JUnit writer records all individual outcomes and continues after
# failures. Preserve its status for callers while ensuring results.xml exists.
pytest -q --junitxml=/workspace/eval/results.xml
status=$?
if [[ ! -s /workspace/eval/results.xml ]]; then
  cat > /workspace/eval/results.xml <<'XML'
<testsuites><testsuite name="suite" tests="1" failures="0" errors="1"><testcase classname="runner" name="pytest"><error message="pytest did not produce a report" /></testcase></testsuite></testsuites>
XML
fi
exit "$status"
