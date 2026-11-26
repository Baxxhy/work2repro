import ast,inspect,json,subprocess,sys,types
from timeout_policy import activate,Timeouts,GO_MODULES
activate()
from req2test.execute import ensure_engine_path
ensure_engine_path()
from r2t.go import execution,mutation_copy,runtime,mutation_runtime,registry,bootstrap
assert execution.COMMAND_TIMEOUT==1800
assert execution.RETIRE_TIMEOUT==1800
assert inspect.signature(execution.ExecutionCopy._call).parameters['timeout'].default==600
assert inspect.signature(execution.ExecutionCopy._checked).parameters['timeout'].default==600
assert inspect.signature(runtime.run_solution).parameters['timeout'].default==1800
assert inspect.signature(mutation_runtime.run_solution).parameters['timeout'].default==1800
assert runtime._options(1800)==1
try:runtime._options(600)
except ValueError:pass
else:raise AssertionError('stale runtime timeout accepted')
# Exercise actual transformed helper dispatch, including copy-reference.
class Runner:
    def run(self,command,**kwargs):
        self.timeout=kwargs['timeout'];return subprocess.CompletedProcess([],0,'ok','')
obj=object.__new__(execution.ExecutionCopy);obj.runner=Runner();obj.quarantined=False
obj._checked('copy-reference')
assert obj.runner.timeout==600
obj._checked('cleanup',timeout=120)
assert obj.runner.timeout==120
# All former short waits in these two modules have been transformed.
for mod in [execution,mutation_copy]:
    tree=Timeouts(mod.__name__).visit(ast.parse(inspect.getsource(mod)))
    assert not any(isinstance(n,ast.Constant) and type(n.value) is int and n.value in (15,30) for n in ast.walk(tree))
from req2test import layout
source=inspect.getsource(layout)
assert "timeout" in source
print(json.dumps({'command_timeout':1800,'retire_timeout':1800,'copy_reference_default':600,'cleanup_wait':120,'runtime_and_mutation_timeout':1800,'all_short_go_helper_literals_replaced':True,'import_hook':True}))
# A fresh interpreter must receive the same profile as forked workers.
code='from r2t.go.execution import COMMAND_TIMEOUT; from r2t.go.runtime import run_solution; import inspect; assert COMMAND_TIMEOUT==1800; assert inspect.signature(run_solution).parameters["timeout"].default==1800; print(COMMAND_TIMEOUT)'
import os
child_env=dict(os.environ)
child_env['PYTHONPATH']=os.pathsep.join([str(__import__('pathlib').Path(__file__).parent),str(__import__('pathlib').Path(execution.__file__).parents[2]),child_env.get('PYTHONPATH','')])
assert subprocess.check_output([sys.executable,'-c',code],env=child_env,text=True).strip()=='1800'
node=Timeouts('req2test.layout').visit(ast.parse('value=KitInputs(timeout=600)'))
ast.fix_missing_locations(node);scope={'KitInputs':lambda **kwargs:kwargs};exec(compile(node,'kit','exec'),scope)
assert scope['value']['timeout']==1800
print('fresh child and kit timeout verified')
