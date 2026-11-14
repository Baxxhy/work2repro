#!/bin/sh
set -u
cd "$(dirname "$0")"
python3 -m pytest -q --junitxml=/workspace/eval/results.xml
