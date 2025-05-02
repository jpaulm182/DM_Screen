            if column == 1:
                try:
                    # Validate the initiative value
                    int(item.text()) # Try converting to int
                    if self.initiative_table.rowCount() > 1:
                        self._sort_initiative()
                except (ValueError, TypeError):
                    item.setText("0") # Reset invalid input

            # Handle Max HP changes (column 3) without sorting
            elif column == 3:
                hp_item = self.initiative_table.item(row, 2)
                max_hp_item = self.initiative_table.item(row, 3)
                if hp_item and max_hp_item:
                    try:
                        current_hp = int(hp_item.text())
                        max_hp = int(max_hp_item.text())
                        if current_hp > max_hp:
                            hp_item.setText(str(max_hp))
                    except (ValueError, TypeError):
                        pass # Ignore if values aren't integers

            # Update combatant data dictionary if it exists
            if row in self.combatant_manager.combatants_by_id:
                self._update_combatant_hp_and_status(row)
        
        finally:
            self.initiative_table.blockSignals(False)
    
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
    
    def _next_turn(self):
        """Move to the next combatant's turn"""
        if self.initiative_table.rowCount() == 0:
            return
        
        # Set combat as started when first advancing turns
        if not self.combat_started:
            self.combat_started = True
        
        # Store the index of the last combatant
        last_combatant_index = self.initiative_table.rowCount() - 1
        
        # Check if the current turn is the last combatant
        if self.current_turn == last_combatant_index:
            # End of the round: Increment round, reset turn to 0
            self.current_turn = 0
            self.current_round += 1
            self.round_spin.setValue(self.current_round)
            self._update_game_time()
            print(f"--- End of Round {self.current_round - 1}, Starting Round {self.current_round} ---") # Debug
        else:
            # Not the end of the round: Just advance to the next combatant
            self.current_turn += 1
        
        # Highlight the new current combatant
        self._update_highlight()
        
        # Log the turn change
        if self.initiative_table.rowCount() > 0 and self.current_turn < self.initiative_table.rowCount():
            combatant_name = self.initiative_table.item(self.current_turn, 0).text()
            self._log_combat_action("Initiative", combatant_name, "started their turn")
            
        # If this is the first turn of a new round, log the round start
        if self.current_turn == 0:
            self._log_combat_action("Initiative", f"Round {self.current_round}", "started")
    
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
    
    def _show_context_menu(self, position):
        """Show custom context menu for the initiative table"""
        # Get row under cursor
        row = self.initiative_table.rowAt(position.y())
        if row < 0:
            return
        
        # --- Ensure row selection before menu pops ---
        # If the right‑clicked row is not already selected, clear any previous
        # selection (to avoid unintended multi‑row edits) and select this row.
        if row not in [idx.row() for idx in self.initiative_table.selectionModel().selectedRows()]:
            self.initiative_table.clearSelection()
            self.initiative_table.selectRow(row)

        # Create menu
        menu = QMenu(self)
        
        # Add menu actions
        remove_action = QAction("Remove", self)
        remove_action.triggered.connect(self._remove_selected)
        menu.addAction(remove_action)
        
        # View details action
        view_details_action = QAction("View Details", self)
        view_details_action.triggered.connect(lambda: self._view_combatant_details(row))
        menu.addAction(view_details_action)
        
                # --- Add this new block ---
        # Show tracker data action (opens the dialog directly)
        show_tracker_data_action = QAction("Show Tracker Data", self)
        # Need combatant name and type for _show_combatant_dialog
        name_item = self.initiative_table.item(row, 0)
        combatant_name = name_item.text() if name_item else "Unknown"
        combatant_type = name_item.data(Qt.UserRole) # Get type stored in name item
        if not combatant_type: # Infer if not stored
             type_item = self.initiative_table.item(row, 7) 
             combatant_type = type_item.text().lower() if type_item else "custom"
        
        # Connect to _show_combatant_dialog, passing required args
        show_tracker_data_action.triggered.connect(
            lambda checked=False, r=row, n=combatant_name, t=combatant_type: self._show_combatant_dialog(r, n, t)
        )
        menu.addAction(show_tracker_data_action)
        # --- End of new block ---

        # --- Existing code continues below (Damage, Heal, etc.) ---
        menu.addSeparator()

        # View combatant details action
        view_details_action = QAction("View Details", self)
        view_details_action.triggered.connect(lambda: self._view_combatant_details(row))
        menu.addAction(view_details_action)
        
        # Toggle details panel action
        toggle_details_action = QAction("Hide Details Panel" if self.show_details_pane else "Show Details Panel", self)
        toggle_details_action.triggered.connect(self._toggle_details_pane)
        menu.addAction(toggle_details_action)
        menu.addSeparator()
        
        # HP adjustment submenu
        hp_menu = menu.addMenu("Adjust HP")
        
        # Quick damage options
        damage_menu = hp_menu.addMenu("Damage")
        d1_action = damage_menu.addAction("1 HP")
        d1_action.triggered.connect(lambda: self._quick_damage(1))
        d5_action = damage_menu.addAction("5 HP")
        d5_action.triggered.connect(lambda: self._quick_damage(5))
        d10_action = damage_menu.addAction("10 HP")
        d10_action.triggered.connect(lambda: self._quick_damage(10))
        
        damage_custom = damage_menu.addAction("Custom...")
        damage_custom.triggered.connect(lambda: self._apply_damage(False))
        
        # Quick healing options
        heal_menu = hp_menu.addMenu("Heal")
        h1_action = heal_menu.addAction("1 HP")
        h1_action.triggered.connect(lambda: self._quick_heal(1))
        h5_action = heal_menu.addAction("5 HP")
        h5_action.triggered.connect(lambda: self._quick_heal(5))
        h10_action = heal_menu.addAction("10 HP")
        h10_action.triggered.connect(lambda: self._quick_heal(10))
        
        heal_custom = heal_menu.addAction("Custom...")
        heal_custom.triggered.connect(lambda: self._apply_damage(True))
        
        menu.addSeparator()
        
        # Death saves - check for 0 HP safely
        hp_item = self.initiative_table.item(row, 2)  # HP is now column 2
        hp_value = 0
        if hp_item:
            try:
                hp_text = hp_item.text().strip()
                if hp_text:  # Only try to convert if not empty
                    hp_value = int(hp_text)
            except ValueError:
                hp_value = 0  # Default to 0 if conversion fails
        
        if hp_value <= 0:
            death_saves = QAction("Death Saves...", self)
            death_saves.triggered.connect(lambda: self._manage_death_saves(row))
            menu.addAction(death_saves)
            menu.addSeparator()
        
        save_action = QAction("Make Saving Throw...", self)
        save_action.triggered.connect(self._prompt_saving_throw) # Connect to new handler
        menu.addAction(save_action)
        menu.addSeparator() # Optional separator after
    
        # Status submenu - Changed to Add Status and Remove Status
        status_menu = menu.addMenu("Add Status")
        status_menu.addAction("Clear All").triggered.connect(lambda: self._clear_statuses())
        
        for condition in CONDITIONS:
            action = status_menu.addAction(condition)
            action.triggered.connect(lambda checked, c=condition: self._add_status(c))
        
        # Get current statuses for the Remove Status menu
        status_item = self.initiative_table.item(row, 5)  # Status is now column 5
        current_statuses = []
        if status_item and status_item.text():
            current_statuses = [s.strip() for s in status_item.text().split(',')]
            
        # Only show Remove Status menu if there are statuses to remove
        if current_statuses:
            remove_status_menu = menu.addMenu("Remove Status")
            for status in current_statuses:
                action = remove_status_menu.addAction(status)
                action.triggered.connect(lambda checked, s=status: self._remove_status(s))
        
        # Concentration toggle
        conc_item = self.initiative_table.item(row, 6)  # Concentration is now column 6
        if conc_item:
            is_concentrating = conc_item.checkState() == Qt.Checked
            conc_action = QAction("Remove Concentration" if is_concentrating else "Add Concentration", self)
            conc_action.triggered.connect(lambda: self._toggle_concentration(row))
            menu.addAction(conc_action)
        
        # Show the menu
        menu.exec_(self.initiative_table.mapToGlobal(position))
        
    def _add_status(self, status):
        """Add a status condition to selected combatants without removing existing ones"""
        # Get selected rows
        selected_rows = set(index.row() for index in self.initiative_table.selectedIndexes())
        if not selected_rows:
            return
        
        # Apply status to each selected row
        for row in selected_rows:
            if row < self.initiative_table.rowCount():
                status_item = self.initiative_table.item(row, 5)  # Status is now column 5
                if status_item:
                    current_statuses = []
                    if status_item.text():
                        current_statuses = [s.strip() for s in status_item.text().split(',')]
                    
                    # Only add if not already present
                    if status not in current_statuses:
                        current_statuses.append(status)
                        status_item.setText(', '.join(current_statuses))
                
                # Log status change if there's a name
                name_item = self.initiative_table.item(row, 0)
                if name_item:
                    name = name_item.text()
                    
                    # Log status change
                    self._log_combat_action(
                        "Status Effect", 
                        "DM", 
                        "applied status", 
                        name, 
                        status
                    )
    
    def _remove_status(self, status):
        """Remove a specific status condition from selected combatants"""
        # Get selected rows
        selected_rows = set(index.row() for index in self.initiative_table.selectedIndexes())
        if not selected_rows:
            return
        
        # Remove status from each selected row
        for row in selected_rows:
            if row < self.initiative_table.rowCount():
                status_item = self.initiative_table.item(row, 5)  # Status is now column 5
                if status_item and status_item.text():
                    current_statuses = [s.strip() for s in status_item.text().split(',')]
                    
                    # Remove the status if present
                    if status in current_statuses:
                        current_statuses.remove(status)
                        status_item.setText(', '.join(current_statuses))
                
                # Log status removal if there's a name
                name_item = self.initiative_table.item(row, 0)
                if name_item:
                    name = name_item.text()
                    
                    # Log status removal
                    self._log_combat_action(
                        "Status Effect", 
                        "DM", 
                        "removed status", 
                        name, 
                        status
                    )
    
    def _clear_statuses(self):
        """Clear all status conditions from selected combatants"""
        # Get selected rows
        selected_rows = set(index.row() for index in self.initiative_table.selectedIndexes())
        if not selected_rows:
            return
        
        # Clear statuses for each selected row
        for row in selected_rows:
            if row < self.initiative_table.rowCount():
                status_item = self.initiative_table.item(row, 5)  # Status is now column 5
                if status_item:
                    status_item.setText("")
                
                # Log status clearing if there's a name
                name_item = self.initiative_table.item(row, 0)
                if name_item:
                    name = name_item.text()
                    
                    # Log status clearing
                    self._log_combat_action(
                        "Status Effect", 
                        "DM", 
                        "cleared all statuses from", 
                        name
                    )
    
    # Keep _set_status for backwards compatibility but modify it to call _add_status
    def _set_status(self, status):
        """Apply a status condition to selected combatants (legacy method)"""
        if not status:
            # If empty status, clear all
            self._clear_statuses()
        else:
            # Otherwise add the status
            self._add_status(status)
    
    def _round_changed(self, value):
        """Handle round number change"""
        self.current_round = value
        self._update_game_time()
    
    def _toggle_timer(self):
        """Toggle the combat timer"""
        if self.timer.isActive():
            self.timer.stop()
            self.timer_button.setText("Start")
        else:
            self.timer.start()  # Update every second
            self.timer_button.setText("Stop")
    
    def _update_timer(self):
        """Update the combat timer display"""
        self.combat_time += 1
        hours = self.combat_time // 3600
        minutes = (self.combat_time % 3600) // 60
        seconds = self.combat_time % 60
        self.timer_label.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
    
    def _roll_initiative(self):
        """Roll initiative for the current combatant"""
        from random import randint
        modifier = self.init_mod_input.value()
        roll = randint(1, 20)
        total = roll + modifier
        self.initiative_input.setValue(total)
        
        # Show roll details
        QMessageBox.information(
            self,
            "Initiative Roll",
            f"Roll: {roll}\nModifier: {modifier:+d}\nTotal: {total}"
        )
        
        # Log the initiative roll if a name is entered
        name = self.name_input.text()
        if name:
            self._log_combat_action(
                "Initiative", 
                name, 
                "rolled initiative", 
                result=f"{roll} + {modifier} = {total}"
            )
    
    def _update_game_time(self):
        """Update the in-game time display"""
        # In D&D 5e, a round is 6 seconds
        total_seconds = (self.current_round - 1) * 6
        minutes = total_seconds // 60
        self.game_time_label.setText(
            f"{self.current_round - 1} rounds ({minutes} minutes)"
        )
    
    def _reset_combat(self):
        """Reset the entire combat tracker to its initial state."""
        # Log combat reset
        self._log_combat_action(
            "Other", 
            "DM", 
            "reset combat", 
            result="Combat tracker reset to initial state"
        )
        
        reply = QMessageBox.question(
            self,
            'Reset Combat',
            "Are you sure you want to reset the combat tracker? \nThis will clear all combatants and reset the round/timer.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Clear the table
            self.initiative_table.setRowCount(0)
            
            # Reset combat state variables
            self.current_round = 1
            self._current_turn = 0
            self.previous_turn = -1
            self.combat_time = 0
            self.combat_started = False
            self.death_saves.clear()
            self.concentrating.clear()
            
            # Reset UI elements
            self.round_spin.setValue(self.current_round)
            if self.timer.isActive():
                self.timer.stop()
            self.timer_label.setText("00:00:00")
            self.timer_button.setText("Start")
            self._update_game_time()
    
    def _restart_combat(self):
        """Restart the current combat (reset turn/round counter but keep combatants)."""
        # Log combat restart
        self._log_combat_action(
            "Other", 
            "DM", 
            "restarted combat", 
            result="Combat restarted with same combatants"
        )
        
        if self.initiative_table.rowCount() == 0:
            QMessageBox.information(self, "Restart Combat", "No combatants to restart.")
            return
            
        reply = QMessageBox.question(
            self,
            'Restart Combat',
            "Are you sure you want to restart the combat? \nThis will reset HP, status, round, and timer, but keep all combatants.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Reset combat state variables
            self.current_round = 1
            self._current_turn = 0
            self.previous_turn = -1
            self.combat_time = 0
            self.combat_started = False
            self.death_saves.clear()
            self.concentrating.clear()
            
            # Reset UI elements
            self.round_spin.setValue(self.current_round)
            if self.timer.isActive():
                self.timer.stop()
            self.timer_label.setText("00:00:00")
            self.timer_button.setText("Start")
            self._update_game_time()
            
            # Reset combatant state in the table
            for row in range(self.initiative_table.rowCount()):
                # Reset HP to max using the Max HP value from column 3
                hp_item = self.initiative_table.item(row, 2)
                max_hp_item = self.initiative_table.item(row, 3)
                
                if hp_item and max_hp_item:
                    max_hp_text = max_hp_item.text()
                    if max_hp_text and max_hp_text != "None":
                        hp_item.setText(max_hp_text)
                    else:
                        # Fallback if max_hp is None or empty
                        hp_item.setText("10") 
                        
                # Clear status
                status_item = self.initiative_table.item(row, 4)
                if status_item:
                    status_item.setText("")
                
                # Reset concentration
                conc_item = self.initiative_table.item(row, 5)
                if conc_item:
                    conc_item.setCheckState(Qt.Unchecked)
            
            # Re-sort based on original initiative (just in case)
            # And update highlight to the first combatant
            self._sort_initiative()
    
    # Custom event classes for safe thread communication
    class _ProgressEvent(QEvent):
        def __init__(self, message):
            super().__init__(QEvent.Type(QEvent.User + 100))
            self.message = message
    
    class _ErrorEvent(QEvent):
        def __init__(self, title, message):
            super().__init__(QEvent.Type(QEvent.User + 101))
            self.title = title
            self.message = message
    
    class _ClearLogEvent(QEvent):
        def __init__(self):
            super().__init__(QEvent.Type(QEvent.User + 102))
    
    class _AddInitialStateEvent(QEvent):
        def __init__(self, combat_state):
            super().__init__(QEvent.Type(QEvent.User + 103))
            self.combat_state = combat_state
    
    class _LogDiceEvent(QEvent):
        def __init__(self, expr, result):
            super().__init__(QEvent.Type(QEvent.User + 104))
            self.expr = expr
            self.result = result
    
    class _ProcessResultEvent(QEvent):
        def __init__(self, result, error):
            super().__init__(QEvent.Type(QEvent.User + 105))
            self.result = result
            self.error = error
    
    class _UpdateUIEvent(QEvent):
        def __init__(self, turn_state):
            super().__init__(QEvent.Type(QEvent.User + 106))
            self.turn_state = turn_state
    
    class _SetResolvingEvent(QEvent):
        def __init__(self, is_resolving):
            super().__init__(QEvent.Type(QEvent.User + 107))
            self.is_resolving = is_resolving
    
    class _ConnectSignalEvent(QEvent):
        def __init__(self):
            super().__init__(QEvent.Type(QEvent.User + 108))
    
    class _UpdateButtonEvent(QEvent):
        def __init__(self, text, enabled=True):
            super().__init__(QEvent.Type(QEvent.User + 109))
            self.text = text
            self.enabled = enabled
    
    def _fast_resolve_combat(self):
        """Use LLM to resolve the current combat encounter (turn-by-turn, rule-correct)."""
        import traceback
        import threading
        import gc
        from PySide6.QtWidgets import QApplication, QMessageBox

        # First, update UI to indicate processing is happening
        self.fast_resolve_button.setEnabled(False)
        self.fast_resolve_button.setText("Initializing...")
        QApplication.processEvents()  # Force immediate UI update
        
        # Add a safety timer that will reset the button after 5 minutes regardless
        # of whether the combat resolver signals completion
        safety_timer = QTimer(self)
        safety_timer.setSingleShot(True)
        safety_timer.timeout.connect(lambda: self._reset_resolve_button("Fast Resolve", True))
        safety_timer.start(300000)  # 5 minutes in milliseconds
        
        # Add a second backup timer with shorter timeout (2 minutes)
        backup_timer = QTimer(self)
        backup_timer.setSingleShot(True)
        backup_timer.timeout.connect(lambda: self._check_and_reset_button())
        backup_timer.start(120000)  # 2 minutes in milliseconds
        
        # Store timers for cancellation
        self._safety_timer = safety_timer
        self._backup_timer = backup_timer
        
        # Force garbage collection before starting
        gc.collect()
        
        # Define the main processing function to run in a separate thread
        def setup_and_start_combat():
            try:
                # Step 1: Validate we have combatants
                has_monster = has_player = False
                for row in range(self.initiative_table.rowCount()):
                    type_item = self.initiative_table.item(row, 7)  # Type is now column 7
                    if type_item:
                        combatant_type = type_item.text().lower()
                        if combatant_type == "monster":
                            has_monster = True
                        elif combatant_type in ["character", "pc", "npc"]:
                            has_player = True
                
                # Update progress on UI thread
                QApplication.instance().postEvent(self, CombatTrackerPanel._ProgressEvent("Validating combatants..."))
                
                # Handle validation errors
                if not has_monster and not has_player:
                    QApplication.instance().postEvent(self, CombatTrackerPanel._ErrorEvent(
                        "Cannot Start Combat", 
                        "You need at least one combatant (monster or character) to run combat."
                    ))
                    return
                    
                elif not has_monster and has_player:
                    QApplication.instance().postEvent(self, CombatTrackerPanel._ErrorEvent(
                        "Cannot Start Combat", 
                        "You need at least one monster to run combat against player characters.\n\n" +
                        "Add monsters from the Monster Panel."
                    ))
                    return
                
                # Step 2: Gather combat state
                QApplication.instance().postEvent(self, CombatTrackerPanel._ProgressEvent("Gathering combat data..."))
                combat_state = self._gather_combat_state()
                if not combat_state or not combat_state.get("combatants"):
                    QApplication.instance().postEvent(self, CombatTrackerPanel._ErrorEvent(
                        "Fast Resolve", 
                        "No combatants in the tracker to resolve."
                    ))
                    return
                
                # Step 3: Clear and prepare the combat log
                QApplication.instance().postEvent(self, CombatTrackerPanel._ProgressEvent("Preparing combat log..."))
                QApplication.instance().postEvent(self, CombatTrackerPanel._ClearLogEvent())
                
                # Step 4: Add initial combat state to log (this will be done on the UI thread)
                QApplication.instance().postEvent(self, CombatTrackerPanel._AddInitialStateEvent(combat_state))
                
                # Step 5: Setup the dice roller function that will be passed to the resolver
                def dice_roller(expr):
                    """Parse and roll a dice expression like '1d20+5'. Returns the integer result."""
                    try:
                        import re, random
                        match = re.match(r"(\d*)d(\d+)([+-]\d+)?", expr.replace(' ', ''))
                        if not match:
                            return 0
                        num, die, mod = match.groups()
                        num = int(num) if num else 1
                        die = int(die)
                        mod = int(mod) if mod else 0
                        total = sum(random.randint(1, die) for _ in range(num)) + mod
                        
                        # Log the roll to the combat log via a custom event
                        QApplication.instance().postEvent(self, CombatTrackerPanel._LogDiceEvent(expr, total))
                        return total
                    except Exception as e:
                        print(f"[CombatTracker] Error in dice roller: {e}")
                        return 10  # Provide a reasonable default
                
                # Step 6: Setup completion callback
                def completion_callback(result, error):
                    """Callback for resolution completion if signals aren't working"""
                    print(f"[CombatTracker] Manual completion callback called with result={bool(result)}, error={bool(error)}")
                    
                    # Forward to our UI handler via a custom event - safest approach
                    QApplication.instance().postEvent(self, CombatTrackerPanel._ProcessResultEvent(result, error))
                    
                    # Directly update button state via event
                    QApplication.instance().postEvent(self, CombatTrackerPanel._UpdateButtonEvent("Fast Resolve", True))
                    print("[CombatTracker] Posted button update event")
                    
                    # Create a very short timer as a last resort
                    reset_timer = QTimer()
                    reset_timer.setSingleShot(True)
                    reset_timer.timeout.connect(lambda: self._check_and_reset_button())
                    reset_timer.start(1000)  # 1 second delay
                
                # Step 7: Setup turn callback
                def manual_turn_callback(turn_state):
                    """Callback for per-turn updates if signals aren't working"""
                    print(f"[CombatTracker] Manual turn update callback received data with "
                          f"{len(turn_state.get('combatants', []))} combatants")
                    # Forward to our wrapper method via a custom event
                    QApplication.instance().postEvent(self, CombatTrackerPanel._UpdateUIEvent(turn_state))
                
                # Step 8: Start the actual combat resolution
                QApplication.instance().postEvent(self, CombatTrackerPanel._SetResolvingEvent(True))
                
                # Setup signal connection (done on UI thread)
                QApplication.instance().postEvent(self, CombatTrackerPanel._ConnectSignalEvent())
                
                # Update UI to show we're now resolving
                QApplication.instance().postEvent(self, CombatTrackerPanel._UpdateButtonEvent("Resolving...", False))
                
                # Step 9: Call the resolver with our setup
                resolver_callable = self.app_state.combat_resolver.resolve_combat_turn_by_turn
                accepts_turn_callback = 'turn_update_callback' in resolver_callable.__code__.co_varnames

                # Update UI with final preparation status
                QApplication.instance().postEvent(self, CombatTrackerPanel._ProgressEvent("Starting combat resolution..."))
                
                # Call with appropriate arguments based on what the resolver supports
                if accepts_turn_callback:
                    print("[CombatTracker] Resolver supports turn_update_callback, using it")
                    # This resolver takes a turn callback directly
                    self.app_state.combat_resolver.resolve_combat_turn_by_turn(
                        combat_state,
                        dice_roller,
                        completion_callback,  # Use our manual callback
                        manual_turn_callback  # Pass the callback for turns
                    )
                else:
                    print("[CombatTracker] Using standard resolver with update_ui_callback, relying on signals")
                    # Standard resolver - use it with our update_ui_wrapper and rely on signals
                    self.app_state.combat_resolver.resolve_combat_turn_by_turn(
                        combat_state,
                        dice_roller,
                        completion_callback,  # Pass our manual callback for backup
                        self._update_ui_wrapper  # This might be treated as update_ui_callback depending on interface
                    )
                    
            except Exception as e:
                traceback.print_exc()
                # If any error occurs, send an error event
                QApplication.instance().postEvent(self, CombatTrackerPanel._ErrorEvent(
                    "Error", 
                    f"Failed to start combat resolution: {str(e)}"
                ))
        
        # Start the setup in a background thread
        setup_thread = threading.Thread(target=setup_and_start_combat)
        setup_thread.daemon = True  # Allow app to exit even if thread is running
        setup_thread.start()
    
    # Override event handler to process our custom events
    def event(self, event):
        """Handle custom events posted to our panel"""
        from PySide6.QtWidgets import QApplication, QMessageBox
        
        if event.type() == QEvent.Type(QEvent.User + 1):
            # This is our UpdateUIEvent for JSON
            try:
                self._update_ui(event.json_data)
                return True
            except Exception as e:
                print(f"[CombatTracker] Error in event handler UI update: {e}")
                return False
        elif event.type() == QEvent.Type(QEvent.User + 100):
            # Progress event
            self.fast_resolve_button.setText(event.message)
            QApplication.processEvents()
            return True
        elif event.type() == QEvent.Type(QEvent.User + 101):
            # Error event
            self._reset_resolve_button("Fast Resolve", True)
            QMessageBox.critical(self, event.title, event.message)
            return True
        elif event.type() == QEvent.Type(QEvent.User + 102):
            # Clear log event
            self.combat_log_text.clear()
            return True
        elif event.type() == QEvent.Type(QEvent.User + 103):
            # Add initial state event
            self._add_initial_combat_state_to_log(event.combat_state)
            return True
        elif event.type() == QEvent.Type(QEvent.User + 104):
            # Log dice event
            self._log_combat_action(
                "Dice", 
                "AI", 
                f"rolled {event.expr}", 
                result=f"Result: {event.result}"
            )
            return True
        elif event.type() == QEvent.Type(QEvent.User + 105):
            # Process result event
            self._process_resolution_ui(event.result, event.error)
            return True
        elif event.type() == QEvent.Type(QEvent.User + 106):
            # Update UI event
            self._update_ui_wrapper(event.turn_state)
            return True
        elif event.type() == QEvent.Type(QEvent.User + 107):
            # Set resolving event
            self._is_resolving_combat = event.is_resolving
            print(f"[CombatTracker] Setting _is_resolving_combat = {event.is_resolving}")
            return True
        elif event.type() == QEvent.Type(QEvent.User + 108):
            # Connect signal event
            try:
                # Disconnect any existing connection first to be safe
                try:
                    self.app_state.combat_resolver.resolution_complete.disconnect(self._process_resolution_ui)
                    print("[CombatTracker] Disconnected existing signal connection")
                except Exception:
                    # Connection might not exist yet, which is fine
                    pass
                
                # Connect the signal
                self.app_state.combat_resolver.resolution_complete.connect(self._process_resolution_ui)
                print("[CombatTracker] Successfully connected resolution_complete signal")
            except Exception as conn_error:
                print(f"[CombatTracker] Failed to connect signal: {conn_error}")
            return True
        elif event.type() == QEvent.Type(QEvent.User + 109):
            # Update button event
            self._reset_resolve_button(event.text, event.enabled)
            return True
            
        return super().event(event)

    # This method remains, but it's the wrapper for thread-safe UI updates
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

    # Also add a custom event handler to handle our backup approach
    def _event_duplicate_backup(self, event):
        """Handle custom events posted to our panel"""
        if event.type() == QEvent.Type(QEvent.User + 1):
            # This is our UpdateUIEvent
            try:
                self._update_ui(event.json_data)
                return True
            except Exception as e:
                print(f"[CombatTracker] Error in event handler UI update: {e}")
                return False
        return super().event(event)

    # Make the actual UI update function a slot callable by the wrapper
    # The slot now accepts a string (JSON)
    @Slot(str)
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
                
                # Check if this is a fallback action (error handling)
                if latest_action.get("fallback", False):
                    # This is a fallback action due to an error - show a more user-friendly message
                    turn_text += f"<p style='color:#880000; margin-top:5px;'><i>{action}</i></p>"
                    turn_text += f"<p style='color:#000000; margin-top:5px;'>{result}</p>"
                    
                    # Add a note about the AI having trouble
                    turn_text += f"<p style='color:#666666; font-style:italic; margin-top:5px;'>Note: The AI had difficulty generating a response. Using fallback action instead.</p>"
                else:
                    # Normal action presentation with better visual hierarchy
                    # Add an action icon based on action type
                    action_icon = "⚔️"  # Default combat icon
                    action_lower = action.lower()
                    if "cast" in action_lower or "spell" in action_lower:
                        action_icon = "✨"  # Magic icon
                    elif "heal" in action_lower or "cure" in action_lower:
                        action_icon = "💚"  # Healing icon
                    elif "attack" in action_lower or "strike" in action_lower:
                        action_icon = "🗡️"  # Attack icon
                    elif "move" in action_lower:
                        action_icon = "👣"  # Movement icon
                    elif "dash" in action_lower:
                        action_icon = "🏃"  # Dash icon
                    elif "wait" in action_lower or "dodge" in action_lower:
                        action_icon = "🛡️"  # Defensive icon
                        
                    # Enhanced display with icon and better formatting
                    turn_text += f"<p style='color:#000000; margin-top:5px; font-weight:bold;'>{action_icon} {action}</p>"
                    
                    # Add result with better styling
                    if result:
                        turn_text += f"<p style='color:#000000; margin-top:5px;'><strong>Result:</strong> {result}</p>"
                
                # Add dice roll information with better visualization
                if dice_summary:
                    turn_text += f"<div style='background-color:#f0f0f0; border-radius:5px; padding:5px; margin-top:5px;'>"
                    turn_text += f"<p style='color:#000000; margin:0;'><strong>🎲 Dice Rolls:</strong></p>"
                    
                    # Format each die roll on its own line with better styling
                    for d_line in dice_summary.split('\n'):
                        parts = d_line.split('=')
                        if len(parts) == 2:
                            purpose = parts[0].strip()
                            result_val = parts[1].strip()
                            turn_text += f"<p style='color:#000000; margin:3px 0 0 10px;'>{purpose} <strong>→</strong> {result_val}</p>"
                        else:
                            turn_text += f"<p style='color:#000000; margin:3px 0 0 10px;'>{d_line}</p>"
                    
                    turn_text += "</div>"
                
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