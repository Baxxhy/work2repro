from pathlib import Path
from zipfile import ZipFile
from lxml import etree as E
from datetime import datetime
from zoneinfo import ZoneInfo
import shutil
b=Path('/root/Baxxhy/work2/diagnostics/20261121-095709-SeDev参考本科任务书');p=b/'基于需求语义分析的测试用例生成方法研究-任务书-11-21.docx'
backup=b/'历史版本/任务书-A会优先调整前-11-21.docx';shutil.copy2(p,backup)
with ZipFile(p) as z:infos=z.infolist();data={i.filename:z.read(i.filename) for i in infos}
r=E.fromstring(data['word/document.xml']);ns={'w':r.nsmap['w']}
refs={1:'Ma Z, Zhang X, Zhang J, et al. Dynamic Scaling of Unit Tests for Code Reward Modeling[C]//Proceedings of the 63rd Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers). 2025: 6917-6935.',3:'Mendoza D, Mavridou A, Katis A, et al. Automating Requirements Formalization: Using LLMs and Low-Complexity Distinguishing Traces for Semantic Validation[C]//Proceedings of the 48th International Conference on Software Engineering (ICSE). 2026.',6:'Nan Z, Guo Z, Liu K, et al. Test Intention Guided LLM-based Unit Test Generation[C]//2025 IEEE/ACM 47th International Conference on Software Engineering (ICSE). 2025.',7:'Huang D, Zhang J M, Harman M, et al. Measuring the Influence of Incorrect Code on Test Generation[C]//Proceedings of the 48th International Conference on Software Engineering (ICSE). 2026.'}
for i,txt in refs.items():
 nodes=r.findall('.//w:tbl',ns)[2].findall('w:tr',ns)[i].findall('w:tc',ns)[1].findall('.//w:t',ns);pos=0
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
old=Document(backup);new=Document(p)
for i in (0,1,3):assert old.tables[i]._element.xml==new.tables[i]._element.xml
report='''# A会优先参考资料核查

完成时间：'''+datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()+'''

当前版本替代此前参考资料清单：9篇均为2025—2026年，中文3篇、英文6篇；英文含4篇A类会议主会研究论文，1篇MSR技术论文、1篇ACL工业轨论文，无预印本。没有SeDev。只更新参考文献，题目、正文及进度表XML不变，非文字格式结构及其他ZIP成员与第一份原模板一致。视觉分页未核验。

|序号|论文中文译名|出处及用途|核验链接|
|---|---|---|---|
|1|面向代码奖励建模的单元测试动态扩展|ACL 2025主会长文；支撑用生成测试评价候选代码，不要求本科复现训练或动态扩展|https://aclanthology.org/2025.acl-long.343/|
|3|需求形式化自动化：利用大语言模型与低复杂度区分轨迹进行语义验证|ICSE 2026研究轨；支撑需求语义澄清，不是直接测试生成方法，不加入本科实现要求|https://conf.researchr.org/details/icse-2026/icse-2026-research-track/287/Automating-Requirements-Formalization-Using-LLMs-and-Low-Complexity-Distinguishing-T|
|4|利用大语言模型从系统级需求多步骤生成测试规格|ACL 2025工业轨；因需求到中间测试表示直接相关而保留，不计入4篇主会研究论文|https://aclanthology.org/2025.acl-industry.11/|
|5|利用大语言模型自动生成高层测试用例|MSR 2025技术论文；直接支持需求与测试对齐，不计作A会|https://2025.msrconf.org/details/msr-2025-technical-papers/2/Automatic-High-Level-Test-Case-Generation-using-Large-Language-Models|
|6|测试意图引导的大语言模型单元测试生成|ICSE 2025研究轨；支持输入、预期结果等测试意图组织。虽含工业案例，但会议轨道确为Research Track|https://conf.researchr.org/details/icse-2025/icse-2025-research-track/242/Test-Intention-Guided-LLM-based-Unit-Test-Generation|
|7|衡量错误代码对测试生成的影响|ICSE 2026研究轨；用于解释代码输入会影响测试可靠性以及自然语言描述的作用，不把毕设改为缺陷报告生成测试|https://conf.researchr.org/details/icse-2026/icse-2026-research-track/15/Measuring-the-Influence-of-Incorrect-Code-on-Test-Generation|

学校与会议网页核验ICSE A类及轨道；ACL主会以Anthology Volume 1 Long Papers识别，Industry Track单列。未据A会等级推断每篇均直接解决需求生成测试问题；各篇支持范围见表。中文三篇延续已核实的期刊资料。原始附件不上传，旧版本保留。
'''
(b/'A会优先参考资料核查-11-21.md').write_text(report)
shutil.copy2('/tmp/update_a_refs.py',b/'更新A会优先参考资料.py')
shutil.copytree(b,Path('/root/Baxxhy/work2/publication/work2repro/reports')/b.name,dirs_exist_ok=True)
print('PASS: 4篇A会主会研究论文；1篇工业轨；正文与模板格式设置未变')
