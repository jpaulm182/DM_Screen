# Helpers for CombatTrackerPanel (_handle_)

def _handle_add_click(self):
    """Handle the Add button click to add a new combatant from form fields"""
    try:
        name = self.name_input.text().strip()
        if not name:
            # Don't add combatants without a name
            QMessageBox.warning(self, "Missing Name", "Please enter a name for the combatant.")
            return
        
        # Get values from input fields
        initiative = self.initiative_input.value()
        hp = self.hp_input.value()
        max_hp = hp  # Set max_hp to same as current hp for manually added combatants
        ac = self.ac_input.value()
        
        # Add the combatant (no specific type for manual adds)
        row = self.combatant_manager.add_combatant(name, initiative, hp, max_hp, ac, "manual")
        
        # Only reset fields and log if the add was successful
        if row >= 0:
            # Reset fields for next entry (except initiative modifier)
            self.name_input.clear()
            self.initiative_input.setValue(0)
            
            # Log to combat log
            self._log_combat_action("Setup", "DM", "added manual combatant", name, f"(Initiative: {initiative})")
            
            return row
        else:
            QMessageBox.warning(self, "Add Failed", f"Failed to add {name} to the combat tracker.")
            return -1
    except Exception as e:
        import traceback
        traceback.print_exc()
        QMessageBox.critical(self, "Error", f"An error occurred adding the combatant: {str(e)}")
        return -1

    """Add a combatant to the initiative table"""
    print(f"[CombatTracker] _add_combatant called: name={name}, initiative={initiative}, hp={hp}, max_hp={max_hp}, ac={ac}, type={combatant_type}, id={monster_id}")
    logging.debug(f"[CombatTracker] Adding combatant: Name={name}, Init={initiative}, HP={hp}/{max_hp}, AC={ac}, Type={combatant_type}, ID={monster_id}") # Add DEBUG log
    
    # Get current row count
    row = self.initiative_table.rowCount()
    self.initiative_table.insertRow(row)
    
    # Create name item with combatant type stored in user role
    name_item = QTableWidgetItem(name)
    name_item.setData(Qt.UserRole, combatant_type)  # Store type with the name item
    
    # If this is a monster with ID, store the ID in UserRole+2
    if monster_id is not None:
        name_item.setData(Qt.UserRole + 2, monster_id)
        print(f"[CombatTracker] Set monster ID {monster_id} for {name}")
    
    # Ensure no checkbox
    name_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
    self.initiative_table.setItem(row, 0, name_item)
    
    # Set initiative
    init_item = QTableWidgetItem(str(initiative))
    init_item.setData(Qt.DisplayRole, initiative)  # For sorting
    init_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
    self.initiative_table.setItem(row, 1, init_item)
    
    # Set current HP - Make extra sure we're dealing with valid values
    hp_str = str(hp) if hp is not None else "10"
    print(f"[CombatTracker] Setting HP for {name} to {hp_str}")
    hp_item = QTableWidgetItem(hp_str)
    hp_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
    self.initiative_table.setItem(row, 2, hp_item)
    
    # Set Max HP - Make extra sure we're dealing with valid values
    max_hp_str = str(max_hp) if max_hp is not None else "10"
    print(f"[CombatTracker] Setting Max HP for {name} to {max_hp_str}")
    max_hp_item = QTableWidgetItem(max_hp_str)
    max_hp_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
    self.initiative_table.setItem(row, 3, max_hp_item)
    
    # Set AC
    ac_str = str(ac) if ac is not None else "10"
    ac_item = QTableWidgetItem(ac_str)
    ac_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
    self.initiative_table.setItem(row, 4, ac_item)
    
    # Set status as empty initially
    status_item = QTableWidgetItem("")
    status_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
    self.initiative_table.setItem(row, 5, status_item)
    
    # Set concentration as unchecked initially - only column with checkbox
    conc_item = QTableWidgetItem()
    conc_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
    conc_item.setCheckState(Qt.Unchecked)
    self.initiative_table.setItem(row, 6, conc_item)
    
    # Set type (monster, character, etc.) for filtering
    type_item = QTableWidgetItem(combatant_type)
    type_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
    self.initiative_table.setItem(row, 7, type_item)
    
    # Store current row before sorting
    current_row = row
    
    # Sort the initiative order
    self._sort_initiative()
    
    # Verify the final result
    final_hp_item = self.initiative_table.item(row, 2)
    if final_hp_item:
        final_hp = final_hp_item.text()
        print(f"[CombatTracker] Final verification - {name} HP after sorting: {final_hp}")
    
    # After sorting, find this monster's new row by its ID
    sorted_row = -1
    if monster_id is not None:
        sorted_row = self._find_monster_by_id(monster_id)
        if sorted_row >= 0:
            print(f"[CombatTracker] After sorting, monster {name} (ID {monster_id}) is at row {sorted_row}")
        else:
            print(f"[CombatTracker] WARNING: Could not find monster {name} (ID {monster_id}) after sorting")
            sorted_row = row  # Fall back to original row
    
    # Return the row where the combatant was added (post-sorting if monster with ID)
    return sorted_row if sorted_row >= 0 else row

    """Find the row of a monster by its unique ID"""
    if monster_id is None:
        return -1
        
    for row in range(self.initiative_table.rowCount()):
        name_item = self.initiative_table.item(row, 0)
        if name_item and name_item.data(Qt.UserRole + 2) == monster_id:
            return row
            
    return -1

def _handle_cell_changed(self, row, column):
    """Handle when a cell in the initiative table is changed."""
    # Prevent handling during program-initiated changes
    if self.initiative_table.signalsBlocked():
        return
        
    # Prevent recursive calls
    self.initiative_table.blockSignals(True)
    
    try:
        # Get the updated item
        item = self.initiative_table.item(row, column)
        if not item:
            return
            
        # Only sort if the Initiative column (column 1) changed
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

