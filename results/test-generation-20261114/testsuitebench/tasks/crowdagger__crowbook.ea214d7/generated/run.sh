#!/bin/sh
set +e
cd /workspace/eval
python3 -m pytest -q --junitxml=/workspace/eval/results.xml
status=$?
# pytest writes JUnit XML even when assertions fail; preserve its test result exit status.
exit "$status"
