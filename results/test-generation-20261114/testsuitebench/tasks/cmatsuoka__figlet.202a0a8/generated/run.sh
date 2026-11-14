#!/bin/sh
set +e
cd /workspace/eval || exit 1
python3 -m pytest -q --junitxml=/workspace/eval/results.xml
status=$?
if [ ! -s /workspace/eval/results.xml ]; then
    python3 - <<'PY'
from xml.etree.ElementTree import Element, SubElement, ElementTree
root = Element('testsuites')
suite = SubElement(root, 'testsuite', name='test_suite', tests='1', failures='1', errors='0', skipped='0')
case = SubElement(suite, 'testcase', classname='runner', name='pytest_runner')
failure = SubElement(case, 'failure', message='pytest did not produce a report')
failure.text = 'pytest invocation failed before writing results.xml'
ElementTree(root).write('/workspace/eval/results.xml', encoding='utf-8', xml_declaration=True)
PY
fi
exit "$status"
