#!/usr/bin/env python3
"""verify-cc-bindings.py — AST-Scan: jede _cc_*-Nutzung in dream_engine.py muss
im Funktions-Scope gebunden sein (Modul-Level oder Funktions-Import).

Warum: compute_config-Refactors (02fda91) fuegten _cc_get-Nutzungen in Phasen ein,
ohne den Import zu erweitern — NREM und Synthesis crashten still mit
"NameError: name '_cc_get' is not defined" und liefen als No-Op weiter, waehrend
der Rest des Cycles "normal" weitermachte. Genau die Klasse, die kein Test faengt.

Usage: python3 verify-cc-bindings.py [pfad-zu-dream_engine.py]
Default: /home/alca/projects/mazemaker-pro/python/dream_engine.py
Exit 0 = alles gebunden; Exit 1 = unbound-Nutzungen gefunden.
"""
import ast
import sys

path = sys.argv[1] if len(sys.argv) > 1 else \
    "/home/alca/projects/mazemaker-pro/python/dream_engine.py"
src = open(path).read()
tree = ast.parse(src)

mod_binds = set()
for n in tree.body:
    if isinstance(n, ast.ImportFrom):
        mod_binds |= {a.asname or a.name for a in n.names}

problems = []
for node in ast.walk(tree):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        fn_binds = set(mod_binds)
        for n in ast.walk(node):
            if isinstance(n, ast.ImportFrom):
                fn_binds |= {a.asname or a.name for a in n.names}
        uses = {n.id for n in ast.walk(node)
                if isinstance(n, ast.Name) and n.id.startswith("_cc_")}
        missing = uses - fn_binds
        if missing:
            problems.append(f"{node.name}: unbound {sorted(missing)}")

if problems:
    print("NAMEERROR-KLASSE GEFUNDEN (unbound _cc_-Nutzungen):")
    for p in problems:
        print("  ", p)
    sys.exit(1)
print(f"OK: alle _cc_*-Nutzungen in allen Funktionen von {path} sind gebunden")
