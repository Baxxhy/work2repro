#!/bin/sh
set -u
cd /workspace/eval
python3 -m pytest -q --junitxml=/workspace/eval/results.xml
status=$?
# pytest writes JUnit XML even when tests fail. Preserve its status for the caller.
exit "$status"
