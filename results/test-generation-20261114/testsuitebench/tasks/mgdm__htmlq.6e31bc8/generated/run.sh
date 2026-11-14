#!/bin/sh
cd /workspace/eval
exec pytest -q --junitxml=/workspace/eval/results.xml
