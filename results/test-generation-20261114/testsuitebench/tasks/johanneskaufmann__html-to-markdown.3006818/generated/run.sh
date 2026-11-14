#!/bin/sh
set -u
cd /workspace/eval
export EXECUTABLE=/workspace/executable
python3 -m pytest -q --junitxml=/workspace/eval/results.xml
status=$?
if [ ! -s /workspace/eval/results.xml ]; then
  python3 - <<'PY'
from xml.etree.ElementTree import Element, SubElement, ElementTree
r=Element('testsuites')
s=SubElement(r,'testsuite',name='pytest',tests='1',failures='0',errors='1',skipped='0')
c=SubElement(s,'testcase',classname='runner',name='pytest-startup')
SubElement(c,'error',message='pytest failed to create its JUnit report').text='pytest did not produce results.xml'
ElementTree(r).write('/workspace/eval/results.xml',encoding='utf-8',xml_declaration=True)
PY
fi
exit "$status"
