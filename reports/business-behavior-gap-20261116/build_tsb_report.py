import json
import re
from pathlib import Path
ROOT=Path(__file__).resolve().parent

def read(p):return json.loads(p.read_text())
def link(p,label=None):return f'[{label or p.name}]({p.resolve()})'
def excerpt(p,start,end):
 lines=p.read_text().splitlines()
 return link(p)+f' 第{start}—{end}行\n\n```text\n'+'\n'.join(f'{i+1:4} {lines[i]}' for i in range(start-1,min(end,len(lines))))+'\n```'
notes={
'01':('局部输入缺失与有效业务操作并存','add/query/remove/import/edit实际操作与状态检查均存在。repo_1接受重复--score、repo_3接受空路径、repo_4隐藏help中的score，均存活。repo_2非数字score变异被test_usage_errors_are_status_two[bad-score]杀死。不能把四条选中元数据都标为存活。当前材料支持局部输入或帮助契约覆盖差异，未确认业务操作整体被替代。',[( 'generated/eval/test_cli.py',31,58)],['test_cli.test_usage_errors_are_status_two[bad-score]']),
'02':('A工作流覆盖缺失与C帮助内容断言不足','规格明确要求与提供的daemon通信，并要求组隔离、依赖与持久任务状态。全部48个测试实例集中于help/version、解析、配置错误及缺失socket。没有成功提交并观察任务状态的流程。该套件业务覆盖缺失已确认，但不能仅凭现有报告判定生成时是否具备可用daemon。\n\n单独可与存活直接对照的C证据是test_each_command_has_standalone_help只检查退出0、非空stdout和空stderr。repo_4把enqueue描述改为queued，repo_5把env改成只读，repo_6把follow改成快照，全部存活；明确帮助语义不受该断言约束。这些CLI文字证据与业务状态缺失分开记载，尚未建立工作流缺失对具体状态变异的漏检因果。', [('requirements/spec.md',39,65),('requirements/spec.md',458,466),('generated/eval/test_cli.py',59,69),('generated/eval/test_cli.py',232,244)],['test_cli.test_each_command_has_standalone_help[enqueue]','test_cli.test_each_command_has_standalone_help[env]','test_cli.test_each_command_has_standalone_help[follow]']),
'03':('C诊断内容约束不足，真实重命名流程存在','缺少命令/未知命令测试只检查部分前缀、退出码和unrecognized文本。repo_1/2/3分别删除命令列表、usage或help提示后仍存活。该局部CLI预言不足不能扩展成未执行重命名。候选还有真实文件重命名、backup、dump/replay及undo检查，repo_25由regex_captures_and_transform杀死。global_help_and_version在正确实现失败，不能把它的失败用作有效杀死证据。', [('generated/eval/test_cli.py',55,61),('generated/eval/test_cli.py',163,188)],['test_cli.test_missing_and_unknown_commands','test_cli.test_chain_order_execution','test_cli.test_from_file_preview_force_undo_and_validation']),
'04':('未确认同类业务缺口，存在参考实现失败测试','执行了实际SQL、文件持久化和重开。事务rollback测试在正确实现失败，不能作为成功验证事务的证据。前三个存活都涉及版本输出，而生成的version_contract、version_alias_and_sql_version、dot_version_first_two_lines在正确实现已失败，按有效测试口径无法贡献kill。这组证据主要体现无效测试与局部契约差异，不能据此确认B/C业务状态缺口。repo_7忽略--readonly写保护，被test_files_and_storage.test_readonly_alias_has_same_write_behavior杀死，支持真实存储边界得到检查。', [('generated/eval/test_cli.py',4,17),('generated/eval/test_cli.py',157,176)],['test_cli.test_persistent_database_reopens_and_isolates','test_files_and_storage.test_readonly_alias_has_same_write_behavior']),
'05':('高Mutation Score中仍有C局部预言缺口','帮助规格给出具体枚举和-x_noenv拼写；候选只检查版本标题、引导句、换行及与另一help调用相等。repo_2插入额外段落、repo_3将8)改成Eight)、repo_4将-x_noenv改成-x-noenv均存活。repo_5删除sqlite3则被test_versions杀死。实际生成配置、目录及资源的测试存在，不能将此例说成完全未执行文档业务。此例提供高分仍有局部断言缺口的对照，帮助文字与Req2Test业务角色/状态关系不同。', [('requirements/spec.md',26,35),('requirements/spec.md',65,77),('generated/eval/test_cli.py',25,52),('generated/eval/test_cli.py',184,196)],['test_cli.test_help_options_and_precedence','test_cli.test_no_args_matches_help_and_exact_error','test_cli.test_run_default_generated_config_creates_formats_and_warns']),
'06':('真实跨进程和Git状态检查的对照','test_capture_summary_preserved_commit_editor_and_main_checkout真实建立Git仓库和remote，调用程序后检查main分支、提交消息、README内容及远程commit一致。该测试在正确实现通过。前三个存活是bool参数/--后operand/普通operand接受行为，与该核心状态检查不属同一义务。CLI错误总测试本身在正确实现失败，不能推断这些存活全是有效测试弱断言。repo_4 help/version优先级变异被明确测试杀死。', [('generated/eval/test_eureka.py',191,203)],['test_eureka.test_capture_summary_preserved_commit_editor_and_main_checkout'])}
report=['# TestSuiteBench交叉核验\n','''## 样本与计分边界

从已发布165条结果中固定6个任务。低分组为zoxide、pueue、rnr、duckdb，均Validity≥0.8且Mutation Score≤0.25，进一步按状态或业务流程需求定向选择。doxygen为高Validity、高Mutation Score对照，eureka为相对较高Mutation Score且有明确Git状态流程的补充对照。不同应用的规格长度、变异池和任务难度没有匹配，不能据此比较因果效应或估计165条中的发生率。

Validity按正确实现上的测试实例通过数/测试实例数核对。Mutation Score按至少被一个正确实现通过的测试实例杀死的变异数/有效变异数核对。参数化实例按官方test_results名称计数。下列6个套件都有部分测试在正确实现失败，故高Validity不能写成整个套件通过。

每个任务抽取官方结果顺序中的前三个存活变异和首个被杀死控制，共24个，保存元数据与源码diff。选择顺序与元数据文件顺序可能不同，以下结果逐个按binary_id核验。源文件从已有reference_impl归档匹配，新增文件在reference-source-audit.json记录。共享条件分支源码按assignment_id/编译选择解释，不能把整份diff的所有分支当成一个变异。
''',link(ROOT/'selection.json','固定清单'),
'|任务|正确实现通过/总数|Validity|杀死/变异数|Mutation Score|\n|---|---|---|---|---|']
verified=[]
for d in sorted((ROOT/'cases').iterdir()):
 c=read(d/'case.json');r=read(d/'official-test-eval.json');g=next(x for x in r['binary_results'] if x['role']=='ground_truth');valid={x['name'] for x in g['test_results'] if x['status']=='passed'};sel=read(d/'mutant-selection.json')
 assert len(valid)/len(g['test_results'])==float(c['metrics']['validity_rate'])
 assert len(sel['killed_controls'])==int(c['metrics']['n_mutants_killed'])
 report.append(f"|{c['instance_id']}|{len(valid)}/{len(g['test_results'])}|{len(valid)/len(g['test_results']):.4f}|{len(sel['killed_controls'])}/{len(sel['survivors'])+len(sel['killed_controls'])}|{float(c['metrics']['mutation_score']):.4f}|")
for d in sorted((ROOT/'cases').iterdir()):
 c=read(d/'case.json');r=read(d/'official-test-eval.json');sel=read(d/'mutant-selection.json');g=next(x for x in r['binary_results'] if x['role']=='ground_truth');valid={t['name'] for t in g['test_results'] if t['status']=='passed'};title,note,snips,tests=notes[d.name]
 report += [f"\n## {c['instance_id']}\n\n### {title}\n",note,link(d/'requirements/spec.md','完整原始规格')+'；'+link(d/'official-test-eval.json','官方逐测试执行记录')+'；'+link(d/'failure-matrix.csv','原有结果矩阵')]
 for name,start,end in snips:report.append(excerpt(d/name,start,end))
 report += ['### 被引用测试的实际状态\n','|测试实例|正确实现状态|\n|---|---|']
 for name in tests:
  result=next(t for t in g['test_results'] if t['name']==name)
  report.append(f"|{name}|{result['status']}|")
 report += ['\n### 选中变异的执行结果\n','|binary_id / assignment_id|具体修改|有效测试杀死|杀死测试|证据|\n|---|---|---|---|---|']
 for m in sel['selected']:
  b=next(b for b in r['binary_results'] if b['binary_id']==m['id']);kills=[t['name'] for t in b['test_results'] if t['name'] in valid and t['status'] in ('failure','failed','error')]
  report.append(f"|{m['id']} / {m.get('assignment_id',m['id'])}|{m['mutation'].replace('|','/')}|{'是' if kills else '否'}|{', '.join(kills) or '无'}|{link(d/(m['id']+'.patch'),'源码差分')}|")
  verified.append({'instance_id':c['instance_id'],'binary_id':m['id'],'killed':bool(kills),'killing_valid_tests':kills})
 report.append('\n正确实现失败的测试实例包括 '+ '、'.join(t['name'] for t in g['test_results'] if t['status']!='passed')+'。')
report += ['''## 对核心假设的支持程度

Pueue提供完整规格中的业务工作流覆盖缺失证据，同时有独立的帮助文本C漏检。rnr与doxygen支持“已有调用和输出观察仍可能缺少指定内容约束”，但其代表性存活涉及CLI诊断/帮助内容。它们只能支持较宽泛的断言充分性问题，尚不能作为管理员视角、跨对象业务状态缺口的同机制跨Benchmark验证。

zoxide、rnr、duckdb和eureka中的真实状态检查提供反例，尤其eureka把本地提交与远程状态关联起来。低Mutation Score无法单独证明Agent绕过了业务操作。DuckDB版本用例展示无效测试造成的判别能力丧失，本轮把它作为不同机制记录。

因此，TestSuiteBench对“规格义务可能遗漏或弱断言”的现象提供独立支持，对“与Req2Test完全相同的业务执行—观察缺口具有普遍性”仍证据不足。尚需更多匹配业务边界的已有案例及更完整运行轨迹。
''']
(ROOT/'TSB_CROSS_VALIDATION.md').write_text(re.sub(r'(?m)(\|[^\n]*\|)\n\n(?=\|)', r'\1\n', '\n\n'.join(report))+'\n')
(ROOT/'tsb-verified-mutants.json').write_text(json.dumps(verified,indent=2)+'\n')
print('TSB verified',len(verified),'selected mutants across',len(notes),'tasks')
