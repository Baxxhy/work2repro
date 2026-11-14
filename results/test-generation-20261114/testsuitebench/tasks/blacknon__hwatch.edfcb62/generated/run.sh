#!/bin/sh
set +e
cd "$(dirname "$0")"
pytest --junitxml=/workspace/eval/results.xml
status=$?
exit "$status"
