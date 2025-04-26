# Helpers for CombatTrackerPanel (_update_)

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
            status = status_item.text()
            
            # Update the status in the combatant data if it's a dictionary
            if isinstance(self.combatant_manager.combatants_by_id[row], dict):
                if 'conditions' not in self.combatant_manager.combatants_by_id[row]:
                    self.combatant_manager.combatants_by_id[row]['conditions'] = []
                if status and status not in self.combatant_manager.combatants_by_id[row]['conditions']:
                    self.combatant_manager.combatants_by_id[row]['conditions'].append(status)
                elif not status and self.combatant_manager.combatants_by_id[row]['conditions']:
                    self.combatant_manager.combatants_by_id[row]['conditions'] = []
            elif hasattr(self.combatant_manager.combatants_by_id[row], 'conditions'):
                pass

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

    def _update_timer(self):
        """Update the combat timer display"""
        self.combat_time += 1
        hours = self.combat_time // 3600
        minutes = (self.combat_time % 3600) // 60
        seconds = self.combat_time % 60
        self.timer_label.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}")

    def _update_game_time(self):
        """Update the in-game time display"""
        # In D&D 5e, a round is 6 seconds
        total_seconds = (self.current_round - 1) * 6
        minutes = total_seconds // 60
        self.game_time_label.setText(
            f"{self.current_round - 1} rounds ({minutes} minutes)"
        )

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
            self._current_turn = current_idx
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
                                
                                # Also update self.combatant_manager.combatants_by_id dictionary if this row is in it
                                if row in self.combatant_manager.combatants_by_id and isinstance(self.combatant_manager.combatants_by_id[row], dict):
                                    self.combatant_manager.combatants_by_id[row]['current_hp'] = new_hp
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

