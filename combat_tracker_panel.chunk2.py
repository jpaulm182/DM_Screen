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

    def _add_initial_combat_state_to_log(self, combat_state):
        """Add initial combat state to the log at the start of combat"""
        # Clear any previous combat log content
        if hasattr(self, 'combat_log_text') and self.combat_log_text:
            # Check if we already have a "Combat Concluded" message
            current_text = self.combat_log_text.toHtml()
            if "Combat Concluded" in current_text:
                # Previous combat summary exists, clear it
                self.combat_log_text.clear()
            
        # Create summary HTML with better contrast colors
        html = "<h3 style='color: #000088;'>Initial Combat State</h3>"
        html += "<p style='color: #000000;'>Combatants in initiative order:</p>"
        html += "<ul style='color: #000000;'>"
        
        # Get combatants and build a summary
        combatants = combat_state.get("combatants", [])
        if not combatants:
            html += "<li>No combatants found</li>"
            html += "</ul>"
            html += "<p style='color: #000000;'><strong>Combat cannot begin with no combatants.</strong></p>"
            
            # Add to local log
            self.combat_log_text.append(html)
            
            # Force UI update
            from PySide6.QtWidgets import QApplication
            QApplication.processEvents()
            return
            
        # Sort by initiative
        try:
            sorted_combatants = sorted(combatants, key=lambda c: -c.get("initiative", 0))
        except Exception as e:
            print(f"[CombatTracker] Error sorting combatants: {e}")
            sorted_combatants = combatants
        
        for c in sorted_combatants:
            name = c.get("name", "Unknown")
            hp = c.get("hp", 0)
            max_hp = c.get("max_hp", hp)
            ac = c.get("ac", 10)
            initiative = c.get("initiative", 0)
            combatant_type = c.get("type", "unknown")
            
            # Different display for monsters vs characters with better styling
            if combatant_type.lower() == "monster":
                html += f"<li><strong style='color: #880000;'>{name}</strong> (Monster) - Initiative: {initiative}, AC: {ac}, HP: {hp}/{max_hp}</li>"
            else:
                html += f"<li><strong style='color: #000088;'>{name}</strong> (PC) - Initiative: {initiative}, AC: {ac}, HP: {hp}/{max_hp}</li>"
                
        html += "</ul>"
        html += "<p style='color: #000000;'><strong>Combat begins now!</strong></p>"
        html += "<hr style='border: 1px solid #000088;'>"
        
        # Add to the log
        self.combat_log_text.append(html)
        
        # Ensure cursor is at the end and scroll to the bottom
        cursor = self.combat_log_text.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.combat_log_text.setTextCursor(cursor)
        
        scrollbar = self.combat_log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        
        # Force UI update
        from PySide6.QtWidgets import QApplication
        QApplication.processEvents()

    def _create_live_combat_log(self):
        """Create a live combat log widget that displays during combat resolution"""
        try:
            from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QDialogButtonBox, QPushButton
            
            # Create the dialog
            self.combat_log_widget = QDialog(self)
            self.combat_log_widget.setWindowTitle("Combat In Progress")
            self.combat_log_widget.setWindowFlags(
                self.combat_log_widget.windowFlags() | Qt.Tool | Qt.WindowStaysOnTopHint
            )
            self.combat_log_widget.setMinimumSize(500, 500)
            
            # Create layout
            layout = QVBoxLayout(self.combat_log_widget)
            
            # Add text display for combat log with improved contrast
            self.combat_log_widget.log_text = QTextEdit()
            self.combat_log_widget.log_text.setReadOnly(True)
            self.combat_log_widget.log_text.setStyleSheet("""
                QTextEdit { 
                    background-color: white;
                    color: #000000;
                    font-family: Arial, sans-serif;
                    font-size: 14px;
                    font-weight: 500;
                }
            """)
            layout.addWidget(self.combat_log_widget.log_text)
            
            # Add header text
            header_text = "<h2 style='color: #000088;'>Combat In Progress</h2>"
            header_text += "<p style='color: #000000;'><strong>Watch as the battle unfolds turn by turn! Combat details will appear here and in popups.</strong></p>"
            header_text += "<hr style='border: 1px solid #000088;'>"
            self.combat_log_widget.log_text.setHtml(header_text)
            
            # Add a close button that just hides the dialog (combat continues)
            btn_box = QDialogButtonBox()
            close_btn = QPushButton("Hide Log")
            close_btn.clicked.connect(self.combat_log_widget.hide)
            btn_box.addButton(close_btn, QDialogButtonBox.ActionRole)
            layout.addWidget(btn_box)
            
            # Add create_entry method to make it compatible with the combat log interface
            def create_entry(category=None, actor=None, action=None, target=None, result=None, round=None, turn=None):
                # Create a simple entry representation
                entry = {
                    "category": category,
                    "actor": actor,
                    "action": action,
                    "target": target,
                    "result": result,
                    "round": round,
                    "turn": turn
                }
                # Format the entry into HTML
                html = f"<p><strong>{actor}:</strong> {action}"
                if target:
                    html += f" <strong>{target}</strong>"
                if result:
                    html += f" - {result}"
                html += "</p>"
                # Add it to the log text if possible
                if hasattr(self.combat_log_widget, 'log_text'):
                    self.combat_log_widget.log_text.append(html)
                return entry
                
            # Add the method to the widget
            self.combat_log_widget.create_entry = create_entry
            
        except Exception as e:
            print(f"[CombatTracker] Error creating live combat log: {e}")
            self.combat_log_widget = None

    @Slot(str, str, str, str, str)
    def _show_turn_result_slot(self, actor, round_num, action, result, dice_summary):
        """
        Show turn result from the main thread (safe way to show dialogs).
        This is connected to the show_turn_result_signal.
        """
        # Ensure we have content to display
        if not action and not result:
            print("[CombatTracker] Warning: Empty turn result, not showing dialog")
            return
            
        # Build message with available information
        message = ""
        if action:
            message += f"Action: {action}\n\n"
        if result:
            message += f"Result: {result}\n\n"
        if dice_summary:
            message += f"Dice Rolls:\n{dice_summary}"
            
        # Ensure the message is not empty
        if not message.strip():
            message = "No action taken this turn."
            
        # Use a non-modal dialog so it doesn't block the UI updates
        from PySide6.QtWidgets import QMessageBox
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle(f"Turn: {actor} (Round {round_num})")
        msg_box.setText(message)
        msg_box.setStandardButtons(QMessageBox.Ok)
        msg_box.setModal(False)  # Make it non-modal
        msg_box.show()

    def _show_turn_result(self, actor, round_num, action, result, dice_summary=None):
        """This method is no longer used directly - we use signals instead"""
        # Emit the signal to show the result from the main thread
        self.show_turn_result_signal.emit(actor, str(round_num), action, result, dice_summary or "")

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
    
    def _gather_combat_state(self):
        """Gather the current state of the combat from the table."""
        combatants = []
        
        print(f"\n[CombatTracker] DEBUG: Gathering combat state with current HP values from table:")
        
        for row in range(self.initiative_table.rowCount()):
            # Basic combatant data
            name_item = self.initiative_table.item(row, 0)
            initiative_item = self.initiative_table.item(row, 1)
            hp_item = self.initiative_table.item(row, 2)
            max_hp_item = self.initiative_table.item(row, 3)
            ac_item = self.initiative_table.item(row, 4)
            status_item = self.initiative_table.item(row, 5)
            conc_item = self.initiative_table.item(row, 6)
            type_item = self.initiative_table.item(row, 7)
            
            # Get values or defaults
            name = name_item.text() if name_item else "Unknown"
            initiative = int(initiative_item.text() or "0") if initiative_item else 0
            hp = int(hp_item.text() or "0") if hp_item else 0
            # Get max_hp from specific max_hp column
            max_hp = int(max_hp_item.text() or str(hp)) if max_hp_item else hp
            ac = int(ac_item.text() or "10") if ac_item else 10
            status = status_item.text() if status_item else ""
            concentration = conc_item.checkState() == Qt.Checked if conc_item else False
            combatant_type = type_item.text() if type_item else "unknown"
            
            # Get monster ID from name item if it's a monster
            # --- RENAME monster_id to instance_id for clarity and consistency --- 
            instance_id = None
            if name_item:
                # Get instance_id regardless of type (both monsters and characters need consistent IDs)
                instance_id = name_item.data(Qt.UserRole + 2)
                
                if not instance_id:
                    # Generate a unique ID if none exists
                    import time
                    import hashlib
                    timestamp = int(time.time())
                    hash_base = f"{name}_{timestamp}_{row}"
                    instance_id = hashlib.md5(hash_base.encode()).hexdigest()[:8]
                    # Store the ID back on the item for future reference
                    name_item.setData(Qt.UserRole + 2, instance_id)
                    print(f"[CombatTracker] Generated new instance ID {instance_id} for {name}")
                else:
                    print(f"[CombatTracker] Using existing instance ID {instance_id} for {name}")
            
            # Debug print current HP values
            print(f"[CombatTracker] DEBUG: Table row {row}: {name} - HP: {hp}/{max_hp} {' (ID: ' + str(instance_id) + ')' if instance_id else ''}")
            
            # Create combatant dictionary
            combatant = {
                "name": name,
                "initiative": initiative,
                "hp": hp,
                "max_hp": max_hp,
                "ac": ac,
                "status": status,
                "concentration": concentration,
                "type": combatant_type,
                "instance_id": instance_id if instance_id else f"combatant_{row}"  # Ensure every combatant has a unique ID
            }
            
            # Add more detailed information if available in the self.combatant_manager.combatants_by_id dictionary
            # --- Use instance_id for lookup, not row index --- 
            stored_combatant = None
            if instance_id and instance_id in self.combatant_manager.combatants_by_id: # USE CONSISTENT instance_id
                 stored_combatant = self.combatant_manager.combatants_by_id[instance_id] # USE CONSISTENT instance_id
                 logging.debug(f"Found stored data for instance ID {instance_id}")
            # REMOVED Fallback to row index lookup to strictly enforce ID matching
            # elif row in self.combatant_manager.combatants_by_id: 

            if stored_combatant:
                # ... (rest of the merging/tagging logic - ENSURE IT USES 'stored_combatant') ...
                # First, ensure the stored combatant has the same instance ID (sync it)
                if isinstance(stored_combatant, dict) and "instance_id" in combatant:
                    # Update the stored combatant's instance_id to match what's in the table
                    stored_combatant["instance_id"] = combatant["instance_id"]
                    
                # Add abilities if available
                if isinstance(stored_combatant, dict):
                    # Only include keys that are useful for combat resolution
                    for key in [
                        "abilities", "skills", "equipment", "features", "spells",
                        "special_traits", "traits", "actions", "legendary_actions",
                        "reactions", "on_death", "on_death_effects", "recharge_abilities",
                        "ability_recharges", "limited_use"
                    ]:
                        if key in stored_combatant:
                            # FIXED: Tag each ability with the monster instance ID to prevent mixing
                            if key in ["actions", "traits", "legendary_actions", "reactions"]:
                                # These are typically lists of dictionaries
                                tagged_abilities = []
                                original_abilities = stored_combatant[key]
                                
                                if isinstance(original_abilities, list):
                                    for ability in original_abilities:
                                        if isinstance(ability, dict):
                                            # Create a copy to avoid modifying the original
                                            ability_copy = ability.copy()
                                            # Add instance ID to the ability
                                            ability_copy["monster_instance_id"] = combatant["instance_id"]
                                            ability_copy["monster_name"] = name
                                            
                                            # Check for monster_source tag
                                            if "monster_source" not in ability_copy:
                                                ability_copy["monster_source"] = name
                                                
                                            tagged_abilities.append(ability_copy)
                                        else:
                                            # Non-dict abilities are simply passed through
                                            tagged_abilities.append(ability)
                                    
                                    # Store the tagged abilities
                                    combatant[key] = tagged_abilities
                                else:
                                    # If not a list, just store as is
                                    combatant[key] = original_abilities
                            elif key == "abilities":
                                # Handle abilities which are typically a dictionary of abilities
                                if isinstance(stored_combatant[key], dict):
                                    tagged_abilities = {}
                                    for ability_name, ability in stored_combatant[key].items():
                                        if isinstance(ability, dict):
                                            # Create a copy to avoid modifying the original
                                            ability_copy = ability.copy()
                                            # Add instance ID to the ability
                                            ability_copy["monster_instance_id"] = combatant["instance_id"]
                                            ability_copy["monster_name"] = name
                                            
                                            # Check for monster_source tag
                                            if "monster_source" not in ability_copy:
                                                ability_copy["monster_source"] = name
                                                
                                            tagged_abilities[ability_name] = ability_copy
                                        else:
                                            # Non-dict abilities are simply passed through
                                            tagged_abilities[ability_name] = ability
                                    
                                    # Store the tagged abilities
                                    combatant[key] = tagged_abilities
                                else:
                                    # If not a dict, just store as is
                                    combatant[key] = stored_combatant[key]
                            else:
                                # For other attributes, copy as is
                                combatant[key] = stored_combatant[key]
                    
                    # If monster and no existing limited_use, create basic recharge placeholders
                    if combatant_type == "monster" and "limited_use" not in combatant:
                        limited_use = {}

                        # Dragons breath weapon
                        if "dragon" in name.lower():
                            limited_use["Breath Weapon"] = "Available (Recharges on 5-6)"

                        if limited_use:
                            combatant["limited_use"] = limited_use
                
                # If it's an object, try to extract useful attributes
                elif hasattr(stored_combatant, "__dict__"):
                    for attr in [
                        "abilities", "skills", "equipment", "features", "spells",
                        "special_traits", "traits", "actions", "legendary_actions",
                        "reactions", "on_death", "on_death_effects", "recharge_abilities",
                        "ability_recharges", "limited_use"
                    ]:
                        if hasattr(stored_combatant, attr):
                            attr_value = getattr(stored_combatant, attr)
                            
                            # FIXED: Tag abilities with monster instance ID
                            if attr in ["actions", "traits", "legendary_actions", "reactions"]:
                                # These are typically lists of objects
                                if isinstance(attr_value, list):
                                    tagged_abilities = []
                                    
                                    for ability in attr_value:
                                        if isinstance(ability, dict):
                                            # Create a copy to avoid modifying the original
                                            ability_copy = ability.copy()
                                            # Add instance ID to the ability
                                            ability_copy["monster_instance_id"] = combatant["instance_id"]
                                            ability_copy["monster_name"] = name
                                            
                                            # Check for monster_source tag
                                            if "monster_source" not in ability_copy:
                                                ability_copy["monster_source"] = name
                                                
                                            tagged_abilities.append(ability_copy)
                                        else:
                                            # Create a dictionary from the object's attributes
                                            ability_dict = {}
                                            for ability_attr in dir(ability):
                                                if not ability_attr.startswith("_") and not callable(getattr(ability, ability_attr)):
                                                    ability_dict[ability_attr] = getattr(ability, ability_attr)
                                            
                                            # Add monster identifier
                                            ability_dict["monster_instance_id"] = combatant["instance_id"]
                                            ability_dict["monster_name"] = name
                                            ability_dict["monster_source"] = name
                                            
                                            tagged_abilities.append(ability_dict)
                                    
                                    # Store the tagged abilities
                                    combatant[attr] = tagged_abilities
                                else:
                                    # If not a list, just store as is
                                    combatant[attr] = attr_value
                            else:
                                # For other attributes, copy as is
                                combatant[attr] = attr_value
            
            combatants.append(combatant)
            
        # FIXED: Add a validation step to ensure no ability mixing
        self._validate_no_ability_mixing(combatants)
            
        return {
            "round": self.current_round,
            "current_turn_index": self.current_turn,
            "combatants": combatants
        }
        
    def _validate_no_ability_mixing(self, combatants):
        """
        Validate that no abilities are mixed between different monster instances.
        This is an additional safety check after the main preparation.
        """
        ability_sources = {}  # Maps ability names to their source monsters
        
        for combatant in combatants:
            combatant_id = combatant.get("instance_id", "unknown")
            combatant_name = combatant.get("name", "Unknown")
            
            # Check each ability-containing attribute
            for ability_type in ["actions", "traits", "legendary_actions", "reactions"]:
                abilities = combatant.get(ability_type, [])
                if not isinstance(abilities, list):
                    continue
                
                for i, ability in enumerate(abilities):
                    if not isinstance(ability, dict):
                        continue
                        
                    ability_name = ability.get("name", f"Unknown_{i}")
                    
                    # Make sure all abilities have the instance ID and source name
                    if "monster_instance_id" not in ability:
                        print(f"[CombatTracker] WARNING: Adding missing instance ID to {ability_name} for {combatant_name}")
                        ability["monster_instance_id"] = combatant_id
                        
                    if "monster_name" not in ability:
                        print(f"[CombatTracker] WARNING: Adding missing monster name to {ability_name} for {combatant_name}")
                        ability["monster_name"] = combatant_name
                        
                    if "monster_source" not in ability:
                        ability["monster_source"] = combatant_name
                    
                    # Track the ability source
                    source_key = f"{ability_name.lower()}"
                    if source_key in ability_sources:
                        # If the ability exists, make sure it comes from the right monster instance
                        previous_source = ability_sources[source_key]
                        if previous_source != combatant_id:
                            # This is a potential mixing situation - check if names match to confirm
                            prev_name = ability.get("monster_name", "Unknown")
                            if prev_name != combatant_name:
                                print(f"[CombatTracker] WARNING: Ability {ability_name} may be mixed between {prev_name} and {combatant_name}")
                                # Ensure this ability is clearly marked with its source for the resolver
                                ability["name"] = f"{combatant_name} {ability_name}"
                    else:
                        # Register this ability with its source
                        ability_sources[source_key] = combatant_id

    def _apply_combat_updates(self, updates):
        """Apply final combatant updates from the resolution result."""
        # Import necessary modules
        import time
        import gc
        from PySide6.QtWidgets import QApplication
        
        # Initialize rows_to_remove and update_summaries
        rows_to_remove = []
        update_summaries = []
        start_time = time.time()

        print(f"[CombatTracker] Applying {len(updates)} combat updates from LLM")
        
        # Ensure the update is a list
        if not isinstance(updates, list):
            print(f"[CombatTracker] Warning: updates is not a list (type: {type(updates)})")
            if isinstance(updates, dict):
                # Convert single dict to list containing one dict
                updates = [updates]
            else:
                # Return empty results for invalid updates
                return 0, ["No valid updates to apply"]
        
        # Skip if empty
        if not updates:
            return 0, ["No updates to apply"]

        # Block signals during updates to prevent unexpected handlers
        self.initiative_table.blockSignals(True)
        try:
            # Process updates with a timeout mechanism
            max_process_time = 5.0  # Max seconds to spend processing updates
            updates_processed = 0
            
            for update_index, update in enumerate(updates):
                # Check processing time limit
                elapsed = time.time() - start_time
                if elapsed > max_process_time:
                    print(f"[CombatTracker] Update processing time limit reached ({elapsed:.1f}s). Processed {updates_processed}/{len(updates)} updates.")
                    update_summaries.append(f"WARNING: Only processed {updates_processed}/{len(updates)} updates due to time limit.")
                    break
                
                # Process update in a try block to handle errors individually
                try:
                    name_to_find = update.get("name")
                    if not name_to_find:
                        continue

                    # Periodically update UI and force GC during long operations
                    if update_index > 0 and update_index % 5 == 0:
                        print(f"[CombatTracker] Processed {update_index}/{len(updates)} updates...")
                        self.initiative_table.blockSignals(False)
                        QApplication.processEvents()
                        self.initiative_table.blockSignals(True)
                        gc.collect()

                    print(f"[CombatTracker] Processing update for {name_to_find}")
                    # Find the row for the combatant
                    found_row = -1
                    for row in range(self.initiative_table.rowCount()):
                        name_item = self.initiative_table.item(row, 0)
                        if name_item and name_item.text() == name_to_find:
                            found_row = row
                            break

                    if found_row != -1:
                        print(f"[CombatTracker] Found {name_to_find} at row {found_row}")
                        # Apply HP update
                        if "hp" in update:
                            hp_item = self.initiative_table.item(found_row, 2)
                            if hp_item:
                                old_hp = hp_item.text()
                                try:
                                    # First try to convert directly to int
                                    if isinstance(update["hp"], int):
                                        new_hp_value = max(0, update["hp"])
                                    elif isinstance(update["hp"], str) and update["hp"].strip().isdigit():
                                        new_hp_value = max(0, int(update["hp"].strip()))
                                    else:
                                        # Handle other formats - extract numbers
                                        import re
                                        match = re.search(r'\d+', str(update["hp"]))
                                        if match:
                                            new_hp_value = max(0, int(match.group(0)))
                                        else:
                                            # If we can't extract a number, keep old HP
                                            print(f"[CombatTracker] Warning: Could not extract HP value from '{update['hp']}'")
                                            if old_hp and old_hp.isdigit():
                                                new_hp_value = int(old_hp)
                                            else:
                                                new_hp_value = 0
                                    
                                    new_hp = str(new_hp_value)
                                    hp_item.setText(new_hp)
                                    print(f"[CombatTracker] Set {name_to_find} HP to {new_hp} in row {found_row} (was {old_hp})")
                                    update_summaries.append(f"- {name_to_find}: HP changed from {old_hp} to {new_hp}")
                                    
                                    # Handle death/unconscious status if HP reaches 0
                                    if new_hp_value <= 0 and "status" not in update:
                                        # Add Unconscious status
                                        status_item = self.initiative_table.item(found_row, 5)  # Status is now column 5
                                        if status_item:
                                            current_statuses = []
                                            if status_item.text():
                                                current_statuses = [s.strip() for s in status_item.text().split(',')]
                                            
                                            # Only add if not already present
                                            if "Unconscious" not in current_statuses:
                                                current_statuses.append("Unconscious")
                                                status_item.setText(', '.join(current_statuses))
                                                update_summaries.append(f"- {name_to_find}: Added 'Unconscious' status due to 0 HP")
                                except Exception as e:
                                    print(f"[CombatTracker] Error processing HP update for {name_to_find}: {str(e)}")
                        # Apply Status update
                        if "status" in update:
                            status_item = self.initiative_table.item(found_row, 5)
                            if status_item:
                                old_status_text = status_item.text()
                                old_statuses = [s.strip() for s in old_status_text.split(',')] if old_status_text else []

                                new_status = update["status"]

                                # Handle different status update formats
                                if isinstance(new_status, list):
                                    # If status is a list, replace all existing statuses
                                    new_statuses = new_status
                                    status_item.setText(', '.join(new_statuses))
                                    update_summaries.append(f"- {name_to_find}: Status changed from '{old_status_text}' to '{', '.join(new_statuses)}'")
                                elif new_status == "clear":
                                    # Special case to clear all statuses
                                    status_item.setText("")
                                    update_summaries.append(f"- {name_to_find}: All statuses cleared (was '{old_status_text}')")
                                elif new_status.startswith("+"):
                                    # Add a status (e.g., "+Poisoned")
                                    status_to_add = new_status[1:].strip()
                                    if status_to_add and status_to_add not in old_statuses:
                                        old_statuses.append(status_to_add)
                                        status_item.setText(', '.join(old_statuses))
                                        update_summaries.append(f"- {name_to_find}: Added '{status_to_add}' status")
                                elif new_status.startswith("-"):
                                    # Remove a status (e.g., "-Poisoned")
                                    status_to_remove = new_status[1:].strip()
                                    if status_to_remove and status_to_remove in old_statuses:
                                        old_statuses.remove(status_to_remove)
                                        status_item.setText(', '.join(old_statuses))
                                        update_summaries.append(f"- {name_to_find}: Removed '{status_to_remove}' status")
                                else:
                                    # Otherwise, directly set the new status (backward compatibility)
                                    status_item.setText(new_status)
                                    update_summaries.append(f"- {name_to_find}: Status changed from '{old_status_text}' to '{new_status}'")

                                # If status contains "Dead" or "Fled", mark for removal
                                current_statuses = status_item.text().split(',')
                                if any(s.strip().lower() in ["dead", "fled"] for s in current_statuses): # Use lower() for case-insensitivity
                                    if found_row not in rows_to_remove: # Avoid duplicates
                                        rows_to_remove.append(found_row)
                                        
                    updates_processed += 1
                except Exception as update_error:
                    print(f"[CombatTracker] Error processing update for index {update_index}: {update_error}")
                    import traceback
                    traceback.print_exc()
                    update_summaries.append(f"ERROR: Failed to process update for index {update_index}")
                    continue  # Skip to next update
        finally:
            # Ensure signals are unblocked even if an error occurs
            self.initiative_table.blockSignals(False)
            
            # Force UI update after all individual updates
            QApplication.processEvents()

        # Process removal separately with a new timeout check
        start_removal_time = time.time()
        removal_time_limit = 3.0  # Limit time spent on removals
        
        # Remove combatants marked for removal (in reverse order)
        if rows_to_remove:
            # Block signals again during row removal for safety
            self.initiative_table.blockSignals(True)
            turn_adjusted = False # Track if current turn needs adjusting
            try:
                print(f"[CombatTracker] Removing {len(rows_to_remove)} combatants...")
                for i, row in enumerate(sorted(list(set(rows_to_remove)), reverse=True)): # Use set() to ensure unique rows
                    # Check timeout for removals
                    if time.time() - start_removal_time > removal_time_limit:
                        print(f"[CombatTracker] Removal time limit reached. Processed {i}/{len(rows_to_remove)} removals.")
                        update_summaries.append(f"WARNING: Only removed {i}/{len(rows_to_remove)} combatants due to time limit.")
                        break
                        
                    # Skip invalid rows
                    if row >= self.initiative_table.rowCount() or row < 0:
                        print(f"[CombatTracker] Skipping invalid row {row}")
                        continue
                        
                    print(f"[CombatTracker] Removing row {row}")
                    self.initiative_table.removeRow(row)
                    # Adjust current turn if needed
                    if row < self.current_turn:
                        self.current_turn -= 1
                        turn_adjusted = True
                    elif row == self.current_turn:
                        # If removing the current turn, reset it (e.g., to -1 or 0 if combatants remain)
                        self.current_turn = 0 if self.initiative_table.rowCount() > 0 else -1
                        turn_adjusted = True

                    # Clean up tracking
                    self.death_saves.pop(row, None)
                    self.concentrating.discard(row) # Use discard for sets
                    self.combatant_manager.combatants_by_id.pop(row, None) # Clean up combatants dict

                # Update highlight ONLY if turn was adjusted
                if turn_adjusted:
                     self._update_highlight()
            finally:
                 self.initiative_table.blockSignals(False) # Unblock after removals

        # Calculate elapsed time
        total_time = time.time() - start_time
        print(f"[CombatTracker] Combat updates applied in {total_time:.2f} seconds: {updates_processed} updates, {len(rows_to_remove)} removals")
        
        # Ensure the UI table is refreshed after all updates and removals
        self.initiative_table.viewport().update()
        QApplication.processEvents()

        # Force garbage collection
        gc.collect()

        # Return the initialized variables
        return len(rows_to_remove), update_summaries

    def _get_combat_log(self):
        """Get reference to the combat log panel for integration or create a local fallback"""
        # If we already have a valid combat log widget with create_entry method, return it
        if hasattr(self, 'combat_log_widget') and self.combat_log_widget:
            if hasattr(self.combat_log_widget, 'create_entry'):
                return self.combat_log_widget
            else:
                print("[CombatTracker] Warning: Cached combat_log_widget doesn't have create_entry method")
                # Clear the invalid reference - we'll try to create a fallback
                self.combat_log_widget = None
            
        # Try to get the combat log panel from panel_manager
        try:
            panel_manager = getattr(self.app_state, 'panel_manager', None)
            if panel_manager:
                combat_log_panel = panel_manager.get_panel("combat_log")
                if combat_log_panel:
                    print("[CombatTracker] Found combat_log panel, checking interface...")
                    
                    # Check if it has the expected create_entry method
                    if hasattr(combat_log_panel, 'create_entry'):
                        print("[CombatTracker] Combat log panel has required create_entry method")
                        self.combat_log_widget = combat_log_panel
                        return self.combat_log_widget
                    else:
                        print("[CombatTracker] Combat log panel doesn't have required interface, creating adapter...")
                        # Create an adapter that wraps the panel
                        try:
                            self._create_combat_log_adapter(combat_log_panel)
                            if hasattr(self.combat_log_widget, 'create_entry'):
                                return self.combat_log_widget
                        except Exception as e:
                            print(f"[CombatTracker] Error creating combat log adapter: {e}")
        except Exception as e:
            print(f"[CombatTracker] Error getting combat log panel: {e}")
        
        # Create a local fallback if needed
        if not hasattr(self, 'combat_log_widget') or not self.combat_log_widget:
            print("[CombatTracker] Creating local fallback combat log")
            self._create_fallback_combat_log()
            
        # Return whatever we have at this point (might still be None in worst case)
        return self.combat_log_widget
    
    def _create_combat_log_adapter(self, panel):
        """Create an adapter for the combat log panel to provide the create_entry method"""
        # Store the panel reference
        self.combat_log_widget = panel
        
        # Add the create_entry method to the panel
        def create_entry(category=None, actor=None, action=None, target=None, result=None, round=None, turn=None):
            try:
                # Create a simple entry representation
                entry = {
                    "category": category,
                    "actor": actor,
                    "action": action,
                    "target": target,
                    "result": result,
                    "round": round,
                    "turn": turn
                }
                
                # Format the entry into HTML
                html = "<p>"
                if round is not None:
                    html += f"<span style='color:#555555;'>[R{round}]</span> "
                html += f"<strong>{actor}:</strong> {action} "
                if target:
                    html += f"<strong>{target}</strong> "
                if result:
                    html += f"- {result}"
                html += "</p>"
                
                # Add to the log text if the panel has appropriate properties
                if hasattr(panel, 'log_text'):
                    panel.log_text.append(html)
                elif hasattr(panel, 'text'):
                    panel.text.append(html)
                elif hasattr(panel, 'append') and callable(panel.append):
                    panel.append(html)
                
                # Always update our local log as a backup
                if hasattr(self, 'combat_log_text') and self.combat_log_text:
                    self.combat_log_text.append(html)
                    
                return entry
            except Exception as e:
                print(f"[CombatTracker] Error in create_entry adapter: {e}")
                return {"error": str(e)}
                
        # Add the method to the panel
        setattr(self.combat_log_widget, 'create_entry', create_entry)
        
    def _create_fallback_combat_log(self):
        """Create a fallback combat log that stores entries for when external log isn't available"""
        try:
            # Create a simple object with the required interface
            from types import SimpleNamespace
            log = SimpleNamespace()
            
            # Add a list to store entries
            log.entries = []
            
            # Add the create_entry method
            def create_entry(category=None, actor=None, action=None, target=None, result=None, round=None, turn=None):
                # Create entry object
                entry = {
                    "category": category,
                    "actor": actor,
                    "action": action,
                    "target": target,
                    "result": result,
                    "round": round,
                    "turn": turn,
                    "timestamp": time.time()
                }
                
                # Store the entry
                log.entries.append(entry)
                
                # Format the entry and add to our local combat log text widget
                try:
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