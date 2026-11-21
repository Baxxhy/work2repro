from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
from lxml import etree as E
from copy import deepcopy,copy
from datetime import datetime
from zoneinfo import ZoneInfo
import shutil
b=Path('/root/Baxxhy/work2/diagnostics/20261121-095709-SeDev参考本科任务书')
p=b/'基于需求语义分析的测试用例生成方法研究-任务书-11-21.docx'
old=b/'历史版本';old.mkdir(exist_ok=True)
shutil.copy2(p,old/'任务书-英文参考资料版-11-21.docx')
z=ZipFile(p);payload={x.filename:z.read(x.filename) for x in z.infolist()};infos=[copy(x) for x in z.infolist()];z.close()
r=E.fromstring(payload['word/document.xml']);ns={'w':r.nsmap['w']}
t=r.findall('.//w:tbl',ns)[2]
refs={2:'宫泽正, 沈富可, 魏同权. 基于大语言模型的测试用例图谱生成研究[J]. 华东师范大学学报(自然科学版), 2026(4): 143-153.',8:'罗嘉乐, 王涛, 程良伦, 等. 基于大语言模型的组件化工业软件系统测试用例生成方法[J]. 广东工业大学学报, 2026, 43(4): 91-102.',9:'吉品, 冯洋, 吴朵, 等. 面向智能软件系统的测试用例生成方法综述[J]. 软件学报, 2026, 37(1): 62-101.'}
for i,txt in refs.items():
 c=t.findall('w:tr',ns)[i].findall('w:tc',ns)[1];nodes=c.findall('.//w:t',ns);pos=0
 for j,n in enumerate(nodes):
  size=len(n.text or '') if j<len(nodes)-1 else len(txt)-pos
  n.text=txt[pos:pos+size];pos+=size
  n.set('{http://www.w3.org/XML/1998/namespace}space','preserve')
with ZipFile(p,'w',ZIP_DEFLATED) as z:
 for info in infos:z.writestr(info,E.tostring(r,xml_declaration=True,encoding='UTF-8',standalone=True) if info.filename=='word/document.xml' else payload[info.filename])
a=E.fromstring(payload['word/document.xml']);bxml=deepcopy(r)
for root in [a,bxml]:
 for n in root.findall('.//w:t',ns):n.text='';n.attrib.pop('{http://www.w3.org/XML/1998/namespace}space',None)
assert E.tostring(a)==E.tostring(bxml)
from docx import Document
d=Document(p);od=Document(old/'任务书-英文参考资料版-11-21.docx')
assert d.tables[1].cell(4,0).text==od.tables[1].cell(4,0).text
assert d.tables[0].cell(0,1).text==od.tables[0].cell(0,1).text
assert len(d.tables[2].rows)==10
# Direct comparison to source template: all non-text XML and all other zip members.
src=next(Path('/root/.codex/attachments/897a872c-ac62-4aac-a920-6e1ff7fdd7a7').glob('*.docx'))
z=ZipFile(src);srcxml=E.fromstring(z.read('word/document.xml'))
for n in srcxml.findall('.//w:t',ns):n.text='';n.attrib.pop('{http://www.w3.org/XML/1998/namespace}space',None)
assert E.tostring(srcxml)==E.tostring(bxml)
assert all(z.read(n)==ZipFile(p).read(n) for n in z.namelist() if n!='word/document.xml')
now=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
(b/'中英文参考资料与一致性核查-11-21.md').write_text('''# 中英文参考资料与一致性核查

修订完成时间：'''+now+'''

上一版9条参考资料全部为英文，不满足本次提出的中英文兼有要求。现修订为3条中文、6条英文，参考资料表仍为9条；第1条保留ACL 2026主会SeDev。中文资料已在期刊官网或软件学报官方聚合页面核实作者、题名、年份与页码。

中文资料来源：
1. https://xblk.ecnu.edu.cn/CN/abstract/abstract26406.shtml
2. https://xbzrb.gdut.edu.cn/cn/article/doi/10.12052/gdutxb.250017
3. https://rjxb.alljournals.cn/jos/article/pdf/7450

一致性结果：
- 题目与上一版完全相同。
- 研究背景和5项工作要求与上一版逐字相同；仍是同一需求分别用于代码生成与测试生成，再执行测试验证代码，不是缺陷报告生成测试。
- 只修改第2、8、9条参考资料，正文与进度均未修改。
- 直接与第一份原附件比较：去除文本及空白保留标记后，document.xml完全相同；其余压缩包成员逐字节相同，字体、字号、行距、段落、表格、边框、页边距、页眉页脚均未改变。
- 两份模板均为4张表，页面尺寸及页边距相同；第一份共92个段落节点，第二份94个，因此不能声称与两份原稿所有细节同时完全一致。本稿严格使用第一份作为底稿。
- Word内容长度变化可能改变换行。此前LibreOffice持续启动崩溃，尚未完成视觉分页核验，不作版面逐页完全一致的承诺。
- 原模板2025日期及2026届保持原样，实际提交应按真实届次和签署时间填写。

修订前版本保存在历史版本目录。原始用户附件未上传。
''')
shutil.copy('/tmp/fix_refs.py',b/'修订中英文参考资料.py')
print('PASS: 3中文+6英文；正文未变；与第一份原模板非文字结构相同')
pub=Path('/root/Baxxhy/work2/publication/work2repro/reports')/b.name
shutil.copytree(b,pub,dirs_exist_ok=True)
