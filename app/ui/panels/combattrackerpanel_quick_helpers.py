# Helpers for CombatTrackerPanel (_quick_)

    def _quick_damage(self, amount):
        """Apply quick damage to selected combatants"""
        if amount <= 0:
            return
            
        # Get selected rows
        selected_rows = [index.row() for index in 
                        self.initiative_table.selectionModel().selectedRows()]
        
        if not selected_rows:
            if 0 <= self.current_turn < self.initiative_table.rowCount():
                # If no selection, apply to current turn
                selected_rows = [self.current_turn]
            else:
                return
                
        for row in selected_rows:
            hp_item = self.initiative_table.item(row, 2)  # HP is now column 2
            max_hp_item = self.initiative_table.item(row, 3)  # Max HP is column 3
            
            if hp_item:
                try:
                    # Safely get current HP
                    hp_text = hp_item.text().strip()
                    current_hp = int(hp_text) if hp_text else 0
                    max_hp = int(max_hp_item.text()) if max_hp_item and max_hp_item.text() else current_hp
                    
                    new_hp = max(current_hp - amount, 0)
                    hp_item.setText(str(new_hp))
                    
                    # Check for concentration
                    if amount > 0:
                        self._check_concentration(row, amount)
                        
                    # Check for death saves if 0 HP
                    if new_hp == 0:
                        name = self.initiative_table.item(row, 0).text()
                        QMessageBox.information(
                            self,
                            "HP Reduced to 0",
                            f"{name} is down! Remember to track death saves."
                        )
                except ValueError:
                    # Handle invalid HP value
                    pass

    def _quick_heal(self, amount):
        """Apply quick healing to selected combatants"""
        if amount <= 0:
            return
            
        # Get selected rows
        selected_rows = [index.row() for index in 
                        self.initiative_table.selectionModel().selectedRows()]
        
        if not selected_rows:
            if 0 <= self.current_turn < self.initiative_table.rowCount():
                # If no selection, apply to current turn
                selected_rows = [self.current_turn]
            else:
                return
                
        for row in selected_rows:
            hp_item = self.initiative_table.item(row, 2)  # HP is now column 2
            max_hp_item = self.initiative_table.item(row, 3)  # Max HP is column 3
            
            if hp_item and max_hp_item:
                try:
                    # Safely get current HP
                    hp_text = hp_item.text().strip()
                    current_hp = int(hp_text) if hp_text else 0
                    
                    # Get max HP from the max HP column
                    max_hp_text = max_hp_item.text().strip()
                    max_hp = int(max_hp_text) if max_hp_text else 999
                    
                    new_hp = min(current_hp + amount, max_hp)
                    hp_item.setText(str(new_hp))
                except ValueError:
                    # Handle invalid HP value
                    pass

