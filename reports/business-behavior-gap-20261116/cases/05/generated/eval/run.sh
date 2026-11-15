#!/bin/sh
set +e
cd /workspace/eval || exit 1
pytest -q --junitxml=/workspace/eval/results.xml
status=$?
# pytest writes the JUnit report even when individual cases fail.
exit "$status"
