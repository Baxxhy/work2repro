#!/bin/sh
set -u
cd /workspace/eval || exit 1
python3 -m pytest -q --junitxml=/workspace/eval/results.xml
status=$?
if [ ! -s /workspace/eval/results.xml ]; then
  cat > /workspace/eval/results.xml <<'EOF'
<?xml version="1.0" encoding="utf-8"?>
<testsuites tests="1" errors="1" failures="0" skipped="0" time="0">
  <testsuite name="runner" tests="1" errors="1" failures="0" skipped="0" time="0">
    <testcase classname="runner" name="pytest invocation">
      <error message="pytest did not produce a JUnit report">pytest invocation failed before report generation</error>
    </testcase>
  </testsuite>
</testsuites>
EOF
fi
exit "$status"
