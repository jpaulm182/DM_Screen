#!/usr/bin/env python3
"""Create app/ui/panels/combat_tracker/facade.py which re-exports the original API, delegating
calls to implementations that live in separate modules."""
from pathlib import Path
import yaml, re, textwrap

# Read the public API description and module mapping
api = Path("public_api.md").read_text()
module_map = yaml.safe_load(Path("module_map.yml").read_text())

# Generate the facade file in the combat_tracker package
target = Path("app/ui/panels/combat_tracker/facade.py")
lines = ["class CombatTrackerPanel:", "    \"\"\"Auto-generated facade class. Delegates to modules.\"\"\""]

# Find all public methods from the API description
methods = re.findall(r"\* \*([A-Za-z_][A-Za-z0-9_]*)\(", api)
for m in methods:
    dest = module_map.get(m)
    if not dest:
        continue
    # Add delegate method
    stub = textwrap.dedent(f"""
        def {m}(self, *args, **kwargs):
            from .{dest} import {m} as _impl
            return _impl(*args, **kwargs)
    """)
    lines.append(stub)

target.write_text("\n".join(lines) + "\n")
print(f"Wrote facade to {target}")
