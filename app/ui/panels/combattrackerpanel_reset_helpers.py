# Helpers for CombatTrackerPanel (_reset_)

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

def _reset_resolve_button(self, text="Fast Resolve", enabled=True):
    """Guaranteed method to reset the button state using the main UI thread"""
    # Direct update on the UI thread
    self.fast_resolve_button.setEnabled(enabled)
    self.fast_resolve_button.setText(text)
    
    # Force immediate UI update
    from PySide6.QtWidgets import QApplication
    QApplication.processEvents()
    
    print(f"[CombatTracker] Reset Fast Resolve button to '{text}' (enabled: {enabled})")

