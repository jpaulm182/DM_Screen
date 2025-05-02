import random
import re
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTableWidgetItem, QApplication, QTimer

class DiceRoller:
    def roll_dice(self, dice_formula):
        """Roll dice based on a formula like "3d8+4" or "2d6-1" """
        print(f"[CombatTracker] Rolling dice formula: {dice_formula}")
        if not dice_formula or not isinstance(dice_formula, str):
            print("[CombatTracker] Invalid dice formula")
            return 10
            
        # Parse the dice formula
        dice_match = re.search(r'(\d+)d(\d+)([+-]\d+)?', dice_formula)
        if not dice_match:
            print(f"[CombatTracker] Could not parse dice formula: {dice_formula}")
            return 10
            
        try:
            # Extract dice components
            count = int(dice_match.group(1))
            sides = int(dice_match.group(2))
            modifier = 0
            if dice_match.group(3):
                modifier = int(dice_match.group(3))
                
            # Roll the dice
            rolls = [random.randint(1, sides) for _ in range(count)]
            total = sum(rolls) + modifier
            print(f"[CombatTracker] Dice rolls: {rolls}, modifier: {modifier}, total: {total}")
            return max(1, total)  # Ensure at least 1 HP
        except (ValueError, TypeError, IndexError) as e:
            print(f"[CombatTracker] Error rolling dice: {e}")
            return 10

    def extract_dice_formula(self, hp_value):
        """Extract a dice formula from various HP value formats"""
        dice_formula = None
        
        if isinstance(hp_value, dict) and 'hit_dice' in hp_value:
            dice_formula = hp_value['hit_dice']
            print(f"[CombatTracker] Found hit_dice in dict: {dice_formula}")
        elif isinstance(hp_value, str):
            # Try to extract formula from string like "45 (6d10+12)"
            match = re.search(r'\(\s*([0-9d+\-\s]+)\s*\)', hp_value)
            if match:
                # Remove any spaces from the formula before processing
                dice_formula = re.sub(r'\s+', '', match.group(1))
                print(f"[CombatTracker] Extracted dice formula from parentheses: {dice_formula}")
            # If the string itself is a dice formula
            elif re.match(r'^\d+d\d+([+-]\d+)?$', hp_value):
                dice_formula = hp_value
                print(f"[CombatTracker] String is directly a dice formula: {dice_formula}")
                
        return dice_formula

    def add_monster(self, monster_data):
        """Add a monster from monster panel to the tracker"""
        if not monster_data:
            return -1
            
        # Block signals to prevent race conditions during adding
        self.initiative_table.blockSignals(True)
        
        try:
            # Diagnostic: Log information about this monster
            monster_name = "Unknown"
            if isinstance(monster_data, dict) and 'name' in monster_data:
                monster_name = monster_data['name']
            elif hasattr(monster_data, 'name'):
                monster_name = monster_data.name
                
            print(f"[CombatTracker] Adding monster '{monster_name}' (type: {type(monster_data)})")
            
            # Validate monster data to prevent ability mixing
            try:
                # Import the validator
                from app.core.improved_combat_resolver import ImprovedCombatResolver
                
                # Only validate if it's a dictionary (proper format)
                if isinstance(monster_data, dict):
                    # Check if this monster has already been validated
                    if "_validation_id" in monster_data:
                        # Already validated, skip further validation to preserve abilities
                        print(f"[CombatTracker] Monster {monster_name} already validated with ID {monster_data['_validation_id']}")
                        validated_monster_data = monster_data
                    else:
                        # Validate monster data
                        print(f"[CombatTracker] Validating monster data for '{monster_name}'")
                        validated_monster_data = ImprovedCombatResolver.validate_monster_data(monster_data)
                    
                    # Check if validation changed anything
                    actions_before = len(monster_data.get('actions', [])) if 'actions' in monster_data else 0
                    actions_after = len(validated_monster_data.get('actions', [])) if 'actions' in validated_monster_data else 0
                    
                    traits_before = len(monster_data.get('traits', [])) if 'traits' in monster_data else 0
                    traits_after = len(validated_monster_data.get('traits', [])) if 'traits' in validated_monster_data else 0
                    
                    if actions_before != actions_after or traits_before != traits_after:
                        print(f"[CombatTracker] Validation modified abilities for {monster_name}")
                        print(f"[CombatTracker] Actions: {actions_before} -> {actions_after}, Traits: {traits_before} -> {traits_after}")
                        
                        # If validation retained most abilities, use the validated data
                        # Otherwise, keep the original to avoid losing legitimate abilities
                        if actions_after >= actions_before * 0.5 and traits_after >= traits_before * 0.5:
                            monster_data = validated_monster_data
                            print(f"[CombatTracker] Using validated monster data (most abilities retained)")
                        else:
                            print(f"[CombatTracker] Validation removed too many abilities, keeping original data")
                            # Still use the validation ID for consistency
                            if "_validation_id" in validated_monster_data:
                                monster_data["_validation_id"] = validated_monster_data["_validation_id"]
            except Exception as e:
                # If validation fails, log the error but continue with the original data
                print(f"[CombatTracker] Error validating monster data: {e}")
                # Don't block combat addition due to validation error
            
            # Helper function to get attribute from either dict or object
            def get_attr(obj, attr, default=None, alt_attrs=None):
                """Get attribute from object or dict, trying alternate attribute names if specified"""
                alt_attrs = alt_attrs or []
                result = default
                
                try:
                    # Implementation remains the same
                    # Just a helper function to retrieve attributes from different object types
                    if isinstance(obj, dict):
                        if attr in obj:
                            return obj[attr]
                        for alt_attr in alt_attrs:
                            if alt_attr in obj:
                                return obj[alt_attr]
                        # Additional checks for nested structures, etc.
                        # ...
                    else:
                        if hasattr(obj, attr):
                            return getattr(obj, attr)
                        for alt_attr in alt_attrs:
                            if hasattr(obj, alt_attr):
                                return getattr(obj, alt_attr)
                        # Additional checks for object attributes, etc.
                        # ...
                    
                    return default
                except Exception as e:
                    print(f"[CombatTracker] Error in get_attr({attr}): {e}")
                    return default
                
            # Get monster name
            name = get_attr(monster_data, "name", "Unknown Monster")
            
            # Generate a unique ID for this monster instance using the correct counter attribute
            monster_id = self.combatant_manager.monster_id_counter
            self.combatant_manager.monster_id_counter += 1
            
            # Get a reasonable initiative modifier from DEX
            dex = get_attr(monster_data, "dexterity", 10, ["dex", "DEX"])
            init_mod = (dex - 10) // 2
            
            # Roll initiative
            initiative_roll = random.randint(1, 20) + init_mod
            
            # Get monster HP data and AC in various formats
            hp_value = get_attr(monster_data, "hp", 10, ["hit_points", "hitPoints", "hit_points_roll", "hit_dice"])
            print(f"[CombatTracker] Retrieved HP value: {hp_value} (type: {type(hp_value)})")
            
            # Calculate average HP (for Max HP display)
            max_hp = 0
            if isinstance(hp_value, int):
                max_hp = hp_value
            elif isinstance(hp_value, dict) and 'average' in hp_value:
                max_hp = int(hp_value['average'])
            elif isinstance(hp_value, str):
                # Try to extract average value from string like "45 (6d10+12)"
                match = re.match(r'(\d+)\s*\(', hp_value)
                if match:
                    max_hp = int(match.group(1))
                elif hp_value.isdigit():
                    max_hp = int(hp_value)
            
            if max_hp <= 0:
                max_hp = 10
                
            print(f"[CombatTracker] Max HP: {max_hp}")
            
            # IMPORTANT PART: EXTRACT DICE FORMULA AND ROLL HP
            dice_formula = self.extract_dice_formula(hp_value)
            
            # ALWAYS ROLL RANDOM HP
            if dice_formula:
                # Roll random HP using the dice formula
                hp = self.roll_dice(dice_formula)
                print(f"[CombatTracker] RANDOM HP ROLL: {hp} using formula {dice_formula}")
            else:
                # If no dice formula, create a better one based on monster CR and average HP
                # For dragons and high-HP monsters, a better approximation would be:
                # d12 for big monsters, d10 for medium monsters, d8 for small monsters
                
                # Determine the creature size based on max HP
                if max_hp > 200:  # Large/Huge creatures like dragons
                    die_size = 12
                    num_dice = max(1, int(max_hp * 0.75 / (die_size/2 + 0.5)))  # Scale dice count to match HP
                elif max_hp > 100:  # Medium creatures
                    die_size = 10
                    num_dice = max(1, int(max_hp * 0.8 / (die_size/2 + 0.5)))
                else:  # Small creatures
                    die_size = 8
                    num_dice = max(1, int(max_hp * 0.85 / (die_size/2 + 0.5)))
                
                # Add a small modifier to account for Constitution
                modifier = int(max_hp * 0.1)
                estimated_formula = f"{num_dice}d{die_size}+{modifier}"
                hp = self.roll_dice(estimated_formula)
                print(f"[CombatTracker] NO FORMULA FOUND - Created estimated formula {estimated_formula} and rolled: {hp}")
                
                # Limit HP to a reasonable range (50%-125% of average)
                min_hp = int(max_hp * 0.5)
                max_possible_hp = int(max_hp * 1.25)
                hp = max(min_hp, min(hp, max_possible_hp))
                print(f"[CombatTracker] Adjusted HP to {hp} (limited to {min_hp}-{max_possible_hp})")
            
            # Set max_hp to the randomly rolled hp value so they match
            max_hp = hp
            
            ac = get_attr(monster_data, "ac", 10, ["armor_class", "armorClass", "AC"])
            print(f"[CombatTracker] Retrieved AC value: {ac}")
            
            # Save monster stats for later verification
            monster_stats = {
                "id": monster_id,
                "name": name,
                "hp": hp,
                "max_hp": max_hp,
                "ac": ac
            }
            
            # Add to tracker with our randomly rolled HP
            row = self.combatant_manager.add_combatant(name, initiative_roll, hp, max_hp, ac, "monster", monster_id)
            
            # Ensure row is valid, default to -1 if None
            if row is None:
                row = -1
            
            # Store monster data for future reference
            if row >= 0:
                self.combatant_manager.combatants_by_id[row] = monster_data
                
            # Force a refresh of the entire table
            self.initiative_table.viewport().update()
            QApplication.processEvents()
                    
            # Make absolutely sure this monster's values are correctly set (with delay)
            QTimer.singleShot(50, lambda: self._verify_monster_stats(monster_stats))
                    
            # Log to combat log
            self._log_combat_action("Setup", "DM", "added monster", name, f"(Init: {initiative_roll}, HP: {hp}/{max_hp})")
            
            return row
            
        finally:
            # Always unblock signals even if there's an error
            self.initiative_table.blockSignals(False)
            
        """Double-check that monster stats are properly set after adding and sorting"""
        monster_id = monster_stats["id"]
        name = monster_stats["name"]
        hp = monster_stats["hp"]
        max_hp = monster_stats["max_hp"]
        ac = monster_stats["ac"]
        
        # Find the current row for this monster
        row = self._find_monster_by_id(monster_id)
        if row < 0:
            print(f"[CombatTracker] Warning: Cannot verify stats for monster {name} (ID {monster_id}) - not found")
            return
            
        # Verify all stats are correctly set
        hp_item = self.initiative_table.item(row, 2)
        max_hp_item = self.initiative_table.item(row, 3)
        ac_item = self.initiative_table.item(row, 4)
        
        # Prepare values as strings
        hp_str = str(hp) if hp is not None else "10"
        max_hp_str = str(max_hp) if max_hp is not None else "10"
        ac_str = str(ac) if ac is not None else "10"
        
        # Check and fix values if needed
        changes_made = False
        
        # Check HP
        if not hp_item or hp_item.text() != hp_str:
            print(f"[CombatTracker] Fixing HP for {name} (ID {monster_id}) at row {row}: setting to {hp_str}")
            new_hp_item = QTableWidgetItem(hp_str)
            new_hp_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
            self.initiative_table.setItem(row, 2, new_hp_item)
            changes_made = True
            
        # Check Max HP
        if not max_hp_item or max_hp_item.text() != max_hp_str:
            print(f"[CombatTracker] Fixing Max HP for {name} (ID {monster_id}) at row {row}: setting to {max_hp_str}")
            new_max_hp_item = QTableWidgetItem(max_hp_str)
            new_max_hp_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
            self.initiative_table.setItem(row, 3, new_max_hp_item)
            changes_made = True
            
        # Check AC
        if not ac_item or ac_item.text() != ac_str:
            print(f"[CombatTracker] Fixing AC for {name} (ID {monster_id}) at row {row}: setting to {ac_str}")
            new_ac_item = QTableWidgetItem(ac_str)
            new_ac_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
            self.initiative_table.setItem(row, 4, new_ac_item)
            changes_made = True
            
        # If any changes were made, update the table
        if changes_made:
            self.initiative_table.viewport().update()
            print(f"[CombatTracker] Stats verified and fixed for {name} (ID {monster_id})")
        else:
            print(f"[CombatTracker] All stats correct for {name} (ID {monster_id})")
