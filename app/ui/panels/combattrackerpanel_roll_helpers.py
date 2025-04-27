# Helpers for CombatTrackerPanel (_roll_)

def _roll_initiative(self):
    """Roll initiative for the current combatant"""
    from random import randint
    modifier = self.init_mod_input.value()
    roll = randint(1, 20)
    total = roll + modifier
    self.initiative_input.setValue(total)
    
    # Show roll details
    QMessageBox.information(
        self,
        "Initiative Roll",
        f"Roll: {roll}\nModifier: {modifier:+d}\nTotal: {total}"
    )
    
    # Log the initiative roll if a name is entered
    name = self.name_input.text()
    if name:
        self._log_combat_action(
            "Initiative", 
            name, 
            "rolled initiative", 
            result=f"{roll} + {modifier} = {total}"
        )

