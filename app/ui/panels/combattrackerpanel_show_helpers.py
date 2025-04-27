# Helpers for CombatTrackerPanel (_show_)

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

