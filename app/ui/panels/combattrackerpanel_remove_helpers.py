# Helpers for CombatTrackerPanel (_remove_)

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

