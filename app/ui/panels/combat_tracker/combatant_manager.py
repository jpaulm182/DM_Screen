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

            # AC Item
            ac_str = str(ac) if ac is not None else "10"
            ac_item = QTableWidgetItem(ac_str)
            ac_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
            self.panel.initiative_table.setItem(new_row_index, 3, ac_item)

            # Type Item
            type_item = QTableWidgetItem(combatant_type)
            type_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
            self.panel.initiative_table.setItem(new_row_index, 4, type_item)

            # Status Item
            status_item = QTableWidgetItem("")
            status_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
            self.panel.initiative_table.setItem(new_row_index, 5, status_item)

            # Store additional data as user roles in the Name field
            # We can use this to track max HP, concentration, etc. even if not displayed
            name_item = self.panel.initiative_table.item(new_row_index, 0)
            if name_item:
                # Store max HP as user data role
                name_item.setData(Qt.UserRole + 3, max_hp)
                # Store concentration state
                name_item.setData(Qt.UserRole + 4, False)  # Default to not concentrating

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

    @Slot(list) # Can receive a list of monster dictionaries
    def add_monster_group(self, monster_list: list):
        """Add a list of monsters (as dictionaries) to the combat tracker.
        Args:
            monster_list (list): List of monster dictionaries or objects to add.
        """
        if not isinstance(monster_list, list):
            logging.error(f"[CombatantManager] Error: add_monster_group received non-list: {type(monster_list)}")
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

                # Process monster data to get key attributes
                hp = 10
                max_hp = 10
                ac = 10
                initiative = 10  # Default initiative if not found/rolled
                
                # Handle different input formats
                if isinstance(monster_data, dict):
                    monster_dict = monster_data
                    monster_name = monster_dict.get('name', monster_name)
                    
                    # Extract HP - handles "10 (3d6)" format or just number/dice string
                    import re
                    hp_string = str(monster_dict.get('hit_points', monster_dict.get('hp', '10')))
                    
                    # Try to parse average and roll dice
                    try:
                        # Extract average HP (number before parenthesis)
                        match_avg = re.match(r"\s*(\d+)", hp_string)
                        if match_avg:
                            max_hp = int(match_avg.group(1))
                        
                        # Extract dice formula (inside parenthesis)
                        formula_match = re.search(r"\((.*?)\)", hp_string)
                        if formula_match:
                            formula = formula_match.group(1).replace(" ", "")  # Remove spaces
                            # Roll for current HP using the formula if available
                            if hasattr(self.panel, 'roll_dice'):
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

                    # Extract AC
                    ac = monster_dict.get('ac', monster_dict.get('armor_class', 10))
                    if not isinstance(ac, int):
                        try:
                            ac = int(ac)  # Handle AC potentially being a string
                        except (ValueError, TypeError):
                            ac = 10  # Default AC if conversion fails
                    
                    # Extract Initiative Modifier (Dexterity)
                    import random
                    dex = monster_dict.get('dex', monster_dict.get('dexterity', 10))
                    if not isinstance(dex, int):
                        try:
                            dex = int(dex)
                        except (ValueError, TypeError):
                            dex = 10
                    init_mod = (dex - 10) // 2
                    initiative = random.randint(1, 20) + init_mod
                    
                # Use the parsed/validated values to add the combatant
                row = self.add_combatant(
                    name=monster_name,
                    initiative=initiative,
                    hp=hp,
                    max_hp=max_hp,
                    ac=ac,
                    combatant_type="monster",
                    monster_data=monster_data  # Pass the full dictionary
                )

                if row >= 0:
                    added_count += 1
                    rows_added.append(row)
                    # Log action via panel
                    try:
                        self.panel._log_combat_action("Setup", "DM", "added monster", monster_name, f"(Rolled Initiative: {initiative})")
                    except Exception as log_err:
                        print(f"[CombatantManager] Error logging combat action: {log_err}")
                else:
                    failed_count += 1
                    logging.error(f"[CombatantManager] Failed to add monster '{monster_name}' from group.")
            except Exception as e:
                failed_count += 1
                name = "Unknown"
                if isinstance(monster_data, dict): 
                    name = monster_data.get("name", "Unknown")
                elif hasattr(monster_data, 'name'): 
                    name = getattr(monster_data, 'name', "Unknown")
                logging.error(f"[CombatantManager] Error adding monster '{name}' from group: {e}", exc_info=True)

        if added_count > 0:
            logging.info(f"[CombatantManager] Added {added_count} monsters from group (failed: {failed_count}).")
            # Sort initiative after adding the whole group
            self.panel._sort_initiative()
        else:
            logging.warning(f"[CombatantManager] No monsters were added from the group (all {failed_count} failed).")
            
    # This slot receives signals from the MonsterPanel or other sources
    @Slot(list) 
    def add_combatant_group(self, monster_list: list):
        """Delegates to add_monster_group for backward compatibility"""
        try:
            print(f"[CombatantManager] add_combatant_group called with {len(monster_list) if isinstance(monster_list, list) else 'non-list'} item(s)")
            
            # Error checking - ensure we have a proper list
            if not isinstance(monster_list, list):
                logging.error(f"[CombatantManager] add_combatant_group expected list but got {type(monster_list)}")
                return
                
            # Process the first level of list if necessary (handle nested lists)
            # This handles the case where monster_list is actually [[monster_dict]] instead of [monster_dict]
            if len(monster_list) == 1 and isinstance(monster_list[0], list):
                monster_list = monster_list[0]
                print(f"[CombatantManager] Unwrapped nested list, now processing {len(monster_list)} items")
                
            return self.add_monster_group(monster_list)
        except Exception as e:
            logging.error(f"[CombatantManager] Error in add_combatant_group: {e}", exc_info=True)
            return