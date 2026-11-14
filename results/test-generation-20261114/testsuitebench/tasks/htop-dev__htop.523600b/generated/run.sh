#!/bin/sh
cd /workspace/eval || exit 1
pytest --junitxml=/workspace/eval/results.xml
status=$?
if [ ! -s /workspace/eval/results.xml ]; then
    cat > /workspace/eval/results.xml <<'XML'
<?xml version="1.0" encoding="UTF-8"?>
<testsuites><testsuite name="pytest" tests="1" failures="0" errors="1"><testcase classname="runner" name="pytest"><error message="pytest did not produce JUnit XML" /></testcase></testsuite></testsuites>
XML
fi
exit "$status"
