"""
Monster/NPC stat block viewer panel for D&D 5e

Features:
- Quick access to monster/NPC statistics (Standard & Custom)
- Search and filter functionality
- Stat block display with proper formatting
- Quick-add to combat tracker
- Custom monster creation, editing, and deletion (via LLM or manual)
- Notifies Notes panel on custom monster creation
"""

import logging
from typing import List, Optional, Dict, Any

from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QTextEdit, QLineEdit, QWidget,
    QSpinBox, QComboBox, QDialog, QDialogButtonBox,
    QFormLayout, QTabWidget, QScrollArea, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QListWidgetItem # Added QListWidgetItem
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QIcon

from app.ui.panels.base_panel import BasePanel
from app.core.models.monster import Monster # Import Monster dataclass
# Import the dialog
from app.ui.dialogs.monster_edit_dialog import MonsterEditDialog
# Assuming db_manager and llm_service are accessible via app_state
# from app.data.db_manager import DatabaseManager
# from app.core.llm_service import LLMService
# from app.core.llm_integration import monster_generator # Import LLM functions

# Setup logger for this module
logger = logging.getLogger(__name__)

# CR to XP mapping (from D&D 5e DMG or Basic Rules)
CR_TO_XP = {
    "0": 10,
    "1/8": 25,
    "1/4": 50,
    "1/2": 100,
    "1": 200,
    "2": 450,
    "3": 700,
    "4": 1100,
    "5": 1800,
    "6": 2300,
    "7": 2900,
    "8": 3900,
    "9": 5000,
    "10": 5900,
    "11": 7200,
    "12": 8400,
    "13": 10000,
    "14": 11500,
    "15": 13000,
    "16": 15000,
    "17": 18000,
    "18": 20000,
    "19": 22000,
    "20": 25000,
    "21": 33000,
    "22": 41000,
    "23": 50000,
    "24": 62000,
    "25": 75000,
    "26": 90000,
    "27": 105000,
    "28": 120000,
    "29": 135000,
    "30": 155000
}

def get_xp_for_cr(cr_string: str) -> int:
    """Convert a CR string (like '1/2' or '5') to its XP value."""
    return CR_TO_XP.get(str(cr_string), 0) # Return 0 if CR not found

class MonsterPanel(BasePanel):
    """Panel for viewing and managing monster/NPC stat blocks"""
    
    # Signal emitted when adding monster to combat
    add_to_combat = Signal(dict)  # Emits monster data as dict

    # Signal emitted when a new custom monster is created/saved
    custom_monster_created = Signal(str) # Emits new monster's name

    def __init__(self, app_state):
        # Get services from app_state
        self.db_manager = app_state.db_manager
        self.llm_service = app_state.llm_service # Assuming LLM service is here
        self.monsters: List[Monster] = []  # Store loaded Monster objects
        self.current_monster: Optional[Monster] = None
        super().__init__(app_state, "Monster Reference") # Calls _setup_ui via BasePanel

        # Load monsters after UI is set up
        self._load_initial_monsters()

    def _setup_ui(self):
        """Set up the monster panel UI"""
        main_layout = QVBoxLayout(self) # Set layout on self

        # --- Search and filter area ---
        search_layout = QHBoxLayout()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search monsters...")
        # Use a timer to avoid filtering on every keystroke (optional enhancement)
        self.search_input.textChanged.connect(self._filter_monsters)
        search_layout.addWidget(self.search_input)

        # TODO: CR filter needs to handle string values like "1/2" correctly
        self.cr_filter = QComboBox()
        self.cr_filter.addItem("All CRs")
        # Add common fractional CRs first
        self.cr_filter.addItems(["0", "1/8", "1/4", "1/2"] + [str(i) for i in range(1, 31)])
        self.cr_filter.currentTextChanged.connect(self._filter_monsters)
        search_layout.addWidget(self.cr_filter)

        self.type_filter = QComboBox()
        self.type_filter.addItem("All Types")
        # Add common monster types
        self.type_filter.addItems([
            "Aberration", "Beast", "Celestial", "Construct",
            "Dragon", "Elemental", "Fey", "Fiend", "Giant",
            "Humanoid", "Monstrosity", "Ooze", "Plant", "Undead", "Other" # Added Other
        ])
        self.type_filter.currentTextChanged.connect(self._filter_monsters)
        search_layout.addWidget(self.type_filter)

        main_layout.addLayout(search_layout)

        # --- Split view ---
        content_layout = QHBoxLayout()

        # --- Monster list ---
        list_layout = QVBoxLayout()
        self.monster_list = QListWidget()
        self.monster_list.currentItemChanged.connect(self._on_monster_selected) # Renamed method
        list_layout.addWidget(self.monster_list)

        # --- List Buttons ---
        list_button_layout = QHBoxLayout()

        self.add_to_combat_btn = QPushButton("Add to Combat")
        self.add_to_combat_btn.setIcon(QIcon.fromTheme("list-add")) # Example icon
        self.add_to_combat_btn.clicked.connect(self._add_to_combat)
        self.add_to_combat_btn.setEnabled(False) # Disabled initially
        list_button_layout.addWidget(self.add_to_combat_btn)

        self.create_monster_btn = QPushButton("Create New")
        self.create_monster_btn.setIcon(QIcon.fromTheme("document-new")) # Example icon
        self.create_monster_btn.clicked.connect(self._create_monster)
        list_button_layout.addWidget(self.create_monster_btn)

        self.edit_monster_btn = QPushButton("Edit")
        self.edit_monster_btn.setIcon(QIcon.fromTheme("document-edit")) # Example icon
        self.edit_monster_btn.clicked.connect(self._edit_monster)
        self.edit_monster_btn.setEnabled(False) # Disabled initially
        list_button_layout.addWidget(self.edit_monster_btn)

        self.delete_monster_btn = QPushButton("Delete")
        self.delete_monster_btn.setIcon(QIcon.fromTheme("edit-delete")) # Example icon
        self.delete_monster_btn.clicked.connect(self._delete_monster)
        self.delete_monster_btn.setEnabled(False) # Disabled initially
        list_button_layout.addWidget(self.delete_monster_btn)

        list_layout.addLayout(list_button_layout)
        content_layout.addLayout(list_layout, stretch=1) # List takes 1/3 space

        # --- Stat block display ---
        # Use a QScrollArea for potentially long stat blocks
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame) # Optional: remove border

        # Widget to contain the actual stat block labels
        self.stat_block_widget = QWidget()
        self.stat_block_layout = QVBoxLayout(self.stat_block_widget)
        self.stat_block_layout.setAlignment(Qt.AlignTop)
        scroll_area.setWidget(self.stat_block_widget)
        
        # Initialize labels for details (will be populated later)
        self.name_label = QLabel("")
        self.name_label.setFont(QFont("Arial", 16, QFont.Bold))
        self.stat_block_layout.addWidget(self.name_label)

        self.meta_label = QLabel("") # For size, type, alignment
        self.meta_label.setStyleSheet("font-style: italic;")
        self.stat_block_layout.addWidget(self.meta_label)
        
        self.stat_block_layout.addWidget(QFrame(frameShape=QFrame.HLine))
        
        self.ac_label = QLabel("")
        self.stat_block_layout.addWidget(self.ac_label)
        self.hp_label = QLabel("")
        self.stat_block_layout.addWidget(self.hp_label)
        self.speed_label = QLabel("")
        self.stat_block_layout.addWidget(self.speed_label)
        
        self.stat_block_layout.addWidget(QFrame(frameShape=QFrame.HLine))

        # Table for ability scores (or use horizontal layout)
        # For simplicity, using labels for now
        self.stats_grid = QHBoxLayout()
        self.str_label = QLabel("")
        self.dex_label = QLabel("")
        self.con_label = QLabel("")
        self.int_label = QLabel("")
        self.wis_label = QLabel("")
        self.cha_label = QLabel("")
        for label in [self.str_label, self.dex_label, self.con_label, self.int_label, self.wis_label, self.cha_label]:
             self.stats_grid.addWidget(label)
        self.stat_block_layout.addLayout(self.stats_grid)

        self.stat_block_layout.addWidget(QFrame(frameShape=QFrame.HLine))
        
        self.skills_label = QLabel("")
        self.senses_label = QLabel("")
        self.languages_label = QLabel("")
        self.cr_label = QLabel("")
        self.xp_label = QLabel("") # <-- ADDED XP LABEL
        for label in [self.skills_label, self.senses_label, self.languages_label, self.cr_label, self.xp_label]:
             self.stat_block_layout.addWidget(label)

        self.stat_block_layout.addWidget(QFrame(frameShape=QFrame.HLine))
        
        self.traits_layout = QVBoxLayout()
        self.stat_block_layout.addLayout(self.traits_layout)
        
        self.actions_layout = QVBoxLayout()
        self.stat_block_layout.addLayout(self.actions_layout)
        
        self.legendary_actions_layout = QVBoxLayout()
        self.stat_block_layout.addLayout(self.legendary_actions_layout)
        
        self.description_label = QLabel("")
        self.description_label.setWordWrap(True)
        self.stat_block_layout.addWidget(self.description_label)

        self.stat_block_layout.addStretch() # Push content to top

        scroll_area.setWidget(self.stat_block_widget)
        content_layout.addWidget(scroll_area, stretch=2) # Stat block area takes 2/3 space

        main_layout.addLayout(content_layout)

        # Set minimum size for the panel
        self.setMinimumSize(800, 600)

    def _load_initial_monsters(self):
        """Load all monsters from the database on startup."""
        logger.info("Loading initial monster list from database...")
        try:
            # Fetch all monsters (standard and custom) initially
            # search_monsters returns List[Monster]
            self.monsters = self.db_manager.search_monsters("", include_custom=True, include_standard=True)
            logger.info(f"Loaded {len(self.monsters)} monsters.")
            self._populate_monster_list()
        except Exception as e:
            logger.error(f"Failed to load initial monsters: {e}", exc_info=True)
            QMessageBox.warning(self, "Load Error", f"Could not load monsters from the database: {e}")
        finally:
             self._update_button_states() # Ensure buttons are correct state initially

    def _populate_monster_list(self):
        """Populate the monster list widget based on current filters and loaded data."""
        self.monster_list.clear()
        self.monster_list.blockSignals(True) # Block signals during population

        search_text = self.search_input.text().lower().strip()
        cr_filter = self.cr_filter.currentText()
        type_filter = self.type_filter.currentText().lower() # Lowercase for comparison

        logger.debug(f"Filtering monsters. Search: '{search_text}', CR: '{cr_filter}', Type: '{type_filter}'")

        count = 0
        for monster in self.monsters:
            # Apply filters
            if search_text and search_text not in monster.name.lower():
                continue

            # CR Filtering - needs careful comparison for fractions
            if cr_filter != "All CRs":
                 # Normalize CR for comparison (e.g., "1/2" vs "0.5") - simplistic for now
                 # A more robust solution might involve converting CRs to numerical values
                 if monster.challenge_rating != cr_filter:
                     # Basic check, might miss equivalent CRs (e.g. "5.0" vs "5")
                     continue

            # Type Filtering
            if type_filter != "all types":
                 # Check if the selected type is a substring of the monster's type
                 # Handles cases like "humanoid (elf)" matching "humanoid"
                 if type_filter not in monster.type.lower():
                     continue

            # If all filters pass, add to list
            item = QListWidgetItem(monster.name)
            # Store tuple (id, is_custom) in UserRole for later retrieval
            item.setData(Qt.UserRole, (monster.id, monster.is_custom))
            # Optional: Add tooltip with basic info like CR/Type
            item.setToolTip(f"CR: {monster.challenge_rating}, Type: {monster.type}, Source: {monster.source}")
            self.monster_list.addItem(item)
            count += 1

        self.monster_list.blockSignals(False) # Unblock signals
        logger.debug(f"Populated list with {count} monsters.")
        # Reselect the current monster if it's still in the filtered list
        if self.current_monster:
            items = self.monster_list.findItems(self.current_monster.name, Qt.MatchExactly)
            if items:
                self.monster_list.setCurrentItem(items[0])

    def _on_monster_selected(self, current: QListWidgetItem, previous: QListWidgetItem):
        """Display the selected monster's stat block and update button states."""
        if not current:
            self.current_monster = None
            self._clear_monster_details()
            self._update_button_states()
            return

        try:
            monster_id, is_custom = current.data(Qt.UserRole)
            logger.debug(f"Monster selected: ID={monster_id}, IsCustom={is_custom}, Name='{current.text()}'")

            # Find the monster in the loaded list (more efficient than DB query)
            found_monster = None
            for m in self.monsters:
                if m.id == monster_id and m.is_custom == is_custom:
                    found_monster = m
                    break

            if found_monster:
                self.current_monster = found_monster
                logger.debug(f"Found monster in memory: {self.current_monster.name}")
            else:
                # Fallback: If not found in memory list (should not happen if list is correct), fetch from DB
                logger.warning(f"Monster ID {monster_id} (Custom: {is_custom}) not found in memory list. Fetching from DB.")
                self.current_monster = self.db_manager.get_monster_by_id(monster_id, is_custom)
                if not self.current_monster:
                     logger.error(f"Failed to fetch monster ID {monster_id} from DB.")
                     self._clear_monster_details()
                     self.current_monster = None # Ensure it's None if fetch failed
                     self._update_button_states()
                     return

            # Format stat block using the new display method
            self._display_monster_details(self.current_monster)

        except Exception as e:
            logger.error(f"Error displaying monster details: {e}", exc_info=True)
            self._clear_monster_details() # Clear display on error
            QMessageBox.critical(self, "Display Error", f"Error displaying monster: {e}")
            self.current_monster = None # Clear current monster on error

        finally:
            self._update_button_states()

    def _display_monster_details(self, monster: Optional[Monster]):
        """Populate the UI labels with the details of the given monster."""
        if not monster:
            self._clear_monster_details()
            return

        # Helper to get modifier as string (with sign)
        def get_mod_str(score):
            mod = (score - 10) // 2
            return f"+{mod}" if mod >= 0 else str(mod)

        self.name_label.setText(monster.name)
        self.meta_label.setText(f"{monster.size} {monster.type}, {monster.alignment}")
        self.ac_label.setText(f"<b>Armor Class</b> {monster.armor_class}")
        self.hp_label.setText(f"<b>Hit Points</b> {monster.hit_points}")
        self.speed_label.setText(f"<b>Speed</b> {monster.speed}")

        # Stats
        self.str_label.setText(f"<b>STR</b><br>{monster.strength} ({get_mod_str(monster.strength)})")
        self.dex_label.setText(f"<b>DEX</b><br>{monster.dexterity} ({get_mod_str(monster.dexterity)})")
        self.con_label.setText(f"<b>CON</b><br>{monster.constitution} ({get_mod_str(monster.constitution)})")
        self.int_label.setText(f"<b>INT</b><br>{monster.intelligence} ({get_mod_str(monster.intelligence)})")
        self.wis_label.setText(f"<b>WIS</b><br>{monster.wisdom} ({get_mod_str(monster.wisdom)})")
        self.cha_label.setText(f"<b>CHA</b><br>{monster.charisma} ({get_mod_str(monster.charisma)})")

        # Skills
        if monster.skills:
            skills_str = ", ".join([f"{s.name} {s.modifier:+}" for s in monster.skills])
            self.skills_label.setText(f"<b>Skills</b> {skills_str}")
            self.skills_label.setVisible(True)
        else:
            self.skills_label.setVisible(False)

        # Senses (including passive perception calculation)
        senses_list = [f"{s.name} {s.range}" for s in monster.senses]
        wis_mod_int = (monster.wisdom - 10) // 2
        passive_perception = 10 + wis_mod_int
        perception_skill = next((s for s in monster.skills if s.name.lower() == 'perception'), None)
        if perception_skill:
             passive_perception = 10 + perception_skill.modifier
        if not any("passive perception" in s.name.lower() for s in monster.senses):
             senses_list.append(f"passive Perception {passive_perception}")
             
        if senses_list:
            self.senses_label.setText(f"<b>Senses</b> {', '.join(senses_list)}")
            self.senses_label.setVisible(True)
        else:
            self.senses_label.setVisible(False)

        # Languages
        if monster.languages:
            self.languages_label.setText(f"<b>Languages</b> {monster.languages}")
            self.languages_label.setVisible(True)
        else:
            self.languages_label.setVisible(False)

        # Challenge Rating and XP
        if monster.challenge_rating:
            xp = get_xp_for_cr(monster.challenge_rating)
            self.cr_label.setText(f"<b>Challenge</b> {monster.challenge_rating}")
            self.xp_label.setText(f"<b>XP</b> {xp:,}") # Add comma formatting
            self.cr_label.setVisible(True)
            self.xp_label.setVisible(True)
        else:
            self.cr_label.setVisible(False)
            self.xp_label.setVisible(False)

        # Clear previous dynamic content (Traits, Actions, etc.)
        self._clear_layout(self.traits_layout)
        self._clear_layout(self.actions_layout)
        self._clear_layout(self.legendary_actions_layout)

        # Traits
        if monster.traits:
            self.traits_layout.addWidget(QLabel("<b>Traits</b>")) # Add header
            for trait in monster.traits:
                label = QLabel(f"<b><i>{trait.name}.</i></b> {trait.description}")
                label.setWordWrap(True)
                self.traits_layout.addWidget(label)

        # Actions
        if monster.actions:
            self.actions_layout.addWidget(QLabel("<h3>Actions</h3>")) # Use h3 style
            for action in monster.actions:
                label = QLabel(f"<b><i>{action.name}.</i></b> {action.description}")
                label.setWordWrap(True)
                self.actions_layout.addWidget(label)

        # Legendary Actions
        if monster.legendary_actions:
            self.legendary_actions_layout.addWidget(QLabel("<h3>Legendary Actions</h3>"))
            # Optional: Add intro text
            # self.legendary_actions_layout.addWidget(QLabel("The monster can take X legendary actions..."))
            for la in monster.legendary_actions:
                # Handle la being either a dict or a MonsterLegendaryAction object
                if isinstance(la, dict):
                    cost = la.get('cost', 1)
                    name = la.get('name', 'Unknown')
                    description = la.get('description', '')
                else:
                    cost = la.cost if hasattr(la, 'cost') else 1
                    name = la.name if hasattr(la, 'name') else 'Unknown'
                    description = la.description if hasattr(la, 'description') else ''
                
                cost_text = f" (Costs {cost} Actions)" if cost > 1 else ""
                label = QLabel(f"<b><i>{name}{cost_text}.</i></b> {description}")
                label.setWordWrap(True)
                self.legendary_actions_layout.addWidget(label)

        # Description / Lore
        if monster.description:
            self.description_label.setText(f"<hr><h3>Description</h3>{monster.description}")
            self.description_label.setVisible(True)
        else:
            self.description_label.setVisible(False)

    def _clear_monster_details(self):
        """Clear all the labels in the stat block display."""
        self.name_label.clear()
        self.meta_label.clear()
        self.ac_label.clear()
        self.hp_label.clear()
        self.speed_label.clear()
        self.str_label.clear()
        self.dex_label.clear()
        self.con_label.clear()
        self.int_label.clear()
        self.wis_label.clear()
        self.cha_label.clear()
        self.skills_label.clear()
        self.senses_label.clear()
        self.languages_label.clear()
        self.cr_label.clear()
        self.xp_label.clear() # Clear XP label
        self.description_label.clear()
        # Clear dynamic layouts
        self._clear_layout(self.traits_layout)
        self._clear_layout(self.actions_layout)
        self._clear_layout(self.legendary_actions_layout)

    def _clear_layout(self, layout):
        """Remove all widgets from a layout."""
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
                else:
                    # If item is another layout, clear it recursively
                    sub_layout = item.layout()
                    if sub_layout is not None:
                         self._clear_layout(sub_layout)

    def _filter_monsters(self):
        """Filter the monster list based on search text and combo boxes."""
        # We repopulate based on the full self.monsters list according to filters
        self._populate_monster_list()
        # Clear display if current selection is filtered out
        if self.current_monster:
             items = self.monster_list.findItems(self.current_monster.name, Qt.MatchExactly)
             if not items:
                  self._clear_monster_details()
                  self.current_monster = None
                  self._update_button_states()

    def _add_to_combat(self):
        """Add the current monster to the combat tracker."""
        if self.current_monster:
            logger.info(f"Adding monster '{self.current_monster.name}' to combat.")
            try:
                # Emit the monster data as a dictionary
                monster_dict = self.current_monster.to_dict()
                self.add_to_combat.emit(monster_dict)
                logger.debug("add_to_combat signal emitted.")
            except Exception as e:
                logger.error(f"Error emitting add_to_combat signal: {e}", exc_info=True)
                QMessageBox.critical(self, "Error", f"Could not add monster to combat: {e}")
        else:
             logger.warning("Add to combat called with no monster selected.")

    def _create_monster(self):
        """Open the monster creation/edit dialog for a new monster."""
        logger.info("Create Monster button clicked.")
        monster = Monster(is_custom=True, source="Custom")
        dialog = MonsterEditDialog(monster, self.llm_service, self.db_manager, self)

        if dialog.exec() == QDialog.Accepted:
            # Get the successfully saved monster object from the dialog
            saved_monster = dialog.get_saved_monster()
            if saved_monster: # Check if we got a valid monster back (implies successful save and ID set)
                self._add_or_update_monster_in_list(saved_monster)
                self._populate_monster_list()
                self.custom_monster_created.emit(saved_monster.name)
                logger.info(f"Custom monster '{saved_monster.name}' created and saved.")
                # ... select new monster in list ...
                for i in range(self.monster_list.count()):
                    item = self.monster_list.item(i)
                    data = item.data(Qt.UserRole)
                    if isinstance(data, tuple) and data == (saved_monster.id, True):
                        self.monster_list.setCurrentItem(item)
                        break
            else:
                 # This path might be hit if accept() succeeded but get_saved_monster returned None (save failed silently?)
                 logger.error("Monster creation dialog accepted, but could not retrieve valid saved monster object from dialog.")
        else:
            logger.info("Monster creation dialog cancelled.")

    def _edit_monster(self):
        """Open the monster creation/edit dialog for the selected custom monster."""
        if self.current_monster and self.current_monster.is_custom:
            logger.info(f"Edit Monster button clicked for: {self.current_monster.name}")
            # Pass the selected monster (or a copy if preferred)
            dialog = MonsterEditDialog(self.current_monster, self.llm_service, self.db_manager, self)

            if dialog.exec() == QDialog.Accepted:
                # Get the successfully saved monster object from the dialog
                edited_monster = dialog.get_saved_monster()
                if edited_monster:
                    # Update the panel's current selection ONLY if edit succeeded
                    self.current_monster = edited_monster
                    self._add_or_update_monster_in_list(edited_monster)
                    self._populate_monster_list()
                    # ... reselect edited monster ...
                    found = False
                    for i in range(self.monster_list.count()):
                         item = self.monster_list.item(i)
                         data = item.data(Qt.UserRole)
                         if isinstance(data, tuple) and data == (edited_monster.id, True):
                             self.monster_list.setCurrentItem(item)
                             self._on_monster_selected(item, None)
                             found = True
                             break
                    if not found:
                         self.monster_list.clearSelection()
                         self._on_monster_selected(None, None)
                    logger.info(f"Custom monster '{edited_monster.name}' updated.")
                else:
                     logger.error("Monster edit dialog accepted, but could not retrieve valid saved monster object from dialog.")
            else:
                 logger.info("Monster edit dialog cancelled.")
        else:
            logger.warning("Edit monster called but no custom monster is selected.")

    def _delete_monster(self):
        """Delete the selected custom monster."""
        if self.current_monster and self.current_monster.is_custom:
            monster_name = self.current_monster.name
            monster_id = self.current_monster.id
            logger.info(f"Delete Monster button clicked for: {monster_name} (ID: {monster_id})")

            reply = QMessageBox.question(self, "Confirm Delete",
                                       f"Are you sure you want to permanently delete the custom monster '{monster_name}'?",
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                       QMessageBox.StandardButton.No)

            if reply == QMessageBox.StandardButton.Yes:
                logger.info(f"Deletion confirmed for monster ID: {monster_id}")
                try:
                    success = self.db_manager.delete_custom_monster(monster_id)
                    if success:
                        logger.info(f"Successfully deleted monster ID {monster_id} from database.")
                        # Remove from internal list
                        self.monsters = [m for m in self.monsters if not (m.id == monster_id and m.is_custom)]
                        # Clear selection and repopulate list
                        self.current_monster = None
                        self._clear_monster_details()
                        self._populate_monster_list()
                        self._update_button_states()
                        QMessageBox.information(self, "Deleted", f"Monster '{monster_name}' deleted.")
                    else:
                        # This might happen if delete fails in DB manager despite confirmation
                        logger.error(f"db_manager reported failure deleting monster ID {monster_id}.")
                        QMessageBox.critical(self, "Error", f"Failed to delete monster '{monster_name}' from the database.")
                except Exception as e:
                    logger.error(f"Exception during monster deletion (ID: {monster_id}): {e}", exc_info=True)
                    QMessageBox.critical(self, "Error", f"An error occurred while deleting '{monster_name}': {e}")
        else:
            logger.warning("Delete monster called but no custom monster is selected.")

    def _update_button_states(self):
        """Enable/disable buttons based on current selection."""
        has_selection = self.current_monster is not None
        is_custom_selected = has_selection and self.current_monster.is_custom

        self.add_to_combat_btn.setEnabled(has_selection)
        self.edit_monster_btn.setEnabled(is_custom_selected)
        self.delete_monster_btn.setEnabled(is_custom_selected)

    # Helper to update internal list after create/edit
    def _add_or_update_monster_in_list(self, updated_monster: Monster):
        """Adds or updates a monster in the internal self.monsters list."""
        if not updated_monster or updated_monster.id is None:
            logger.warning("Attempted to add/update invalid monster in internal list.")
            return

        found = False
        for i, monster in enumerate(self.monsters):
            # Match by ID and is_custom flag
            if monster.id == updated_monster.id and monster.is_custom == updated_monster.is_custom:
                self.monsters[i] = updated_monster # Replace existing entry
                found = True
                logger.debug(f"Updated monster ID {updated_monster.id} in internal list.")
                break
        if not found:
            self.monsters.append(updated_monster) # Add new entry
            logger.debug(f"Added new monster ID {updated_monster.id} to internal list.")
            # Optional: Resort list if needed (e.g., after adding)
            # self.monsters.sort(key=lambda m: m.name)

    # --- State Management (Example) ---
    # Override if BasePanel requires specific state handling for this panel
    # def save_state(self) -> Dict[str, Any]:
    #     state = super().save_state()
    #     state['current_monster_id'] = self.current_monster.id if self.current_monster else None
    #     state['current_monster_is_custom'] = self.current_monster.is_custom if self.current_monster else None
    #     # Add filter states if needed
    #     return state

    # def restore_state(self, state: Dict[str, Any]):
    #     super().restore_state(state)
    #     monster_id = state.get('current_monster_id')
    #     is_custom = state.get('current_monster_is_custom')
    #     if monster_id is not None and is_custom is not None:
    #          # Find and select the monster in the list after loading
    #          # Need to ensure monsters are loaded before calling this
    #          pass # Implementation depends on when restore_state is called vs _load_initial_monsters


# Example: Placeholder for the Edit Dialog (would be in its own file)
# class MonsterEditDialog(QDialog):
#     def __init__(self, monster: Monster, llm_service, parent=None):
#         super().__init__(parent)
#         self.monster = monster # Store the monster being edited/created
#         self.llm_service = llm_service
#         self.setWindowTitle("Create/Edit Custom Monster")
#         self._setup_ui()
#
#     def _setup_ui(self):
#         layout = QVBoxLayout(self)
#         # ... Add QLineEdit, QTextEdit, etc. for all Monster fields ...
#         self.name_input = QLineEdit(self.monster.name)
#         layout.addWidget(QLabel("Name:"))
#         layout.addWidget(self.name_input)
#         # ... many more fields ...
#
#         # LLM Buttons
#         llm_layout = QHBoxLayout()
#         generate_btn = QPushButton("Generate from Prompt (LLM)")
#         generate_btn.clicked.connect(self._generate_with_llm)
#         extract_btn = QPushButton("Extract from Text (LLM)")
#         extract_btn.clicked.connect(self._extract_with_llm)
#         llm_layout.addWidget(generate_btn)
#         llm_layout.addWidget(extract_btn)
#         layout.addLayout(llm_layout)
#
#         # Dialog buttons (OK/Cancel)
#         button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
#         button_box.accepted.connect(self.accept) # `accept` will trigger saving
#         button_box.rejected.connect(self.reject)
#         layout.addWidget(button_box)
#
#     def _generate_with_llm(self):
#         # Show prompt input, call monster_generator.generate_monster_from_prompt
#         # Populate fields with result
#         pass
#
#     def _extract_with_llm(self):
#         # Show text input, call monster_generator.extract_monster_from_text
#         # Populate fields with result
#         pass
#
#     def accept(self):
#         # Called when OK is clicked
#         # 1. Update self.monster object from UI fields
#         self.monster.name = self.name_input.text()
#         # ... update all other fields ...
#         self.monster.is_custom = True # Ensure it's marked custom
#
#         # 2. Save to database (using db_manager from parent or passed in)
#         db_manager = self.parent().db_manager # Assuming parent is MonsterPanel
#         try:
#              saved_id = db_manager.save_custom_monster(self.monster)
#              if saved_id is not None:
#                  self.monster.id = saved_id # Update object with ID if new
#                  super().accept() # Close dialog if save successful
#              else:
#                  QMessageBox.critical(self, "Save Error", "Failed to save monster to database.")
#         except Exception as e:
#              QMessageBox.critical(self, "Save Error", f"An error occurred during save: {e}")
#
#     def get_monster(self) -> Optional[Monster]:
#         # Returns the saved monster object IF save was successful (dialog accepted)
#         # The caller should check if the dialog was accepted before calling this
#         return self.monster 