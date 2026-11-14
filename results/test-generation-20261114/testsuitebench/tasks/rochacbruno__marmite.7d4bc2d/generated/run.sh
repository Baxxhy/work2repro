#!/bin/sh
set +e
cd /workspace/eval
python3 -m pytest -q --junitxml=/workspace/eval/results.xml
status=$?
if [ ! -s /workspace/eval/results.xml ]; then
  cat > /workspace/eval/results.xml <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<testsuites><testsuite name="pytest" tests="1" failures="1" errors="0" skipped="0"><testcase classname="runner" name="pytest"><failure message="pytest did not produce results.xml" /></testcase></testsuite></testsuites>
EOF
fi
exit "$status"
