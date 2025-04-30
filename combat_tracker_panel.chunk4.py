                
                # Update the max_hp in the combatant data if it's a dictionary
                if isinstance(self.combatant_manager.combatants_by_id[row], dict):
                    self.combatant_manager.combatants_by_id[row]['max_hp'] = max_hp
                elif hasattr(self.combatant_manager.combatants_by_id[row], 'max_hp'):
                    self.combatant_manager.combatants_by_id[row].max_hp = max_hp
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
            if isinstance(self.combatant_manager.combatants_by_id[row], dict):
                if 'conditions' not in self.combatant_manager.combatants_by_id[row]:
                    self.combatant_manager.combatants_by_id[row]['conditions'] = []
                self.combatant_manager.combatants_by_id[row]['conditions'] = statuses
            elif hasattr(self.combatant_manager.combatants_by_id[row], 'conditions'):
                self.combatant_manager.combatants_by_id[row].conditions = statuses
    
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

            def _prompt_saving_throw(self):
                """Prompt user for saving throw details and apply to selected combatants."""
                # Get selected rows first
                selected_rows = sorted(list(set(index.row() for index in self.initiative_table.selectedIndexes())))

                if not selected_rows:
                    QMessageBox.warning(self, "Selection Error", "Please select one or more combatants to apply the saving throw.")
                    return

        # 1. Prompt for Ability
        ability_name, ok1 = QInputDialog.getItem(self, "Select Saving Throw Ability",
                                                 "Ability:", ABILITIES, 0, False)
        if not ok1 or not ability_name:
            return # User cancelled

        # 2. Prompt for DC
        dc, ok2 = QInputDialog.getInt(self, "Enter Saving Throw DC",
                                      "DC:", 10, 1, 30, 1)
        if not ok2:
            return # User cancelled

        # 3. Process each selected combatant
        for row in selected_rows:
            name_item = self.initiative_table.item(row, 0)
            if not name_item:
                continue
            combatant_name = name_item.text()

            combatant_data = self.combatant_manager.get_combatant_data(row)
            save_bonus = self._get_save_bonus(combatant_data, ability_name)

            # Show the dialog for this combatant
            dialog = SavingThrowDialog(combatant_name, ability_name, save_bonus, dc, self)

            if dialog.exec_(): # User confirmed roll in the dialog
                roll = dialog.final_roll
                total_save = roll + save_bonus # Recalculate total for logging clarity
                succeeded = dialog.succeeded # Use the outcome stored by the dialog

                outcome_text = "succeeded on" if succeeded else "failed"
                # Log the action
                self._log_combat_action(
                    "Saving Throw", # New category
                    combatant_name,
                    f"{outcome_text} DC {dc} {ability_name} save", # Describe action
                    target=None, # Save is against an effect/DC
                    result=f"(Rolled {roll}, Total: {total_save})" # Show roll and total
                )
                # Future: Apply effects based on failure (e.g., status condition)
                # if not succeeded:
                #     # Example: apply 'Burning' status on failed DEX save vs Fire Breath
                #     if ability_name == "Dexterity" and dc > 10: # Simplistic check
                #          self._add_status("Burning", row=row) # Need _add_status to accept row

            else: # User cancelled the roll dialog for this specific combatant
                 self._log_combat_action(
                    "Saving Throw",
                    combatant_name,
                    f"DC {dc} {ability_name} save cancelled",
                    target=None, result=None
                 )
                 # Loop continues to the next selected combatant


        def _check_concentration(self, row, damage):
            """Check if a combatant needs to make a concentration save, get bonus, and log correctly."""
            # Check if the combatant in this row is actually concentrating
            concentration_item = self.initiative_table.item(row, 6) # Concentration is column 6
            if not concentration_item or concentration_item.checkState() != Qt.Checked:
                # Also check our internal tracking set, though the checkbox should be the source of truth
                if row not in self.concentrating:
                 return # Not concentrating, no check needed

        # Get combatant name
        name_item = self.initiative_table.item(row, 0)
        if not name_item:
            return
        combatant_name = name_item.text()

        # --- Get Combatant Data to find CON Save Bonus ---
        combatant_data = self.combatant_manager.get_combatant_data(row)
        con_save_bonus = 0 # Default bonus
        if combatant_data:
            # Try to get Constitution score and calculate modifier
            con_score_str = get_attr(combatant_data, 'constitution', None)
            if con_score_str is not None:
                try:
                    con_score = int(con_score_str)
                    con_save_bonus = (con_score - 10) // 2
                    # TODO: Add proficiency bonus if proficient in CON saves?
                    # Need proficiency bonus and save proficiencies from combatant_data
                except (ValueError, TypeError):
                    print(f"[CombatTracker] Warning: Could not parse CON score '{con_score_str}' for {combatant_name}")
            else:
                 # Maybe the bonus is stored directly? (Less likely based on SRD format)
                 con_save_bonus_str = get_attr(combatant_data, 'constitution_save', '0')
                 try:
                      con_save_bonus = int(con_save_bonus_str)
                 except (ValueError, TypeError):
                      print(f"[CombatTracker] Warning: Could not parse CON save bonus '{con_save_bonus_str}' for {combatant_name}")

        # Calculate DC for concentration check
        dc = max(10, damage // 2)

        # --- Corrected call to ConcentrationDialog ---
        # Pass combatant_name, con_save_bonus, damage
        dialog = ConcentrationDialog(combatant_name, con_save_bonus, damage, self)

        if dialog.exec_():
            # --- Retrieve roll using the new final_roll attribute ---
            save_roll = dialog.final_roll
            total_save = save_roll + con_save_bonus # Calculate total here
            passed = total_save >= dc

            # Log result of concentration check using the correct roll
            outcome = "passed" if passed else "failed"
            self._log_combat_action(
                "Concentration Check",
                combatant_name,
                f"{outcome} DC {dc} concentration check", # Put DC in action text
                target=None, # No target for a self-save
                result=f"(Rolled {save_roll}, Total: {total_save})" # Show roll and total
            )

            # If failed, update concentration state and log
            if not passed:
                if concentration_item:
                    concentration_item.setCheckState(Qt.Unchecked)

                # Update internal tracking set
                if row in self.concentrating:
                    self.concentrating.remove(row)

                # Log concentration broken
                self._log_combat_action(
                    "Effect Ended",
                    combatant_name,
                    "lost concentration",
                    target=None, result=None
                )
        else:
             # User cancelled the dialog
             self._log_combat_action(
                  "Concentration Check",
                  combatant_name,
                  f"DC {dc} concentration check cancelled",
                  target=None, result=None
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
                self.combatant_manager.combatants_by_id.pop(row, None) # Clean up combatants dict
                
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
            original_indices = sorted(self.combatant_manager.combatants_by_id.keys()) # Get keys before modifying
            
            current_new_row = 0
            for old_row in range(max(original_indices) + 1): # Iterate through potential old indices
                if old_row not in rows_to_remove and old_row in original_indices:
                    old_to_new_map[old_row] = current_new_row
                    current_new_row += 1

            # Apply the mapping
            for old_row, new_row in old_to_new_map.items():
                if old_row in self.combatant_manager.combatants_by_id:
                    new_combatants[new_row] = self.combatant_manager.combatants_by_id[old_row]
                if old_row in self.concentrating:
                    new_concentrating.add(new_row)
                if old_row in self.death_saves:
                    new_death_saves[new_row] = self.death_saves[old_row]
                     
            self.combatant_manager.combatants_by_id = new_combatants
            self.concentrating = new_concentrating
            self.death_saves = new_death_saves
            print(f"[CombatTracker] Cleanup: Re-indexing complete. New combatants dict size: {len(self.combatant_manager.combatants_by_id)}")
            
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
        
        def _get_save_bonus(self, combatant_data, ability_name):
            """Calculate the saving throw bonus for a given ability."""
            if not combatant_data or not ability_name:
                return 0

            ability_lower = ability_name.lower()
            bonus = 0

        # 1. Check for explicit save bonus (e.g., "dexterity_save")
        save_key = f"{ability_lower}_save"
        if save_key in combatant_data:
            try:
                # Use get_attr for safe retrieval
                bonus = int(get_attr(combatant_data, save_key, '0'))
                # print(f"[DEBUG] Found explicit save bonus {save_key}: {bonus}") # Optional Debug
                return bonus
            except (ValueError, TypeError):
                 print(f"[CombatTracker] Warning: Could not parse explicit save bonus '{save_key}' for {combatant_data.get('name', 'Unknown')}")

        # 2. If no explicit bonus, calculate from ability score
        score_key = ability_lower
        if score_key in combatant_data:
             # Use get_attr for safe retrieval
             score_str = get_attr(combatant_data, score_key, None)
             if score_str is not None:
                 try:
                     score = int(score_str)
                     bonus = (score - 10) // 2
                     # print(f"[DEBUG] Calculated save bonus from {score_key}={score}: {bonus}") # Optional Debug
                 except (ValueError, TypeError):
                     print(f"[CombatTracker] Warning: Could not parse ability score '{score_key}' for {combatant_data.get('name', 'Unknown')}")
             else:
                 # Log if the key exists but the value is None or empty
                 print(f"[CombatTracker] Warning: Ability score key '{score_key}' present but value is None/empty for {combatant_data.get('name', 'Unknown')}")
        else:
             # Log if the ability score key itself is missing
             print(f"[CombatTracker] Warning: Ability score key '{score_key}' not found for {combatant_data.get('name', 'Unknown')}")


        # TODO: Add proficiency bonus if proficient? Requires proficiency data.
        # This depends heavily on how proficiency information is stored in combatant_data
        # prof_bonus = get_attr(combatant_data, 'proficiency_bonus', 0)
        # save_proficiencies = get_attr(combatant_data, 'proficiencies', []) # Example structure
        # is_proficient = any(p.get('proficiency', {}).get('name', '') == f"Saving Throw: {ability_name}" for p in save_proficiencies)
        # if is_proficient:
        #     try:
        #          bonus += int(prof_bonus)
        #          print(f"[DEBUG] Added proficiency bonus {prof_bonus}, total {bonus}")
        #     except (ValueError, TypeError):
        #          print(f"[CombatTracker] Warning: Could not parse proficiency bonus '{prof_bonus}'")

        return bonus

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

        # Try to get more detailed data from the stored self.combatant_manager.combatants_by_id dictionary
        if row in self.combatant_manager.combatants_by_id:
            stored_data = self.combatant_manager.combatants_by_id[row]
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
             print(f"[Combat Tracker] No stored data found in self.combatant_manager.combatants_by_id for row {row}. Using table data only.")

        # Create and execute the details dialog
        print(f"[Combat Tracker] Final data for dialog: {combatant_data}")
            # --- Add this line ---
        print(f"[DEBUG] Data being passed to CombatantDetailsDialog:\n{combatant_data}\n")
        # --- End of added line ---
        dialog = CombatantDetailsDialog(combatant_data=combatant_data, combatant_type=combatant_type, parent=self)
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
        if row in self.combatant_manager.combatants_by_id:
             self.current_details_combatant = self.combatant_manager.combatants_by_id[row]
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
                if row in self.combatant_manager.combatants_by_id:
                    data = self.combatant_manager.combatants_by_id[row]
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
        
            # Always append full summary, keeping prior log intact
            self.combat_log_text.append("<hr><h3 style='color:#000088;'>Combat Concluded</h3>")
            self.combat_log_text.append(summary_content)
            
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
