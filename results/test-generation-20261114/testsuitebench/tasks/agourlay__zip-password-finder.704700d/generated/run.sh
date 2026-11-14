#!/bin/sh
set +e
cd /workspace/eval || exit 1
python3 -m pytest -q --junitxml=/workspace/eval/results.xml
status=$?
# pytest writes the complete JUnit report even when cases fail.
exit "$status"
