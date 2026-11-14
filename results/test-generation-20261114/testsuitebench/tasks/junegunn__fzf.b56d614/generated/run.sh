#!/bin/sh
set -u
cd /workspace/eval || exit 1
python3 -m pytest -q --junitxml=/workspace/eval/results.xml
status=$?
if [ ! -s /workspace/eval/results.xml ]; then
  python3 - <<'PY'
from xml.etree.ElementTree import Element, SubElement, ElementTree
root = Element('testsuites')
suite = SubElement(root, 'testsuite', name='pytest', tests='1', failures='0', errors='1', skipped='0')
case = SubElement(suite, 'testcase', classname='harness', name='pytest-startup')
SubElement(case, 'error', message='pytest did not produce a report').text = 'pytest did not produce a report'
ElementTree(root).write('/workspace/eval/results.xml', encoding='utf-8', xml_declaration=True)
PY
fi
exit "$status"
