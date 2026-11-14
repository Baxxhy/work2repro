#!/bin/sh
cd /workspace/eval
set +e
pytest -q --junitxml=/workspace/eval/results.xml
status=$?
if [ ! -s /workspace/eval/results.xml ]; then
  python3 - <<'PY'
from pathlib import Path
Path('/workspace/eval/results.xml').write_text('<?xml version="1.0" encoding="utf-8"?>\n<testsuites><testsuite name="eval" tests="1" failures="1"><testcase classname="eval" name="pytest_collection"><failure message="pytest failed before producing JUnit XML" /></testcase></testsuite></testsuites>\n', encoding='utf-8')
PY
fi
exit "$status"
