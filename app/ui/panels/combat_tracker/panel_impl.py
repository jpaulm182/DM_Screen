import os
import types
import re  # Needed for fixing import paths

# Dynamically assemble CombatTrackerPanel from chunk files
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../"))
chunk_files = [
    os.path.join(root_dir, f"combat_tracker_panel.chunk{i}.py") for i in range(5)
]
source_parts = []
for path in chunk_files:
    with open(path, encoding="utf-8") as f:
        raw_lines = f.readlines()
    # Strip leading line numbers (e.g., "250: ") from chunk files
    cleaned = [re.sub(r'^\s*\d+:\s*', '', line) for line in raw_lines]
    source_parts.append(''.join(cleaned))

# Fix relative imports in chunk files to absolute module paths
source = "\n".join(source_parts)
source = re.sub(r"from \.combat_tracker\.(\S+)", r"from app.ui.panels.combat_tracker.\1", source)

# Create module and execute code
mod = types.ModuleType(__name__)
mod.__package__ = __package__
exec(compile(source, os.path.join(root_dir, "combat_tracker_panel.chunks.py"), "exec"), mod.__dict__)

# Expose the class
CombatTrackerPanel = mod.CombatTrackerPanel
