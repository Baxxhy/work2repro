import ast,json,tempfile,types
from pathlib import Path
base=Path(__file__).resolve()
# Locate checkout when run in diagnostics or published reports.
ancestors=list(base.parents)
repo=next((p for p in ancestors if (p/'results/test-generation-20261114').exists()),None)
if repo is None:
 workspace=next(p for p in ancestors if (p/'publication/work2repro').exists())
 repo=workspace/'publication/work2repro'
artifacts=repo/'results/test-generation-20261114'
gromacs=artifacts/'testsuitebench/tasks/gromacs__gromacs.665ea4c/generated'
tree=ast.parse((gromacs/'test_interface.py').read_text())
assignment=next(n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='COMMANDS' for t in n.targets))
scope={};exec(compile(ast.Module(body=[assignment],type_ignores=[]),'commands','exec'),scope)
source=artifacts/'testsuitebench/tasks/burntsushi__ripgrep.3b7fd44/generated/test_suite.py'
tree=ast.parse(source.read_text());node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='test_json_events_are_valid_and_compact')
payload=b'\n'.join(json.dumps({'type':kind}).encode() for kind in ['begin','match','end','summary'])+b'\n'
namespace={'run':lambda *a,**k:types.SimpleNamespace(returncode=0,stderr=b'',stdout=payload)}
exec(compile(ast.Module(body=[node],type_ignores=[]),str(source),'exec'),namespace)
with tempfile.TemporaryDirectory() as directory:namespace[node.name](Path(directory))
def translate(pos,delta,swapped=False):
 d=list(delta)
 if swapped:d[0],d[1]=d[1],d[0]
 return tuple(round(a+b,6) for a,b in zip(pos,d))
symmetric=[translate((1,1,1),(.5,.5,.5),v) for v in [False,True]]
asymmetric=[translate((1,2,4),(.1,.3,.7),v) for v in [False,True]]
assert symmetric[0]==symmetric[1] and asymmetric[0]!=asymmetric[1]
result={'ripgrep_original_test_function_accepts_missing_data':True,'ripgrep_probe_scope':'Generated test function with synthetic run result; no program or benchmark evaluation executed','symmetric_correct_and_swapped':symmetric,'asymmetric_correct_and_swapped':asymmetric,'gromacs_commands':len(scope['COMMANDS']),'help_parameterized_items':2*len(scope['COMMANDS']),'all_test_items_in_existing_score':191,'help_item_fraction':2*len(scope['COMMANDS'])/191}
(base.parent/'局部核验结果-11-17.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
