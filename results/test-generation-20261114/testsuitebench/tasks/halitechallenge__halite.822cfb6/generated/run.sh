#!/bin/sh
cd /workspace/eval || exit 1
python3 -m pytest -q --junitxml=/workspace/eval/results.xml
status=$?
# pytest writes JUnit XML even when tests fail; preserve its suite exit status.
exit "$status"
