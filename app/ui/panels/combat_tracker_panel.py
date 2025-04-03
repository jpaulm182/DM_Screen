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
"""

from PySide6.QtWidgets import (
    QTableWidget, QTableWidgetItem, QHeaderView, QPushButton,
    QLineEdit, QSpinBox, QHBoxLayout, QVBoxLayout, QComboBox,
    QLabel, QCheckBox, QMenu, QMessageBox, QDialog, QDialogButtonBox,
    QGroupBox, QWidget, QStyledItemDelegate, QStyle, QToolButton,
    QTabWidget, QScrollArea, QFormLayout, QFrame
)
from PySide6.QtCore import Qt, QTimer, Signal, Slot, QSize
from PySide6.QtGui import QAction, QColor, QIcon, QKeySequence, QBrush, QPalette
import random

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
    
    def __init__(self, app_state):
        """Initialize combat tracker panel"""
        self.combat_started = False
        self.current_turn = -1
        self.previous_turn = -1
        self.current_round = 1  # Current combat round
        self.elapsed_time = 0  # Seconds of combat
        self.timer_running = False
        self.timer = QTimer()
        self.timer.timeout.connect(self._update_timer)
        self.timer.setInterval(1000)  # 1 second interval
        
        # Set up time tracking variables
        self.combat_in_game_seconds = 0  # Time passed in game during combat
        
        # Tracking sets for special conditions
        self.concentrating = set()  # Set of rows with concentration
        self.death_saves = {}  # Dict of row -> {successes, failures}
        
        # Store combatant data for monster/character viewing
        self.combatants = {}  # Dict of row index -> Monster or PlayerCharacter object
        
        super().__init__(app_state, "Combat Tracker")
        
        # Connect combat resolver signals
        self.resolution_complete.connect(self._process_resolution_ui)

    def _setup_ui(self):
        """Set up the combat tracker UI"""
        # Add keyboard shortcuts
        next_turn_shortcut = QKeySequence(Qt.CTRL | Qt.Key_Space)
        self.next_turn_action = QAction("Next Combatant", self)
        self.next_turn_action.setShortcut(next_turn_shortcut)
        self.next_turn_action.triggered.connect(self._next_turn)
        self.addAction(self.next_turn_action)

        sort_shortcut = QKeySequence(Qt.CTRL | Qt.Key_S)
        self.sort_action = QAction("Sort Initiative", self)
        self.sort_action.setShortcut(sort_shortcut)
        self.sort_action.triggered.connect(self._sort_initiative)
        self.addAction(self.sort_action)

        timer_shortcut = QKeySequence(Qt.CTRL | Qt.Key_T)
        self.timer_action = QAction("Toggle Timer", self)
        self.timer_action.setShortcut(timer_shortcut)
        self.timer_action.triggered.connect(self._toggle_timer)
        self.addAction(self.timer_action)
        
        # HP adjustment shortcuts
        damage_1_shortcut = QKeySequence(Qt.Key_1)
        self.damage_1_action = QAction("Damage 1", self)
        self.damage_1_action.setShortcut(damage_1_shortcut)
        self.damage_1_action.triggered.connect(lambda: self._quick_damage(1))
        self.addAction(self.damage_1_action)
        
        damage_5_shortcut = QKeySequence(Qt.Key_2)
        self.damage_5_action = QAction("Damage 5", self)
        self.damage_5_action.setShortcut(damage_5_shortcut)
        self.damage_5_action.triggered.connect(lambda: self._quick_damage(5))
        self.addAction(self.damage_5_action)
        
        damage_10_shortcut = QKeySequence(Qt.Key_3)
        self.damage_10_action = QAction("Damage 10", self)
        self.damage_10_action.setShortcut(damage_10_shortcut)
        self.damage_10_action.triggered.connect(lambda: self._quick_damage(10))
        self.addAction(self.damage_10_action)
        
        heal_1_shortcut = QKeySequence(Qt.SHIFT | Qt.Key_1)
        self.heal_1_action = QAction("Heal 1", self)
        self.heal_1_action.setShortcut(heal_1_shortcut)
        self.heal_1_action.triggered.connect(lambda: self._quick_heal(1))
        self.addAction(self.heal_1_action)
        
        heal_5_shortcut = QKeySequence(Qt.SHIFT | Qt.Key_2)
        self.heal_5_action = QAction("Heal 5", self)
        self.heal_5_action.setShortcut(heal_5_shortcut)
        self.heal_5_action.triggered.connect(lambda: self._quick_heal(5))
        self.addAction(self.heal_5_action)
        
        heal_10_shortcut = QKeySequence(Qt.SHIFT | Qt.Key_3)
        self.heal_10_action = QAction("Heal 10", self)
        self.heal_10_action.setShortcut(heal_10_shortcut)
        self.heal_10_action.triggered.connect(lambda: self._quick_heal(10))
        self.addAction(self.heal_10_action)

        # Create main layout
        main_layout = QVBoxLayout()
        
        # Add shortcuts info
        shortcuts_label = QLabel(
            "Shortcuts: Next Combatant (Ctrl+Space) | Sort (Ctrl+S) | Timer (Ctrl+T) | "
            "Damage (1,2,3) | Heal (Shift+1,2,3)"
        )
        shortcuts_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(shortcuts_label)
        
        # Control area
        control_layout = self._setup_control_area()
        main_layout.addLayout(control_layout)
        
        # Initiative table
        self.initiative_table = QTableWidget(0, 7)  # Added Concentration column
        self.initiative_table.setHorizontalHeaderLabels([
            "Name", "Initiative", "HP", "AC", "Status", "Concentration", "Notes"
        ])
        
        # Set column widths
        header = self.initiative_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)  # Name
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Initiative
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # HP
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # AC
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # Status
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)  # Concentration
        header.setSectionResizeMode(6, QHeaderView.Stretch)  # Notes
        
        # Context menu
        self.initiative_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.initiative_table.customContextMenuRequested.connect(self._show_context_menu)
        
        # Enable item editing for HP column
        self.initiative_table.setEditTriggers(QTableWidget.DoubleClicked | QTableWidget.SelectedClicked)
        
        # Set HP column delegate for direct editing
        self.hp_delegate = HPUpdateDelegate(self)
        self.hp_delegate.hpChanged.connect(self._hp_changed)
        self.initiative_table.setItemDelegateForColumn(2, self.hp_delegate)
        
        main_layout.addWidget(self.initiative_table)
        
        # Add combatant controls
        add_layout = self._setup_add_combatant_controls()
        main_layout.addLayout(add_layout)
        
        # Sort button
        sort_button = QPushButton("Sort Initiative")
        sort_button.clicked.connect(self._sort_initiative)
        main_layout.addWidget(sort_button)
        
        # Set the main layout
        self.setLayout(main_layout)
        
        # Initialize the table with proper size
        self.initiative_table.horizontalHeader().setStretchLastSection(True)
        self.initiative_table.verticalHeader().setVisible(False)
        self.initiative_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.initiative_table.setSelectionMode(QTableWidget.ExtendedSelection)
        
        # Apply custom stylesheet for basic appearance (delegate handles highlight)
        self.initiative_table.setStyleSheet('''
            QTableWidget {
                alternate-background-color: #f8f8f8; /* Very light gray for alternates */
                background-color: #ffffff; /* White base */
                gridline-color: #e0e0e0; /* Lighter gray grid lines */
                selection-background-color: #a0c4ff; /* Color for selected row (non-active turn) */
                selection-color: black; /* Text color for selected row */
            }
            QTableWidget::item {
                padding: 5px; /* Add some padding */
                color: black; /* Default text color */
                /* Alternating background handled by QTableWidget */
            }
            /* Highlight rule removed - handled by delegate */
            /* QTableWidget::item[is_current_turn="true"] { ... } */
        ''')
        
        # Set the custom delegate for painting
        self.initiative_table.setItemDelegate(CurrentTurnDelegate(self.initiative_table))
        
        # Set minimum sizes
        self.setMinimumSize(800, 400)
        self.initiative_table.setMinimumHeight(200)
    
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
        
        add_button = QPushButton("Add")
        add_button.clicked.connect(self._add_combatant)
        add_layout.addWidget(add_button)
        
        return add_layout
    
    def _add_combatant(self, name, initiative, hp, ac):
        """Add a new combatant to initiative order"""
        table = self.initiative_table
        row = table.rowCount()
        table.insertRow(row)
        
        # Name
        name_item = QTableWidgetItem(name)
        table.setItem(row, 0, name_item)
        
        # Initiative
        init_item = QTableWidgetItem(str(initiative))
        init_item.setTextAlignment(Qt.AlignCenter)
        table.setItem(row, 1, init_item)
        
        # HP
        hp_item = QTableWidgetItem(str(hp))
        hp_item.setTextAlignment(Qt.AlignCenter)
        hp_item.setData(Qt.UserRole, hp)  # Store max HP
        table.setItem(row, 2, hp_item)
        
        # AC
        ac_item = QTableWidgetItem(str(ac))
        ac_item.setTextAlignment(Qt.AlignCenter)
        table.setItem(row, 3, ac_item)
        
        # Status - empty initially
        table.setItem(row, 4, QTableWidgetItem(""))
        
        # Concentration checkbox
        conc_item = QTableWidgetItem()
        conc_item.setCheckState(Qt.Unchecked)
        conc_item.setTextAlignment(Qt.AlignCenter)
        table.setItem(row, 5, conc_item)
        
        # Empty notes
        table.setItem(row, 6, QTableWidgetItem(""))
        
        # Sort after adding
        self._sort_initiative()
        
        # Return the row where it was inserted after sorting
        for row in range(table.rowCount()):
            if table.item(row, 0).text() == name and table.item(row, 1).text() == str(initiative):
                return row
        
        return -1  # Not found (shouldn't happen)
    
    def _sort_initiative(self):
        """Sort the initiative tracker by initiative value (descending)"""
        if self.initiative_table.rowCount() <= 1:
            return
        
        # Get current selection
        selected_rows = [index.row() for index in self.initiative_table.selectionModel().selectedRows()]
        selected_names = [self.initiative_table.item(row, 0).text() for row in selected_rows]
        
        # Remember current turn
        current_name = ""
        if 0 <= self.current_turn < self.initiative_table.rowCount():
            current_name = self.initiative_table.item(self.current_turn, 0).text()
        
        # Create a list of rows with their initiative values
        rows = []
        for row in range(self.initiative_table.rowCount()):
            init_item = self.initiative_table.item(row, 1)
            if init_item:
                init_value = float(init_item.text())
                rows.append((row, init_value))
        
        # Sort by initiative (highest first)
        rows.sort(key=lambda x: (x[1], random.random()), reverse=True)
        
        # Save combatant data keyed by row before reordering
        old_combatants = self.combatants.copy()
        
        # Remember items to restore
        items = []
        # Track the mapping of old_row to new_row
        row_map = {}
        
        for i, (old_row, _) in enumerate(rows):
            row_items = []
            for col in range(self.initiative_table.columnCount()):
                item = self.initiative_table.takeItem(old_row, col)
                # Clone item to avoid issues
                new_item = QTableWidgetItem()
                new_item.setText(item.text())
                if hasattr(item, 'checkState'):
                    new_item.setCheckState(item.checkState())
                for role in [Qt.UserRole, Qt.UserRole + 1]:
                    if item.data(role) is not None:
                        new_item.setData(role, item.data(role))
                new_item.setTextAlignment(item.textAlignment())
                row_items.append(new_item)
            items.append(row_items)
            
            # Record the mapping of old_row to its new position
            row_map[old_row] = i
        
        # Clear the table and add items back in sorted order
        self.initiative_table.setRowCount(0)
        for row_items in items:
            row = self.initiative_table.rowCount()
            self.initiative_table.insertRow(row)
            for col, item in enumerate(row_items):
                self.initiative_table.setItem(row, col, item)
        
        # Remap the combatants dictionary based on new row order
        new_combatants = {}
        for old_row, combatant in old_combatants.items():
            if old_row in row_map:
                new_row = row_map[old_row]
                new_combatants[new_row] = combatant
        self.combatants = new_combatants
        
        # Remap tracking sets as well
        new_concentrating = set()
        for old_row in self.concentrating:
            if old_row in row_map:
                new_concentrating.add(row_map[old_row])
        self.concentrating = new_concentrating
        
        new_death_saves = {}
        for old_row, saves in self.death_saves.items():
            if old_row in row_map:
                new_death_saves[row_map[old_row]] = saves
        self.death_saves = new_death_saves
        
        # Restore selection
        if selected_names:
            self.initiative_table.clearSelection()
            for row in range(self.initiative_table.rowCount()):
                name = self.initiative_table.item(row, 0).text()
                if name in selected_names:
                    self.initiative_table.selectRow(row)
        
        # Update current turn index if combat has started
        if current_name and self.combat_started:
            for row in range(self.initiative_table.rowCount()):
                if self.initiative_table.item(row, 0).text() == current_name:
                    self.current_turn = row
                    break
        
        # Update the highlighting
        self._update_highlight()
    
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
            hp_item = self.initiative_table.item(row, 2)
            if hp_item:
                current_hp = int(hp_item.text())
                max_hp = hp_item.data(Qt.UserRole)
                
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
            hp_item = self.initiative_table.item(row, 2)
            if hp_item:
                current_hp = int(hp_item.text())
                max_hp = hp_item.data(Qt.UserRole)
                
                new_hp = min(current_hp + amount, max_hp)
                hp_item.setText(str(new_hp))
    
    def _hp_changed(self, row, new_hp):
        """Handle HP changes from delegate editing"""
        if 0 <= row < self.initiative_table.rowCount():
            # Get current HP
            hp_item = self.initiative_table.item(row, 2)
            if hp_item:
                # Already updated via setModelData, check for special cases
                if new_hp == 0:
                    name = self.initiative_table.item(row, 0).text()
                    QMessageBox.information(
                        self,
                        "HP Reduced to 0",
                        f"{name} is down! Remember to track death saves."
                    )
    
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
        
        # Death saves
        hp_item = self.initiative_table.item(row, 2)
        if hp_item and int(hp_item.text()) <= 0:
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
        
        # Show the menu
        menu.exec_(self.initiative_table.mapToGlobal(position))
    
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
                hp_item = self.initiative_table.item(row, 2)
                if not hp_item:
                    continue
                    
                name_item = self.initiative_table.item(row, 0)
                if not name_item:
                    continue
                    
                combatant_name = name_item.text()
                
                try:
                    current_hp = int(hp_item.text() or "0")
                    
                    if is_healing:
                        new_hp = current_hp + amount
                        max_hp = hp_item.data(Qt.UserRole) or 0
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
                        status_item = self.initiative_table.item(row, 4)
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
                        max_hp = hp_item.data(Qt.UserRole)
                        if max_hp:
                            # Set up death saves tracking if not already
                            if row not in self.death_saves:
                                self.death_saves[row] = {"successes": 0, "failures": 0}
                except ValueError:
                    # Handle invalid HP value
                    pass
    
    def _check_concentration(self, row, damage):
        """Check if concentration is maintained after taking damage"""
        conc_item = self.initiative_table.item(row, 5)
        if conc_item and conc_item.checkState() == Qt.Checked:
            dc = max(10, damage // 2)
            name = self.initiative_table.item(row, 0).text()
            
            # Roll the concentration check
            roll = random.randint(1, 20)
            success = roll >= dc
            
            # Log concentration check
            self._log_combat_action(
                "Status Effect", 
                name, 
                "rolled concentration check", 
                result=f"DC {dc}, Roll: {roll}, {'Success' if success else 'Failure'}"
            )
            
            # If concentration check failed
            if not success:
                conc_item.setCheckState(Qt.Unchecked)
                self.concentrating.discard(row)
                
                # Log concentration lost
                self._log_combat_action(
                    "Status Effect", 
                    name, 
                    "lost concentration", 
                    result="Failed check"
                )
                
                # Show message
                QMessageBox.information(
                    self,
                    "Concentration Lost",
                    f"{name} failed DC {dc} concentration check with roll of {roll}."
                )
            else:
                # Show message for successful check
                QMessageBox.information(
                    self,
                    "Concentration Maintained",
                    f"{name} passed DC {dc} concentration check with roll of {roll}."
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
                status_item = self.initiative_table.item(row, 4)
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
            self.timer.start(1000)  # Update every second
            self.timer_button.setText("Stop")
    
    def _update_timer(self):
        """Update the combat timer display"""
        self.elapsed_time += 1
        hours = self.elapsed_time // 3600
        minutes = (self.elapsed_time % 3600) // 60
        seconds = self.elapsed_time % 60
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
            self.elapsed_time = 0
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
            self.elapsed_time = 0
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
            "elapsed_time": self.elapsed_time,
            "combatants": [],
            "death_saves": self.death_saves,
            "concentrating": list(self.concentrating)
        }
        
        # Save all combatants
        for row in range(self.initiative_table.rowCount()):
            combatant = {}
            for col, key in enumerate(["name", "initiative", "hp", "ac", "status", "concentration", "notes"]):
                item = self.initiative_table.item(row, col)
                if col == 5:  # Concentration
                    combatant[key] = item.checkState() == Qt.Checked if item else False
                else:
                    combatant[key] = item.text() if item else ""
                
                # Save max HP
                if col == 2 and item:
                    combatant["max_hp"] = item.data(Qt.UserRole)
            
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
        
        # Restore round and turn
        self.current_round = state.get("round", 1)
        self.round_spin.setValue(self.current_round)
        
        self.current_turn = state.get("turn", 0)
        self.elapsed_time = state.get("elapsed_time", 0)
        self._update_timer()
        
        # Restore death saves and concentration
        self.death_saves = state.get("death_saves", {})
        self.concentrating = set(state.get("concentrating", []))
        
        # Restore combatants
        for combatant in state.get("combatants", []):
            row = self.initiative_table.rowCount()
            self.initiative_table.insertRow(row)
            
            # Restore each field
            for col, key in enumerate(["name", "initiative", "hp", "ac", "status", "concentration", "notes"]):
                value = combatant.get(key, "")
                item = QTableWidgetItem()
                
                if col == 5:  # Concentration
                    item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                    item.setCheckState(Qt.Checked if value else Qt.Unchecked)
                else:
                    item.setText(str(value))
                
                # Restore max HP
                if col == 2:
                    item.setData(Qt.UserRole, combatant.get("max_hp", value))
                
                self.initiative_table.setItem(row, col, item)
        
        # Highlight current turn
        self._update_highlight()

    @Slot(list) # Explicitly mark as a slot receiving a list
    def add_combatant_group(self, monster_dicts: list):
        """Add a list of monsters (as dictionaries) to the combat tracker."""
        if not isinstance(monster_dicts, list):
            print(f"[CombatTracker] Error: add_combatant_group received non-list: {type(monster_dicts)}")
            return
            
        print(f"[CombatTracker] Received group of {len(monster_dicts)} monsters to add.")
        
        added_count = 0
        for monster_data in monster_dicts:
            try:
                self.add_monster(monster_data)
                added_count += 1
            except Exception as e:
                import traceback
                name = monster_data.get("name", "Unknown") if isinstance(monster_data, dict) else getattr(monster_data, "name", "Unknown")
                print(f"[CombatTracker] Error adding monster '{name}' from group: {e}")
                traceback.print_exc()  # Print the full traceback for debugging

        if added_count > 0:
             print(f"[CombatTracker] Added {added_count} monsters from group.")
             self._sort_initiative() # Sort after adding group
        else:
             print("[CombatTracker] No monsters were added from the group.")

    def add_monster(self, monster_data):
        """Add a monster from monster panel to the tracker"""
        if not monster_data:
            return
        
        # Debug: Print the monster data structure to understand the format
        print(f"[CombatTracker] Adding monster: {type(monster_data)}")
        if isinstance(monster_data, dict):
            print(f"[CombatTracker] Monster keys: {list(monster_data.keys())}")
        
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
                
                # Check if stats are nested in a 'stats' dictionary
                if 'stats' in obj and isinstance(obj['stats'], dict):
                    if attr in obj['stats']:
                        return obj['stats'][attr]
                    for alt_attr in alt_attrs:
                        if alt_attr in obj['stats']:
                            return obj['stats'][alt_attr]
                
                return default
            
            # Try getattr for object access
            if hasattr(obj, attr):
                return getattr(obj, attr)
            
            # Try alternative attributes for objects
            for alt_attr in alt_attrs:
                if hasattr(obj, alt_attr):
                    return getattr(obj, alt_attr)
            
            return default
        
        name = get_attr(monster_data, "name", "Unknown Monster")
        
        # Extract challenge rating to calculate approximate initiative bonus
        cr = get_attr(monster_data, "challenge_rating", "0", ["cr"])
        try:
            # Handle fractional CR values
            if isinstance(cr, str) and '/' in cr:
                num, denom = cr.split('/')
                cr_value = float(num) / float(denom)
            else:
                cr_value = float(cr)
                
            # Calculate a plausible initiative bonus based on DEX and CR
            dex = get_attr(monster_data, "dexterity", 10, ["dex"])
            if isinstance(dex, str):
                dex = int(dex)
            dex_mod = (dex - 10) // 2
            
            
            # Initiative bonus based on DEX, +0-3 based on CR
            initiative_bonus = dex_mod + min(3, int(cr_value / 5))
        except (ValueError, TypeError):
            # Default to +0 if any calculation errors
            initiative_bonus = 0
        
        # Roll initiative with the bonus
        initiative_roll = random.randint(1, 20) + initiative_bonus
        
        # Extract hit points
        hp_text = str(get_attr(monster_data, "hit_points", "10", ["hp"]))
        try:
            # Handle formats like "45 (7d8+14)" or just "45"
            hp = int(hp_text.split(' ')[0]) if ' ' in hp_text else int(hp_text)
        except (ValueError, TypeError, IndexError):
            # Default to 10 HP if any extraction errors
            hp = 10
        
        # Get AC with special handling for various formats
        ac = get_attr(monster_data, "armor_class", 10, ["ac", "AC"])
        print(f"[CombatTracker] Raw AC value for {name}: {ac}")
        
        # Handle different AC formats (string, int, or nested dictionary)
        if isinstance(ac, dict):
            # Some formats store AC in a dict with a 'value' key
            ac_value = ac.get('value', 10)
            if isinstance(ac_value, str):
                try:
                    ac = int(ac_value.split(' ')[0])
                except (ValueError, IndexError):
                    ac = 10
            else:
                ac = int(ac_value) if isinstance(ac_value, (int, float)) else 10
        elif isinstance(ac, str):
            try:
                ac = int(ac.split(' ')[0])
            except (ValueError, IndexError):
                ac = 10
        elif not isinstance(ac, (int, float)):
            # If it's not a recognized format, default to 10
            ac = 10
        
        # Convert to int if it's a float
        ac = int(ac)
        print(f"[CombatTracker] Processed AC for {name}: {ac}")
        
        # Add to tracker
        row = self._add_combatant(name, initiative_roll, hp, ac)
        
        # Store monster data for future reference
        if row >= 0:
            self.combatants[row] = monster_data
        
        # Log to combat log
        self._log_combat_action("Setup", "DM", "added monster", name, f"(Initiative: {initiative_roll})")
        
        return row

    def add_character(self, character):
        """Add a player character from character panel to the tracker"""
        if not character:
            return
            
        # Get initiative bonus
        initiative_bonus = getattr(character, 'initiative_bonus', 0)
        
        # Roll initiative with the bonus
        initiative_roll = random.randint(1, 20) + initiative_bonus
        
        # Get HP and AC
        hp = getattr(character, 'current_hp', 10)
        ac = getattr(character, 'armor_class', 10)
        
        # Add to tracker
        row = self._add_combatant(character.name, initiative_roll, hp, ac)
        
        # Store character data for future reference
        if row >= 0:
            self.combatants[row] = character
            
            # Ensure we store ability scores correctly
            if hasattr(character, 'ability_scores') and isinstance(character.ability_scores, dict):
                # Make sure we have a proper copy of the ability scores
                if character.ability_scores and isinstance(character.ability_scores, dict):
                    # Already stored in the character object
                    pass
            
        # Log to combat log
        self._log_combat_action("Setup", "DM", "added character", character.name, f"(Initiative: {initiative_roll})")
        
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
        """View details for a selected combatant"""
        if row < 0 or row >= self.initiative_table.rowCount():
            return
        
        # Get the selected combatant's name
        name = self.initiative_table.item(row, 0).text()
        
        # First check if we have stored data for this combatant
        combatant_data = self.combatants.get(row)
        
        # If not found in stored data, try to get from the monster panel or character panel
        if not combatant_data:
            # Try to find the monster in the monster panel
            monster_panel = self.get_panel("monster")
            if monster_panel:
                # Try to find monster by name
                monster_data = monster_panel.find_monster_by_name(name)
                if monster_data:
                    combatant_data = monster_data
                    combatant_type = "monster"
                else:
                    # No monster found, try character panel
                    player_panel = self.get_panel("player_character")
                    if player_panel:
                        character_data = player_panel.find_character_by_name(name)
                        if character_data:
                            combatant_data = character_data
                            combatant_type = "character"
                        else:
                            # No character found either, create a simple data object
                            from types import SimpleNamespace
                            combatant_data = SimpleNamespace(
                                name=name,
                                armor_class=self.initiative_table.item(row, 3).text(),
                                hit_points=self.initiative_table.item(row, 2).text(),
                                ability_scores={}
                            )
                            combatant_type = "unknown"
                    else:
                        # No character panel available
                        from types import SimpleNamespace
                        combatant_data = SimpleNamespace(
                            name=name,
                            armor_class=self.initiative_table.item(row, 3).text(),
                            hit_points=self.initiative_table.item(row, 2).text(),
                            ability_scores={}
                        )
                        combatant_type = "unknown"
            else:
                # No monster panel available
                from types import SimpleNamespace
                combatant_data = SimpleNamespace(
                    name=name,
                    armor_class=self.initiative_table.item(row, 3).text(),
                    hit_points=self.initiative_table.item(row, 2).text(),
                    ability_scores={}
                )
                combatant_type = "unknown"
        else:
            # Determine if the stored data is a monster or character
            if hasattr(combatant_data, 'is_custom') and hasattr(combatant_data, 'type'):
                combatant_type = "monster"
                # Try to get the full monster data from the monster panel
                monster_panel = self.get_panel("monster")
                if monster_panel:
                    full_monster = monster_panel.find_monster_by_name(name)
                    if full_monster:
                        combatant_data = full_monster
            elif hasattr(combatant_data, 'character_class') and hasattr(combatant_data, 'race'):
                combatant_type = "character"
                # Try to get the full character data from the character panel
                player_panel = self.get_panel("player_character")
                if player_panel:
                    full_character = player_panel.find_character_by_name(name)
                    if full_character:
                        combatant_data = full_character
            else:
                combatant_type = "unknown"
                
            # Debug: Print ability scores if available
            if hasattr(combatant_data, 'ability_scores') and isinstance(combatant_data.ability_scores, dict):
                print(f"[CombatTracker] Character ability scores for {name}: {combatant_data.ability_scores}")
        
        # Create and show the details dialog
        dialog = CombatantDetailsDialog(self, combatant_data=combatant_data, combatant_type=combatant_type)
        dialog.exec_()
    
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
