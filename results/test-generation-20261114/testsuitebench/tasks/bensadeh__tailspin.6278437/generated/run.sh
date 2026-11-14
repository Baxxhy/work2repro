#!/bin/sh
cd /workspace/eval
exec python3 -m pytest -q --junitxml=/workspace/eval/results.xml
