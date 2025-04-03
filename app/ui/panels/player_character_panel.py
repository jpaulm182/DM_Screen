# app/ui/panels/player_character_panel.py - Player Character Quick Reference panel
"""
Player Character Quick Reference panel

Provides a quick reference for player characters with their stats and abilities.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QSpinBox, QTextEdit, QComboBox, QPushButton, QTabWidget,
    QScrollArea, QFormLayout, QSplitter, QFrame, QGroupBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QToolButton, QMenu, QStackedWidget, QListWidget
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QIcon, QColor, QAction

import json
from pathlib import Path

from app.ui.panels.base_panel import BasePanel
from app.ui.panels.panel_category import PanelCategory

class PlayerCharacter:
    """Class representing a player character"""
    
    def __init__(self, name="", race="", character_class="", level=1):
        # Basic info
        self.name = name
        self.race = race
        self.character_class = character_class
        self.level = level
        
        # Character stats
        self.ability_scores = {
            "STR": 10, 
            "DEX": 10, 
            "CON": 10, 
            "INT": 10, 
            "WIS": 10, 
            "CHA": 10
        }
        self.max_hp = 10
        self.current_hp = 10
        self.temp_hp = 0
        self.armor_class = 10
        self.speed = 30
        self.initiative_bonus = 0
        self.proficiency_bonus = 2
        
        # Other information
        self.background = ""
        self.alignment = "True Neutral"
        self.features = []
        self.equipment = []
        self.spells = []
        self.notes = ""
        self.conditions = []
    
    def to_dict(self):
        """Convert the character to a dictionary for storage"""
        return {
            "name": self.name,
            "race": self.race,
            "character_class": self.character_class,
            "level": self.level,
            "ability_scores": self.ability_scores,
            "max_hp": self.max_hp,
            "current_hp": self.current_hp,
            "temp_hp": self.temp_hp,
            "armor_class": self.armor_class,
            "speed": self.speed,
            "initiative_bonus": self.initiative_bonus,
            "proficiency_bonus": self.proficiency_bonus,
            "background": self.background,
            "alignment": self.alignment,
            "features": self.features,
            "equipment": self.equipment,
            "spells": self.spells,
            "notes": self.notes,
            "conditions": self.conditions
        }
    
    @classmethod
    def from_dict(cls, data):
        """Create a character from a dictionary"""
        character = cls()
        for key, value in data.items():
            if hasattr(character, key):
                setattr(character, key, value)
        return character
    
    def get_ability_modifier(self, ability):
        """Calculate ability modifier from score"""
        score = self.ability_scores.get(ability, 10)
        return (score - 10) // 2
    
    def get_saving_throw(self, ability):
        """Calculate saving throw bonus"""
        # TODO: Add proficiency if character is proficient in this save
        return self.get_ability_modifier(ability)


class PlayerCharacterPanel(BasePanel):
    """Player Character Quick Reference Panel"""
    
    # Signal emitted when adding character to combat
    add_to_combat = Signal(object)  # Emits character data
    
    def __init__(self, app_state):
        """Initialize the player character panel"""
        # Initialize attributes before parent constructor
        self.characters = []
        self.current_character_index = -1
        self.character_file = None
        
        # Call parent constructor
        super().__init__(app_state, "Player Characters")
        
        # Set up character file path after app_state is set
        self.character_file = self.app_state.data_dir / "player_characters.json"
        self._load_characters()
    
    def _setup_ui(self):
        """Set up the panel UI"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(4)
        
        # Create toolbar for character management
        toolbar_layout = QHBoxLayout()
        
        # Add new character button
        self.add_btn = QPushButton("New Character")
        self.add_btn.clicked.connect(self._add_character)
        toolbar_layout.addWidget(self.add_btn)
        
        # Import character button
        self.import_btn = QPushButton("Import")
        self.import_btn.clicked.connect(self._import_character)
        toolbar_layout.addWidget(self.import_btn)
        
        # Character selector
        self.char_selector = QComboBox()
        self.char_selector.currentIndexChanged.connect(self._select_character)
        toolbar_layout.addWidget(self.char_selector)
        
        # Delete character button
        self.delete_btn = QPushButton("Delete")
        self.delete_btn.clicked.connect(self._delete_character)
        toolbar_layout.addWidget(self.delete_btn)
        
        # Add to combat button
        self.add_to_combat_btn = QPushButton("Add to Combat")
        self.add_to_combat_btn.clicked.connect(self._add_to_combat)
        toolbar_layout.addWidget(self.add_to_combat_btn)
        
        main_layout.addLayout(toolbar_layout)
        
        # Main character view
        self.stack = QStackedWidget()
        
        # Empty state widget
        self.empty_widget = QWidget()
        empty_layout = QVBoxLayout(self.empty_widget)
        empty_label = QLabel("No characters added yet.\nClick 'New Character' to create one.")
        empty_label.setAlignment(Qt.AlignCenter)
        empty_layout.addWidget(empty_label)
        self.stack.addWidget(self.empty_widget)
        
        # Character editor widget
        self.editor_widget = QTabWidget()
        
        # Basic info tab
        basic_tab = QWidget()
        basic_layout = QFormLayout(basic_tab)
        
        # Character name
        self.name_edit = QLineEdit()
        self.name_edit.textChanged.connect(self._on_name_changed)
        basic_layout.addRow("Name:", self.name_edit)
        
        # Race
        self.race_edit = QLineEdit()
        self.race_edit.textChanged.connect(self._on_race_changed)
        basic_layout.addRow("Race:", self.race_edit)
        
        # Class
        self.class_edit = QLineEdit()
        self.class_edit.textChanged.connect(self._on_class_changed)
        basic_layout.addRow("Class:", self.class_edit)
        
        # Level
        self.level_spin = QSpinBox()
        self.level_spin.setRange(1, 20)
        self.level_spin.valueChanged.connect(self._on_level_changed)
        basic_layout.addRow("Level:", self.level_spin)
        
        # Ability scores group
        abilities_group = QGroupBox("Ability Scores")
        abilities_layout = QHBoxLayout(abilities_group)
        
        self.ability_edits = {}
        self.ability_labels = {}
        
        for ability in ["STR", "DEX", "CON", "INT", "WIS", "CHA"]:
            ability_layout = QVBoxLayout()
            ability_layout.setSpacing(2)
            
            # Label with ability name
            ability_label = QLabel(ability)
            ability_label.setAlignment(Qt.AlignCenter)
            ability_layout.addWidget(ability_label)
            
            # Spinbox for score
            score_spin = QSpinBox()
            score_spin.setRange(1, 30)
            score_spin.setValue(10)
            score_spin.ability = ability
            score_spin.valueChanged.connect(self._on_ability_changed)
            self.ability_edits[ability] = score_spin
            ability_layout.addWidget(score_spin)
            
            # Label for modifier
            mod_label = QLabel("(+0)")
            mod_label.setAlignment(Qt.AlignCenter)
            self.ability_labels[ability] = mod_label
            ability_layout.addWidget(mod_label)
            
            abilities_layout.addLayout(ability_layout)
        
        basic_layout.addRow(abilities_group)
        
        # Combat stats
        combat_group = QGroupBox("Combat Stats")
        combat_layout = QFormLayout(combat_group)
        
        # Hit points
        hp_layout = QHBoxLayout()
        
        self.max_hp_spin = QSpinBox()
        self.max_hp_spin.setRange(1, 999)
        self.max_hp_spin.setValue(10)
        self.max_hp_spin.valueChanged.connect(self._on_max_hp_changed)
        hp_layout.addWidget(QLabel("Max:"))
        hp_layout.addWidget(self.max_hp_spin)
        
        self.current_hp_spin = QSpinBox()
        self.current_hp_spin.setRange(0, 999)
        self.current_hp_spin.setValue(10)
        self.current_hp_spin.valueChanged.connect(self._on_current_hp_changed)
        hp_layout.addWidget(QLabel("Current:"))
        hp_layout.addWidget(self.current_hp_spin)
        
        self.temp_hp_spin = QSpinBox()
        self.temp_hp_spin.setRange(0, 999)
        self.temp_hp_spin.valueChanged.connect(self._on_temp_hp_changed)
        hp_layout.addWidget(QLabel("Temp:"))
        hp_layout.addWidget(self.temp_hp_spin)
        
        combat_layout.addRow("Hit Points:", hp_layout)
        
        # AC, Initiative, Speed
        stat_layout = QHBoxLayout()
        
        self.ac_spin = QSpinBox()
        self.ac_spin.setRange(1, 30)
        self.ac_spin.setValue(10)
        self.ac_spin.valueChanged.connect(self._on_ac_changed)
        stat_layout.addWidget(QLabel("AC:"))
        stat_layout.addWidget(self.ac_spin)
        
        self.init_spin = QSpinBox()
        self.init_spin.setRange(-10, 20)
        self.init_spin.valueChanged.connect(self._on_initiative_changed)
        stat_layout.addWidget(QLabel("Initiative:"))
        stat_layout.addWidget(self.init_spin)
        
        self.speed_spin = QSpinBox()
        self.speed_spin.setRange(0, 120)
        self.speed_spin.setValue(30)
        self.speed_spin.valueChanged.connect(self._on_speed_changed)
        stat_layout.addWidget(QLabel("Speed:"))
        stat_layout.addWidget(self.speed_spin)
        
        combat_layout.addRow("Combat Stats:", stat_layout)
        
        basic_layout.addRow(combat_group)
        
        # Background and alignment
        background_widget = QWidget()
        background_layout = QVBoxLayout(background_widget)
        background_layout.setContentsMargins(0, 0, 0, 0)
        background_label = QLabel("Background:")
        background_layout.addWidget(background_label)
        
        self.background_edit = QTextEdit()
        self.background_edit.setMaximumHeight(80)
        self.background_edit.textChanged.connect(self._on_background_changed)
        background_layout.addWidget(self.background_edit)
        
        basic_layout.addRow("Background:", background_widget)
        
        self.alignment_combo = QComboBox()
        self.alignment_combo.addItems([
            "Lawful Good", "Neutral Good", "Chaotic Good",
            "Lawful Neutral", "True Neutral", "Chaotic Neutral",
            "Lawful Evil", "Neutral Evil", "Chaotic Evil"
        ])
        self.alignment_combo.currentTextChanged.connect(self._on_alignment_changed)
        basic_layout.addRow("Alignment:", self.alignment_combo)
        
        self.editor_widget.addTab(basic_tab, "Basic Info")
        
        # Features & Equipment tab
        features_tab = QWidget()
        features_layout = QVBoxLayout(features_tab)
        
        splitter = QSplitter(Qt.Vertical)
        
        # Features section
        features_group = QGroupBox("Features & Traits")
        features_group_layout = QVBoxLayout(features_group)
        
        features_label = QLabel("Enter features, traits, and special abilities:")
        features_group_layout.addWidget(features_label)
        
        self.features_edit = QTextEdit()
        self.features_edit.textChanged.connect(self._on_features_changed)
        features_group_layout.addWidget(self.features_edit)
        
        splitter.addWidget(features_group)
        
        # Equipment section
        equipment_group = QGroupBox("Equipment")
        equipment_layout = QVBoxLayout(equipment_group)
        
        equipment_label = QLabel("Enter equipment, weapons, and items:")
        equipment_layout.addWidget(equipment_label)
        
        self.equipment_edit = QTextEdit()
        self.equipment_edit.textChanged.connect(self._on_equipment_changed)
        equipment_layout.addWidget(self.equipment_edit)
        
        splitter.addWidget(equipment_group)
        features_layout.addWidget(splitter)
        
        self.editor_widget.addTab(features_tab, "Features & Equipment")
        
        # Spells tab
        spells_tab = QWidget()
        spells_layout = QVBoxLayout(spells_tab)
        
        spells_label = QLabel("Enter spells and spell slots:")
        spells_layout.addWidget(spells_label)
        
        self.spells_edit = QTextEdit()
        self.spells_edit.textChanged.connect(self._on_spells_changed)
        spells_layout.addWidget(self.spells_edit)
        
        self.editor_widget.addTab(spells_tab, "Spells")
        
        # Notes tab
        notes_tab = QWidget()
        notes_layout = QVBoxLayout(notes_tab)
        
        notes_label = QLabel("General notes about this character:")
        notes_layout.addWidget(notes_label)
        
        self.notes_edit = QTextEdit()
        self.notes_edit.textChanged.connect(self._on_notes_changed)
        notes_layout.addWidget(self.notes_edit)
        
        self.editor_widget.addTab(notes_tab, "Notes")
        
        self.stack.addWidget(self.editor_widget)
        main_layout.addWidget(self.stack)
        
        # Save button
        self.save_btn = QPushButton("Save All Characters")
        self.save_btn.clicked.connect(self._save_characters)
        main_layout.addWidget(self.save_btn)
        
        # Show empty state initially
        self.stack.setCurrentWidget(self.empty_widget)
        self._update_interface()
    
    def _load_characters(self):
        """Load player characters from file"""
        if self.character_file.exists():
            try:
                with open(self.character_file, 'r') as f:
                    data = json.load(f)
                    
                self.characters = [PlayerCharacter.from_dict(char_data) 
                                  for char_data in data]
                    
                if self.characters:
                    self.current_character_index = 0
            except Exception as e:
                QMessageBox.warning(
                    self, "Error Loading Characters",
                    f"Failed to load player characters: {str(e)}"
                )
    
    def _save_characters(self):
        """Save player characters to file"""
        try:
            data = [char.to_dict() for char in self.characters]
            
            with open(self.character_file, 'w') as f:
                json.dump(data, f, indent=2)
                
            QMessageBox.information(
                self, "Success",
                "Player characters saved successfully."
            )
        except Exception as e:
            QMessageBox.warning(
                self, "Error Saving Characters",
                f"Failed to save player characters: {str(e)}"
            )
    
    def _update_interface(self):
        """Update the interface with current data"""
        # Update character selector
        self.char_selector.blockSignals(True)
        self.char_selector.clear()
        
        for char in self.characters:
            display_name = f"{char.name} (Level {char.level} {char.race} {char.character_class})"
            if not char.name:
                display_name = "Unnamed Character"
            self.char_selector.addItem(display_name)
        
        if self.current_character_index >= 0:
            self.char_selector.setCurrentIndex(self.current_character_index)
            
        self.char_selector.blockSignals(False)
        
        # Update UI state
        if not self.characters:
            self.stack.setCurrentWidget(self.empty_widget)
            self.delete_btn.setEnabled(False)
            self.char_selector.setEnabled(False)
        else:
            self.stack.setCurrentWidget(self.editor_widget)
            self.delete_btn.setEnabled(True)
            self.char_selector.setEnabled(True)
            self._update_character_display()
    
    def _update_character_display(self):
        """Update display with current character"""
        if self.current_character_index < 0 or self.current_character_index >= len(self.characters):
            return
            
        character = self.characters[self.current_character_index]
        
        # Block signals to prevent triggering update events
        self._block_signals(True)
        
        # Basic info
        self.name_edit.setText(character.name)
        self.race_edit.setText(character.race)
        self.class_edit.setText(character.character_class)
        self.level_spin.setValue(character.level)
        
        # Ability scores
        for ability, score in character.ability_scores.items():
            if ability in self.ability_edits:
                self.ability_edits[ability].setValue(score)
                modifier = character.get_ability_modifier(ability)
                sign = "+" if modifier >= 0 else ""
                self.ability_labels[ability].setText(f"({sign}{modifier})")
        
        # Combat stats
        self.max_hp_spin.setValue(character.max_hp)
        self.current_hp_spin.setValue(character.current_hp)
        self.current_hp_spin.setMaximum(character.max_hp)
        self.temp_hp_spin.setValue(character.temp_hp)
        self.ac_spin.setValue(character.armor_class)
        self.init_spin.setValue(character.initiative_bonus)
        self.speed_spin.setValue(character.speed)
        
        # Background and alignment
        self.background_edit.setPlainText(character.background)
        index = self.alignment_combo.findText(character.alignment)
        if index >= 0:
            self.alignment_combo.setCurrentIndex(index)
        
        # Other tabs
        self.features_edit.setText("\n".join(character.features))
        self.equipment_edit.setText("\n".join(character.equipment))
        self.spells_edit.setText("\n".join(character.spells))
        self.notes_edit.setText(character.notes)
        
        self._block_signals(False)
    
    def _block_signals(self, block):
        """Block or unblock signals from all input widgets"""
        widgets = [
            self.name_edit, self.race_edit, self.class_edit, self.level_spin,
            self.max_hp_spin, self.current_hp_spin, self.temp_hp_spin,
            self.ac_spin, self.init_spin, self.speed_spin,
            self.background_edit, self.alignment_combo,
            self.features_edit, self.equipment_edit, self.spells_edit,
            self.notes_edit
        ]
        
        for ability, widget in self.ability_edits.items():
            widgets.append(widget)
            
        for widget in widgets:
            widget.blockSignals(block)
    
    def _add_character(self):
        """Add a new character"""
        self.characters.append(PlayerCharacter())
        self.current_character_index = len(self.characters) - 1
        self._update_interface()
    
    def _delete_character(self):
        """Delete the current character"""
        if self.current_character_index < 0 or not self.characters:
            return
            
        character = self.characters[self.current_character_index]
        name = character.name or "Unnamed Character"
        
        reply = QMessageBox.question(
            self, "Confirm Deletion",
            f"Are you sure you want to delete '{name}'?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.characters.pop(self.current_character_index)
            
            if self.characters:
                self.current_character_index = max(0, self.current_character_index - 1)
            else:
                self.current_character_index = -1
                
            self._update_interface()
    
    def _import_character(self):
        """Import a character from a file"""
        # TODO: Implement character import functionality
        QMessageBox.information(
            self, "Not Implemented",
            "Character import is not yet implemented."
        )
    
    def _select_character(self, index):
        """Handle character selection"""
        if index >= 0 and index < len(self.characters):
            self.current_character_index = index
            self._update_character_display()
    
    def _on_name_changed(self):
        """Handle character name change"""
        if self.current_character_index < 0:
            return
            
        self.characters[self.current_character_index].name = self.name_edit.text()
        
        # Update character selector display
        char = self.characters[self.current_character_index]
        display_name = f"{char.name} (Level {char.level} {char.race} {char.character_class})"
        if not char.name:
            display_name = "Unnamed Character"
        
        self.char_selector.setItemText(self.current_character_index, display_name)
    
    def _on_race_changed(self):
        """Handle character race change"""
        if self.current_character_index < 0:
            return
            
        self.characters[self.current_character_index].race = self.race_edit.text()
        
        # Update character selector display
        char = self.characters[self.current_character_index]
        display_name = f"{char.name} (Level {char.level} {char.race} {char.character_class})"
        if not char.name:
            display_name = "Unnamed Character"
        
        self.char_selector.setItemText(self.current_character_index, display_name)
    
    def _on_class_changed(self):
        """Handle character class change"""
        if self.current_character_index < 0:
            return
            
        self.characters[self.current_character_index].character_class = self.class_edit.text()
        
        # Update character selector display
        char = self.characters[self.current_character_index]
        display_name = f"{char.name} (Level {char.level} {char.race} {char.character_class})"
        if not char.name:
            display_name = "Unnamed Character"
        
        self.char_selector.setItemText(self.current_character_index, display_name)
    
    def _on_level_changed(self, value):
        """Handle character level change"""
        if self.current_character_index < 0:
            return
            
        self.characters[self.current_character_index].level = value
        
        # Update character selector display
        char = self.characters[self.current_character_index]
        display_name = f"{char.name} (Level {char.level} {char.race} {char.character_class})"
        if not char.name:
            display_name = "Unnamed Character"
        
        self.char_selector.setItemText(self.current_character_index, display_name)
    
    def _on_ability_changed(self, value):
        """Handle ability score change"""
        if self.current_character_index < 0:
            return
            
        ability = self.sender().ability
        self.characters[self.current_character_index].ability_scores[ability] = value
        
        # Update modifier display
        modifier = self.characters[self.current_character_index].get_ability_modifier(ability)
        sign = "+" if modifier >= 0 else ""
        self.ability_labels[ability].setText(f"({sign}{modifier})")
    
    def _on_max_hp_changed(self, value):
        """Handle max HP change"""
        if self.current_character_index < 0:
            return
            
        self.characters[self.current_character_index].max_hp = value
        
        # Update current HP spinner maximum
        self.current_hp_spin.setMaximum(value)
    
    def _on_current_hp_changed(self, value):
        """Handle current HP change"""
        if self.current_character_index < 0:
            return
            
        self.characters[self.current_character_index].current_hp = value
    
    def _on_temp_hp_changed(self, value):
        """Handle temporary HP change"""
        if self.current_character_index < 0:
            return
            
        self.characters[self.current_character_index].temp_hp = value
    
    def _on_ac_changed(self, value):
        """Handle AC change"""
        if self.current_character_index < 0:
            return
            
        self.characters[self.current_character_index].armor_class = value
    
    def _on_initiative_changed(self, value):
        """Handle initiative bonus change"""
        if self.current_character_index < 0:
            return
            
        self.characters[self.current_character_index].initiative_bonus = value
    
    def _on_speed_changed(self, value):
        """Handle speed change"""
        if self.current_character_index < 0:
            return
            
        self.characters[self.current_character_index].speed = value
    
    def _on_background_changed(self):
        """Handle background change"""
        if self.current_character_index < 0:
            return
            
        self.characters[self.current_character_index].background = self.background_edit.toPlainText()
    
    def _on_alignment_changed(self, text):
        """Handle alignment change"""
        if self.current_character_index < 0:
            return
            
        self.characters[self.current_character_index].alignment = text
    
    def _on_features_changed(self):
        """Handle features text change"""
        if self.current_character_index < 0:
            return
            
        text = self.features_edit.toPlainText()
        self.characters[self.current_character_index].features = text.split("\n") if text else []
    
    def _on_equipment_changed(self):
        """Handle equipment text change"""
        if self.current_character_index < 0:
            return
            
        text = self.equipment_edit.toPlainText()
        self.characters[self.current_character_index].equipment = text.split("\n") if text else []
    
    def _on_spells_changed(self):
        """Handle spells text change"""
        if self.current_character_index < 0:
            return
            
        text = self.spells_edit.toPlainText()
        self.characters[self.current_character_index].spells = text.split("\n") if text else []
    
    def _on_notes_changed(self):
        """Handle notes text change"""
        if self.current_character_index < 0:
            return
            
        self.characters[self.current_character_index].notes = self.notes_edit.toPlainText()
    
    def _add_to_combat(self):
        """Add the current character to the combat tracker"""
        if self.current_character_index >= 0:
            character = self.characters[self.current_character_index]
            self.add_to_combat.emit(character)
    
    def save_state(self):
        """Save the panel state"""
        return {
            "current_character_index": self.current_character_index
        }
    
    def restore_state(self, state):
        """Restore panel state from saved data"""
        if not state:
            return
            
        self.current_character_index = state.get("current_character_index", -1)
        self._update_interface()
    
    def add_npc_character(self, npc_data):
        """Add an NPC from the NPC generator as a character
        
        Args:
            npc_data (dict): Dictionary containing NPC data
        """
        try:
            # Parse NPC content as JSON
            content = npc_data.get("content", "")
            npc_json = json.loads(content)
            
            # Extract basic information
            name = npc_json.get("name", "Unnamed NPC") + " (NPC)"
            race = npc_json.get("race", "")
            char_class = npc_json.get("role", "NPC")
            level = npc_json.get("level", 1)
            alignment = npc_json.get("alignment", "True Neutral")
            
            # Create a new character
            character = PlayerCharacter(name=name, race=race, character_class=char_class, level=level)
            character.alignment = alignment
            
            # Update character stats
            stats = npc_json.get("stats", {})
            character.ability_scores = stats if stats else character.ability_scores
            
            # Update HP and combat stats from NPC data
            if stats:
                # Set HP from stats
                if "HP" in stats:
                    character.max_hp = stats["HP"]
                    character.current_hp = stats["HP"]
                
                # Set AC
                if "AC" in stats:
                    character.armor_class = stats["AC"]
                
                # Set speed
                if "speed" in stats:
                    character.speed = stats["speed"]
                
                # Calculate initiative bonus from DEX if available
                if "DEX" in stats:
                    dex_mod = (stats["DEX"] - 10) // 2
                    character.initiative_bonus = dex_mod
            
            # Add skills as notes
            skills_text = ""
            if npc_json.get("skills"):
                skills_text = "Skills:\n"
                for skill, value in npc_json.get("skills", {}).items():
                    skills_text += f"{skill}: +{value}\n"
            
            # Add languages as notes
            languages_text = ""
            if npc_json.get("languages"):
                languages_text = "\nLanguages: " + ", ".join(npc_json.get("languages", []))
            
            # Handle spells
            character.spells = [spell["name"] for spell in npc_json.get("spells", [])]
            
            # Properly set the background field - use the full background text since we now support it
            if npc_json.get("background"):
                character.background = npc_json.get("background", "")
            
            # Handle features, include quirk if available
            features_list = []
            if npc_json.get("quirk"):
                features_list.append("Quirk: " + npc_json.get("quirk"))
            
            # Add personality as a feature
            if npc_json.get("personality"):
                features_list.append("Personality: " + npc_json.get("personality"))
            
            # Add goals as a feature
            if npc_json.get("goals"):
                features_list.append("Goals: " + npc_json.get("goals"))
                
            character.features = features_list
            
            # Process equipment with descriptions
            equipment = npc_json.get("equipment", [])
            formatted_equipment = []
            
            if isinstance(equipment, list):
                for item in equipment:
                    if isinstance(item, dict) and "name" in item and "description" in item:
                        # Format equipment with description
                        formatted_equipment.append(f"{item['name']} - {item['description']}")
                    elif isinstance(item, dict) and "name" in item:
                        # Just the name if no description
                        formatted_equipment.append(item['name'])
                    elif isinstance(item, str):
                        # Legacy format - just strings
                        formatted_equipment.append(item)
            else:
                # Handle non-list equipment (unlikely but for safety)
                formatted_equipment = [str(equipment)] if equipment else []
                
            character.equipment = formatted_equipment
            
            # Combine all notes
            notes_parts = []
            
            if npc_json.get("description"):
                notes_parts.append("Description:\n" + npc_json.get("description"))
            
            if npc_json.get("personality"):
                notes_parts.append("\nPersonality:\n" + npc_json.get("personality"))
                
            if npc_json.get("background"):
                notes_parts.append("\nBackground:\n" + npc_json.get("background"))
                
            if npc_json.get("goals"):
                notes_parts.append("\nGoals:\n" + npc_json.get("goals"))
            
            if skills_text:
                notes_parts.append("\n" + skills_text)
                
            if languages_text:
                notes_parts.append(languages_text)
            
            if npc_json.get("narrative_output"):
                notes_parts.append("\n--- Narrative ---\n" + npc_json.get("narrative_output"))
            
            character.notes = "".join(notes_parts)
            
            # Add NPC as a character
            self.characters.append(character)
            self.current_character_index = len(self.characters) - 1
            self._update_interface()
            
            # Show success message
            QMessageBox.information(
                self, "NPC Added",
                f"NPC '{name}' has been added as a character."
            )
            
            return True
            
        except json.JSONDecodeError:
            QMessageBox.warning(
                self, "Error Adding NPC",
                "Failed to parse NPC data as JSON."
            )
        except Exception as e:
            QMessageBox.warning(
                self, "Error Adding NPC",
                f"Failed to add NPC as character: {str(e)}"
            )
        return False
    
    def find_character_by_name(self, character_name):
        """Find a character by its name and return the full character data.
        
        This method is used by the combat tracker to get the full character data.
        
        Args:
            character_name (str): Name of the character to find
            
        Returns:
            PlayerCharacter: The character object if found, None otherwise
        """
        # Check all loaded characters
        for character in self.characters:
            if character.name.lower() == character_name.lower():
                return character
                
        # Not found
        return None 