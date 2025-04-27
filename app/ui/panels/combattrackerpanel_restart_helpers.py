# Helpers for CombatTrackerPanel (_restart_)

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

