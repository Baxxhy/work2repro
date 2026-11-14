#!/bin/sh
cd /workspace/eval
python3 -m pytest -q --junitxml=/workspace/eval/results.xml
status=$?
if [ ! -s /workspace/eval/results.xml ]; then
  cat > /workspace/eval/results.xml <<'EOF'
<?xml version="1.0" encoding="utf-8"?>
<testsuites><testsuite name="pytest" tests="1" errors="1"><testcase classname="runner" name="pytest"><error message="pytest failed to produce JUnit XML"/></testcase></testsuite></testsuites>
EOF
fi
exit "$status"
