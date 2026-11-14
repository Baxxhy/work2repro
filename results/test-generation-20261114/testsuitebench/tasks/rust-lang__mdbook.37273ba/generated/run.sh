#!/usr/bin/env bash
set -u
cd "$(dirname "$0")"
export MDBOOK_EXECUTABLE="${MDBOOK_EXECUTABLE:-/workspace/executable}"
python3 -m pytest -q --junitxml=/workspace/eval/results.xml
status=$?
if [ ! -s /workspace/eval/results.xml ]; then
    cat > /workspace/eval/results.xml <<'XML'
<?xml version="1.0" encoding="UTF-8"?>
<testsuites><testsuite name="eval" tests="1" failures="0" errors="1" skipped="0"><testcase classname="eval" name="pytest invocation"><error message="pytest did not produce a JUnit report" /></testcase></testsuite></testsuites>
XML
fi
exit "$status"
