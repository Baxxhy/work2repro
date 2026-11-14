#!/bin/sh
set +e
cd /workspace/eval
python3 -m pytest -q --junitxml=/workspace/eval/results.xml
status=$?
if [ ! -s /workspace/eval/results.xml ]; then
  cat > /workspace/eval/results.xml <<'EOF'
<testsuites><testsuite name="pytest" tests="1" failures="1"><testcase name="pytest_runner"><failure message="pytest failed before producing a report"/></testcase></testsuite></testsuites>
EOF
fi
exit "$status"
