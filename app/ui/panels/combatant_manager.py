from .combat_utils import get_attr, extract_dice_formula, roll_dice
from app.ui.panels.combat_utils import get_attr, extract_dice_formula, roll_dice# combatant_manager.py
"""
Functions for managing combatant data: add, update, verify, etc.
"""
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from .combat_utils import get_attr, extract_dice_formula, roll_dice
import random
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
            hp_value = get_attr(monster_data, "hp", 10, ["hit_points", "hitPoints", "hit_points_roll", "hit_dice"])
            # Calculate max_hp
            max_hp = 0
            if isinstance(hp_value, int):
                max_hp = hp_value
            elif isinstance(hp_value, dict) and 'average' in hp_value:
                max_hp = int(hp_value['average'])
            elif isinstance(hp_value, str):
                match = re.match(r'(\d+)\s*\(', hp_value)
                if match:
                    max_hp = int(match.group(1))
                elif hp_value.isdigit():
                    max_hp = int(hp_value)
            if max_hp <= 0:
                max_hp = 10
            dice_formula = extract_dice_formula(hp_value)
            if dice_formula:
                hp = roll_dice(dice_formula)
            else:
                if max_hp > 200:
                    die_size = 12
                    num_dice = max(1, int(max_hp * 0.75 / (die_size/2 + 0.5)))
                elif max_hp > 100:
                    die_size = 10
                    num_dice = max(1, int(max_hp * 0.8 / (die_size/2 + 0.5)))
                else:
                    die_size = 8
                    num_dice = max(1, int(max_hp * 0.85 / (die_size/2 + 0.5)))
                modifier = int(max_hp * 0.1)
                estimated_formula = f"{num_dice}d{die_size}+{modifier}"
                hp = roll_dice(estimated_formula)
                min_hp = int(max_hp * 0.5)
                max_possible_hp = int(max_hp * 1.25)
                hp = max(min_hp, min(hp, max_possible_hp))
            max_hp = hp
            ac = get_attr(monster_data, "ac", 10, ["armor_class", "armorClass", "AC"])
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
