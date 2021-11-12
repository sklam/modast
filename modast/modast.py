"""
This file can be executed as __main__ with one cmdline argument for the file
to be modified.
"""
import sys
import ast
import os
import importlib
import importlib.abc
import importlib.util


def _fix_line(tree, old):
    """Fixes lineno for a one-liner
    """
    return ast.increment_lineno(tree, old.lineno - 1)


def _recurse_visit_children(transformer, node):
    for child in ast.iter_child_nodes(node):
        transformer.visit(child)
    return node


class FunctionNamePrinter(ast.NodeTransformer):
    _src_print = "print('=== Inside function {!r}'.format('<stub>'))"

    class ReplaceConstant(ast.NodeTransformer):
        def __init__(self, new_value):
            self.new_value = new_value

        def visit_Constant(self, node: ast.Constant):
            if node.value == "<stub>":
                node.value = self.new_value
            return node

    def visit_FunctionDef(self, node: ast.FunctionDef):
        tree = self.ReplaceConstant(node.name).visit(
            ast.parse(self._src_print)
        )

        expr = tree.body[0]
        assert isinstance(expr, ast.Expr)
        if node.body:
            expr = _fix_line(expr, node.body[-1])
        node.body.insert(0, expr)

        return _recurse_visit_children(self, node)


def has_docstring(body):
    has_docstring = False
    if body:
        firststmt = body[0]
        if isinstance(firststmt, ast.Expr):
            if isinstance(firststmt.value, ast.Constant):
                cval = firststmt.value
                if isinstance(cval.value, str):
                    has_docstring = True
    return has_docstring


def fix_line_in_body(new_stmts, old_body):
    new_body = []
    for stmt in new_stmts:
        if old_body:
            stmt = _fix_line(stmt, old_body[0])
        new_body.append(stmt)
    return new_body


class TypeRetChecker(ast.NodeTransformer):
    _src_ret_check = """__typecheck_return__({value}, {expected_type})"""

    def __init__(self, expected_type):
        self.depth = 0
        self.expected_type = expected_type

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self.depth += 1
        return node

    def visit_Return(self, node: ast.Return):
        if self.depth != 0:
            return node
        self.depth -= 1

        tree = self.generate_check(node.value)
        _fix_line(tree, node)
        node.value = tree.value
        return node

    def generate_check(self, rhs):
        if rhs is not None:
            rhs = ast.unparse(rhs)
        return ast.parse(
            self._src_ret_check.format(
                expected_type=self.expected_type, value=rhs,
            )
        ).body[0]


def has_yield(node):
    class SearchYield(ast.NodeVisitor):
        found = False

        def visit_Yield(self, node: ast.Yield):
            self.found = True

    search = SearchYield()
    search.visit(node)
    return search.found


class TypeChecker(ast.NodeTransformer):
    _src_import = """
from modast.runtime.typecheck import typecheck_return as __typecheck_return__, typecheck_arg as __typecheck_arg__, typecheck_assign as __typecheck_assign__   # noqa
"""
    _src_arg_check = "__typecheck_arg__({name!r}, {value}, {expected_type}) # CHECKING {name})"  # noqa
    _src_assign_check = "__typecheck_assign__({name!r}, {value}, {expected_type}) # CHECKING {name})"  # noqa

    def __init__(self, filename):
        super().__init__()
        self.filename = filename

    def visit_Module(self, node: ast.Module):
        if not node.body:
            return node

        last_import = None
        for stmt in node.body:
            if isinstance(stmt, (ast.Import, ast.ImportFrom)):
                last_import = stmt
            elif last_import is not None:
                break
        if last_import is None:
            where = max(node.body.index(stmt) - 1, 1)
        else:
            where = node.body.index(stmt)
        new_body = ast.parse(self._src_import).body
        node.body = node.body[:where] + new_body + node.body[where:]
        return _recurse_visit_children(self, node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        _recurse_visit_children(self, node)

        if not has_yield(node):
            if node.returns is not None:
                expected_type = (
                    ast.unparse(node.returns)
                    if node.returns is not None
                    else "None"
                )
                node.body = [
                    TypeRetChecker(expected_type).visit(stmt)
                    for stmt in node.body
                ]
                # check last statement to be a Return
                if not isinstance(node.body[-1], ast.Return):
                    # insert check
                    node.body.append(
                        TypeRetChecker(expected_type).generate_check(None)
                    )
                print(
                    f"Line {node.lineno}: "
                    f"inserted return guard to {node.name!r}"
                )

        if any(arg.annotation is not None for arg in node.args.args):
            # Insert argument check to the start of the function
            new_body = []
            for arg in node.args.args:
                arg: ast.arg
                if arg.annotation is not None:
                    argcheck_tree = ast.parse(
                        self._src_arg_check.format(
                            name=arg.arg,
                            value=arg.arg,
                            expected_type=ast.unparse(arg.annotation),
                        )
                    )
                    new_body.extend(
                        fix_line_in_body(argcheck_tree.body, node.body)
                    )
            # find insertion point
            insertpt = 1 if has_docstring(node.body) else 0
            # splice
            node.body = node.body[:insertpt] + new_body + node.body[insertpt:]
            print(
                f"Line {node.lineno}: " f"inserted arg guard to {node.name!r}"
            )
            print("-" * 80)
            print(ast.unparse(node))
            print("-" * 80)

        return node

    def visit_AnnAssign(self, node: ast.AnnAssign):
        _recurse_visit_children(self, node)

        if node.value is not None:
            tree = ast.parse(
                self._src_assign_check.format(
                    name=ast.unparse(node.target),
                    value=ast.unparse(node.value),
                    expected_type=ast.unparse(node.annotation),
                ),
            )
            node.value = _fix_line(tree.body[0].value, node)
        return node


def parse_ast_from_path(filepath):
    with open(filepath) as fin:
        src = fin.read()
    tree = ast.parse(
        src, filename=os.path.basename(filepath), type_comments=True
    )
    return tree


def ast_to_bytecode(tree, filepath):
    Loader = importlib.abc.InspectLoader
    code = Loader.source_to_code(tree, filepath)
    return code


def write_pyc(code):
    filepath = code.co_filename
    # Shamelessly borrowed code from https://github.com/python/cpython/blob/b71bc052454803aa8bd3e7edd2044e2d5e962243/Lib/py_compile.py#L79  # noqa
    loader = importlib.machinery.SourceFileLoader("<py_compile>", filepath)
    source_stats = loader.path_stats(filepath)
    cfile = importlib.util.cache_from_source(filepath)

    try:
        dirname = os.path.dirname(cfile)
        if dirname:
            os.makedirs(dirname)
    except FileExistsError:
        pass

    bytecode = importlib._bootstrap_external._code_to_timestamp_pyc(
        code, source_stats["mtime"], source_stats["size"]
    )
    mode = importlib._bootstrap_external._calc_mode(filepath)
    importlib._bootstrap_external._write_atomic(cfile, bytecode, mode)
    # print(cfile)


def transform(tree, filename):
    tree = TypeChecker(filename).visit(tree)
    return tree


def run(filepath):
    tree = parse_ast_from_path(filepath)
    tree = transform(tree, filepath)
    # print('-' * 80)
    # unparsed = ast.unparse(tree)
    # for i, ln in enumerate(unparsed.splitlines(), 1):
    #     print(f"{i:8} | {ln}")
    # with open("temp.py", "w") as fout:
    #     print(unparsed, file=fout)
    code = ast_to_bytecode(tree, filepath)
    write_pyc(code)


def main():
    [filepath] = sys.argv[1:]
    run(filepath)


if __name__ == "__main__":
    main()
