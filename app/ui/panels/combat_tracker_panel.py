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
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QLabel,
    QSpinBox, QLineEdit, QPushButton, QHeaderView, QComboBox, QCheckBox,
    QGroupBox, QWidget, QStyledItemDelegate, QStyle, QToolButton,
    QTabWidget, QScrollArea, QFormLayout, QFrame, QSplitter, QApplication,
    QSizePolicy, QTextEdit, QMenu, QMessageBox, QDialog, QDialogButtonBox,
    QAbstractItemView
)
from PySide6.QtCore import Qt, QTimer, Signal, Slot, QSize, QMetaObject, Q_ARG, QObject, QPoint, QRect, QEvent, QThread
from PySide6.QtGui import QColor, QFont, QTextCharFormat, QBrush, QPixmap, QImage, QTextCursor, QPalette, QAction, QKeySequence
import random
import re
import json # Added json import
import copy
import time
import threading
import gc
import hashlib

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

# --- Concentration Dialog (Moved Here) --- 
class ConcentrationDialog(QDialog):
    """Dialog for concentration checks when taking damage"""
    def __init__(self, parent=None, combatant_name="", dc=10):
        super().__init__(parent)
        self.setWindowTitle("Concentration Check")
        self.combatant_name = combatant_name
        self.dc = dc
        self.save_result = 0
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout()
        
        # Information label
        info_label = QLabel(f"{self.combatant_name} must make a concentration check (DC {self.dc})")
        layout.addWidget(info_label)
        
        # Save roll input
        save_layout = QHBoxLayout()
        save_layout.addWidget(QLabel("Save Roll:"))
        self.save_spin = QSpinBox()
        self.save_spin.setRange(1, 30)
        self.save_spin.setValue(10)
        save_layout.addWidget(self.save_spin)
        
        # Roll button
        roll_button = QPushButton("Roll")
        roll_button.clicked.connect(self._roll_save)
        save_layout.addWidget(roll_button)
        
        layout.addLayout(save_layout)
        
        # Result display
        self.result_label = QLabel("")
        layout.addWidget(self.result_label)
        
        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        self.setLayout(layout)
    
    def _roll_save(self):
        """Roll a d20 for the save"""
        roll = random.randint(1, 20)
        self.save_spin.setValue(roll)
        self._update_result()
    
    def _update_result(self):
        """Update the result label"""
        value = self.save_spin.value()
        if value >= self.dc:
            self.result_label.setText(f"Success! ({value} ≥ {self.dc})")
            self.result_label.setStyleSheet("color: green;")
        else:
            self.result_label.setText(f"Failure! ({value} < {self.dc})")
            self.result_label.setStyleSheet("color: red;")
    
    def get_save_result(self):
        """Get the final save roll result"""
        return self.save_spin.value()

# --- Main Panel Class --- 

class CombatTrackerPanel(BasePanel):
    """Panel for tracking combat initiative, HP, and conditions"""
    
    # Signal to emit when combat resolution is complete (or failed)
    # Carries the result dict and error string (one will be None)
    resolution_complete = Signal(dict, str)
    
    # New signal for showing turn results
    show_turn_result_signal = Signal(str, str, str, str, str)
    
    # Add missing combat_log_signal for panel connection
    combat_log_signal = Signal(str, str, str, str, str)  # category, actor, action, target, result
    
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
        
        # Initialize combat state
        self.current_round = 1
        self.current_turn = 0
        self._current_turn = 0
        self.previous_turn = -1
        self.combat_time = 0
        self.combat_started = False
        self.death_saves = {}  # Store by row index: {successes: int, failures: int}
        self.concentrating = set()  # Store row indices of concentrating combatants
        self.combatants = {} # Store combatant data, keyed by row index
        self.monster_id_counter = 0  # Counter for unique monster IDs
        
        # Add missing property initialization
        self.show_details_pane = False
        
        # --- NEW: Flag to prevent sorting during LLM resolution --- 
        self._is_resolving_combat = False 
        
        # Initialize timers
        self.timer = QTimer()
        self.timer.timeout.connect(self._update_timer)
        self.timer.setInterval(1000)  # 1 second interval
        self.combat_log = []  # List of combat log entries
        
        # New: live combat log
        self.combat_log_widget = None
        
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
        
        # Connect the turn result signal to the slot
        self.show_turn_result_signal.connect(self._show_turn_result_slot)
        
        # Connect to combat resolver if available - FIXED CONNECTION SETUP
        if hasattr(self.app_state, 'combat_resolver') and self.app_state.combat_resolver:
            try:
                # Ensure the resolver is a QObject (it should be after the previous edit)
                if isinstance(self.app_state.combat_resolver, QObject):
                    # Connect the signal for completion of the entire combat
                    self.app_state.combat_resolver.resolution_complete.connect(self._process_resolution_ui)
                    
                    # Connect the per-turn update signal if it exists
                    if hasattr(self.app_state.combat_resolver, 'turn_update'):
                        self.app_state.combat_resolver.turn_update.connect(self._update_ui_wrapper)
                        print("[CombatTracker] Connected turn_update signal to _update_ui_wrapper")
                    else:
                        print("[CombatTracker] Warning: CombatResolver has no turn_update signal, per-turn updates may not work")
                    
                    print("[CombatTracker] Connected resolution_complete signal to _process_resolution_ui slot.")
                else:
                    print("[CombatTracker] Warning: CombatResolver is not a QObject, cannot connect signals.")
            except Exception as e:
                print(f"[CombatTracker] Error connecting to combat resolver: {e}")

    def _ensure_table_ready(self):
        """Ensure the table exists and has the correct number of columns"""
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
        """Setup the UI components"""
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Create a splitter to allow manual resizing between the table and log
        self.main_splitter = QSplitter(Qt.Vertical)
        
        # --- Initiative Table Area ---
        table_container = QWidget()
        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create initiative table
        self.initiative_table = QTableWidget(0, 8)  # Changed to 8 columns
        self.initiative_table.setHorizontalHeaderLabels(["Name", "Initiative", "HP", "Max HP", "AC", "Status", "Conc.", "Type"])
        self.initiative_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.initiative_table.setSelectionMode(QTableWidget.ExtendedSelection)
        # Allow editing via double‑click or pressing a key, but NOT on single
        # mouse right‑clicks so the context menu can appear reliably.
        self.initiative_table.setEditTriggers(
            QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed
        )
        
        # Set column widths
        self.initiative_table.setColumnWidth(0, 150)  # Name
        self.initiative_table.setColumnWidth(1, 80)   # Initiative
        self.initiative_table.setColumnWidth(2, 80)   # HP
        self.initiative_table.setColumnWidth(3, 80)   # Max HP
        self.initiative_table.setColumnWidth(4, 60)   # AC
        self.initiative_table.setColumnWidth(5, 120)  # Status
        self.initiative_table.setColumnWidth(6, 60)   # Conc
        self.initiative_table.setColumnWidth(7, 100)  # Type
        
        # Set header behavior
        header = self.initiative_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)       # Name stretches
        header.setSectionResizeMode(5, QHeaderView.Stretch)       # Status stretches
        header.setSectionResizeMode(1, QHeaderView.Fixed)         # Initiative fixed
        header.setSectionResizeMode(2, QHeaderView.Fixed)         # HP fixed
        header.setSectionResizeMode(3, QHeaderView.Fixed)         # Max HP fixed  
        header.setSectionResizeMode(4, QHeaderView.Fixed)         # AC fixed
        header.setSectionResizeMode(6, QHeaderView.Fixed)         # Conc fixed
        header.setSectionResizeMode(7, QHeaderView.Fixed)         # Type fixed
        
        # Connect context menu
        self.initiative_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.initiative_table.customContextMenuRequested.connect(self._show_context_menu)
        
        # Connect change signals
        self.initiative_table.cellChanged.connect(self._handle_cell_changed)
        
        # Set up the custom delegates
        self._setup_delegates()
        
        # --- Control Area with three rows: Round/Timer, Buttons, Add Combatant ---
        control_layout = self._setup_control_area()
        table_layout.addLayout(control_layout)
        
        # Add add combatant controls if needed
        add_combatant_layout = self._setup_add_combatant_controls()
        table_layout.addLayout(add_combatant_layout)
        
        # Add table to layout
        table_layout.addWidget(self.initiative_table)
        
        # Add table to main splitter
        self.main_splitter.addWidget(table_container)
        
        # --- Combat Log Area (NEW) ---
        self.log_container = QWidget()
        log_layout = QVBoxLayout(self.log_container)
        log_layout.setContentsMargins(0, 0, 0, 0)
        
        # Header for combat log
        log_header = QHBoxLayout()
        log_header.addWidget(QLabel("<b>Combat Log & Results</b>"))
        
        # Add clear button for log
        clear_log_btn = QPushButton("Clear Log")
        clear_log_btn.setMaximumWidth(100)
        clear_log_btn.clicked.connect(self._clear_combat_log)
        log_header.addWidget(clear_log_btn)
        
        log_layout.addLayout(log_header)
        
        # Create text area for combat log
        self.combat_log_text = QTextEdit()
        self.combat_log_text.setReadOnly(True)
        self.combat_log_text.setMinimumHeight(100)
        self.combat_log_text.setStyleSheet("""
            QTextEdit { 
                background-color: white;
                color: #000000;
                font-family: Arial, sans-serif;
                font-size: 12px;
            }
        """)
        log_layout.addWidget(self.combat_log_text)
        
        # Add log container to splitter
        self.main_splitter.addWidget(self.log_container)
        
        # Set reasonable initial sizes
        self.main_splitter.setSizes([600, 200])
        
        # Add the splitter to the main layout
        layout.addWidget(self.main_splitter)
        
        self.setLayout(layout)
        
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
    
    def _add_combatant(self, name, initiative, hp, max_hp, ac, combatant_type="", monster_id=None):
        """Add a combatant to the initiative table"""
        print(f"[CombatTracker] _add_combatant called: name={name}, initiative={initiative}, hp={hp}, max_hp={max_hp}, ac={ac}, type={combatant_type}, id={monster_id}")
        
        # Get current row count
        row = self.initiative_table.rowCount()
        self.initiative_table.insertRow(row)
        
        # Create name item with combatant type stored in user role
        name_item = QTableWidgetItem(name)
        name_item.setData(Qt.UserRole, combatant_type)  # Store type with the name item
        
        # If this is a monster with ID, store the ID in UserRole+2
        if monster_id is not None:
            name_item.setData(Qt.UserRole + 2, monster_id)
            print(f"[CombatTracker] Set monster ID {monster_id} for {name}")
        
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
        
        # Store current row before sorting
        current_row = row
        
        # Sort the initiative order
        self._sort_initiative()
        
        # Verify the final result
        final_hp_item = self.initiative_table.item(row, 2)
        if final_hp_item:
            final_hp = final_hp_item.text()
            print(f"[CombatTracker] Final verification - {name} HP after sorting: {final_hp}")
        
        # After sorting, find this monster's new row by its ID
        sorted_row = -1
        if monster_id is not None:
            sorted_row = self._find_monster_by_id(monster_id)
            if sorted_row >= 0:
                print(f"[CombatTracker] After sorting, monster {name} (ID {monster_id}) is at row {sorted_row}")
            else:
                print(f"[CombatTracker] WARNING: Could not find monster {name} (ID {monster_id}) after sorting")
                sorted_row = row  # Fall back to original row
        
        # Return the row where the combatant was added (post-sorting if monster with ID)
        return sorted_row if sorted_row >= 0 else row
    
    def _find_monster_by_id(self, monster_id):
        """Find the row of a monster by its unique ID"""
        if monster_id is None:
            return -1
            
        for row in range(self.initiative_table.rowCount()):
            name_item = self.initiative_table.item(row, 0)
            if name_item and name_item.data(Qt.UserRole + 2) == monster_id:
                return row
                
        return -1
    
    def _sort_initiative(self):
        """Sort the initiative list in descending order."""
        # --- Check flag: Prevent sorting during LLM resolution --- 
        if self._is_resolving_combat:
            print("[CombatTracker] _sort_initiative: Skipping sort because _is_resolving_combat is True.")
            return
            
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
                
            # Save all monsters IDs and stats before sorting
            monster_stats = {}
            monster_instance_ids = {}  # NEW: Track instance IDs for each row
            for row in range(row_count):
                name_item = self.initiative_table.item(row, 0)
                if name_item:
                    # Save monster ID if it exists
                    if name_item.data(Qt.UserRole + 2) is not None:
                        monster_id = name_item.data(Qt.UserRole + 2)
                        monster_stats[monster_id] = {
                            "id": monster_id,
                            "name": name_item.text(),
                            "hp": self.initiative_table.item(row, 2).text() if self.initiative_table.item(row, 2) else "10",
                            "max_hp": self.initiative_table.item(row, 3).text() if self.initiative_table.item(row, 3) else "10",
                            "ac": self.initiative_table.item(row, 4).text() if self.initiative_table.item(row, 4) else "10"
                        }
                    
                    # NEW: Store instance ID for this row
                    monster_instance_ids[row] = name_item.data(Qt.UserRole + 2) or f"combatant_{row}"
                    print(f"[CombatTracker] Row {row} has instance ID: {monster_instance_ids[row]}")
            
            # Store pre-sort HP and AC data for verification
            pre_sort_values = {}
            for row in range(row_count):
                name_item = self.initiative_table.item(row, 0)
                hp_item = self.initiative_table.item(row, 2)
                ac_item = self.initiative_table.item(row, 4)
                
                name = name_item.text() if name_item else f"Row {row}"
                hp = hp_item.text() if hp_item else "?"
                ac = ac_item.text() if ac_item else "?"
                
                pre_sort_values[name] = {"hp": hp, "ac": ac, "instance_id": monster_instance_ids.get(row, f"combatant_{row}")}
            
            # Collect all the data from the table first
            print(f"[CombatTracker] Collecting data from {row_count} rows")
            
            # Store all row data before clearing
            rows_data = []
            initiative_values = []
            
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
                            'currentTurn': item.data(Qt.UserRole + 1),
                            'instanceId': item.data(Qt.UserRole + 2) if col == 0 else None  # Save monster ID/instance ID
                        }
                        
                # Add this row's data to our collection
                rows_data.append(row_data)
                initiative_values.append((initiative, row))
                hp_value = row_data.get(2, {}).get('text', '?')
                ac_value = row_data.get(4, {}).get('text', '?')
                instance_id = row_data.get(0, {}).get('instanceId', f"combatant_{row}")
                print(f"[CombatTracker] Row {row}: initiative={initiative}, hp={hp_value}, ac={ac_value}, instance_id={instance_id}")
                
            # Execute the rest of the original sort code
            # Sort the initiative values in descending order
            initiative_values.sort(key=lambda x: x[0], reverse=True)
            
            # Remap original rows to their new position after sorting
            row_map = {old_row: new_row for new_row, (_, old_row) in enumerate(initiative_values)}
            # NEW: Also create reverse mapping
            new_to_old_map = {new_row: old_row for old_row, new_row in row_map.items()}
            
            # Remember the current selection and turn
            current_row = self.initiative_table.currentRow()
            current_turn = self._current_turn if hasattr(self, '_current_turn') else None
            
            # Clear the table (but don't update combat stats yet)
            self.initiative_table.setRowCount(0)
            self.initiative_table.setRowCount(row_count)
            
            # Add the sorted rows back to the table
            for old_row, new_row in row_map.items():
                row_data = rows_data[old_row]
                
                # Debug HP and AC for this row
                hp_value = row_data.get(2, {}).get('text', '?')
                ac_value = row_data.get(4, {}).get('text', '?')
                instance_id = row_data.get(0, {}).get('instanceId', f"combatant_{old_row}")
                print(f"[CombatTracker] Moving HP value: {hp_value} from old_row={old_row} to new_row={new_row}")
                print(f"[CombatTracker] Moving AC value: {ac_value} from old_row={old_row} to new_row={new_row}")
                print(f"[CombatTracker] Moving instance ID: {instance_id} from old_row={old_row} to new_row={new_row}")
                
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
                    
                    # IMPORTANT: Restore instance ID for the name column
                    if col == 0 and 'instanceId' in item_data and item_data['instanceId'] is not None:
                        new_item.setData(Qt.UserRole + 2, item_data['instanceId'])
                        print(f"[CombatTracker] Set instance ID {item_data['instanceId']} for new_row={new_row}")
                    
                    # Set the item in the table
                    self.initiative_table.setItem(new_row, col, new_item)
            
            # Update current selection and turn if needed
            if current_row >= 0 and current_row < row_count:
                new_current_row = row_map.get(current_row, 0)
                self.initiative_table.setCurrentCell(new_current_row, 0)
            
            if current_turn is not None and current_turn >= 0 and current_turn < row_count:
                self._current_turn = row_map.get(current_turn, 0)
            
            # NEW: Update the self.combatants dictionary to keep instance IDs aligned
            if hasattr(self, 'combatants') and isinstance(self.combatants, dict):
                new_combatants = {}
                for old_row, combatant_data in self.combatants.items():
                    if old_row in row_map:
                        new_row = row_map[old_row]
                        new_combatants[new_row] = combatant_data
                        
                        # If combatant_data is a dictionary, update its instance_id
                        if isinstance(combatant_data, dict):
                            instance_id = monster_instance_ids.get(old_row, f"combatant_{old_row}")
                            combatant_data['instance_id'] = instance_id
                            print(f"[CombatTracker] Updated instance_id in combatants dict: {old_row} -> {new_row} with ID {instance_id}")
                
                self.combatants = new_combatants
            
            # Verify HP and AC values after sorting
            post_sort_values = {}
            for row in range(row_count):
                name_item = self.initiative_table.item(row, 0)
                hp_item = self.initiative_table.item(row, 2)
                ac_item = self.initiative_table.item(row, 4)
                
                name = name_item.text() if name_item else f"Row {row}"
                hp = hp_item.text() if hp_item else "?"
                ac = ac_item.text() if ac_item else "?"
                instance_id = name_item.data(Qt.UserRole + 2) if name_item else f"combatant_{row}"
                
                post_sort_values[name] = {"hp": hp, "ac": ac, "instance_id": instance_id}
            
            # Compare pre and post sort values
            for name, pre_values in pre_sort_values.items():
                post_values = post_sort_values.get(name, {"hp": "MISSING", "ac": "MISSING", "instance_id": "MISSING"})
                
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
                    
                # Check instance ID
                pre_instance_id = pre_values["instance_id"]
                post_instance_id = post_values["instance_id"]
                if pre_instance_id != post_instance_id:
                    print(f"[CombatTracker] WARNING: Instance ID changed during sort for {name}: {pre_instance_id} -> {post_instance_id}")
                else:
                    print(f"[CombatTracker] Instance ID preserved for {name}: {pre_instance_id}")

            # At the end of the sort function, add the monster stats verification
            # Schedule verification for all monsters after sorting is complete
            for monster_id, stats in monster_stats.items():
                QTimer.singleShot(100, lambda stats=stats: self._verify_monster_stats(stats))
            
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
                
            # Only sort if the Initiative column (column 1) changed
            if column == 1:
                try:
                    # Validate the initiative value
                    int(item.text()) # Try converting to int
                    if self.initiative_table.rowCount() > 1:
                        self._sort_initiative()
                except (ValueError, TypeError):
                    item.setText("0") # Reset invalid input

            # Handle Max HP changes (column 3) without sorting
            elif column == 3:
                hp_item = self.initiative_table.item(row, 2)
                max_hp_item = self.initiative_table.item(row, 3)
                if hp_item and max_hp_item:
                    try:
                        current_hp = int(hp_item.text())
                        max_hp = int(max_hp_item.text())
                        if current_hp > max_hp:
                            hp_item.setText(str(max_hp))
                    except (ValueError, TypeError):
                        pass # Ignore if values aren't integers

            # Update combatant data dictionary if it exists
            if row in self.combatants:
                self._update_combatant_hp_and_status(row)
        
        finally:
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
                pass
    
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
        
        # --- Ensure row selection before menu pops ---
        # If the right‑clicked row is not already selected, clear any previous
        # selection (to avoid unintended multi‑row edits) and select this row.
        if row not in [idx.row() for idx in self.initiative_table.selectionModel().selectedRows()]:
            self.initiative_table.clearSelection()
            self.initiative_table.selectRow(row)

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
        
        # Status submenu - Changed to Add Status and Remove Status
        status_menu = menu.addMenu("Add Status")
        status_menu.addAction("Clear All").triggered.connect(lambda: self._clear_statuses())
        
        for condition in CONDITIONS:
            action = status_menu.addAction(condition)
            action.triggered.connect(lambda checked, c=condition: self._add_status(c))
        
        # Get current statuses for the Remove Status menu
        status_item = self.initiative_table.item(row, 5)  # Status is now column 5
        current_statuses = []
        if status_item and status_item.text():
            current_statuses = [s.strip() for s in status_item.text().split(',')]
            
        # Only show Remove Status menu if there are statuses to remove
        if current_statuses:
            remove_status_menu = menu.addMenu("Remove Status")
            for status in current_statuses:
                action = remove_status_menu.addAction(status)
                action.triggered.connect(lambda checked, s=status: self._remove_status(s))
        
        # Concentration toggle
        conc_item = self.initiative_table.item(row, 6)  # Concentration is now column 6
        if conc_item:
            is_concentrating = conc_item.checkState() == Qt.Checked
            conc_action = QAction("Remove Concentration" if is_concentrating else "Add Concentration", self)
            conc_action.triggered.connect(lambda: self._toggle_concentration(row))
            menu.addAction(conc_action)
        
        # Show the menu
        menu.exec_(self.initiative_table.mapToGlobal(position))
        
    def _add_status(self, status):
        """Add a status condition to selected combatants without removing existing ones"""
        # Get selected rows
        selected_rows = set(index.row() for index in self.initiative_table.selectedIndexes())
        if not selected_rows:
            return
        
        # Apply status to each selected row
        for row in selected_rows:
            if row < self.initiative_table.rowCount():
                status_item = self.initiative_table.item(row, 5)  # Status is now column 5
                if status_item:
                    current_statuses = []
                    if status_item.text():
                        current_statuses = [s.strip() for s in status_item.text().split(',')]
                    
                    # Only add if not already present
                    if status not in current_statuses:
                        current_statuses.append(status)
                        status_item.setText(', '.join(current_statuses))
                
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
    
    def _remove_status(self, status):
        """Remove a specific status condition from selected combatants"""
        # Get selected rows
        selected_rows = set(index.row() for index in self.initiative_table.selectedIndexes())
        if not selected_rows:
            return
        
        # Remove status from each selected row
        for row in selected_rows:
            if row < self.initiative_table.rowCount():
                status_item = self.initiative_table.item(row, 5)  # Status is now column 5
                if status_item and status_item.text():
                    current_statuses = [s.strip() for s in status_item.text().split(',')]
                    
                    # Remove the status if present
                    if status in current_statuses:
                        current_statuses.remove(status)
                        status_item.setText(', '.join(current_statuses))
                
                # Log status removal if there's a name
                name_item = self.initiative_table.item(row, 0)
                if name_item:
                    name = name_item.text()
                    
                    # Log status removal
                    self._log_combat_action(
                        "Status Effect", 
                        "DM", 
                        "removed status", 
                        name, 
                        status
                    )
    
    def _clear_statuses(self):
        """Clear all status conditions from selected combatants"""
        # Get selected rows
        selected_rows = set(index.row() for index in self.initiative_table.selectedIndexes())
        if not selected_rows:
            return
        
        # Clear statuses for each selected row
        for row in selected_rows:
            if row < self.initiative_table.rowCount():
                status_item = self.initiative_table.item(row, 5)  # Status is now column 5
                if status_item:
                    status_item.setText("")
                
                # Log status clearing if there's a name
                name_item = self.initiative_table.item(row, 0)
                if name_item:
                    name = name_item.text()
                    
                    # Log status clearing
                    self._log_combat_action(
                        "Status Effect", 
                        "DM", 
                        "cleared all statuses from", 
                        name
                    )
    
    # Keep _set_status for backwards compatibility but modify it to call _add_status
    def _set_status(self, status):
        """Apply a status condition to selected combatants (legacy method)"""
        if not status:
            # If empty status, clear all
            self._clear_statuses()
        else:
            # Otherwise add the status
            self._add_status(status)
    
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
                # Reset HP to max using the Max HP value from column 3
                hp_item = self.initiative_table.item(row, 2)
                max_hp_item = self.initiative_table.item(row, 3)
                
                if hp_item and max_hp_item:
                    max_hp_text = max_hp_item.text()
                    if max_hp_text and max_hp_text != "None":
                        hp_item.setText(max_hp_text)
                    else:
                        # Fallback if max_hp is None or empty
                        hp_item.setText("10") 
                        
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
    
    # Custom event classes for safe thread communication
    class _ProgressEvent(QEvent):
        def __init__(self, message):
            super().__init__(QEvent.Type(QEvent.User + 100))
            self.message = message
    
    class _ErrorEvent(QEvent):
        def __init__(self, title, message):
            super().__init__(QEvent.Type(QEvent.User + 101))
            self.title = title
            self.message = message
    
    class _ClearLogEvent(QEvent):
        def __init__(self):
            super().__init__(QEvent.Type(QEvent.User + 102))
    
    class _AddInitialStateEvent(QEvent):
        def __init__(self, combat_state):
            super().__init__(QEvent.Type(QEvent.User + 103))
            self.combat_state = combat_state
    
    class _LogDiceEvent(QEvent):
        def __init__(self, expr, result):
            super().__init__(QEvent.Type(QEvent.User + 104))
            self.expr = expr
            self.result = result
    
    class _ProcessResultEvent(QEvent):
        def __init__(self, result, error):
            super().__init__(QEvent.Type(QEvent.User + 105))
            self.result = result
            self.error = error
    
    class _UpdateUIEvent(QEvent):
        def __init__(self, turn_state):
            super().__init__(QEvent.Type(QEvent.User + 106))
            self.turn_state = turn_state
    
    class _SetResolvingEvent(QEvent):
        def __init__(self, is_resolving):
            super().__init__(QEvent.Type(QEvent.User + 107))
            self.is_resolving = is_resolving
    
    class _ConnectSignalEvent(QEvent):
        def __init__(self):
            super().__init__(QEvent.Type(QEvent.User + 108))
    
    class _UpdateButtonEvent(QEvent):
        def __init__(self, text, enabled=True):
            super().__init__(QEvent.Type(QEvent.User + 109))
            self.text = text
            self.enabled = enabled
    
    def _fast_resolve_combat(self):
        """Use LLM to resolve the current combat encounter (turn-by-turn, rule-correct)."""
        import traceback
        import threading
        import gc
        from PySide6.QtWidgets import QApplication, QMessageBox

        # First, update UI to indicate processing is happening
        self.fast_resolve_button.setEnabled(False)
        self.fast_resolve_button.setText("Initializing...")
        QApplication.processEvents()  # Force immediate UI update
        
        # Add a safety timer that will reset the button after 5 minutes regardless
        # of whether the combat resolver signals completion
        safety_timer = QTimer(self)
        safety_timer.setSingleShot(True)
        safety_timer.timeout.connect(lambda: self._reset_resolve_button("Fast Resolve", True))
        safety_timer.start(300000)  # 5 minutes in milliseconds
        
        # Add a second backup timer with shorter timeout (2 minutes)
        backup_timer = QTimer(self)
        backup_timer.setSingleShot(True)
        backup_timer.timeout.connect(lambda: self._check_and_reset_button())
        backup_timer.start(120000)  # 2 minutes in milliseconds
        
        # Store timers for cancellation
        self._safety_timer = safety_timer
        self._backup_timer = backup_timer
        
        # Force garbage collection before starting
        gc.collect()
        
        # Define the main processing function to run in a separate thread
        def setup_and_start_combat():
            try:
                # Step 1: Validate we have combatants
                has_monster = has_player = False
                for row in range(self.initiative_table.rowCount()):
                    type_item = self.initiative_table.item(row, 7)  # Type is now column 7
                    if type_item:
                        combatant_type = type_item.text().lower()
                        if combatant_type == "monster":
                            has_monster = True
                        elif combatant_type in ["character", "pc", "npc"]:
                            has_player = True
                
                # Update progress on UI thread
                QApplication.instance().postEvent(self, CombatTrackerPanel._ProgressEvent("Validating combatants..."))
                
                # Handle validation errors
                if not has_monster and not has_player:
                    QApplication.instance().postEvent(self, CombatTrackerPanel._ErrorEvent(
                        "Cannot Start Combat", 
                        "You need at least one combatant (monster or character) to run combat."
                    ))
                    return
                    
                elif not has_monster and has_player:
                    QApplication.instance().postEvent(self, CombatTrackerPanel._ErrorEvent(
                        "Cannot Start Combat", 
                        "You need at least one monster to run combat against player characters.\n\n" +
                        "Add monsters from the Monster Panel."
                    ))
                    return
                
                # Step 2: Gather combat state
                QApplication.instance().postEvent(self, CombatTrackerPanel._ProgressEvent("Gathering combat data..."))
                combat_state = self._gather_combat_state()
                if not combat_state or not combat_state.get("combatants"):
                    QApplication.instance().postEvent(self, CombatTrackerPanel._ErrorEvent(
                        "Fast Resolve", 
                        "No combatants in the tracker to resolve."
                    ))
                    return
                
                # Step 3: Clear and prepare the combat log
                QApplication.instance().postEvent(self, CombatTrackerPanel._ProgressEvent("Preparing combat log..."))
                QApplication.instance().postEvent(self, CombatTrackerPanel._ClearLogEvent())
                
                # Step 4: Add initial combat state to log (this will be done on the UI thread)
                QApplication.instance().postEvent(self, CombatTrackerPanel._AddInitialStateEvent(combat_state))
                
                # Step 5: Setup the dice roller function that will be passed to the resolver
                def dice_roller(expr):
                    """Parse and roll a dice expression like '1d20+5'. Returns the integer result."""
                    try:
                        import re, random
                        match = re.match(r"(\d*)d(\d+)([+-]\d+)?", expr.replace(' ', ''))
                        if not match:
                            return 0
                        num, die, mod = match.groups()
                        num = int(num) if num else 1
                        die = int(die)
                        mod = int(mod) if mod else 0
                        total = sum(random.randint(1, die) for _ in range(num)) + mod
                        
                        # Log the roll to the combat log via a custom event
                        QApplication.instance().postEvent(self, CombatTrackerPanel._LogDiceEvent(expr, total))
                        return total
                    except Exception as e:
                        print(f"[CombatTracker] Error in dice roller: {e}")
                        return 10  # Provide a reasonable default
                
                # Step 6: Setup completion callback
                def completion_callback(result, error):
                    """Callback for resolution completion if signals aren't working"""
                    print(f"[CombatTracker] Manual completion callback called with result={bool(result)}, error={bool(error)}")
                    
                    # Forward to our UI handler via a custom event - safest approach
                    QApplication.instance().postEvent(self, CombatTrackerPanel._ProcessResultEvent(result, error))
                    
                    # Directly update button state via event
                    QApplication.instance().postEvent(self, CombatTrackerPanel._UpdateButtonEvent("Fast Resolve", True))
                    print("[CombatTracker] Posted button update event")
                    
                    # Create a very short timer as a last resort
                    reset_timer = QTimer()
                    reset_timer.setSingleShot(True)
                    reset_timer.timeout.connect(lambda: self._check_and_reset_button())
                    reset_timer.start(1000)  # 1 second delay
                
                # Step 7: Setup turn callback
                def manual_turn_callback(turn_state):
                    """Callback for per-turn updates if signals aren't working"""
                    print(f"[CombatTracker] Manual turn update callback received data with "
                          f"{len(turn_state.get('combatants', []))} combatants")
                    # Forward to our wrapper method via a custom event
                    QApplication.instance().postEvent(self, CombatTrackerPanel._UpdateUIEvent(turn_state))
                
                # Step 8: Start the actual combat resolution
                QApplication.instance().postEvent(self, CombatTrackerPanel._SetResolvingEvent(True))
                
                # Setup signal connection (done on UI thread)
                QApplication.instance().postEvent(self, CombatTrackerPanel._ConnectSignalEvent())
                
                # Update UI to show we're now resolving
                QApplication.instance().postEvent(self, CombatTrackerPanel._UpdateButtonEvent("Resolving...", False))
                
                # Step 9: Call the resolver with our setup
                resolver_callable = self.app_state.combat_resolver.resolve_combat_turn_by_turn
                accepts_turn_callback = 'turn_update_callback' in resolver_callable.__code__.co_varnames

                # Update UI with final preparation status
                QApplication.instance().postEvent(self, CombatTrackerPanel._ProgressEvent("Starting combat resolution..."))
                
                # Call with appropriate arguments based on what the resolver supports
                if accepts_turn_callback:
                    print("[CombatTracker] Resolver supports turn_update_callback, using it")
                    # This resolver takes a turn callback directly
                    self.app_state.combat_resolver.resolve_combat_turn_by_turn(
                        combat_state,
                        dice_roller,
                        completion_callback,  # Use our manual callback
                        manual_turn_callback  # Pass the callback for turns
                    )
                else:
                    print("[CombatTracker] Using standard resolver with update_ui_callback, relying on signals")
                    # Standard resolver - use it with our update_ui_wrapper and rely on signals
                    self.app_state.combat_resolver.resolve_combat_turn_by_turn(
                        combat_state,
                        dice_roller,
                        completion_callback,  # Pass our manual callback for backup
                        self._update_ui_wrapper  # This might be treated as update_ui_callback depending on interface
                    )
                    
            except Exception as e:
                traceback.print_exc()
                # If any error occurs, send an error event
                QApplication.instance().postEvent(self, CombatTrackerPanel._ErrorEvent(
                    "Error", 
                    f"Failed to start combat resolution: {str(e)}"
                ))
        
        # Start the setup in a background thread
        setup_thread = threading.Thread(target=setup_and_start_combat)
        setup_thread.daemon = True  # Allow app to exit even if thread is running
        setup_thread.start()
    
    # Override event handler to process our custom events
    def event(self, event):
        """Handle custom events posted to our panel"""
        from PySide6.QtWidgets import QApplication, QMessageBox
        
        if event.type() == QEvent.Type(QEvent.User + 1):
            # This is our UpdateUIEvent for JSON
            try:
                self._update_ui(event.json_data)
                return True
            except Exception as e:
                print(f"[CombatTracker] Error in event handler UI update: {e}")
                return False
        elif event.type() == QEvent.Type(QEvent.User + 100):
            # Progress event
            self.fast_resolve_button.setText(event.message)
            QApplication.processEvents()
            return True
        elif event.type() == QEvent.Type(QEvent.User + 101):
            # Error event
            self._reset_resolve_button("Fast Resolve", True)
            QMessageBox.critical(self, event.title, event.message)
            return True
        elif event.type() == QEvent.Type(QEvent.User + 102):
            # Clear log event
            self.combat_log_text.clear()
            return True
        elif event.type() == QEvent.Type(QEvent.User + 103):
            # Add initial state event
            self._add_initial_combat_state_to_log(event.combat_state)
            return True
        elif event.type() == QEvent.Type(QEvent.User + 104):
            # Log dice event
            self._log_combat_action(
                "Dice", 
                "AI", 
                f"rolled {event.expr}", 
                result=f"Result: {event.result}"
            )
            return True
        elif event.type() == QEvent.Type(QEvent.User + 105):
            # Process result event
            self._process_resolution_ui(event.result, event.error)
            return True
        elif event.type() == QEvent.Type(QEvent.User + 106):
            # Update UI event
            self._update_ui_wrapper(event.turn_state)
            return True
        elif event.type() == QEvent.Type(QEvent.User + 107):
            # Set resolving event
            self._is_resolving_combat = event.is_resolving
            print(f"[CombatTracker] Setting _is_resolving_combat = {event.is_resolving}")
            return True
        elif event.type() == QEvent.Type(QEvent.User + 108):
            # Connect signal event
            try:
                # Disconnect any existing connection first to be safe
                try:
                    self.app_state.combat_resolver.resolution_complete.disconnect(self._process_resolution_ui)
                    print("[CombatTracker] Disconnected existing signal connection")
                except Exception:
                    # Connection might not exist yet, which is fine
                    pass
                
                # Connect the signal
                self.app_state.combat_resolver.resolution_complete.connect(self._process_resolution_ui)
                print("[CombatTracker] Successfully connected resolution_complete signal")
            except Exception as conn_error:
                print(f"[CombatTracker] Failed to connect signal: {conn_error}")
            return True
        elif event.type() == QEvent.Type(QEvent.User + 109):
            # Update button event
            self._reset_resolve_button(event.text, event.enabled)
            return True
            
        return super().event(event)

    # This method remains, but it's the wrapper for thread-safe UI updates
    def _update_ui_wrapper(self, turn_state):
        """Thread-safe wrapper to update UI during combat (used by the resolver)"""
        # Serialize the turn state to JSON
        try:
            import json
            import traceback
            from PySide6.QtCore import QMetaObject, Qt, Q_ARG
            from PySide6.QtWidgets import QApplication
            from PySide6.QtCore import QEvent
            
            # Debug count of combatants
            combatants = turn_state.get("combatants", [])
            print(f"[CombatTracker] _update_ui_wrapper called with turn state containing {len(combatants)} combatants")
            
            # Ensure the turn state is serializable by sanitizing it
            def sanitize_object(obj):
                """Recursively sanitize an object to ensure it's JSON serializable"""
                if isinstance(obj, dict):
                    return {str(k): sanitize_object(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [sanitize_object(item) for item in obj]
                elif isinstance(obj, (int, float, bool, str)) or obj is None:
                    return obj
                else:
                    return str(obj)  # Convert any other types to strings
            
            # Apply sanitization
            sanitized_turn_state = sanitize_object(turn_state)
            
            # Serialize to JSON with error handling
            try:
                json_string = json.dumps(sanitized_turn_state)
                print(f"[CombatTracker] Successfully serialized turn state to JSON ({len(json_string)} chars)")
            except Exception as e:
                print(f"[CombatTracker] Error serializing turn state: {e}")
                traceback.print_exc()
                # Create a minimal valid JSON object as fallback
                json_string = json.dumps({
                    "round": turn_state.get("round", 1),
                    "current_turn_index": turn_state.get("current_turn_index", 0),
                    "combatants": []
                })
            
            # Pass the JSON string as an argument
            print("[CombatTracker] Using QMetaObject.invokeMethod for thread-safe UI update")
            try:
                result = QMetaObject.invokeMethod(
                    self, 
                    '_update_ui', 
                    Qt.QueuedConnection,  # Ensures it queues in the main thread's event loop
                    Q_ARG(str, json_string)  # Pass JSON string instead of dict/object
                )
                if not result:
                    print("[CombatTracker] WARNING: QMetaObject.invokeMethod returned False, trying alternative method")
                    # Try direct call with a slight delay (as fallback)
                    def delayed_update():
                        try:
                            self._update_ui(json_string)
                        except Exception as e:
                            print(f"[CombatTracker] Error in delayed update: {e}")
                    
                    # Schedule for execution in main thread after a slight delay
                    QApplication.instance().postDelayed(delayed_update, 100)
                
                # Force process events to ensure UI updates (helps with thread sync issues)
                QApplication.processEvents()
                
            except Exception as e:
                print(f"[CombatTracker] Critical error in invokeMethod: {e}")
                traceback.print_exc()
                # As a last resort, try to post a user event to update UI
                try:
                    # Create a custom event 
                    class UpdateUIEvent(QEvent):
                        def __init__(self, json_data):
                            super().__init__(QEvent.Type(QEvent.User + 1))
                            self.json_data = json_data
                    
                    # Post the event to our panel
                    QApplication.postEvent(self, UpdateUIEvent(json_string))
                    print("[CombatTracker] Posted custom event as last resort for UI update")
                except Exception as e2:
                    print(f"[CombatTracker] All UI update methods failed: {e2}")
                    traceback.print_exc()
                    
        except Exception as e:
            print(f"[CombatTracker] Unhandled error in _update_ui_wrapper: {e}")
            traceback.print_exc()

    # Also add a custom event handler to handle our backup approach
    def _event_duplicate_backup(self, event):
        """Handle custom events posted to our panel"""
        if event.type() == QEvent.Type(QEvent.User + 1):
            # This is our UpdateUIEvent
            try:
                self._update_ui(event.json_data)
                return True
            except Exception as e:
                print(f"[CombatTracker] Error in event handler UI update: {e}")
                return False
        return super().event(event)

    # Make the actual UI update function a slot callable by the wrapper
    # The slot now accepts a string (JSON)
    @Slot(str)
    def _update_ui(self, turn_state_json):
        """Update UI after each turn (runs in main thread via _update_ui_wrapper)."""
        # Deserialize the JSON string back into a dictionary
        try:
            # First check if the JSON string is valid
            if not turn_state_json or turn_state_json == '{}':
                print(f"[CombatTracker] Error: Empty or invalid turn_state_json")
                return
            
            # Clean the JSON string to remove any invalid characters
            import re
            turn_state_json = re.sub(r'[\x00-\x1F\x7F]', '', turn_state_json)
            
            # Additional safety for broken JSON
            if not turn_state_json.strip().startswith('{'):
                print(f"[CombatTracker] Error: Invalid JSON format, does not start with '{{'. First 100 chars: {turn_state_json[:100]}")
                # Try to extract a JSON object if present
                json_match = re.search(r'(\{.*\})', turn_state_json)
                if json_match:
                    turn_state_json = json_match.group(1)
                    print(f"[CombatTracker] Extracted potential JSON object: {turn_state_json[:50]}...")
                else:
                    # Create a minimal valid state
                    turn_state_json = '{}'
            
            # Attempt to parse JSON
            import json
            import traceback
            from PySide6.QtWidgets import QApplication
            turn_state = json.loads(turn_state_json)
            if not isinstance(turn_state, dict):
                print(f"[CombatTracker] Error: Deserialized turn_state is not a dict: {type(turn_state)}")
                turn_state = {} # Use empty dict on error
        except json.JSONDecodeError as e:
            print(f"[CombatTracker] Error deserializing turn_state JSON: {e}")
            print(f"[CombatTracker] JSON string causing error (first 100 chars): {turn_state_json[:100]}")
            # Fallback to an empty dict
            turn_state = {} 
        except Exception as e:
            print(f"[CombatTracker] Unexpected error in deserializing turn_state: {e}")
            traceback.print_exc()
            # Fallback to an empty dict
            turn_state = {} 
            
        # Existing logic from the original update_ui function
        try:
            # Extract state
            round_num = turn_state.get("round", 1)
            current_idx = turn_state.get("current_turn_index", 0)
            combatants = turn_state.get("combatants", [])
            latest_action = turn_state.get("latest_action", {})
            
            # Debug logging
            print(f"\n[CombatTracker] DEBUG: Received updated turn state with {len(combatants)} combatants")
            
            # Update round counter
            self.round_spin.setValue(round_num)
            
            # Update current turn highlight
            self.current_turn = current_idx
            self._update_highlight()
            
            # Apply combatant updates to the table
            if combatants:
                # Make a copy of combatants to avoid any reference issues
                import copy
                combatants_copy = copy.deepcopy(combatants)
                self._update_combatants_in_table(combatants_copy)
                
                # Force UI refresh after table update
                QApplication.processEvents()
            
            # Log the action to combat log
            if latest_action:
                # Extract action details
                actor = latest_action.get("actor", "Unknown")
                action = latest_action.get("action", "")
                result = latest_action.get("result", "")
                dice = latest_action.get("dice", [])
                
                # Create a descriptive result string
                result_str = result
                dice_summary = ""
                if dice:
                    dice_strs = [f"{d.get('purpose', 'Roll')}: {d.get('expression', '')} = {d.get('result', '')}" 
                                for d in dice]
                    dice_summary = "\n".join(dice_strs)
                    self._log_combat_action(
                        "Turn", 
                        actor, 
                        action, 
                        result=f"{result}\n\nDice Rolls:\n{dice_summary}"
                    )
                else:
                    self._log_combat_action(
                        "Turn", 
                        actor, 
                        action, 
                        result=result
                    )
                
                # Update the combat log with high contrast colors - use the persistent log instead of popup
                turn_text = f"<div style='margin-bottom:10px;'>"
                turn_text += f"<h4 style='color:#000088; margin:0;'>Round {round_num} - {actor}'s Turn:</h4>"
                turn_text += f"<p style='color:#000000; margin-top:5px;'>{action}</p>"
                if result:
                    turn_text += f"<p style='color:#000000; margin-top:5px;'><strong>Result:</strong> {result}</p>"
                if dice_summary:
                    dice_html = dice_summary.replace('\n', '<br>')
                    turn_text += f"<p style='color:#000000; margin-top:5px;'><strong>Dice:</strong><br>{dice_html}</p>"
                turn_text += f"<hr style='border:1px solid #cccccc; margin:10px 0;'></div>"
                
                # Add to the persistent combat log
                current_text = self.combat_log_text.toHtml()
                if "Combat Concluded" in current_text:
                    # Previous combat summary exists, clear it and start fresh
                    self.combat_log_text.clear()
                    
                # Append the new turn text
                self.combat_log_text.append(turn_text)
                
                # Ensure cursor is at the end
                cursor = self.combat_log_text.textCursor()
                cursor.movePosition(QTextCursor.End)
                self.combat_log_text.setTextCursor(cursor)
                
                # Scroll to the bottom to see latest entries
                scrollbar = self.combat_log_text.verticalScrollBar()
                scrollbar.setValue(scrollbar.maximum())
                
                # Force UI update after appending to combat log
                QApplication.processEvents()
            
            # Release any references to copied data
            combatants_copy = None
            latest_action = None
            
            # Process any UI events to ensure the table updates
            QApplication.processEvents()
            
            # Force garbage collection
            import gc
            gc.collect()
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"[CombatTracker] Error in UI update: {str(e)}")

            # Force UI refresh even on error
            from PySide6.QtWidgets import QApplication
            QApplication.processEvents()

    def _add_initial_combat_state_to_log(self, combat_state):
        """Add initial combat state to the log at the start of combat"""
        # Clear any previous combat log content
        if hasattr(self, 'combat_log_text') and self.combat_log_text:
            # Check if we already have a "Combat Concluded" message
            current_text = self.combat_log_text.toHtml()
            if "Combat Concluded" in current_text:
                # Previous combat summary exists, clear it
                self.combat_log_text.clear()
            
        # Create summary HTML with better contrast colors
        html = "<h3 style='color: #000088;'>Initial Combat State</h3>"
        html += "<p style='color: #000000;'>Combatants in initiative order:</p>"
        html += "<ul style='color: #000000;'>"
        
        # Get combatants and build a summary
        combatants = combat_state.get("combatants", [])
        if not combatants:
            html += "<li>No combatants found</li>"
            html += "</ul>"
            html += "<p style='color: #000000;'><strong>Combat cannot begin with no combatants.</strong></p>"
            
            # Add to local log
            self.combat_log_text.append(html)
            
            # Force UI update
            from PySide6.QtWidgets import QApplication
            QApplication.processEvents()
            return
            
        # Sort by initiative
        try:
            sorted_combatants = sorted(combatants, key=lambda c: -c.get("initiative", 0))
        except Exception as e:
            print(f"[CombatTracker] Error sorting combatants: {e}")
            sorted_combatants = combatants
        
        for c in sorted_combatants:
            name = c.get("name", "Unknown")
            hp = c.get("hp", 0)
            max_hp = c.get("max_hp", hp)
            ac = c.get("ac", 10)
            initiative = c.get("initiative", 0)
            combatant_type = c.get("type", "unknown")
            
            # Different display for monsters vs characters with better styling
            if combatant_type.lower() == "monster":
                html += f"<li><strong style='color: #880000;'>{name}</strong> (Monster) - Initiative: {initiative}, AC: {ac}, HP: {hp}/{max_hp}</li>"
            else:
                html += f"<li><strong style='color: #000088;'>{name}</strong> (PC) - Initiative: {initiative}, AC: {ac}, HP: {hp}/{max_hp}</li>"
                
        html += "</ul>"
        html += "<p style='color: #000000;'><strong>Combat begins now!</strong></p>"
        html += "<hr style='border: 1px solid #000088;'>"
        
        # Add to the log
        self.combat_log_text.append(html)
        
        # Ensure cursor is at the end and scroll to the bottom
        cursor = self.combat_log_text.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.combat_log_text.setTextCursor(cursor)
        
        scrollbar = self.combat_log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        
        # Force UI update
        from PySide6.QtWidgets import QApplication
        QApplication.processEvents()

    def _create_live_combat_log(self):
        """Create a live combat log widget that displays during combat resolution"""
        try:
            from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QDialogButtonBox, QPushButton
            
            # Create the dialog
            self.combat_log_widget = QDialog(self)
            self.combat_log_widget.setWindowTitle("Combat In Progress")
            self.combat_log_widget.setWindowFlags(
                self.combat_log_widget.windowFlags() | Qt.Tool | Qt.WindowStaysOnTopHint
            )
            self.combat_log_widget.setMinimumSize(500, 500)
            
            # Create layout
            layout = QVBoxLayout(self.combat_log_widget)
            
            # Add text display for combat log with improved contrast
            self.combat_log_widget.log_text = QTextEdit()
            self.combat_log_widget.log_text.setReadOnly(True)
            self.combat_log_widget.log_text.setStyleSheet("""
                QTextEdit { 
                    background-color: white;
                    color: #000000;
                    font-family: Arial, sans-serif;
                    font-size: 14px;
                    font-weight: 500;
                }
            """)
            layout.addWidget(self.combat_log_widget.log_text)
            
            # Add header text
            header_text = "<h2 style='color: #000088;'>Combat In Progress</h2>"
            header_text += "<p style='color: #000000;'><strong>Watch as the battle unfolds turn by turn! Combat details will appear here and in popups.</strong></p>"
            header_text += "<hr style='border: 1px solid #000088;'>"
            self.combat_log_widget.log_text.setHtml(header_text)
            
            # Add a close button that just hides the dialog (combat continues)
            btn_box = QDialogButtonBox()
            close_btn = QPushButton("Hide Log")
            close_btn.clicked.connect(self.combat_log_widget.hide)
            btn_box.addButton(close_btn, QDialogButtonBox.ActionRole)
            layout.addWidget(btn_box)
            
            # Add create_entry method to make it compatible with the combat log interface
            def create_entry(category=None, actor=None, action=None, target=None, result=None, round=None, turn=None):
                # Create a simple entry representation
                entry = {
                    "category": category,
                    "actor": actor,
                    "action": action,
                    "target": target,
                    "result": result,
                    "round": round,
                    "turn": turn
                }
                # Format the entry into HTML
                html = f"<p><strong>{actor}:</strong> {action}"
                if target:
                    html += f" <strong>{target}</strong>"
                if result:
                    html += f" - {result}"
                html += "</p>"
                # Add it to the log text if possible
                if hasattr(self.combat_log_widget, 'log_text'):
                    self.combat_log_widget.log_text.append(html)
                return entry
                
            # Add the method to the widget
            self.combat_log_widget.create_entry = create_entry
            
        except Exception as e:
            print(f"[CombatTracker] Error creating live combat log: {e}")
            self.combat_log_widget = None

    @Slot(str, str, str, str, str)
    def _show_turn_result_slot(self, actor, round_num, action, result, dice_summary):
        """
        Show turn result from the main thread (safe way to show dialogs).
        This is connected to the show_turn_result_signal.
        """
        # Ensure we have content to display
        if not action and not result:
            print("[CombatTracker] Warning: Empty turn result, not showing dialog")
            return
            
        # Build message with available information
        message = ""
        if action:
            message += f"Action: {action}\n\n"
        if result:
            message += f"Result: {result}\n\n"
        if dice_summary:
            message += f"Dice Rolls:\n{dice_summary}"
            
        # Ensure the message is not empty
        if not message.strip():
            message = "No action taken this turn."
            
        # Use a non-modal dialog so it doesn't block the UI updates
        from PySide6.QtWidgets import QMessageBox
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(f"Turn: {actor} (Round {round_num})")
        msg_box.setText(message)
        msg_box.setStandardButtons(QMessageBox.Ok)
        msg_box.setModal(False)  # Make it non-modal
        msg_box.show()

    def _show_turn_result(self, actor, round_num, action, result, dice_summary=None):
        """This method is no longer used directly - we use signals instead"""
        # Emit the signal to show the result from the main thread
        self.show_turn_result_signal.emit(actor, str(round_num), action, result, dice_summary or "")

    def _update_combatants_in_table(self, combatants):
        """
        Update the initiative table with new combatant data.
        
        Args:
            combatants: List of combatant dictionaries with updated values
        """
        print(f"\n[CombatTracker] DEBUG: Updating table with HP values from resolver:")
        for c in combatants:
            print(f"[CombatTracker] DEBUG: Incoming update for {c.get('name', 'Unknown')}: HP {c.get('hp', 'N/A')}")
            
        # Collect the combatants by name for easier lookup
        combatants_by_name = {}
        for combatant in combatants:
            name = combatant.get("name", "")
            if name and name not in ["Nearest Enemy", "Enemy", "Target"] and "Enemy" not in name:
                combatants_by_name[name] = combatant
        
        # Block signals during programmatic updates
        self.initiative_table.blockSignals(True)
        try:
            # Loop through rows in the table and update with corresponding combatant data
            for row in range(self.initiative_table.rowCount()):
                name_item = self.initiative_table.item(row, 0)
                if not name_item:
                    continue
                    
                name = name_item.text()
                if not name or name not in combatants_by_name:
                    continue
                
                # Get the corresponding combatant data
                combatant = combatants_by_name[name]
                
                # Update HP
                if "hp" in combatant:
                    hp_item = self.initiative_table.item(row, 2)
                    if hp_item:
                        old_hp = hp_item.text()
                        hp_value = combatant["hp"]
                        
                        # Track max_hp for consistency check
                        max_hp_item = self.initiative_table.item(row, 3)
                        max_hp = 0
                        if max_hp_item and max_hp_item.text():
                            try:
                                max_hp = int(max_hp_item.text())
                            except (ValueError, TypeError):
                                pass
                        
                        try:
                            # Convert to integer - use clear, strict parsing here
                            if isinstance(hp_value, int):
                                new_hp = hp_value
                                print(f"[CombatTracker] DEBUG: Integer HP value {hp_value} for {name}")
                            elif isinstance(hp_value, str) and hp_value.strip().isdigit():
                                new_hp = int(hp_value.strip())
                                print(f"[CombatTracker] DEBUG: String HP value '{hp_value}' converted to {new_hp} for {name}")
                            else:
                                # More complex string - extract first integer
                                import re
                                match = re.search(r'\d+', str(hp_value))
                                if match:
                                    new_hp = int(match.group(0))
                                    print(f"[CombatTracker] DEBUG: Extracted HP value {new_hp} from complex string '{hp_value}' for {name}")
                                else:
                                    # Keep existing HP if parsing fails
                                    new_hp = int(old_hp) if old_hp.isdigit() else 0
                                    print(f"[CombatTracker] DEBUG: Failed to parse HP from '{hp_value}', keeping {new_hp} for {name}")
                                
                            # Ensure HP is not greater than max_hp (if max_hp is known and positive)
                            if max_hp > 0 and "max_hp" not in combatant and new_hp > max_hp:
                                print(f"[CombatTracker] WARNING: HP value {new_hp} exceeds max_hp {max_hp} for {name}, setting HP = max_hp")
                                new_hp = max_hp
                                
                            # Set HP in table
                            if str(new_hp) != old_hp:
                                hp_item.setText(str(new_hp))
                                print(f"[CombatTracker] Updated {name} HP from {old_hp} to {new_hp}")
                                
                                # Also update self.combatants dictionary if this row is in it
                                if row in self.combatants and isinstance(self.combatants[row], dict):
                                    self.combatants[row]['current_hp'] = new_hp
                                    print(f"[CombatTracker] Updated internal combatants dictionary for {name}: HP = {new_hp}")
                        except Exception as e:
                            print(f"[CombatTracker] Error processing HP update for {name}: {e}")
                
                # Update status (this code remains the same)
                if "status" in combatant:
                    status_item = self.initiative_table.item(row, 5)
                    if status_item:
                        old_status = status_item.text()
                        new_status = combatant["status"]
                        if old_status != new_status:
                            status_item.setText(new_status)
                            print(f"[CombatTracker] Updated {name} status from '{old_status}' to '{new_status}'")
                
                # Update concentration if present
                if "concentration" in combatant:
                    conc_item = self.initiative_table.item(row, 6)
                    if conc_item:
                        new_state = Qt.Checked if combatant["concentration"] else Qt.Unchecked
                        if conc_item.checkState() != new_state:
                            conc_item.setCheckState(new_state)
                
                # Handle death saves if present
                if "death_saves" in combatant:
                    # Store for later tracking
                    self.death_saves[row] = combatant["death_saves"]
                    
                    # Display in status (if not already shown)
                    status_item = self.initiative_table.item(row, 5)
                    if status_item:
                        current_status = status_item.text()
                        successes = combatant["death_saves"].get("successes", 0)
                        failures = combatant["death_saves"].get("failures", 0)
                        
                        # If status doesn't already mention death saves, add them
                        if "death save" not in current_status.lower():
                            death_saves_text = f"Death Saves: {successes}S/{failures}F"
                            if current_status:
                                new_status = f"{current_status}, {death_saves_text}"
                            else:
                                new_status = death_saves_text
                            status_item.setText(new_status)
                            
                            # Log death save progress
                            self._log_combat_action(
                                "Death Save", 
                                name, 
                                "death saves", 
                                result=f"{successes} successes, {failures} failures"
                            )
        finally:
            # Ensure signals are unblocked
            self.initiative_table.blockSignals(False)
        
        # Ensure the table is updated visually - moved outside the loop
        self.initiative_table.viewport().update()
        from PySide6.QtWidgets import QApplication
        QApplication.processEvents()
    
    def _gather_combat_state(self):
        """Gather the current state of the combat from the table."""
        combatants = []
        
        print(f"\n[CombatTracker] DEBUG: Gathering combat state with current HP values from table:")
        
        for row in range(self.initiative_table.rowCount()):
            # Basic combatant data
            name_item = self.initiative_table.item(row, 0)
            initiative_item = self.initiative_table.item(row, 1)
            hp_item = self.initiative_table.item(row, 2)
            max_hp_item = self.initiative_table.item(row, 3)
            ac_item = self.initiative_table.item(row, 4)
            status_item = self.initiative_table.item(row, 5)
            conc_item = self.initiative_table.item(row, 6)
            type_item = self.initiative_table.item(row, 7)
            
            # Get values or defaults
            name = name_item.text() if name_item else "Unknown"
            initiative = int(initiative_item.text() or "0") if initiative_item else 0
            hp = int(hp_item.text() or "0") if hp_item else 0
            # Get max_hp from specific max_hp column
            max_hp = int(max_hp_item.text() or str(hp)) if max_hp_item else hp
            ac = int(ac_item.text() or "10") if ac_item else 10
            status = status_item.text() if status_item else ""
            concentration = conc_item.checkState() == Qt.Checked if conc_item else False
            combatant_type = type_item.text() if type_item else "unknown"
            
            # Get monster ID from name item if it's a monster
            monster_id = None
            if name_item:
                # Get instance_id regardless of type (both monsters and characters need consistent IDs)
                monster_id = name_item.data(Qt.UserRole + 2)
                
                if not monster_id:
                    # Generate a unique ID if none exists
                    import time
                    import hashlib
                    timestamp = int(time.time())
                    hash_base = f"{name}_{timestamp}_{row}"
                    monster_id = hashlib.md5(hash_base.encode()).hexdigest()[:8]
                    # Store the ID back on the item for future reference
                    name_item.setData(Qt.UserRole + 2, monster_id)
                    print(f"[CombatTracker] Generated new instance ID {monster_id} for {name}")
                else:
                    print(f"[CombatTracker] Using existing instance ID {monster_id} for {name}")
            
            # Debug print current HP values
            print(f"[CombatTracker] DEBUG: Table row {row}: {name} - HP: {hp}/{max_hp} {' (ID: ' + str(monster_id) + ')' if monster_id else ''}")
            
            # Create combatant dictionary
            combatant = {
                "name": name,
                "initiative": initiative,
                "hp": hp,
                "max_hp": max_hp,
                "ac": ac,
                "status": status,
                "concentration": concentration,
                "type": combatant_type,
                "instance_id": monster_id if monster_id else f"combatant_{row}"  # Ensure every combatant has a unique ID
            }
            
            # Add more detailed information if available in the self.combatants dictionary
            if row in self.combatants:
                stored_combatant = self.combatants[row]
                
                # First, ensure the stored combatant has the same instance ID (sync it)
                if isinstance(stored_combatant, dict) and "instance_id" in combatant:
                    # Update the stored combatant's instance_id to match what's in the table
                    stored_combatant["instance_id"] = combatant["instance_id"]
                    
                # Add abilities if available
                if isinstance(stored_combatant, dict):
                    # Only include keys that are useful for combat resolution
                    for key in [
                        "abilities", "skills", "equipment", "features", "spells",
                        "special_traits", "traits", "actions", "legendary_actions",
                        "reactions", "on_death", "on_death_effects", "recharge_abilities",
                        "ability_recharges", "limited_use"
                    ]:
                        if key in stored_combatant:
                            # FIXED: Tag each ability with the monster instance ID to prevent mixing
                            if key in ["actions", "traits", "legendary_actions", "reactions"]:
                                # These are typically lists of dictionaries
                                tagged_abilities = []
                                original_abilities = stored_combatant[key]
                                
                                if isinstance(original_abilities, list):
                                    for ability in original_abilities:
                                        if isinstance(ability, dict):
                                            # Create a copy to avoid modifying the original
                                            ability_copy = ability.copy()
                                            # Add instance ID to the ability
                                            ability_copy["monster_instance_id"] = combatant["instance_id"]
                                            ability_copy["monster_name"] = name
                                            
                                            # Check for monster_source tag
                                            if "monster_source" not in ability_copy:
                                                ability_copy["monster_source"] = name
                                                
                                            tagged_abilities.append(ability_copy)
                                        else:
                                            # Non-dict abilities are simply passed through
                                            tagged_abilities.append(ability)
                                    
                                    # Store the tagged abilities
                                    combatant[key] = tagged_abilities
                                else:
                                    # If not a list, just store as is
                                    combatant[key] = original_abilities
                            elif key == "abilities":
                                # Handle abilities which are typically a dictionary of abilities
                                if isinstance(stored_combatant[key], dict):
                                    tagged_abilities = {}
                                    for ability_name, ability in stored_combatant[key].items():
                                        if isinstance(ability, dict):
                                            # Create a copy to avoid modifying the original
                                            ability_copy = ability.copy()
                                            # Add instance ID to the ability
                                            ability_copy["monster_instance_id"] = combatant["instance_id"]
                                            ability_copy["monster_name"] = name
                                            
                                            # Check for monster_source tag
                                            if "monster_source" not in ability_copy:
                                                ability_copy["monster_source"] = name
                                                
                                            tagged_abilities[ability_name] = ability_copy
                                        else:
                                            # Non-dict abilities are simply passed through
                                            tagged_abilities[ability_name] = ability
                                    
                                    # Store the tagged abilities
                                    combatant[key] = tagged_abilities
                                else:
                                    # If not a dict, just store as is
                                    combatant[key] = stored_combatant[key]
                            else:
                                # For other attributes, copy as is
                                combatant[key] = stored_combatant[key]
                    
                    # If monster and no existing limited_use, create basic recharge placeholders
                    if combatant_type == "monster" and "limited_use" not in combatant:
                        limited_use = {}

                        # Dragons breath weapon
                        if "dragon" in name.lower():
                            limited_use["Breath Weapon"] = "Available (Recharges on 5-6)"

                        if limited_use:
                            combatant["limited_use"] = limited_use
                
                # If it's an object, try to extract useful attributes
                elif hasattr(stored_combatant, "__dict__"):
                    for attr in [
                        "abilities", "skills", "equipment", "features", "spells",
                        "special_traits", "traits", "actions", "legendary_actions",
                        "reactions", "on_death", "on_death_effects", "recharge_abilities",
                        "ability_recharges", "limited_use"
                    ]:
                        if hasattr(stored_combatant, attr):
                            attr_value = getattr(stored_combatant, attr)
                            
                            # FIXED: Tag abilities with monster instance ID
                            if attr in ["actions", "traits", "legendary_actions", "reactions"]:
                                # These are typically lists of objects
                                if isinstance(attr_value, list):
                                    tagged_abilities = []
                                    
                                    for ability in attr_value:
                                        if isinstance(ability, dict):
                                            # Create a copy to avoid modifying the original
                                            ability_copy = ability.copy()
                                            # Add instance ID to the ability
                                            ability_copy["monster_instance_id"] = combatant["instance_id"]
                                            ability_copy["monster_name"] = name
                                            
                                            # Check for monster_source tag
                                            if "monster_source" not in ability_copy:
                                                ability_copy["monster_source"] = name
                                                
                                            tagged_abilities.append(ability_copy)
                                        else:
                                            # Create a dictionary from the object's attributes
                                            ability_dict = {}
                                            for ability_attr in dir(ability):
                                                if not ability_attr.startswith("_") and not callable(getattr(ability, ability_attr)):
                                                    ability_dict[ability_attr] = getattr(ability, ability_attr)
                                            
                                            # Add monster identifier
                                            ability_dict["monster_instance_id"] = combatant["instance_id"]
                                            ability_dict["monster_name"] = name
                                            ability_dict["monster_source"] = name
                                            
                                            tagged_abilities.append(ability_dict)
                                    
                                    # Store the tagged abilities
                                    combatant[attr] = tagged_abilities
                                else:
                                    # If not a list, just store as is
                                    combatant[attr] = attr_value
                            else:
                                # For other attributes, copy as is
                                combatant[attr] = attr_value
            
            combatants.append(combatant)
            
        # FIXED: Add a validation step to ensure no ability mixing
        self._validate_no_ability_mixing(combatants)
            
        return {
            "round": self.current_round,
            "current_turn_index": self.current_turn,
            "combatants": combatants
        }
        
    def _validate_no_ability_mixing(self, combatants):
        """
        Validate that no abilities are mixed between different monster instances.
        This is an additional safety check after the main preparation.
        """
        ability_sources = {}  # Maps ability names to their source monsters
        
        for combatant in combatants:
            combatant_id = combatant.get("instance_id", "unknown")
            combatant_name = combatant.get("name", "Unknown")
            
            # Check each ability-containing attribute
            for ability_type in ["actions", "traits", "legendary_actions", "reactions"]:
                abilities = combatant.get(ability_type, [])
                if not isinstance(abilities, list):
                    continue
                
                for i, ability in enumerate(abilities):
                    if not isinstance(ability, dict):
                        continue
                        
                    ability_name = ability.get("name", f"Unknown_{i}")
                    
                    # Make sure all abilities have the instance ID and source name
                    if "monster_instance_id" not in ability:
                        print(f"[CombatTracker] WARNING: Adding missing instance ID to {ability_name} for {combatant_name}")
                        ability["monster_instance_id"] = combatant_id
                        
                    if "monster_name" not in ability:
                        print(f"[CombatTracker] WARNING: Adding missing monster name to {ability_name} for {combatant_name}")
                        ability["monster_name"] = combatant_name
                        
                    if "monster_source" not in ability:
                        ability["monster_source"] = combatant_name
                    
                    # Track the ability source
                    source_key = f"{ability_name.lower()}"
                    if source_key in ability_sources:
                        # If the ability exists, make sure it comes from the right monster instance
                        previous_source = ability_sources[source_key]
                        if previous_source != combatant_id:
                            # This is a potential mixing situation - check if names match to confirm
                            prev_name = ability.get("monster_name", "Unknown")
                            if prev_name != combatant_name:
                                print(f"[CombatTracker] WARNING: Ability {ability_name} may be mixed between {prev_name} and {combatant_name}")
                                # Ensure this ability is clearly marked with its source for the resolver
                                ability["name"] = f"{combatant_name} {ability_name}"
                    else:
                        # Register this ability with its source
                        ability_sources[source_key] = combatant_id

    def _apply_combat_updates(self, updates):
        """Apply final combatant updates from the resolution result."""
        # Import necessary modules
        import time
        import gc
        from PySide6.QtWidgets import QApplication
        
        # Initialize rows_to_remove and update_summaries
        rows_to_remove = []
        update_summaries = []
        start_time = time.time()

        print(f"[CombatTracker] Applying {len(updates)} combat updates from LLM")
        
        # Ensure the update is a list
        if not isinstance(updates, list):
            print(f"[CombatTracker] Warning: updates is not a list (type: {type(updates)})")
            if isinstance(updates, dict):
                # Convert single dict to list containing one dict
                updates = [updates]
            else:
                # Return empty results for invalid updates
                return 0, ["No valid updates to apply"]
        
        # Skip if empty
        if not updates:
            return 0, ["No updates to apply"]

        # Block signals during updates to prevent unexpected handlers
        self.initiative_table.blockSignals(True)
        try:
            # Process updates with a timeout mechanism
            max_process_time = 5.0  # Max seconds to spend processing updates
            updates_processed = 0
            
            for update_index, update in enumerate(updates):
                # Check processing time limit
                elapsed = time.time() - start_time
                if elapsed > max_process_time:
                    print(f"[CombatTracker] Update processing time limit reached ({elapsed:.1f}s). Processed {updates_processed}/{len(updates)} updates.")
                    update_summaries.append(f"WARNING: Only processed {updates_processed}/{len(updates)} updates due to time limit.")
                    break
                
                # Process update in a try block to handle errors individually
                try:
                    name_to_find = update.get("name")
                    if not name_to_find:
                        continue

                    # Periodically update UI and force GC during long operations
                    if update_index > 0 and update_index % 5 == 0:
                        print(f"[CombatTracker] Processed {update_index}/{len(updates)} updates...")
                        self.initiative_table.blockSignals(False)
                        QApplication.processEvents()
                        self.initiative_table.blockSignals(True)
                        gc.collect()

                    print(f"[CombatTracker] Processing update for {name_to_find}")
                    # Find the row for the combatant
                    found_row = -1
                    for row in range(self.initiative_table.rowCount()):
                        name_item = self.initiative_table.item(row, 0)
                        if name_item and name_item.text() == name_to_find:
                            found_row = row
                            break

                    if found_row != -1:
                        print(f"[CombatTracker] Found {name_to_find} at row {found_row}")
                        # Apply HP update
                        if "hp" in update:
                            hp_item = self.initiative_table.item(found_row, 2)
                            if hp_item:
                                old_hp = hp_item.text()
                                try:
                                    # First try to convert directly to int
                                    if isinstance(update["hp"], int):
                                        new_hp_value = max(0, update["hp"])
                                    elif isinstance(update["hp"], str) and update["hp"].strip().isdigit():
                                        new_hp_value = max(0, int(update["hp"].strip()))
                                    else:
                                        # Handle other formats - extract numbers
                                        import re
                                        match = re.search(r'\d+', str(update["hp"]))
                                        if match:
                                            new_hp_value = max(0, int(match.group(0)))
                                        else:
                                            # If we can't extract a number, keep old HP
                                            print(f"[CombatTracker] Warning: Could not extract HP value from '{update['hp']}'")
                                            if old_hp and old_hp.isdigit():
                                                new_hp_value = int(old_hp)
                                            else:
                                                new_hp_value = 0
                                    
                                    new_hp = str(new_hp_value)
                                    hp_item.setText(new_hp)
                                    print(f"[CombatTracker] Set {name_to_find} HP to {new_hp} in row {found_row} (was {old_hp})")
                                    update_summaries.append(f"- {name_to_find}: HP changed from {old_hp} to {new_hp}")
                                    
                                    # Handle death/unconscious status if HP reaches 0
                                    if new_hp_value <= 0 and "status" not in update:
                                        # Add Unconscious status
                                        status_item = self.initiative_table.item(found_row, 5)  # Status is now column 5
                                        if status_item:
                                            current_statuses = []
                                            if status_item.text():
                                                current_statuses = [s.strip() for s in status_item.text().split(',')]
                                            
                                            # Only add if not already present
                                            if "Unconscious" not in current_statuses:
                                                current_statuses.append("Unconscious")
                                                status_item.setText(', '.join(current_statuses))
                                                update_summaries.append(f"- {name_to_find}: Added 'Unconscious' status due to 0 HP")
                                except Exception as e:
                                    print(f"[CombatTracker] Error processing HP update for {name_to_find}: {str(e)}")
                        # Apply Status update
                        if "status" in update:
                            status_item = self.initiative_table.item(found_row, 5)
                            if status_item:
                                old_status_text = status_item.text()
                                old_statuses = [s.strip() for s in old_status_text.split(',')] if old_status_text else []

                                new_status = update["status"]

                                # Handle different status update formats
                                if isinstance(new_status, list):
                                    # If status is a list, replace all existing statuses
                                    new_statuses = new_status
                                    status_item.setText(', '.join(new_statuses))
                                    update_summaries.append(f"- {name_to_find}: Status changed from '{old_status_text}' to '{', '.join(new_statuses)}'")
                                elif new_status == "clear":
                                    # Special case to clear all statuses
                                    status_item.setText("")
                                    update_summaries.append(f"- {name_to_find}: All statuses cleared (was '{old_status_text}')")
                                elif new_status.startswith("+"):
                                    # Add a status (e.g., "+Poisoned")
                                    status_to_add = new_status[1:].strip()
                                    if status_to_add and status_to_add not in old_statuses:
                                        old_statuses.append(status_to_add)
                                        status_item.setText(', '.join(old_statuses))
                                        update_summaries.append(f"- {name_to_find}: Added '{status_to_add}' status")
                                elif new_status.startswith("-"):
                                    # Remove a status (e.g., "-Poisoned")
                                    status_to_remove = new_status[1:].strip()
                                    if status_to_remove and status_to_remove in old_statuses:
                                        old_statuses.remove(status_to_remove)
                                        status_item.setText(', '.join(old_statuses))
                                        update_summaries.append(f"- {name_to_find}: Removed '{status_to_remove}' status")
                                else:
                                    # Otherwise, directly set the new status (backward compatibility)
                                    status_item.setText(new_status)
                                    update_summaries.append(f"- {name_to_find}: Status changed from '{old_status_text}' to '{new_status}'")

                                # If status contains "Dead" or "Fled", mark for removal
                                current_statuses = status_item.text().split(',')
                                if any(s.strip().lower() in ["dead", "fled"] for s in current_statuses): # Use lower() for case-insensitivity
                                    if found_row not in rows_to_remove: # Avoid duplicates
                                        rows_to_remove.append(found_row)
                                        
                    updates_processed += 1
                except Exception as update_error:
                    print(f"[CombatTracker] Error processing update for index {update_index}: {update_error}")
                    import traceback
                    traceback.print_exc()
                    update_summaries.append(f"ERROR: Failed to process update for index {update_index}")
                    continue  # Skip to next update
        finally:
            # Ensure signals are unblocked even if an error occurs
            self.initiative_table.blockSignals(False)
            
            # Force UI update after all individual updates
            QApplication.processEvents()

        # Process removal separately with a new timeout check
        start_removal_time = time.time()
        removal_time_limit = 3.0  # Limit time spent on removals
        
        # Remove combatants marked for removal (in reverse order)
        if rows_to_remove:
            # Block signals again during row removal for safety
            self.initiative_table.blockSignals(True)
            turn_adjusted = False # Track if current turn needs adjusting
            try:
                print(f"[CombatTracker] Removing {len(rows_to_remove)} combatants...")
                for i, row in enumerate(sorted(list(set(rows_to_remove)), reverse=True)): # Use set() to ensure unique rows
                    # Check timeout for removals
                    if time.time() - start_removal_time > removal_time_limit:
                        print(f"[CombatTracker] Removal time limit reached. Processed {i}/{len(rows_to_remove)} removals.")
                        update_summaries.append(f"WARNING: Only removed {i}/{len(rows_to_remove)} combatants due to time limit.")
                        break
                        
                    # Skip invalid rows
                    if row >= self.initiative_table.rowCount() or row < 0:
                        print(f"[CombatTracker] Skipping invalid row {row}")
                        continue
                        
                    print(f"[CombatTracker] Removing row {row}")
                    self.initiative_table.removeRow(row)
                    # Adjust current turn if needed
                    if row < self.current_turn:
                        self.current_turn -= 1
                        turn_adjusted = True
                    elif row == self.current_turn:
                        # If removing the current turn, reset it (e.g., to -1 or 0 if combatants remain)
                        self.current_turn = 0 if self.initiative_table.rowCount() > 0 else -1
                        turn_adjusted = True

                    # Clean up tracking
                    self.death_saves.pop(row, None)
                    self.concentrating.discard(row) # Use discard for sets
                    self.combatants.pop(row, None) # Clean up combatants dict

                # Update highlight ONLY if turn was adjusted
                if turn_adjusted:
                     self._update_highlight()
            finally:
                 self.initiative_table.blockSignals(False) # Unblock after removals

        # Calculate elapsed time
        total_time = time.time() - start_time
        print(f"[CombatTracker] Combat updates applied in {total_time:.2f} seconds: {updates_processed} updates, {len(rows_to_remove)} removals")
        
        # Ensure the UI table is refreshed after all updates and removals
        self.initiative_table.viewport().update()
        QApplication.processEvents()

        # Force garbage collection
        gc.collect()

        # Return the initialized variables
        return len(rows_to_remove), update_summaries

    def _get_combat_log(self):
        """Get reference to the combat log panel for integration or create a local fallback"""
        # If we already have a valid combat log widget with create_entry method, return it
        if hasattr(self, 'combat_log_widget') and self.combat_log_widget:
            if hasattr(self.combat_log_widget, 'create_entry'):
                return self.combat_log_widget
            else:
                print("[CombatTracker] Warning: Cached combat_log_widget doesn't have create_entry method")
                # Clear the invalid reference - we'll try to create a fallback
                self.combat_log_widget = None
            
        # Try to get the combat log panel from panel_manager
        try:
            panel_manager = getattr(self.app_state, 'panel_manager', None)
            if panel_manager:
                combat_log_panel = panel_manager.get_panel("combat_log")
                if combat_log_panel:
                    print("[CombatTracker] Found combat_log panel, checking interface...")
                    
                    # Check if it has the expected create_entry method
                    if hasattr(combat_log_panel, 'create_entry'):
                        print("[CombatTracker] Combat log panel has required create_entry method")
                        self.combat_log_widget = combat_log_panel
                        return self.combat_log_widget
                    else:
                        print("[CombatTracker] Combat log panel doesn't have required interface, creating adapter...")
                        # Create an adapter that wraps the panel
                        try:
                            self._create_combat_log_adapter(combat_log_panel)
                            if hasattr(self.combat_log_widget, 'create_entry'):
                                return self.combat_log_widget
                        except Exception as e:
                            print(f"[CombatTracker] Error creating combat log adapter: {e}")
        except Exception as e:
            print(f"[CombatTracker] Error getting combat log panel: {e}")
        
        # Create a local fallback if needed
        if not hasattr(self, 'combat_log_widget') or not self.combat_log_widget:
            print("[CombatTracker] Creating local fallback combat log")
            self._create_fallback_combat_log()
            
        # Return whatever we have at this point (might still be None in worst case)
        return self.combat_log_widget
    
    def _create_combat_log_adapter(self, panel):
        """Create an adapter for the combat log panel to provide the create_entry method"""
        # Store the panel reference
        self.combat_log_widget = panel
        
        # Add the create_entry method to the panel
        def create_entry(category=None, actor=None, action=None, target=None, result=None, round=None, turn=None):
            try:
                # Create a simple entry representation
                entry = {
                    "category": category,
                    "actor": actor,
                    "action": action,
                    "target": target,
                    "result": result,
                    "round": round,
                    "turn": turn
                }
                
                # Format the entry into HTML
                html = "<p>"
                if round is not None:
                    html += f"<span style='color:#555555;'>[R{round}]</span> "
                html += f"<strong>{actor}:</strong> {action} "
                if target:
                    html += f"<strong>{target}</strong> "
                if result:
                    html += f"- {result}"
                html += "</p>"
                
                # Add to the log text if the panel has appropriate properties
                if hasattr(panel, 'log_text'):
                    panel.log_text.append(html)
                elif hasattr(panel, 'text'):
                    panel.text.append(html)
                elif hasattr(panel, 'append') and callable(panel.append):
                    panel.append(html)
                
                # Always update our local log as a backup
                if hasattr(self, 'combat_log_text') and self.combat_log_text:
                    self.combat_log_text.append(html)
                    
                return entry
            except Exception as e:
                print(f"[CombatTracker] Error in create_entry adapter: {e}")
                return {"error": str(e)}
                
        # Add the method to the panel
        setattr(self.combat_log_widget, 'create_entry', create_entry)
        
    def _create_fallback_combat_log(self):
        """Create a fallback combat log that stores entries for when external log isn't available"""
        try:
            # Create a simple object with the required interface
            from types import SimpleNamespace
            log = SimpleNamespace()
            
            # Add a list to store entries
            log.entries = []
            
            # Add the create_entry method
            def create_entry(category=None, actor=None, action=None, target=None, result=None, round=None, turn=None):
                # Create entry object
                entry = {
                    "category": category,
                    "actor": actor,
                    "action": action,
                    "target": target,
                    "result": result,
                    "round": round,
                    "turn": turn,
                    "timestamp": time.time()
                }
                
                # Store the entry
                log.entries.append(entry)
                
                # Format the entry and add to our local combat log text widget
                try:
                    if hasattr(self, 'combat_log_text') and self.combat_log_text:
                        # Determine text color based on category
                        color_map = {
                            "Attack": "#8B0000",   # Dark Red
                            "Damage": "#A52A2A",   # Brown
                            "Healing": "#006400",  # Dark Green
                            "Status Effect": "#4B0082",  # Indigo
                            "Death Save": "#000080",  # Navy
                            "Initiative": "#2F4F4F",  # Dark Slate Gray
                            "Turn": "#000000",  # Black
                            "Other": "#708090",  # Slate Gray
                            "Dice": "#696969",  # Dim Gray
                            "Setup": "#708090",  # Slate Gray
                            "Concentration Check": "#800080"  # Purple
                        }
                        
                        text_color = color_map.get(category, "#000000")
                        
                        # Format the HTML
                        round_text = f"R{round}" if round is not None else ""
                        
                        html = f"<p style='margin-top:5px; margin-bottom:5px;'>"
                        if round_text:
                            html += f"<span style='color:#555555;'>[{round_text}]</span> "
                        html += f"<span style='font-weight:bold; color:{text_color};'>{actor}</span> "
                        html += f"{action} "
                        
                        if target:
                            html += f"<span style='font-weight:bold;'>{target}</span> "
                            
                        if result:
                            html += f"<span style='color:#555555;'>{result}</span>"
                            
                        html += "</p>"
                        
                        self.combat_log_text.append(html)
                        
                        # Scroll to the bottom to see latest entries
                        scrollbar = self.combat_log_text.verticalScrollBar()
                        scrollbar.setValue(scrollbar.maximum())
                except Exception as e:
                    print(f"[CombatTracker] Error formatting log entry for display: {e}")
                
                return entry
                
            # Add the method
            log.create_entry = create_entry
            
            # Store the log
            self.combat_log_widget = log
            
            print("[CombatTracker] Created fallback combat log")
        except Exception as e:
            print(f"[CombatTracker] Error creating fallback combat log: {e}")
            self.combat_log_widget = None

    def _log_combat_action(self, category, actor, action, target=None, result=None, round=None, turn=None):
        """Log a combat action and update the persistent combat log"""
        # Safely get the combat log with all our fallback mechanisms
        try:
            combat_log = self._get_combat_log()
            log_entry = None
            
            # Emit the combat_log_signal for panel connections
            try:
                self.combat_log_signal.emit(
                    category or "",
                    actor or "",
                    action or "",
                    target or "",
                    result or ""
                )
            except Exception as e:
                print(f"[CombatTracker] Error emitting combat_log_signal: {e}")
            
            # Try to create an entry using the combat log
            if combat_log and hasattr(combat_log, 'create_entry'):
                try:
                    log_entry = combat_log.create_entry(
                        category=category,
                        actor=actor,
                        action=action,
                        target=target,
                        result=result,
                        round=round if round is not None else self.round_spin.value(),
                        turn=turn
                    )
                except Exception as e:
                    print(f"[CombatTracker] Error creating combat log entry: {str(e)}")
            else:
                # Direct display to our local combat log if external log not available
                try:
                    # Only proceed if we have a local log text widget
                    if hasattr(self, 'combat_log_text') and self.combat_log_text:
                        # Determine text color based on category
                        color_map = {
                            "Attack": "#8B0000",   # Dark Red
                            "Damage": "#A52A2A",   # Brown
                            "Healing": "#006400",  # Dark Green
                            "Status Effect": "#4B0082",  # Indigo
                            "Death Save": "#000080",  # Navy
                            "Initiative": "#2F4F4F",  # Dark Slate Gray
                            "Turn": "#000000",  # Black
                            "Other": "#708090",  # Slate Gray
                            "Dice": "#696969",  # Dim Gray
                            "Setup": "#708090",  # Slate Gray
                            "Concentration Check": "#800080"  # Purple
                        }
                        
                        text_color = color_map.get(category, "#000000")
                        
                        # Format the HTML
                        round_text = f"R{self.round_spin.value()}" if round is None else f"R{round}"
                        
                        html = f"<p style='margin-top:5px; margin-bottom:5px;'>"
                        html += f"<span style='color:#555555;'>[{round_text}]</span> "
                        html += f"<span style='font-weight:bold; color:{text_color};'>{actor}</span> "
                        html += f"{action} "
                        
                        if target:
                            html += f"<span style='font-weight:bold;'>{target}</span> "
                            
                        if result:
                            html += f"<span style='color:#555555;'>{result}</span>"
                            
                        html += "</p>"
                        
                        self.combat_log_text.append(html)
                        
                        # Scroll to the bottom to see latest entries
                        scrollbar = self.combat_log_text.verticalScrollBar()
                        scrollbar.setValue(scrollbar.maximum())
                except Exception as e:
                    print(f"[CombatTracker] Error updating local combat log display: {str(e)}")
            
            return log_entry
        except Exception as e:
            # Extra safety to prevent crashes
            print(f"[CombatTracker] Critical error in _log_combat_action: {str(e)}")
            return None

    def save_state(self):
        """Save the current state of the combat tracker panel."""
        # Initialize the state dictionary with basic combat info
        state = {
            "round": self.current_round,
            "turn": self.current_turn,
            "elapsed_time": self.combat_time,
            "combatants": [], # List to hold state of each combatant
            "death_saves": self.death_saves, # Store death saves data (dict: row -> {successes, failures})
            "concentrating": list(self.concentrating) # Store concentrating combatants (set of row indices)
        }
        
        # Iterate through each row in the initiative table to save combatant data
        for row in range(self.initiative_table.rowCount()):
            # Dictionary to store the state of the current combatant
            combatant_state = {}
            
            # Define the keys corresponding to table columns for easy iteration
            # Columns: Name, Init, HP, Max HP, AC, Status, Conc, Type
            keys = ["name", "initiative", "hp", "max_hp", "ac", "status", "concentration", "type"]
            
            # Extract data for each relevant column
            for col, key in enumerate(keys):
                # Get the QTableWidgetItem from the current cell
                item = self.initiative_table.item(row, col)
                
                # Handle different data types based on column
                if col == 6:  # Concentration column (index 6)
                    # Store boolean based on checkbox state
                    combatant_state[key] = item.checkState() == Qt.Checked if item else False
                elif col == 0: # Name column (index 0)
                    # Store text and also UserRole data (combatant type)
                    combatant_state[key] = item.text() if item else ""
                    # Save the type stored in UserRole if available, otherwise use the 'type' column later
                    user_role_type = item.data(Qt.UserRole) if item else None
                    if user_role_type:
                         combatant_state["user_role_type"] = user_role_type # Store separately for restore logic
                else:
                    # For other columns, store the text content
                    combatant_state[key] = item.text() if item else ""
            
            # Ensure 'type' is saved correctly (prioritize UserRole, then column, then default)
            combatant_state["type"] = combatant_state.pop("user_role_type", combatant_state.get("type", "manual"))

            # Retrieve and save the detailed combatant data stored in self.combatants dictionary
            if row in self.combatants:
                # Store the associated data object/dictionary
                # Note: Ensure this data is serializable (e.g., dict, list, primitives)
                # If it's a complex object, you might need a custom serialization method
                combatant_state["data"] = self.combatants[row] 
            
            # Add the combatant's state to the main state list
            state["combatants"].append(combatant_state)
            
        # Return the complete state dictionary
        return state

    def restore_state(self, state):
        """Restore the combat tracker state from a saved state dictionary."""
        # Check if the provided state is valid (not None and is a dictionary)
        if not state or not isinstance(state, dict):
            print("[CombatTracker] Restore Error: Invalid or missing state data.")
            return # Exit if state is invalid

        print("[CombatTracker] Restoring combat tracker state...")
        # Block signals during restoration to prevent unwanted side effects
        self.initiative_table.blockSignals(True)
        
        try:
            # --- Clear Existing State ---
            self.initiative_table.setRowCount(0) # Clear all rows from the table
            self.death_saves.clear()            # Clear tracked death saves
            self.concentrating.clear()          # Clear tracked concentration
            self.combatants.clear()             # Clear stored combatant data
            self.monster_id_counter = 0         # Reset monster ID counter (important for new monsters added after restore)

            # --- Restore Basic Combat Info ---
            self.current_round = state.get("round", 1)
            self.round_spin.setValue(self.current_round) # Update UI spinner
            
            # Restore current turn, ensuring it's within bounds of restored combatants later
            self.current_turn = state.get("turn", 0) 
            
            self.combat_time = state.get("elapsed_time", 0)
            # Update timer display immediately (will show 00:00:00 if time is 0)
            hours = self.combat_time // 3600
            minutes = (self.combat_time % 3600) // 60
            seconds = self.combat_time % 60
            self.timer_label.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
            # Reset timer button state (assume stopped on restore)
            if self.timer.isActive():
                self.timer.stop()
            self.timer_button.setText("Start") 
            
            # Restore game time display based on restored round
            self._update_game_time()

            # --- Restore Tracking Dictionaries ---
            # Restore death saves - keys (row indices) might need remapping if table structure changes significantly
            self.death_saves = state.get("death_saves", {}) 
            # Restore concentration - convert list back to set
            self.concentrating = set(state.get("concentrating", [])) 

            # --- Restore Combatants ---
            restored_combatants_list = state.get("combatants", [])
            for idx, combatant_state in enumerate(restored_combatants_list):
                # Insert a new row for each combatant
                row = self.initiative_table.rowCount()
                self.initiative_table.insertRow(row)
                
                # Restore detailed combatant data if it exists
                if "data" in combatant_state:
                    self.combatants[row] = combatant_state["data"]
                    # If it's a monster, try to assign a unique ID
                    if combatant_state.get("type") == "monster":
                         # Create a unique ID for this monster instance
                         monster_id = self.monster_id_counter
                         self.monster_id_counter += 1
                         # Store the ID with the name item's UserRole + 2
                         # We create the name item below
                         
                # Determine combatant type (use saved 'type' field)
                combatant_type = combatant_state.get("type", "manual") # Default to manual if missing

                # --- Create and set items for each column ---
                # Column 0: Name
                name_item = QTableWidgetItem(combatant_state.get("name", f"Combatant {row+1}"))
                name_item.setData(Qt.UserRole, combatant_type) # Store type in UserRole
                # Assign monster ID if applicable
                if combatant_type == "monster" and "data" in combatant_state:
                    name_item.setData(Qt.UserRole + 2, monster_id) # Store the generated monster ID
                name_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
                self.initiative_table.setItem(row, 0, name_item)
                
                # Column 1: Initiative
                init_item = QTableWidgetItem(str(combatant_state.get("initiative", "0")))
                init_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
                self.initiative_table.setItem(row, 1, init_item)
                
                # Column 2: Current HP
                hp_item = QTableWidgetItem(str(combatant_state.get("hp", "1")))
                hp_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
                self.initiative_table.setItem(row, 2, hp_item)
                
                # Column 3: Max HP
                # Use saved max_hp, fallback to current hp if max_hp is missing/invalid
                max_hp_val = combatant_state.get("max_hp", combatant_state.get("hp", "1")) 
                # Ensure max_hp is at least current hp if both are numbers
                try:
                    current_hp_int = int(hp_item.text())
                    max_hp_int = int(str(max_hp_val)) # Convert to string first for safety
                    if max_hp_int < current_hp_int:
                         max_hp_val = hp_item.text() # Set max HP to current HP if inconsistent
                except ValueError:
                     pass # Ignore conversion errors, use the value as is
                max_hp_item = QTableWidgetItem(str(max_hp_val))
                max_hp_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
                self.initiative_table.setItem(row, 3, max_hp_item)
                
                # Column 4: AC
                ac_item = QTableWidgetItem(str(combatant_state.get("ac", "10")))
                ac_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
                self.initiative_table.setItem(row, 4, ac_item)
                
                # Column 5: Status
                status_item = QTableWidgetItem(combatant_state.get("status", ""))
                status_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
                self.initiative_table.setItem(row, 5, status_item)
                
                # Column 6: Concentration (Checkbox)
                conc_item = QTableWidgetItem()
                conc_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
                # Set check state based on saved boolean value
                is_concentrating = combatant_state.get("concentration", False)
                conc_item.setCheckState(Qt.Checked if is_concentrating else Qt.Unchecked)
                self.initiative_table.setItem(row, 6, conc_item)
                
                # Column 7: Type (Read-only display, actual type stored in Name item UserRole)
                type_item = QTableWidgetItem(combatant_type)
                type_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled) # Generally not editable directly
                self.initiative_table.setItem(row, 7, type_item)

            # Adjust current_turn if it's out of bounds after restoring
            if self.current_turn >= self.initiative_table.rowCount():
                self.current_turn = 0 if self.initiative_table.rowCount() > 0 else -1
            
            # --- Final Steps ---
            # Re-apply highlighting based on the restored current turn
            self.previous_turn = -1 # Reset previous turn before updating highlight
            self._update_highlight()
            
            # Optional: Re-sort the table based on restored initiative values
            # self._sort_initiative() # Might be desired, but could change turn order if initiatives were edited before save

            # Optional: Fix any inconsistencies in types (should be less needed now)
            # self._fix_missing_types()
            
            print(f"[CombatTracker] State restoration complete. {self.initiative_table.rowCount()} combatants restored.")

        except Exception as e:
            # Catch any unexpected errors during restoration
            print(f"[CombatTracker] CRITICAL ERROR during state restoration: {e}")
            import traceback
            traceback.print_exc()
            # Optionally, clear the tracker completely to avoid a corrupted state
            # self._reset_combat() 
            QMessageBox.critical(self, "Restore Error", f"Failed to restore combat state: {e}")
        finally:
            # ALWAYS unblock signals, even if an error occurred
            self.initiative_table.blockSignals(False)
            # Force UI refresh after restoration
            self.initiative_table.viewport().update()
            QApplication.processEvents()

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

    def roll_dice(self, dice_formula):
        """Roll dice based on a formula like "3d8+4" or "2d6-1" """
        print(f"[CombatTracker] Rolling dice formula: {dice_formula}")
        if not dice_formula or not isinstance(dice_formula, str):
            print("[CombatTracker] Invalid dice formula")
            return 10
            
        # Parse the dice formula
        dice_match = re.search(r'(\d+)d(\d+)([+-]\d+)?', dice_formula)
        if not dice_match:
            print(f"[CombatTracker] Could not parse dice formula: {dice_formula}")
            return 10
            
        try:
            # Extract dice components
            count = int(dice_match.group(1))
            sides = int(dice_match.group(2))
            modifier = 0
            if dice_match.group(3):
                modifier = int(dice_match.group(3))
                
            # Roll the dice
            rolls = [random.randint(1, sides) for _ in range(count)]
            total = sum(rolls) + modifier
            print(f"[CombatTracker] Dice rolls: {rolls}, modifier: {modifier}, total: {total}")
            return max(1, total)  # Ensure at least 1 HP
        except (ValueError, TypeError, IndexError) as e:
            print(f"[CombatTracker] Error rolling dice: {e}")
            return 10

    def extract_dice_formula(self, hp_value):
        """Extract a dice formula from various HP value formats"""
        dice_formula = None
        
        if isinstance(hp_value, dict) and 'hit_dice' in hp_value:
            dice_formula = hp_value['hit_dice']
            print(f"[CombatTracker] Found hit_dice in dict: {dice_formula}")
        elif isinstance(hp_value, str):
            # Try to extract formula from string like "45 (6d10+12)"
            match = re.search(r'\(\s*([0-9d+\-\s]+)\s*\)', hp_value)
            if match:
                # Remove any spaces from the formula before processing
                dice_formula = re.sub(r'\s+', '', match.group(1))
                print(f"[CombatTracker] Extracted dice formula from parentheses: {dice_formula}")
            # If the string itself is a dice formula
            elif re.match(r'^\d+d\d+([+-]\d+)?$', hp_value):
                dice_formula = hp_value
                print(f"[CombatTracker] String is directly a dice formula: {dice_formula}")
                
        return dice_formula

    def add_monster(self, monster_data):
        """Add a monster from monster panel to the tracker"""
        if not monster_data:
            return -1
            
        # Block signals to prevent race conditions during adding
        self.initiative_table.blockSignals(True)
        
        try:
            # Diagnostic: Log information about this monster
            monster_name = "Unknown"
            if isinstance(monster_data, dict) and 'name' in monster_data:
                monster_name = monster_data['name']
            elif hasattr(monster_data, 'name'):
                monster_name = monster_data.name
                
            print(f"[CombatTracker] Adding monster '{monster_name}' (type: {type(monster_data)})")
            
            # Validate monster data to prevent ability mixing
            try:
                # Import the validator
                from app.core.improved_combat_resolver import ImprovedCombatResolver
                
                # Only validate if it's a dictionary (proper format)
                if isinstance(monster_data, dict):
                    # Check if this monster has already been validated
                    if "_validation_id" in monster_data:
                        # Already validated, skip further validation to preserve abilities
                        print(f"[CombatTracker] Monster {monster_name} already validated with ID {monster_data['_validation_id']}")
                        validated_monster_data = monster_data
                    else:
                        # Validate monster data
                        print(f"[CombatTracker] Validating monster data for '{monster_name}'")
                        validated_monster_data = ImprovedCombatResolver.validate_monster_data(monster_data)
                    
                    # Check if validation changed anything
                    actions_before = len(monster_data.get('actions', [])) if 'actions' in monster_data else 0
                    actions_after = len(validated_monster_data.get('actions', [])) if 'actions' in validated_monster_data else 0
                    
                    traits_before = len(monster_data.get('traits', [])) if 'traits' in monster_data else 0
                    traits_after = len(validated_monster_data.get('traits', [])) if 'traits' in validated_monster_data else 0
                    
                    if actions_before != actions_after or traits_before != traits_after:
                        print(f"[CombatTracker] Validation modified abilities for {monster_name}")
                        print(f"[CombatTracker] Actions: {actions_before} -> {actions_after}, Traits: {traits_before} -> {traits_after}")
                        
                        # If validation retained most abilities, use the validated data
                        # Otherwise, keep the original to avoid losing legitimate abilities
                        if actions_after >= actions_before * 0.5 and traits_after >= traits_before * 0.5:
                            monster_data = validated_monster_data
                            print(f"[CombatTracker] Using validated monster data (most abilities retained)")
                        else:
                            print(f"[CombatTracker] Validation removed too many abilities, keeping original data")
                            # Still use the validation ID for consistency
                            if "_validation_id" in validated_monster_data:
                                monster_data["_validation_id"] = validated_monster_data["_validation_id"]
            except Exception as e:
                # If validation fails, log the error but continue with the original data
                print(f"[CombatTracker] Error validating monster data: {e}")
                # Don't block combat addition due to validation error
            
            # Helper function to get attribute from either dict or object
            def get_attr(obj, attr, default=None, alt_attrs=None):
                """Get attribute from object or dict, trying alternate attribute names if specified"""
                alt_attrs = alt_attrs or []
                result = default
                
                try:
                    # Implementation remains the same
                    # Just a helper function to retrieve attributes from different object types
                    if isinstance(obj, dict):
                        if attr in obj:
                            return obj[attr]
                        for alt_attr in alt_attrs:
                            if alt_attr in obj:
                                return obj[alt_attr]
                        # Additional checks for nested structures, etc.
                        # ...
                    else:
                        if hasattr(obj, attr):
                            return getattr(obj, attr)
                        for alt_attr in alt_attrs:
                            if hasattr(obj, alt_attr):
                                return getattr(obj, alt_attr)
                        # Additional checks for object attributes, etc.
                        # ...
                    
                    return default
                except Exception as e:
                    print(f"[CombatTracker] Error in get_attr({attr}): {e}")
                    return default
                
            # Get monster name
            name = get_attr(monster_data, "name", "Unknown Monster")
            
            # Generate a unique ID for this monster instance using the correct counter attribute
            monster_id = self.monster_id_counter
            self.monster_id_counter += 1
            
            # Get a reasonable initiative modifier from DEX
            dex = get_attr(monster_data, "dexterity", 10, ["dex", "DEX"])
            init_mod = (dex - 10) // 2
            
            # Roll initiative
            initiative_roll = random.randint(1, 20) + init_mod
            
            # Get monster HP data and AC in various formats
            hp_value = get_attr(monster_data, "hp", 10, ["hit_points", "hitPoints", "hit_points_roll", "hit_dice"])
            print(f"[CombatTracker] Retrieved HP value: {hp_value} (type: {type(hp_value)})")
            
            # Calculate average HP (for Max HP display)
            max_hp = 0
            if isinstance(hp_value, int):
                max_hp = hp_value
            elif isinstance(hp_value, dict) and 'average' in hp_value:
                max_hp = int(hp_value['average'])
            elif isinstance(hp_value, str):
                # Try to extract average value from string like "45 (6d10+12)"
                match = re.match(r'(\d+)\s*\(', hp_value)
                if match:
                    max_hp = int(match.group(1))
                elif hp_value.isdigit():
                    max_hp = int(hp_value)
            
            if max_hp <= 0:
                max_hp = 10
                
            print(f"[CombatTracker] Max HP: {max_hp}")
            
            # IMPORTANT PART: EXTRACT DICE FORMULA AND ROLL HP
            dice_formula = self.extract_dice_formula(hp_value)
            
            # ALWAYS ROLL RANDOM HP
            if dice_formula:
                # Roll random HP using the dice formula
                hp = self.roll_dice(dice_formula)
                print(f"[CombatTracker] RANDOM HP ROLL: {hp} using formula {dice_formula}")
            else:
                # If no dice formula, create a better one based on monster CR and average HP
                # For dragons and high-HP monsters, a better approximation would be:
                # d12 for big monsters, d10 for medium monsters, d8 for small monsters
                
                # Determine the creature size based on max HP
                if max_hp > 200:  # Large/Huge creatures like dragons
                    die_size = 12
                    num_dice = max(1, int(max_hp * 0.75 / (die_size/2 + 0.5)))  # Scale dice count to match HP
                elif max_hp > 100:  # Medium creatures
                    die_size = 10
                    num_dice = max(1, int(max_hp * 0.8 / (die_size/2 + 0.5)))
                else:  # Small creatures
                    die_size = 8
                    num_dice = max(1, int(max_hp * 0.85 / (die_size/2 + 0.5)))
                
                # Add a small modifier to account for Constitution
                modifier = int(max_hp * 0.1)
                estimated_formula = f"{num_dice}d{die_size}+{modifier}"
                hp = self.roll_dice(estimated_formula)
                print(f"[CombatTracker] NO FORMULA FOUND - Created estimated formula {estimated_formula} and rolled: {hp}")
                
                # Limit HP to a reasonable range (50%-125% of average)
                min_hp = int(max_hp * 0.5)
                max_possible_hp = int(max_hp * 1.25)
                hp = max(min_hp, min(hp, max_possible_hp))
                print(f"[CombatTracker] Adjusted HP to {hp} (limited to {min_hp}-{max_possible_hp})")
            
            # Set max_hp to the randomly rolled hp value so they match
            max_hp = hp
            
            ac = get_attr(monster_data, "ac", 10, ["armor_class", "armorClass", "AC"])
            print(f"[CombatTracker] Retrieved AC value: {ac}")
            
            # Save monster stats for later verification
            monster_stats = {
                "id": monster_id,
                "name": name,
                "hp": hp,
                "max_hp": max_hp,
                "ac": ac
            }
            
            # Add to tracker with our randomly rolled HP
            row = self._add_combatant(name, initiative_roll, hp, max_hp, ac, "monster", monster_id)
            
            # Ensure row is valid, default to -1 if None
            if row is None:
                row = -1
            
            # Store monster data for future reference
            if row >= 0:
                self.combatants[row] = monster_data
                
            # Force a refresh of the entire table
            self.initiative_table.viewport().update()
            QApplication.processEvents()
                    
            # Make absolutely sure this monster's values are correctly set (with delay)
            QTimer.singleShot(50, lambda: self._verify_monster_stats(monster_stats))
                    
            # Log to combat log
            self._log_combat_action("Setup", "DM", "added monster", name, f"(Init: {initiative_roll}, HP: {hp}/{max_hp})")
            
            return row
            
        finally:
            # Always unblock signals even if there's an error
            self.initiative_table.blockSignals(False)
            
    def _verify_monster_stats(self, monster_stats):
        """Double-check that monster stats are properly set after adding and sorting"""
        monster_id = monster_stats["id"]
        name = monster_stats["name"]
        hp = monster_stats["hp"]
        max_hp = monster_stats["max_hp"]
        ac = monster_stats["ac"]
        
        # Find the current row for this monster
        row = self._find_monster_by_id(monster_id)
        if row < 0:
            print(f"[CombatTracker] Warning: Cannot verify stats for monster {name} (ID {monster_id}) - not found")
            return
            
        # Verify all stats are correctly set
        hp_item = self.initiative_table.item(row, 2)
        max_hp_item = self.initiative_table.item(row, 3)
        ac_item = self.initiative_table.item(row, 4)
        
        # Prepare values as strings
        hp_str = str(hp) if hp is not None else "10"
        max_hp_str = str(max_hp) if max_hp is not None else "10"
        ac_str = str(ac) if ac is not None else "10"
        
        # Check and fix values if needed
        changes_made = False
        
        # Check HP
        if not hp_item or hp_item.text() != hp_str:
            print(f"[CombatTracker] Fixing HP for {name} (ID {monster_id}) at row {row}: setting to {hp_str}")
            new_hp_item = QTableWidgetItem(hp_str)
            new_hp_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
            self.initiative_table.setItem(row, 2, new_hp_item)
            changes_made = True
            
        # Check Max HP
        if not max_hp_item or max_hp_item.text() != max_hp_str:
            print(f"[CombatTracker] Fixing Max HP for {name} (ID {monster_id}) at row {row}: setting to {max_hp_str}")
            new_max_hp_item = QTableWidgetItem(max_hp_str)
            new_max_hp_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
            self.initiative_table.setItem(row, 3, new_max_hp_item)
            changes_made = True
            
        # Check AC
        if not ac_item or ac_item.text() != ac_str:
            print(f"[CombatTracker] Fixing AC for {name} (ID {monster_id}) at row {row}: setting to {ac_str}")
            new_ac_item = QTableWidgetItem(ac_str)
            new_ac_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
            self.initiative_table.setItem(row, 4, new_ac_item)
            changes_made = True
            
        # If any changes were made, update the table
        if changes_made:
            self.initiative_table.viewport().update()
            print(f"[CombatTracker] Stats verified and fixed for {name} (ID {monster_id})")
        else:
            print(f"[CombatTracker] All stats correct for {name} (ID {monster_id})")
    
    def _sort_initiative(self):
        """Sort the initiative list in descending order."""
        # --- Check flag: Prevent sorting during LLM resolution --- 
        if self._is_resolving_combat:
            print("[CombatTracker] _sort_initiative: Skipping sort because _is_resolving_combat is True.")
            return
            
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
                
            # Save all monsters IDs and stats before sorting
            monster_stats = {}
            monster_instance_ids = {}  # NEW: Track instance IDs for each row
            for row in range(row_count):
                name_item = self.initiative_table.item(row, 0)
                if name_item:
                    # Save monster ID if it exists
                    if name_item.data(Qt.UserRole + 2) is not None:
                        monster_id = name_item.data(Qt.UserRole + 2)
                        monster_stats[monster_id] = {
                            "id": monster_id,
                            "name": name_item.text(),
                            "hp": self.initiative_table.item(row, 2).text() if self.initiative_table.item(row, 2) else "10",
                            "max_hp": self.initiative_table.item(row, 3).text() if self.initiative_table.item(row, 3) else "10",
                            "ac": self.initiative_table.item(row, 4).text() if self.initiative_table.item(row, 4) else "10"
                        }
                    
                    # NEW: Store instance ID for this row
                    monster_instance_ids[row] = name_item.data(Qt.UserRole + 2) or f"combatant_{row}"
                    print(f"[CombatTracker] Row {row} has instance ID: {monster_instance_ids[row]}")
            
            # Store pre-sort HP and AC data for verification
            pre_sort_values = {}
            for row in range(row_count):
                name_item = self.initiative_table.item(row, 0)
                hp_item = self.initiative_table.item(row, 2)
                ac_item = self.initiative_table.item(row, 4)
                
                name = name_item.text() if name_item else f"Row {row}"
                hp = hp_item.text() if hp_item else "?"
                ac = ac_item.text() if ac_item else "?"
                
                pre_sort_values[name] = {"hp": hp, "ac": ac, "instance_id": monster_instance_ids.get(row, f"combatant_{row}")}
            
            # Collect all the data from the table first
            print(f"[CombatTracker] Collecting data from {row_count} rows")
            
            # Store all row data before clearing
            rows_data = []
            initiative_values = []
            
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
                            'currentTurn': item.data(Qt.UserRole + 1),
                            'instanceId': item.data(Qt.UserRole + 2) if col == 0 else None  # Save monster ID/instance ID
                        }
                        
                # Add this row's data to our collection
                rows_data.append(row_data)
                initiative_values.append((initiative, row))
                hp_value = row_data.get(2, {}).get('text', '?')
                ac_value = row_data.get(4, {}).get('text', '?')
                instance_id = row_data.get(0, {}).get('instanceId', f"combatant_{row}")
                print(f"[CombatTracker] Row {row}: initiative={initiative}, hp={hp_value}, ac={ac_value}, instance_id={instance_id}")
                
            # Execute the rest of the original sort code
            # Sort the initiative values in descending order
            initiative_values.sort(key=lambda x: x[0], reverse=True)
            
            # Remap original rows to their new position after sorting
            row_map = {old_row: new_row for new_row, (_, old_row) in enumerate(initiative_values)}
            # NEW: Also create reverse mapping
            new_to_old_map = {new_row: old_row for old_row, new_row in row_map.items()}
            
            # Remember the current selection and turn
            current_row = self.initiative_table.currentRow()
            current_turn = self._current_turn if hasattr(self, '_current_turn') else None
            
            # Clear the table (but don't update combat stats yet)
            self.initiative_table.setRowCount(0)
            self.initiative_table.setRowCount(row_count)
            
            # Add the sorted rows back to the table
            for old_row, new_row in row_map.items():
                row_data = rows_data[old_row]
                
                # Debug HP and AC for this row
                hp_value = row_data.get(2, {}).get('text', '?')
                ac_value = row_data.get(4, {}).get('text', '?')
                instance_id = row_data.get(0, {}).get('instanceId', f"combatant_{old_row}")
                print(f"[CombatTracker] Moving HP value: {hp_value} from old_row={old_row} to new_row={new_row}")
                print(f"[CombatTracker] Moving AC value: {ac_value} from old_row={old_row} to new_row={new_row}")
                print(f"[CombatTracker] Moving instance ID: {instance_id} from old_row={old_row} to new_row={new_row}")
                
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
                    
                    # IMPORTANT: Restore instance ID for the name column
                    if col == 0 and 'instanceId' in item_data and item_data['instanceId'] is not None:
                        new_item.setData(Qt.UserRole + 2, item_data['instanceId'])
                        print(f"[CombatTracker] Set instance ID {item_data['instanceId']} for new_row={new_row}")
                    
                    # Set the item in the table
                    self.initiative_table.setItem(new_row, col, new_item)
            
            # Update current selection and turn if needed
            if current_row >= 0 and current_row < row_count:
                new_current_row = row_map.get(current_row, 0)
                self.initiative_table.setCurrentCell(new_current_row, 0)
            
            if current_turn is not None and current_turn >= 0 and current_turn < row_count:
                self._current_turn = row_map.get(current_turn, 0)
            
            # NEW: Update the self.combatants dictionary to keep instance IDs aligned
            if hasattr(self, 'combatants') and isinstance(self.combatants, dict):
                new_combatants = {}
                for old_row, combatant_data in self.combatants.items():
                    if old_row in row_map:
                        new_row = row_map[old_row]
                        new_combatants[new_row] = combatant_data
                        
                        # If combatant_data is a dictionary, update its instance_id
                        if isinstance(combatant_data, dict):
                            instance_id = monster_instance_ids.get(old_row, f"combatant_{old_row}")
                            combatant_data['instance_id'] = instance_id
                            print(f"[CombatTracker] Updated instance_id in combatants dict: {old_row} -> {new_row} with ID {instance_id}")
                
                self.combatants = new_combatants
            
            # Verify HP and AC values after sorting
            post_sort_values = {}
            for row in range(row_count):
                name_item = self.initiative_table.item(row, 0)
                hp_item = self.initiative_table.item(row, 2)
                ac_item = self.initiative_table.item(row, 4)
                
                name = name_item.text() if name_item else f"Row {row}"
                hp = hp_item.text() if hp_item else "?"
                ac = ac_item.text() if ac_item else "?"
                instance_id = name_item.data(Qt.UserRole + 2) if name_item else f"combatant_{row}"
                
                post_sort_values[name] = {"hp": hp, "ac": ac, "instance_id": instance_id}
            
            # Compare pre and post sort values
            for name, pre_values in pre_sort_values.items():
                post_values = post_sort_values.get(name, {"hp": "MISSING", "ac": "MISSING", "instance_id": "MISSING"})
                
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
                    
                # Check instance ID
                pre_instance_id = pre_values["instance_id"]
                post_instance_id = post_values["instance_id"]
                if pre_instance_id != post_instance_id:
                    print(f"[CombatTracker] WARNING: Instance ID changed during sort for {name}: {pre_instance_id} -> {post_instance_id}")
                else:
                    print(f"[CombatTracker] Instance ID preserved for {name}: {pre_instance_id}")

            # At the end of the sort function, add the monster stats verification
            # Schedule verification for all monsters after sorting is complete
            for monster_id, stats in monster_stats.items():
                QTimer.singleShot(100, lambda stats=stats: self._verify_monster_stats(stats))
            
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
                        # Mark as unconscious - add to existing statuses
                        status_item = self.initiative_table.item(row, 5)  # Status is now column 5
                        if status_item:
                            current_statuses = []
                            if status_item.text():
                                current_statuses = [s.strip() for s in status_item.text().split(',')]
                            
                            # Only add if not already present
                            if "Unconscious" not in current_statuses:
                                current_statuses.append("Unconscious")
                                status_item.setText(', '.join(current_statuses))
                                
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
            status_text = status_item.text()
            
            # Parse statuses from comma-separated list
            statuses = []
            if status_text:
                statuses = [s.strip() for s in status_text.split(',')]
            
            # Update the status in the combatant data if it's a dictionary
            if isinstance(self.combatants[row], dict):
                if 'conditions' not in self.combatants[row]:
                    self.combatants[row]['conditions'] = []
                self.combatants[row]['conditions'] = statuses
            elif hasattr(self.combatants[row], 'conditions'):
                self.combatants[row].conditions = statuses
    
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
                        
                        # Update status - add Stable, remove Unconscious
                        status_item = self.initiative_table.item(row, 5)  # Status is now column 5
                        if status_item:
                            current_statuses = []
                            if status_item.text():
                                current_statuses = [s.strip() for s in status_item.text().split(',')]
                            
                            # Remove Unconscious if present
                            if "Unconscious" in current_statuses:
                                current_statuses.remove("Unconscious")
                            
                            # Add Stable if not present
                            if "Stable" not in current_statuses:
                                current_statuses.append("Stable")
                                
                            status_item.setText(', '.join(current_statuses))
                            
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
                        
                        # Update status - add Dead, remove Unconscious
                        status_item = self.initiative_table.item(row, 5)  # Status is now column 5
                        if status_item:
                            current_statuses = []
                            if status_item.text():
                                current_statuses = [s.strip() for s in status_item.text().split(',')]
                            
                            # Remove Unconscious if present
                            if "Unconscious" in current_statuses:
                                current_statuses.remove("Unconscious")
                            
                            # Add Dead if not present
                            if "Dead" not in current_statuses:
                                current_statuses.append("Dead")
                                
                            status_item.setText(', '.join(current_statuses))
                    else:
                        self._log_combat_action(
                            "Death Save", 
                            name, 
                            "updated death saves", 
                            result=f"{successes} successes, {failures} failures"
                        )

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

    def _cleanup_dead_combatants(self):
        """Iterate through the table and remove combatants marked as Dead or Fled."""
        rows_to_remove = []
        for row in range(self.initiative_table.rowCount()):
            status_item = self.initiative_table.item(row, 5) # Status column
            if status_item:
                # Check status case-insensitively
                statuses = [s.strip().lower() for s in status_item.text().split(',')]
                if "dead" in statuses or "fled" in statuses:
                    rows_to_remove.append(row)

        if not rows_to_remove:
            print("[CombatTracker] Cleanup: No dead/fled combatants found.")
            return # Nothing to remove

        print(f"[CombatTracker] Cleanup: Removing {len(rows_to_remove)} dead/fled combatants.")
        
        # Block signals during row removal for safety
        self.initiative_table.blockSignals(True)
        turn_adjusted = False
        try:
            # --- Remove Rows Phase --- 
            for row in sorted(rows_to_remove, reverse=True):
                # Log removal before actually removing
                name_item = self.initiative_table.item(row, 0)
                name = name_item.text() if name_item else f"Row {row}"
                print(f"[CombatTracker] Cleanup: Removing row {row} ({name})")
                self._log_combat_action("Setup", "DM", "removed dead/fled combatant", name)

                self.initiative_table.removeRow(row)
                
                # --- State Adjustment Phase (after each removal) ---
                # Adjust current turn index if it was affected by the removal
                if row < self.current_turn:
                    self.current_turn -= 1
                    turn_adjusted = True
                    print(f"[CombatTracker] Cleanup: Adjusted current_turn to {self.current_turn} (was < {row})")
                elif row == self.current_turn:
                    # If removing the current turn, reset it (e.g., to 0 or -1)
                    self.current_turn = 0 if self.initiative_table.rowCount() > 0 else -1
                    turn_adjusted = True
                    print(f"[CombatTracker] Cleanup: Reset current_turn to {self.current_turn} (was == {row})")

                # Clean up tracking
                self.death_saves.pop(row, None)
                self.concentrating.discard(row) # Use discard for sets
                self.combatants.pop(row, None) # Clean up combatants dict
                
        finally:
            self.initiative_table.blockSignals(False) # Unblock after removals
            print("[CombatTracker] Cleanup: Finished removing rows.")
            
        # --- Re-indexing Phase (after ALL removals) --- 
        # Only reindex if rows were actually removed
        if rows_to_remove:
            print("[CombatTracker] Cleanup: Re-indexing remaining combatant data.")
            new_combatants = {}
            new_concentrating = set()
            new_death_saves = {}
            
            # Map old rows to new rows efficiently
            current_row_count = self.initiative_table.rowCount()
            old_to_new_map = {}
            original_indices = sorted(self.combatants.keys()) # Get keys before modifying
            
            current_new_row = 0
            for old_row in range(max(original_indices) + 1): # Iterate through potential old indices
                if old_row not in rows_to_remove and old_row in original_indices:
                    old_to_new_map[old_row] = current_new_row
                    current_new_row += 1

            # Apply the mapping
            for old_row, new_row in old_to_new_map.items():
                if old_row in self.combatants:
                    new_combatants[new_row] = self.combatants[old_row]
                if old_row in self.concentrating:
                    new_concentrating.add(new_row)
                if old_row in self.death_saves:
                    new_death_saves[new_row] = self.death_saves[old_row]
                     
            self.combatants = new_combatants
            self.concentrating = new_concentrating
            self.death_saves = new_death_saves
            print(f"[CombatTracker] Cleanup: Re-indexing complete. New combatants dict size: {len(self.combatants)}")
            
        # --- Final UI Update Phase --- 
        # Update highlight ONLY if turn was adjusted OR the table is now empty
        if turn_adjusted or self.initiative_table.rowCount() == 0:
            print("[CombatTracker] Cleanup: Updating highlight.")
            self._update_highlight()
            
        # Final UI refresh
        print("[CombatTracker] Cleanup: Refreshing viewport.")
        self.initiative_table.viewport().update()
        QApplication.processEvents()
        print("[CombatTracker] Cleanup: Finished.")

    def _view_combatant_details(self, row, col=0): # Added col default
        """Show the details for the combatant at the given row"""
        # Ensure row is valid
        if row < 0 or row >= self.initiative_table.rowCount():
            print(f"[Combat Tracker] Invalid row provided to _view_combatant_details: {row}")
            return
            
        name_item = self.initiative_table.item(row, 0) # Name is in column 0
        if not name_item:
            print(f"[Combat Tracker] No name item found at row {row}")
            return
            
        combatant_name = name_item.text()
        # Get type from UserRole data first
        combatant_type = name_item.data(Qt.UserRole)
        
        # If type is None or empty, try to get it from the type column (index 7)
        if not combatant_type:
             type_item = self.initiative_table.item(row, 7) 
             if type_item:
                 combatant_type = type_item.text().lower()
                 # Store it back in the name item for future use
                 name_item.setData(Qt.UserRole, combatant_type)
                 print(f"[Combat Tracker] Inferred type '{combatant_type}' for {combatant_name} from column 7")
            
        # If still None, default to custom
        if not combatant_type:
            combatant_type = "custom"
            name_item.setData(Qt.UserRole, combatant_type) # Store default
            print(f"[Combat Tracker] Defaulting type to 'custom' for {combatant_name}")
            
        print(f"[Combat Tracker] Viewing details for {combatant_type} '{combatant_name}'")
        
        panel_manager = getattr(self.app_state, 'panel_manager', None)
        if not panel_manager:
             print("[Combat Tracker] No panel_manager found in app_state, falling back to dialog.")
             self._show_combatant_dialog(row, combatant_name, combatant_type)
             return

        # Redirect to appropriate panel based on combatant type
        panel_found = False
        if combatant_type == "monster":
            monster_panel = self.get_panel("monster")
            if monster_panel:
                panel_manager.show_panel("monster")
                # Now search and select the monster
                result = monster_panel.search_and_select_monster(combatant_name)
                panel_found = True
                if not result:
                    print(f"[Combat Tracker] Monster '{combatant_name}' not found in monster browser. Showing dialog.")
                    self._show_combatant_dialog(row, combatant_name, combatant_type)
            else:
                 print("[Combat Tracker] Monster panel not found. Showing dialog.")
                 self._show_combatant_dialog(row, combatant_name, combatant_type)
                 panel_found = True # Dialog shown, counts as handled
                 
        elif combatant_type == "character":
            character_panel = self.get_panel("player_character")
            if character_panel:
                panel_manager.show_panel("player_character")
                # Now search and select the character
                result = character_panel.select_character_by_name(combatant_name)
                panel_found = True
                if not result:
                    print(f"[Combat Tracker] Character '{combatant_name}' not found in character panel. Showing dialog.")
                    self._show_combatant_dialog(row, combatant_name, combatant_type)
            else:
                print("[Combat Tracker] Character panel not found. Showing dialog.")
                self._show_combatant_dialog(row, combatant_name, combatant_type)
                panel_found = True # Dialog shown, counts as handled

        # Fallback for custom types or if panels failed
        if not panel_found:
            print(f"[Combat Tracker] Type is '{combatant_type}' or panel redirection failed. Showing dialog.")
            self._show_combatant_dialog(row, combatant_name, combatant_type)

    def _show_combatant_dialog(self, row, combatant_name, combatant_type):
        """Show a dialog with combatant details when we can't redirect to another panel"""
        print(f"[Combat Tracker] Showing dialog for {combatant_type} '{combatant_name}' at row {row}")
        
        # Start with basic data from the initiative table
        combatant_data = {
            "name": combatant_name,
            "type": combatant_type, # Ensure type is passed
            "initiative": 0,
            "hp": 0,
            "max_hp": 0,
            "ac": 10, # Default AC
            "status": ""
        }
        try:
            combatant_data["initiative"] = int(self.initiative_table.item(row, 1).text()) if self.initiative_table.item(row, 1) else 0
            combatant_data["hp"] = int(self.initiative_table.item(row, 2).text()) if self.initiative_table.item(row, 2) else 0
            combatant_data["max_hp"] = int(self.initiative_table.item(row, 3).text()) if self.initiative_table.item(row, 3) else combatant_data["hp"] # Use current HP as max if missing
            combatant_data["ac"] = int(self.initiative_table.item(row, 4).text()) if self.initiative_table.item(row, 4) else 10
            combatant_data["status"] = self.initiative_table.item(row, 5).text() if self.initiative_table.item(row, 5) else ""
        except (ValueError, AttributeError) as e:
             print(f"[Combat Tracker] Error getting basic data from table for row {row}: {e}")

        # Try to get more detailed data from the stored self.combatants dictionary
        if row in self.combatants:
            stored_data = self.combatants[row]
            print(f"[Combat Tracker] Found stored data for row {row}: {type(stored_data)}")
            # If stored_data is an object, convert to dict if possible
            if hasattr(stored_data, '__dict__'):
                 # Combine basic table data with stored object attributes
                 # Prioritize stored data if keys overlap (except maybe HP/Status)
                 more_data = stored_data.__dict__
                 # Keep current HP/Status from table, but add other details
                 current_hp = combatant_data["hp"]
                 current_status = combatant_data["status"]
                 combatant_data.update(more_data) # Update with object data
                 combatant_data["hp"] = current_hp # Restore table HP
                 combatant_data["status"] = current_status # Restore table status
                 print(f"[Combat Tracker] Merged object data into combatant_data")
            elif isinstance(stored_data, dict):
                 # Combine basic table data with stored dictionary data
                 # Prioritize stored data if keys overlap (except maybe HP/Status)
                 more_data = stored_data
                 current_hp = combatant_data["hp"]
                 current_status = combatant_data["status"]
                 combatant_data.update(more_data) # Update with stored dict data
                 combatant_data["hp"] = current_hp # Restore table HP
                 combatant_data["status"] = current_status # Restore table status
                 print(f"[Combat Tracker] Merged dictionary data into combatant_data")
            else:
                 print(f"[Combat Tracker] Stored data for row {row} is not a dict or object with __dict__.")
        else:
             print(f"[Combat Tracker] No stored data found in self.combatants for row {row}. Using table data only.")

        # Create and execute the details dialog
        print(f"[Combat Tracker] Final data for dialog: {combatant_data}")
        dialog = CombatantDetailsDialog(self, combatant_data, combatant_type)
        dialog.exec()

    def _on_selection_changed(self):
        """Handle when the selection in the initiative table changes"""
        selected_items = self.initiative_table.selectedItems()
        if not selected_items:
            # If selection is cleared, potentially clear details pane or do nothing
            # self.current_details_combatant = None
            # self._clear_details_layouts() 
            return
            
        # Get the selected row (selectedItems gives all cells in the row)
        row = selected_items[0].row()
        
        # If details pane is visible, update it with the selected combatant
        # Avoid calling _view_combatant_details directly if it causes loops
        # Store selected combatant info and call update method
        if row in self.combatants:
             self.current_details_combatant = self.combatants[row]
             name_item = self.initiative_table.item(row, 0)
             self.current_details_type = name_item.data(Qt.UserRole) if name_item else "custom" 
        else:
            # Handle cases where there's no stored data (e.g., manually added)
            # Create temporary data from table for display
             name_item = self.initiative_table.item(row, 0)
             type_item = self.initiative_table.item(row, 7)
             self.current_details_combatant = {
                 "name": name_item.text() if name_item else "Manual Entry",
                 "hp": self.initiative_table.item(row, 2).text() if self.initiative_table.item(row, 2) else "0",
                 "max_hp": self.initiative_table.item(row, 3).text() if self.initiative_table.item(row, 3) else "0",
                 "ac": self.initiative_table.item(row, 4).text() if self.initiative_table.item(row, 4) else "10",
                 "status": self.initiative_table.item(row, 5).text() if self.initiative_table.item(row, 5) else "",
             }
             self.current_details_type = type_item.text().lower() if type_item else "custom"
        
        if self.show_details_pane:
             self._update_details_pane() # Update the pane content

    def _toggle_details_pane(self):
        """Toggle visibility of the details pane"""
        self.show_details_pane = not self.show_details_pane
        
        # Log which action we're taking
        action = "showing" if self.show_details_pane else "hiding"
        print(f"[CombatTracker] {action} details pane")
    
    def _update_details_pane(self):
        """Placeholder for details pane update - no longer needed with new UI but referenced in code"""
        print("[CombatTracker] _update_details_pane called - this is a placeholder in the new UI")
        # No actual implementation needed with the new UI design

    def _fix_missing_types(self):
        """Fix any missing combatant types for existing entries after initialization or state restore."""
        # Check if table exists and has rows
        if not hasattr(self, 'initiative_table') or self.initiative_table.rowCount() == 0:
            return 0 # Nothing to fix
            
        fix_count = 0
        print("[CombatTracker] Running _fix_missing_types...")
        
        for row in range(self.initiative_table.rowCount()):
            name_item = self.initiative_table.item(row, 0)
            type_item = self.initiative_table.item(row, 7) # Type is column 7
            name = name_item.text() if name_item else f"Row {row}"
            
            # Check if type is missing or invalid
            current_type = type_item.text().lower().strip() if type_item and type_item.text() else None
            needs_fix = not current_type or current_type not in ["monster", "character", "manual"]
            
            # Also check if UserRole data is missing (used by context menu/details)
            if name_item and name_item.data(Qt.UserRole) is None:
                needs_fix = True

            if needs_fix:
                inferred_type = ""
                # 1. Check stored combatant data first
                if row in self.combatants:
                    data = self.combatants[row]
                    if isinstance(data, dict):
                        if any(k in data for k in ["monster_id", "size", "challenge_rating", "hit_points"]):
                            inferred_type = "monster"
                        elif any(k in data for k in ["character_class", "level", "race"]):
                            inferred_type = "character"
                    elif hasattr(data, '__dict__'): # Handle object data
                         if hasattr(data, 'size') or hasattr(data, 'challenge_rating') or hasattr(data, 'hit_points'):
                            inferred_type = "monster"
                         elif hasattr(data, 'character_class') or hasattr(data, 'level') or hasattr(data, 'race'):
                            inferred_type = "character"
                
                # 2. If still unknown, use name-based heuristics
                if not inferred_type:
                    monster_names = ["goblin", "ogre", "dragon", "troll", "zombie", "skeleton", 
                                     "ghoul", "ghast", "ghost", "demon", "devil", "elemental", "giant"]
                    lower_name = name.lower()
                    
                    if any(monster in lower_name for monster in monster_names):
                        inferred_type = "monster"
                    elif "(npc)" in lower_name:
                        inferred_type = "character"
                    elif name == "Add your party here!": # Handle placeholder
                         inferred_type = "character"
                    else:
                        # Default fallback - might be risky, consider 'manual'?
                        inferred_type = "manual" 
                
                # Apply the fix
                if not type_item:
                    type_item = QTableWidgetItem()
                    self.initiative_table.setItem(row, 7, type_item)
                
                if type_item.text() != inferred_type:
                     type_item.setText(inferred_type)
                     
                # Also fix UserRole data on name item
                if name_item and name_item.data(Qt.UserRole) != inferred_type:
                    name_item.setData(Qt.UserRole, inferred_type)
                    
                fix_count += 1
                print(f"[CombatTracker] Fixed missing/invalid type for '{name}' (row {row}) - set to '{inferred_type}'")
        
        if fix_count > 0:
            print(f"[CombatTracker] Fixed types for {fix_count} combatants")
        else:
             print("[CombatTracker] _fix_missing_types: No types needed fixing.")
        
        return fix_count

    def _toggle_concentration(self, row):
        """Toggle concentration state for a combatant"""
        if row not in self.concentrating:
            self.concentrating.add(row)
            # Log concentration gained
            self._log_combat_action("Effect Started", "DM", "gained concentration", "", "")
        else:
            self.concentrating.remove(row)
            # Log concentration broken
            self._log_combat_action("Effect Ended", "DM", "lost concentration", "", "")

    def closeEvent(self, event):
        # Call parent closeEvent
        super().closeEvent(event)

    # This method is the SLOT connected to the CombatResolver's resolution_complete signal.
    # It MUST be defined before it's connected in __init__.
    @Slot(object, object)
    def _process_resolution_ui(self, result, error):
        """Process the combat resolution result from the resolver"""
        # Import needed modules at the start
        import copy
        import gc
        import traceback
        from PySide6.QtWidgets import QApplication
        
        print("[CombatTracker] _process_resolution_ui called - processing combat results")
        
        try:
            # Cancel safety timers if they exist
            if hasattr(self, '_safety_timer') and self._safety_timer:
                self._safety_timer.stop()
                print("[CombatTracker] Canceled safety timer")
                
            if hasattr(self, '_backup_timer') and self._backup_timer:
                self._backup_timer.stop()
                print("[CombatTracker] Canceled backup timer")
            
            # Reset UI elements first
            self._reset_resolve_button("Fast Resolve", True)
            
            # Ensure the _is_resolving_combat flag is reset
            self._is_resolving_combat = False
            print("[CombatTracker] Setting _is_resolving_combat = False")
            
            # Force UI update immediately
            QApplication.processEvents()
            
            # Disconnect signal to prevent memory leaks
            try:
                self.app_state.combat_resolver.resolution_complete.disconnect(self._process_resolution_ui)
                print("[CombatTracker] Successfully disconnected resolution_complete signal")
            except Exception as disconnect_error:
                print(f"[CombatTracker] Failed to disconnect signal: {disconnect_error}")
            
            # Handle error first
            if error:
                self.combat_log_text.append(f"<p style='color:red;'><b>Error:</b> {error}</p>")
                # Force immediate UI update
                QApplication.processEvents()
                # Force garbage collection
                gc.collect()
                return
                
            if not result:
                self.combat_log_text.append("<p style='color:orange;'><b>Warning:</b> Combat resolution produced no result.</p>")
                # Force immediate UI update
                QApplication.processEvents()
                # Force garbage collection
                gc.collect()
                return
            
            # Extract results and update the UI
            # Save the existing combat log content before we modify it
            existing_log = ""
            try:
                existing_log = self.combat_log_text.toHtml()
                print("[CombatTracker] Preserved existing combat log")
            except Exception as log_error:
                print(f"[CombatTracker] Error preserving existing log: {log_error}")
            
            # Make a deep copy of result to prevent reference issues
            local_result = copy.deepcopy(result)
            
            # Clear the original reference to help GC
            result = None
            
            # Force garbage collection
            gc.collect()
            
            # Now work with local copy
            final_narrative = local_result.get("narrative", "No narrative provided.")
            combatants = local_result.get("updates", [])
            log_entries = local_result.get("log", [])
            round_count = local_result.get("rounds", 0)
            
            print(f"[CombatTracker] Processing combat results: {len(combatants)} combatants, {len(log_entries)} log entries, {round_count} rounds")
            
            # Make another deep copy of combatants to ensure no reference issues during updates
            combatants_copy = copy.deepcopy(combatants)
            
            # Clear original reference
            combatants = None
            
            # Update the UI first with an interim message
            self.combat_log_text.append("<hr>")
            self.combat_log_text.append("<h3 style='color:#000088;'>Processing Combat Results...</h3>")
            
            # Force UI update before applying updates
            QApplication.processEvents()
            
            # Apply the updates to the table, getting combatants that were removed
            removed_count, update_summaries = self._apply_combat_updates(combatants_copy)
            
            # Force UI update after applying updates
            QApplication.processEvents()
            
            # Build a detailed summary for the user
            turn_count = len(log_entries)
            survivors_details = []
            casualties = []
            
            # Process each combatant in the table
            for row in range(self.initiative_table.rowCount()):
                name_item = self.initiative_table.item(row, 0)
                hp_item = self.initiative_table.item(row, 2)
                status_item = self.initiative_table.item(row, 5)
                
                
                if name_item and hp_item:
                    name = name_item.text()
                    hp = hp_item.text()
                    status_text = status_item.text() if status_item else ""
                    
                    # Add death saves info for unconscious characters
                    death_saves_text = ""
                    saves = self.death_saves.get(row, None)
                    if saves:
                        successes = saves.get("successes", 0)
                        failures = saves.get("failures", 0)
                        death_saves_text = f" [DS: {successes}S/{failures}F]"

                    # Add to survivors/casualties list
                    if status_text and "dead" in status_text.lower():
                        casualties.append(name)
                    else:
                        survivors_details.append(f"{name}: {hp} HP ({status_text}){death_saves_text}")

            # Prepare final combat log with the original content preserved
            final_log = existing_log
            
            # Check if we should append to existing log or start fresh
            if "Combat Concluded" in final_log:
                # Previous combat summary exists, clear the log and start fresh
                final_log = ""
            
            # Build summary content
            summary_content = "<hr>\n"
            summary_content += "<h3 style='color:#000088;'>Combat Concluded</h3>\n"
            summary_content += f"<p>{final_narrative}</p>\n"
            summary_content += f"<p><b>Duration:</b> {round_count} rounds, {turn_count} turns</p>\n"
            
            # Add turn-by-turn log if available
            if log_entries:
                summary_content += "<p><b>Combat Log:</b></p>\n<div style='max-height: 200px; overflow-y: auto; border: 1px solid #ccc; padding: 5px; margin: 5px 0;'>\n"
                for entry in log_entries:
                    round_num = entry.get("round", "?")
                    actor = entry.get("actor", "Unknown")
                    action = entry.get("action", "")
                    result_text = entry.get("result", "")
                    
                    summary_content += f"<p><b>Round {round_num}:</b> {actor} {action}"
                    if result_text:
                        summary_content += f" - {result_text}"
                    summary_content += "</p>\n"
                summary_content += "</div>\n"
            
            # Add survivors
            if survivors_details:
                summary_content += "<p><b>Survivors:</b></p>\n<ul>\n"
                for survivor in survivors_details:
                    summary_content += f"<li>{survivor}</li>\n"
                summary_content += "</ul>\n"
            else:
                summary_content += "<p><b>Survivors:</b> None!</p>\n"
                
            # Add casualties
            if casualties:
                summary_content += "<p><b>Casualties:</b></p>\n<ul>\n"
                for casualty in casualties:
                    summary_content += f"<li>{casualty}</li>\n"
                summary_content += "</ul>\n"
            
            # Now update the combat log with our final content
            if final_log:
                # Append to existing log
                self.combat_log_text.setHtml(final_log)
                self.combat_log_text.append(summary_content)
            else:
                # Start fresh with summary only
                self.combat_log_text.setHtml(summary_content)
            
            # Explicitly set cursor to end and scroll to bottom
            cursor = self.combat_log_text.textCursor()
            cursor.movePosition(QTextCursor.End)
            self.combat_log_text.setTextCursor(cursor)
            
            # Scroll to the bottom to see the summary
            scrollbar = self.combat_log_text.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
            
            # Final UI update
            QApplication.processEvents()
            
            # Clean up the rest of the references
            local_result = None
            log_entries = None
            combatants_copy = None
            survivors_details = None
            casualties = None
            
            # Final garbage collection
            gc.collect()
            
            print("[CombatTracker] Combat results processing completed successfully")
            
        except Exception as e:
            traceback.print_exc()
            print(f"[CombatTracker] Error in _process_resolution_ui: {e}")
            
            # Always reset button state no matter what
            self._reset_resolve_button("Fast Resolve", True)
            self._is_resolving_combat = False
            
            # Log the error
            self.combat_log_text.append(f"<p style='color:red;'><b>Error:</b> An error occurred while processing the combat result: {str(e)}</p>")
            
            # Force garbage collection
            gc.collect()

    def _clear_combat_log(self):
        """Clear the combat log display"""
        self.combat_log_text.clear()
        self.combat_log_text.setHtml("<p><i>Combat log cleared.</i></p>")

    def _reset_resolve_button(self, text="Fast Resolve", enabled=True):
        """Guaranteed method to reset the button state using the main UI thread"""
        # Direct update on the UI thread
        self.fast_resolve_button.setEnabled(enabled)
        self.fast_resolve_button.setText(text)
        
        # Force immediate UI update
        from PySide6.QtWidgets import QApplication
        QApplication.processEvents()
        
        print(f"[CombatTracker] Reset Fast Resolve button to '{text}' (enabled: {enabled})")

    def _check_and_reset_button(self):
        """Check if the button should be reset and reset it if necessary"""
        # Check if the button text is still in "Initializing..." state after our timer
        if self.fast_resolve_button.text() == "Initializing..." or self.fast_resolve_button.text().startswith("Resolving"):
            print("[CombatTracker] Backup timer detected hanging button, forcing reset")
            self._reset_resolve_button("Fast Resolve", True)
            
            # Also log this to the combat log for user awareness
            self.combat_log_text.append("<p style='color:orange;'><b>Notice:</b> Combat resolution timed out or is taking too long. The Fast Resolve button has been reset.</p>")
            
            # Maybe the combat resolver is still running - force all needed flag resets too
            self._is_resolving_combat = False

    # ---------------------------------------------------------------
    # Helper: remove currently selected combatants (invoked by the
    # context‑menu 'Remove' action).
    # ---------------------------------------------------------------
    def _remove_selected(self):
        """Remove all currently selected rows from the combat tracker.

        We reuse the existing _cleanup_dead_combatants logic to ensure all
        bookkeeping (death_saves, concentrating sets, current_turn index,
        etc.) is handled in one place.
        """

        # Determine which rows are selected.
        rows = sorted({idx.row() for idx in self.initiative_table.selectedIndexes()})
        if not rows:
            return

        # Ask for confirmation to prevent accidental deletion.
        reply = QMessageBox.question(
            self,
            "Remove Combatant(s)",
            f"Remove {len(rows)} selected combatant(s) from the tracker?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        # Tag each selected combatant as Dead so that the existing cleanup
        # routine will remove them and handle all related state.
        for row in rows:
            if row >= self.initiative_table.rowCount():
                continue
            status_item = self.initiative_table.item(row, 5)
            if status_item is None:
                status_item = QTableWidgetItem()
                self.initiative_table.setItem(row, 5, status_item)
            status_item.setText("Dead")

        # Now invoke the shared cleanup function to physically remove rows.
        self._cleanup_dead_combatants()
