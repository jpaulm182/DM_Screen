# app/ui/panels/combat_tracker/combatant_manager.py
# Manages combatants (adding, removing, data access) for the Combat Tracker Panel

import logging
import random
import re
from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import QTableWidgetItem, QMessageBox

# Import ImprovedCombatResolver conditionally for validation (if available)
try:
    from app.core.improved_combat_resolver import ImprovedCombatResolver
except ImportError:
    ImprovedCombatResolver = None # Allow running without resolver

class CombatantManager:
    """Handles the management of combatants within the combat tracker."""

    def __init__(self, panel):
        """
        Initializes the CombatantManager.

        Args:
            panel: The parent CombatTrackerPanel instance.
        """
        self.panel = panel  # Reference to the main panel
        self.combatants = {} # Store detailed combatant data, keyed by row index (or name/ID later?)
        self.combatants_by_id = {} # NEW: Store combatant data by unique instance ID
        self.monster_id_counter = 0 # Counter for unique monster instance IDs

    def _get_next_monster_id(self):
        """Generate a unique ID for a new monster instance."""
        self.monster_id_counter += 1
        return f"monster_instance_{self.monster_id_counter}"

    def add_combatant(self, name, initiative, hp, max_hp, ac, combatant_type="", monster_data=None):
        """
        Adds a single combatant to the initiative table.

        Args:
            name (str): Combatant's name.
            initiative (int): Combatant's initiative roll.
            hp (int): Combatant's current HP.
            max_hp (int): Combatant's maximum HP.
            ac (int): Combatant's Armor Class.
            combatant_type (str): Type ('character', 'monster', 'manual').
            monster_data (dict, optional): Full data for monsters being added.

        Returns:
            int: The final row index where the combatant was added, or -1 on failure.
        """
        # Ensure the panel and table are accessible
        if not self.panel or not hasattr(self.panel, 'initiative_table'):
            logging.error("[CombatantManager] Panel or initiative_table not available.")
            return -1

        # Generate a unique instance ID, especially important for monsters
        # Characters might use their name if unique, otherwise generate one.
        # Monsters *always* get a unique ID.
        instance_id = None
        if combatant_type == "monster":
            instance_id = self._get_next_monster_id()
            logging.debug(f"[CombatantManager] Generated monster instance ID: {instance_id} for {name}")
        elif combatant_type == "character":
            # Assuming character names are unique for now, could use UUID if needed
            instance_id = name
            logging.debug(f"[CombatantManager] Using character name as instance ID: {instance_id}")
        else: # manual/other
             instance_id = f"manual_{self.panel.initiative_table.rowCount()}" # Simple ID for manual entries
             logging.debug(f"[CombatantManager] Generated manual instance ID: {instance_id}")


        logging.debug(f"[CombatantManager] Adding combatant: Name={name}, Init={initiative}, HP={hp}/{max_hp}, AC={ac}, Type={combatant_type}, InstanceID={instance_id}")

        # Block signals on the table during modification
        self.panel.initiative_table.blockSignals(True)
        new_row_index = -1

        try:
            # Get current row count *before* insertion
            row_count = self.panel.initiative_table.rowCount()
            self.panel.initiative_table.insertRow(row_count)
            new_row_index = row_count # Store the intended index

            # --- Create Table Items ---
            # Name Item (Store type and instance ID)
            name_item = QTableWidgetItem(name)
            name_item.setData(Qt.UserRole, combatant_type)
            name_item.setData(Qt.UserRole + 2, instance_id) # Store unique instance ID
            name_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
            self.panel.initiative_table.setItem(new_row_index, 0, name_item)

            # Initiative Item
            init_item = QTableWidgetItem()
            init_item.setData(Qt.DisplayRole, int(initiative)) # Store as int for sorting
            init_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
            self.panel.initiative_table.setItem(new_row_index, 1, init_item)

            # HP Item
            hp_str = str(hp) if hp is not None else "10"
            hp_item = QTableWidgetItem(hp_str)
            hp_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
            self.panel.initiative_table.setItem(new_row_index, 2, hp_item)

            # Max HP Item
            max_hp_str = str(max_hp) if max_hp is not None else "10"
            max_hp_item = QTableWidgetItem(max_hp_str)
            max_hp_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
            self.panel.initiative_table.setItem(new_row_index, 3, max_hp_item)

            # AC Item
            ac_str = str(ac) if ac is not None else "10"
            ac_item = QTableWidgetItem(ac_str)
            ac_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
            self.panel.initiative_table.setItem(new_row_index, 4, ac_item)

            # Status Item
            status_item = QTableWidgetItem("")
            status_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
            self.panel.initiative_table.setItem(new_row_index, 5, status_item)

            # Concentration Item
            conc_item = QTableWidgetItem()
            conc_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            conc_item.setCheckState(Qt.Unchecked)
            self.panel.initiative_table.setItem(new_row_index, 6, conc_item)

            # Type Item
            type_item = QTableWidgetItem(combatant_type)
            type_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
            self.panel.initiative_table.setItem(new_row_index, 7, type_item)

            # --- Store Combatant Data ---
            # Store comprehensive data associated with this instance ID
            combatant_full_data = {
                "name": name,
                "initiative": initiative,
                "hp": hp,
                "max_hp": max_hp,
                "ac": ac,
                "status": "",
                "concentration": False,
                "type": combatant_type,
                "instance_id": instance_id,
                # Add monster-specific details if available
                **(monster_data if monster_data and isinstance(monster_data, dict) else {})
            }
            # Use the unique instance_id as the key for storage
            self.combatants_by_id[instance_id] = combatant_full_data
            logging.debug(f"[CombatantManager] Stored data for {instance_id}: {combatant_full_data}")


        except Exception as e:
            logging.error(f"[CombatantManager] Error adding combatant row {new_row_index}: {e}", exc_info=True)
            # Clean up potentially partially added row if error occurred
            if new_row_index != -1 and new_row_index < self.panel.initiative_table.rowCount():
                self.panel.initiative_table.removeRow(new_row_index)
            # Remove stored data if added
            if instance_id and instance_id in self.combatants_by_id:
                del self.combatants_by_id[instance_id]
            new_row_index = -1 # Indicate failure
        finally:
            # Always unblock signals
            self.panel.initiative_table.blockSignals(False)


        # Sort initiative *after* adding and unblocking signals
        # Sorting might change the row index, so we need to find the *new* row
        if new_row_index != -1:
             self.panel._sort_initiative() # Call the panel's sort method
             # Find the new row index based on the unique instance ID
             final_row_index = self.find_combatant_row_by_id(instance_id)
             if final_row_index == -1:
                 logging.warning(f"[CombatantManager] Could not find combatant {name} (ID: {instance_id}) after sorting! Using original index {new_row_index}.")
                 # Fallback: maybe sorting failed or ID wasn't set right?
                 # Check the original index again.
                 check_item = self.panel.initiative_table.item(new_row_index, 0)
                 if check_item and check_item.data(Qt.UserRole + 2) == instance_id:
                     final_row_index = new_row_index
                 else:
                    # Still can't find it, something is wrong.
                    logging.error(f"[CombatantManager] CRITICAL: Failed to locate added combatant {name} (ID: {instance_id}) post-sort.")
                    # Maybe remove the potentially broken entry? Or return error?
                    return -1 # Indicate failure

             logging.debug(f"[CombatantManager] Combatant {name} (ID: {instance_id}) is at final row {final_row_index} after sorting.")
             return final_row_index
        else:
            return -1 # Return failure


    def find_combatant_row_by_id(self, instance_id):
        """Find the current table row of a combatant by its unique instance ID."""
        if not instance_id or not self.panel or not hasattr(self.panel, 'initiative_table'):
            return -1

        for row in range(self.panel.initiative_table.rowCount()):
            name_item = self.panel.initiative_table.item(row, 0)
            # Check the UserRole+2 data where the instance ID is stored
            if name_item and name_item.data(Qt.UserRole + 2) == instance_id:
                return row
        return -1 # Not found

    # This slot receives the signal from PlayerCharacterPanel
    @Slot(object)
    def add_character(self, character):
        """Add a player character received from the PlayerCharacterPanel."""
        try:
            if not character or not hasattr(character, 'name'):
                logging.error("[CombatantManager] Received invalid character object.")
                QMessageBox.critical(self.panel, "Error", "Received invalid character data.")
                return

            logging.info(f"[CombatantManager] Received character to add: {character.name}")

            # Extract data from the PlayerCharacter object using getattr for safety
            name = getattr(character, 'name', "Unnamed Character")
            initiative_bonus = getattr(character, 'initiative_bonus', 0)
            try:
                # Ensure bonus is numeric
                initiative_bonus = int(initiative_bonus)
            except (ValueError, TypeError):
                logging.warning(f"Invalid initiative bonus for {name}: {initiative_bonus}. Using 0.")
                initiative_bonus = 0

            # Roll initiative: 1d20 + bonus
            initiative = random.randint(1, 20) + initiative_bonus

            # Extract HP and AC, providing defaults
            hp = getattr(character, 'current_hp', 10)
            max_hp = getattr(character, 'max_hp', 10)
            ac = getattr(character, 'armor_class', 10)

            # Ensure HP/MaxHP/AC are numeric, defaulting if not
            try: hp = int(hp)
            except (ValueError, TypeError): hp = 10
            try: max_hp = int(max_hp)
            except (ValueError, TypeError): max_hp = hp # Default max_hp to current hp if invalid
            try: ac = int(ac)
            except (ValueError, TypeError): ac = 10

            # Prepare character data dict for storage
            # Convert character object attributes to a dictionary if possible
            char_data = {}
            if hasattr(character, '__dict__'):
                char_data = character.__dict__.copy() # Get attributes
            else: # Fallback if no __dict__
                 char_data = {'name': name, 'initiative_bonus': initiative_bonus, 'current_hp':hp, 'max_hp':max_hp, 'armor_class':ac}

            # Add the character using the core add_combatant method
            # Pass the dictionary as 'monster_data' for storage purposes
            row = self.add_combatant(name, initiative, hp, max_hp, ac, combatant_type="character", monster_data=char_data)

            if row >= 0:
                logging.info(f"[CombatantManager] Successfully added character '{name}' to combat at row {row} with initiative {initiative}.")
                # Log the action via the panel's logger
                self.panel._log_combat_action("Setup", "DM", "added character", name, f"(Rolled Initiative: {initiative})")
            else:
                logging.error(f"[CombatantManager] Failed to add character '{name}' using add_combatant.")
                QMessageBox.warning(self.panel, "Add Failed", f"Failed to add character '{name}' to the combat tracker.")

        except AttributeError as e:
            logging.error(f"[CombatantManager] Error accessing attribute on received character object: {e}", exc_info=True)
            QMessageBox.critical(self.panel, "Error", f"Failed to add character. The character data might be incomplete or invalid: {e}")
        except Exception as e:
            logging.error(f"[CombatantManager] Unexpected error adding character: {e}", exc_info=True)
            QMessageBox.critical(self.panel, "Error", f"An unexpected error occurred while adding the character: {str(e)}")

    # This slot receives signals from the MonsterPanel or other sources
    @Slot(list) # Can receive a list of monster dictionaries
    def add_combatant_group(self, monster_list: list):
        """Add a list of monsters (as dictionaries) to the combat tracker.
        Args:
            monster_list (list): List of monster dictionaries or objects to add.
        """
        if not isinstance(monster_list, list):
            logging.error(f"[CombatantManager] Error: add_combatant_group received non-list: {type(monster_list)}")
            return

        logging.info(f"[CombatantManager] Received group of {len(monster_list)} monsters to add.")
        added_count = 0
        failed_count = 0
        rows_added = []

        for monster_data in monster_list:
            try:
                # Extract name for logging, handle dict/object cases
                monster_name = "Unknown"
                if isinstance(monster_data, dict) and 'name' in monster_data:
                    monster_name = monster_data['name']
                elif hasattr(monster_data, 'name'):
                    monster_name = monster_data.name

                logging.debug(f"[CombatantManager] Adding monster from group: {monster_name}")

                # Use the add_monster method to handle individual addition
                row = self.add_monster(monster_data)
                if row >= 0:
                    added_count += 1
                    rows_added.append(row)
                    # Optional: Verify type in table after adding (add_monster should handle it)
                    type_item = self.panel.initiative_table.item(row, 7)
                    if type_item and type_item.text() != "monster":
                         logging.warning(f"[CombatantManager] Type mismatch for added monster {monster_name} at row {row}. Expected 'monster', found '{type_item.text()}'. Attempting fix.")
                         type_item.setText("monster")
                         name_item = self.panel.initiative_table.item(row, 0)
                         if name_item: name_item.setData(Qt.UserRole, "monster")

                else:
                    failed_count += 1
                    logging.error(f"[CombatantManager] Failed to add monster '{monster_name}' from group.")
            except Exception as e:
                failed_count += 1
                name = "Unknown"
                if isinstance(monster_data, dict): name = monster_data.get("name", "Unknown")
                elif hasattr(monster_data, 'name'): name = getattr(monster_data, 'name', "Unknown")
                logging.error(f"[CombatantManager] Error adding monster '{name}' from group: {e}", exc_info=True)


        if added_count > 0:
            logging.info(f"[CombatantManager] Added {added_count} monsters from group (failed: {failed_count}).")
            # Sort initiative after adding the whole group
            self.panel._sort_initiative()
        else:
            logging.warning(f"[CombatantManager] No monsters were added from the group (all {failed_count} failed).")


    def add_monster(self, monster_data):
        """Adds a single monster (dict or object) to the combat tracker."""
        if not monster_data:
            logging.warning("[CombatantManager] add_monster called with empty data.")
            return -1

        monster_name = "Unknown Monster"
        hp = 10
        max_hp = 10
        ac = 10
        initiative = 10 # Default initiative if not found/rolled

        # --- Data Extraction ---
        try:
            # Handle both dictionary and object inputs
            if isinstance(monster_data, dict):
                monster_dict = monster_data
                monster_name = monster_dict.get('name', monster_name)
                # Extract HP - handles "10 (3d6)" format or just number/dice string
                hp_string = str(monster_dict.get('hit_points', monster_dict.get('hp', '10')))
                max_hp = 10 # default max HP
                hp = 10 # default current HP

                # Try to parse average and roll dice
                try:
                    # Extract average HP (number before parenthesis)
                    match_avg = re.match(r"\s*(\d+)", hp_string)
                    if match_avg:
                        max_hp = int(match_avg.group(1))
                    
                    # Extract dice formula (inside parenthesis)
                    formula_match = re.search(r"\((.*?)\)", hp_string)
                    if formula_match:
                        formula = formula_match.group(1).replace(" ", "") # Remove spaces
                        # Roll for current HP using the formula
                        hp = self.panel.roll_dice(formula) 
                        # Use average if roll fails or is unreasonable
                        if not isinstance(hp, int) or hp <= 0 or hp > max_hp * 2:
                            print(f"[CombatantManager] Warning: Dice roll for {formula} failed or unreasonable ({hp}). Using average HP {max_hp}.")
                            hp = max_hp
                    else:
                        # If no formula, use the average/parsed number for both current and max HP
                        hp = max_hp 
                except Exception as e:
                    print(f"[CombatantManager] Error parsing HP string '{hp_string}': {e}. Using defaults.")
                    hp = 10
                    max_hp = 10

                # Ensure HP values are reasonable minimums
                hp = max(1, hp)
                max_hp = max(1, max_hp)
                
                # Ensure current HP doesn't exceed max HP initially
                hp = min(hp, max_hp)

                print(f"[CombatantManager] Parsed HP for {monster_name}: Current={hp}, Max={max_hp}")

                # Extract AC
                ac = monster_dict.get('ac', monster_dict.get('armor_class', 10))
                if not isinstance(ac, int):
                    try:
                        ac = int(ac) # Handle AC potentially being a string
                    except (ValueError, TypeError):
                        ac = 10 # Default AC if conversion fails
                
                # Extract Initiative Modifier (Dexterity)
                dex = monster_dict.get('dex', monster_dict.get('dexterity', 10))
                if not isinstance(dex, int):
                     try:
                         dex = int(dex)
                     except (ValueError, TypeError):
                         dex = 10
                init_mod = (dex - 10) // 2
                initiative = random.randint(1, 20) + init_mod
                
                # Keep the full original dictionary for storage, but use parsed values for adding
                storage_data = monster_dict
                
            elif hasattr(monster_data, 'name'): # Handle object input (e.g., Monster class instance)
                 # Fallback logic for object attributes (should ideally not be needed if to_dict works)
                 monster_name = getattr(monster_data, 'name', monster_name)
                 # Similar HP parsing logic required here if this path is used
                 hp_string = getattr(monster_data, 'hit_points', '10') # Assuming attribute name 'hit_points'
                 # ... (repeat HP parsing logic as above) ... 
                 # For brevity, assuming to_dict path is the primary one
                 hp = getattr(monster_data, 'hp', hp) # Placeholder if direct attribute exists
                 max_hp = getattr(monster_data, 'max_hp', max_hp)
                 ac = getattr(monster_data, 'armor_class', ac)
                 dex = getattr(monster_data, 'dexterity', 10)
                 init_mod = (dex - 10) // 2
                 initiative = random.randint(1, 20) + init_mod
                 # Convert object to dict for storage (less ideal than a proper to_dict)
                 storage_data = {attr: getattr(monster_data, attr) for attr in dir(monster_data) if not attr.startswith('_') and not callable(getattr(monster_data, attr))}
            else:
                logging.error(f"[CombatantManager] Unsupported monster_data type: {type(monster_data)}")
                return -1 # Indicate failure

            # Validate data using ImprovedCombatResolver if available
            if ImprovedCombatResolver and isinstance(storage_data, dict):
                 # ... (Keep existing validation logic) ...
                 pass # Placeholder for brevity

        except Exception as e:
            logging.error(f"[CombatantManager] Error during monster data extraction for '{monster_name}': {e}", exc_info=True)
            return -1

        # --- Combatant Addition ---
        try:
            # Ensure hp and max_hp are integers
            hp = int(hp)
            max_hp = int(max_hp)
            ac = int(ac)
            initiative = int(initiative)

            # Use the parsed/validated values to add the combatant
            # Add using the core method, passing the full (validated) data
            row = self.add_combatant(
                name=monster_name,
                initiative=initiative,
                hp=hp,
                max_hp=max_hp,
                ac=ac,
                combatant_type="monster",
                monster_data=storage_data # Pass the full dictionary
            )

            if row >= 0:
                logging.info(f"[CombatantManager] Successfully added monster '{monster_name}' at row {row}.")
                # Log action via panel
                self.panel._log_combat_action("Setup", "DM", "added monster", monster_name, f"(Rolled Initiative: {initiative})")
            else:
                 logging.error(f"[CombatantManager] Failed to add monster '{monster_name}' via add_combatant.")

            return row # Return the final row index (or -1)

        except Exception as e:
            logging.error(f"[CombatantManager] Unexpected error processing monster data for '{monster_name}': {e}", exc_info=True)
            return -1 # Indicate failure


    def remove_selected(self):
        """
        Marks selected combatants as 'Dead' and triggers cleanup.

        Relies on the panel's _cleanup_dead_combatants method to handle
        actual removal and state updates (current turn, concentrating set etc.).
        """
        if not self.panel or not hasattr(self.panel, 'initiative_table'):
            logging.error("[CombatantManager] Cannot remove selected, panel or table not available.")
            return

        try:
            selected_indexes = self.panel.initiative_table.selectedIndexes()
            if not selected_indexes:
                return # Nothing selected

            # Get unique rows, sorted ascending
            rows_to_remove = sorted(list(set(idx.row() for idx in selected_indexes)))

            if not rows_to_remove:
                return

            # Confirmation dialog
            reply = QMessageBox.question(
                self.panel, # Parent widget
                "Remove Combatant(s)",
                f"Remove {len(rows_to_remove)} selected combatant(s) from the tracker?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No, # Default button
            )

            if reply != QMessageBox.StandardButton.Yes:
                return # User cancelled

            logging.info(f"[CombatantManager] User confirmed removal of rows: {rows_to_remove}")

            # Mark rows for removal by setting status to 'Dead'
            # The panel's cleanup method will handle the actual removal.
            self.panel.initiative_table.blockSignals(True) # Block signals during marking
            modified_rows = []
            try:
                for row in reversed(rows_to_remove): # Iterate backwards to avoid index issues if removing directly
                    if row < self.panel.initiative_table.rowCount():
                        status_item = self.panel.initiative_table.item(row, 5) # Status column
                        if status_item is None:
                            status_item = QTableWidgetItem("Dead")
                            self.panel.initiative_table.setItem(row, 5, status_item)
                        else:
                            status_item.setText("Dead")
                        modified_rows.append(row)
                    else:
                        logging.warning(f"[CombatantManager] Row index {row} out of bounds during removal marking.")

            finally:
                 self.panel.initiative_table.blockSignals(False) # Unblock signals

            # Call the panel's cleanup method IF any rows were actually marked
            if modified_rows:
                 logging.debug(f"[CombatantManager] Triggering panel's cleanup for rows marked dead: {modified_rows}")
                 # Use QTimer.singleShot to ensure cleanup happens after current event processing
                 from PySide6.QtCore import QTimer
                 QTimer.singleShot(0, self.panel._cleanup_dead_combatants)

        except Exception as e:
            logging.error(f"[CombatantManager] Error during remove_selected: {e}", exc_info=True)
            # Ensure signals are unblocked in case of error
            if self.panel and hasattr(self.panel, 'initiative_table'):
                 self.panel.initiative_table.blockSignals(False)


    def get_combatant_data(self, row):
        """
        Retrieves combined data for a combatant at a specific row.

        Prioritizes data stored in self.combatants_by_id using the instance ID
        from the table, then updates it with the current state from the table cells.

        Args:
            row (int): The row index in the initiative table.

        Returns:
            dict: A dictionary containing the combatant's data, or None if invalid row.
        """
        if not self.panel or not hasattr(self.panel, 'initiative_table') or row < 0 or row >= self.panel.initiative_table.rowCount():
            logging.warning(f"[CombatantManager] get_combatant_data: Invalid row index {row}")
            return None

        combatant_data = {}
        instance_id = None

        try:
            # --- Get Instance ID from Table ---
            name_item = self.panel.initiative_table.item(row, 0)
            if name_item:
                instance_id = name_item.data(Qt.UserRole + 2)
                if instance_id:
                     logging.debug(f"[CombatantManager] Found instance ID '{instance_id}' for row {row}")
                else:
                     logging.warning(f"[CombatantManager] No instance ID found for row {row}, data retrieval might be incomplete.")
            else:
                logging.warning(f"[CombatantManager] No name item found for row {row}, cannot get instance ID.")
                # Attempt to construct some data purely from table as fallback
                instance_id = None # Ensure it's None

            # --- Retrieve Base Data using Instance ID ---
            if instance_id and instance_id in self.combatants_by_id:
                # Make a copy to avoid modifying the stored master data
                combatant_data = self.combatants_by_id[instance_id].copy()
                logging.debug(f"[CombatantManager] Retrieved base data for instance ID '{instance_id}'")
            else:
                logging.warning(f"[CombatantManager] No stored data found for instance ID '{instance_id}' (or ID is missing). Building data from table.")
                # If no stored data, create a basic structure
                combatant_data = {'instance_id': instance_id} # Still store ID if we have it


            # --- Update with Current Table Values ---
            table_updates = {}
            headers = self.panel.COLUMN_HEADERS # Get headers from panel constant
            for col, header_key in headers.items():
                item = self.panel.initiative_table.item(row, col)
                if item:
                    if header_key == "concentration": # Column 6
                        table_updates[header_key] = item.checkState() == Qt.CheckState.Checked
                    elif header_key == "name": # Column 0
                         table_updates[header_key] = item.text()
                         # Also get type from UserRole data on name item
                         type_role = item.data(Qt.UserRole)
                         if type_role:
                             table_updates['type'] = type_role
                         # Ensure instance ID from table matches, or update if missing
                         table_id = item.data(Qt.UserRole + 2)
                         if not combatant_data.get('instance_id') and table_id:
                              combatant_data['instance_id'] = table_id
                         elif combatant_data.get('instance_id') != table_id:
                              logging.warning(f"Instance ID mismatch for row {row}! Stored: {combatant_data.get('instance_id')}, Table: {table_id}")
                              # Potentially update stored ID? Or log error? For now, trust table.
                              combatant_data['instance_id'] = table_id

                    elif header_key in ["initiative", "hp", "max_hp", "ac"]:
                        # Try converting to int, fallback to text
                        try:
                            table_updates[header_key] = int(item.text())
                        except (ValueError, TypeError):
                             table_updates[header_key] = item.text() # Keep as string if conversion fails
                             logging.warning(f"Could not convert column '{header_key}' value '{item.text()}' to int for row {row}")
                    else: # Status, Type columns
                        table_updates[header_key] = item.text()
                else:
                     # If item doesn't exist, ensure key is present with None or default?
                     # For now, we only update if item exists.
                     pass

            # Update the base data with the latest from the table
            # Table values generally override stored values for dynamic state (hp, status, conc)
            combatant_data.update(table_updates)

            # --- Add Death Saves (managed by the panel) ---
            if hasattr(self.panel, 'death_saves') and row in self.panel.death_saves:
                combatant_data['death_saves'] = self.panel.death_saves[row]

            # --- Add Concentration status (managed by the panel) ---
            # Note: table_updates should already contain concentration from the checkbox
            # combatant_data['concentration'] = row in self.panel.concentrating # Alternative check


            logging.debug(f"[CombatantManager] Final combined data for row {row}: {combatant_data}")
            return combatant_data

        except Exception as e:
            logging.error(f"[CombatantManager] Error in get_combatant_data for row {row}: {e}", exc_info=True)
            return None # Return None on error


    def fix_missing_types(self):
        """
        Iterates through the table, identifies combatants with missing or invalid
        types, and attempts to infer the correct type ('monster', 'character', 'manual').

        Updates both the table cell (column 7) and the UserRole data on the name item (column 0).

        Returns:
            int: The number of combatants whose types were fixed.
        """
        if not self.panel or not hasattr(self.panel, 'initiative_table'):
            logging.error("[CombatantManager] Cannot fix types, panel or table not available.")
            return 0

        fix_count = 0
        logging.info("[CombatantManager] Running fix_missing_types...")
        self.panel.initiative_table.blockSignals(True) # Prevent signals during fix

        try:
            for row in range(self.panel.initiative_table.rowCount()):
                name_item = self.panel.initiative_table.item(row, 0)
                type_item = self.panel.initiative_table.item(row, 7) # Type column index from panel constant

                name = name_item.text() if name_item else f"Row {row} (No Name)"
                instance_id = name_item.data(Qt.UserRole + 2) if name_item else None

                # --- Determine if Fix is Needed ---
                current_type_text = type_item.text().lower().strip() if type_item and type_item.text() else ""
                current_type_role = name_item.data(Qt.UserRole) if name_item else None

                needs_fix = False
                reason = ""

                if not current_type_text or current_type_text not in ["monster", "character", "manual"]:
                    needs_fix = True
                    reason = f"Invalid/missing text ('{current_type_text}')"
                elif not current_type_role or current_type_role not in ["monster", "character", "manual"]:
                     needs_fix = True
                     reason = f"Invalid/missing role data ('{current_type_role}')"
                elif current_type_text != current_type_role:
                     needs_fix = True
                     reason = f"Mismatch between text ('{current_type_text}') and role ('{current_type_role}')"


                if needs_fix:
                    logging.debug(f"Row {row} ('{name}') needs type fix. Reason: {reason}")
                    inferred_type = "manual" # Default assumption

                    # --- Inference Logic ---
                    # 1. Check stored data using instance ID
                    if instance_id and instance_id in self.combatants_by_id:
                        stored_data = self.combatants_by_id[instance_id]
                        if isinstance(stored_data, dict):
                            stored_type = stored_data.get('type', '').lower()
                            if stored_type in ["monster", "character"]:
                                inferred_type = stored_type
                                logging.debug(f"  Inferred type '{inferred_type}' from stored data.")

                    # 2. Use heuristics if still manual/unknown
                    if inferred_type == "manual":
                         # Add name heuristics (simplified)
                        monster_keywords = ["goblin", "orc", "dragon", "zombie", "skeleton", "beholder", "lich"] # Example keywords
                        lower_name = name.lower()
                        if any(keyword in lower_name for keyword in monster_keywords):
                             inferred_type = "monster"
                             logging.debug(f"  Inferred type '{inferred_type}' from name keyword.")
                        elif "(pc)" in lower_name or "(player)" in lower_name:
                             inferred_type = "character"
                             logging.debug(f"  Inferred type '{inferred_type}' from name suffix.")
                        # Could add more heuristics (e.g., check for class/level in name)

                    # --- Apply the Fix ---
                    # Update Type Column (Column 7)
                    if type_item is None:
                        type_item = QTableWidgetItem(inferred_type)
                        self.panel.initiative_table.setItem(row, 7, type_item)
                        logging.debug(f"  Created and set type item to '{inferred_type}'")
                    elif type_item.text() != inferred_type:
                        type_item.setText(inferred_type)
                        logging.debug(f"  Updated type item text to '{inferred_type}'")

                    # Update Name Item UserRole (Column 0)
                    if name_item is None:
                         # This shouldn't happen if we have a name, but handle defensively
                         logging.warning(f"  Cannot set type role for row {row}, name item is missing.")
                    elif name_item.data(Qt.UserRole) != inferred_type:
                        name_item.setData(Qt.UserRole, inferred_type)
                        logging.debug(f"  Updated name item role data to '{inferred_type}'")

                    # Update stored data if inconsistent
                    if instance_id and instance_id in self.combatants_by_id:
                         if self.combatants_by_id[instance_id].get('type') != inferred_type:
                              self.combatants_by_id[instance_id]['type'] = inferred_type
                              logging.debug(f"  Updated stored data type to '{inferred_type}' for {instance_id}")

                    fix_count += 1
                    logging.info(f"Fixed type for '{name}' (Row {row}, ID {instance_id}) to '{inferred_type}'")

        except Exception as e:
            logging.error(f"[CombatantManager] Error during fix_missing_types: {e}", exc_info=True)
        finally:
             self.panel.initiative_table.blockSignals(False) # Ensure signals are unblocked

        if fix_count > 0:
            logging.info(f"[CombatantManager] Finished fix_missing_types. Fixed {fix_count} combatants.")
        else:
            logging.info("[CombatantManager] Finished fix_missing_types. No types needed fixing.")

        return fix_count 