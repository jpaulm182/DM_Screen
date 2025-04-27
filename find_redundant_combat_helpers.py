"""
find_redundant_combat_helpers.py

This script scans all combattrackerpanel_*_helpers.py files and CombatTrackerPanel.py for redundant function/class definitions.
It reports any functions/classes defined in both a helper file and the main file, including their line numbers for easy manual cleanup.

Usage: python find_redundant_combat_helpers.py
"""
import os
import ast
from collections import defaultdict

# --- CONFIG ---
HELPERS_DIR = os.path.join("app", "ui", "panels")
HELPERS_GLOB = "combattrackerpanel_"  # prefix
MAIN_FILE = os.path.join("app", "ui", "panels", "combat_tracker_split", "CombatTrackerPanel.py")

# --- UTILS ---
def get_py_files(directory, prefix):
    return [
        os.path.join(directory, f)
        for f in os.listdir(directory)
        if f.startswith(prefix) and f.endswith(".py")
    ]

def get_definitions(filepath):
    """Returns dict: name -> (type, lineno, end_lineno) for top-level defs."""
    with open(filepath, "r", encoding="utf-8") as f:
        source = f.read()
    tree = ast.parse(source, filename=filepath)
    defs = {}
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef):
            defs[node.name] = ("function", node.lineno, getattr(node, "end_lineno", node.lineno))
        elif isinstance(node, ast.ClassDef):
            defs[node.name] = ("class", node.lineno, getattr(node, "end_lineno", node.lineno))
    return defs

# --- MAIN ANALYSIS ---
def main():
    helpers_path = os.path.abspath(HELPERS_DIR)
    main_path = os.path.abspath(MAIN_FILE)
    helper_files = get_py_files(helpers_path, HELPERS_GLOB)
    print(f"Found {len(helper_files)} helper files.")

    # Get all definitions in main file
    main_defs = get_definitions(main_path)

    # For each helper, get defs and compare
    redundant = []
    for helper in helper_files:
        helper_defs = get_definitions(helper)
        for name, (typ, h_start, h_end) in helper_defs.items():
            if name in main_defs:
                typ2, m_start, m_end = main_defs[name]
                redundant.append({
                    "name": name,
                    "type": typ,
                    "helper_file": helper,
                    "main_file": main_path,
                    "helper_lines": (h_start, h_end),
                    "main_lines": (m_start, m_end),
                })

    # Print report
    if not redundant:
        print("No redundant functions/classes found.")
    else:
        print("Redundant functions/classes found:")
        for entry in redundant:
            print(f"- {entry['type']} '{entry['name']}':")
            print(f"    Helper: {os.path.relpath(entry['helper_file'])} lines {entry['helper_lines'][0]}-{entry['helper_lines'][1]}")
            print(f"    Main:   {os.path.relpath(entry['main_file'])} lines {entry['main_lines'][0]}-{entry['main_lines'][1]}")
        print("\nYou can now safely remove these from the main file if the helper is used.")

if __name__ == "__main__":
    main()
