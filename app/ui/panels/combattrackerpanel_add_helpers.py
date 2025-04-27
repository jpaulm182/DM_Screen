# Helpers for CombatTrackerPanel (_add_)

def _add_status(self, status):
    """Add a status condition to selected combatants without removing existing ones"""
    # Get selected rows
    selected_rows = set(index.row() for index in self.initiative_table.selectedIndexes())
    if not selected_rows:
        return
    
    # Apply status to each selected row
    for row in selected_rows:
        if row < self.initiative_table.rowCount():
            status_item = self.initiative_table.item(row, 5)  # Status is now column 5
            if status_item:
                current_statuses = []
                if status_item.text():
                    current_statuses = [s.strip() for s in status_item.text().split(',')]
                
                # Only add if not already present
                if status not in current_statuses:
                    current_statuses.append(status)
                    status_item.setText(', '.join(current_statuses))
            
            # Log status change if there's a name
            name_item = self.initiative_table.item(row, 0)
            if name_item:
                name = name_item.text()
                
                # Log status change
                self._log_combat_action(
                    "Status Effect", 
                    "DM", 
                    "applied status", 
                    name, 
                    status
                )

def _add_initial_combat_state_to_log(self, combat_state):
    """Add initial combat state to the log at the start of combat"""
    # Clear any previous combat log content
    if hasattr(self, 'combat_log_text') and self.combat_log_text:
        # Check if we already have a "Combat Concluded" message
        current_text = self.combat_log_text.toHtml()
        if "Combat Concluded" in current_text:
            # Previous combat summary exists, clear it
            self.combat_log_text.clear()
        
    # Create summary HTML with better contrast colors
    html = "<h3 style='color: #000088;'>Initial Combat State</h3>"
    html += "<p style='color: #000000;'>Combatants in initiative order:</p>"
    html += "<ul style='color: #000000;'>"
    
    # Get combatants and build a summary
    combatants = combat_state.get("combatants", [])
    if not combatants:
        html += "<li>No combatants found</li>"
        html += "</ul>"
        html += "<p style='color: #000000;'><strong>Combat cannot begin with no combatants.</strong></p>"
        
        # Add to local log
        self.combat_log_text.append(html)
        
        # Force UI update
        from PySide6.QtWidgets import QApplication
        QApplication.processEvents()
        return
        
    # Sort by initiative
    try:
        sorted_combatants = sorted(combatants, key=lambda c: -c.get("initiative", 0))
    except Exception as e:
        print(f"[CombatTracker] Error sorting combatants: {e}")
        sorted_combatants = combatants
    
    for c in sorted_combatants:
        name = c.get("name", "Unknown")
        hp = c.get("hp", 0)
        max_hp = c.get("max_hp", hp)
        ac = c.get("ac", 10)
        initiative = c.get("initiative", 0)
        combatant_type = c.get("type", "unknown")
        
        # Different display for monsters vs characters with better styling
        if combatant_type.lower() == "monster":
            html += f"<li><strong style='color: #880000;'>{name}</strong> (Monster) - Initiative: {initiative}, AC: {ac}, HP: {hp}/{max_hp}</li>"
        else:
            html += f"<li><strong style='color: #000088;'>{name}</strong> (PC) - Initiative: {initiative}, AC: {ac}, HP: {hp}/{max_hp}</li>"
            
    html += "</ul>"
    html += "<p style='color: #000000;'><strong>Combat begins now!</strong></p>"
    html += "<hr style='border: 1px solid #000088;'>"
    
    # Add to the log
    self.combat_log_text.append(html)
    
    # Ensure cursor is at the end and scroll to the bottom
    cursor = self.combat_log_text.textCursor()
    cursor.movePosition(QTextCursor.End)
    self.combat_log_text.setTextCursor(cursor)
    
    scrollbar = self.combat_log_text.verticalScrollBar()
    scrollbar.setValue(scrollbar.maximum())
    
    # Force UI update
    from PySide6.QtWidgets import QApplication
    QApplication.processEvents()

