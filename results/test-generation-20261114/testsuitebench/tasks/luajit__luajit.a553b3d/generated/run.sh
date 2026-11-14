#!/bin/sh
set -eu
cd "$(dirname "$0")"
pytest --junitxml=results.xml
