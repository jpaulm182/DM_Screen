#!/usr/bin/env python3
"""Append a Markdown list of every class & public method (w/ arg names)
from each given Python file to public_api.md."""
import ast, sys
from pathlib import Path

md = Path("public_api.md")

for file in map(Path, sys.argv[1:]):
    text = file.read_text()
    try:
        tree = ast.parse(text)
    except SyntaxError as e:
        print(f"Skipping {file.name} due to syntax error: {e}", file=sys.stderr)
        continue
    out = [f"## {file.name}\n"]
    for cls in [n for n in tree.body if isinstance(n, ast.ClassDef)]:
        out.append(f"### class {cls.name}\n")
        for func in [n for n in cls.body if isinstance(n, ast.FunctionDef)]:
            if func.name.startswith("_"):
                continue
            args = ", ".join(a.arg for a in func.args.args)
            out.append(f"* **{func.name}({args})**")
    content = md.read_text() if md.exists() else ""
    md.write_text(content + "\n".join(out) + "\n")
