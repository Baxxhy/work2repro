#!/bin/sh
cd /workspace/eval
python3 -m pytest -q --junitxml=/workspace/eval/results.xml
status=$?
# pytest writes a report even when tests fail; keep its exit status for the harness.
exit "$status"
