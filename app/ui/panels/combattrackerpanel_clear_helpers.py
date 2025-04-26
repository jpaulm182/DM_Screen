# Helpers for CombatTrackerPanel (_clear_)

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

    def _clear_combat_log(self):
        """Clear the combat log display"""
        self.combat_log_text.clear()
        self.combat_log_text.setHtml("<p><i>Combat log cleared.</i></p>")

