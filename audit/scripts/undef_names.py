"""Names a script reads that nothing binds: a constant left in a patch (NHD_MIN_KM2) compiles but stops the step.
   undef_names.py <scripts dir> [file.py ...]   (default: every .py in the dir)
Also a top-level function or class defined twice in one file: the later def silently replaces the
earlier one for every call after it (2026-11-23, a patch's named_along shadowed 05_score's own).
Crude on purpose: a name counts as bound if the file binds it anywhere (any scope), a local module it star-imports or
from-imports binds it at module level, or it is a builtin. Prints file:line name for the rest."""
import ast, builtins, os, sys

d = sys.argv[1]
files = sys.argv[2:] or sorted(f for f in os.listdir(d) if f.endswith('.py'))
_mod_cache = {}

def module_names(mod):
    """Module-level names of a local module (scripts/<mod>.py), following its own star imports."""
    if mod in _mod_cache:
        return _mod_cache[mod]
    _mod_cache[mod] = set()
    p = os.path.join(d, mod + '.py')
    if not os.path.exists(p):
        return None
    tree = ast.parse(open(p).read())
    names = bound(tree, top_only=True)
    _mod_cache[mod] = names
    return names

def bound(tree, top_only=False):
    names = set()
    nodes = tree.body if top_only else list(ast.walk(tree))
    if top_only:   # module level, including inside top-level if/try/with blocks
        stack, nodes = list(tree.body), []
        while stack:
            n = stack.pop()
            nodes.append(n)
            if isinstance(n, (ast.If, ast.Try, ast.With, ast.For, ast.While)):
                for f in ('body', 'orelse', 'finalbody', 'handlers'):
                    stack.extend(getattr(n, f, []) or [])
            if isinstance(n, ast.ExceptHandler):
                stack.extend(n.body)
            for t in ast.walk(n) if isinstance(n, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.For, ast.With)) else []:
                if isinstance(t, ast.Name) and isinstance(t.ctx, ast.Store):
                    names.add(t.id)
    for n in nodes:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(n.name)
            if not top_only:
                a = n.args if hasattr(n, 'args') else None
                if a:
                    for x in a.posonlyargs + a.args + a.kwonlyargs + [a.vararg, a.kwarg]:
                        if x is not None:
                            names.add(x.arg)
        elif isinstance(n, ast.Lambda):
            a = n.args
            for x in a.posonlyargs + a.args + a.kwonlyargs + [a.vararg, a.kwarg]:
                if x is not None:
                    names.add(x.arg)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            for al in n.names:
                if al.name == '*':
                    sub = module_names(n.module) if isinstance(n, ast.ImportFrom) and n.module else None
                    if sub is None:
                        names.add('*')       # unknown star import: can't judge this file
                    else:
                        names |= sub
                else:
                    names.add((al.asname or al.name).split('.')[0])
        elif isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
            names.add(n.id)
        elif isinstance(n, ast.ExceptHandler) and n.name:
            names.add(n.name)
        elif isinstance(n, (ast.Global, ast.Nonlocal)):
            names.update(n.names)
        elif isinstance(n, ast.arg):
            names.add(n.arg)
        elif hasattr(ast, 'MatchAs') and isinstance(n, (ast.MatchAs, ast.MatchStar)) and n.name:
            names.add(n.name)
        elif isinstance(n, ast.NamedExpr):
            names.add(n.target.id)
    return names

bad = 0
known = set(dir(builtins)) | {'__file__', '__name__', '__doc__', '__builtins__', '__spec__', '__loader__'}
for f in files:
    p = f if os.path.sep in f else os.path.join(d, f)
    try:
        tree = ast.parse(open(p).read(), p)
    except SyntaxError as e:
        print(f'{f}: does not parse: {e}'); bad += 1; continue
    names = bound(tree) | known
    if '*' in names:
        print(f'{f}: star import of a non-local module; skipped'); continue
    first = {}
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if n.name in first:
                print(f'{os.path.basename(p)}:{n.lineno} {n.name} defined again (first at line {first[n.name]})'); bad += 1
            else:
                first[n.name] = n.lineno
    seen = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and n.id not in names and n.id not in seen:
            seen.add(n.id)
            print(f'{os.path.basename(p)}:{n.lineno} {n.id}'); bad += 1
print(f'{bad} unbound or twice-defined name(s) in {len(files)} file(s)')
sys.exit(1 if bad else 0)
