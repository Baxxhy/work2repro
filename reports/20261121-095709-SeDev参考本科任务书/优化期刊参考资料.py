from pathlib import Path
from zipfile import ZipFile
from lxml import etree as E
from datetime import datetime
from zoneinfo import ZoneInfo
import shutil
b=Path('diagnostics/20261121-095709-SeDev参考本科任务书');p=b/'基于需求语义分析的测试用例生成方法研究-任务书-11-21.docx'
shutil.copy2(p,b/'历史版本/任务书-期刊资料优化前-11-21.docx')
with ZipFile(p) as z:infos=z.infolist();data={i.filename:z.read(i.filename) for i in infos}
r=E.fromstring(data['word/document.xml']);ns={'w':r.nsmap['w']}
def put(el,txt):
 nodes=el.findall('.//w:t',ns)
 if not nodes:
  run=el.find('.//w:r',ns)
  if run is None:
   para=el.find('.//w:p',ns);run=E.SubElement(para,'{'+ns['w']+'}r')
  nodes=[E.SubElement(run,'{'+ns['w']+'}t')]
 pos=0
 for j,n in enumerate(nodes):
  size=len(n.text or '') if j<len(nodes)-1 else len(txt)-pos
  n.text=txt[pos:pos+size];pos+=size;n.set('{http://www.w3.org/XML/1998/namespace}space','preserve')
tables=r.findall('.//w:tbl',ns)
for i,txt in {4:'Yang Z, Huang R, Cui C, et al. Requirements-Based Test Generation: A Comprehensive Survey[J]. ACM Transactions on Software Engineering and Methodology, 2026, 35(10): 343:1-343:61.',8:'董益宏, 姜雪, 钱家如, 等. 基于大语言模型智能体的代码生成综述[J]. 软件学报, 2026, 37(8): 3089-3115.'}.items():put(tables[2].findall('w:tr',ns)[i].findall('w:tc',ns)[1],txt)
changes={'2025年12月':'2026年12月','教师科研题':'','（2）参考相关论文的需求驱动测试流程，分析需求中的功能与约束，设计从需求描述生成文字测试用例、再转换为可执行测试的方法，实现利用测试验证生成代码的原型工具；':'（2）分析需求中的功能与约束，设计从需求描述生成文本测试用例并转换为可执行测试的方法，实现用于验证生成代码的测试用例生成原型工具；','（3）选取小规模功能需求案例，分别生成代码与测试，执行测试并与直接生成测试的方法对比，从用例正确性、需求覆盖程度和代码验证效果等方面开展实验分析；':'（3）在公开或自有数据集上进行实验，验证所提出方法的有效性；','（5）通过设计开发，提升综合素养、自主学习能力、批判性思维意识和创新意识，综合运用所学知识，掌握科学研究的一般方法和技术。':'通过设计开发，提升综合素养、自主学习能力、批判性思维意识和创新意识，综合运用所学知识，掌握科学研究的一般方法和技术。'}
for para in r.findall('.//w:p',ns):
 txt=''.join(para.itertext()) if False else ''.join(para.xpath('.//w:t/text()',namespaces=ns))
 if txt in changes:put(para,changes[txt])
put(tables[0].findall('w:tr',ns)[2].findall('w:tc',ns)[1],'邝砾')
newdata=E.tostring(r,xml_declaration=True,encoding='UTF-8',standalone=True)
# Check every existing formatting element, despite filling previously blank text.
old=E.fromstring(data['word/document.xml'])
for tag in ['pPr','rPr','tblPr','tcPr','trPr','sectPr']:
 assert [E.tostring(x) for x in old.findall('.//w:'+tag,ns)]==[E.tostring(x) for x in r.findall('.//w:'+tag,ns)],tag
with ZipFile(p,'w') as z:
 for i in infos:z.writestr(i,newdata if i.filename=='word/document.xml' else data[i.filename])
assert 'SeDev' not in newdata.decode()
report='''# 高质量期刊参考资料修订

完成时间：'''+datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()+'''

替换第4条为TOSEM 2026需求测试生成综述，第8条为软件学报2026代码生成综述。英文4篇A会研究轨、1篇TOSEM、1篇MSR；无工业轨。中文保留1篇直接相关的华东师范大学学报论文及2篇软件学报综述。全部2025—2026年，3中文6英文。

核验来源：
- https://huangrubing.github.io/ （作者主页：TOSEM 35(10),343:1-343:61,2026）
- https://arxiv.org/abs/2505.02015 （作者预印本及正式DOI：10.1145/3771727；ACM页面403无法直接访问）
- https://rjxb.alljournals.cn/jos/article/pdf/7593 （中文期刊原文）

同步用户本轮提供的第2、3项、最后一段无编号、指导教师邝砾、题目来源空白、封面2026年12月。签署日期2025年10月及2026届仍按用户文本保留，但存在时间不一致，需正式签署时确认；不能自行编造日期。

验证：所有段落、文字、表格、单元格及页面属性元素与修改前相同，其余DOCX成员沿用原内容；填入原空白指导教师单元格可能新增文字节点；实际分页未视觉核验。旧版本已保留。
'''
(b/'高质量期刊参考资料修订-11-21.md').write_text(report)
shutil.copy2('/tmp/improve_refs.py',b/'优化期刊参考资料.py')
shutil.copytree(b,Path('publication/work2repro/reports')/b.name,dirs_exist_ok=True)
print('PASS: 引用与用户正文更新；所有格式属性保留')
