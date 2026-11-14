#!/bin/sh
set -u
cd /workspace/eval
python3 -m pytest -q --junitxml=/workspace/eval/results.xml
status=$?
exit "$status"
