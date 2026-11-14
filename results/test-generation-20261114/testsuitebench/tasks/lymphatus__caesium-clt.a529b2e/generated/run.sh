#!/bin/sh
set -u
cd /workspace/eval
if command -v pytest >/dev/null 2>&1; then
  exec pytest -q --junitxml=/workspace/eval/results.xml
fi
exec python3 -m pytest -q --junitxml=/workspace/eval/results.xml
