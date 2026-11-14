#!/bin/sh
cd /workspace/eval
python3 -m pytest -q --junitxml=/workspace/eval/results.xml
status=$?
if [ ! -s /workspace/eval/results.xml ]; then
  cat > /workspace/eval/results.xml <<'EOF'
<testsuites><testsuite name="pytest" tests="1" failures="1" errors="0" skipped="0"><testcase classname="runner" name="pytest"><failure message="pytest failed before writing JUnit XML"/></testcase></testsuite></testsuites>
EOF
fi
exit "$status"
