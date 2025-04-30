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

        # Removed obsolete block referencing monster_dicts, which was undefined and not used in this method.
        # This prevents NameError and clarifies the restore_state logic.
        # ... existing code ...

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
            monster_id = self.combatant_manager.monster_id_counter
            self.combatant_manager.monster_id_counter += 1
            
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
            row = self.combatant_manager.add_combatant(name, initiative_roll, hp, max_hp, ac, "monster", monster_id)
            
            # Ensure row is valid, default to -1 if None
            if row is None:
                row = -1
            
            # Store monster data for future reference
            if row >= 0:
                self.combatant_manager.combatants_by_id[row] = monster_data
                
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
            
            # NEW: Update the self.combatant_manager.combatants_by_id dictionary to keep instance IDs aligned
            if hasattr(self, 'combatants') and isinstance(self.combatant_manager.combatants_by_id, dict):
                new_combatants = {}
                for old_row, combatant_data in self.combatant_manager.combatants_by_id.items():
                    if old_row in row_map:
                        new_row = row_map[old_row]
                        new_combatants[new_row] = combatant_data
                        
                        # If combatant_data is a dictionary, update its instance_id
                        if isinstance(combatant_data, dict):
                            instance_id = monster_instance_ids.get(old_row, f"combatant_{old_row}")
                            combatant_data['instance_id'] = instance_id
                            print(f"[CombatTracker] Updated instance_id in combatants dict: {old_row} -> {new_row} with ID {instance_id}")
                
                self.combatant_manager.combatants_by_id = new_combatants
            
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
        if row not in self.combatant_manager.combatants_by_id:
            return
            
        # Get HP from table
        hp_item = self.initiative_table.item(row, 2)  # Current HP
        max_hp_item = self.initiative_table.item(row, 3)  # Max HP
        
        if hp_item:
            hp_text = hp_item.text().strip()
            try:
                hp = int(hp_text) if hp_text else 0
                
                # Update the hp in the combatant data if it's a dictionary
                if isinstance(self.combatant_manager.combatants_by_id[row], dict):
                    self.combatant_manager.combatants_by_id[row]['current_hp'] = hp
                elif hasattr(self.combatant_manager.combatants_by_id[row], 'current_hp'):
                    self.combatant_manager.combatants_by_id[row].current_hp = hp
            except (ValueError, TypeError):
                # Ignore if not a valid number
                pass
        
        # Update max HP if available
        if max_hp_item:
            max_hp_text = max_hp_item.text().strip()
            try:
                max_hp = int(max_hp_text) if max_hp_text else 0
                
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