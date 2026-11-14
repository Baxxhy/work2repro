#!/bin/sh
cd /workspace/eval
pytest --junitxml=/workspace/eval/results.xml
status=$?
if [ ! -s /workspace/eval/results.xml ]; then
  python3 - <<'PY'
from xml.etree.ElementTree import Element, SubElement, ElementTree
r=Element('testsuites'); s=SubElement(r,'testsuite',name='pytest',tests='1',failures='0',errors='1',skipped='0')
c=SubElement(s,'testcase',name='pytest_runner',classname='runner'); e=SubElement(c,'error',message='pytest failed before producing JUnit XML'); e.text='pytest did not create results.xml'
ElementTree(r).write('/workspace/eval/results.xml',encoding='utf-8',xml_declaration=True)
PY
fi
exit "$status"
