# Helpers for CombatTrackerPanel (_toggle_)

def _toggle_timer(self):
    """Toggle the combat timer"""
    if self.timer.isActive():
        self.timer.stop()
        self.timer_button.setText("Start")
    else:
        self.timer.start()  # Update every second
        self.timer_button.setText("Stop")

def _toggle_details_pane(self):
    """Toggle visibility of the details pane"""
    self.show_details_pane = not self.show_details_pane
    
    # Log which action we're taking
    action = "showing" if self.show_details_pane else "hiding"
    print(f"[CombatTracker] {action} details pane")

def _toggle_concentration(self, row):
    """Toggle concentration state for a combatant"""
    if row not in self.concentrating:
        self.concentrating.add(row)
        # Log concentration gained
        self._log_combat_action("Effect Started", "DM", "gained concentration", "", "")
    else:
        self.concentrating.remove(row)
        # Log concentration broken
        self._log_combat_action("Effect Ended", "DM", "lost concentration", "", "")

