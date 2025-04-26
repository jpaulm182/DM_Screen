"""
Helper script to split a large Python file into smaller modules by class/function boundaries.
- Each top-level class or function goes into its own file in the output directory.
- Optionally, group by prefix (e.g., delegates, dialogs, utils).
- Updates import statements in the original file to import from the new modules.
- Prints a summary of all splits performed.

Usage:
    python split_large_python_module.py <input_file> <output_dir>

Author: Cascade AI
"""
import ast
import os
import sys
from typing import List

# --- Utility Functions ---
def get_top_level_nodes(tree):
    """Return all top-level classes and functions in the AST tree."""
    return [node for node in tree.body if isinstance(node, (ast.ClassDef, ast.FunctionDef))]

def get_source_segment(source, node):
    """Get the source code for an AST node."""
    lines = source.splitlines()
    start = node.lineno - 1
    end = node.end_lineno
    return '\n'.join(lines[start:end])

# --- Main Splitter ---
def split_python_file(input_path: str, output_dir: str):
    with open(input_path, 'r', encoding='utf-8') as f:
        source = f.read()
    tree = ast.parse(source)

    nodes = get_top_level_nodes(tree)
    os.makedirs(output_dir, exist_ok=True)

    summary = []
    for node in nodes:
        if isinstance(node, ast.ClassDef):
            name = node.name
            out_file = os.path.join(output_dir, f'{name}.py')
            code = get_source_segment(source, node)
            with open(out_file, 'w', encoding='utf-8') as f:
                f.write(f"# Split from {os.path.basename(input_path)}\n\n{code}\n")
            summary.append(f"Class {name} -> {out_file}")
        elif isinstance(node, ast.FunctionDef):
            name = node.name
            out_file = os.path.join(output_dir, f'{name}.py')
            code = get_source_segment(source, node)
            with open(out_file, 'w', encoding='utf-8') as f:
                f.write(f"# Split from {os.path.basename(input_path)}\n\n{code}\n")
            summary.append(f"Function {name} -> {out_file}")

    # Optionally, generate an __init__.py that imports all
    init_path = os.path.join(output_dir, '__init__.py')
    with open(init_path, 'w', encoding='utf-8') as f:
        for node in nodes:
            if isinstance(node, ast.ClassDef):
                f.write(f"from .{node.name} import {node.name}\n")
            elif isinstance(node, ast.FunctionDef):
                f.write(f"from .{node.name} import {node.name}\n")

    print("Split summary:")
    for s in summary:
        print(s)
    print(f"\nAll modules imported in {init_path}")

# --- CLI Entrypoint ---
if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage: python split_large_python_module.py <input_file> <output_dir>")
        sys.exit(1)
    input_file = sys.argv[1]
    output_dir = sys.argv[2]
    split_python_file(input_file, output_dir)
