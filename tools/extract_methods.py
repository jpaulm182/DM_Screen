#!/usr/bin/env python3
"""Move method bodies from the monolithic class into destination modules.
Keeps identical signatures. Leaves a two-line delegate stub behind."""
import ast, inspect, textwrap, sys, yaml
from pathlib import Path

src_path, map_path, pkg_dir = map(Path, sys.argv[1:4])
module_map = yaml.safe_load(map_path.read_text())

source_lines = src_path.read_text().splitlines()
module_buffers = {}
replacements = []  # (start, end, newlines)

class MethodGrabber(ast.NodeVisitor):
    def visit_ClassDef(self, node):
        for func in [n for n in node.body if isinstance(n, ast.FunctionDef)]:
            name = func.name
            dest = module_map.get(name)
            if not dest:
                continue
            # grab source slice
            start, end = func.lineno - 1, func.end_lineno
            body = "\n".join(source_lines[start:end])
            module_buffers.setdefault(dest, []).append(body)
            # create delegate lines
            delegate = textwrap.dedent(f"""
                from .{dest} import {name}
            """)
            replacements.append((start, end, delegate.strip().splitlines()))

# Parse the monolithic source and collect methods
a = ast.parse(src_path.read_text())
MethodGrabber().visit(a)

# apply replacements backwards to preserve indices
for start, end, rep in sorted(replacements, reverse=True):
    source_lines[start:end] = rep
# Write modified monolithic file
src_path.write_text("\n".join(source_lines) + "\n")

# Ensure destination package directory exists
pkg_dir.mkdir(exist_ok=True)
# Write extracted methods into separate modules
for mod, bodies in module_buffers.items():
    file = pkg_dir / f"{mod}.py"
    file.write_text("\n\n".join(bodies) + "\n")
print("moved", sum(len(b) for b in module_buffers.values()), "methods →", pkg_dir)
