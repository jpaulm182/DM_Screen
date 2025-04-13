# app/ui/panels/combat_tracker_panel.py - Combat tracker panel
"""
Combat tracker panel for managing initiative and combat encounters

Features:
- Initiative tracking with auto-sorting
- HP and AC management
- Status conditions with quick apply
- Death saving throws tracking
- Concentration tracking
- Combat timer
- Round/turn tracking
- Keyboard shortcuts
- Quick HP updates
- Combat log integration
- View monster and character details
- Inline details panel for quick reference
"""

from PySide6.QtWidgets import (
    QTableWidget, QTableWidgetItem, QHeaderView, QPushButton,
    QLineEdit, QSpinBox, QHBoxLayout, QVBoxLayout, QComboBox,
    QLabel, QCheckBox, QMenu, QMessageBox, QDialog, QDialogButtonBox,
    QGroupBox, QWidget, QStyledItemDelegate, QStyle, QToolButton,
    QTabWidget, QScrollArea, QFormLayout, QFrame, QSplitter, QApplication,
    QSizePolicy
)
from PySide6.QtCore import Qt, QTimer, Signal, Slot, QSize
from PySide6.QtGui import QAction, QColor, QIcon, QKeySequence, QBrush, QPalette
import random
import re

from app.ui.panels.base_panel import BasePanel
from app.ui.panels.panel_category import PanelCategory

# D&D 5e Conditions
CONDITIONS = [
    "Blinded", "Charmed", "Deafened", "Frightened", "Grappled",
    "Incapacitated", "Invisible", "Paralyzed", "Petrified",
    "Poisoned", "Prone", "Restrained", "Stunned", "Unconscious"
]

# --- Custom Delegates for Table Cell Display ---

class CurrentTurnDelegate(QStyledItemDelegate):
    '''Delegate to handle custom painting for the current turn row.'''
    def paint(self, painter, option, index):
        # Check if this item belongs to the current turn using UserRole + 1
        is_current = index.data(Qt.UserRole + 1)
        
        if is_current == True: # Explicit check for True
            # Save painter state
            painter.save()
            
            # Define highlight colors
            highlight_bg = QColor(0, 51, 102) # Dark blue background (#003366)
            highlight_fg = QColor(Qt.white) # White text
            
            # Fill background
            painter.fillRect(option.rect, highlight_bg)
            
            # Set text color
            pen = painter.pen()
            pen.setColor(highlight_fg)
            painter.setPen(pen)
            
            # Draw text (adjusting rect slightly for padding)
            text_rect = option.rect.adjusted(5, 0, -5, 0) # Add horizontal padding
            painter.drawText(text_rect, option.displayAlignment, index.data(Qt.DisplayRole))
            
            # Restore painter state
            painter.restore()
        else:
            # Default painting for non-current turns
            super().paint(painter, option, index)

class HPUpdateDelegate(QStyledItemDelegate):
    """Delegate to handle HP updates with quick buttons"""
    
    # Signal to notify HP changes
    hpChanged = Signal(int, int)  # row, new_hp
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.buttons = {}  # Store buttons for each cell
    
    def createEditor(self, parent, option, index):
        """Create editor for HP cell (SpinBox)"""
        editor = QSpinBox(parent)
        editor.setMinimum(0)
        editor.setMaximum(999)
        
        # Get max HP from UserRole
        max_hp = index.data(Qt.UserRole) or 999
        editor.setMaximum(max_hp)
        
        return editor
    
    def setEditorData(self, editor, index):
        """Set editor data from the model"""
        value = int(index.data(Qt.DisplayRole) or 0)
        editor.setValue(value)
    
    def setModelData(self, editor, model, index):
        """Set model data from the editor"""
        value = editor.value()
        model.setData(index, str(value), Qt.DisplayRole)
        
        # Emit signal for hp changed
        self.hpChanged.emit(index.row(), value)

class InitiativeUpdateDelegate(QStyledItemDelegate):
    """Delegate to handle initiative updates with auto-sorting"""
    
    # Signal to notify initiative changes
    initChanged = Signal(int, int)  # row, new_initiative
    
    def __init__(self, parent=None):
        super().__init__(parent)
    
    def createEditor(self, parent, option, index):
        """Create editor for Initiative cell (SpinBox)"""
        editor = QSpinBox(parent)
        editor.setMinimum(-20)  # Allow negative initiative
        editor.setMaximum(30)
        return editor
    
    def setEditorData(self, editor, index):
        """Set editor data from the model"""
        try:
            value = int(index.data(Qt.DisplayRole) or 0)
            editor.setValue(value)
        except ValueError:
            editor.setValue(0)
    
    def setModelData(self, editor, model, index):
        """Set model data from the editor"""
        value = editor.value()
        model.setData(index, str(value), Qt.DisplayRole)
        
        # Emit signal for initiative changed
        self.initChanged.emit(index.row(), value)

# --- Dialog Classes --- 

class CombatantDetailsDialog(QDialog):
    """Dialog for displaying monster or character details"""
    def __init__(self, parent=None, combatant_data=None, combatant_type=None):
        super().__init__(parent)
        self.combatant_data = combatant_data
        self.combatant_type = combatant_type  # "monster", "character", or "unknown"
        
        # Debug: Print raw combatant data
        print(f"[CombatDetailsDialog] Received data for {combatant_type}: {combatant_data}")
        
        # If it's an object with __dict__, print its attributes
        if hasattr(combatant_data, '__dict__'):
            print(f"[CombatDetailsDialog] Attributes: {combatant_data.__dict__}")
        
        # Helper function to get attribute from either dict or object
        def get_attr(obj, attr, default=None, alt_attrs=None):
            """Get attribute from object or dict, trying alternate attribute names if specified"""
            alt_attrs = alt_attrs or []
            
            result = default
            source = "default"
            
            if isinstance(obj, dict):
                # Try the main attribute name first
                if attr in obj:
                    result = obj[attr]
                    source = f"dict[{attr}]"
                # Try alternative attribute names
                elif any(alt_attr in obj for alt_attr in alt_attrs):
                    for alt_attr in alt_attrs:
                        if alt_attr in obj:
                            result = obj[alt_attr]
                            source = f"dict[{alt_attr}]"
                            break
                # Check if stats are nested in a 'stats' dictionary
                elif 'stats' in obj and isinstance(obj['stats'], dict):
                    if attr in obj['stats']:
                        result = obj['stats'][attr]
                        source = f"dict[stats][{attr}]"
                    else:
                        for alt_attr in alt_attrs:
                            if alt_attr in obj['stats']:
                                result = obj['stats'][alt_attr]
                                source = f"dict[stats][{alt_attr}]"
                                break
                
                # If attribute is ability_scores, check for individual abilities
                elif attr == "ability_scores":
                    # Try to build ability_scores from individual attributes
                    ability_scores = {}
                    ability_pairs = [
                        ("strength", "str"), 
                        ("dexterity", "dex"), 
                        ("constitution", "con"),
                        ("intelligence", "int"), 
                        ("wisdom", "wis"), 
                        ("charisma", "cha")
                    ]
                    
                    for full_name, short_name in ability_pairs:
                        # Check for abilities in the main dict
                        if full_name in obj:
                            ability_scores[short_name] = obj[full_name]
                        elif short_name in obj:
                            ability_scores[short_name] = obj[short_name]
                        # Check in stats dict if it exists
                        elif 'stats' in obj and isinstance(obj['stats'], dict):
                            if full_name in obj['stats']:
                                ability_scores[short_name] = obj['stats'][full_name]
                            elif short_name in obj['stats']:
                                ability_scores[short_name] = obj['stats'][short_name]
                    
                    # If we found any abilities, return them
                    if ability_scores:
                        result = ability_scores
                        source = "individual_dict_attrs"
            
            # Try getattr for object access
            elif hasattr(obj, attr):
                result = getattr(obj, attr)
                source = f"obj.{attr}"
            # Try alternative attributes for objects
            elif any(hasattr(obj, alt_attr) for alt_attr in alt_attrs):
                for alt_attr in alt_attrs:
                    if hasattr(obj, alt_attr):
                        result = getattr(obj, alt_attr)
                        source = f"obj.{alt_attr}"
                        break
            
            # If attribute is ability_scores, check for individual abilities
            elif attr == "ability_scores" and not hasattr(obj, attr):
                # Try to build ability_scores from individual attributes
                ability_scores = {}
                ability_pairs = [
                    ("strength", "str"), 
                    ("dexterity", "dex"), 
                    ("constitution", "con"),
                    ("intelligence", "int"), 
                    ("wisdom", "wis"), 
                    ("charisma", "cha")
                ]
                
                for full_name, short_name in ability_pairs:
                    # Try full name
                    if hasattr(obj, full_name):
                        ability_scores[short_name] = getattr(obj, full_name)
                    # Try short name
                    elif hasattr(obj, short_name):
                        ability_scores[short_name] = getattr(obj, short_name)
                    # Try upper case short name (e.g., "STR")
                    elif hasattr(obj, short_name.upper()):
                        ability_scores[short_name] = getattr(obj, short_name.upper())
                
                # If we found any abilities, return them
                if ability_scores:
                    result = ability_scores
                    source = "individual_obj_attrs"
            
            # Debug print for ability_scores attribute
            if attr == "ability_scores":
                print(f"[CombatDetailsDialog] get_attr('{attr}') = {result} (from {source})")
                
                # If we have a dict, check for keys in different formats
                if isinstance(obj, dict):
                    for key in obj.keys():
                        if isinstance(key, str) and key.lower() in ["ability_scores", "ability scores", "abilities", "stats"]:
                            print(f"[CombatDetailsDialog] Found potential ability scores key: '{key}' = {obj[key]}")
                
                # If we have an object, check for attributes in different formats
                else:
                    for attr_name in dir(obj):
                        if attr_name.lower() in ["ability_scores", "ability scores", "abilities", "stats"]:
                            print(f"[CombatDetailsDialog] Found potential ability scores attribute: '{attr_name}' = {getattr(obj, attr_name)}")
            
            return result
             
        # Store the helper function as an instance method
        self.get_attr = get_attr
        
        # Get the name of the combatant
        name = self.get_attr(combatant_data, "name", "Unknown", [])
        
        if combatant_type == "monster":
            self.setWindowTitle(f"Monster: {name}")
        elif combatant_type == "character":
            self.setWindowTitle(f"Character: {name}")
        else:
            self.setWindowTitle(f"Combatant: {name}")
            
        self.setMinimumSize(450, 400)
        self._setup_ui()
    
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
        
        hp_text = ""
        if self.combatant_type == "monster":
            hp = self.get_attr(self.combatant_data, "hit_points", None, ["hp", "HP"])
            if hp is not None:
                hp_text = str(hp)
        else:  # character
            current_hp = self.get_attr(self.combatant_data, "current_hp", None, ["hp"])
            max_hp = self.get_attr(self.combatant_data, "max_hp", None, ["maximum_hp"])
            if current_hp is not None and max_hp is not None:
                hp_text = f"{current_hp}/{max_hp}"
                
                temp_hp = self.get_attr(self.combatant_data, "temp_hp", 0, ["temporary_hp"])
                if temp_hp and int(temp_hp) > 0:
                    hp_text += f" (+{temp_hp})"
        
        hp_value = QLabel(hp_text or "—")
        hp_value.setAlignment(Qt.AlignCenter)
        hp_layout.addWidget(hp_value)
        combat_stats_layout.addLayout(hp_layout)
        
        # Speed
        speed = self.get_attr(self.combatant_data, "speed", None, [])
        if speed is not None:
            speed_layout = QVBoxLayout()
            speed_layout.setSpacing(0)
            speed_title = QLabel("Speed")
            speed_title.setStyleSheet("font-weight: bold;")
            speed_title.setAlignment(Qt.AlignCenter)
            speed_layout.addWidget(speed_title)
            
            speed_value = QLabel(f"{speed}")
            speed_value.setAlignment(Qt.AlignCenter)
            speed_layout.addWidget(speed_value)
            combat_stats_layout.addLayout(speed_layout)
        
        # Initiative (for characters)
        if self.combatant_type == "character":
            init_bonus = self.get_attr(self.combatant_data, "initiative_bonus", None, ["initiative"])
            if init_bonus is not None:
                init_layout = QVBoxLayout()
                init_layout.setSpacing(0)
                init_title = QLabel("Init")
                init_title.setStyleSheet("font-weight: bold;")
                init_title.setAlignment(Qt.AlignCenter)
                init_layout.addWidget(init_title)
                
                init_text = f"+{init_bonus}" if int(init_bonus) >= 0 else str(init_bonus)
                init_value = QLabel(init_text)
                init_value.setAlignment(Qt.AlignCenter)
                init_layout.addWidget(init_value)
                combat_stats_layout.addLayout(init_layout)
        
        # CR (for monsters)
        if self.combatant_type == "monster":
            cr = self.get_attr(self.combatant_data, "challenge_rating", None, ["cr", "CR"])
            if cr is not None:
                cr_layout = QVBoxLayout()
                cr_layout.setSpacing(0)
                cr_title = QLabel("CR")
                cr_title.setStyleSheet("font-weight: bold;")
                cr_title.setAlignment(Qt.AlignCenter)
                cr_layout.addWidget(cr_title)
                
                cr_value = QLabel(str(cr))
                cr_value.setAlignment(Qt.AlignCenter)
                cr_layout.addWidget(cr_value)
                combat_stats_layout.addLayout(cr_layout)
        
        header_layout.addLayout(combat_stats_layout)
        
        # --- Ability Scores in a dedicated section ---
        ability_scores = {}
        
        # First try to get ability_scores as a dict
        scores_dict = self.get_attr(self.combatant_data, "ability_scores", {}, [])
        print(f"[CombatDetailsDialog] Initial ability_scores retrieval: {scores_dict}")
        
        if scores_dict and isinstance(scores_dict, dict):
            ability_scores = scores_dict
            print(f"[CombatDetailsDialog] Using scores_dict: {ability_scores}")
        # If not found as a dict, try individual ability scores
        elif any(self.get_attr(self.combatant_data, attr, None, [alt]) is not None 
                for attr, alt in [
                    ("strength", "str"),
                    ("dexterity", "dex"),
                    ("constitution", "con"),
                    ("intelligence", "int"),
                    ("wisdom", "wis"),
                    ("charisma", "cha")
                ]):
            ability_scores = {
                'str': self.get_attr(self.combatant_data, "strength", 'X', ["str"]),
                'dex': self.get_attr(self.combatant_data, "dexterity", 'X', ["dex"]),
                'con': self.get_attr(self.combatant_data, "constitution", 'X', ["con"]),
                'int': self.get_attr(self.combatant_data, "intelligence", 'X', ["int"]),
                'wis': self.get_attr(self.combatant_data, "wisdom", 'X', ["wis"]),
                'cha': self.get_attr(self.combatant_data, "charisma", 'X', ["cha"])
            }
            print(f"[CombatDetailsDialog] Using individual abilities: {ability_scores}")
        # If still empty, provide default values
        else:
            ability_scores = {
                'str': 'X', 'dex': 'X', 'con': 'X', 'int': 'X', 'wis': 'X', 'cha': 'X'
            }
            print(f"[CombatDetailsDialog] Using default values: {ability_scores}")
        
        # Also check if ability_scores exist in uppercase format
        if hasattr(self.combatant_data, 'ABILITY_SCORES'):
            print(f"[CombatDetailsDialog] Found uppercase ABILITY_SCORES: {self.combatant_data.ABILITY_SCORES}")
        
        # Print the final ability_scores being used
        print(f"[CombatDetailsDialog] Final ability_scores for display: {ability_scores}")
        
        ability_map = {
            'str': 'STR', 'strength': 'STR',
            'dex': 'DEX', 'dexterity': 'DEX',
            'con': 'CON', 'constitution': 'CON',
            'int': 'INT', 'intelligence': 'INT',
            'wis': 'WIS', 'wisdom': 'WIS',
            'cha': 'CHA', 'charisma': 'CHA'
        }
        
        # Create a dedicated section for ability scores with a border (always show)
        abilities_group = QGroupBox("Ability Scores")
        abilities_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        abilities_layout = QHBoxLayout(abilities_group)
        abilities_layout.setSpacing(5)
        abilities_layout.setContentsMargins(10, 15, 10, 10)
        
        # Helper to get modifier as string
        def get_mod_str(score):
            if score == 'X':
                return '(?)'
            if isinstance(score, str):
                try:
                    score = int(score)
                except ValueError:
                    return '(?)'
            mod = (score - 10) // 2
            return f"+{mod}" if mod >= 0 else str(mod)
        
        # Always show all six ability scores
        for ability, label in [('str', 'STR'), ('dex', 'DEX'), ('con', 'CON'), 
                              ('int', 'INT'), ('wis', 'WIS'), ('cha', 'CHA')]:
            # Get score value (default to 'X' if not found)
            score = ability_scores.get(ability, None)
            
            # Try uppercase key if lowercase not found
            if score is None:
                score = ability_scores.get(ability.upper(), 'X')
                print(f"[CombatDetailsDialog] Tried uppercase key '{ability.upper()}': {score}")
            
            # Try other variations
            if score == 'X':
                # Try variations like 'Strength', 'STRENGTH', etc.
                variations = [
                    ability,
                    ability.upper(),
                    ability.capitalize(),
                    {'str': 'strength', 'dex': 'dexterity', 'con': 'constitution', 
                     'int': 'intelligence', 'wis': 'wisdom', 'cha': 'charisma'}[ability],
                    {'str': 'STRENGTH', 'dex': 'DEXTERITY', 'con': 'CONSTITUTION', 
                     'int': 'INTELLIGENCE', 'wis': 'WISDOM', 'cha': 'CHARISMA'}[ability]
                ]
                
                for variation in variations:
                    if variation in ability_scores:
                        score = ability_scores[variation]
                        print(f"[CombatDetailsDialog] Found ability score using variation '{variation}': {score}")
                        break
            
            print(f"[CombatDetailsDialog] Final score for {label}: {score}")
            
            score_layout = QVBoxLayout()
            score_layout.setSpacing(2)
            
            # Ability name (STR, DEX, etc.)
            ability_title = QLabel(label)
            ability_title.setStyleSheet("font-weight: bold; font-size: 11pt;")
            ability_title.setAlignment(Qt.AlignCenter)
            score_layout.addWidget(ability_title)
            
            # Score value
            score_value_label = QLabel(str(score))
            score_value_label.setStyleSheet("font-size: 12pt;")
            score_value_label.setAlignment(Qt.AlignCenter)
            score_layout.addWidget(score_value_label)
            
            # Modifier in parentheses
            mod_text = get_mod_str(score)
            mod_label = QLabel(f"({mod_text})")
            mod_label.setStyleSheet("color: #444;")
            mod_label.setAlignment(Qt.AlignCenter)
            score_layout.addWidget(mod_label)
            
            abilities_layout.addLayout(score_layout)
        
        # Add the abilities group below the combat stats
        header_layout.addWidget(abilities_group)
        
        main_layout.addWidget(header_widget)
        
        # --- Tabbed Content ---
        content_tabs = QTabWidget()
        content_tabs.setTabPosition(QTabWidget.North)
        
        # --- Tab: Features & Traits ---
        traits_tab = QWidget()
        traits_layout = QVBoxLayout(traits_tab)
        traits_layout.setContentsMargins(5, 5, 5, 5)
        
        # Different content based on combatant type
        if self.combatant_type == "monster":
            # Get traits
            traits_data = self.get_attr(self.combatant_data, "special_traits", None, ["traits"])
            if traits_data:
                traits_widget = self._create_titled_section("Special Traits", traits_data)
                traits_layout.addWidget(traits_widget)
            
            # Languages
            languages = self.get_attr(self.combatant_data, "languages", "", [])
            if languages:
                languages_label = QLabel(f"<b>Languages:</b> {languages}")
                languages_label.setWordWrap(True)
                traits_layout.addWidget(languages_label)
            
            # Senses
            senses = self.get_attr(self.combatant_data, "senses", [], [])
            if senses:
                senses_text = ", ".join([f"{s.name} {s.range}" for s in senses]) if hasattr(senses[0], 'name') else str(senses)
                senses_label = QLabel(f"<b>Senses:</b> {senses_text}")
                senses_label.setWordWrap(True)
                traits_layout.addWidget(senses_label)
        else:  # character
            # Background
            background = self.get_attr(self.combatant_data, "background", "", [])
            if background:
                bg_label = QLabel(f"<b>Background:</b> {background}")
                bg_label.setWordWrap(True)
                traits_layout.addWidget(bg_label)
            
            # Features
            features = self.get_attr(self.combatant_data, "features", [], ["traits", "feats"])
            if features:
                features_widget = self._create_feature_list("Features & Traits", features)
                traits_layout.addWidget(features_widget)
        
        traits_layout.addStretch()
        content_tabs.addTab(traits_tab, "Features")
        
        # --- Tab: Actions ---
        actions_tab = QWidget()
        actions_layout = QVBoxLayout(actions_tab)
        actions_layout.setContentsMargins(5, 5, 5, 5)
        
        if self.combatant_type == "monster":
            # Standard actions
            actions_data = self.get_attr(self.combatant_data, "actions", [], [])
            if actions_data:
                actions_widget = self._create_titled_section("Actions", actions_data)
                actions_layout.addWidget(actions_widget)
                
            # Legendary actions
            legendary_actions = self.get_attr(self.combatant_data, "legendary_actions", [], [])
            if legendary_actions:
                legendary_widget = self._create_titled_section("Legendary Actions", legendary_actions)
                actions_layout.addWidget(legendary_widget)
        else:  # character
            # Equipment
            equipment = self.get_attr(self.combatant_data, "equipment", [], [])
            if equipment:
                equipment_widget = self._create_feature_list("Equipment", equipment)
                actions_layout.addWidget(equipment_widget)
            
            # Spells
            spells = self.get_attr(self.combatant_data, "spells", [], ["spell_list"])
            if spells:
                spells_widget = self._create_feature_list("Spells", spells)
                actions_layout.addWidget(spells_widget)
        
        actions_layout.addStretch()
        content_tabs.addTab(actions_tab, "Actions & Items")
        
        # --- Tab: Notes/Description ---
        notes_tab = QWidget()
        notes_layout = QVBoxLayout(notes_tab)
        notes_layout.setContentsMargins(5, 5, 5, 5)
        
        if self.combatant_type == "monster":
            # Description
            description = self.get_attr(self.combatant_data, "description", "", [])
            if description:
                desc_label = QLabel(description)
                desc_label.setWordWrap(True)
                notes_layout.addWidget(desc_label)
        else:  # character
            # Notes
            notes = self.get_attr(self.combatant_data, "notes", "", [])
            if notes:
                notes_label = QLabel(notes)
                notes_label.setWordWrap(True)
                notes_layout.addWidget(notes_label)
                
        notes_layout.addStretch()
        content_tabs.addTab(notes_tab, "Notes")
        
        main_layout.addWidget(content_tabs)
        
        # --- OK Button ---
        button_box = QDialogButtonBox(QDialogButtonBox.Ok)
        button_box.accepted.connect(self.accept)
        main_layout.addWidget(button_box)

    def _create_titled_section(self, title, items_data):
        """Create a widget with a title and list of items with name/description fields"""
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)
        
        # Title
        title_label = QLabel(f"<b>{title}</b>")
        layout.addWidget(title_label)
        
        # Add each item
        for item in items_data:
            if isinstance(item, dict) and 'name' in item:
                # Get description from either 'desc' or 'description' field
                description = item.get('desc', item.get('description', ''))
                cost_text = ""
                if 'cost' in item and item['cost'] > 1:
                    cost_text = f" (Costs {item['cost']})"
                    
                item_label = QLabel(f"<b>{item['name']}{cost_text}.</b> {description}")
                item_label.setWordWrap(True)
                item_label.setTextFormat(Qt.RichText)
                layout.addWidget(item_label)
            elif hasattr(item, 'name'):
                # Get description from either 'desc' or 'description' attribute
                description = getattr(item, 'desc', getattr(item, 'description', ''))
                cost_text = ""
                if hasattr(item, 'cost') and item.cost > 1:
                    cost_text = f" (Costs {item.cost})"
                    
                item_label = QLabel(f"<b>{item.name}{cost_text}.</b> {description}")
                item_label.setWordWrap(True)
                item_label.setTextFormat(Qt.RichText)
                layout.addWidget(item_label)
                
        return section
        
    def _create_feature_list(self, title, items):
        """Create a widget with a title and list of string items"""
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)
        
        # Title
        title_label = QLabel(f"<b>{title}</b>")
        layout.addWidget(title_label)
        
        # Add each item
        for item in items:
            if isinstance(item, str):
                item_label = QLabel(item)
                item_label.setWordWrap(True)
                layout.addWidget(item_label)
            elif isinstance(item, dict) and 'name' in item:
                desc = item.get('description', item.get('desc', ''))
                if desc:
                    item_label = QLabel(f"<b>{item['name']}</b>: {desc}")
                else:
                    item_label = QLabel(f"<b>{item['name']}</b>")
                item_label.setWordWrap(True)
                layout.addWidget(item_label)
                
        return section

class DamageDialog(QDialog):
    """Dialog for applying damage or healing"""
    def __init__(self, parent=None, is_healing=False):
        super().__init__(parent)
        self.is_healing = is_healing
        self.setWindowTitle("Apply Healing" if is_healing else "Apply Damage")
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout()
        
        # Amount input
        amount_layout = QHBoxLayout()
        amount_layout.addWidget(QLabel("Amount:"))
        self.amount_spin = QSpinBox()
        self.amount_spin.setRange(0, 999)
        amount_layout.addWidget(self.amount_spin)
        layout.addLayout(amount_layout)
        
        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        self.setLayout(layout)
    
    def get_amount(self):
        """Get the entered amount"""
        return self.amount_spin.value()

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

class CombatTrackerPanel(BasePanel):
    """Panel for tracking combat initiative, HP, and conditions"""
    
    # Signal to emit when combat resolution is complete (or failed)
    # Carries the result dict and error string (one will be None)
    resolution_complete = Signal(dict, str)
    
    @property
    def current_turn(self):
        """Get the current turn index"""
        return getattr(self, '_current_turn', -1)
    
    @current_turn.setter
    def current_turn(self, value):
        """Set the current turn index"""
        self._current_turn = value

    def __init__(self, app_state):
        """Initialize the combat tracker panel"""
        # Store app state and get services
        self.app_state = app_state
        self.db = app_state.db_manager
        self.llm_service = app_state.llm_service
        
        # Combat state tracking
        self._current_turn = -1  # Index of current turn in initiative table
        self.current_round = 1
        self.combat_started = False
        self.timer_running = False
        self.combat_seconds = 0
        self.previous_turn = -1
        self.last_round_end_time = None  # For logging time between rounds
        self.game_elapsed_seconds = 0
        self.game_elapsed_minutes = 0
        
        # Combatant tracking
        self.combatants = {}  # Maps row index to full data structure (for monsters/characters)
        self.concentrating = set()  # Set of row indices that are concentrating
        self.death_saves = {}  # Maps row index to dict of {success: count, failure: count}
        self.show_details_pane = False  # Whether to show the details pane
        self.current_details_combatant = None  # Current combatant for details
        self.current_details_type = None  # Type of current combatant for details
        
        # Initialize timers
        self.timer = QTimer()
        self.timer.timeout.connect(self._update_timer)
        self.timer.setInterval(1000)  # 1 second interval
        self.combat_log = []  # List of combat log entries
        
        # Initialize base panel (calls _setup_ui)
        super().__init__(app_state, "Combat Tracker")
        
        print("[CombatTracker] Basic attributes initialized")
        
        # Set up our custom delegates after the table is created
        self._setup_delegates()
        
        # Ensure table is ready for display
        self._ensure_table_ready()
        
        # After state is restored, fix missing types
        QTimer.singleShot(500, self._fix_missing_types)
        
        print("[CombatTracker] Initialization completed successfully")
        
    def _ensure_table_ready(self):
        """Make sure the initiative table is ready for display and properly configured"""
        # First check if table exists
        if not hasattr(self, 'initiative_table'):
            print("[CombatTracker] ERROR: initiative_table not found during initialization")
            return
            
        # Ensure the vertical header is hidden (row numbers)
        self.initiative_table.verticalHeader().setVisible(False)
        
        # Make sure horizontal headers are visible
        self.initiative_table.horizontalHeader().setVisible(True)
        
        # Adjust column widths for better display
        self.initiative_table.resizeColumnsToContents()
        
        # Add test combatant if table is empty and we're in development
        if self.initiative_table.rowCount() == 0:
            # Restore state first if available
            state = self.app_state.get_setting("combat_tracker_state", None)
            if state:
                print("[CombatTracker] Restoring combat tracker state from settings")
                self.restore_state(state)
                # Force a table update after restoring state
                self.initiative_table.viewport().update()
                self.initiative_table.update()
            
            # If still empty after restore attempt, add placeholder
            if self.initiative_table.rowCount() == 0:
                # Add a demo player character if table is still empty
                print("[CombatTracker] Adding placeholder character to empty table for visibility")
                self._add_combatant("Add your party here!", 20, 30, 15, "character")
        
        # Ensure viewport is updated
        self.initiative_table.viewport().update()
        
        # Force application to process events
        QApplication.processEvents()
    
    def _setup_delegates(self):
        """Set up custom delegates for the initiative table"""
        # Set custom delegates for initiative and HP columns
        self.init_delegate = InitiativeUpdateDelegate(self)
        self.init_delegate.initChanged.connect(self._initiative_changed)
        self.initiative_table.setItemDelegateForColumn(1, self.init_delegate)
        
        self.hp_delegate = HPUpdateDelegate(self)
        self.hp_delegate.hpChanged.connect(self._hp_changed)
        self.initiative_table.setItemDelegateForColumn(2, self.hp_delegate)
        
        # Set delegate for highlighting current turn
        self.current_turn_delegate = CurrentTurnDelegate()
        for col in range(8):  # Apply to all columns (including the new Max HP column)
            self.initiative_table.setItemDelegateForColumn(col, self.current_turn_delegate)
        
        # When cell content changes, update internal data
        self.initiative_table.cellChanged.connect(self._handle_cell_changed)
    
    def _setup_ui(self):
        """Set up the combat tracker panel UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(4)
        
        # Create main splitter for combat tracker and details view
        self.main_splitter = QSplitter(Qt.Vertical)
        
        # Upper section: combat tracker
        combat_tracker_widget = QWidget()
        combat_layout = QVBoxLayout(combat_tracker_widget)
        combat_layout.setContentsMargins(0, 0, 0, 0)
        combat_layout.setSpacing(4)
        
        # --- Controls Area ---
        control_layout = self._setup_control_area()
        combat_layout.addLayout(control_layout)
        
        # --- Initiative Table ---
        self.initiative_table = QTableWidget()
        
        # Set table properties to ensure proper visibility
        self.initiative_table.setAlternatingRowColors(True)
        self.initiative_table.setShowGrid(True)
        self.initiative_table.setGridStyle(Qt.SolidLine)
        
        # Make sure the table expands to fill available space
        self.initiative_table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # Set column count and headers - adding Max HP column
        self.initiative_table.setColumnCount(8)
        self.initiative_table.setHorizontalHeaderLabels([
            "Name", "Init", "HP", "Max HP", "AC", "Status", "Conc", "Type"
        ])
        
        # Configure header and column properties
        header = self.initiative_table.horizontalHeader()
        header.setVisible(True)  # Ensure header is always visible
        header.setSectionResizeMode(0, QHeaderView.Stretch)  # Name stretches
        
        # Set reasonable default column widths
        default_widths = [150, 40, 50, 50, 40, 100, 40, 60]
        for col, width in enumerate(default_widths):
            self.initiative_table.setColumnWidth(col, width)
            
        # Set other header sections to resize to content
        for col in range(1, 8):
            header.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        
        # Configure selection behavior
        self.initiative_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.initiative_table.setSelectionMode(QTableWidget.SingleSelection)
        
        # Enable sorting
        self.initiative_table.setSortingEnabled(False)  # We'll handle sorting manually
        
        # Connect signals
        self.initiative_table.cellChanged.connect(self._handle_cell_changed)
        self.initiative_table.cellDoubleClicked.connect(self._view_combatant_details)
        self.initiative_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.initiative_table.customContextMenuRequested.connect(self._show_context_menu)
        
        combat_layout.addWidget(self.initiative_table)
        
        # --- Add Combatant Area ---
        add_combatant_layout = self._setup_add_combatant_controls()
        combat_layout.addLayout(add_combatant_layout)
        
        # Add combat tracker widget to splitter
        self.main_splitter.addWidget(combat_tracker_widget)
        
        # --- Combatant Details Area ---
        self.details_widget = QWidget()
        self.details_layout = QVBoxLayout(self.details_widget)
        self.details_layout.setContentsMargins(0, 0, 0, 0)
        
        # Header area with title and toggle button
        details_header = QHBoxLayout()
        self.details_title = QLabel("Combatant Details")
        self.details_title.setStyleSheet("font-weight: bold; font-size: 14px;")
        details_header.addWidget(self.details_title)
        
        details_header.addStretch()
        
        self.toggle_details_btn = QPushButton("Show Details")
        self.toggle_details_btn.setCheckable(True)
        self.toggle_details_btn.setChecked(False)
        self.toggle_details_btn.clicked.connect(self._toggle_details_pane)
        details_header.addWidget(self.toggle_details_btn)
        
        self.details_layout.addLayout(details_header)
        
        # Details content area
        self.details_content = QScrollArea()
        self.details_content.setWidgetResizable(True)
        self.details_content.setFrameShape(QFrame.StyledPanel)
        
        # Widget to contain actual stats
        self.stats_widget = QWidget()
        self.stats_layout = QVBoxLayout(self.stats_widget)
        
        # Add component sections for the stats
        # Basic Info
        self.basic_info_group = QGroupBox("Basic Info")
        basic_info_layout = QFormLayout(self.basic_info_group)
        
        self.name_label = QLabel("")
        basic_info_layout.addRow("Name:", self.name_label)
        
        self.type_label = QLabel("")
        basic_info_layout.addRow("Type:", self.type_label)
        
        self.ac_details_label = QLabel("")
        basic_info_layout.addRow("AC:", self.ac_details_label)
        
        self.hp_details_label = QLabel("")
        basic_info_layout.addRow("HP:", self.hp_details_label)
        
        self.speed_label = QLabel("")
        basic_info_layout.addRow("Speed:", self.speed_label)
        
        self.stats_layout.addWidget(self.basic_info_group)
        
        # Ability Scores
        self.abilities_group = QGroupBox("Ability Scores")
        abilities_layout = QHBoxLayout(self.abilities_group)
        
        self.str_label = QLabel("STR\n-")
        self.str_label.setAlignment(Qt.AlignCenter)
        abilities_layout.addWidget(self.str_label)
        
        self.dex_label = QLabel("DEX\n-")
        self.dex_label.setAlignment(Qt.AlignCenter)
        abilities_layout.addWidget(self.dex_label)
        
        self.con_label = QLabel("CON\n-")
        self.con_label.setAlignment(Qt.AlignCenter)
        abilities_layout.addWidget(self.con_label)
        
        self.int_label = QLabel("INT\n-")
        self.int_label.setAlignment(Qt.AlignCenter)
        abilities_layout.addWidget(self.int_label)
        
        self.wis_label = QLabel("WIS\n-")
        self.wis_label.setAlignment(Qt.AlignCenter)
        abilities_layout.addWidget(self.wis_label)
        
        self.cha_label = QLabel("CHA\n-")
        self.cha_label.setAlignment(Qt.AlignCenter)
        abilities_layout.addWidget(self.cha_label)
        
        self.stats_layout.addWidget(self.abilities_group)
        
        # Actions & Features Tab Widget
        self.actions_tab = QTabWidget()
        
        # Actions tab
        self.actions_widget = QWidget()
        self.actions_layout = QVBoxLayout(self.actions_widget)
        self.actions_layout.setContentsMargins(5, 5, 5, 5)
        self.actions_tab.addTab(self.actions_widget, "Actions")
        
        # Features/traits tab
        self.traits_widget = QWidget()
        self.traits_layout = QVBoxLayout(self.traits_widget)
        self.traits_layout.setContentsMargins(5, 5, 5, 5)
        self.actions_tab.addTab(self.traits_widget, "Features")
        
        # Spells tab
        self.spells_widget = QWidget()
        self.spells_layout = QVBoxLayout(self.spells_widget)
        self.spells_layout.setContentsMargins(5, 5, 5, 5)
        self.actions_tab.addTab(self.spells_widget, "Spells")
        
        self.stats_layout.addWidget(self.actions_tab)
        
        # Set the stats widget as the content of the scroll area
        self.details_content.setWidget(self.stats_widget)
        self.details_layout.addWidget(self.details_content)
        
        # Add details widget to splitter but hide initially
        self.main_splitter.addWidget(self.details_widget)
        self.details_widget.hide()
        
        # Add the splitter to the main layout
        main_layout.addWidget(self.main_splitter)
        
        # Initialize UI components
        self.initiative_table.setMinimumHeight(200)
        
        # Connect signals
        self.initiative_table.itemSelectionChanged.connect(self._on_selection_changed)
        
        # Create keyboard shortcuts
        QAction("Next Turn", self, triggered=self._next_turn, shortcut=QKeySequence("N")).setShortcutContext(Qt.WidgetWithChildrenShortcut)
        self.addAction(QAction("Next Turn", self, triggered=self._next_turn, shortcut=QKeySequence("N")))
        
        # Set table stretch 
        self.main_splitter.setStretchFactor(0, 3)  # Combat tracker gets 3 parts
        self.main_splitter.setStretchFactor(1, 2)  # Details gets 2 parts
        
        # Initialize the table
        self._update_highlight()
    
    def _setup_control_area(self):
        """Set up the combat control area"""
        control_layout = QHBoxLayout()
        
        # Combat info group
        combat_info = QGroupBox("Combat Info")
        info_layout = QHBoxLayout()
        
        # Round counter
        round_layout = QVBoxLayout()
        round_layout.addWidget(QLabel("Round:"))
        self.round_spin = QSpinBox()
        self.round_spin.setMinimum(1)
        self.round_spin.setValue(self.current_round)
        self.round_spin.valueChanged.connect(self._round_changed)
        round_layout.addWidget(self.round_spin)
        info_layout.addLayout(round_layout)
        
        # Combat duration
        duration_layout = QVBoxLayout()
        duration_layout.addWidget(QLabel("Duration:"))
        duration_widget = QWidget()
        duration_inner = QHBoxLayout()
        
        self.timer_label = QLabel("00:00:00")
        duration_inner.addWidget(self.timer_label)
        
        self.timer_button = QPushButton("Start")
        self.timer_button.clicked.connect(self._toggle_timer)
        duration_inner.addWidget(self.timer_button)
        
        duration_widget.setLayout(duration_inner)
        duration_layout.addWidget(duration_widget)
        info_layout.addLayout(duration_layout)
        
        # In-game time
        game_time_layout = QVBoxLayout()
        game_time_layout.addWidget(QLabel("In-Game Time:"))
        self.game_time_label = QLabel("0 rounds (0 minutes)")
        game_time_layout.addWidget(self.game_time_label)
        info_layout.addLayout(game_time_layout)
        
        combat_info.setLayout(info_layout)
        control_layout.addWidget(combat_info)
        
        control_layout.addStretch(1)
        
        # Next combatant button (previously Next Turn)
        self.next_turn_button = QPushButton("Next Combatant")
        self.next_turn_button.clicked.connect(self._next_turn)
        control_layout.addWidget(self.next_turn_button)

        # Add Fast Resolve button
        self.fast_resolve_button = QPushButton("Fast Resolve")
        self.fast_resolve_button.setToolTip("Resolve the current combat using AI (Experimental)")
        self.fast_resolve_button.clicked.connect(self._fast_resolve_combat)
        control_layout.addWidget(self.fast_resolve_button)

        # Reset Combat button
        self.reset_button = QPushButton("Reset Combat")
        self.reset_button.clicked.connect(self._reset_combat)
        control_layout.addWidget(self.reset_button)
        
        # Restart Combat button
        self.restart_button = QPushButton("Restart Combat")
        self.restart_button.clicked.connect(self._restart_combat)
        control_layout.addWidget(self.restart_button)
        
        return control_layout
    
    def _setup_add_combatant_controls(self):
        """Set up the controls for adding new combatants"""
        add_layout = QHBoxLayout()
        
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Name")
        add_layout.addWidget(self.name_input)
        
        init_layout = QHBoxLayout()
        self.initiative_input = QSpinBox()
        self.initiative_input.setRange(-20, 30)  # Allow for negative initiative
        self.initiative_input.setPrefix("Init: ")
        init_layout.addWidget(self.initiative_input)
        
        # Add quick roll button
        roll_init_button = QPushButton("🎲")
        roll_init_button.setToolTip("Roll initiative (1d20)")
        roll_init_button.clicked.connect(self._roll_initiative)
        roll_init_button.setMaximumWidth(30)
        init_layout.addWidget(roll_init_button)
        
        init_widget = QWidget()
        init_widget.setLayout(init_layout)
        add_layout.addWidget(init_widget)
        
        self.hp_input = QSpinBox()
        self.hp_input.setRange(1, 999)
        self.hp_input.setPrefix("HP: ")
        add_layout.addWidget(self.hp_input)
        
        self.ac_input = QSpinBox()
        self.ac_input.setRange(0, 30)
        self.ac_input.setPrefix("AC: ")
        add_layout.addWidget(self.ac_input)
        
        # Add modifier input for initiative
        self.init_mod_input = QSpinBox()
        self.init_mod_input.setRange(-10, 10)
        self.init_mod_input.setPrefix("Init Mod: ")
        self.init_mod_input.setValue(0)
        add_layout.addWidget(self.init_mod_input)
        
        # Create Add button with new connection approach
        add_button = QPushButton("Add Manual Combatant")
        add_button.clicked.connect(self._handle_add_click)
        add_layout.addWidget(add_button)
        
        return add_layout
    
    def _handle_add_click(self):
        """Handle the Add button click to add a new combatant from form fields"""
        try:
            name = self.name_input.text().strip()
            if not name:
                # Don't add combatants without a name
                QMessageBox.warning(self, "Missing Name", "Please enter a name for the combatant.")
                return
            
            # Get values from input fields
            initiative = self.initiative_input.value()
            hp = self.hp_input.value()
            max_hp = hp  # Set max_hp to same as current hp for manually added combatants
            ac = self.ac_input.value()
            
            # Add the combatant (no specific type for manual adds)
            row = self._add_combatant(name, initiative, hp, max_hp, ac, "manual")
            
            # Only reset fields and log if the add was successful
            if row >= 0:
                # Reset fields for next entry (except initiative modifier)
                self.name_input.clear()
                self.initiative_input.setValue(0)
                
                # Log to combat log
                self._log_combat_action("Setup", "DM", "added manual combatant", name, f"(Initiative: {initiative})")
                
                return row
            else:
                QMessageBox.warning(self, "Add Failed", f"Failed to add {name} to the combat tracker.")
                return -1
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"An error occurred adding the combatant: {str(e)}")
            return -1
    
    def _add_combatant(self, name, initiative, hp, max_hp, ac, combatant_type=""):
        """Add a combatant to the initiative table"""
        print(f"[CombatTracker] _add_combatant called: name={name}, initiative={initiative}, hp={hp}, max_hp={max_hp}, ac={ac}, type={combatant_type}")
        
        # Get current row count
        row = self.initiative_table.rowCount()
        self.initiative_table.insertRow(row)
        
        # Create name item with combatant type stored in user role
        name_item = QTableWidgetItem(name)
        name_item.setData(Qt.UserRole, combatant_type)  # Store type with the name item
        # Ensure no checkbox
        name_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
        self.initiative_table.setItem(row, 0, name_item)
        
        # Set initiative
        init_item = QTableWidgetItem(str(initiative))
        init_item.setData(Qt.DisplayRole, initiative)  # For sorting
        init_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
        self.initiative_table.setItem(row, 1, init_item)
        
        # Set current HP - Make extra sure we're dealing with valid values
        hp_str = str(hp) if hp is not None else "10"
        print(f"[CombatTracker] Setting HP for {name} to {hp_str}")
        hp_item = QTableWidgetItem(hp_str)
        hp_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
        self.initiative_table.setItem(row, 2, hp_item)
        
        # Set Max HP - Make extra sure we're dealing with valid values
        max_hp_str = str(max_hp) if max_hp is not None else "10"
        print(f"[CombatTracker] Setting Max HP for {name} to {max_hp_str}")
        max_hp_item = QTableWidgetItem(max_hp_str)
        max_hp_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
        self.initiative_table.setItem(row, 3, max_hp_item)
        
        # Set AC
        ac_str = str(ac) if ac is not None else "10"
        ac_item = QTableWidgetItem(ac_str)
        ac_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
        self.initiative_table.setItem(row, 4, ac_item)
        
        # Set status as empty initially
        status_item = QTableWidgetItem("")
        status_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
        self.initiative_table.setItem(row, 5, status_item)
        
        # Set concentration as unchecked initially - only column with checkbox
        conc_item = QTableWidgetItem()
        conc_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
        conc_item.setCheckState(Qt.Unchecked)
        self.initiative_table.setItem(row, 6, conc_item)
        
        # Set type (monster, character, etc.) for filtering
        type_item = QTableWidgetItem(combatant_type)
        type_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
        self.initiative_table.setItem(row, 7, type_item)
        
        # Sort the initiative order
        self._sort_initiative()
        
        # Verify the final result
        final_hp_item = self.initiative_table.item(row, 2)
        if final_hp_item:
            final_hp = final_hp_item.text()
            print(f"[CombatTracker] Final verification - {name} HP after sorting: {final_hp}")
        
        # Return the row where the combatant was added
        return row
    
    def _sort_initiative(self):
        """Sort the initiative list in descending order."""
        print(f"[CombatTracker] _sort_initiative ENTRY with {self.initiative_table.rowCount()} rows")
        # Block signals to prevent recursive calls during sorting
        self.initiative_table.blockSignals(True)
        
        try:
            # Get the number of rows
            row_count = self.initiative_table.rowCount()
            if row_count <= 1:
                # Nothing to sort if there's 0 or 1 row
                print("[CombatTracker] _sort_initiative: Nothing to sort (≤1 row)")
                return
            
            # Store all row data before clearing
            rows_data = []
            initiative_values = []
            
            # Store pre-sort HP and AC data for verification
            pre_sort_values = {}
            for row in range(row_count):
                name_item = self.initiative_table.item(row, 0)
                hp_item = self.initiative_table.item(row, 2)
                ac_item = self.initiative_table.item(row, 4)
                
                name = name_item.text() if name_item else f"Row {row}"
                hp = hp_item.text() if hp_item else "?"
                ac = ac_item.text() if ac_item else "?"
                
                pre_sort_values[name] = {"hp": hp, "ac": ac}
            
            # Collect all the data from the table first
            print(f"[CombatTracker] Collecting data from {row_count} rows")
            for row in range(row_count):
                # Get the initiative value and row number
                initiative_item = self.initiative_table.item(row, 1)
                if initiative_item and initiative_item.text():
                    try:
                        initiative = int(initiative_item.text())
                    except (ValueError, TypeError):
                        initiative = 0
                else:
                    initiative = 0
                    
                # Gather all row data
                row_data = {}
                for col in range(self.initiative_table.columnCount()):
                    item = self.initiative_table.item(row, col)
                    if item:
                        row_data[col] = {
                            'text': item.text(),
                            'data': item.data(Qt.UserRole),
                            'checkState': item.checkState() if col == 6 else None,  # Only save checkState for concentration column
                            'currentTurn': item.data(Qt.UserRole + 1)
                        }
                        
                # Add this row's data to our collection
                rows_data.append(row_data)
                initiative_values.append((initiative, row))
                hp_value = row_data.get(2, {}).get('text', '?')
                ac_value = row_data.get(4, {}).get('text', '?')
                print(f"[CombatTracker] Row {row}: initiative={initiative}, hp={hp_value}, ac={ac_value}")
            
            # Sort the initiative values in descending order
            initiative_values.sort(key=lambda x: x[0], reverse=True)
            print(f"[CombatTracker] Sorted initiatives: {initiative_values}")
            
            # Remap original rows to their new position after sorting
            row_map = {old_row: new_row for new_row, (_, old_row) in enumerate(initiative_values)}
            print(f"[CombatTracker] Row mapping: {row_map}")
            
            # Remember the current selection and turn
            current_row = self.initiative_table.currentRow()
            current_turn = self._current_turn if hasattr(self, '_current_turn') else None
            print(f"[CombatTracker] Before sort: current_row={current_row}, current_turn={current_turn}")
            
            # Clear the table (but don't update combat stats yet)
            print("[CombatTracker] Clearing table and rebuilding with sorted data")
            self.initiative_table.setRowCount(0)
            self.initiative_table.setRowCount(row_count)
            
            # Add the sorted rows back to the table
            for old_row, new_row in row_map.items():
                row_data = rows_data[old_row]
                print(f"[CombatTracker] Moving row {old_row} to position {new_row}")
                
                # Debug HP and AC for this row
                hp_value = row_data.get(2, {}).get('text', '?')
                ac_value = row_data.get(4, {}).get('text', '?')
                print(f"[CombatTracker] Moving HP value: {hp_value} from old_row={old_row} to new_row={new_row}")
                print(f"[CombatTracker] Moving AC value: {ac_value} from old_row={old_row} to new_row={new_row}")
                
                for col, item_data in row_data.items():
                    # Create a new item with the right flags for each column
                    new_item = QTableWidgetItem()
                    
                    # Set text data
                    if 'text' in item_data:
                        new_item.setText(item_data['text'])
                    
                    # Set appropriate flags based on column - ENSURE ONLY CONCENTRATION HAS CHECKBOXES
                    if col == 6:  # Concentration column - the only one with checkboxes
                        new_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
                        if 'checkState' in item_data and item_data['checkState'] is not None:
                            new_item.setCheckState(item_data['checkState'])
                        else:
                            new_item.setCheckState(Qt.Unchecked)
                    elif col == 0:  # Name column - should be editable
                        new_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
                    elif col == 1:  # Initiative column - should be editable
                        new_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
                    elif col == 2:  # HP column - should be editable
                        new_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
                    elif col == 3:  # Max HP column - should be editable
                        new_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
                    elif col == 4:  # AC column - should be editable
                        new_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
                    elif col == 5:  # Status column - should be editable
                        new_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
                    else:  # Any other columns - make selectable but not editable by default
                        new_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                    
                    # Restore UserRole data (like combatant type)
                    if 'data' in item_data and item_data['data'] is not None:
                        new_item.setData(Qt.UserRole, item_data['data'])
                    
                    # Restore current turn highlight data
                    if 'currentTurn' in item_data and item_data['currentTurn'] is not None:
                        new_item.setData(Qt.UserRole + 1, item_data['currentTurn'])
                    
                    # Set the item in the table
                    self.initiative_table.setItem(new_row, col, new_item)
            
            # Update current selection and turn if needed
            if current_row >= 0 and current_row < row_count:
                new_current_row = row_map.get(current_row, 0)
                print(f"[CombatTracker] Setting current cell: {new_current_row}")
                self.initiative_table.setCurrentCell(new_current_row, 0)
            
            
            if current_turn is not None and current_turn >= 0 and current_turn < row_count:
                self._current_turn = row_map.get(current_turn, 0)
                print(f"[CombatTracker] Setting current turn to: {self._current_turn}")
            
            # Verify HP and AC values after sorting
            post_sort_values = {}
            for row in range(row_count):
                name_item = self.initiative_table.item(row, 0)
                hp_item = self.initiative_table.item(row, 2)
                ac_item = self.initiative_table.item(row, 4)
                
                name = name_item.text() if name_item else f"Row {row}"
                hp = hp_item.text() if hp_item else "?"
                ac = ac_item.text() if ac_item else "?"
                
                post_sort_values[name] = {"hp": hp, "ac": ac}
            
            # Compare pre and post sort values
            for name, pre_values in pre_sort_values.items():
                post_values = post_sort_values.get(name, {"hp": "MISSING", "ac": "MISSING"})
                
                # Check HP
                pre_hp = pre_values["hp"]
                post_hp = post_values["hp"]
                if pre_hp != post_hp:
                    print(f"[CombatTracker] WARNING: HP changed during sort for {name}: {pre_hp} -> {post_hp}")
                else:
                    print(f"[CombatTracker] HP preserved for {name}: {pre_hp}")
                
                # Check AC
                pre_ac = pre_values["ac"]
                post_ac = post_values["ac"]
                if pre_ac != post_ac:
                    print(f"[CombatTracker] WARNING: AC changed during sort for {name}: {pre_ac} -> {post_ac}")
                else:
                    print(f"[CombatTracker] AC preserved for {name}: {pre_ac}")
            
            # Force a UI update - IMPORTANT
            self.initiative_table.viewport().update()
            self.update()  # Update the whole combat tracker panel
        
        except Exception as e:
            print(f"[CombatTracker] ERROR in _sort_initiative: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            # Always unblock signals
            print("[CombatTracker] Unblocking table signals")
            self.initiative_table.blockSignals(False)
            print("[CombatTracker] _sort_initiative completed")
            
            # Force the UI to update one more time
            QApplication.processEvents()  # Process pending events to ensure UI updates
    
    def _quick_damage(self, amount):
        """Apply quick damage to selected combatants"""
        if amount <= 0:
            return
            
        # Get selected rows
        selected_rows = [index.row() for index in 
                        self.initiative_table.selectionModel().selectedRows()]
        
        if not selected_rows:
            if 0 <= self.current_turn < self.initiative_table.rowCount():
                # If no selection, apply to current turn
                selected_rows = [self.current_turn]
            else:
                return
                
        for row in selected_rows:
            hp_item = self.initiative_table.item(row, 2)  # HP is now column 2
            max_hp_item = self.initiative_table.item(row, 3)  # Max HP is column 3
            
            if hp_item:
                try:
                    # Safely get current HP
                    hp_text = hp_item.text().strip()
                    current_hp = int(hp_text) if hp_text else 0
                    max_hp = int(max_hp_item.text()) if max_hp_item and max_hp_item.text() else current_hp
                    
                    new_hp = max(current_hp - amount, 0)
                    hp_item.setText(str(new_hp))
                    
                    # Check for concentration
                    if amount > 0:
                        self._check_concentration(row, amount)
                        
                    # Check for death saves if 0 HP
                    if new_hp == 0:
                        name = self.initiative_table.item(row, 0).text()
                        QMessageBox.information(
                            self,
                            "HP Reduced to 0",
                            f"{name} is down! Remember to track death saves."
                        )
                except ValueError:
                    # Handle invalid HP value
                    pass
    
    def _quick_heal(self, amount):
        """Apply quick healing to selected combatants"""
        if amount <= 0:
            return
            
        # Get selected rows
        selected_rows = [index.row() for index in 
                        self.initiative_table.selectionModel().selectedRows()]
        
        if not selected_rows:
            if 0 <= self.current_turn < self.initiative_table.rowCount():
                # If no selection, apply to current turn
                selected_rows = [self.current_turn]
            else:
                return
                
        for row in selected_rows:
            hp_item = self.initiative_table.item(row, 2)  # HP is now column 2
            max_hp_item = self.initiative_table.item(row, 3)  # Max HP is column 3
            
            if hp_item and max_hp_item:
                try:
                    # Safely get current HP
                    hp_text = hp_item.text().strip()
                    current_hp = int(hp_text) if hp_text else 0
                    
                    # Get max HP from the max HP column
                    max_hp_text = max_hp_item.text().strip()
                    max_hp = int(max_hp_text) if max_hp_text else 999
                    
                    new_hp = min(current_hp + amount, max_hp)
                    hp_item.setText(str(new_hp))
                except ValueError:
                    # Handle invalid HP value
                    pass
    
    def _hp_changed(self, row, new_hp):
        """Handle HP changes from delegate editing"""
        if 0 <= row < self.initiative_table.rowCount():
            # Get current HP
            hp_item = self.initiative_table.item(row, 2)  # HP is now column 2
            if hp_item:
                # Already updated via setModelData, check for special cases
                if new_hp == 0:
                    name = self.initiative_table.item(row, 0).text()
                    QMessageBox.information(
                        self,
                        "HP Reduced to 0",
                        f"{name} is down! Remember to track death saves."
                    )
    
    def _initiative_changed(self, row, new_initiative):
        """Handle initiative changes from delegate editing"""
        if 0 <= row < self.initiative_table.rowCount():
            # Log the initiative change
            name = self.initiative_table.item(row, 0).text() if self.initiative_table.item(row, 0) else "Unknown"
            print(f"[CombatTracker] Initiative changed: {name} now has initiative {new_initiative}")
            self._log_combat_action("Initiative", name, "changed initiative", result=f"New value: {new_initiative}")
            
            # Auto-sort the initiative table
            self._sort_initiative()
    
    def _handle_cell_changed(self, row, column):
        """Handle when a cell in the initiative table is changed."""
        # Prevent handling during program-initiated changes
        if self.initiative_table.signalsBlocked():
            return
            
        # Prevent recursive calls
        self.initiative_table.blockSignals(True)
        
        try:
            # Get the updated item
            item = self.initiative_table.item(row, column)
            if not item:
                return
                
            # Handle initiative changes (column 1)
            if column == 1:  # Initiative column
                # Check if the initiative was actually changed
                try:
                    # Convert to int (ignore if not a valid number)
                    new_initiative = int(item.text()) if item.text() else 0
                    
                    # Only sort if we have more than one combatant
                    if self.initiative_table.rowCount() > 1:
                        self._sort_initiative()
                except (ValueError, TypeError):
                    # Not a valid number, reset to 0
                    item.setText("0")
            
            # Handle Max HP changes (column 3)
            elif column == 3:  # Max HP column
                # Update current HP if it's higher than max
                hp_item = self.initiative_table.item(row, 2)
                max_hp_item = self.initiative_table.item(row, 3)
                
                if hp_item and max_hp_item:
                    try:
                        current_hp = int(hp_item.text())
                        max_hp = int(max_hp_item.text())
                        
                        # If current HP is higher than max, cap it
                        if current_hp > max_hp:
                            hp_item.setText(str(max_hp))
                    except (ValueError, TypeError):
                        pass
            
            # Update combatant data if we have a combat data dictionary
            if row in self.combatants:
                # Just update the HP and status to match what's shown in the table
                self._update_combatant_hp_and_status(row)
        
        finally:
            # Always restore signals
            self.initiative_table.blockSignals(False)
    
    def _update_combatant_hp_and_status(self, row):
        """Update the HP and status of a combatant in the data dictionary based on the table"""
        if row not in self.combatants:
            return
            
        # Get HP from table
        hp_item = self.initiative_table.item(row, 2)  # Current HP
        max_hp_item = self.initiative_table.item(row, 3)  # Max HP
        
        if hp_item:
            hp_text = hp_item.text().strip()
            try:
                hp = int(hp_text) if hp_text else 0
                
                # Update the hp in the combatant data if it's a dictionary
                if isinstance(self.combatants[row], dict):
                    self.combatants[row]['current_hp'] = hp
                elif hasattr(self.combatants[row], 'current_hp'):
                    self.combatants[row].current_hp = hp
            except (ValueError, TypeError):
                # Ignore if not a valid number
                pass
        
        # Update max HP if available
        if max_hp_item:
            max_hp_text = max_hp_item.text().strip()
            try:
                max_hp = int(max_hp_text) if max_hp_text else 0
                
                # Update the max_hp in the combatant data if it's a dictionary
                if isinstance(self.combatants[row], dict):
                    self.combatants[row]['max_hp'] = max_hp
                elif hasattr(self.combatants[row], 'max_hp'):
                    self.combatants[row].max_hp = max_hp
            except (ValueError, TypeError):
                # Ignore if not a valid number
                pass
                
        # Get status from table
        status_item = self.initiative_table.item(row, 5)  # Status is now column 5
        if status_item:
            status = status_item.text()
            
            # Update the status in the combatant data if it's a dictionary
            if isinstance(self.combatants[row], dict):
                if 'conditions' not in self.combatants[row]:
                    self.combatants[row]['conditions'] = []
                if status and status not in self.combatants[row]['conditions']:
                    self.combatants[row]['conditions'].append(status)
                elif not status and self.combatants[row]['conditions']:
                    self.combatants[row]['conditions'] = []
            elif hasattr(self.combatants[row], 'conditions'):
                if status and status not in self.combatants[row].conditions:
                    self.combatants[row].conditions.append(status)
                elif not status and self.combatants[row].conditions:
                    self.combatants[row].conditions = []
    
    def _next_turn(self):
        """Move to the next combatant's turn"""
        if self.initiative_table.rowCount() == 0:
            return
        
        # Set combat as started when first advancing turns
        if not self.combat_started:
            self.combat_started = True
        
        # Store the index of the last combatant
        last_combatant_index = self.initiative_table.rowCount() - 1
        
        # Check if the current turn is the last combatant
        if self.current_turn == last_combatant_index:
            # End of the round: Increment round, reset turn to 0
            self.current_turn = 0
            self.current_round += 1
            self.round_spin.setValue(self.current_round)
            self._update_game_time()
            print(f"--- End of Round {self.current_round - 1}, Starting Round {self.current_round} ---") # Debug
        else:
            # Not the end of the round: Just advance to the next combatant
            self.current_turn += 1
        
        # Highlight the new current combatant
        self._update_highlight()
        
        # Log the turn change
        if self.initiative_table.rowCount() > 0 and self.current_turn < self.initiative_table.rowCount():
            combatant_name = self.initiative_table.item(self.current_turn, 0).text()
            self._log_combat_action("Initiative", combatant_name, "started their turn")
            
        # If this is the first turn of a new round, log the round start
        if self.current_turn == 0:
            self._log_combat_action("Initiative", f"Round {self.current_round}", "started")
    
    def _update_highlight(self):
        """Update the highlight state using item data and trigger repaint via dataChanged."""
        rows = self.initiative_table.rowCount()
        if rows == 0:
            return

        # Clear the data from the previous turn's row
        if 0 <= self.previous_turn < rows:
            for col in range(self.initiative_table.columnCount()):
                item = self.initiative_table.item(self.previous_turn, col)
                if item:
                    item.setData(Qt.UserRole + 1, False) # Use setData with Boolean False
            # Emit dataChanged for the previous row to trigger delegate repaint
            start_index = self.initiative_table.model().index(self.previous_turn, 0)
            end_index = self.initiative_table.model().index(self.previous_turn, self.initiative_table.columnCount() - 1)
            self.initiative_table.model().dataChanged.emit(start_index, end_index, [Qt.UserRole + 1])

        # Set the data on the current turn's row
        if 0 <= self.current_turn < rows:
            for col in range(self.initiative_table.columnCount()):
                item = self.initiative_table.item(self.current_turn, col)
                if item:
                    item.setData(Qt.UserRole + 1, True) # Use setData with Boolean True
            # Emit dataChanged for the current row to trigger delegate repaint
            start_index = self.initiative_table.model().index(self.current_turn, 0)
            end_index = self.initiative_table.model().index(self.current_turn, self.initiative_table.columnCount() - 1)
            self.initiative_table.model().dataChanged.emit(start_index, end_index, [Qt.UserRole + 1])
            
            # Ensure the current row is visible
            self.initiative_table.scrollToItem(
                self.initiative_table.item(self.current_turn, 0),
                QTableWidget.ScrollHint.EnsureVisible
            )

        # Update the style to reflect property changes. 
        # setProperty should handle this, but polish/unpolish is safer.
        self.initiative_table.style().unpolish(self.initiative_table)
        self.initiative_table.style().polish(self.initiative_table)
        self.initiative_table.viewport().update() 

        # Update previous_turn for the next call
        self.previous_turn = self.current_turn
    
    def _show_context_menu(self, position):
        """Show custom context menu for the initiative table"""
        # Get row under cursor
        row = self.initiative_table.rowAt(position.y())
        if row < 0:
            return
        
        # Create menu
        menu = QMenu(self)
        
        # Add menu actions
        remove_action = QAction("Remove", self)
        remove_action.triggered.connect(self._remove_selected)
        menu.addAction(remove_action)
        
        # View combatant details action
        view_details_action = QAction("View Details", self)
        view_details_action.triggered.connect(lambda: self._view_combatant_details(row))
        menu.addAction(view_details_action)
        
        # Toggle details panel action
        toggle_details_action = QAction("Hide Details Panel" if self.show_details_pane else "Show Details Panel", self)
        toggle_details_action.triggered.connect(self._toggle_details_pane)
        menu.addAction(toggle_details_action)
        menu.addSeparator()
        
        # HP adjustment submenu
        hp_menu = menu.addMenu("Adjust HP")
        
        # Quick damage options
        damage_menu = hp_menu.addMenu("Damage")
        d1_action = damage_menu.addAction("1 HP")
        d1_action.triggered.connect(lambda: self._quick_damage(1))
        d5_action = damage_menu.addAction("5 HP")
        d5_action.triggered.connect(lambda: self._quick_damage(5))
        d10_action = damage_menu.addAction("10 HP")
        d10_action.triggered.connect(lambda: self._quick_damage(10))
        
        damage_custom = damage_menu.addAction("Custom...")
        damage_custom.triggered.connect(lambda: self._apply_damage(False))
        
        # Quick healing options
        heal_menu = hp_menu.addMenu("Heal")
        h1_action = heal_menu.addAction("1 HP")
        h1_action.triggered.connect(lambda: self._quick_heal(1))
        h5_action = heal_menu.addAction("5 HP")
        h5_action.triggered.connect(lambda: self._quick_heal(5))
        h10_action = heal_menu.addAction("10 HP")
        h10_action.triggered.connect(lambda: self._quick_heal(10))
        
        heal_custom = heal_menu.addAction("Custom...")
        heal_custom.triggered.connect(lambda: self._apply_damage(True))
        
        menu.addSeparator()
        
        # Death saves - check for 0 HP safely
        hp_item = self.initiative_table.item(row, 2)  # HP is now column 2
        hp_value = 0
        if hp_item:
            try:
                hp_text = hp_item.text().strip()
                if hp_text:  # Only try to convert if not empty
                    hp_value = int(hp_text)
            except ValueError:
                hp_value = 0  # Default to 0 if conversion fails
        
        if hp_value <= 0:
            death_saves = QAction("Death Saves...", self)
            death_saves.triggered.connect(lambda: self._manage_death_saves(row))
            menu.addAction(death_saves)
            menu.addSeparator()
        
        # Status submenu
        status_menu = menu.addMenu("Set Status")
        status_menu.addAction("None").triggered.connect(lambda: self._set_status(""))
        
        for condition in CONDITIONS:
            action = status_menu.addAction(condition)
            action.triggered.connect(lambda checked, c=condition: self._set_status(c))
        
        # Concentration toggle
        conc_item = self.initiative_table.item(row, 6)  # Concentration is now column 6
        if conc_item:
            is_concentrating = conc_item.checkState() == Qt.Checked
            conc_action = QAction("Remove Concentration" if is_concentrating else "Add Concentration", self)
            conc_action.triggered.connect(lambda: self._toggle_concentration(row))
            menu.addAction(conc_action)
        
        # Show the menu
        menu.exec_(self.initiative_table.mapToGlobal(position))
        
    def _toggle_concentration(self, row):
        """Toggle concentration state for a combatant"""
        conc_item = self.initiative_table.item(row, 6)  # Concentration is now column 6
        if conc_item:
            # Toggle check state
            current_state = conc_item.checkState()
            new_state = Qt.Unchecked if current_state == Qt.Checked else Qt.Checked
            conc_item.setCheckState(new_state)
            
            # Update tracking set
            if new_state == Qt.Checked:
                self.concentrating.add(row)
            else:
                self.concentrating.discard(row)
                
            # Log concentration change
            name_item = self.initiative_table.item(row, 0)
            if name_item:
                name = name_item.text()
                if new_state == Qt.Checked:
                    self._log_combat_action("Status Effect", name, "began concentrating")
                else:
                    self._log_combat_action("Status Effect", name, "ended concentration")
    
    def _apply_damage(self, is_healing=False):
        """Apply damage or healing to selected combatants"""
        # Get selected rows
        selected_rows = set(index.row() for index in self.initiative_table.selectedIndexes())
        if not selected_rows:
            return
            
        # Get name of first selected combatant for dialog
        first_row = min(selected_rows)
        name_item = self.initiative_table.item(first_row, 0)
        target_name = name_item.text() if name_item else "combatant"
        
        # Open damage/healing dialog
        dialog = DamageDialog(self, is_healing=is_healing)
        if dialog.exec_():
            amount = dialog.get_amount()
            
            # Apply to each selected row
            for row in selected_rows:
                hp_item = self.initiative_table.item(row, 2)  # HP is now column 2
                max_hp_item = self.initiative_table.item(row, 3)  # Max HP is now column 3
                if not hp_item or not max_hp_item:
                    continue
                    
                name_item = self.initiative_table.item(row, 0)
                if not name_item:
                    continue
                    
                combatant_name = name_item.text()
                
                try:
                    # Safely get current HP
                    hp_text = hp_item.text().strip()
                    current_hp = int(hp_text) if hp_text else 0
                    
                    # Get max HP
                    max_hp_text = max_hp_item.text().strip()
                    max_hp = int(max_hp_text) if max_hp_text else 999
                    
                    if is_healing:
                        new_hp = current_hp + amount
                        if max_hp > 0:  # Don't exceed max HP
                            new_hp = min(new_hp, max_hp)
                        
                        # Log healing action
                        self._log_combat_action(
                            "Healing", 
                            "DM", 
                            "healed", 
                            combatant_name, 
                            f"{amount} HP (to {new_hp})"
                        )
                    else:
                        new_hp = current_hp - amount
                        
                        # Check concentration if damaged
                        if row in self.concentrating and amount > 0:
                            self._check_concentration(row, amount)
                        
                        # Log damage action
                        self._log_combat_action(
                            "Damage", 
                            "DM", 
                            "dealt damage to", 
                            combatant_name, 
                            f"{amount} damage (to {new_hp})"
                        )
                    
                    # Update HP
                    hp_item.setText(str(new_hp))
                    
                    # Check for unconsciousness/death
                    if new_hp <= 0:
                        # Mark as unconscious
                        status_item = self.initiative_table.item(row, 5)  # Status is now column 5
                        if status_item:
                            old_status = status_item.text()
                            status_item.setText("Unconscious")
                            
                            if old_status != "Unconscious":
                                # Log status change
                                self._log_combat_action(
                                    "Status Effect", 
                                    "DM", 
                                    "applied status", 
                                    combatant_name, 
                                    "Unconscious"
                                )
                        
                        
                        # Check if player character (has max HP) for death saves
                        if max_hp > 0:
                            # Set up death saves tracking if not already
                            if row not in self.death_saves:
                                self.death_saves[row] = {"successes": 0, "failures": 0}
                except ValueError:
                    # Handle invalid HP value
                    pass
    
    def _check_concentration(self, row, damage):
        """Check if a combatant needs to make a concentration save"""
        if row not in self.concentrating:
            return

        # Get combatant name
        name_item = self.initiative_table.item(row, 0)
        if not name_item:
            return
        
        combatant_name = name_item.text()
            
        # Calculate DC for concentration check
        dc = max(10, damage // 2)
        
        # Create and show concentration check dialog
        dialog = ConcentrationDialog(self, combatant_name, dc)
        if dialog.exec_():
            save_result = dialog.get_save_result()
            passed = save_result >= dc
            
            # Log result of concentration check
            outcome = "passed" if passed else "failed"
            self._log_combat_action(
                "Concentration Check", 
                combatant_name, 
                outcome,
                f"DC {dc} concentration check",
                f"(rolled {save_result})"
            )
            
            # If failed, remove concentration
            if not passed:
                # Remove concentration
                concentration_item = self.initiative_table.item(row, 6)  # Concentration is now column 6
                if concentration_item:
                    concentration_item.setCheckState(Qt.Unchecked)
                
                # Remove from concentrating list
                if row in self.concentrating:
                    self.concentrating.remove(row)
                    
                # Log concentration broken
                self._log_combat_action(
                    "Effect Ended", 
                    combatant_name, 
                    "lost concentration",
                    "", ""
                )
    
    def _manage_death_saves(self, row):
        """Manage death saving throws for a character"""
        current_saves = self.death_saves.get(row, {"successes": 0, "failures": 0})
        dialog = DeathSavesDialog(self, current_saves)
        
        if dialog.exec_():
            dialog_result = dialog.get_saves()
            self.death_saves[row] = dialog_result
            saves = self.death_saves[row]
            
            name_item = self.initiative_table.item(row, 0)
            if name_item:
                name = name_item.text()
                
                # Log death save changes
                if saves:
                    successes = saves.get("successes", 0)
                    failures = saves.get("failures", 0)
                    
                    if successes >= 3:
                        self._log_combat_action(
                            "Death Save", 
                            name, 
                            "stabilized", 
                            result=f"{successes} successes"
                        )
                        QMessageBox.information(self, "Stabilized", 
                            f"{name} has stabilized!")
                        self.death_saves.pop(row)
                        
                        # Update status to stable
                        status_item = self.initiative_table.item(row, 4)
                        if status_item:
                            status_item.setText("Stable")
                            
                    elif failures >= 3:
                        self._log_combat_action(
                            "Death Save", 
                            name, 
                            "failed death saves", 
                            result=f"{failures} failures"
                        )
                        QMessageBox.warning(self, "Death", 
                            f"{name} has died!")
                        self.death_saves.pop(row)
                        
                        # Update status to dead
                        status_item = self.initiative_table.item(row, 4)
                        if status_item:
                            status_item.setText("Dead")
                    else:
                        self._log_combat_action(
                            "Death Save", 
                            name, 
                            "updated death saves", 
                            result=f"{successes} successes, {failures} failures"
                        )
    
    def _set_status(self, status):
        """Apply a status condition to selected combatants"""
        # Get selected rows
        selected_rows = set(index.row() for index in self.initiative_table.selectedIndexes())
        if not selected_rows:
            return
        
        # Apply status to each selected row
        for row in selected_rows:
            if row < self.initiative_table.rowCount():
                status_item = self.initiative_table.item(row, 5)  # Status is now column 5
                if status_item:
                    status_item.setText(status)
                
                # Log status change if there's a name
                name_item = self.initiative_table.item(row, 0)
                if name_item:
                    name = name_item.text()
                    
                    # Log status change
                    self._log_combat_action(
                        "Status Effect", 
                        "DM", 
                        "applied status", 
                        name, 
                        status
                    )
    
    def _round_changed(self, value):
        """Handle round number change"""
        self.current_round = value
        self._update_game_time()
    
    def _toggle_timer(self):
        """Toggle the combat timer"""
        if self.timer.isActive():
            self.timer.stop()
            self.timer_button.setText("Start")
        else:
            self.timer.start()  # Update every second
            self.timer_button.setText("Stop")
    
    def _update_timer(self):
        """Update the combat timer display"""
        self.combat_time += 1
        hours = self.combat_time // 3600
        minutes = (self.combat_time % 3600) // 60
        seconds = self.combat_time % 60
        self.timer_label.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
    
    def _roll_initiative(self):
        """Roll initiative for the current combatant"""
        from random import randint
        modifier = self.init_mod_input.value()
        roll = randint(1, 20)
        total = roll + modifier
        self.initiative_input.setValue(total)
        
        # Show roll details
        QMessageBox.information(
            self,
            "Initiative Roll",
            f"Roll: {roll}\nModifier: {modifier:+d}\nTotal: {total}"
        )
        
        # Log the initiative roll if a name is entered
        name = self.name_input.text()
        if name:
            self._log_combat_action(
                "Initiative", 
                name, 
                "rolled initiative", 
                result=f"{roll} + {modifier} = {total}"
            )
    
    def _update_game_time(self):
        """Update the in-game time display"""
        # In D&D 5e, a round is 6 seconds
        total_seconds = (self.current_round - 1) * 6
        minutes = total_seconds // 60
        self.game_time_label.setText(
            f"{self.current_round - 1} rounds ({minutes} minutes)"
        )
    
    def _reset_combat(self):
        """Reset the entire combat tracker to its initial state."""
        # Log combat reset
        self._log_combat_action(
            "Other", 
            "DM", 
            "reset combat", 
            result="Combat tracker reset to initial state"
        )
        
        reply = QMessageBox.question(
            self,
            'Reset Combat',
            "Are you sure you want to reset the combat tracker? \nThis will clear all combatants and reset the round/timer.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Clear the table
            self.initiative_table.setRowCount(0)
            
            # Reset combat state variables
            self.current_round = 1
            self.current_turn = 0
            self.previous_turn = -1
            self.combat_time = 0
            self.combat_started = False
            self.death_saves.clear()
            self.concentrating.clear()
            
            # Reset UI elements
            self.round_spin.setValue(self.current_round)
            if self.timer.isActive():
                self.timer.stop()
            self.timer_label.setText("00:00:00")
            self.timer_button.setText("Start")
            self._update_game_time()
    
    def _restart_combat(self):
        """Restart the current combat (reset turn/round counter but keep combatants)."""
        # Log combat restart
        self._log_combat_action(
            "Other", 
            "DM", 
            "restarted combat", 
            result="Combat restarted with same combatants"
        )
        
        if self.initiative_table.rowCount() == 0:
            QMessageBox.information(self, "Restart Combat", "No combatants to restart.")
            return
            
        reply = QMessageBox.question(
            self,
            'Restart Combat',
            "Are you sure you want to restart the combat? \nThis will reset HP, status, round, and timer, but keep all combatants.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Reset combat state variables
            self.current_round = 1
            self.current_turn = 0
            self.previous_turn = -1
            self.combat_time = 0
            self.combat_started = False
            self.death_saves.clear()
            self.concentrating.clear()
            
            # Reset UI elements
            self.round_spin.setValue(self.current_round)
            if self.timer.isActive():
                self.timer.stop()
            self.timer_label.setText("00:00:00")
            self.timer_button.setText("Start")
            self._update_game_time()
            
            # Reset combatant state in the table
            for row in range(self.initiative_table.rowCount()):
                # Reset HP to max
                hp_item = self.initiative_table.item(row, 2)
                if hp_item:
                    max_hp = hp_item.data(Qt.UserRole)
                    if max_hp:
                        hp_item.setText(str(max_hp))
                    else: # Fallback if max_hp wasn't stored
                        hp_item.setText("1") 
                        
                # Clear status
                status_item = self.initiative_table.item(row, 4)
                if status_item:
                    status_item.setText("")
                    
                # Reset concentration
                conc_item = self.initiative_table.item(row, 5)
                if conc_item:
                    conc_item.setCheckState(Qt.Unchecked)
            
            # Re-sort based on original initiative (just in case)
            # And update highlight to the first combatant
            self._sort_initiative()
    
    def _fast_resolve_combat(self):
        """Use LLM to resolve the current combat encounter."""
        # Log fast resolve request
        self._log_combat_action(
            "Other", 
            "DM", 
            "requested fast combat resolution"
        )
        
        # Check if combat resolver is available
        if not hasattr(self.app_state, 'combat_resolver'):
            QMessageBox.warning(self, "Error", "Combat Resolver service not available.")
            return

        # Gather current combat state
        combat_state = self._gather_combat_state()
        if not combat_state or not combat_state.get("combatants"):
            QMessageBox.information(self, "Fast Resolve", "No combatants in the tracker to resolve.")
            return
            
        # Disable button while processing
        self.fast_resolve_button.setEnabled(False)
        self.fast_resolve_button.setText("Resolving...")

        # Call the resolver asynchronously
        self.app_state.combat_resolver.resolve_combat_async(
            combat_state,
            self._handle_resolution_result
        )
    
    def _gather_combat_state(self):
        """Gather the current state of the combat from the table."""
        combatants = []
        for row in range(self.initiative_table.rowCount()):
            combatant = {
                "name": self.initiative_table.item(row, 0).text() if self.initiative_table.item(row, 0) else "Unknown",
                "initiative": int(self.initiative_table.item(row, 1).text() or "0") if self.initiative_table.item(row, 1) else 0,
                "hp": int(self.initiative_table.item(row, 2).text() or "0") if self.initiative_table.item(row, 2) else 0,
                "max_hp": self.initiative_table.item(row, 2).data(Qt.UserRole) if self.initiative_table.item(row, 2) else 0,
                "ac": int(self.initiative_table.item(row, 3).text() or "10") if self.initiative_table.item(row, 3) else 10,
                "status": self.initiative_table.item(row, 4).text() if self.initiative_table.item(row, 4) else "",
                "concentration": self.initiative_table.item(row, 5).checkState() == Qt.Checked if self.initiative_table.item(row, 5) else False,
                "notes": self.initiative_table.item(row, 6).text() if self.initiative_table.item(row, 6) else ""
            }
            combatants.append(combatant)
            
        return {
            "round": self.current_round,
            "current_turn_index": self.current_turn,
            "combatants": combatants
        }

    def _handle_resolution_result(self, result, error):
        """Handle the result from the combat resolver (runs in background thread!)."""
        # *** CRITICAL: DO NOT update UI directly here! ***
        # Emit signal to pass data safely to the main GUI thread.
        self.resolution_complete.emit(result, error)

    def _process_resolution_ui(self, result, error):
        """Process the combat resolution result in the main GUI thread."""
        # Re-enable button
        self.fast_resolve_button.setEnabled(True)
        self.fast_resolve_button.setText("Fast Resolve")
        
        if error:
            QMessageBox.critical(self, "Fast Resolve Error", f"Error resolving combat: {error}")
            return
            
        if result:
            # Log resolution result
            narrative = result.get("narrative", "No narrative provided.")
            updates = result.get("updates", [])
            
            self._log_combat_action(
                "Other", 
                "DM", 
                "resolved combat with AI", 
                result=f"Applied {len(updates)} updates"
            )
            
            # Then log each update
            for update in updates:
                name = update.get("name", "Unknown")
                
                if "hp" in update:
                    self._log_combat_action(
                        "Damage" if update["hp"] < 0 else "Healing", 
                        "AI", 
                        "updated HP for", 
                        name, 
                        f"New HP: {update['hp']}"
                    )
                
                if "status" in update:
                    self._log_combat_action(
                        "Status Effect", 
                        "AI", 
                        "applied status to", 
                        name, 
                        update["status"]
                    )
            
            # Apply updates first
            num_removed, update_summary = self._apply_combat_updates(updates)
            
            # Display results in a more informative message box
            summary_text = f"Combat Resolved:\n\n{narrative}\n\nApplied {len(updates)} updates:"
            if update_summary:
                summary_text += "\n" + "\n".join(update_summary)
            if num_removed > 0:
                summary_text += f"\nRemoved {num_removed} combatants."
                
            QMessageBox.information(
                self,
                "Fast Resolve Result",
                summary_text
            )
    
    def _apply_combat_updates(self, updates):
        """Apply updates from the combat resolution to the table.
        
        Returns:
            tuple: (number_of_rows_removed, list_of_summary_strings)
        """
        rows_to_remove = []
        update_summaries = []
        
        for update_index, update in enumerate(updates):
            name_to_find = update.get("name")
            if not name_to_find:
                continue
                
            # Find the row for the combatant
            found_row = -1
            for row in range(self.initiative_table.rowCount()):
                name_item = self.initiative_table.item(row, 0)
                if name_item and name_item.text() == name_to_find:
                    found_row = row
                    break
            
            if found_row != -1:
                # Apply HP update
                if "hp" in update:
                    hp_item = self.initiative_table.item(found_row, 2)
                    if hp_item:
                        old_hp = hp_item.text()
                        new_hp = str(update["hp"])
                        hp_item.setText(new_hp)
                        update_summaries.append(f"- {name_to_find}: HP changed from {old_hp} to {new_hp}")
                        # Handle death/unconscious status if HP reaches 0
                        if update["hp"] <= 0 and "status" not in update:
                            update["status"] = "Unconscious" # Or "Dead"
                        
                # Apply Status update
                if "status" in update:
                    status_item = self.initiative_table.item(found_row, 4)
                    if status_item:
                        old_status = status_item.text()
                        new_status = update["status"]
                        status_item.setText(new_status)
                        if old_status != new_status:
                             update_summaries.append(f"- {name_to_find}: Status changed from '{old_status}' to '{new_status}'")
                        # If status is Dead or Fled, mark for removal
                        if update["status"] in ["Dead", "Fled"]:
                            rows_to_remove.append(found_row)
        
        # Remove combatants marked for removal (in reverse order)
        if rows_to_remove:
            for row in sorted(list(set(rows_to_remove)), reverse=True):
                self.initiative_table.removeRow(row)
                # Adjust current turn if needed
                if row < self.current_turn:
                    self.current_turn -= 1
                elif row == self.current_turn:
                    self._update_highlight()
            
                # Clean up tracking
                self.death_saves.pop(row, None)
                if row in self.concentrating:
                    self.concentrating.remove(row)
            
            # Reset highlight if current turn was removed or index shifted
            self._update_highlight()
        
        return len(rows_to_remove), update_summaries

    def _get_combat_log(self):
        """Get the combat log panel if available"""
        if hasattr(self.app_state, 'panel_manager') and hasattr(self.app_state.panel_manager, 'get_panel_widget'):
            return self.app_state.panel_manager.get_panel_widget("combat_log")
        return None
    
    def _log_combat_action(self, category, actor, action, target=None, result=None, round=None, turn=None):
        """Log a combat action to the combat log if available"""
        combat_log = self._get_combat_log()
        if combat_log:
            combat_log.add_log_entry(
                category, 
                actor, 
                action, 
                target, 
                result, 
                round, 
                turn
            )

    def save_state(self):
        """Save the combat tracker state"""
        state = {
            "round": self.current_round,
            "turn": self.current_turn,
            "elapsed_time": self.combat_time,
            "combatants": [],
            "death_saves": self.death_saves,
            "concentrating": list(self.concentrating)
        }
        
        # Save all combatants
        for row in range(self.initiative_table.rowCount()):
            combatant = {}
            for col, key in enumerate(["name", "initiative", "hp", "ac", "status", "concentration"]):
                item = self.initiative_table.item(row, col)
                if col == 5:  # Concentration
                    combatant[key] = item.checkState() == Qt.Checked if item else False
                else:
                    combatant[key] = item.text() if item else ""
                
                # Save max HP
                if col == 2 and item:
                    combatant["max_hp"] = item.data(Qt.UserRole)
            
            # Save type from column 6
            type_item = self.initiative_table.item(row, 6)
            if type_item:
                combatant["type"] = type_item.text()
            
            # Save any associated combatant data
            if row in self.combatants:
                combatant["data"] = self.combatants[row]
            
            state["combatants"].append(combatant)
        
        return state
    
    def restore_state(self, state):
        """Restore the combat tracker state"""
        if not state:
            return
        
        # Clear existing data
        self.initiative_table.setRowCount(0)
        self.death_saves.clear()
        self.concentrating.clear()
        self.combatants.clear()
        
        # Restore round and turn
        self.current_round = state.get("round", 1)
        self.round_spin.setValue(self.current_round)
        
        self.current_turn = state.get("turn", 0)
        self.combat_time = state.get("elapsed_time", 0)
        self._update_timer()
        
        # Restore death saves and concentration
        self.death_saves = state.get("death_saves", {})
        self.concentrating = set(state.get("concentrating", []))
        
        # Restore combatants
        for idx, combatant in enumerate(state.get("combatants", [])):
            row = self.initiative_table.rowCount()
            self.initiative_table.insertRow(row)
            
            # Store combatant data in combatants dictionary if available
            if "data" in combatant:
                self.combatants[row] = combatant["data"]
            
            # Figure out combatant type
            combatant_type = ""
            if "type" in combatant:
                # Explicit type is provided
                combatant_type = combatant["type"]
            elif "data" in combatant:
                # Try to determine type from data
                data = combatant["data"]
                if isinstance(data, dict):
                    if "monster_id" in data or "size" in data or "challenge_rating" in data:
                        combatant_type = "monster"
                    elif "character_class" in data or "level" in data:
                        combatant_type = "character"
            
            # Restore each field
            name_item = QTableWidgetItem(combatant.get("name", ""))
            name_item.setData(Qt.UserRole, combatant_type)  # Store type with the name item
            name_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
            self.initiative_table.setItem(row, 0, name_item)
            
            # Initiative
            init_item = QTableWidgetItem(str(combatant.get("initiative", "")))
            init_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
            self.initiative_table.setItem(row, 1, init_item)
            
            # Current HP
            hp_item = QTableWidgetItem(str(combatant.get("hp", "")))
            hp_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
            self.initiative_table.setItem(row, 2, hp_item)
            
            # Max HP (stored in combatant or same as current HP)
            max_hp = combatant.get("max_hp", combatant.get("hp", ""))
            max_hp_item = QTableWidgetItem(str(max_hp))
            max_hp_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
            self.initiative_table.setItem(row, 3, max_hp_item)
            
            # AC
            ac_item = QTableWidgetItem(str(combatant.get("ac", "")))
            ac_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
            self.initiative_table.setItem(row, 4, ac_item)
            
            # Status
            status_item = QTableWidgetItem(combatant.get("status", ""))
            status_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
            self.initiative_table.setItem(row, 5, status_item)
            
            # Concentration (checkbox)
            conc_item = QTableWidgetItem()
            conc_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            conc_item.setCheckState(Qt.Checked if combatant.get("concentration", False) else Qt.Unchecked)
            self.initiative_table.setItem(row, 6, conc_item)
            
            # Type
            type_item = QTableWidgetItem(combatant_type)
            type_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
            self.initiative_table.setItem(row, 7, type_item)
            
            print(f"[CombatTracker] Restored combatant {combatant.get('name', 'Unknown')} with type: {combatant_type}")
        
        # Highlight current turn
        self._update_highlight()

    @Slot(list) # Explicitly mark as a slot receiving a list
    def add_combatant_group(self, monster_dicts: list):
        """Add a list of monsters (as dictionaries) to the combat tracker."""
        if not isinstance(monster_dicts, list):
            print(f"[CombatTracker] Error: add_combatant_group received non-list: {type(monster_dicts)}")
            return
            
        print(f"[CombatTracker] Received group of {len(monster_dicts)} monsters to add.")
        
        # Sample the first monster to understand the data structure
        if monster_dicts and len(monster_dicts) > 0:
            first_monster = monster_dicts[0]
            print(f"[CombatTracker] First monster type: {type(first_monster)}")
            if isinstance(first_monster, dict):
                # Print a few keys to help debug
                print(f"[CombatTracker] First monster keys: {list(first_monster.keys())[:5]}")
            elif hasattr(first_monster, '__dict__'):
                # If it's an object, print some attributes
                print(f"[CombatTracker] First monster attrs: {list(first_monster.__dict__.keys())[:5]}")
        
        added_count = 0
        failed_count = 0
        for monster_data in monster_dicts:
            try:
                # Debug print monster name if possible
                monster_name = "Unknown"
                if isinstance(monster_data, dict) and 'name' in monster_data:
                    monster_name = monster_data['name']
                elif hasattr(monster_data, 'name'):
                    monster_name = monster_data.name
                print(f"[CombatTracker] Adding monster: {monster_name}")
                
                row = self.add_monster(monster_data)
                if row >= 0:
                    added_count += 1
                    # Double-check that the type is set properly
                    type_item = self.initiative_table.item(row, 7)  # Type is column 7
                    if type_item and not type_item.text():
                        type_item.setText("monster")
                        print(f"[CombatTracker] Fixed missing type for row {row}")
                else:
                    failed_count += 1
                    print(f"[CombatTracker] Failed to add monster '{monster_name}': returned row {row}")
            except Exception as e:
                import traceback
                failed_count += 1
                name = "Unknown"
                if isinstance(monster_data, dict):
                    name = monster_data.get("name", "Unknown")
                elif hasattr(monster_data, 'name'):
                    name = getattr(monster_data, 'name', "Unknown")
                
                print(f"[CombatTracker] Error adding monster '{name}' from group: {e}")
                traceback.print_exc()  # Print the full traceback for debugging

        if added_count > 0:
            print(f"[CombatTracker] Added {added_count} monsters from group (failed: {failed_count}).")
            self._sort_initiative() # Sort after adding group
        else:
            print(f"[CombatTracker] No monsters were added from the group. All {failed_count} failed.")

    def add_monster(self, monster_data):
        """Add a monster from monster panel to the tracker"""
        if not monster_data:
            return -1
            
        # Diagnostic: Log information about this monster
        monster_name = "Unknown"
        if isinstance(monster_data, dict) and 'name' in monster_data:
            monster_name = monster_data['name']
        elif hasattr(monster_data, 'name'):
            monster_name = monster_data.name
            
        print(f"[CombatTracker] Adding monster '{monster_name}' (type: {type(monster_data)})")
        
        # Helper function to get attribute from either dict or object
        def get_attr(obj, attr, default=None, alt_attrs=None):
            """Get attribute from object or dict, trying alternate attribute names if specified"""
            alt_attrs = alt_attrs or []
            result = default
            
            try:
                if isinstance(obj, dict):
                    # Try the main attribute name first
                    if attr in obj:
                        print(f"[CombatTracker] Found '{attr}' directly in dict: {obj[attr]} (type: {type(obj[attr])})")
                        return obj[attr]
                    
                    # Try alternative attribute names
                    for alt_attr in alt_attrs:
                        if alt_attr in obj:
                            print(f"[CombatTracker] Found '{attr}' via alt name '{alt_attr}': {obj[alt_attr]} (type: {type(obj[alt_attr])})")
                            return obj[alt_attr]
                    
                    # Check if stats are nested in a 'stats' or 'attributes' dictionary 
                    for nested_key in ['stats', 'attributes', 'data']:
                        if nested_key in obj and isinstance(obj[nested_key], dict):
                            nested_dict = obj[nested_key]
                            if attr in nested_dict:
                                print(f"[CombatTracker] Found '{attr}' in nested '{nested_key}': {nested_dict[attr]} (type: {type(nested_dict[attr])})")
                                return nested_dict[attr]
                            # Try alternative attributes in nested dict
                            for alt_attr in alt_attrs:
                                if alt_attr in nested_dict:
                                    print(f"[CombatTracker] Found '{attr}' via alt name '{alt_attr}' in nested '{nested_key}': {nested_dict[alt_attr]} (type: {type(nested_dict[alt_attr])})")
                                    return nested_dict[alt_attr]
                    
                    # Handle special case for ability scores that might be in various formats
                    if attr in ['strength', 'dexterity', 'constitution', 'intelligence', 'wisdom', 'charisma']:
                        # Try shortened versions (str, dex, etc.)
                        short_name = attr[:3].lower()
                        if short_name in obj:
                            return obj[short_name]
                        
                        # Look for ability_scores dict
                        if 'ability_scores' in obj and isinstance(obj['ability_scores'], dict):
                            ability_scores = obj['ability_scores']
                            # Try both long and short names in ability_scores
                            if attr in ability_scores:
                                return ability_scores[attr]
                            if short_name in ability_scores:
                                return ability_scores[short_name]
                            # Try uppercase short name
                            if short_name.upper() in ability_scores:
                                return ability_scores[short_name.upper()]
                    
                    if attr in ['hp', 'hit_points', 'hitPoints']:
                        print(f"[CombatTracker] WARNING: Could not find HP for '{monster_name}' in dict structure")
                        print(f"[CombatTracker] Available dict keys: {list(obj.keys())}")
                    
                    return default
                
                # Try getattr for object access
                if hasattr(obj, attr):
                    attr_value = getattr(obj, attr)
                    print(f"[CombatTracker] Found '{attr}' as object attribute: {attr_value} (type: {type(attr_value)})")
                    return attr_value
                
                # Try alternative attributes for objects
                for alt_attr in alt_attrs:
                    if hasattr(obj, alt_attr):
                        attr_value = getattr(obj, alt_attr)
                        print(f"[CombatTracker] Found '{attr}' via alt attribute '{alt_attr}': {attr_value} (type: {type(attr_value)})")
                        return attr_value
                
                # Handle special case for ability scores in objects
                if attr in ['strength', 'dexterity', 'constitution', 'intelligence', 'wisdom', 'charisma']:
                    # Try shortened attribute names
                    short_name = attr[:3].lower()
                    if hasattr(obj, short_name):
                        return getattr(obj, short_name)
                    
                    # Look for ability_scores attribute
                    if hasattr(obj, 'ability_scores'):
                        ability_scores = getattr(obj, 'ability_scores')
                        if isinstance(ability_scores, dict):
                            # Try both long and short names
                            if attr in ability_scores:
                                return ability_scores[attr]
                            if short_name in ability_scores:
                                return ability_scores[short_name]
                            # Try uppercase short name
                            if short_name.upper() in ability_scores:
                                return ability_scores[short_name.upper()]
                
                if attr in ['hp', 'hit_points', 'hitPoints']:
                    print(f"[CombatTracker] WARNING: Could not find HP for '{monster_name}' in object attributes")
                    if hasattr(obj, '__dict__'):
                        print(f"[CombatTracker] Available object attributes: {list(obj.__dict__.keys())}")
                
                return default
            except Exception as e:
                print(f"[CombatTracker] Error in get_attr({attr}): {e}")
                return default
            
        # Get monster name
        name = get_attr(monster_data, "name", "Unknown Monster")
        
        # Get a reasonable initiative modifier from DEX
        dex = get_attr(monster_data, "dexterity", 10, ["dex", "DEX"])
        init_mod = (dex - 10) // 2
        
        # Roll initiative
        initiative_roll = random.randint(1, 20) + init_mod
        
        # Get monster HP and AC - extend with more alternatives
        print(f"[CombatTracker] Retrieving HP for monster '{name}'")
        hp_value = get_attr(monster_data, "hp", 10, ["hit_points", "hitPoints", "hit_points_roll", "hit_dice"])
        print(f"[CombatTracker] Retrieved HP value: {hp_value} (type: {type(hp_value)})")
        
        # For the HP display, we want the actual numeric value
        hp = self._parse_hit_points(hp_value)
        print(f"[CombatTracker] Parsed HP: {hp}")
        
        # For Max HP column, store the original value that may include formula
        max_hp = hp
        if isinstance(hp_value, str) and "(" in hp_value:
            # Extract the number before the parenthesis for current HP
            match = re.match(r'(\d+)\s*\(', hp_value)
            if match:
                hp = int(match.group(1))
                print(f"[CombatTracker] Extracted HP from string formula: {hp}")
        
        ac = get_attr(monster_data, "ac", 10, ["armor_class", "armorClass", "AC"])
        print(f"[CombatTracker] Retrieved AC value: {ac}")
        
        # Add to tracker
        row = self._add_combatant(name, initiative_roll, hp, max_hp, ac, "monster")
        
        # Ensure row is valid, default to -1 if None
        if row is None:
            row = -1
        
        # Store monster data for future reference
        if row >= 0:
            self.combatants[row] = monster_data
        
        # IMPORTANT: Find the actual row after sorting and ensure HP is set directly
        hp_str = str(hp) if hp is not None else "10"
        max_hp_str = str(max_hp) if max_hp is not None else "10"
        ac_str = str(ac) if ac is not None else "10"
        
        # Find the monster we just added by name (post-sorting)
        for check_row in range(self.initiative_table.rowCount()):
            name_item = self.initiative_table.item(check_row, 0)
            if name_item and name_item.text() == name:
                # Directly update the HP in the table after sorting
                hp_item = self.initiative_table.item(check_row, 2)
                if not hp_item or not hp_item.text():  # Check if HP is empty
                    print(f"[CombatTracker] Setting HP for {name} at row {check_row} after sorting")
                    new_hp_item = QTableWidgetItem(hp_str)
                    new_hp_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
                    self.initiative_table.setItem(check_row, 2, new_hp_item)
                
                # Directly update Max HP as well
                max_hp_item = self.initiative_table.item(check_row, 3)
                if not max_hp_item or not max_hp_item.text():  # Check if Max HP is empty
                    print(f"[CombatTracker] Setting Max HP for {name} at row {check_row} after sorting")
                    new_max_hp_item = QTableWidgetItem(max_hp_str)
                    new_max_hp_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
                    self.initiative_table.setItem(check_row, 3, new_max_hp_item)
                
                # Directly update AC as well
                ac_item = self.initiative_table.item(check_row, 4)
                if not ac_item or not ac_item.text():  # Check if AC is empty
                    print(f"[CombatTracker] Setting AC for {name} at row {check_row} after sorting")
                    new_ac_item = QTableWidgetItem(ac_str)
                    new_ac_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
                    self.initiative_table.setItem(check_row, 4, new_ac_item)
                
                # Force the table to update - this requires a viewport() or rect arg
                self.initiative_table.viewport().update()
                break
                
        # Log to combat log
        self._log_combat_action("Setup", "DM", "added monster", name, f"(Initiative: {initiative_roll})")
        
        return row

    def _parse_hit_points(self, hp_value):
        """
        Parse a monster's hit points value from various formats:
        - Integer values (45)
        - String with average ("45 (6d10+12)")
        - String with dice only ("6d10+12")
        - Dict with 'average' key
        - Dict with 'hit_dice' key
        
        Args:
            hp_value: String, integer, or dict representing hit points
            
        Returns:
            Integer value of hit points
        """
        print(f"[CombatTracker] _parse_hit_points called with value: {hp_value} (type: {type(hp_value)})")
        
        # Handle integer values directly
        if isinstance(hp_value, int):
            print(f"[CombatTracker] HP is already an integer: {hp_value}")
            return hp_value
            
        # Handle dictionary format (for newer monster data models)
        if isinstance(hp_value, dict):
            print(f"[CombatTracker] HP is a dictionary with keys: {list(hp_value.keys())}")
            
            # Try to get the 'average' field first
            if 'average' in hp_value:
                try:
                    avg_value = int(hp_value['average'])
                    print(f"[CombatTracker] Found 'average' in HP dict: {avg_value}")
                    return avg_value
                except (ValueError, TypeError) as e:
                    print(f"[CombatTracker] Error converting 'average' to int: {e}")
                    pass
                    
            # Next try 'hit_points' or 'hp' field
            for field in ['hit_points', 'hp']:
                if field in hp_value:
                    # Recursively parse this value
                    print(f"[CombatTracker] Found '{field}' in HP dict, parsing recursively")
                    return self._parse_hit_points(hp_value[field])
            
            # Try to calculate from hit_dice if available
            if 'hit_dice' in hp_value:
                dice_formula = hp_value['hit_dice']
                print(f"[CombatTracker] Found 'hit_dice' in HP dict: {dice_formula}")
                dice_match = re.search(r'(\d+)d(\d+)([+-]\d+)?', dice_formula)
                if dice_match:
                    try:
                        # Extract dice components
                        count = int(dice_match.group(1))
                        sides = int(dice_match.group(2))
                        modifier = 0
                        if dice_match.group(3):
                            modifier = int(dice_match.group(3))
                            
                        # Calculate average
                        average = int((count * (sides + 1) / 2) + modifier)
                        print(f"[CombatTracker] Calculated average from hit_dice: {average}")
                        return max(1, average)  # Ensure at least 1 HP
                    except (ValueError, TypeError, IndexError) as e:
                        print(f"[CombatTracker] Error calculating from hit_dice: {e}")
                        pass
                else:
                    print(f"[CombatTracker] Could not parse hit_dice formula: {dice_formula}")
                        
            # Last resort for dict - return a default
            print(f"[CombatTracker] Could not parse HP dict: {hp_value}, using default")
            return 10
        
        # Handle string formats
        if not hp_value or not isinstance(hp_value, str):
            print(f"[CombatTracker] HP is None or not a string: {hp_value}")
            return 10  # Default fallback
            
        # If it's already just a number, convert and return
        if hp_value.isdigit():
            hp_int = int(hp_value)
            print(f"[CombatTracker] HP is a digit string: {hp_int}")
            return hp_int
            
        # Try to extract the average value (number before parentheses)
        # Format is typically "45 (6d10+12)" or sometimes just "6d10+12"
        match = re.match(r'(\d+)\s*\(', hp_value)
        if match:
            try:
                hp_int = int(match.group(1))
                print(f"[CombatTracker] Extracted HP from formula format: {hp_int}")
                return hp_int
            except (ValueError, TypeError) as e:
                print(f"[CombatTracker] Error extracting from formula: {e}")
                pass
                
        # If no average provided, try to calculate from the dice formula
        dice_match = re.search(r'(\d+)d(\d+)([+-]\d+)?', hp_value)
        if dice_match:
            try:
                # Extract dice components
                count = int(dice_match.group(1))
                sides = int(dice_match.group(2))
                modifier = 0
                if dice_match.group(3):
                    modifier = int(dice_match.group(3))
                    
                # Calculate average
                average = int((count * (sides + 1) / 2) + modifier)
                print(f"[CombatTracker] Calculated average from dice string: {average}")
                return max(1, average)  # Ensure at least 1 HP
            except (ValueError, TypeError, IndexError) as e:
                print(f"[CombatTracker] Error calculating from dice string: {e}")
                pass
                
        # If all parsing fails, return a default value
        print(f"[CombatTracker] Could not parse HP value: {hp_value} (type: {type(hp_value)}), using default")
        return 10

    def add_character(self, character):
        """Add a player character from character panel to the tracker"""
        if not character:
            return
            
        # Helper function to get attribute from either dict or object
        def get_attr(obj, attr, default=None, alt_attrs=None):
            """Get attribute from object or dict, trying alternate attribute names if specified"""
            alt_attrs = alt_attrs or []
            
            if isinstance(obj, dict):
                # Try the main attribute name first
                if attr in obj:
                    return obj[attr]
                
                # Try alternative attribute names
                for alt_attr in alt_attrs:
                    if alt_attr in obj:
                        return obj[alt_attr]
                
                return default
            
            # Try getattr for object access
            if hasattr(obj, attr):
                return getattr(obj, attr)
            
            # Try alternative attributes for objects
            for alt_attr in alt_attrs:
                if hasattr(obj, alt_attr):
                    return getattr(obj, alt_attr)
            
            return default
            
        # Get character name
        name = get_attr(character, "name", "Unknown Character")
        
        # Get initiative bonus
        initiative_bonus = get_attr(character, "initiative_bonus", 0)
        
        # Roll initiative with the bonus
        initiative_roll = random.randint(1, 20) + initiative_bonus
        
        # Get HP and AC
        current_hp = get_attr(character, "current_hp", 10)
        max_hp = get_attr(character, "max_hp", current_hp)
        ac = get_attr(character, "armor_class", 10)
        
        # Add to tracker
        row = self._add_combatant(name, initiative_roll, current_hp, max_hp, ac, "character")
        
        # Store character data for future reference
        if row >= 0:
            self.combatants[row] = character
            
        # Log to combat log
        self._log_combat_action("Setup", "DM", "added character", name, f"(Initiative: {initiative_roll})")
        
        return row

    def _remove_selected(self):
        """Remove selected combatants from the initiative order"""
        selected_rows = sorted([index.row() for index in 
                               self.initiative_table.selectionModel().selectedRows()], reverse=True)
        
        if not selected_rows:
            return
        
        # Ask for confirmation if multiple rows selected
        if len(selected_rows) > 1:
            confirm = QMessageBox.question(
                self,
                "Confirm Removal",
                f"Remove {len(selected_rows)} combatants?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if confirm != QMessageBox.Yes:
                return
        
        # Remove rows from table (in reverse order to avoid index issues)
        for row in selected_rows:
            name = self.initiative_table.item(row, 0).text()
            self.initiative_table.removeRow(row)
            
            # Also remove from tracking collections
            self.concentrating.discard(row)
            if row in self.death_saves:
                del self.death_saves[row]
                
            # Remove from combatants dictionary if present
            if row in self.combatants:
                del self.combatants[row]
            
            # Log removal
            self._log_combat_action("Setup", "DM", "removed", name, "from combat")
        
        # Adjust current turn index if needed
        if self.combat_started:
            # If we removed the current turn, move to the next
            if self.current_turn in selected_rows:
                if self.initiative_table.rowCount() > 0:
                    # Set to previous turn, then _next_turn will advance
                    self.current_turn = (self.current_turn - 1) % self.initiative_table.rowCount()
                    self._next_turn()
                else:
                    # No combatants left, reset
                    self.combat_started = False
                    self.current_turn = -1
            # Otherwise, just adjust for removed rows
            elif self.current_turn >= 0:
                # Count how many removed rows are before current
                removed_before = sum(1 for r in selected_rows if r < self.current_turn)
                self.current_turn -= removed_before
                
        # Update the highlight
        self._update_highlight()
        
        # Update and rebuild combatant index mapping
        new_combatants = {}
        # Reindex combatants dictionary to match new row indices
        for old_row, combatant in self.combatants.items():
            # Skip removed rows
            if old_row in selected_rows:
                continue
                
            # Calculate new row index
            new_row = old_row - sum(1 for r in selected_rows if r < old_row)
            new_combatants[new_row] = combatant
                
        self.combatants = new_combatants
        
        # Adjust concentrating and death_saves mappings
        new_concentrating = set()
        for row in self.concentrating:
            if row not in selected_rows:
                new_row = row - sum(1 for r in selected_rows if r < row)
                new_concentrating.add(new_row)
        self.concentrating = new_concentrating
        
        new_death_saves = {}
        for row, saves in self.death_saves.items():
            if row not in selected_rows:
                new_row = row - sum(1 for r in selected_rows if r < row)
                new_death_saves[new_row] = saves
        self.death_saves = new_death_saves

    def _view_combatant_details(self, row):
        """Show the details for the combatant at the given row"""
        if not self.initiative_table.item(row, 0):
            return
            
        name_item = self.initiative_table.item(row, 0)
        combatant_name = name_item.text()
        combatant_type = name_item.data(Qt.UserRole)
        
        # If type is None or empty, try to get it from the type column (index 6)
        if not combatant_type and self.initiative_table.item(row, 6):
            combatant_type = self.initiative_table.item(row, 6).text().lower()
            # Store it back in the name item for future use
            name_item.setData(Qt.UserRole, combatant_type)
            
        # If still None, default to custom
        if not combatant_type:
            combatant_type = "custom"
            
        print(f"[Combat Tracker] Viewing details for {combatant_type} '{combatant_name}'")
        
        # Redirect to appropriate panel based on combatant type
        if combatant_type == "monster":
            # Get the monster panel and view the monster
            monster_panel = self.get_panel("monster")
            if monster_panel:
                # Use the panel manager to show the panel
                if hasattr(self.app_state, 'panel_manager'):
                    panel_manager = self.app_state.panel_manager
                    panel_manager.show_panel("monster")
                    
                    # Now search and select the monster
                    result = monster_panel.search_and_select_monster(combatant_name)
                    if not result:
                        # If monster not found, show a message and use the dialog fallback
                        print(f"[Combat Tracker] Monster '{combatant_name}' not found in monster browser")
                        self._show_combatant_dialog(row, combatant_name, combatant_type)
                else:
                    print("[Combat Tracker] No panel_manager found in app_state")
                    self._show_combatant_dialog(row, combatant_name, combatant_type)
            else:
                # Fallback to dialog if panel not found
                self._show_combatant_dialog(row, combatant_name, combatant_type)
        elif combatant_type == "character":
            # Get the character panel and view the character
            character_panel = self.get_panel("player_character")
            if character_panel:
                # Use the panel manager to show the panel
                if hasattr(self.app_state, 'panel_manager'):
                    panel_manager = self.app_state.panel_manager
                    panel_manager.show_panel("player_character")
                    
                    # Now search and select the character
                    result = character_panel.select_character_by_name(combatant_name)
                    if not result:
                        # If character not found, show a message and use the dialog fallback
                        print(f"[Combat Tracker] Character '{combatant_name}' not found in character panel")
                        self._show_combatant_dialog(row, combatant_name, combatant_type)
                else:
                    print("[Combat Tracker] No panel_manager found in app_state")
                    self._show_combatant_dialog(row, combatant_name, combatant_type)
            else:
                # Fallback to dialog if panel not found
                self._show_combatant_dialog(row, combatant_name, combatant_type)
        else:
            # For custom entries, use the dialog approach
            self._show_combatant_dialog(row, combatant_name, combatant_type)
            
    def _show_combatant_dialog(self, row, combatant_name, combatant_type):
        """Show a dialog with combatant details when we can't redirect to another panel"""
        print(f"[Combat Tracker] Showing dialog for {combatant_type} '{combatant_name}'")
        
        # Get basic data from the initiative table
        combatant_data = {
            "name": combatant_name,
            "initiative": int(self.initiative_table.item(row, 1).text()) if self.initiative_table.item(row, 1) else 0,
            "hp": int(self.initiative_table.item(row, 2).text()) if self.initiative_table.item(row, 2) else 0,
            "max_hp": int(self.initiative_table.item(row, 3).text()) if self.initiative_table.item(row, 3) else 0,
            "ac": int(self.initiative_table.item(row, 4).text()) if self.initiative_table.item(row, 4) else 0,
            "status": self.initiative_table.item(row, 5).text() if self.initiative_table.item(row, 5) else ""
        }
        
        # For monsters, try to get the full data from the stored combatants dictionary
        if combatant_type == "monster":
            for combatant_row, stored_data in self.combatants.items():
                if hasattr(stored_data, 'name') and stored_data.name == combatant_name:
                    combatant_data = stored_data
                    break
                elif isinstance(stored_data, dict) and stored_data.get('name') == combatant_name:
                    combatant_data = stored_data
                    break
        
        print(f"[CombatDetailsDialog] Received data for {combatant_type}: {combatant_data}")
        dialog = CombatantDetailsDialog(self, combatant_data, combatant_type)
        dialog.exec()

    def _toggle_details_pane(self):
        """Toggle the visibility of the details pane"""
        self.show_details_pane = self.toggle_details_btn.isChecked()
        
        if self.show_details_pane:
            self.toggle_details_btn.setText("Hide Details")
            self.details_widget.show()
            # If we have a selected combatant, update details
            if self.current_details_combatant:
                self._update_details_pane()
            else:
                # If nothing selected but initiative table has rows, select the first row
                if self.initiative_table.rowCount() > 0:
                    self.initiative_table.selectRow(0)
        else:
            self.toggle_details_btn.setText("Show Details")
            self.details_widget.hide()
    
    def _update_details_pane(self):
        """Update the details pane with the current combatant's information"""
        if not self.current_details_combatant:
            self.name_label.setText("No combatant selected")
            return
            
        # Helper to get attributes safely 
        def get_attr(obj, attr, default=None, alt_attrs=None):
            """Get attribute from dict or object"""
            alt_attrs = alt_attrs or []
            
            if isinstance(obj, dict):
                if attr in obj:
                    return obj[attr]
                for alt in alt_attrs:
                    if alt in obj:
                        return obj[alt]
            else:
                if hasattr(obj, attr):
                    return getattr(obj, attr)
                for alt in alt_attrs:
                    if hasattr(obj, alt):
                        return getattr(obj, alt)
            return default
        
        # Format ability score with modifier
        def format_ability(score):
            if score is None:
                return "-"
            mod = (score - 10) // 2
            mod_str = f"+{mod}" if mod >= 0 else str(mod)
            return f"{score} ({mod_str})"
        
        # Clear previous data
        self._clear_details_layouts()
        
        # Update basic info
        name = get_attr(self.current_details_combatant, "name", "Unknown")
        self.name_label.setText(name)
        self.details_title.setText(f"{name} Details")
        
        # Type info depends on combatant type
        type_text = ""
        if self.current_details_type == "monster":
            size = get_attr(self.current_details_combatant, "size", "")
            type_val = get_attr(self.current_details_combatant, "type", "")
            alignment = get_attr(self.current_details_combatant, "alignment", "")
            
            if size and type_val:
                type_text = f"{size} {type_val}"
                if alignment:
                    type_text += f", {alignment}"
        else:  # character
            race = get_attr(self.current_details_combatant, "race", "")
            character_class = get_attr(self.current_details_combatant, "character_class", "", ["class"])
            level = get_attr(self.current_details_combatant, "level", "")
            
            parts = []
            if level:
                parts.append(f"Level {level}")
            if race:
                parts.append(race)
            if character_class:
                parts.append(character_class)
                
            type_text = " ".join(parts)
            
        self.type_label.setText(type_text)
        
        # AC
        ac = get_attr(self.current_details_combatant, "armor_class", "-", ["ac", "AC"])
        self.ac_details_label.setText(str(ac))
        
        # HP
        hp_text = ""
        if self.current_details_type == "monster":
            hp = get_attr(self.current_details_combatant, "hit_points", "-", ["hp", "HP"])
            hp_text = str(hp)
        else:  # character
            current_hp = get_attr(self.current_details_combatant, "current_hp", "-", ["hp"])
            max_hp = get_attr(self.current_details_combatant, "max_hp", "-", ["maximum_hp"])
            if current_hp is not None and max_hp is not None:
                hp_text = f"{current_hp}/{max_hp}"
                
                temp_hp = get_attr(self.current_details_combatant, "temp_hp", 0, ["temporary_hp"])
                # Check if temp_hp can be converted to int and is positive
                try:
                    temp_hp_value = int(temp_hp)
                    if temp_hp_value > 0:
                        hp_text += f" (+{temp_hp_value})"
                except (ValueError, TypeError):
                    # If temp_hp can't be converted to int, ignore it
                    pass
        
        self.hp_details_label.setText(hp_text)
        
        # Speed
        speed = get_attr(self.current_details_combatant, "speed", "-")
        self.speed_label.setText(str(speed))
        
        # Ability scores
        ability_scores = get_attr(self.current_details_combatant, "ability_scores", {})
        
        if ability_scores:
            # Use different mappings depending on what format the data is in
            if isinstance(ability_scores, dict):
                # Check if using short names (STR) or long names (strength)
                if any(k in ability_scores for k in ["STR", "DEX", "CON", "INT", "WIS", "CHA"]):
                    # Short names
                    self.str_label.setText(f"STR\n{format_ability(ability_scores.get('STR'))}")
                    self.dex_label.setText(f"DEX\n{format_ability(ability_scores.get('DEX'))}")
                    self.con_label.setText(f"CON\n{format_ability(ability_scores.get('CON'))}")
                    self.int_label.setText(f"INT\n{format_ability(ability_scores.get('INT'))}")
                    self.wis_label.setText(f"WIS\n{format_ability(ability_scores.get('WIS'))}")
                    self.cha_label.setText(f"CHA\n{format_ability(ability_scores.get('CHA'))}")
                else:
                    # Long names
                    self.str_label.setText(f"STR\n{format_ability(ability_scores.get('strength', ability_scores.get('str')))}")
                    self.dex_label.setText(f"DEX\n{format_ability(ability_scores.get('dexterity', ability_scores.get('dex')))}")
                    self.con_label.setText(f"CON\n{format_ability(ability_scores.get('constitution', ability_scores.get('con')))}")
                    self.int_label.setText(f"INT\n{format_ability(ability_scores.get('intelligence', ability_scores.get('int')))}")
                    self.wis_label.setText(f"WIS\n{format_ability(ability_scores.get('wisdom', ability_scores.get('wis')))}")
                    self.cha_label.setText(f"CHA\n{format_ability(ability_scores.get('charisma', ability_scores.get('cha')))}")
        
        # Actions & Features
        # Actions
        actions = get_attr(self.current_details_combatant, "actions", [])
        if actions:
            for action in actions:
                action_name = get_attr(action, "name", "")
                action_desc = get_attr(action, "desc", "")
                
                if action_name and action_desc:
                    action_label = QLabel(f"<b>{action_name}</b>: {action_desc}")
                    action_label.setWordWrap(True)
                    self.actions_layout.addWidget(action_label)
        
        # Features/Traits
        traits = get_attr(self.current_details_combatant, "special_abilities", [])
        if not traits:  # Try alternate names
            traits = get_attr(self.current_details_combatant, "traits", [])
        if not traits:
            traits = get_attr(self.current_details_combatant, "features", [])
        
        if traits:
            for trait in traits:
                if isinstance(trait, dict):
                    trait_name = get_attr(trait, "name", "")
                    trait_desc = get_attr(trait, "desc", "")
                    
                    if trait_name and trait_desc:
                        trait_label = QLabel(f"<b>{trait_name}</b>: {trait_desc}")
                        trait_label.setWordWrap(True)
                        self.traits_layout.addWidget(trait_label)
                elif isinstance(trait, str):
                    # If it's just a string, add it directly
                    trait_label = QLabel(trait)
                    trait_label.setWordWrap(True)
                    self.traits_layout.addWidget(trait_label)
        
        # Spells
        spells = get_attr(self.current_details_combatant, "spells", [])
        if spells:
            for spell in spells:
                if isinstance(spell, dict):
                    spell_name = get_attr(spell, "name", "")
                    spell_desc = get_attr(spell, "desc", "")
                    
                    if spell_name:
                        spell_label = QLabel(f"<b>{spell_name}</b>")
                        if spell_desc:
                            spell_label.setText(f"<b>{spell_name}</b>: {spell_desc}")
                        spell_label.setWordWrap(True)
                        self.spells_layout.addWidget(spell_label)
                elif isinstance(spell, str):
                    # If it's just a string, add it directly
                    spell_label = QLabel(spell)
                    spell_label.setWordWrap(True)
                    self.spells_layout.addWidget(spell_label)
        
        # Final spacing
        self.actions_layout.addStretch()
        self.traits_layout.addStretch()
        self.spells_layout.addStretch()
        
        # Force tab widget to update and be visible
        self.actions_tab.setVisible(True)
        self.actions_tab.show()
        self.actions_tab.adjustSize()
        
        # Make sure the details pane refreshes
        self.details_content.setWidget(self.stats_widget)
        self.details_content.adjustSize()
        self.details_widget.adjustSize()
        self.details_widget.update()
    
    def _clear_details_layouts(self):
        """Clear action, trait, and spell layouts"""
        # Clear actions
        while self.actions_layout.count():
            item = self.actions_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Clear traits
        while self.traits_layout.count():
            item = self.traits_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Clear spells
        while self.spells_layout.count():
            item = self.spells_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
    
    def _on_selection_changed(self):
        """Handle when the selection in the initiative table changes"""
        selected_rows = self.initiative_table.selectedItems()
        if not selected_rows:
            return
            
        # Get the selected row
        row = selected_rows[0].row()
        
        # If details pane is visible, update it with the selected combatant
        if self.show_details_pane:
            self._view_combatant_details(row)
    
    def get_panel(self, panel_id):
        """Get a panel from the panel manager"""
        # Try to get from the app_state panel manager
        if hasattr(self.app_state, 'panel_manager'):
            panel_manager = self.app_state.panel_manager
            # First check if the panel manager has a get_panel_widget method
            if hasattr(panel_manager, 'get_panel_widget'):
                return panel_manager.get_panel_widget(panel_id)
            # Otherwise try the get_panel method which returns a dock widget
            elif hasattr(panel_manager, 'get_panel'):
                panel_dock = panel_manager.get_panel(panel_id)
                if panel_dock:
                    return panel_dock.widget()
        # If not found, use the BasePanel's get_panel method from parent class
        return super().get_panel(panel_id)
    
    def closeEvent(self, event):
        """Handle cleanup when panel is closed"""
        # Disconnect signals to avoid errors
        self.hp_delegate.hpChanged.disconnect()
        self.init_delegate.initChanged.disconnect()
        
        # Call parent closeEvent
        super().closeEvent(event)

    def _fix_missing_types(self):
        """Fix any missing combatant types for existing entries"""
        # Check if we need to fix any missing types
        fix_count = 0
        
        for row in range(self.initiative_table.rowCount()):
            # Get the current type
            type_item = self.initiative_table.item(row, 6)
            if not type_item or not type_item.text():
                name_item = self.initiative_table.item(row, 0)
                name = name_item.text() if name_item else "Unknown"
                
                # Try to infer type
                inferred_type = ""
                
                # First, check if we have combatant data
                if row in self.combatants:
                    data = self.combatants[row]
                    if isinstance(data, dict):
                        if any(k in data for k in ["monster_id", "size", "challenge_rating", "hit_points"]):
                            inferred_type = "monster"
                        elif any(k in data for k in ["character_class", "level", "race"]):
                            inferred_type = "character"
                
                # If still unknown, use name-based heuristics
                if not inferred_type:
                    monster_names = ["goblin", "ogre", "dragon", "troll", "zombie", "skeleton", 
                                    "ghoul", "ghast", "ghost", "demon", "devil", "elemental"]
                    lower_name = name.lower()
                    
                    # Check for common monster names
                    if any(monster in lower_name for monster in monster_names):
                        inferred_type = "monster"
                    # Check for NPC tag
                    elif "(npc)" in lower_name:
                        inferred_type = "character"
                    else:
                        # Default to monster if other heuristics fail
                        inferred_type = "monster"
                
                # Set the inferred type
                if not type_item:
                    type_item = QTableWidgetItem()
                    self.initiative_table.setItem(row, 6, type_item)
                
                type_item.setText(inferred_type)
                fix_count += 1
                print(f"[CombatTracker] Fixed missing type for '{name}' - set to '{inferred_type}'")
        
        if fix_count > 0:
            print(f"[CombatTracker] Fixed types for {fix_count} combatants")
        
        return fix_count
