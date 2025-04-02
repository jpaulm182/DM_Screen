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

# Removed SAMPLE_MONSTER

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
        # QTextEdit is already scrollable
        self.stat_block_display = QTextEdit()
        self.stat_block_display.setReadOnly(True)
        content_layout.addWidget(self.stat_block_display, stretch=2) # Stat block takes 2/3 space

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
            self.stat_block_display.clear()
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
                     self.stat_block_display.setHtml("<p style='color: red;'>Error: Could not load monster details.</p>")
                     self.current_monster = None # Ensure it's None if fetch failed
                     self._update_button_states()
                     return

            # Format stat block using the Monster object
            html = self._format_monster_html(self.current_monster)
            self.stat_block_display.setHtml(html)

        except Exception as e:
            logger.error(f"Error displaying monster details: {e}", exc_info=True)
            self.stat_block_display.setHtml(f"<p style='color: red;'>Error displaying monster: {e}</p>")
            self.current_monster = None # Clear current monster on error

        finally:
            self._update_button_states()

    def _format_monster_html(self, monster: Monster) -> str:
        """Generates an HTML representation of the monster stat block."""
        if not monster:
            return ""

        # Helper to get modifier as integer
        def get_mod_int(score):
            return (score - 10) // 2

        # Helper to get modifier as string (with sign)
        def get_mod_str(score):
            mod = get_mod_int(score)
            return f"+{mod}" if mod >= 0 else str(mod)

        # Start HTML
        html = f"""
        <div style='font-family: sans-serif; padding: 5px;'>
            <h2 style='margin-bottom: 2px;'>{monster.name}</h2>
            <p style='margin-top: 0px; font-style: italic;'>{monster.size} {monster.type}, {monster.alignment}</p>
            <hr>
            <p><b>Armor Class</b> {monster.armor_class}</p>
            <p><b>Hit Points</b> {monster.hit_points}</p>
            <p><b>Speed</b> {monster.speed}</p>
            <hr>
            <table width='100%' style='text-align: center;'>
                <tr><th>STR</th><th>DEX</th><th>CON</th><th>INT</th><th>WIS</th><th>CHA</th></tr>
                <tr>
                    <td>{monster.strength} ({get_mod_str(monster.strength)})</td>
                    <td>{monster.dexterity} ({get_mod_str(monster.dexterity)})</td>
                    <td>{monster.constitution} ({get_mod_str(monster.constitution)})</td>
                    <td>{monster.intelligence} ({get_mod_str(monster.intelligence)})</td>
                    <td>{monster.wisdom} ({get_mod_str(monster.wisdom)})</td>
                    <td>{monster.charisma} ({get_mod_str(monster.charisma)})</td>
                </tr>
            </table>
            <hr>
        """

        # Skills
        if monster.skills:
            skills_str = ", ".join([f"{s.name} {s.modifier:+}" for s in monster.skills]) # Use sign for modifier
            html += f"<p><b>Skills</b> {skills_str}</p>"

        # Senses
        senses_list = [f"{s.name} {s.range}" for s in monster.senses]
        # Calculate passive perception using integer modifier
        wis_mod_int = get_mod_int(monster.wisdom)
        passive_perception = 10 + wis_mod_int
        perception_skill = next((s for s in monster.skills if s.name.lower() == 'perception'), None)
        if perception_skill:
             # If perception skill exists, passive perception uses the skill's full modifier value
             # (which includes proficiency bonus if proficient)
             # Assuming modifier is stored correctly as int
             passive_perception = 10 + perception_skill.modifier

        # Add passive perception if not already in senses list
        # Check based on name to avoid duplicates if LLM provided it
        if not any("passive perception" in s.name.lower() for s in monster.senses):
             senses_list.append(f"passive Perception {passive_perception}")

        if senses_list:
             html += f"<p><b>Senses</b> {', '.join(senses_list)}</p>"

        if monster.languages:
            html += f"<p><b>Languages</b> {monster.languages}</p>"

        if monster.challenge_rating:
             # TODO: Add XP calculation based on CR?
             html += f"<p><b>Challenge</b> {monster.challenge_rating}</p>" # Add XP later if needed

        html += "<hr>"

        # Traits
        if monster.traits:
            for trait in monster.traits:
                html += f"<p><b><i>{trait.name}.</i></b> {trait.description}</p>"

        # Actions
        if monster.actions:
            html += "<h3 style='margin-bottom: 2px;'>Actions</h3>"
            for action in monster.actions:
                html += f"<p><b><i>{action.name}.</i></b> {action.description}</p>"

        # Legendary Actions
        if monster.legendary_actions:
            html += "<h3 style='margin-bottom: 2px;'>Legendary Actions</h3>"
            # Optional: Add intro text about number of actions
            # html += "<p>The monster can take X legendary actions...</p>"
            for la in monster.legendary_actions:
                 cost_text = f"(Costs {la.cost} Actions)" if la.cost > 1 else ""
                 html += f"<p><b><i>{la.name} {cost_text}.</i></b> {la.description}</p>"

        # Description / Lore
        if monster.description:
             html += "<hr><h3>Description</h3>"
             html += f"<p>{monster.description}</p>"

        # Source and Type
        html += "<hr>"
        source_text = f"Source: {monster.source}"
        if monster.is_custom:
            source_text += " (Custom)"
            if monster.updated_at:
                source_text += f" | Updated: {monster.updated_at[:16]}" # Shorten timestamp
        html += f"<p style='font-size: small; color: grey;'>{source_text}</p>"

        html += "</div>"
        return html

    def _filter_monsters(self):
        """Filter the monster list based on search text and combo boxes."""
        # We repopulate based on the full self.monsters list according to filters
        self._populate_monster_list()
        # Clear display if current selection is filtered out
        if self.current_monster:
             items = self.monster_list.findItems(self.current_monster.name, Qt.MatchExactly)
             if not items:
                  self.stat_block_display.clear()
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
                        self.stat_block_display.clear()
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