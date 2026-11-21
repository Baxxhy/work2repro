from pathlib import Path
from zipfile import ZipFile
from lxml import etree as E
from datetime import datetime
from zoneinfo import ZoneInfo
import shutil
b=Path('/root/Baxxhy/work2/diagnostics/20261121-095709-SeDev参考本科任务书');p=b/'基于需求语义分析的测试用例生成方法研究-任务书-11-21.docx'
shutil.copy2(p,b/'历史版本/任务书-移除指定文献前-11-21.docx')
with ZipFile(p) as z:infos=z.infolist();data={i.filename:z.read(i.filename) for i in infos}
r=E.fromstring(data['word/document.xml']);ns={'w':r.nsmap['w']}
nodes=r.findall('.//w:tbl',ns)[2].findall('w:tr',ns)[1].findall('w:tc',ns)[1].findall('.//w:t',ns)
txt='Xu T, Zhou Z, Chen X, et al. Requirements Dependency Driven Test Case Generation: An Automotive Industry Practice[C]//2025 IEEE 33rd International Requirements Engineering Conference (RE). 2025.'
pos=0
for j,n in enumerate(nodes):
 size=len(n.text or '') if j<len(nodes)-1 else len(txt)-pos
 n.text=txt[pos:pos+size];pos+=size;n.set('{http://www.w3.org/XML/1998/namespace}space','preserve')
with ZipFile(p,'w') as z:
 for i in infos:z.writestr(i,E.tostring(r,xml_declaration=True,encoding='UTF-8',standalone=True) if i.filename=='word/document.xml' else data[i.filename])
assert 'sedev' not in ''.join(r.itertext()).lower()
source=next(Path('/root/.codex/attachments/897a872c-ac62-4aac-a920-6e1ff7fdd7a7').glob('*.docx'))
with ZipFile(source) as z,ZipFile(p) as a:
 roots=[E.fromstring(x.read('word/document.xml')) for x in (z,a)]
 for root in roots:
  for n in root.findall('.//w:t',ns):n.text='';n.attrib.pop('{http://www.w3.org/XML/1998/namespace}space',None)
 assert E.tostring(roots[0])==E.tostring(roots[1])
 assert all(z.read(n)==a.read(n) for n in z.namelist() if n!='word/document.xml')
from docx import Document
old=Document(b/'历史版本/任务书-移除指定文献前-11-21.docx');new=Document(p)
for i in (0,1,3):assert old.tables[i]._element.xml==new.tables[i]._element.xml
(b/'指定文献移除记录-11-21.md').write_text('# 指定文献移除记录\n\n完成时间：'+datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()+'\n\n按用户要求从交付任务书中移除SeDev文献；替换为Xu等人2025年需求依赖驱动测试生成论文。来源：https://conf.researchr.org/details/RE-2025/RE-2025-industrial-innovation-papers/12/Requirements-Dependency-Driven-Test-Case-Generation-An-Automotive-Industry-Practice 。该文属于RE工业创新轨，仅作为相关资料，不宣称满足此前CCF A主会主参考要求。\n\n当前参考资料：2025年4篇、2026年4篇、2024年1篇，中文3篇、英文6篇。任务书正文无指定论文名称；题目、正文、进度表未变；格式结构与原模板相同。历史分析与旧版本保留作为过程记录，不能当作最新版参考清单。实际分页未视觉核验。\n')
shutil.copy2('/tmp/remove_reference.py',b/'移除指定参考资料.py')
shutil.copytree(b,Path('/root/Baxxhy/work2/publication/work2repro/reports')/b.name,dirs_exist_ok=True)
print('PASS: 名称已移除；9条文献；正文及格式设置不变')
