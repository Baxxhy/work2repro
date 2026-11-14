#!/bin/sh
cd /workspace/eval || exit 2
exec python3 -m pytest -q --junitxml=/workspace/eval/results.xml
