from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
from lxml import etree as E
from datetime import datetime
from zoneinfo import ZoneInfo
base=Path('/root/Baxxhy/work2/diagnostics')/(datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y%m%d-%H%M%S')+'-本科毕设任务书');base.mkdir()
Path('/tmp/task_dir').write_text(str(base))
src=next(Path('/root/.codex/attachments/897a872c-ac62-4aac-a920-6e1ff7fdd7a7').glob('*.docx'))
z=ZipFile(src);r=E.fromstring(z.read('word/document.xml'));ns={'w':r.nsmap['w']};ts=r.findall('.//w:tbl',ns)
def put(p,s):
 nodes=p.findall('.//w:t',ns)
 # Preserve every run and its formatting, distribute replacement over original run lengths.
 pos=0
 for i,n in enumerate(nodes):
  take=len(n.text or '') if i<len(nodes)-1 else len(s)-pos
  n.text=s[pos:pos+take];pos+=take
  n.set('{http://www.w3.org/XML/1998/namespace}space','preserve')
def cell(t,row,col):return ts[t].findall('w:tr',ns)[row].findall('w:tc',ns)[col]
def cp(t,row,col,s):put(cell(t,row,col).find('w:p',ns),s)
title='基于需求要素分解的功能测试用例生成方法研究'
cp(0,0,1,title);cp(1,0,1,title)
p=cell(1,4,0).findall('w:p',ns)
texts=[
'软件需求是功能测试用例设计的重要依据，但自然语言需求中的输入约束、触发条件和预期结果往往混合表述，人工编写用例容易遗漏边界与异常场景。直接使用大语言模型生成用例也可能忽略约束或补充无依据的预期结果。因此，研究基于需求要素分解的功能测试用例生成方法，将需求整理为明确的测试要素，并结合等价类与边界值规则生成用例，有助于提高需求覆盖程度和用例设计效率。',
'毕业设计主要工作要求：',
'（1）学习需求分析与软件测试基础，掌握等价类划分、边界值分析及大语言模型调用方法，调研基于需求的测试用例生成方法；',
'（2）面向小型管理系统，设计需求要素分解与用例生成流程，利用现成模型提取输入、条件及预期结果，结合规则补充边界用例，实现支持需求导入、用例生成与导出的原型工具；',
'（3）整理2—3个系统的30—50条需求，人工标注测试要点，与直接提示生成方法对比，统计要点覆盖率、用例有效率和重复率，分析遗漏与错误案例；',
None,None]
for q,s in zip(p,texts):
 if s is not None:put(q,s)
refs=[
'ISTQB. Certified Tester Foundation Level Syllabus, Version 4.0.1[EB/OL]. 2024. https://istqb.org/.',
'Andersson A, Malmeling A. Automated test case generation from software requirements using ChatGPT[D]. University West, 2024.',
'Garousi V, Bauer S, Felderer M. NLP-assisted software testing: A systematic mapping of the literature[EB/OL]. arXiv:1806.00696, 2018.',
'Zhao L, Alhoshan W, Ferrari A, et al. Natural Language Processing for Requirements Engineering: A Systematic Mapping Study[J]. ACM Computing Surveys, 2021, 54(3): 1-41.',
'Boddu R, Guo L, Mukhopadhyay S, et al. RETNA: From Requirements to Testing in a Natural Way[C]//IEEE International Requirements Engineering Conference. 2004: 262-271.',
'Bhatia S, Gandhi T, Kumar D, et al. System Test Case Design from Requirements Specifications: Insights and Challenges of Using ChatGPT[EB/OL]. arXiv:2412.03693, 2024.',
'Masuda S, Kouzawa S, Sezai K, et al. Generating High-Level Test Cases from Requirements using LLM: An Industry Study[EB/OL]. arXiv:2510.03641, 2025.',
'Cucumber. Gherkin Reference[EB/OL]. https://cucumber.io/docs/gherkin/reference/.',
'Cucumber. Writing better Gherkin[EB/OL]. https://cucumber.io/docs/bdd/better-gherkin/.'
]
for i,s in enumerate(refs,1):cp(2,i,1,s)
out=base/'基于需求要素分解的功能测试用例生成方法研究-任务书-11-21.docx'
with ZipFile(out,'w',ZIP_DEFLATED) as f:
 for x in z.infolist():f.writestr(x,E.tostring(r,xml_declaration=True,encoding='UTF-8',standalone=True) if x.filename=='word/document.xml' else z.read(x.filename))
# All XML structure and formatting must be identical after removing text contents.
z=ZipFile(src)
a=E.fromstring(z.read('word/document.xml'));b=E.fromstring(ZipFile(out).read('word/document.xml'))
for root in (a,b):
 for n in root.findall('.//w:t',ns):
  n.text='';n.attrib.pop('{http://www.w3.org/XML/1998/namespace}space',None)
assert E.tostring(a)==E.tostring(b)
assert all(z.read(n)==ZipFile(out).read(n) for n in z.namelist() if n!='word/document.xml')
(base/'格式验证-11-21.txt').write_text('通过：除正文文字外，所有打包文件保持逐字节一致；正文XML去除文字及空白保留标记后完全一致。保留段落、文字样式、表格、节设置、页边距、页眉页脚。\n')
print(base)
