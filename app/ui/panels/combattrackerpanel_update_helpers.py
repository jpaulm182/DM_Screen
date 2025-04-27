# Helpers for CombatTrackerPanel (_update_)

def _update_combatant_hp_and_status(self, row):
    """Update the HP and status of a combatant in the data dictionary based on the table"""
    if row not in self.combatant_manager.combatants_by_id:
        return
        
    # Get HP from table
    hp_item = self.initiative_table.item(row, 2)  # Current HP
    max_hp_item = self.initiative_table.item(row, 3)  # Max HP
    
    if hp_item:
        hp_text = hp_item.text().strip()
        try:
            hp = int(hp_text) if hp_text else 0
            
            # Update the hp in the combatant data if it's a dictionary
            if isinstance(self.combatant_manager.combatants_by_id[row], dict):
                self.combatant_manager.combatants_by_id[row]['current_hp'] = hp
            elif hasattr(self.combatant_manager.combatants_by_id[row], 'current_hp'):
                self.combatant_manager.combatants_by_id[row].current_hp = hp
        except (ValueError, TypeError):
            # Ignore if not a valid number
            pass
    
    # Update max HP if available
    if max_hp_item:
        max_hp_text = max_hp_item.text().strip()
        try:
            max_hp = int(max_hp_text) if max_hp_text else 0
            
            # Update the max_hp in the combatant data if it's a dictionary
            if isinstance(self.combatant_manager.combatants_by_id[row], dict):
                self.combatant_manager.combatants_by_id[row]['max_hp'] = max_hp
            elif hasattr(self.combatant_manager.combatants_by_id[row], 'max_hp'):
                self.combatant_manager.combatants_by_id[row].max_hp = max_hp
        except (ValueError, TypeError):
            # Ignore if not a valid number
            pass
            
    # Get status from table
    status_item = self.initiative_table.item(row, 5)  # Status is now column 5
    if status_item:
        status_text = status_item.text()
        
        # Parse statuses from comma-separated list
        statuses = []
        if status_text:
            statuses = [s.strip() for s in status_text.split(',')]
        
        # Update the status in the combatant data if it's a dictionary
        if isinstance(self.combatant_manager.combatants_by_id[row], dict):
            if 'conditions' not in self.combatant_manager.combatants_by_id[row]:
                self.combatant_manager.combatants_by_id[row]['conditions'] = []
            self.combatant_manager.combatants_by_id[row]['conditions'] = statuses
        elif hasattr(self.combatant_manager.combatants_by_id[row], 'conditions'):
            self.combatant_manager.combatants_by_id[row].conditions = statuses

def _update_details_pane(self):
    """Placeholder for details pane update - no longer needed with new UI but referenced in code"""
    print("[CombatTracker] _update_details_pane called - this is a placeholder in the new UI")
    # No actual implementation needed with the new UI design

    """Fix any missing combatant types for existing entries after initialization or state restore."""
    # Check if table exists and has rows
    if not hasattr(self, 'initiative_table') or self.initiative_table.rowCount() == 0:
        return 0 # Nothing to fix
        
    fix_count = 0
    print("[CombatTracker] Running _fix_missing_types...")
    
    for row in range(self.initiative_table.rowCount()):
        name_item = self.initiative_table.item(row, 0)
        type_item = self.initiative_table.item(row, 7) # Type is column 7
        name = name_item.text() if name_item else f"Row {row}"
        
        # Check if type is missing or invalid
        current_type = type_item.text().lower().strip() if type_item and type_item.text() else None
        needs_fix = not current_type or current_type not in ["monster", "character", "manual"]
        
        # Also check if UserRole data is missing (used by context menu/details)
        if name_item and name_item.data(Qt.UserRole) is None:
            needs_fix = True

        if needs_fix:
            inferred_type = ""
            # 1. Check stored combatant data first
            if row in self.combatant_manager.combatants_by_id:
                data = self.combatant_manager.combatants_by_id[row]
                if isinstance(data, dict):
                    if any(k in data for k in ["monster_id", "size", "challenge_rating", "hit_points"]):
                        inferred_type = "monster"
                    elif any(k in data for k in ["character_class", "level", "race"]):
                        inferred_type = "character"
                elif hasattr(data, '__dict__'): # Handle object data
                    if hasattr(data, 'size') or hasattr(data, 'challenge_rating') or hasattr(data, 'hit_points'):
                        inferred_type = "monster"
                    elif hasattr(data, 'character_class') or hasattr(data, 'level') or hasattr(data, 'race'):
                        inferred_type = "character"
            
            # 2. If still unknown, use name-based heuristics
            if not inferred_type:
                monster_names = ["goblin", "ogre", "dragon", "troll", "zombie", "skeleton", 
                                    "ghoul", "ghast", "ghost", "demon", "devil", "elemental", "giant"]
                lower_name = name.lower()
                
                if any(monster in lower_name for monster in monster_names):
                    inferred_type = "monster"
                elif "(npc)" in lower_name:
                    inferred_type = "character"
                elif name == "Add your party here!": # Handle placeholder
                        inferred_type = "character"
                else:
                    # Default fallback - might be risky, consider 'manual'?
                    inferred_type = "manual" 
            
            # Apply the fix
            if not type_item:
                type_item = QTableWidgetItem()
                self.initiative_table.setItem(row, 7, type_item)
            
            if type_item.text() != inferred_type:
                    type_item.setText(inferred_type)
                    
            # Also fix UserRole data on name item
            if name_item and name_item.data(Qt.UserRole) != inferred_type:
                name_item.setData(Qt.UserRole, inferred_type)
                
            fix_count += 1
            print(f"[CombatTracker] Fixed missing/invalid type for '{name}' (row {row}) - set to '{inferred_type}'")
    
    if fix_count > 0:
        print(f"[CombatTracker] Fixed types for {fix_count} combatants")
    else:
            print("[CombatTracker] _fix_missing_types: No types needed fixing.")
    
    return fix_count
