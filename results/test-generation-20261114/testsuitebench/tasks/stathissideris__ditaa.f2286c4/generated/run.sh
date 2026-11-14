#!/bin/sh
set -eu
cd /workspace/eval
pytest --junitxml=/workspace/eval/results.xml
