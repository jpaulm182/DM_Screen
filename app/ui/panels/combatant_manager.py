from .combat_utils import get_attr, extract_dice_formula, roll_dice
from app.ui.panels.combat_utils import get_attr, extract_dice_formula, roll_dice# combatant_manager.py
"""
Functions for managing combatant data: add, update, verify, etc.
"""
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from .combat_utils import get_attr, extract_dice_formula, roll_dice
import random
import re  # Needed for extracting average HP from strings like '256 (19d12 + 133)'
import re

class CombatantManager:
    @staticmethod
    def add_monster(panel, monster_data):
        """Add a monster to the tracker via the given panel."""
        if not monster_data:
            return -1
        panel.initiative_table.blockSignals(True)
        try:
            name = get_attr(monster_data, "name", "Unknown Monster")
            monster_id = panel.monster_id_counter
            panel.monster_id_counter += 1
            dex = get_attr(monster_data, "dexterity", 10, ["dex", "DEX"])
            init_mod = (dex - 10) // 2
            initiative_roll = random.randint(1, 20) + init_mod

            # --- REFACTOR: Use canonical HP/AC fields directly if present ---
            # The monster_data dict from MonsterPanel should have integer 'hp', 'max_hp', and 'ac' fields.
            hp = monster_data.get('hp', 10)
            max_hp = monster_data.get('max_hp', hp)
            ac = monster_data.get('ac', 10)
            # Validate types, fallback to default if invalid
            if not isinstance(hp, int):
                try:
                    hp = int(hp)
                except Exception:
                    hp = 10
            if not isinstance(max_hp, int):
                try:
                    max_hp = int(max_hp)
                except Exception:
                    max_hp = hp
            if not isinstance(ac, int):
                try:
                    ac = int(ac)
                except Exception:
                    ac = 10
            # --- END REFACTOR ---

            monster_stats = {
                "id": monster_id,
                "name": name,
                "hp": hp,
                "max_hp": max_hp,
                "ac": ac
            }
            row = panel._add_combatant(name, initiative_roll, hp, max_hp, ac, "monster", monster_id)
            if row is None:
                row = -1
            if row >= 0:
                panel.combatants[row] = monster_data
            panel.initiative_table.viewport().update()
            QApplication.processEvents()
            QTimer.singleShot(50, lambda: panel._verify_monster_stats(monster_stats))
            panel._log_combat_action("Setup", "DM", "added monster", name, f"(Init: {initiative_roll}, HP: {hp}/{max_hp})")
            return row
        finally:
            panel.initiative_table.blockSignals(False)

    # Additional combatant management methods can be added here.
