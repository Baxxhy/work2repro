#!/bin/sh
set -u
cd /workspace/eval
python3 -m pytest -q --junitxml=/workspace/eval/results.xml
status=$?
# pytest writes the complete JUnit report even when tests fail.
exit "$status"
