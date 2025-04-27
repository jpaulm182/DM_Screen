# Helpers for CombatTrackerPanel (_ensure_)

def _ensure_table_ready(self):
    """Ensure the table exists and has the correct number of columns"""
    # First check if table exists
    if not hasattr(self, 'initiative_table'):
        print("[CombatTracker] ERROR: initiative_table not found during initialization")
        return
        
    # Ensure the vertical header is hidden (row numbers)
    self.initiative_table.verticalHeader().setVisible(False)
    
    # Make sure horizontal headers are visible
    self.initiative_table.horizontalHeader().setVisible(True)
    
    # Adjust column widths for better display
    self.initiative_table.resizeColumnsToContents()
    
    # Add test combatant if table is empty and we're in development
    if self.initiative_table.rowCount() == 0:
        # Restore state first if available
        state = self.app_state.get_setting("combat_tracker_state", None)
        if state:
            print("[CombatTracker] Restoring combat tracker state from settings")
            self.restore_state(state)
            # Force a table update after restoring state
            self.initiative_table.viewport().update()
            self.initiative_table.update()
        
        # If still empty after restore attempt, add placeholder
        if self.initiative_table.rowCount() == 0:
            # Add a demo player character if table is still empty
            print("[CombatTracker] Adding placeholder character to empty table for visibility")
            self.combatant_manager.add_combatant("Add your party here!", 20, 30, 15, "character")
    
    # Ensure viewport is updated
    self.initiative_table.viewport().update()
    
    # Force application to process events
    QApplication.processEvents()

