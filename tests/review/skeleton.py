"""Compare the control-flow skeleton of a package between two git revisions.

Blanks every string constant and every identifier, so a translation or a rename
of a private name is invisible, while any change to a condition, a `raise`, or
the shape of the code shows up. An f-string with no placeholder is collapsed to
a plain constant, since `f"literal"` and `"literal"` are the same `str`.
Also compares the set of raised exception types per file.

    python -I tests/review/skeleton.py master <branch> src/forge/plugins/<domain>

A review tool, not a CI gate: it needs two revisions and someone to read the
result. Written while verifying the five ZED-24 translation PRs, where it
compared 85 files across the five domains and reported zero differences — the
claim a `tests/golden/` diff cannot make, since that says nothing about a
condition quietly inverted while its message was being rewritten.
"""
import ast, subprocess, sys

def files(ref, pathspec):
    out = subprocess.run(["git", "ls-tree", "-r", "--name-only", ref, pathspec],
                         capture_output=True, text=True, check=True).stdout.split()
    return sorted(f for f in out if f.endswith(".py"))

def read(ref, path):
    return subprocess.run(["git", "show", f"{ref}:{path}"],
                          capture_output=True, check=True).stdout.decode("utf-8")

class Blank(ast.NodeTransformer):
    def visit_JoinedStr(self, node):
        self.generic_visit(node)
        if all(isinstance(v, ast.Constant) for v in node.values):
            return ast.copy_location(ast.Constant(value="S"), node)
        return node
    def visit_Constant(self, node):
        if isinstance(node.value, str):
            return ast.copy_location(ast.Constant(value="S"), node)
        return node
    def visit_Name(self, node):
        node.id = "N"; return self.generic_visit(node)
    def visit_Attribute(self, node):
        node.attr = "A"; return self.generic_visit(node)
    def visit_arg(self, node):
        node.arg = "a"; return self.generic_visit(node)
    def visit_keyword(self, node):
        node.arg = "k"; return self.generic_visit(node)
    def visit_FunctionDef(self, node):
        node.name = "f"; return self.generic_visit(node)
    def visit_AsyncFunctionDef(self, node):
        node.name = "f"; return self.generic_visit(node)
    def visit_ClassDef(self, node):
        node.name = "C"; return self.generic_visit(node)
    def visit_alias(self, node):
        node.name = "m"; node.asname = None; return node
    def visit_ImportFrom(self, node):
        node.module = "m"; return self.generic_visit(node)

def skel(ref, path):
    tree = ast.parse(read(ref, path))
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if isinstance(body, list) and body and isinstance(body[0], ast.Expr) \
           and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
            body.pop(0)
    return ast.dump(Blank().visit(tree))

def raised(ref, path):
    names = []
    for node in ast.walk(ast.parse(read(ref, path))):
        if isinstance(node, ast.Raise) and node.exc is not None:
            exc = node.exc.func if isinstance(node.exc, ast.Call) else node.exc
            names.append(ast.unparse(exc))
    return sorted(names)

if __name__ == "__main__":
    base, head, pathspec = sys.argv[1], sys.argv[2], sys.argv[3]
    fb, fh = files(base, pathspec), files(head, pathspec)
    bad = 0
    if fb != fh:
        print("  file set differs:", set(fb) ^ set(fh)); bad += 1
    for p in sorted(set(fb) & set(fh)):
        if skel(base, p) != skel(head, p):
            print(f"  SKELETON CHANGED: {p}"); bad += 1
        rb, rh = raised(base, p), raised(head, p)
        if rb != rh:
            print(f"  RAISED TYPES CHANGED: {p}: {rb} -> {rh}"); bad += 1
    print(f"  {len(fb)} files compared, {bad} difference(s)")
