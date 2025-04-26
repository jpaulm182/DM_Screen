# /home/jpaulm_loki/Github/DM_Screen_New/app/ui/panels/combat_dialogs.py
import re
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTextEdit, QFormLayout, QWidget, QFrame, QSpinBox, QCheckBox,
    QGridLayout, QMessageBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor

# Assuming roll_dice is now in combat_utils
# If it's not, adjust this import path accordingly
# NOTE: We will add the import for get_attr later if needed for CombatantDetailsDialog
from .combat_utils import roll_dice, get_attr # Added get_attr import
# from .combat_constants import CONDITIONS # Import if needed by ConcentrationDialog logic


# --- Combatant Details Dialog ---

class CombatantDetailsDialog(QDialog):
    """Dialog to display detailed information about a combatant."""

    # Define signals if needed, e.g., for editing
    # dataChanged = Signal()

    def __init__(self, combatant_data, combatant_type, parent=None):
        super().__init__(parent)
        self.combatant_data = combatant_data
        self.combatant_type = combatant_type # "monster", "character", or other

        # Store the helper function from combat_utils
        # Assuming get_attr is moved to combat_utils.py
        self.get_attr = get_attr

        # Get the name of the combatant
        name = self.get_attr(combatant_data, "name", "Unknown", [])

        if combatant_type == "monster":
            self.setWindowTitle(f"Monster: {name}")
        elif combatant_type == "character":
            self.setWindowTitle(f"Character: {name}")
        else:
            self.setWindowTitle(f"Combatant: {name}")

        self.setMinimumSize(450, 500) # Increased min height slightly
        self._setup_ui() # We will add this call back later

# --- Dialog Classes --- 


class DeathSavesDialog(QDialog):
    """Dialog for tracking death saving throws"""
    def __init__(self, parent=None, current_saves=None):
        super().__init__(parent)
        self.setWindowTitle("Death Saving Throws")
        self.current_saves = current_saves or {"successes": 0, "failures": 0}
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout()
        
        # Successes
        success_group = QGroupBox("Successes")
        success_layout = QHBoxLayout()
        self.success_checks = []
        for i in range(3):
            check = QCheckBox()
            check.setChecked(i < self.current_saves["successes"])
            self.success_checks.append(check)
            success_layout.addWidget(check)
        success_group.setLayout(success_layout)
        layout.addWidget(success_group)
        
        # Failures
        failure_group = QGroupBox("Failures")
        failure_layout = QHBoxLayout()
        self.failure_checks = []
        for i in range(3):
            check = QCheckBox()
            check.setChecked(i < self.current_saves["failures"])
            self.failure_checks.append(check)
            failure_layout.addWidget(check)
        failure_group.setLayout(failure_layout)
        layout.addWidget(failure_group)
        
        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        self.setLayout(layout)
    
    def get_saves(self):
        """Get the current death saves state"""
        return {
            "successes": sum(1 for c in self.success_checks if c.isChecked()),
            "failures": sum(1 for c in self.failure_checks if c.isChecked())
        }


    def _setup_ui(self):
        """Set up the dialog UI with a compact layout"""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(6)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # --- Header with essential info ---
        header_widget = QWidget()
        header_layout = QVBoxLayout(header_widget)
        header_layout.setSpacing(2)
        header_layout.setContentsMargins(0, 0, 0, 0)

        # Name (large and bold)
        name = self.get_attr(self.combatant_data, "name", "Unknown", [])
        name_label = QLabel(name)
        name_label.setStyleSheet("font-size: 16pt; font-weight: bold;")
        header_layout.addWidget(name_label)

        # Type/Class line
        subheader_text = ""
        if self.combatant_type == "monster":
            size = self.get_attr(self.combatant_data, "size", "", [])
            type_val = self.get_attr(self.combatant_data, "type", "", [])
            alignment = self.get_attr(self.combatant_data, "alignment", "", [])

            if size and type_val:
                subheader_text = f"{size} {type_val}"
                if alignment:
                    subheader_text += f", {alignment}"
        else:  # character or unknown
            race = self.get_attr(self.combatant_data, "race", "", [])
            character_class = self.get_attr(self.combatant_data, "character_class", "", ["class"])
            level = self.get_attr(self.combatant_data, "level", None, [])

            parts = []
            if level is not None:
                parts.append(f"Level {level}")
            if race:
                parts.append(race)
            if character_class:
                parts.append(character_class)

            subheader_text = " ".join(parts)

        if subheader_text:
            subheader_label = QLabel(subheader_text)
            subheader_label.setStyleSheet("font-style: italic;")
            header_layout.addWidget(subheader_label)

        # Horizontal line separator
        header_layout.addWidget(QFrame(frameShape=QFrame.HLine))

        # --- Combat Stats in a single row ---
        combat_stats_layout = QHBoxLayout()
        combat_stats_layout.setSpacing(10)

        # AC
        ac = self.get_attr(self.combatant_data, "armor_class", None, ["ac", "AC"])
        if ac is not None:
            ac_layout = QVBoxLayout()
            ac_layout.setSpacing(0)
            ac_title = QLabel("AC")
            ac_title.setStyleSheet("font-weight: bold;")
            ac_title.setAlignment(Qt.AlignCenter)
            ac_layout.addWidget(ac_title)

            ac_value = QLabel(str(ac))
            ac_value.setAlignment(Qt.AlignCenter)
            ac_layout.addWidget(ac_value)
            combat_stats_layout.addLayout(ac_layout)

        # HP
        hp_layout = QVBoxLayout()
        hp_layout.setSpacing(0)
        hp_title = QLabel("HP")
        hp_title.setStyleSheet("font-weight: bold;")
        hp_title.setAlignment(Qt.AlignCenter)
        hp_layout.addWidget(hp_title)

        hp_current = self.get_attr(self.combatant_data, "current_hp", None, ["hp"])
        hp_max = self.get_attr(self.combatant_data, "max_hp", None, ["hit_points"])
        hp_text = "--"
        if hp_current is not None and hp_max is not None:
            hp_text = f"{hp_current} / {hp_max}"
        elif hp_max is not None: # Use max HP if current is unknown
             hp_text = f"-- / {hp_max}"
        elif hp_current is not None:
             hp_text = f"{hp_current} / --"
        elif self.combatant_type == "monster": # Try hit dice for monsters
             hit_dice = self.get_attr(self.combatant_data, "hit_dice", None)
             if hit_dice:
                 hp_text = f"({hit_dice})"

        hp_value = QLabel(hp_text)
        hp_value.setAlignment(Qt.AlignCenter)
        hp_layout.addWidget(hp_value)
        combat_stats_layout.addLayout(hp_layout)

        # Speed
        speed = self.get_attr(self.combatant_data, "speed", None, ["Speed"])
        if speed is not None:
            speed_layout = QVBoxLayout()
            speed_layout.setSpacing(0)
            speed_title = QLabel("Speed")
            speed_title.setStyleSheet("font-weight: bold;")
            speed_title.setAlignment(Qt.AlignCenter)
            speed_layout.addWidget(speed_title)

            # Speed can be a dict (e.g., {'walk': 30, 'fly': 60}) or a string
            speed_text = "--"
            if isinstance(speed, dict):
                speed_text = ", ".join([f"{k} {v} ft." for k, v in speed.items()])
            elif isinstance(speed, str):
                speed_text = speed # Assume it's formatted correctly
            elif isinstance(speed, (int, float)): # Simple numeric speed
                 speed_text = f"{speed} ft."

            speed_value = QLabel(speed_text)
            speed_value.setAlignment(Qt.AlignCenter)
            speed_layout.addWidget(speed_value)
            combat_stats_layout.addLayout(speed_layout)

        # --- Combine Header and Combat Stats ---
        main_layout.addWidget(header_widget)
        main_layout.addLayout(combat_stats_layout)
        main_layout.addSpacing(5)
        main_layout.addWidget(QFrame(frameShape=QFrame.HLine))
        main_layout.addSpacing(5)

        # --- Ability Scores ---
        ability_scores_layout = QHBoxLayout()
        ability_scores_layout.setSpacing(5)

        # Directly fetch scores from the top level of combatant_data
        full_scores = {
            'str': self.get_attr(self.combatant_data, 'str', None),
            'dex': self.get_attr(self.combatant_data, 'dex', None),
            'con': self.get_attr(self.combatant_data, 'con', None),
            'int': self.get_attr(self.combatant_data, 'int', None),
            'wis': self.get_attr(self.combatant_data, 'wis', None),
            'cha': self.get_attr(self.combatant_data, 'cha', None)
        }

        # Restore the loop and the original complex widget structure
        for ability, score in full_scores.items():
            ability_widget = QWidget()
            ability_vbox = QVBoxLayout(ability_widget)
            ability_vbox.setContentsMargins(0, 0, 0, 0)
            ability_vbox.setSpacing(0)

            ability_label = QLabel(ability.upper())
            ability_label.setStyleSheet("font-weight: bold;")
            ability_label.setAlignment(Qt.AlignCenter)
            ability_vbox.addWidget(ability_label)

            score_text = "--"
            mod_text = "(--)"
            if score is not None:
                try:
                    score_val = int(score)
                    score_text = str(score_val)
                    mod = (score_val - 10) // 2
                    mod_text = f"({mod:+})" # Show sign (+/-)
                except (ValueError, TypeError):
                    score_text = str(score) # Display as is if not an int

            score_label = QLabel(score_text)
            score_label.setAlignment(Qt.AlignCenter)
            ability_vbox.addWidget(score_label)

            mod_label = QLabel(mod_text)
            mod_label.setAlignment(Qt.AlignCenter)
            ability_vbox.addWidget(mod_label)

            # Explicitly set the layout for the container widget
            ability_widget.setLayout(ability_vbox)

            ability_scores_layout.addWidget(ability_widget)

        # --- Skills, Senses, Languages ---
        details_layout = QFormLayout()
        details_layout.setSpacing(4)
        details_layout.setLabelAlignment(Qt.AlignRight)

        # Saving Throws (if available)
        saves = self.get_attr(self.combatant_data, "saving_throws", None, ["saves"])
        if saves and isinstance(saves, dict): # Check if saves is a dict
            saves_text = ", ".join([f"{k.capitalize()} {v:+}" for k, v in saves.items()])
            details_layout.addRow(QLabel("<b>Saving Throws:</b>"), QLabel(saves_text))

        # Skills (if available)
        skills = self.get_attr(self.combatant_data, "skills", None)
        if skills and isinstance(skills, dict): # Check if skills is a dict
            # Filter out non-numeric skill values before formatting
            valid_skills = {k: v for k, v in skills.items() if isinstance(v, (int, float))}
            skills_text = ", ".join([f"{k.replace('_', ' ').title()} {v:+}" for k, v in valid_skills.items()])
            if skills_text: # Only add row if there are valid skills
                details_layout.addRow(QLabel("<b>Skills:</b>"), QLabel(skills_text))


        # Senses (if available)
        senses = self.get_attr(self.combatant_data, "senses", None)
        if senses:
             # Handle cases where senses might be a single string vs a dict
             if isinstance(senses, dict):
                 senses_text = ", ".join([f"{k.replace('_', ' ').title()} {v}" for k, v in senses.items()])
             else:
                 senses_text = str(senses) # Display as is if not a dict
             details_layout.addRow(QLabel("<b>Senses:</b>"), QLabel(senses_text))


        # Languages (if available)
        languages = self.get_attr(self.combatant_data, "languages", None)
        if languages:
            details_layout.addRow(QLabel("<b>Languages:</b>"), QLabel(languages))

        # Challenge Rating (for monsters)
        if self.combatant_type == "monster":
            cr = self.get_attr(self.combatant_data, "challenge_rating", None, ["cr"])
            xp = self.get_attr(self.combatant_data, "xp", None)
            if cr is not None:
                cr_text = str(cr)
                if xp is not None:
                    cr_text += f" ({xp} XP)"
                details_layout.addRow(QLabel("<b>Challenge:</b>"), QLabel(cr_text))

        # --- Combine sections ---
        # (Adding Ability Scores and Details to main layout)
        main_layout.addLayout(ability_scores_layout)
        main_layout.addSpacing(5)
        main_layout.addWidget(QFrame(frameShape=QFrame.HLine))
        main_layout.addSpacing(5)
        main_layout.addLayout(details_layout)

        # --- Resistances, Immunities, Vulnerabilities ---
        res_imm_vuln_layout = QVBoxLayout()
        res_imm_vuln_layout.setSpacing(2)

        vulnerabilities = self.get_attr(self.combatant_data, "damage_vulnerabilities", "", ["vulnerabilities"])
        resistances = self.get_attr(self.combatant_data, "damage_resistances", "", ["resistances"])
        immunities = self.get_attr(self.combatant_data, "damage_immunities", "", ["immunities"])
        condition_immunities = self.get_attr(self.combatant_data, "condition_immunities", "", ["condition immunities"])

        # Ensure these are strings or lists/tuples before adding them
        def format_list_or_string(data):
            if isinstance(data, (list, tuple)):
                return ", ".join(str(item) for item in data)
            elif isinstance(data, str):
                return data
            return ""

        vuln_str = format_list_or_string(vulnerabilities)
        if vuln_str:
            res_imm_vuln_layout.addWidget(QLabel(f"<b>Vulnerabilities:</b> {vuln_str}"))
        res_str = format_list_or_string(resistances)
        if res_str:
            res_imm_vuln_layout.addWidget(QLabel(f"<b>Resistances:</b> {res_str}"))
        imm_str = format_list_or_string(immunities)
        if imm_str:
            res_imm_vuln_layout.addWidget(QLabel(f"<b>Immunities:</b> {imm_str}"))
        cond_imm_str = format_list_or_string(condition_immunities)
        if cond_imm_str:
            res_imm_vuln_layout.addWidget(QLabel(f"<b>Condition Immunities:</b> {cond_imm_str}"))

        # --- Special Abilities ---
        abilities_layout = QVBoxLayout()
        abilities_layout.setSpacing(5)
        special_abilities = self.get_attr(self.combatant_data, "special_abilities", [], ["abilities"]) # Check 'abilities' as alt
        if special_abilities and isinstance(special_abilities, list):
             abilities_layout.addWidget(QLabel("<b>Special Abilities</b>"))
             abilities_layout.addWidget(QFrame(frameShape=QFrame.HLine))
             for ability in special_abilities:
                  # Check if ability is a dictionary before accessing keys
                 if not isinstance(ability, dict): continue

                 name = self.get_attr(ability, "name", "Unnamed Ability")
                 desc = self.get_attr(ability, "description", "No description.") # Correct key
                 usage = self.get_attr(ability, "usage", None)

                 ability_text = f"<b>{name}.</b> {desc}"
                 if usage:
                     usage_text = "Usage: "
                     if isinstance(usage, dict):
                        usage_text += f"{usage.get('type', '')}"
                        if usage.get('times'):
                            usage_text += f" ({usage.get('times')} times"
                            rest_types = usage.get('rest_types', [])
                            if rest_types and isinstance(rest_types, list): # Check if list
                                usage_text += f" per {', '.join(rest_types)}"
                            usage_text += ")"
                     else:
                        usage_text += str(usage) # Fallback
                     ability_text += f" <i>({usage_text})</i>"

                 ability_label = QLabel(ability_text)
                 ability_label.setWordWrap(True)
                 abilities_layout.addWidget(ability_label)
                 abilities_layout.addSpacing(3) # Small gap between abilities

        # --- Combine sections ---
        # (Adding Res/Imm/Vuln and Special Abilities to main layout)
        if res_imm_vuln_layout.count() > 0:
             main_layout.addSpacing(5)
             main_layout.addWidget(QFrame(frameShape=QFrame.HLine))
             main_layout.addLayout(res_imm_vuln_layout)

        if abilities_layout.count() > 2: # Check if abilities were added (label + hline + entries)
             main_layout.addSpacing(5)
             main_layout.addLayout(abilities_layout)

        # --- Actions ---
        actions_layout = QVBoxLayout()
        actions_layout.setSpacing(5)
        actions = self.get_attr(self.combatant_data, "actions", [])
        if actions and isinstance(actions, list):
            actions_layout.addWidget(QLabel("<b>Actions</b>"))
            actions_layout.addWidget(QFrame(frameShape=QFrame.HLine))
            for action in actions:
                # Check if action is a dictionary
                if not isinstance(action, dict): continue

                name = self.get_attr(action, "name", "Unnamed Action")
                desc = self.get_attr(action, "description", "No description.") # Correct key
                attack_bonus = self.get_attr(action, "attack_bonus", None)
                damage_list = self.get_attr(action, "damage", []) # Handle multiple damage parts
                dc = self.get_attr(action, "dc", None)
                usage = self.get_attr(action, "usage", None)

                action_text = f"<b>{name}.</b> {desc}" # Append the description right after the name
                if attack_bonus is not None:
                    action_text += f" <i>Melee or Ranged Weapon Attack:</i> +{attack_bonus} to hit."
                    # Add reach/range if available (needs parsing from desc or dedicated field)

                # Handle damage list
                if damage_list and isinstance(damage_list, list):
                    hit_parts = []
                    for damage_part in damage_list:
                        if not isinstance(damage_part, dict): continue
                        damage_dice = self.get_attr(damage_part, "damage_dice")
                        damage_type_data = self.get_attr(damage_part, "damage_type", {})
                        damage_type = self.get_attr(damage_type_data, "name", "damage") # Nested type

                        if damage_dice:
                            hit_parts.append(f"{damage_dice} {damage_type}")
                    if hit_parts:
                         action_text += f" <i>Hit:</i> {' or '.join(hit_parts)}." # Join multiple damages if needed

                if dc and isinstance(dc, dict):
                     dc_type_data = self.get_attr(dc, "dc_type", {})
                     dc_type = self.get_attr(dc_type_data, "name", "Save")
                     dc_value = self.get_attr(dc, "dc_value", "??")
                     success_type = self.get_attr(dc, "success_type", "negates effect")
                     action_text += f" (DC {dc_value} {dc_type} {success_type})"

                if usage:
                     usage_text = "Usage: "
                     # Similar usage formatting as special abilities
                     if isinstance(usage, dict):
                        usage_text += f"{usage.get('type', '')}"
                        if usage.get('times'):
                            usage_text += f" ({usage.get('times')} times"
                            rest_types = usage.get('rest_types', [])
                            if rest_types and isinstance(rest_types, list): # Check if list
                                usage_text += f" per {', '.join(rest_types)}"
                            usage_text += ")"
                     else:
                        usage_text += str(usage)
                     action_text += f" <i>({usage_text})</i>"

                action_label = QLabel(action_text)
                action_label.setWordWrap(True)
                actions_layout.addWidget(action_label)
                actions_layout.addSpacing(3)

        # --- Legendary Actions ---
        legendary_actions_layout = QVBoxLayout()
        legendary_actions_layout.setSpacing(5)
        legendary_actions = self.get_attr(self.combatant_data, "legendary_actions", [])
        if legendary_actions and isinstance(legendary_actions, list):
            # Get the description of how many legendary actions the creature gets
            legendary_desc = self.get_attr(self.combatant_data, "legendary_desc", "The creature can take legendary actions.")
            legendary_actions_layout.addWidget(QLabel(f"<b>Legendary Actions</b>"))
            legendary_actions_layout.addWidget(QLabel(f"<i>{legendary_desc}</i>"))
            legendary_actions_layout.addWidget(QFrame(frameShape=QFrame.HLine))

            for action in legendary_actions:
                if not isinstance(action, dict): continue
                name = self.get_attr(action, "name", "Unnamed Legendary Action")
                cost = self.get_attr(action, "cost", 1) # Assume cost is 1 if not specified
                desc = self.get_attr(action, "description", "No description.") # Correct key
                attack_bonus = self.get_attr(action, "attack_bonus", None)
                damage_list = self.get_attr(action, "damage", [])
                dc = self.get_attr(action, "dc", None)
                usage = self.get_attr(action, "usage", None)

                action_text = f"<b>{name}"
                # Cost is often part of the name or description, but check if explicit field exists
                # Let's assume cost is handled in description for now.
                # if cost > 1:
                #     action_text += f" (Costs {cost} Actions)"
                action_text += f".</b> {desc}" # Append the description right after the name
                # Add attack/damage info if present (needs parsing from desc or dedicated fields)
                if attack_bonus is not None:
                     action_text += f" (+{attack_bonus} to hit)" # Simplified

                action_label = QLabel(action_text)
                action_label.setWordWrap(True)
                legendary_actions_layout.addWidget(action_label)
                legendary_actions_layout.addSpacing(3)

        # --- Reactions ---
        reactions_layout = QVBoxLayout()
        reactions_layout.setSpacing(5)
        reactions = self.get_attr(self.combatant_data, "reactions", [])
        if reactions and isinstance(reactions, list):
             reactions_layout.addWidget(QLabel("<b>Reactions</b>"))
             reactions_layout.addWidget(QFrame(frameShape=QFrame.HLine))
             for reaction in reactions:
                 if not isinstance(reaction, dict): continue
                 name = self.get_attr(reaction, "name", "Unnamed Reaction")
                 desc = self.get_attr(reaction, "description", "No description.") # Correct key
                 reaction_text = f"<b>{name}.</b> {desc}" # Append the description right after the name
                 reaction_label = QLabel(reaction_text)
                 reaction_label.setWordWrap(True)
                 reactions_layout.addWidget(reaction_label)
                 reactions_layout.addSpacing(3)

        # --- Combine sections ---
        # (Adding Actions, Legendary Actions, Reactions to main layout)
        if actions_layout.count() > 2:
            main_layout.addSpacing(5)
            main_layout.addLayout(actions_layout)

        if legendary_actions_layout.count() > 3: # label + desc + hline + entries
             main_layout.addSpacing(5)
             main_layout.addLayout(legendary_actions_layout)

        if reactions_layout.count() > 2:
             main_layout.addSpacing(5)
             main_layout.addLayout(reactions_layout)

        main_layout.addStretch() # Push content up

        # Close button
        button_layout = QHBoxLayout()
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        button_layout.addStretch()
        button_layout.addWidget(close_button)
        button_layout.addStretch()
        main_layout.addLayout(button_layout)


# --- Damage/Healing Dialog ---
class DamageDialog(QDialog):
    """Dialog for applying damage or healing."""
    # Signal: amount (int), type (str), is_healing (bool)
    damageApplied = Signal(int, str, bool)

    def __init__(self, combatant_name, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Apply Damage/Healing to {combatant_name}")
        self._setup_ui()

    def _setup_ui(self):
        layout = QFormLayout(self)

        self.amount_input = QLineEdit()
        self.amount_input.setPlaceholderText("e.g., 10 or 2d6+3")
        layout.addRow("Amount/Dice:", self.amount_input)

        self.type_input = QLineEdit("bludgeoning") # Default type
        layout.addRow("Damage Type:", self.type_input)

        self.healing_checkbox = QCheckBox("Is Healing")
        layout.addRow(self.healing_checkbox)

        button_layout = QHBoxLayout()
        self.apply_button = QPushButton("Apply")
        self.apply_button.clicked.connect(self._apply)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addStretch()
        button_layout.addWidget(self.apply_button)
        button_layout.addWidget(self.cancel_button)
        layout.addRow(button_layout) # Add the button layout to the form

    def _apply(self):
        amount_str = self.amount_input.text().strip()
        damage_type = self.type_input.text().strip().lower() or "untyped"
        is_healing = self.healing_checkbox.isChecked()

        if not amount_str:
            QMessageBox.warning(self, "Invalid Input", "Please enter an amount or dice expression.")
            return

        try:
            # Check if it's a dice roll expression (more robust regex)
            # Allows spaces, negative modifiers, etc.
            dice_match = re.match(r"^\s*(\d+)\s*d\s*(\d+)\s*([+-]\s*\d+)?\s*$", amount_str, re.IGNORECASE)
            flat_match = re.match(r"^\s*([+-]?\d+)\s*$", amount_str)

            if dice_match:
                 # Use the imported roll_dice function
                 amount, _ = roll_dice(amount_str) # roll_dice should handle parsing
            elif flat_match:
                # Treat as a flat number
                amount = int(flat_match.group(1))
            else:
                raise ValueError("Input is not a valid number or dice expression.")

        except ValueError as ve:
            QMessageBox.warning(self, "Invalid Input", f"Please enter a valid number or dice expression (e.g., 10, 2d6, 1d8+2).\nError: {ve}")
            return
        except Exception as e: # Catch potential errors from roll_dice
            QMessageBox.critical(self, "Roll Error", f"Error calculating dice roll: {e}")
            return

        self.damageApplied.emit(amount, damage_type, is_healing)
        self.accept()


class DeathSavesDialog(QDialog):
    """Dialog for tracking death saving throws."""
    savesUpdated = Signal(int, int) # successes, failures

    def __init__(self, successes=0, failures=0, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Death Saving Throws")
        self.successes = successes
        self.failures = failures
        self._setup_ui()
        self._update_labels()

    def _setup_ui(self):
        layout = QGridLayout(self)

        self.success_label = QLabel("Successes:")
        self.success_count_label = QLabel()
        self.success_button = QPushButton("+ Success")
        self.success_button.clicked.connect(self._add_success)

        self.failure_label = QLabel("Failures:")
        self.failure_count_label = QLabel()
        self.failure_button = QPushButton("+ Failure")
        self.failure_button.clicked.connect(self._add_failure)

        self.reset_button = QPushButton("Reset Saves")
        self.reset_button.clicked.connect(self._reset_saves)

        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.accept) # Close dialog

        layout.addWidget(self.success_label, 0, 0)
        layout.addWidget(self.success_count_label, 0, 1)
        layout.addWidget(self.success_button, 0, 2)
        layout.addWidget(self.failure_label, 1, 0)
        layout.addWidget(self.failure_count_label, 1, 1)
        layout.addWidget(self.failure_button, 1, 2)
        layout.addWidget(self.reset_button, 2, 0, 1, 3, alignment=Qt.AlignCenter)
        layout.addWidget(self.close_button, 3, 0, 1, 3, alignment=Qt.AlignCenter)

    def _update_labels(self):
        self.success_count_label.setText(f"{self.successes} / 3")
        self.failure_count_label.setText(f"{self.failures} / 3")

        # Optionally disable buttons when max is reached
        can_change = self.successes < 3 and self.failures < 3
        self.success_button.setEnabled(can_change)
        self.failure_button.setEnabled(can_change)

        # Check for end state after update
        should_close = False
        if self.successes >= 3:
            QMessageBox.information(self, "Stable", "Combatant is stable (3 successes).")
            should_close = True
        elif self.failures >= 3:
             QMessageBox.warning(self, "Dead", "Combatant has died (3 failures).")
             should_close = True

        # Close *after* showing message if state is terminal
        if should_close:
            self.accept()


    def _add_success(self):
        if self.successes < 3 and self.failures < 3:
            self.successes += 1
            self.savesUpdated.emit(self.successes, self.failures)
            self._update_labels() # Update labels *after* emitting signal and checking state

    def _add_failure(self):
         if self.failures < 3 and self.successes < 3:
            self.failures += 1
            self.savesUpdated.emit(self.successes, self.failures)
            self._update_labels() # Update labels *after* emitting signal and checking state

    def _reset_saves(self):
        self.successes = 0
        self.failures = 0
        self.savesUpdated.emit(self.successes, self.failures)
        self._update_labels()


class ConcentrationDialog(QDialog):
    """Dialog for handling concentration checks."""
    # Signal: save_dc (int), damage_taken (int), result (bool: True=succeeded, False=failed)
    checkResult = Signal(int, int, bool)

    def __init__(self, combatant_name, con_save_bonus, damage_taken, parent=None):
        super().__init__(parent)
        self.combatant_name = combatant_name
        self.con_save_bonus = con_save_bonus
        self.damage_taken = damage_taken
        # DC is 10 or half the damage taken, whichever is higher
        self.save_dc = max(10, damage_taken // 2)
        self.final_roll = 0 # Initialize final roll storage

        self.setWindowTitle(f"Concentration Check: {combatant_name}")
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        info_text = (f"<b>{self.combatant_name}</b> took <b>{self.damage_taken}</b> damage "
                     f"while concentrating.\n"
                     f"Concentration DC: <b>{self.save_dc}</b> (Max(10, {self.damage_taken}//2))\n"
                     f"CON Save Bonus: <b>{self.con_save_bonus:+}</b>")
        info_label = QLabel(info_text)
        layout.addWidget(info_label)

        roll_layout = QHBoxLayout()
        roll_layout.addWidget(QLabel("Roll d20:"))
        self.roll_input = QSpinBox()
        self.roll_input.setRange(1, 20)
        roll_layout.addWidget(self.roll_input)
        roll_layout.addStretch()
        layout.addLayout(roll_layout)

        self.result_label = QLabel("Result: --")
        self.result_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.result_label)

        button_layout = QHBoxLayout()
        self.check_button = QPushButton("Check Save")
        self.check_button.clicked.connect(self._check_save)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addStretch()
        button_layout.addWidget(self.check_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

        # Connect roll input changes to update result display dynamically (optional but nice)
        self.roll_input.valueChanged.connect(self._update_result_display)
        # Initial display update
        self._update_result_display()


    def _update_result_display(self):
        """Updates the result label based on the current roll input."""
        roll = self.roll_input.value()
        total_save = roll + self.con_save_bonus
        succeeded = total_save >= self.save_dc

        result_text = f"Result: {roll} + {self.con_save_bonus} = {total_save} vs DC {self.save_dc} -> "
        if succeeded:
            result_text += "<span style='color: green;'>Success!</span>"
        else:
            result_text += "<span style='color: red;'>Failed!</span>"
        self.result_label.setText(result_text)


    def _check_save(self):
        """Finalize the check, emit the signal, and accept the dialog."""
        roll = self.roll_input.value()
        self.final_roll = roll # Store the final roll value
        total_save = roll + self.con_save_bonus
        succeeded = total_save >= self.save_dc

        # Emit the final result
        self.checkResult.emit(self.save_dc, self.damage_taken, succeeded)
        self.accept()


# ==============================================================================
# Generic Saving Throw Dialog
# ==============================================================================

ABILITIES = ["Strength", "Dexterity", "Constitution", "Intelligence", "Wisdom", "Charisma"]

class SavingThrowDialog(QDialog):
    """Dialog for handling a generic saving throw check."""

    def __init__(self, combatant_name, ability_name, save_bonus, save_dc, parent=None):
        super().__init__(parent)
        self.combatant_name = combatant_name
        self.ability_name = ability_name
        self.save_bonus = save_bonus
        self.save_dc = save_dc
        self.final_roll = 0  # Store the final d20 roll
        self.succeeded = False # Store the outcome

        self.setWindowTitle(f"{ability_name} Save: {combatant_name}")
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        info_text = (f"<b>{self.combatant_name}</b> must make a DC <b>{self.save_dc}</b> "
                     f"<b>{self.ability_name}</b> saving throw.\n"
                     f"{self.ability_name[:3].upper()} Save Bonus: <b>{self.save_bonus:+}</b>")
        info_label = QLabel(info_text)
        layout.addWidget(info_label)

        roll_layout = QHBoxLayout()
        roll_layout.addWidget(QLabel("Roll d20:"))
        self.roll_input = QSpinBox()
        self.roll_input.setRange(1, 20)
        self.roll_input.setToolTip("Enter the d20 roll result")
        roll_layout.addWidget(self.roll_input)
        roll_layout.addStretch()
        layout.addLayout(roll_layout)

        self.result_label = QLabel("Result: --")
        self.result_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.result_label)

        button_layout = QHBoxLayout()
        # Changed button text for clarity
        self.ok_button = QPushButton("Confirm Roll")
        self.ok_button.clicked.connect(self._finalize_save)
        self.ok_button.setDefault(True)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addStretch()
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

        # Connect roll input changes to update result display dynamically
        self.roll_input.valueChanged.connect(self._update_result_display)
        # Initial display update
        self._update_result_display()

    def _update_result_display(self):
        """Updates the result label based on the current roll input."""
        roll = self.roll_input.value()
        total_save = roll + self.save_bonus
        succeeded = total_save >= self.save_dc

        result_text = f"Result: {roll} + {self.save_bonus} = {total_save} vs DC {self.save_dc} \u2192 " # Using arrow
        if succeeded:
            result_text += "<span style='color: green;'>Success!</span>"
        else:
            result_text += "<span style='color: red;'>Failed!</span>"
        self.result_label.setText(result_text)

    def _finalize_save(self):
        """Store the final roll and outcome, then accept the dialog."""
        roll = self.roll_input.value()
        self.final_roll = roll
        total_save = roll + self.save_bonus
        self.succeeded = total_save >= self.save_dc
        self.accept() # Close dialog with success

    # Optional: Add getters if needed outside the dialog context, though we'll use attributes directly
    def get_roll(self):
        return self.final_roll

    def was_successful(self):
        return self.succeeded
