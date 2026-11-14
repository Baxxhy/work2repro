#!/bin/sh
cd /workspace/eval
python3 -m pytest -q --junitxml=/workspace/eval/results.xml
status=$?
# pytest writes JUnit XML even when tests fail; preserve its status for the harness.
exit "$status"
