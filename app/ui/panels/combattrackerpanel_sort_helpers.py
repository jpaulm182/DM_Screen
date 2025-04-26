# Helpers for CombatTrackerPanel (_sort_)

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

