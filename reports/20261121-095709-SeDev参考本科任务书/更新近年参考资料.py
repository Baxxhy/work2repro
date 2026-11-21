from pathlib import Path
from zipfile import ZipFile
from lxml import etree as E
from datetime import datetime
from zoneinfo import ZoneInfo
import shutil
b=Path('/root/Baxxhy/work2/diagnostics/20261121-095709-SeDev参考本科任务书')
p=b/'基于需求语义分析的测试用例生成方法研究-任务书-11-21.docx'
backup=b/'历史版本/任务书-更新近年文献前-11-21.docx'
shutil.copy2(p,backup)
with ZipFile(p) as z:
 infos=z.infolist();data={i.filename:z.read(i.filename) for i in infos}
r=E.fromstring(data['word/document.xml']);ns={'w':r.nsmap['w']}
refs={3:'Folorunsho O, Reza H. AI-Driven Test Case Generation from Natural Language Requirements: A Survey of Techniques and Research Gaps[EB/OL]. arXiv:2606.06563, 2026.',4:'Milchevski D, Frank G, Hätty A, et al. Multi-Step Generation of Test Specifications using Large Language Models for System-Level Requirements[C]//Proceedings of ACL (Volume 6: Industry Track). 2025: 132-146.',5:'Hasan N B, Islam M A, Khan J Y, et al. Automatic High-Level Test Case Generation using Large Language Models[C]//2025 IEEE/ACM 22nd International Conference on Mining Software Repositories (MSR). 2025.'}
t=r.findall('.//w:tbl',ns)[2]
for i,txt in refs.items():
 nodes=t.findall('w:tr',ns)[i].findall('w:tc',ns)[1].findall('.//w:t',ns);pos=0
 for j,n in enumerate(nodes):
  size=len(n.text or '') if j<len(nodes)-1 else len(txt)-pos
  n.text=txt[pos:pos+size];pos+=size
  n.set('{http://www.w3.org/XML/1998/namespace}space','preserve')
with ZipFile(p,'w') as z:
 for i in infos:z.writestr(i,E.tostring(r,xml_declaration=True,encoding='UTF-8',standalone=True) if i.filename=='word/document.xml' else data[i.filename])
s=next(Path('/root/.codex/attachments/897a872c-ac62-4aac-a920-6e1ff7fdd7a7').glob('*.docx'))
with ZipFile(s) as z,ZipFile(p) as a:
 roots=[E.fromstring(x.read('word/document.xml')) for x in (z,a)]
 for root in roots:
  for n in root.findall('.//w:t',ns):n.text='';n.attrib.pop('{http://www.w3.org/XML/1998/namespace}space',None)
 assert E.tostring(roots[0])==E.tostring(roots[1])
 assert all(z.read(n)==a.read(n) for n in z.namelist() if n!='word/document.xml')
from docx import Document
old=Document(backup);new=Document(p)
for i in (0,1,3):assert old.tables[i]._element.xml==new.tables[i]._element.xml
now=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
report='''# 近年参考资料更新说明

修订时间：'''+now+'''

按用户“优先25、26论文”要求，只替换第3、4、5条参考资料。9篇中2026年5篇、2025年3篇、2024年1篇；中文3篇、英文6篇。保留2024年Bhatia等人的需求规格测试生成研究，因其与选题直接相关。SeDev仍为主要参考。

新增资料及核验入口：
- Folorunsho、Reza，2026年需求到测试生成综述：https://arxiv.org/abs/2606.06563 （预印本，按EB/OL标注）。
- Milchevski等，2025年系统需求到测试规格多步骤生成：https://aclanthology.org/2025.acl-industry.11/ （工业轨，文献中明确标注，不称为主会研究长文）。
- Hasan等，2025年高层测试用例生成：https://arxiv.org/abs/2503.17998 ；会议确认：https://2025.msrconf.org/details/msr-2025-technical-papers/2/Automatic-High-Level-Test-Case-Generation-using-Large-Language-Models （MSR Technical Papers，非ICSE主会论文）。

验证：题目、正文、进度表XML与修订前一致；所有非文字格式XML与第一份用户模板一致；其余DOCX成员逐字节一致。保留9条参考资料。实际换行、分页仍未视觉核验。原版本保存在历史版本目录。
'''
(b/'近年参考资料更新说明-11-21.md').write_text(report)
shutil.copy2('/tmp/update_recent_refs.py',b/'更新近年参考资料.py')
shutil.copytree(b,Path('/root/Baxxhy/work2/publication/work2repro/reports')/b.name,dirs_exist_ok=True)
print('PASS: 8/9篇为2025—2026；正文不变；模板格式一致')
