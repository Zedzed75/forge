"""Compare the key-shaped identifiers of a package between two git revisions.

Covers what the acceptance criteria forbid renaming: dict literal keys, the
field names of the spec models, `Literal[...]` members, `choices` members and
the `name=`/`alias=`/`key=` keywords of any call (catalog entries, role and
resource definitions).

    python -I tests/review/keys.py master <branch> src/forge/plugins/<domain>

A review tool, not a CI gate. It is the measurement `skeleton.py` cannot make,
because `skeleton.py` blanks exactly the strings this one reads: a renamed spec
or catalog key is invisible to the skeleton compare and breaks every template
that reads it by name. Both come from the ZED-24 verification session; the
third script of that set, a French scan, has become the CI gate in
`tests/french_guard.py` and is not kept here.
"""
import ast, subprocess, sys

def files(ref, pathspec):
    out = subprocess.run(["git", "ls-tree", "-r", "--name-only", ref, pathspec],
                         capture_output=True, text=True, check=True).stdout.split()
    return sorted(f for f in out if f.endswith(".py"))

def keys(ref, path):
    src = subprocess.run(["git", "show", f"{ref}:{path}"],
                         capture_output=True, check=True).stdout.decode("utf-8")
    found = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Dict):
            for k in node.keys:
                if isinstance(k, ast.Constant) and isinstance(k.value, str):
                    found.add(("dict-key", k.value))
        elif isinstance(node, ast.ClassDef):
            for stmt in node.body:
                if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                    found.add(("field", stmt.target.id))
        elif isinstance(node, ast.Subscript):
            val = node.value
            name = val.attr if isinstance(val, ast.Attribute) else getattr(val, "id", "")
            if name == "Literal":
                sl = node.slice
                members = sl.elts if isinstance(sl, ast.Tuple) else [sl]
                for m in members:
                    if isinstance(m, ast.Constant) and isinstance(m.value, str):
                        found.add(("literal", m.value))
        elif isinstance(node, ast.Call):
            for kw in node.keywords:
                if kw.arg in ("name", "alias", "serialization_alias", "validation_alias", "key") \
                   and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                    found.add((f"{kw.arg}=", kw.value.value))
                if kw.arg == "choices" and isinstance(kw.value, (ast.Tuple, ast.List)):
                    for m in kw.value.elts:
                        if isinstance(m, ast.Constant) and isinstance(m.value, str):
                            found.add(("choice", m.value))
    return found

if __name__ == "__main__":
    base, head, pathspec = sys.argv[1], sys.argv[2], sys.argv[3]
    kb = set(); kh = set()
    for p in files(base, pathspec): kb |= keys(base, p)
    for p in files(head, pathspec): kh |= keys(head, p)
    gone, new = sorted(kb - kh), sorted(kh - kb)
    for kind, v in gone: print(f"  REMOVED {kind:22} {v!r}")
    for kind, v in new:  print(f"  ADDED   {kind:22} {v!r}")
    print(f"  {len(kb)} keys on base, {len(kh)} on head, {len(gone)} removed, {len(new)} added")
