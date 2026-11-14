#!/bin/sh
set +e
cd /workspace/eval || exit 1
python3 -m pytest -q --junitxml=/workspace/eval/results.xml
status=$?
# pytest writes JUnit XML even when tests fail. Keep a minimal valid report if pytest
# itself could not start (for example, if the runner image lacks pytest).
if [ ! -s /workspace/eval/results.xml ]; then
    cat > /workspace/eval/results.xml <<'XML'
<?xml version="1.0" encoding="UTF-8"?>
<testsuites><testsuite name="eval" tests="1" failures="0" errors="1"><testcase classname="runner" name="pytest"><error message="pytest did not produce a report"/></testcase></testsuite></testsuites>
XML
fi
exit "$status"
