from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
from lxml import etree as E
from datetime import datetime
from zoneinfo import ZoneInfo
base=Path('/root/Baxxhy/work2/diagnostics')/(datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y%m%d-%H%M%S')+'-SeDev参考本科任务书');base.mkdir()
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
title='基于需求语义分析的测试用例生成方法研究'
cp(0,0,1,title);cp(1,0,1,title)
p=cell(1,4,0).findall('w:p',ns)
texts=[
'大语言模型能够根据自然语言需求生成程序代码，但生成结果是否满足功能要求仍需通过测试进行验证。若测试主要依据生成代码编写，可能忽略需求中的条件与预期行为，影响验证效果。因此，研究基于需求语义分析的测试用例生成方法，从需求中识别功能、输入条件和预期结果，生成相应的测试用例并用于验证生成代码，有助于提高需求验证的完整性和测试设计效率。',
'毕业设计主要工作要求：',
'（1）学习软件需求分析与软件测试基础，掌握大语言模型调用和Python测试框架的使用方法，调研需求驱动的代码生成与测试生成相关研究；',
'（2）参考相关论文的需求驱动测试流程，分析需求中的功能与约束，设计从需求描述生成文字测试用例、再转换为可执行测试的方法，实现利用测试验证生成代码的原型工具；',
'（3）选取小规模功能需求案例，分别生成代码与测试，执行测试并与直接生成测试的方法对比，从用例正确性、需求覆盖程度和代码验证效果等方面开展实验分析；',
None,None]
for q,s in zip(p,texts):
 if s is not None:put(q,s)
refs=[
'Yang R, Liu J, Zeng J, et al. SeDev: Structured Semantic Exploration for LLM-Driven Code Generation[C]//Proceedings of the 64th Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers). 2026: 35485-35512.',
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
out=base/'基于需求语义分析的测试用例生成方法研究-任务书-11-21.docx'
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
