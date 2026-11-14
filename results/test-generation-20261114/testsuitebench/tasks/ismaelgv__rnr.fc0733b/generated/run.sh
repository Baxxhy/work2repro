#!/bin/sh
set -u
cd /workspace/eval || exit 1
python3 -m pytest -q --basetemp=/workspace/eval/.pytest-tmp --junitxml=/workspace/eval/results.xml
status=$?
if [ ! -s /workspace/eval/results.xml ]; then
  cat > /workspace/eval/results.xml <<'EOF'
<testsuites><testsuite name="pytest" tests="1" errors="1"><testcase name="pytest"><error message="pytest did not produce a report" /></testcase></testsuite></testsuites>
EOF
fi
exit "$status"
