"""
split_combat_tracker_panel.py

This script helps split large Python files (like CombatTrackerPanel.py) into smaller, focused helper modules.
It will:
- Parse the main file for all top-level functions and classes.
- For each function (or group by prefix), move the code into a helper file (e.g., combattrackerpanel_<name>_helpers.py).
- Replace the code in the main file with an import and delegation if needed.
- Add comments for clarity.

Usage: python split_combat_tracker_panel.py
"""
import os
import ast
import shutil
from collections import defaultdict

HELPERS_DIR = os.path.join("app", "ui", "panels")
MAIN_FILE = os.path.join("app", "ui", "panels", "combat_tracker_split", "CombatTrackerPanel.py")
BACKUP_FILE = MAIN_FILE + ".bak"
HELPER_PREFIX = "combattrackerpanel_"
HELPER_SUFFIX = "_helpers.py"

# --- UTILS ---
def get_source(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()

def write_source(filepath, code):
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(code)

def extract_defs(tree):
    """Return a list of (name, type, start, end) for top-level defs."""
    defs = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            name = node.name
            typ = "class" if isinstance(node, ast.ClassDef) else "function"
            start = node.lineno - 1
            end = getattr(node, "end_lineno", node.lineno)  # end_lineno is Python 3.8+
            defs.append((name, typ, start, end))
    return defs

def group_by_prefix(defs):
    """Group function names by prefix before first underscore (e.g., _add_status -> add).
    Returns dict: prefix -> list of (name, type, start, end)
    """
    groups = defaultdict(list)
    for name, typ, start, end in defs:
        if name.startswith("_"):
            parts = name[1:].split("_", 1)
            prefix = parts[0] if len(parts) > 1 else name[1:]
        else:
            prefix = name.split("_", 1)[0]
        groups[prefix].append((name, typ, start, end))
    return groups

def make_helper_filename(prefix):
    return HELPER_PREFIX + prefix + HELPER_SUFFIX

# --- MAIN SPLIT FUNCTION ---
def main():
    print(f"Backing up {MAIN_FILE} to {BACKUP_FILE}")
    shutil.copy2(MAIN_FILE, BACKUP_FILE)
    source = get_source(MAIN_FILE)
    tree = ast.parse(source)
    defs = extract_defs(tree)
    groups = group_by_prefix(defs)
    lines = source.splitlines(keepends=True)

    # For each group, move to helper
    for prefix, items in groups.items():
        helper_file = os.path.join(HELPERS_DIR, make_helper_filename(prefix))
        helper_code = []
        for name, typ, start, end in items:
            # Extract code block
            block = lines[start:end]
            # Add header if new file
            if not os.path.exists(helper_file):
                helper_code.append(f"# Helpers for CombatTrackerPanel ({prefix})\n\n")
            helper_code.extend(block)
            helper_code.append("\n\n")
            # Remove from main file
            for i in range(start, end):
                lines[i] = None  # Mark for removal
        # Write or append to helper
        with open(helper_file, "a", encoding="utf-8") as f:
            f.writelines(helper_code)
        print(f"Moved {len(items)} defs to {helper_file}")

    # Remove marked lines from main file
    new_lines = [line for line in lines if line is not None]
    # Add import comments for helpers
    import_lines = [f"# See helpers: {make_helper_filename(prefix)}\n" for prefix in groups]
    new_lines = new_lines[:1] + import_lines + new_lines[1:]
    write_source(MAIN_FILE, "".join(new_lines))
    print(f"Refactor complete. Main file reduced, helpers created.")

if __name__ == "__main__":
    main()
