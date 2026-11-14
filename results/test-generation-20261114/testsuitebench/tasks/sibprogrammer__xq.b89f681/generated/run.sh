#!/bin/sh
cd /workspace/eval
pytest -q --junitxml=/workspace/eval/results.xml
