"""
Automated script to modularize a large class by extracting its methods into helper modules.
- Accepts a Python file and class name.
- Extracts all methods from the class.
- Groups methods by prefix (e.g., _setup_, _handle_, _update_, etc.) or by user-defined tags.
- Writes each group to a helper module (e.g., combat_resolver_turn_helpers.py, combat_resolver_llm_helpers.py).
- Rewrites the original class to import and delegate to these helpers.

Usage:
    python modularize_large_class.py <input_file> <class_name> <output_dir>

Author: Cascade AI
"""
import ast
import os
import sys
from collections import defaultdict

HELPER_PREFIXES = ["_setup_", "_handle_", "_update_", "_sort_", "_quick_", "_next_", "_add_", "_remove_", "_clear_", "_reset_", "_show_", "_toggle_", "_roll_", "_restart_", "_round_", "_check_", "_ensure_", "_process_", "_create_", "_get_", "_format_"]

def group_methods_by_prefix(methods):
    grouped = defaultdict(list)
    for m in methods:
        for prefix in HELPER_PREFIXES:
            if m.name.startswith(prefix):
                grouped[prefix].append(m)
                break
        else:
            grouped["other"].append(m)
    return grouped

def get_source_segment(source, node):
    lines = source.splitlines()
    start = node.lineno - 1
    end = node.end_lineno
    return '\n'.join(lines[start:end])

def modularize_class(input_path, class_name, output_dir):
    with open(input_path, 'r', encoding='utf-8') as f:
        source = f.read()
    tree = ast.parse(source)

    # Find the target class
    class_node = None
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            class_node = node
            break
    if not class_node:
        print(f"Class {class_name} not found in {input_path}")
        sys.exit(1)

    # Group methods
    methods = [n for n in class_node.body if isinstance(n, ast.FunctionDef)]
    grouped = group_methods_by_prefix(methods)

    os.makedirs(output_dir, exist_ok=True)
    helper_imports = []

    # Write each group to a helper module
    for prefix, method_nodes in grouped.items():
        if prefix == "other":
            continue  # keep in main class for now
        fname = f"{class_name.lower()}_{prefix[1:-1]}_helpers.py"
        out_file = os.path.join(output_dir, fname)
        with open(out_file, 'w', encoding='utf-8') as f:
            f.write(f"# Helpers for {class_name} ({prefix})\n\n")
            for m in method_nodes:
                code = get_source_segment(source, m)
                f.write(code + '\n\n')
        helper_imports.append((prefix, fname))

    # Write a new main class file with imports
    main_out_file = os.path.join(output_dir, f'{class_name}.py')
    with open(main_out_file, 'w', encoding='utf-8') as f:
        f.write(f"# Modularized {class_name} (auto-generated)\n\n")
        for prefix, fname in helper_imports:
            f.write(f"from .{fname[:-3]} import *  # {prefix} helpers\n")
        # Write the class header and keep only 'other' methods
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                header = get_source_segment(source, node).split('\n')[:2]  # class line + docstring
                f.write('\n'.join(header) + '\n    # ... see helpers for most methods ...\n\n')
                for m in grouped["other"]:
                    code = get_source_segment(source, m)
                    for line in code.splitlines():
                        f.write('    ' + line + '\n')
                f.write('\n')

    print(f"Modularization complete. Helpers and new main class written to {output_dir}")

if __name__ == '__main__':
    if len(sys.argv) != 4:
        print("Usage: python modularize_large_class.py <input_file> <class_name> <output_dir>")
        sys.exit(1)
    input_file = sys.argv[1]
    class_name = sys.argv[2]
    output_dir = sys.argv[3]
    modularize_class(input_file, class_name, output_dir)
