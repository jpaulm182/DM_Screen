#!/usr/bin/env python3
import sys, json
from pathlib import Path

# Ensure project root is on PYTHONPATH
sys.path.append(str(Path(__file__).parent.parent))

from app.ui.panels.combat_tracker.facade import CombatTrackerPanel


def main():
    """
    Test the combat tracker panel's ability mixing prevention logic.
    """
    # Create an uninitialized panel instance (bypass __init__)
    panel = CombatTrackerPanel.__new__(CombatTrackerPanel)

    # Sample combatants with a shared ability name
    combatants = [
        {
            "instance_id": "id1",
            "name": "Alpha",
            "actions": [{"name": "Strike"}]
        },
        {
            "instance_id": "id2",
            "name": "Beta",
            "actions": [{"name": "Strike"}]
        }
    ]

    # Apply ability mixing validation
    panel._validate_no_ability_mixing(combatants)

    # Display results
    print("After validation:")
    print(json.dumps(combatants, indent=2))


if __name__ == "__main__":
    main()
