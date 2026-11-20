from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
from lxml import etree as E
from datetime import datetime
from zoneinfo import ZoneInfo
base=Path('/root/Baxxhy/work2/diagnostics')/(datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y%m%d-%H%M%S')+'-多提示测试生成本科方案');base.mkdir()
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
title='基于多提示策略的需求驱动测试生成方法研究'
cp(0,0,1,title);cp(1,0,1,title)
p=cell(1,4,0).findall('w:p',ns)
texts=[
'自然语言描述的功能需求和缺陷报告是软件测试的重要依据，但将其转换为可执行测试需要理解输入条件与预期行为，人工编写成本较高。现成大语言模型能够辅助生成测试，但单一提示容易遗漏测试场景，生成的测试也可能存在语法或接口使用错误。因此，研究基于多提示策略的需求驱动测试生成方法，从不同角度生成候选测试，并结合执行结果进行检查，有助于提高测试的可用性和需求验证效果。',
'毕业设计主要工作要求：',
'（1）学习软件测试基础与Python测试框架，掌握大语言模型调用与提示设计方法，阅读需求驱动测试生成相关论文；',
'（2）参考多提示测试生成方法，针对功能需求与缺陷描述设计直接生成、示例引导和边界分析提示，结合执行结果检查语法与接口错误，实现支持需求输入、测试生成及结果展示的原型工具；',
'（3）选取20—30个小型Python案例，与单一提示方法对比，统计测试可执行率、需求符合率及缺陷检出率，分析不同提示策略的效果；',
None,None]
for q,s in zip(p,texts):
 if s is not None:put(q,s)
refs=[
'Ahmed T, Ganhotra J, Shinnar A, et al. Heterogeneous Prompting and Execution Feedback for SWE Issue Test Generation and Selection[C]//ICSE. 2026. DOI: 10.1145/3744916.3787837.',
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
out=base/'基于多提示策略的需求驱动测试生成方法研究-任务书-11-21.docx'
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
