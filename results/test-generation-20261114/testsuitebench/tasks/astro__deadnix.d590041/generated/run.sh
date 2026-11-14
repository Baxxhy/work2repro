#!/bin/sh
cd /workspace/eval
python3 -m pytest -q --junitxml=/workspace/eval/results.xml
status=$?
# pytest writes JUnit XML after completing the full suite; preserve its status.
exit "$status"
