# Helpers for CombatTrackerPanel (_next_)

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

