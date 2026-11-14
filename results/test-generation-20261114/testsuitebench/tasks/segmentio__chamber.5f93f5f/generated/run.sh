#!/bin/sh
cd /workspace/eval || exit 1
pytest -q --junitxml=/workspace/eval/results.xml
