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

            # Retrieve and save the detailed combatant data stored in self.combatant_manager.combatants_by_id dictionary
            if row in self.combatant_manager.combatants_by_id:
                # Store the associated data object/dictionary
                # Note: Ensure this data is serializable (e.g., dict, list, primitives)
                # If it's a complex object, you might need a custom serialization method
                combatant_state["data"] = self.combatant_manager.combatants_by_id[row] 
            
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
            self.combatant_manager.combatants_by_id.clear()             # Clear stored combatant data
            
            # --- Restore Basic Combat Info ---
            self.current_round = state.get("round", 1)
            self.round_spin.setValue(self.current_round) # Update UI spinner
            
            # Restore current turn, ensuring it's within bounds of restored combatants later
            self._current_turn = state.get("turn", 0) 
            
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
                    self.combatant_manager.combatants_by_id[row] = combatant_state["data"]
                    # If it's a monster, try to assign a unique ID
                    if combatant_state.get("type") == "monster":
                         # Create a unique ID for this monster instance
                         monster_id = self.combatant_manager.monster_id_counter
                         self.combatant_manager.monster_id_counter += 1
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
            if self._current_turn >= self.initiative_table.rowCount():
                self._current_turn = 0 if self.initiative_table.rowCount() > 0 else -1
            
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
