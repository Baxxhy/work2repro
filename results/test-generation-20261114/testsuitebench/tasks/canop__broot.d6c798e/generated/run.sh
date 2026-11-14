#!/bin/sh
set +e
cd /workspace/eval
python3 -m pytest -q --junitxml=/workspace/eval/results.xml
status=$?
# pytest writes JUnit XML even when tests fail; preserve its test exit status.
exit "$status"
