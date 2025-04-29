AI‑Only Refactor Playbook

Purpose: This single Markdown file tells an AI code‑assistant how to slice a 5 000‑line monolithic Python class into several ≤1 500‑line modules without any further human help.  Copy this file into the repository root (e.g. REFactor_instructions.md).

Everything the AI needs—algorithm, step order, and helper scripts—is embedded below.

0  Prerequisites (assumed by the AI)

Python ≥3.9 available in the workspace.

Project is version‑controlled (Git).

A reliable test suite (pytest -q exits ≡0 on success).

The monolithic file is named big_file.py at repo root.

1  Job Overview

Protect Baseline: run tests → commit.

Chunk & Summarise: generate overlapping slices, then AST‑summarise each slice to build public_api.md.

Plan Split: decide which method belongs to which topic module (create module_map.yml).

Autogenerate Skeletons & Facade.

Extract Methods Autonomously: move code into the new modules while inserting delegates into the legacy file.

Green‑bar after every step → commit.

Every stage is scripted below.

2  Command Sequence for the AI

# Step 1 – Snapshot
pytest -q
git add -A && git commit -m "baseline before refactor"

# Step 2 – Chunk file into AI‑digestible windows
python tools/chunker.py big_file.py --max-lines 1200 --overlap 150

# Step 3 – Build API description
python tools/api_map.py big_file.chunk*.py

# Step 4 – Define module_map.yml (see template in §3.3 below)
#       (AI: infer best grouping from api_map output)

# Step 5 – Generate facade class & blank module files
python tools/generate_facade.py

# Step 6 – Autonomous extraction of code bodies
python tools/extract_methods.py big_file.py module_map.yml package/

# Step 7 – Run tests and commit
pytest -q && git add -A && git commit -m "moved <batch> methods"

If the test suite fails the AI must inspect git diff, roll back (git reset --hard HEAD~1) and re‑chunk the failed section.

3  Helper Scripts (place in tools/)

All scripts are stand‑alone and under 150 lines each.

3.1  chunker.py

#!/usr/bin/env python3
"""Split a long source file into overlapping <max_lines>‑line chunks.
Creates <src>.chunk<N>.py files beside the original.
Usage:   python chunker.py big_file.py --max-lines 1200 --overlap 150
"""
from pathlib import Path
import argparse

def chunk(path: Path, max_lines: int, overlap: int):
    lines = path.read_text().splitlines()
    start = idx = 0
    while start < len(lines):
        end = min(start + max_lines, len(lines))
        Path(f"{path.stem}.chunk{idx}{path.suffix}").write_text("\n".join(lines[start:end]))
        if end == len(lines):
            break
        start, idx = end - overlap, idx + 1

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("file", type=Path)
    ap.add_argument("--max-lines", type=int, default=1200)
    ap.add_argument("--overlap", type=int, default=150)
    args = ap.parse_args()
    chunk(args.file, args.max_lines, args.overlap)

3.2  api_map.py

#!/usr/bin/env python3
"""Append a Markdown list of every class & public method (w/ arg names)
from each given Python file to public_api.md."""
import ast, sys
from pathlib import Path

md = Path("public_api.md")
for file in map(Path, sys.argv[1:]):
    tree = ast.parse(file.read_text())
    out = [f"## {file.name}\n"]
    for cls in [n for n in tree.body if isinstance(n, ast.ClassDef)]:
        out.append(f"### class {cls.name}\n")
        for func in [n for n in cls.body if isinstance(n, ast.FunctionDef)]:
            if func.name.startswith("_"):  # skip private helpers
                continue
            args = ", ".join(a.arg for a in func.args.args)
            out.append(f"* **{func.name}({args})**")
    md.write_text(md.read_text() + "\n".join(out) + "\n" if md.exists() else "\n".join(out))

3.3  Template module_map.yml

# key = method name, value = destination module (without .py)
load_data: io_layer
save_data: io_layer
validate_record: validation
serialise: serialization
parse: serialization
# …extend until every public API method is mapped

The AI must fill this file using the semantic grouping it infers from public_api.md.

3.4  generate_facade.py

#!/usr/bin/env python3
"""Create package/facade.py which re‑exports the original API, delegating
calls to implementations that will live in separate modules."""
from pathlib import Path
import yaml, re, textwrap

api = Path("public_api.md").read_text()
map_ = yaml.safe_load(Path("module_map.yml").read_text())
facade = Path("package/facade.py")

methods = re.findall(r"\* \*([A-Za-z_][A-Za-z0-9_]*)\(", api)
lines = ["class MonolithFacade:", "    \"\"\"Auto‑generated façade class.\"\"\""]
for m in methods:
    mod = map_.get(m)
    if not mod:
        continue  # unmapped private or removed
    lines.append(textwrap.dedent(f"""
        def {m}(self, *a, **kw):
            from .{mod} import {m} as _impl
            return _impl(*a, **kw)
    """))
facade.write_text("\n".join(lines) + "\n")
print("wrote", facade)

3.5  extract_methods.py

#!/usr/bin/env python3
"""Move method bodies from the monolithic class into destination modules.
Keeps identical signatures. Leaves a two‑line delegate stub behind."""
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
            # grab source slice
            start, end = func.lineno - 1, func.end_lineno
            body = "\n".join(source_lines[start:end])
            module_buffers.setdefault(dest, []).append(body)
            # create delegate lines
            delegate = textwrap.dedent(f"""
                from .{dest} import {name}
            """)
            replacements.append((start, end, delegate.strip().splitlines()))

MethodGrabber().visit(ast.parse(src_path.read_text()))

# apply replacements backwards to preserve indices
for start, end, rep in sorted(replacements, reverse=True):
    source_lines[start:end] = rep
src_path.write_text("\n".join(source_lines) + "\n")

pkg_dir.mkdir(exist_ok=True)
for mod, bodies in module_buffers.items():
    file = pkg_dir / f"{mod}.py"
    file.write_text("\n\n".join(bodies) + "\n")
print("moved", sum(len(b) for b in module_buffers.values()), "methods →", pkg_dir)

All scripts run in <1500 lines and under the AI's context window.

4  Success Criteria

Green tests after each extraction batch.

Each new module <1 500 lines.

big_file.py shrinks until it merely imports delegates or is replaced entirely by facade.py.

Public API remains identical (signatures & semantics).

End of AI Instruction File

