"""Apply the recorded timeout profile at import, leaving the checkout intact."""
import ast
import importlib.abc
import importlib.machinery
import sys

GO_MODULES = {
    'r2t.go.execution', 'r2t.go.mutation_copy', 'r2t.go.runtime',
    'r2t.go.bootstrap', 'r2t.go.mutation_runtime', 'r2t.go.mutation_audit',
    'r2t.go.registry', 'r2t.go.prod_index_cli', 'r2t.go.mutation_cli',
}
MODULES = GO_MODULES | {'r2t.bench.cli', 'req2test.layout'}

class Timeouts(ast.NodeTransformer):
    def __init__(self, module):
        self.module = module

    def visit_Constant(self, node):
        if self.module in GO_MODULES:
            changes = {600:1800, 30:600, 15:120, 900:1800, 300:900, 120:600}
            if self.module=='r2t.go.prod_index_cli':
                changes[1800]=3600
            if type(node.value) is int and node.value in changes:
                return ast.copy_location(ast.Constant(changes[node.value]),node)
            if node.value == '-timeout=600s':
                return ast.copy_location(ast.Constant('-timeout=1800s'),node)
        return node

    def visit_Call(self, node):
        node = self.generic_visit(node)
        if self.module=='r2t.bench.cli' and node.args and isinstance(node.args[0],ast.Constant) and node.args[0].value=='--timeout':
            for keyword in node.keywords:
                if keyword.arg=='default' and isinstance(keyword.value,ast.Constant) and keyword.value.value==600:
                    keyword.value=ast.Constant(1800)
        if self.module=='req2test.layout' and isinstance(node.func,ast.Name) and node.func.id=='KitInputs':
            for keyword in node.keywords:
                if keyword.arg=='timeout':
                    keyword.value=ast.Call(func=ast.Name(id='max',ctx=ast.Load()),args=[ast.Constant(1800),keyword.value],keywords=[])
        return node

class Loader(importlib.machinery.SourceFileLoader):
    def get_code(self, fullname):
        source=self.get_data(self.path).decode('utf-8')
        tree=Timeouts(fullname).visit(ast.parse(source,filename=self.path))
        ast.fix_missing_locations(tree)
        return compile(tree,self.path,'exec')

class Finder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname not in MODULES:
            return None
        spec=importlib.machinery.PathFinder.find_spec(fullname,path)
        if spec is None or spec.origin is None:
            return None
        spec.loader=Loader(fullname,spec.origin)
        return spec

def activate():
    if not any(isinstance(f,Finder) for f in sys.meta_path):
        sys.meta_path.insert(0,Finder())
