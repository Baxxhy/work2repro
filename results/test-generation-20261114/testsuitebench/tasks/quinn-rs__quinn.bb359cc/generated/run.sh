#!/bin/sh
cd /workspace/eval
python3 -m pytest -q --junitxml=/workspace/eval/results.xml
status=$?
if [ ! -s /workspace/eval/results.xml ]; then
  cat > /workspace/eval/results.xml <<'EOF'
<testsuites><testsuite name="pytest" tests="1" failures="1"><testcase classname="runner" name="pytest"><failure message="pytest did not produce a report">runner failed before writing JUnit XML</failure></testcase></testsuite></testsuites>
EOF
fi
exit "$status"
