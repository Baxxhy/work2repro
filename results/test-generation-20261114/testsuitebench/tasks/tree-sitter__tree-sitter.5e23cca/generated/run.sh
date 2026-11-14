#!/bin/sh
set +e
cd /workspace/eval || exit 1
python3 -m pytest -q --junitxml=/workspace/eval/results.xml
status=$?
# pytest writes JUnit XML after the complete suite, including on assertion failures.
exit "$status"
