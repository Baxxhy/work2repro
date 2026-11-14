#!/bin/sh
set -u
cd "$(dirname "$0")"
python3 -m pytest -q --junitxml=/workspace/eval/results.xml
status=$?
if [ ! -s /workspace/eval/results.xml ]; then
  cat > /workspace/eval/results.xml <<'EOF'
<testsuites><testsuite name="eval" tests="1" errors="1"><testcase classname="runner" name="pytest"><error message="pytest did not produce a report" /></testcase></testsuite></testsuites>
EOF
fi
exit "$status"
