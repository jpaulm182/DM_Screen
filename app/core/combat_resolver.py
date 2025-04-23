"""
Core component for resolving combat encounters using LLM.

This class takes the current combat state and uses an LLM to generate
tactical decisions, which are then executed with dice rolls and
properly reflected in the UI.
"""

from app.core.llm_service import LLMService, ModelInfo
import json
import re
import time
import logging

# Import QObject and Signal for thread-safe communication
from PySide6.QtCore import QObject, Signal

# Inherit from QObject
class CombatResolver(QObject):
    """
    Handles the logic for resolving combat using an LLM, with proper
    UI feedback and dice-rolling integration.
    """
    # Define a signal to emit results thread-safely
    # It will carry the result dictionary (or None) and error string (or None)
    resolution_complete = Signal(object, object)

    def __init__(self, llm_service: LLMService):
        """Initialize the CombatResolver with the LLM service."""
        # Call QObject initializer
        super().__init__()
        self.llm_service = llm_service

    def resolve_combat_turn_by_turn(self, combat_state, dice_roller, callback, update_ui_callback=None):
        """
        Resolve combat turn-by-turn, with proper UI feedback.
        
        Args:
            combat_state: Dictionary with current combat state (combatants, round, etc.)
            dice_roller: Function that rolls dice (takes expression, returns result)
            callback: Function called with final result or error (DEPRECATED - Use resolution_complete signal)
            update_ui_callback: Function called after each turn to update UI (optional)
        """
        # NOTE: The 'callback' argument is now effectively unused, relying on the signal instead.
        # We keep it for now to avoid breaking the calling signature immediately, but it should be removed later.
        import copy
        import threading
        
        # Make a deep copy to avoid mutating the original
        # Ensure combat_state is a dictionary before copying
        if isinstance(combat_state, dict):
            state_copy = copy.deepcopy(combat_state)
        else:
            print(f"[CombatResolver] Warning: combat_state is not a dictionary, type: {type(combat_state)}")
            # Create a valid dictionary
            state_copy = {
                "round": 1,
                "current_turn_index": 0,
                "combatants": []
            }
            # If it's a string, try to parse as JSON
            if isinstance(combat_state, str):
                try:
                    import json
                    parsed = json.loads(combat_state)
                    if isinstance(parsed, dict):
                        state_copy = parsed
                except Exception as e:
                    print(f"[CombatResolver] Failed to parse combat_state as JSON: {e}")
        
        log = []  # Combat log for transparency
        
        # Pre-validate the combat state before starting the thread
        combatants = state_copy.get("combatants", [])
        if not combatants:
            # Emit signal with error
            self.resolution_complete.emit(None, "No combatants in the combat state.")
            return
            
        # Validate that we have at least one monster and one character
        monsters = [c for c in combatants if c.get("type", "").lower() == "monster" and c.get("hp", 0) > 0]
        characters = [c for c in combatants if c.get("type", "").lower() != "monster" and c.get("name", "") != "Add your party here!"]
        
        # Handle the special placeholder "Add your party here!" by converting it to a real character
        for c in combatants:
            if c.get("name", "") == "Add your party here!":
                c["name"] = "Player Character"
                c["type"] = "character"
                c["hp"] = max(20, c.get("hp", 20))
                c["max_hp"] = c.get("max_hp", c["hp"])
                print("[CombatResolver] Converted placeholder to Player Character")
                # Add to characters list
                characters.append(c)
        
        if not monsters:
            # Emit signal with error
            self.resolution_complete.emit(None, "No monsters in the combat. Add at least one monster from the monster panel.")
            return
            
        print(f"[CombatResolver] Combat validation passed: {len(monsters)} monsters and {len(characters)} characters")
        
        def run_resolution():
            try:
                # Use state_copy from outer scope
                state = state_copy
                
                # Ensure state is a dictionary, not a string or other type
                if not isinstance(state, dict):
                    print(f"[CombatResolver] Error: state is not a dictionary in run_resolution, type: {type(state)}")
                    # Emit signal with error
                    self.resolution_complete.emit(None, f"Invalid combat state: {type(state)}")
                    return
                
                # Extract combat state - defensively get values with defaults
                round_num = state.get("round", 1)
                if not isinstance(round_num, int):
                    try:
                        round_num = int(round_num)
                    except (ValueError, TypeError):
                        round_num = 1
                    
                combatants = state.get("combatants", [])
                if not isinstance(combatants, list):
                    print(f"[CombatResolver] Error: combatants is not a list, type: {type(combatants)}")
                    combatants = []
                
                # Sort active combatants by initiative (safely)
                try:
                    active_combatants = sorted(range(len(combatants)), 
                                            key=lambda i: -int(combatants[i].get("initiative", 0)))
                except Exception as e:
                    print(f"[CombatResolver] Error sorting combatants: {e}")
                    active_combatants = list(range(len(combatants)))
                
                max_rounds = 50  # Failsafe to prevent infinite loops
                
                # Main combat loop - continue until only one type of combatant remains or max rounds reached
                while round_num <= max_rounds:
                    print(f"[CombatResolver] Starting round {round_num}")
                    
                    # Check if combat should end
                    remaining_monsters = [c for c in combatants if c.get("type", "").lower() == "monster" and c.get("hp", 0) > 0 and c.get("status", "").lower() != "dead"]
                    remaining_characters = [c for c in combatants if c.get("type", "").lower() != "monster" and (c.get("hp", 0) > 0 or c.get("status", "").lower() == "unconscious" or c.get("status", "").lower() == "stable")]
                    
                    print(f"[CombatResolver] Combat state check: {len(remaining_monsters)} monsters and {len(remaining_characters)} characters remaining")
                    
                    # Determine if combat should end based on remaining factions
                    combat_should_end = False
                    if not remaining_monsters and not remaining_characters:
                        # No one left
                        combat_should_end = True
                        print("[CombatResolver] Combat ending: No combatants left.")
                    elif not remaining_characters:
                        # Only monsters left, end if 1 or 0 remain
                        if len(remaining_monsters) <= 1:
                            combat_should_end = True
                            print("[CombatResolver] Combat ending: Only 1 or 0 monsters left.")
                    elif not remaining_monsters:
                        # Only characters left, combat ends
                        combat_should_end = True
                        print("[CombatResolver] Combat ending: Only characters left.")
                    # Removed the check for failed death saves here, handled within loop

                    # End combat if necessary
                    if combat_should_end:
                        break
                    
                    # Process each combatant's turn in initiative order
                    for idx in active_combatants:
                        if idx >= len(combatants):
                            print(f"[CombatResolver] Error: combatant index {idx} out of range")
                            continue
                            
                        combatant = combatants[idx]
                        
                        # Get the type and determine if it's a monster or character
                        combatant_type = combatant.get("type", "").lower()
                        is_monster = combatant_type == "monster"
                        
                        # Skip dead monsters completely (but not unconscious characters)
                        if is_monster and (combatant.get("hp", 0) <= 0 or combatant.get("status", "").lower() == "dead"):
                            print(f"[CombatResolver] Skipping dead monster: {combatant.get('name', 'Unknown')}")
                            continue
                            
                        # Characters who are unconscious make death saves instead of normal actions
                        if not is_monster and combatant.get("hp", 0) <= 0 and combatant.get("status", "").lower() in ["unconscious", ""]:
                            self._process_death_save(combatant)
                            
                            # Create and add a log entry for the death save
                            turn_log_entry = {
                                "round": round_num,
                                "turn": idx,
                                "actor": combatant.get("name", "Unknown"),
                                "action": "Makes a death saving throw",
                                "dice": [{"expression": "1d20", "result": "See death saves", "purpose": "Death Save"}],
                                "result": f"Current death saves: {combatant.get('death_saves', {}).get('successes', 0)} successes, {combatant.get('death_saves', {}).get('failures', 0)} failures"
                            }
                            log.append(turn_log_entry)
                            
                            # Update the UI for death saves
                            if update_ui_callback:
                                combat_display_state = {
                                    "round": round_num,
                                    "current_turn_index": idx,
                                    "combatants": combatants,
                                    "latest_action": turn_log_entry
                                }
                                update_ui_callback(combat_display_state)
                                time.sleep(0.5)
                                
                            continue
                            
                        # Process normal turn for conscious combatants
                        turn_result = self._process_turn(combatants, idx, round_num, dice_roller)
                        
                        if not turn_result:
                            # Error or timeout processing turn - create a basic result to continue
                            print(f"[CombatResolver] Error processing turn for {combatant.get('name', 'Unknown')} - using fallback")
                            turn_result = {
                                "action": f"{combatant.get('name', 'Unknown')} takes no action due to confusion.",
                                "narrative": f"{combatant.get('name', 'Unknown')} looks confused and takes no action this turn.",
                                "updates": []
                            }
                            
                        # Add turn to log
                        turn_log_entry = {
                            "round": round_num,
                            "turn": idx,
                            "actor": combatant.get("name", "Unknown"),
                            "action": turn_result.get("action", ""),
                            "dice": turn_result.get("dice", []),
                            "result": turn_result.get("narrative", "")
                        }
                        log.append(turn_log_entry)
                        
                        # Apply combatant updates
                        if "updates" in turn_result:
                            # Track combatant HP changes for debugging
                            hp_changes = {}
                            
                            # Create a copy of the original HP values for verification
                            original_hp_values = {c["name"]: c.get("hp", 0) for c in combatants if "name" in c}
                            
                            # Log original HP values before any changes
                            print(f"[CombatResolver] ORIGINAL HP VALUES BEFORE UPDATES:")
                            for name, hp in original_hp_values.items():
                                print(f"[CombatResolver] {name}: {hp}")
                            
                            # STRICTLY validate updates coming from the LLM
                            valid_updates = []
                            for update in turn_result["updates"]:
                                # Skip updates without a name
                                if "name" not in update:
                                    print(f"[CombatResolver] WARNING: Skipping update without 'name' field: {update}")
                                    continue
                                
                                # Verify the named combatant exists
                                target_name = update["name"]
                                target_exists = any(c.get("name") == target_name for c in combatants)
                                if not target_exists:
                                    print(f"[CombatResolver] WARNING: Skipping update for unknown combatant: {target_name}")
                                    continue
                                
                                # Verify HP changes are reasonable if present
                                if "hp" in update:
                                    try:
                                        # Get original HP
                                        orig_hp = original_hp_values.get(target_name, 0)
                                        new_hp = update["hp"]
                                        
                                        # Convert to integer
                                        if isinstance(new_hp, str):
                                            try:
                                                new_hp = int(new_hp)
                                            except ValueError:
                                                print(f"[CombatResolver] WARNING: Invalid HP value {new_hp} for {target_name}, skipping update")
                                                continue
                                        elif not isinstance(new_hp, int):
                                            print(f"[CombatResolver] WARNING: Non-integer HP value {new_hp} for {target_name}, skipping update")
                                            continue
                                            
                                        # Find the combatant
                                        target = next((c for c in combatants if c.get("name") == target_name), None)
                                        if not target:
                                            print(f"[CombatResolver] WARNING: Could not find combatant {target_name}, skipping update")
                                            continue
                                        
                                        # Get max HP
                                        max_hp = target.get("max_hp", orig_hp * 2 if orig_hp > 0 else 100)
                                        
                                        # Calculate the change
                                        hp_change = new_hp - orig_hp
                                        
                                        # Check if the change is reasonable
                                        if hp_change > 0:  # Healing
                                            if new_hp > max_hp * 1.5:  # Cap healing at 150% of max HP
                                                print(f"[CombatResolver] WARNING: Unreasonable HP increase for {target_name}: {orig_hp} -> {new_hp} (max: {max_hp})")
                                                new_hp = max_hp  # Cap at max HP
                                                update["hp"] = new_hp
                                        elif hp_change < 0:  # Damage
                                            # Check if damage is too extreme
                                            if abs(hp_change) > max_hp * 0.9 and max_hp > 20:  # Should not lose more than 90% in one hit for larger creatures
                                                print(f"[CombatResolver] WARNING: Unreasonable HP decrease for {target_name}: {orig_hp} -> {new_hp} (change: {hp_change})")
                                                # Limit damage to 50% of max
                                                new_hp = max(0, orig_hp - int(max_hp * 0.5))
                                                update["hp"] = new_hp
                                        
                                        print(f"[CombatResolver] VALIDATED HP change for {target_name}: {orig_hp} -> {new_hp} (change: {hp_change})")
                                    except Exception as e:
                                        print(f"[CombatResolver] ERROR validating HP for {target_name}: {e}")
                                
                                # Only include valid updates
                                valid_updates.append(update)
                            
                            # Replace with validated updates
                            turn_result["updates"] = valid_updates
                            print(f"[CombatResolver] VALIDATED UPDATES: {valid_updates}")
                            
                            for update in turn_result["updates"]:
                                target_name = update.get("name")
                                
                                # Handle special case for "Nearest Enemy" or similar targets
                                if target_name == "Nearest Enemy" or "Enemy" in target_name:
                                    # Find first enemy of current combatant
                                    enemy_idx = None
                                    for i, c in enumerate(combatants):
                                        # Skip current combatant
                                        if i == idx:
                                            continue
                                        # Found an enemy
                                        enemy_idx = i
                                        break
                                        
                                    if enemy_idx is not None:
                                        target_name = combatants[enemy_idx].get("name", "Unknown")
                                
                                for i, c in enumerate(combatants):
                                    if c.get("name") == target_name:
                                        # Store original values for debugging
                                        original_hp = c.get("hp", 0)
                                        
                                        # Update HP if specified
                                        hp_changed = False
                                        if "hp" in update:
                                            # Ensure HP is an integer using our helper function
                                            try:
                                                # Find the current HP for this combatant
                                                current_hp = c.get("hp", 0)
                                                
                                                # Process the HP update
                                                processed_hp = self._process_hp_update(
                                                    target_name=target_name,
                                                    hp_update=update["hp"],
                                                    current_hp=current_hp
                                                )
                                                
                                                # Update HP if it changed
                                                if processed_hp != current_hp:
                                                    c["hp"] = processed_hp
                                                    hp_changed = True
                                                    print(f"[CombatResolver] Set {target_name}'s HP to {processed_hp} (was {current_hp})")
                                                    
                                                    # Track HP changes for debugging
                                                    hp_changes[target_name] = {
                                                        "before": current_hp,
                                                        "after": processed_hp,
                                                        "change": processed_hp - current_hp
                                                    }
                                            except Exception as e:
                                                print(f"[CombatResolver] Error processing HP update for {target_name}: {str(e)}")

                                        # Update status if specified
                                        status_updated_by_llm = False
                                        if "status" in update:
                                            c["status"] = update["status"]
                                            status_updated_by_llm = True
                                            print(f"[CombatResolver] Updated {target_name}'s status to '{c['status']}' from LLM")

                                        # If HP changed to 0 or below AND status wasn't explicitly set by LLM, apply default status
                                        if hp_changed and c["hp"] <= 0 and not status_updated_by_llm:
                                            if c.get("type", "").lower() == "monster":
                                                c["status"] = "Dead" # Default for monsters
                                                print(f"[CombatResolver] Monster {c.get('name', 'Unknown')} died (default status)")
                                            else:
                                                c["status"] = "Unconscious" # Default for PCs
                                                print(f"[CombatResolver] Character {c.get('name', 'Unknown')} fell unconscious (default status)")
                                                # Initialize death saves only if status is now Unconscious
                                                if "death_saves" not in c:
                                                    c["death_saves"] = {"successes": 0, "failures": 0}

                                        # Initialize death saves if status IS Unconscious (regardless of how it was set)
                                        if c.get("status", "").lower() == "unconscious" and c.get("type", "").lower() != "monster":
                                            if "death_saves" not in c:
                                                c["death_saves"] = {"successes": 0, "failures": 0}

                                        # Update limited-use abilities if specified
                                        if "limited_use" in update:
                                            if "limited_use" not in c:
                                                c["limited_use"] = {}
                                            for ability, state in update["limited_use"].items():
                                                c["limited_use"][ability] = state
                                        # Update death saves if specified (allow LLM to override default init)
                                        if "death_saves" in update:
                                            if "death_saves" not in c:
                                                c["death_saves"] = {"successes": 0, "failures": 0}
                                            c["death_saves"].update(update["death_saves"])

                                            # Check for death save completion immediately after update
                                            if c["death_saves"].get("successes", 0) >= 3:
                                                c["status"] = "Stable"
                                                print(f"[CombatResolver] {c.get('name', 'Unknown')} stabilized")
                                            elif c["death_saves"].get("failures", 0) >= 3:
                                                c["status"] = "Dead"
                                                print(f"[CombatResolver] {c.get('name', 'Unknown')} died from failed death saves")
                        
                        # Update the UI
                        if update_ui_callback:
                            # Create a deep copy of the combatants to ensure latest HP values
                            # are passed to the UI after all updates are applied
                            import copy
                            combatants_updated = copy.deepcopy(combatants)
                            
                            combat_display_state = {
                                "round": round_num,
                                "current_turn_index": idx,
                                "combatants": combatants_updated,
                                "latest_action": turn_log_entry
                            }
                            # Print HP values being sent to UI
                            print(f"\n[CombatResolver] DEBUG: HP VALUES BEING SENT TO UI:")
                            for c in combatants_updated:
                                print(f"[CombatResolver] DEBUG: {c.get('name', 'Unknown')}: HP {c.get('hp', 0)}/{c.get('max_hp', c.get('hp', 0))}")
                            
                            # Give the UI a chance to update between turns
                            update_ui_callback(combat_display_state)
                            # Small delay to let UI update and for more natural combat flow
                            time.sleep(0.5)
                            
                        # After each turn, check if combat is over
                        remaining_monsters = [c for c in combatants if c.get("type", "").lower() == "monster" and c.get("hp", 0) > 0 and c.get("status", "").lower() != "dead"]
                        remaining_characters = [c for c in combatants if c.get("type", "").lower() != "monster" and (c.get("hp", 0) > 0 or c.get("status", "").lower() == "unconscious" or c.get("status", "").lower() == "stable")]
                        
                        # Check end condition again after turn
                        combat_should_end_after_turn = False
                        if not remaining_monsters and not remaining_characters:
                            combat_should_end_after_turn = True
                        elif not remaining_characters:
                            if len(remaining_monsters) <= 1:
                                combat_should_end_after_turn = True
                        elif not remaining_monsters:
                             combat_should_end_after_turn = True
                             
                        if combat_should_end_after_turn:
                            print(f"[CombatResolver] Combat ending after turn: Monsters alive={len(remaining_monsters)}, Characters alive={len(remaining_characters)}")
                            break # Break inner turn loop
                    
                    # Check end condition at end of round (after processing all turns)
                    remaining_monsters_end_round = [c for c in combatants if c.get("type", "").lower() == "monster" and c.get("hp", 0) > 0 and c.get("status", "").lower() != "dead"]
                    remaining_characters_end_round = [c for c in combatants if c.get("type", "").lower() != "monster" and (c.get("hp", 0) > 0 or c.get("status", "").lower() == "unconscious" or c.get("status", "").lower() == "stable")]
                    
                    combat_should_end_end_round = False
                    if not remaining_monsters_end_round and not remaining_characters_end_round:
                        combat_should_end_end_round = True
                    elif not remaining_characters_end_round:
                        if len(remaining_monsters_end_round) <= 1:
                            combat_should_end_end_round = True
                    elif not remaining_monsters_end_round:
                         combat_should_end_end_round = True
                         
                    if combat_should_end_end_round:
                        print(f"[CombatResolver] Combat ending after round: Monsters alive={len(remaining_monsters_end_round)}, Characters alive={len(remaining_characters_end_round)}")
                        break # Break outer round loop
                    
                    # End of round, increment counter
                    round_num += 1
                    
                    # Update round in state dictionary (defensive approach)
                    try:
                        state["round"] = round_num
                    except Exception as e:
                        print(f"[CombatResolver] Error updating round: {e}")
                        # This might mean state was corrupted, recreate it
                        state = {
                            "round": round_num,
                            "current_turn_index": 0,
                            "combatants": combatants
                        }
                    
                    # Update active combatants (some may have died during the round)
                    try:
                        active_combatants = [i for i in sorted(range(len(combatants)), 
                                            key=lambda i: -int(combatants[i].get("initiative", 0))) 
                                            if combatants[i].get("hp", 0) > 0 or (
                                                combatants[i].get("status", "").lower() in ["unconscious", "stable"] and 
                                                combatants[i].get("type", "").lower() != "monster"
                                            )]
                    except Exception as e:
                        print(f"[CombatResolver] Error updating active combatants: {e}")
                        active_combatants = [i for i in range(len(combatants)) if combatants[i].get("hp", 0) > 0]

                    # Print HP changes summary after each turn
                    if hp_changes:
                        print(f"\n[CombatResolver] DEBUG: HP CHANGES THIS TURN:")
                        for name, change in hp_changes.items():
                            print(f"[CombatResolver] DEBUG: {name}: {change['before']} → {change['after']} (Δ {change['change']})")
                        print("")

                    # Verify all HP changes were applied correctly
                    print(f"\n[CombatResolver] DEBUG: VERIFYING HP CHANGES WERE APPLIED CORRECTLY:")
                    for c in combatants:
                        name = c.get("name", "")
                        if name in original_hp_values:
                            orig_hp = original_hp_values[name]
                            new_hp = c.get("hp", 0)
                            if orig_hp != new_hp:
                                print(f"[CombatResolver] DEBUG: {name} HP changed from {orig_hp} to {new_hp}")
                            else:
                                print(f"[CombatResolver] DEBUG: {name} HP unchanged at {new_hp}")
                                
                    # Ensure these changes are reflected in the state dictionary
                    try:
                        # Update state["combatants"] to reflect changes made to combatants list
                        state["combatants"] = combatants
                    except Exception as e:
                        print(f"[CombatResolver] Error updating state combatants: {e}")

                # Prepare final summary
                survivors = [c for c in combatants if c.get("hp", 0) > 0]
                summary = {
                    "narrative": f"Combat ended after {round_num-1} rounds. Survivors: {[c.get('name', 'Unknown') for c in survivors]}",
                    "updates": combatants,
                    "log": log,
                    "rounds": round_num-1
                }
                
                if round_num > max_rounds:
                    summary["narrative"] += " (Stopped due to round limit; possible LLM error)"
                    
                # Emit signal with summary result and no error
                self.resolution_complete.emit(summary, None)
                
            except Exception as e:
                import traceback
                traceback.print_exc()
                # Emit signal with no result and the error message
                self.resolution_complete.emit(None, f"Error in turn-by-turn resolution: {str(e)}")
        
        # Run in a background thread
        threading.Thread(target=run_resolution).start()

    def _process_turn(self, combatants, active_idx, round_num, dice_roller):
        """
        Process a single combatant's turn with LLM.
        
        Args:
            combatants: List of all combatants
            active_idx: Index of active combatant
            round_num: Current round number
            dice_roller: Function to roll dice
            
        Returns:
            Dictionary with turn results or None if error
        """
        try:
            active_combatant = combatants[active_idx]
            print(f"[CombatResolver] Processing turn for {active_combatant.get('name', 'Unknown')} (round {round_num})")
            
            # Import ActionEconomyManager if needed
            from app.combat.action_economy import ActionEconomyManager
            
            # Initialize or reset action economy at the start of the turn
            active_combatant = ActionEconomyManager.initialize_action_economy(active_combatant)
            
            # Debug: Log all combatant HP values at start of turn
            print(f"\n[CombatResolver] DEBUG: CURRENT HP VALUES AT START OF TURN:")
            for i, c in enumerate(combatants):
                print(f"[CombatResolver] DEBUG: Combatant {i}: {c.get('name')} - HP: {c.get('hp', 0)}/{c.get('max_hp', c.get('hp', 0))}")
            
            # Process aura effects at the start of turn
            aura_updates = self._process_auras(active_combatant, combatants)
            if aura_updates:
                print(f"[CombatResolver] Processed {len(aura_updates)} aura effects affecting {active_combatant.get('name', 'Unknown')}")
                for update in aura_updates:
                    print(f"[CombatResolver] Aura effect: {update.get('source')} -> {update.get('target')}: {update.get('effect')}")
                    
                    # Update the combatant in the list after processing aura effects
                    combatants[active_idx] = active_combatant
            else:
                print(f"[CombatResolver] No aura effects processed for {active_combatant.get('name', 'Unknown')}")
                
                # Debug the auras
                active_auras = self._get_active_auras(active_combatant, combatants)
                if active_auras:
                    print(f"[CombatResolver] Found {len(active_auras)} auras that should affect {active_combatant.get('name', 'Unknown')}:")
                    for aura in active_auras:
                        print(f"[CombatResolver] - {aura.get('source')}'s {aura.get('name')} (range: {aura.get('range')}ft, distance: {aura.get('distance')}ft)")
                else:
                    print(f"[CombatResolver] No active auras found for {active_combatant.get('name', 'Unknown')}")
                    
                # Debug aura data on all combatants
                for idx, c in enumerate(combatants):
                    if "auras" in c and c.get("auras"):
                        print(f"[CombatResolver] Combatant {idx} ({c.get('name')}) has {len(c.get('auras'))} defined auras:")
                        for aura_name, aura in c.get("auras", {}).items():
                            aura_range = aura.get("range", 0)
                            affects = aura.get("affects", "unknown")
                            print(f"[CombatResolver] -- {aura_name} (range: {aura_range}ft, affects: {affects})")
            
            # Skip if combatant is dead or has status "Dead"
            if active_combatant.get("hp", 0) <= 0 and active_combatant.get("status", "").lower() == "dead":
                print(f"[CombatResolver] Skipping turn for {active_combatant.get('name', 'Unknown')}: dead or 0 HP")
                # Return a minimal result to avoid None return which would error
                return {
                    "action": f"{active_combatant.get('name', 'Unknown')} is unconscious/dead and skips their turn.",
                    "narrative": f"{active_combatant.get('name', 'Unknown')} is unconscious/dead and skips their turn.",
                    "dice": [],
                    "updates": []
                }
                
            # If aura effects reduced HP to 0, handle that before processing the turn
            if active_combatant.get("hp", 0) <= 0 and active_combatant.get("status", "").lower() != "dead":
                active_combatant["status"] = "Unconscious"
                print(f"[CombatResolver] {active_combatant.get('name', 'Unknown')} was knocked unconscious by aura effects")
                return {
                    "action": f"{active_combatant.get('name', 'Unknown')} falls unconscious due to aura damage.",
                    "narrative": f"{active_combatant.get('name', 'Unknown')} falls unconscious due to aura damage.",
                    "dice": [],
                    "updates": [{
                        "name": active_combatant.get('name', 'Unknown'),
                        "hp": 0,
                        "status": "Unconscious"
                    }],
                    "aura_updates": aura_updates
                }
            
            # 1. Create a prompt for the LLM to decide the action
            prompt = self._create_decision_prompt(combatants, active_idx, round_num)
            
            # 2. Get action decision from LLM
            print(f"[CombatResolver] Requesting action decision from LLM for {active_combatant.get('name', 'Unknown')}")
            try:
                # Prefer GPT-4.1 Mini for fast combat resolution if available
                available_models = self.llm_service.get_available_models()
                model_id = None
                for m in available_models:
                    if m["id"] == ModelInfo.OPENAI_GPT4O_MINI:
                        model_id = m["id"]
                        break
                if not model_id:
                    # Fallback: use first available model
                    model_id = available_models[0]["id"]
                # Now use model_id for LLM calls
                decision_response = self.llm_service.generate_completion(
                    model=model_id,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    max_tokens=800
                )
                print(f"[CombatResolver] Received LLM decision for {active_combatant.get('name', 'Unknown')}")
                print(f"[CombatResolver] Raw decision response: {decision_response!r}")
            except Exception as e:
                print(f"[CombatResolver] Error getting LLM decision: {str(e)}")
                return None
                
            # 3. Parse the LLM's decision
            try:
                # Clean the LLM response to extract JSON properly
                decision_text = decision_response
                
                # Fix 1: Strip code block markers if they exist
                decision_text = re.sub(r'```(?:json)?\s*', '', decision_text)
                decision_text = re.sub(r'```\s*$', '', decision_text)
                
                # Fix 2: Try to extract JSON even if there's other text around it
                json_match = re.search(r'\{[\s\S]*\}', decision_text)
                if not json_match:
                    print(f"[CombatResolver] Could not find JSON in LLM decision response")
                    # Try a fallback approach to create a minimal valid decision
                    print(f"[CombatResolver] Trying to create a fallback decision")
                    action_match = re.search(r'action["\s:]+([^"]+)"', decision_text)
                    fallback_action = "The combatant makes a basic attack." if not action_match else action_match.group(1)
                    
                    # Create a minimal valid decision
                    decision = {
                        "action": fallback_action,
                        "dice_requests": [
                            {"expression": "1d20", "purpose": "Basic attack roll"},
                            {"expression": "1d6", "purpose": "Basic damage roll"}
                        ],
                        "action_type": "action"  # Default action type
                    }
                else:
                    json_str = json_match.group(0)
                    try:
                        decision = json.loads(json_str)
                    except json.JSONDecodeError as e:
                        print(f"[CombatResolver] JSON decode error: {e}")
                        # Try to clean up the JSON string further
                        cleaned_json = re.sub(r',\s*}', '}', json_str)  # Remove trailing commas
                        cleaned_json = re.sub(r',\s*]', ']', cleaned_json)  # Remove trailing commas in arrays
                        try:
                            decision = json.loads(cleaned_json)
                        except json.JSONDecodeError:
                            print(f"[CombatResolver] Failed to parse JSON even after cleanup, creating fallback")
                            # Create fallback decision
                            decision = {
                                "action": "The combatant makes a basic attack after a parsing error.",
                                "dice_requests": [
                                    {"expression": "1d20", "purpose": "Basic attack roll"},
                                    {"expression": "1d6", "purpose": "Basic damage roll"}
                                ],
                                "action_type": "action"  # Default action type
                            }
                
                # Validate required fields and provide defaults if missing
                if "action" not in decision:
                    print(f"[CombatResolver] Missing 'action' field in decision, adding default")
                    decision["action"] = "The combatant takes a defensive stance."
                    
                if "dice_requests" not in decision:
                    print(f"[CombatResolver] Missing 'dice_requests' field in decision, adding default")
                    decision["dice_requests"] = []
                
                # Set default action type if not provided
                if "action_type" not in decision:
                    decision["action_type"] = "action"
                    
                action = decision["action"]
                dice_requests = decision.get("dice_requests", [])
                
                # Extra safety check to ensure dice_requests is a list
                if not isinstance(dice_requests, list):
                    print(f"[CombatResolver] 'dice_requests' is not a list, fixing")
                    dice_requests = []
                    
            except Exception as e:
                print(f"[CombatResolver] Error parsing LLM decision: {str(e)}")
                # Create a very simple fallback
                action = "The combatant takes a cautious action after an error."
                dice_requests = [
                    {"expression": "1d20", "purpose": "Basic roll"}
                ]
                decision = {
                    "action": action,
                    "dice_requests": dice_requests,
                    "action_type": "action"
                }
            
            # 4. Roll dice as requested
            dice_results = []
            try:
                for req in dice_requests:
                    if not isinstance(req, dict):
                        print(f"[CombatResolver] Invalid dice request format: {req}")
                        continue

                    expression = req.get("expression", "")
                    purpose = req.get("purpose", "")
                    if expression:
                        try:
                            result = dice_roller(expression)
                            dice_results.append({
                                "expression": expression,
                                "result": result,
                                "purpose": purpose
                            })
                            print(f"[CombatResolver] Rolled {expression} for {purpose}: {result}")
                        except Exception as e:
                            print(f"[CombatResolver] Error rolling dice: {str(e)}")
                            # Continue with other dice rolls instead of failing completely
                            dice_results.append({
                                "expression": expression,
                                "result": "Error rolling",
                                "purpose": purpose
                            })
            except Exception as e:
                print(f"[CombatResolver] Critical error in dice rolling section: {str(e)}")
                # If we get here, something went very wrong with the dice rolling loop
                # Return a minimal valid result instead of None
                return {
                    "action": action,
                    "narrative": f"The {active_combatant.get('name', 'combatant')} attempted an action but encountered a technical issue.",
                    "updates": [],
                    "dice": []
                }

            # 5. Send dice results to LLM for resolution
            try:
                # Include aura updates in the resolution context
                resolution_prompt = self._create_resolution_prompt(
                    combatants, active_idx, round_num, action, dice_results, aura_updates)
                    
                print(f"[CombatResolver] Requesting resolution from LLM for {active_combatant.get('name', 'Unknown')}")
                resolution_response = self.llm_service.generate_completion(
                    model=model_id,
                    messages=[{"role": "user", "content": resolution_prompt}],
                    temperature=0.7,
                    max_tokens=800
                )
                print(f"[CombatResolver] Received LLM resolution for {active_combatant.get('name', 'Unknown')}")
                print(f"[CombatResolver] Raw resolution response: {resolution_response!r}")
            except Exception as e:
                print(f"[CombatResolver] Error getting LLM resolution: {str(e)}")
                # Create a minimal valid result instead of returning None
                return {
                    "action": action,
                    "narrative": f"The {active_combatant.get('name', 'combatant')} acted, but a technical issue prevented recording the outcome.",
                    "updates": [],
                    "dice": dice_results
                }
                
            # 6. Parse the resolution 
            try:
                # Parse the LLM's resolution 
                resolution_text = resolution_response
                
                # Strip code block markers if they exist
                resolution_text = re.sub(r'```(?:json)?\s*', '', resolution_text)
                resolution_text = re.sub(r'```\s*$', '', resolution_text)
                
                # Try to extract JSON
                json_match = re.search(r'\{[\s\S]*\}', resolution_text)
                if not json_match:
                    print(f"[CombatResolver] Could not find JSON in LLM resolution response")
                    # Create a minimal valid resolution if JSON extraction fails
                    resolution = {
                        "narrative": resolution_text if resolution_text else "The action is completed.",
                        "updates": []
                    }
                else:
                    json_str = json_match.group(0)
                    
                    try:
                        resolution = json.loads(json_str)
                    except json.JSONDecodeError as e:
                        print(f"[CombatResolver] JSON decode error in resolution: {e}")
                        # Try to clean up the JSON string further
                        cleaned_json = re.sub(r',\s*}', '}', json_str)  # Remove trailing commas
                        cleaned_json = re.sub(r',\s*]', ']', cleaned_json)  # Remove trailing commas in arrays
                        
                        try:
                            resolution = json.loads(cleaned_json)
                        except json.JSONDecodeError:
                            print(f"[CombatResolver] Failed to parse JSON resolution even after cleanup")
                            resolution = {
                                "narrative": "The action resolves with technical difficulties.",
                                "updates": []
                            }
                
                # Apply updates from the resolution
                for update in resolution.get("updates", []):
                    # Safety checks
                    if not isinstance(update, dict) or "name" not in update:
                        print(f"[CombatResolver] Invalid update format: {update}")
                        continue
                    
                    # Find the target combatant
                    target_name = update.get("name", "")
                    target_idx = None
                    
                    for i, c in enumerate(combatants):
                        if c.get("name", "") == target_name:
                            target_idx = i
                            break
                    
                    if target_idx is None:
                        print(f"[CombatResolver] Could not find target combatant: {target_name}")
                        
                        # Try to find a similar combatant name (fuzzy matching)
                        best_match = None
                        best_score = 0
                        
                        # Try to find the closest name match
                        for i, c in enumerate(combatants):
                            c_name = c.get("name", "")
                            
                            # Check if either name contains the other
                            if target_name in c_name or c_name in target_name:
                                similarity = min(len(target_name), len(c_name)) / max(len(target_name), len(c_name))
                                if similarity > best_score:
                                    best_score = similarity
                                    best_match = i
                            
                            # Check if they share common words
                            target_words = set(target_name.lower().split())
                            name_words = set(c_name.lower().split())
                            common_words = target_words.intersection(name_words)
                            
                            if common_words and len(common_words) / min(len(target_words), len(name_words)) > best_score:
                                best_score = len(common_words) / min(len(target_words), len(name_words))
                                best_match = i
                        
                        # If we found a good enough match, use it
                        if best_match is not None and best_score > 0.3:
                            target_idx = best_match
                            old_name = target_name
                            new_name = combatants[target_idx].get("name", "")
                            print(f"[CombatResolver] Using similar combatant {new_name} instead of {old_name}")
                            
                            # Also update the narrative to use the correct name
                            if "narrative" in resolution:
                                resolution["narrative"] = resolution["narrative"].replace(old_name, new_name)
                        else:
                            # If the target is the active combatant's type or an enemy, apply to a random enemy
                            active_type = active_combatant.get("type", "unknown")
                            target_is_enemy = True  # Default assumption if target doesn't exist
                            
                            # Check if target name matches common enemy classes
                            enemy_classes = ["goblin", "orc", "warrior", "monster", "enemy", "creature", 
                                            "demon", "dragon", "undead", "zombie", "skeleton", "fighter"]
                            
                            if any(ec in target_name.lower() for ec in enemy_classes):
                                # Look for a valid enemy of the active combatant
                                for i, c in enumerate(combatants):
                                    if c.get("type", "") != active_type:
                                        target_idx = i
                                        old_name = target_name
                                        new_name = combatants[target_idx].get("name", "")
                                        print(f"[CombatResolver] Using enemy {new_name} instead of non-existent {old_name}")
                                        
                                        # Update the narrative to use the correct name
                                        if "narrative" in resolution:
                                            resolution["narrative"] = resolution["narrative"].replace(old_name, new_name)
                                        break
                            else:
                                # If common ally classes, apply to an ally
                                ally_classes = ["ally", "friend", "companion", "paladin", "cleric", "wizard", "ally"]
                                if any(ac in target_name.lower() for ac in ally_classes):
                                    # Look for a valid ally of the active combatant
                                    for i, c in enumerate(combatants):
                                        if c.get("type", "") == active_type and i != active_idx:
                                            target_idx = i
                                            old_name = target_name
                                            new_name = combatants[target_idx].get("name", "")
                                            print(f"[CombatResolver] Using ally {new_name} instead of non-existent {old_name}")
                                            
                                            # Update the narrative to use the correct name
                                            if "narrative" in resolution:
                                                resolution["narrative"] = resolution["narrative"].replace(old_name, new_name)
                                            break
                            
                        # If still no valid target, use the active combatant as a last resort
                        if target_idx is None:
                            # Apply the update to the active combatant as a fallback
                            target_idx = active_idx
                            old_name = target_name
                            new_name = combatants[target_idx].get("name", "")
                            print(f"[CombatResolver] Falling back to active combatant {new_name} instead of {old_name}")
                            
                            # Update the narrative to use the correct name
                            if "narrative" in resolution:
                                resolution["narrative"] = resolution["narrative"].replace(old_name, new_name)
                    
                    # Update HP if present, ensuring it's an integer
                    if "hp" in update:
                        hp_update = update["hp"]
                        current_hp = combatants[target_idx].get("hp", 0)
                        
                        # Process the HP update to ensure it's valid
                        new_hp = self._process_hp_update(combatants[target_idx].get("name", ""), hp_update, current_hp)
                        combatants[target_idx]["hp"] = new_hp
                    
                    # Update status if present
                    if "status" in update:
                        combatants[target_idx]["status"] = update["status"]
                    
                    # Update other fields if present
                    for field in ["limited_use", "spell_slots", "conditions", "death_saves"]:
                        if field in update:
                            combatants[target_idx][field] = update[field]
                
                # Format the result
                result = {
                    "action": action,
                    "narrative": resolution.get("narrative", "The action is resolved."),
                    "updates": resolution.get("updates", []),
                    "dice": dice_results
                }
                
                # If there were aura updates, add them to the result
                if aura_updates and len(aura_updates) > 0:
                    # Add aura information to the result
                    result["aura_updates"] = aura_updates
                    
                    # Ensure the narrative mentions aura effects if they aren't already mentioned
                    aura_narrative = ""
                    for update in aura_updates:
                        source = update.get("source", "Unknown")
                        target = update.get("target", "Unknown")
                        effect = update.get("effect", "Unknown effect")
                        aura_name = update.get("aura", "unnamed aura")
                        
                        # Create a brief description if not already in narrative
                        if source not in result["narrative"] or aura_name not in result["narrative"]:
                            aura_narrative += f"{source}'s {aura_name} affects {target}, causing {effect}. "
                    
                    # Only prepend aura narrative if it's not already mentioned
                    if aura_narrative and "aura" not in result["narrative"].lower():
                        result["narrative"] = f"{aura_narrative}\n\n{result['narrative']}"
                
                # 7. Update action economy based on the decision
                if "action_type" in decision:
                    action_type = decision["action_type"]
                    action_decision = {
                        "action_type": action_type
                    }
                    
                    # Add movement cost if available
                    if "movement_cost" in decision and action_type == "movement":
                        action_decision["movement_cost"] = decision["movement_cost"]
                    
                    # Add legendary action cost if applicable
                    if "legendary_action_cost" in decision and action_type == "legendary_action":
                        action_decision["legendary_action_cost"] = decision["legendary_action_cost"]
                    
                    # Apply the action economy usage
                    active_combatant, success, reason = ActionEconomyManager.process_action_decision(
                        active_combatant, action_decision
                    )
                    
                    # Update the combatant in the list
                    combatants[active_idx] = active_combatant
                    
                    # Add action economy information to the result
                    result_action_economy = {
                        "action_type": action_type,
                        "success": success,
                        "reason": reason if not success else "",
                        "available_actions": ActionEconomyManager.check_available_actions(active_combatant)
                    }
                    
                    if "movement_cost" in decision:
                        result_action_economy["movement_cost"] = decision["movement_cost"]
                        
                    if "legendary_action_cost" in decision:
                        result_action_economy["legendary_action_cost"] = decision["legendary_action_cost"]
                
                    # Add action economy info to the result
                    result["action_economy"] = result_action_economy
                
                return result
            except Exception as e:
                print(f"[CombatResolver] Error processing turn resolution: {str(e)}")
                import traceback
                traceback.print_exc()
                
                # Return a minimal valid result
                return {
                    "action": action,
                    "narrative": f"The {active_combatant.get('name', 'combatant')} takes an action, but a technical issue occurs.",
                    "updates": [],
                    "dice": dice_results
                }
                
        except Exception as e:
            print(f"[CombatResolver] Critical error in _process_turn: {str(e)}")
            import traceback
            traceback.print_exc()
            
            # Return a safe, minimal result rather than None
            return {
                "action": "Technical difficulty occurred",
                "narrative": "A technical issue occurred during this turn. Combat continues.",
                "updates": [],
                "dice": []
            }

    def _create_decision_prompt(self, combatants, active_idx, round_num):
        """
        Create a prompt for the LLM to decide the action for a combatant.
        
        Args:
            combatants: List of all combatants
            active_idx: Index of active combatant
            round_num: Current round number
            
        Returns:
            Prompt string
        """
        active = combatants[active_idx]
        
        # Import ActionEconomyManager if needed for checking available actions
        from app.combat.action_economy import ActionEconomyManager
        
        # Initialize action economy if not already present
        if "action_economy" not in active:
            active = ActionEconomyManager.initialize_action_economy(active)
            
        # Get available actions
        available_actions = ActionEconomyManager.check_available_actions(active)

        # Format active combatant's name and position
        active_name = active.get('name', 'Unknown')
        
        # Format nearby combatants
        nearby = self._get_nearby_combatants(active, combatants)
        nearby_str = self._format_nearby_combatants(nearby)
        
        # Get and format conditions affecting the active combatant
        condition_str = self._format_conditions(active)
        
        # Get active auras affecting the combatant
        active_auras = self._get_active_auras(active, combatants)
        active_auras_str = self._format_active_auras(active_auras)
        num_auras = len(active_auras)
        print(f"[CombatResolver] Found {num_auras} active auras affecting {active_name}")
        
        # Extract abilities and actions the combatant can use
        abilities_str = "No special abilities."
        actions_str = "Basic attack only."
        traits_str = "No special traits."
        
        # Format abilities if present
        if "abilities" in active:
            abilities = active.get("abilities", {})
            if abilities:
                abilities_str = ""
                for name, ability in abilities.items():
                    desc = ability.get("description", "No description")
                    usage = ability.get("usage", "At will")
                    abilities_str += f"- {name}: {desc} ({usage})\n"
        
        # Format actions if present
        if "actions" in active:
            actions_data = active.get("actions", []) # Get actions data, default to empty list
            
            # Check if actions_data is a non-empty list
            if isinstance(actions_data, list) and actions_data: 
                actions_str = ""
                # Iterate over the list of action dictionaries
                for action_dict in actions_data: 
                    # Ensure the item in the list is actually a dictionary
                    if isinstance(action_dict, dict): 
                        # Get action details from the dictionary
                        name = action_dict.get("name", "Unknown Action") 
                        desc = action_dict.get("description", "No description")
                        attack_bonus = action_dict.get("attack_bonus", "")
                        damage = action_dict.get("damage", "")
                        
                        # Format the string based on available details
                        if attack_bonus and damage:
                            actions_str += f"- {name}: {desc} (Attack: +{attack_bonus}, Damage: {damage})\n"
                        else:
                            actions_str += f"- {name}: {desc}\n"
                    else:
                        # Log a warning if an item in the actions list is not a dictionary
                        logging.warning(f"[CombatResolver] Item in actions list for {active.get('name', 'Unknown')} is not a dictionary: {action_dict}")
            # Optional: Handle legacy dictionary format if necessary (add code here if needed)
            # elif isinstance(actions_data, dict) and actions_data:
            #    # ... code to handle dictionary format ...
            #    pass 
            # If actions_data is empty or not a list/dict, actions_str remains "Basic attack only."

        # Format traits if present
        if "traits" in active:
            traits_data = active.get("traits", []) # Get traits data, default to empty list
            
            # Check if traits_data is a non-empty list
            if isinstance(traits_data, list) and traits_data:
                traits_str = ""
                # Iterate over the list of trait dictionaries
                for trait_dict in traits_data:
                    # Ensure the item in the list is a dictionary
                    if isinstance(trait_dict, dict):
                        # Get trait details from the dictionary
                        name = trait_dict.get("name", "Unknown Trait")
                        desc = trait_dict.get("description", "No description")
                        traits_str += f"- {name}: {desc}\n"
                    else:
                        # Log a warning if an item in the traits list is not a dictionary
                        logging.warning(f"[CombatResolver] Item in traits list for {active.get('name', 'Unknown')} is not a dictionary: {trait_dict}")
            # Optional: Handle legacy dictionary format if needed
            # elif isinstance(traits_data, dict) and traits_data:
            #     # ... code to handle dictionary format ...
            #     pass
            # If traits_data is empty or not a list/dict, traits_str remains "No special traits."

        # Basic attacks if no actions are defined
        if actions_str == "Basic attack only.":
            attack_bonus = active.get("attack_bonus", 0)
            damage_dice = active.get("damage_dice", "1d6")
            damage_bonus = active.get("damage_bonus", 0)
            weapon = active.get("weapon", "weapon")
            
            if attack_bonus or damage_dice:
                actions_str = f"- Basic Attack: Attack with {weapon} (Attack: +{attack_bonus}, Damage: {damage_dice}"
                if damage_bonus > 0:
                    actions_str += f"+{damage_bonus}"
                actions_str += ")\n"
        
        # --- BEGIN DEBUG LOGGING ---
        logging.debug(f"[CombatResolver] Decision Prompt Data for {active_name}:")
        logging.debug(f"--- Actions String ---\n{actions_str}")
        logging.debug(f"--- Abilities String ---\n{abilities_str}")
        logging.debug(f"--- Traits String ---\n{traits_str}")
        # --- END DEBUG LOGGING ---
        
        prompt = f"""
You are the tactical combat AI for a D&D 5e game. You decide actions for {active_name}.

# COMBAT SITUATION
Round: {round_num}
Active Combatant: {active_name}

# {active_name.upper()} DETAILS
HP: {active.get('hp', 0)}/{active.get('max_hp', active.get('hp', 0))}
AC: {active.get('ac', 10)}
Type: {active.get('type', 'Unknown')}
Status: {active.get('status', 'OK')}

# AVAILABLE ACTIONS
{active_name} has ALL of the following available this turn:
- A standard ACTION
- A BONUS ACTION
- MOVEMENT up to {active.get('speed', 30)} feet
- A REACTION (if triggered)

# SPECIFIC ABILITIES, ACTIONS AND TRAITS
IMPORTANT: {active_name} can ONLY use the following specific abilities, actions, and traits. DO NOT invent new abilities or modify these in any way.

## Actions:
{actions_str}

## Special Abilities:
{abilities_str}

## Traits:
{traits_str}

# NEARBY COMBATANTS
{nearby_str}

# CURRENT CONDITIONS
{condition_str}
"""
        
        # Add aura information if present
        if active_auras:
            prompt += f"""
# ACTIVE AURAS AFFECTING {active_name}
{active_auras_str}
"""

        prompt += f"""
# YOUR TASK
Decide the most appropriate action for {active_name} this turn. Consider:
1. Tactical position
2. HP status of all combatants
3. STRICTLY USE ONLY the listed abilities and actions - DO NOT INVENT NEW ONES
4. Known enemy capabilities
5. Team strategy (focus fire, crowd control, etc.)

IMPORTANT: {active_name} has FULL ACTIONS available this turn, including standard action, bonus action, and full movement. DO NOT claim the combatant has no actions or movement remaining.

CRITICAL: You MUST choose ONLY from the actions, abilities, and traits explicitly listed above. DO NOT create new abilities or modify the existing ones. Use them exactly as described.

Your response should be a JSON object containing:
{{
  "action": "A detailed description of what the active combatant does, including any choices that affect the game mechanics",
  "dice_requests": [
    {{"expression": "1d20+5", "purpose": "Attack roll"}},
    {{"expression": "2d6+3", "purpose": "Damage roll"}}
  ],
  "action_type": "action/bonus_action/movement/etc.",
  "target": "The target of the action, if applicable"
}}

ACTION: Describe the action and any choices clearly. Be specific about ranges, area effects, etc.
DICE_REQUESTS: List any dice rolls needed to resolve the action with precise expressions and modifiers.
ACTION_TYPE: 'action', 'bonus_action', 'movement', 'reaction', 'legendary_action', or 'none'
TARGET: The target of the action, if applicable. Use exact combatant names, not generic descriptions.

RESPONSE FORMAT EXAMPLES:
For attacks:
{{"action": "The Orc Captain attacks the nearest enemy with its greataxe.", "dice_requests": [{{"expression": "1d20+5", "purpose": "Attack roll"}}, {{"expression": "1d12+3", "purpose": "Damage roll"}}], "action_type": "action", "target": "Fighter"}}

For spells:
{{"action": "The Wizard casts Fireball centered on the group of goblins.", "dice_requests": [{{"expression": "8d6", "purpose": "Fire damage (DEX save DC 15 for half)"}}], "action_type": "action", "target": "Enemy group"}}

For movement:
{{"action": "The Rogue moves 30 feet to get behind the ogre for a flanking position.", "dice_requests": [], "action_type": "movement", "movement_cost": 30}}

For taking no action:
{{"action": "The Goblin is frightened and stunned, unable to act this turn.", "dice_requests": [], "action_type": "none"}}
"""
        return prompt

    def _create_resolution_prompt(self, combatants, active_idx, round_num, action, dice_results, aura_updates=None):
        """
        Create a detailed prompt for the LLM to resolve combat.
        
        Args:
            combatants: List of all combatants
            active_idx: Index of active combatant
            round_num: Current round number
            action: Action description
            dice_results: List of dice roll results
            aura_updates: List of aura effects applied at the start of the turn
            
        Returns:
            Formatted prompt for the LLM
        """
        try:
            # Check for valid indices
            if not combatants or active_idx >= len(combatants):
                print(f"[CombatResolver] Invalid combatants or index: {active_idx}, {len(combatants) if combatants else 0}")
                return ""
                
            active = combatants[active_idx]
            
            # Debug: Log all combatant HP values for debugging
            print(f"\n[CombatResolver] DEBUG: CURRENT HP VALUES IN PROMPT CREATION:")
            for i, c in enumerate(combatants):
                print(f"[CombatResolver] DEBUG: Combatant {i}: {c.get('name')} - HP: {c.get('hp', 0)}/{c.get('max_hp', c.get('hp', 0))}")
            
            # Format active combatant information
            active_name = active.get('name', 'Unknown')
            
            # Format dice results for the prompt
            dice_str = ""
            for dice in dice_results:
                expr = dice.get("expression", "")
                result = dice.get("result", "")
                purpose = dice.get("purpose", "")
                
                dice_str += f"{purpose}: {expr} = {result}\n"
            
            # Format aura updates if provided
            aura_effects_str = ""
            if aura_updates and len(aura_updates) > 0:
                aura_effects_str = "# AURA EFFECTS APPLIED\n"
                for update in aura_updates:
                    source = update.get("source", "Unknown")
                    target = update.get("target", "Unknown")
                    effect = update.get("effect", "Unknown effect")
                    aura_name = update.get("aura", "unnamed aura")
                    
                    # Add HP information if available for damage auras
                    if "hp_before" in update and "hp_after" in update:
                        hp_before = update.get("hp_before", 0)
                        hp_after = update.get("hp_after", 0)
                        aura_effects_str += f"{source}'s {aura_name} affected {target}, causing {effect}. HP: {hp_before} → {hp_after}\n"
                    else:
                        aura_effects_str += f"{source}'s {aura_name} affected {target}, causing {effect}.\n"
                aura_effects_str += "\n"
            
            # Create a detailed prompt
            prompt = f"""
You are the combat AI for a D&D 5e game. Resolve the current action and create a JSON response with a narrative description and updates to any combatants.

# COMBAT STATE 
Round: {round_num}

# COMBATANTS
"""
            
            # Add each combatant with proper indentation
            for combatant in combatants:
                prompt += f"""
{combatant.get('name', 'Unknown')}: 
- HP: {combatant.get('hp', 0)}/{combatant.get('max_hp', combatant.get('hp', 0))}
- AC: {combatant.get('ac', 10)}
- Type: {combatant.get('type', 'Unknown')}
- Status: {combatant.get('status', 'OK')}
"""

            # Add active combatant with proper indentation
            prompt += f"""
# ACTIVE COMBATANT
Name: {active.get('name', 'Unknown')}
HP: {active.get('hp', 0)}/{active.get('max_hp', active.get('hp', 0))}
AC: {active.get('ac', 10)}
Type: {active.get('type', 'Unknown')}
Status: {active.get('status', 'OK')}

"""

            # Add the active combatant's abilities, actions, and traits
            abilities_str = "No special abilities."
            actions_str = "Basic attack only."
            traits_str = "No special traits."
            
            # Format abilities if present
            if "abilities" in active:
                abilities = active.get("abilities", {})
                if abilities:
                    abilities_str = ""
                    for name, ability in abilities.items():
                        desc = ability.get("description", "No description")
                        usage = ability.get("usage", "At will")
                        abilities_str += f"- {name}: {desc} ({usage})\n"
            
            # Format actions if present
            if "actions" in active:
                actions_data = active.get("actions", []) # Get actions data, default to empty list
                
                # Check if actions_data is a non-empty list
                if isinstance(actions_data, list) and actions_data: 
                    actions_str = ""
                    # Iterate over the list of action dictionaries
                    for action_dict in actions_data: 
                        # Ensure the item in the list is actually a dictionary
                        if isinstance(action_dict, dict): 
                            # Get action details from the dictionary
                            name = action_dict.get("name", "Unknown Action") 
                            desc = action_dict.get("description", "No description")
                            attack_bonus = action_dict.get("attack_bonus", "")
                            damage = action_dict.get("damage", "")
                            
                            # Format the string based on available details
                            if attack_bonus and damage:
                                actions_str += f"- {name}: {desc} (Attack: +{attack_bonus}, Damage: {damage})\n"
                            else:
                                actions_str += f"- {name}: {desc}\n"
                        else:
                            # Log a warning if an item in the actions list is not a dictionary
                            logging.warning(f"[CombatResolver] Item in actions list for {active.get('name', 'Unknown')} is not a dictionary: {action_dict}")
                # Optional: Handle legacy dictionary format if necessary (add code here if needed)
                # elif isinstance(actions_data, dict) and actions_data:
                #    # ... code to handle dictionary format ...
                #    pass 
                # If actions_data is empty or not a list/dict, actions_str remains "Basic attack only."

            # Format traits if present
            if "traits" in active:
                traits_data = active.get("traits", []) # Get traits data, default to empty list
                
                # Check if traits_data is a non-empty list
                if isinstance(traits_data, list) and traits_data:
                    traits_str = ""
                    # Iterate over the list of trait dictionaries
                    for trait_dict in traits_data:
                        # Ensure the item in the list is a dictionary
                        if isinstance(trait_dict, dict):
                            # Get trait details from the dictionary
                            name = trait_dict.get("name", "Unknown Trait")
                            desc = trait_dict.get("description", "No description")
                            traits_str += f"- {name}: {desc}\n"
                        else:
                            # Log a warning if an item in the traits list is not a dictionary
                            logging.warning(f"[CombatResolver] Item in traits list for {active.get('name', 'Unknown')} is not a dictionary: {trait_dict}")
                # Optional: Handle legacy dictionary format if needed
                # elif isinstance(traits_data, dict) and traits_data:
                #     # ... code to handle dictionary format ...
                #     pass
                # If traits_data is empty or not a list/dict, traits_str remains "No special traits."

            # --- BEGIN DEBUG LOGGING ---
            logging.debug(f"[CombatResolver] Resolution Prompt - Abilities/Actions/Traits for {active.get('name', 'Unknown')}:")
            logging.debug(f"--- Actions String ---\n{actions_str}")
            logging.debug(f"--- Abilities String ---\n{abilities_str}")
            logging.debug(f"--- Traits String ---\n{traits_str}")
            # --- END DEBUG LOGGING ---
            
            prompt += f"""# ABILITIES, ACTIONS AND TRAITS
IMPORTANT: {active.get('name', 'Unknown')} can ONLY use the following specific abilities, actions, and traits.

## Actions:
{actions_str}

## Special Abilities:
{abilities_str}

## Traits:
{traits_str}

"""

            # Add aura information to the prompt
            active_auras = self._get_active_auras(active, combatants)
            if active_auras:
                active_name = active.get('name', 'Unknown')
                prompt += f"""# ACTIVE AURAS AFFECTING {active_name}
{self._format_active_auras(active_auras)}

"""

            # Include aura effects that were applied at turn start
            if aura_effects_str:
                prompt += aura_effects_str

            prompt += f"""# INTENDED ACTION
{action}

# DICE RESULTS
{dice_str}

# INSTRUCTIONS
1. Create a vivid, exciting narrative of what happens based on the action and dice results
2. If the action was an attack, determine if it hits based on the attack roll vs. target's AC
3. If successful, apply any damage or effects based on the dice results
4. ONLY use abilities and actions listed in the ABILITIES, ACTIONS AND TRAITS section - do NOT invent new ones
5. CRUCIAL: Track final HP values accurately!
6. CRITICALLY IMPORTANT: ONLY use the combatant names exactly as listed above. Do NOT invent new names or refer to generic classes like "Fighter" or "Rogue". Only reference the actual names shown in the COMBATANTS section.
7. DO NOT have combatants use abilities they do not possess. Stay strictly within their defined abilities.

Your response MUST be in JSON format with these fields:
1. "narrative": A vivid description of what happened
2. "updates": Array of objects containing changes to combatants (name, hp, status)

Example:
{{
  "narrative": "Fighter slashes at the Hobgoblin Captain with his longsword. The blade connects with a solid hit, slicing through the hobgoblin's armor and drawing blood. The hobgoblin staggers but remains standing, now visibly wounded. (AC 15 vs. roll 17, hit for 8 damage)",
  "updates": [
    {{
      "name": "Hobgoblin Captain",
      "hp": 24,
      "status": "Wounded"
    }}
  ]
}}

IMPORTANT: 
1. Always include CURRENT HP values in your narrative to help players track the battle state.
2. ALWAYS express HP updates as absolute integer values (e.g., "hp": 24), not as text like "reduce by 5" or relative changes.
3. Your response MUST be valid JSON that can be parsed, with no extra text before or after.
4. For this combat to be interesting, attacks should often hit and do damage. 
5. A roll of 15 or higher almost always hits average AC targets (around 14-16).
6. CRITICAL: Use the exact HP values provided at the start of this prompt. DO NOT RESET TO FULL HP or make up values.
7. Calculate damage from the CURRENT HP values shown at the start of this prompt, not from max HP.
8. EXTREMELY IMPORTANT: Only update combatants that actually exist in this combat. Use EXACT names as shown above, do not make up new combatants like "Goblin", "Fighter", etc.
9. NEVER invent new abilities or actions that are not explicitly listed in the ABILITIES, ACTIONS AND TRAITS section.
"""
            return prompt
        except Exception as e:
            print(f"[CombatResolver] Error creating resolution prompt: {str(e)}")
            import traceback
            traceback.print_exc()
            
            # Return a simplified prompt that still works but has minimal data
            return f"""
You are the combat AI for a D&D 5e game. Create a JSON response with these fields:
- "narrative": A brief description of what happened
- "updates": An array of combatant updates (empty if nothing changed)

Example:
{{
  "narrative": "The combatant attacks but misses.",
  "updates": []
}}

IMPORTANT: Your response MUST be valid JSON with no text before or after.
"""

    def _process_death_save(self, combatant):
        """Process a death save for an unconscious character"""
        import random
        
        # Set up death saves tracking if not present
        if "death_saves" not in combatant:
            combatant["death_saves"] = {
                "successes": 0,
                "failures": 0
            }
        
        # Roll a d20 for the death save
        roll = random.randint(1, 20)
        
        # Natural 20: regain 1 hit point
        if roll == 20:
            combatant["hp"] = 1
            combatant["status"] = "Conscious"
            print(f"[CombatResolver] {combatant['name']} rolled a natural 20 on death save and regains consciousness with 1 HP!")
            return
        
        # Natural 1: two failures
        if roll == 1:
            combatant["death_saves"]["failures"] += 2
            print(f"[CombatResolver] {combatant['name']} rolled a natural 1 on death save - two failures! Now at {combatant['death_saves']['failures']} failures.")
        # 10 or higher: success
        elif roll >= 10:
            combatant["death_saves"]["successes"] += 1
            print(f"[CombatResolver] {combatant['name']} succeeded on death save with {roll}! Now at {combatant['death_saves']['successes']} successes.")
        # Below 10: failure
        else:
            combatant["death_saves"]["failures"] += 1
            print(f"[CombatResolver] {combatant['name']} failed death save with {roll}! Now at {combatant['death_saves']['failures']} failures.")
        
        # Check results
        if combatant["death_saves"]["successes"] >= 3:
            combatant["status"] = "Stable"
            print(f"[CombatResolver] {combatant['name']} is now stable after 3 successful death saves!")
        elif combatant["death_saves"]["failures"] >= 3:
            combatant["status"] = "Dead"
            print(f"[CombatResolver] {combatant['name']} has died after 3 failed death saves!")

    # Keep legacy methods for backwards compatibility
    def resolve_combat_async(self, combat_state, callback):
        # Legacy method retained for backwards compatibility
        print("Legacy resolve_combat_async called - consider using resolve_combat_turn_by_turn instead")
        # Create a simplified prompt
        prompt = self._create_combat_prompt(combat_state)
        
        try:
            # Get available models
            available_models = self.llm_service.get_available_models()
            if not available_models:
                callback(None, "No LLM models available. Check your API keys.")
                return
            model_id = available_models[0]["id"]
            
            # Call the LLM service
            self.llm_service.generate_completion_async(
                model=model_id,
                messages=[{"role": "user", "content": prompt}],
                callback=lambda response, error: self._handle_llm_response(response, error, callback),
                temperature=0.7,
                max_tokens=1000
            )
        except Exception as e:
            callback(None, f"Error calling LLM service: {str(e)}")
            
    def resolve_combat_turn_by_turn_async(self, combat_state, dice_roller, callback):
        # Redirect to the new implementation
        self.resolve_combat_turn_by_turn(combat_state, dice_roller, callback)
        
    # Keep legacy methods for backwards compatibility
    def _create_combat_prompt(self, combat_state):
        # Simplified legacy prompt creation
        round_num = combat_state.get("round", 1)
        combatants = combat_state.get("combatants", [])
        
        combatant_str = "\n".join([
            f"- {c.get('name', 'Unknown')}: HP {c.get('hp', 0)}/{c.get('max_hp', c.get('hp', 0))}, AC {c.get('ac', 10)}, Status: {c.get('status', 'OK')}"
            for c in combatants
        ])
        
        prompt = f"""
You are a Dungeons & Dragons 5e Dungeon Master. Resolve this combat encounter with a brief narrative and status updates.

Combat State:
Round: {round_num}
Combatants:
{combatant_str}

Response format:
{{
  "narrative": "Brief description of combat outcome",
  "updates": [
    {{"name": "Combatant1", "hp": 25, "status": "OK"}},
    ...
  ]
}}

Return ONLY the JSON object with no other text.
"""
        return prompt

    def _handle_llm_response(self, response, error, callback):
        # Legacy handler for backward compatibility
        if error:
            callback(None, f"LLM Error: {error}")
            return
            
        if not response:
            callback(None, "Empty response from LLM")
            return
             
        try:
            # Extract JSON from response
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                json_str = json_match.group(0)
                result = json.loads(json_str)
                callback(result, None)
            else:
                callback(None, f"Could not find JSON in LLM response: {response}")
        except Exception as e:
            callback(None, f"Error parsing LLM response: {str(e)}\nResponse: {response}")

    def _process_hp_update(self, target_name, hp_update, current_hp):
        """
        Process an HP update value to ensure it's valid and properly formatted.
        
        Args:
            target_name: Name of the target combatant
            hp_update: The HP update value (could be integer, string, or None)
            current_hp: The current HP value to compare against
            
        Returns:
            Validated integer HP value
        """
        # If hp_update is None, return the current HP
        if hp_update is None:
            print(f"[CombatResolver] HP update for {target_name} is None, keeping current HP {current_hp}")
            return current_hp
        
        # If hp_update is an integer, use it directly
        if isinstance(hp_update, int):
            print(f"[CombatResolver] HP update for {target_name} is already an integer: {hp_update}")
            return hp_update
            
        # If hp_update is a string, try to convert it to an integer
        if isinstance(hp_update, str):
            # Clean up the string
            hp_str = hp_update.strip()
            
            # Try to extract a plain integer
            try:
                return int(hp_str)
            except ValueError:
                pass
                
            # Try to extract it from a format like "X/Y" (current/max HP)
            try:
                if '/' in hp_str:
                    parts = hp_str.split('/')
                    return int(parts[0].strip())
            except (ValueError, IndexError):
                pass
                
            # Try to handle patterns like "reduced to X" or "takes X damage"
            try:
                if "reduced to " in hp_str.lower():
                    remaining_hp = int(re.search(r'reduced to (\d+)', hp_str.lower()).group(1))
                    return remaining_hp
                elif "takes " in hp_str.lower() and " damage" in hp_str.lower():
                    damage_match = re.search(r'takes (\d+) damage', hp_str.lower())
                    if damage_match and current_hp is not None:
                        damage = int(damage_match.group(1))
                        return max(0, current_hp - damage)
                elif "heals " in hp_str.lower() or "healing " in hp_str.lower():
                    healing_match = re.search(r'(?:heals|healing) (\d+)', hp_str.lower())
                    if healing_match and current_hp is not None:
                        healing = int(healing_match.group(1))
                        return current_hp + healing
            except (ValueError, AttributeError, TypeError):
                pass
        
        # If all else fails, return the current HP or 0 if that's None too
        print(f"[CombatResolver] Could not parse HP update '{hp_update}' for {target_name}, using current HP {current_hp or 0}")
        return current_hp if current_hp is not None else 0 

    def _process_auras(self, active_combatant, all_combatants):
        """
        Process aura effects at the start of a combatant's turn
        
        Args:
            active_combatant: The combatant whose turn is starting
            all_combatants: List of all combatants in the encounter
            
        Returns:
            List of aura effect updates
        """
        updates = []
        
        # Ensure each combatant has auras detected and processed
        for combatant in all_combatants:
            # Add auras if not already present
            if "auras" not in combatant:
                self._add_auras_from_traits(combatant)
        
        # Check for aura effects from all combatants
        for c in all_combatants:
            if "auras" not in c:
                continue
                
            for aura_name, aura in c.get("auras", {}).items():
                # Skip self-auras that don't affect others (unless they're beneficial)
                if c.get("name") == active_combatant.get("name") and not aura.get("affects_self", False):
                    continue
                    
                # Skip auras that don't affect allies/enemies appropriately
                if aura.get("affects", "enemies") == "enemies" and c.get("type") == active_combatant.get("type"):
                    continue
                if aura.get("affects", "enemies") == "allies" and c.get("type") != active_combatant.get("type"):
                    continue
                
                # Check if this combatant is affected by the aura based on distance
                range_feet = aura.get("range", 10)  # Default 10 ft range
                distance = self._get_distance_between(c, active_combatant)
                
                if distance <= range_feet:
                    effect = aura.get("effect", {})
                    effect_type = effect.get("type", "damage")
                    
                    # Process based on effect type
                    if effect_type == "damage":
                        # Get dice expression or default damage amount
                        damage_expr = effect.get("expression", "1d6")
                        
                        # Roll damage using random if dice_roller not available
                        try:
                            import re, random
                            # Simple dice parser for expressions like "2d6+3"
                            dice_match = re.match(r'(\d+)d(\d+)(?:\+(\d+))?', damage_expr)
                            if dice_match:
                                num_dice = int(dice_match.group(1))
                                dice_size = int(dice_match.group(2))
                                modifier = int(dice_match.group(3) or 0)
                                damage = sum(random.randint(1, dice_size) for _ in range(num_dice)) + modifier
                            else:
                                # Default to fixed damage if expression parsing fails
                                damage = int(damage_expr) if damage_expr.isdigit() else 1
                        except Exception as e:
                            print(f"[CombatResolver] Error rolling aura damage: {str(e)}")
                            damage = 1  # Fallback to minimal damage
                        
                        # Apply damage to active combatant
                        damage_type = effect.get("damage_type", "fire")
                        old_hp = active_combatant.get("hp", 0)
                        active_combatant["hp"] = max(0, old_hp - damage)
                        
                        # Record the update
                        updates.append({
                            "source": c.get("name", "Unknown"),
                            "source_type": c.get("type", "unknown"),
                            "aura": aura_name,
                            "target": active_combatant.get("name", "Unknown"),
                            "effect": f"{damage} {damage_type} damage",
                            "hp_before": old_hp,
                            "hp_after": active_combatant.get("hp", 0)
                        })
                        
                    elif effect_type == "condition":
                        # Add condition to active combatant
                        condition = effect.get("condition", "")
                        if condition:
                            if "conditions" not in active_combatant:
                                active_combatant["conditions"] = {}
                            active_combatant["conditions"][condition] = {
                                "source": f"{c.get('name', 'Unknown')}'s {aura_name}",
                                "duration": effect.get("duration", 1)
                            }
                            
                            # Record the update
                            updates.append({
                                "source": c.get("name", "Unknown"),
                                "source_type": c.get("type", "unknown"), 
                                "aura": aura_name,
                                "target": active_combatant.get("name", "Unknown"),
                                "effect": f"Condition: {condition}"
                            })
        
        return updates
    
    def _get_distance_between(self, combatant1, combatant2):
        """Get distance between two combatants in feet"""
        # Check if distances are explicitly defined in position data
        if "position" in combatant1 and "distance_to" in combatant1["position"]:
            target_name = combatant2.get("name", "")
            if target_name in combatant1["position"]["distance_to"]:
                return combatant1["position"]["distance_to"][target_name]
                
        # Default distance if not explicitly defined
        # 5ft for melee range, otherwise large distance (effectively out of range)
        if combatant1.get("type") != combatant2.get("type"):
            return 5  # Assume enemies are in melee range by default
        return 1  # Assume allies are very close by default
    
    def _add_auras_from_traits(self, combatant):
        """
        Analyze combatant traits and detect auras using pattern matching or LLM
        
        Args:
            combatant: The combatant to analyze for auras
            
        Returns:
            Updated combatant with auras field
        """
        # Initialize auras dict if not present
        if "auras" not in combatant:
            combatant["auras"] = {}
            
        # Skip if already processed
        if combatant.get("auras_processed", False):
            return combatant
            
        # Special handling for known monsters with auras
        name = combatant.get("name", "").lower()
        
        # Specific handling for Infernal Tyrant
        if "infernal tyrant" in name or "demon" in name or "devil" in name:
            print(f"[CombatResolver] Adding fire aura to {combatant.get('name', 'Unknown')} based on name")
            combatant["auras"]["fire aura"] = {
                "range": 10,
                "effect": {
                    "type": "damage", 
                    "expression": "1d6", 
                    "damage_type": "fire"
                },
                "affects": "enemies",
                "affects_self": False,
                "source": "infernal_nature"
            }
            
        # Special handling for Magma Mephit
        if "magma" in name or "mephit" in name or "fire elemental" in name:
            print(f"[CombatResolver] Adding fire aura to {combatant.get('name', 'Unknown')} based on name")
            combatant["auras"]["heat aura"] = {
                "range": 5,
                "effect": {
                    "type": "damage", 
                    "expression": "1d4", 
                    "damage_type": "fire"
                },
                "affects": "enemies",
                "affects_self": False,
                "source": "elemental_nature"
            }
            
        # Try pattern matching for common aura types
        traits_data = combatant.get("traits", []) or [] # Get traits data, default to empty list
        actions = combatant.get("actions", {}) or {}
        
        # Ensure traits_data is a list
        if not isinstance(traits_data, list):
            logging.warning(f"[CombatResolver] Traits data for {combatant.get('name', 'Unknown')} is not a list: {traits_data}")
            traits_data = []
            
        # Check trait descriptions for aura keywords
        # Iterate over the list of trait dictionaries
        for trait_dict in traits_data:
            # Ensure the item is a dictionary
            if isinstance(trait_dict, dict):
                trait_name = trait_dict.get("name", "Unknown Trait")
                trait_desc = trait_dict.get("description", "")
                
                if not trait_desc:
                    continue
                    
                trait_text = trait_desc.lower() if isinstance(trait_desc, str) else str(trait_desc).lower()
                
                # Check each common aura type
                for aura_type, aura_info in common_auras.items():
                    if any(keyword in trait_text for keyword in aura_info["keywords"]):
                        # Found a matching aura pattern in traits
                        aura_name_to_add = trait_name # Use the actual trait name
                        combatant["auras"][aura_name_to_add] = {
                            "range": aura_info["range"],
                            "effect": aura_info["effect"],
                            "affects": aura_info["affects"],
                            "affects_self": aura_info.get("affects_self", False),
                            "source": "trait"
                        }
                        print(f"[CombatResolver] Detected {aura_type} ('{aura_name_to_add}') in {combatant.get('name', 'Unknown')}'s traits")
            else:
                logging.warning(f"[CombatResolver] Item in traits list for {combatant.get('name', 'Unknown')} is not a dictionary: {trait_dict}")
        
        # If no auras found through pattern matching, use LLM to detect them
        if not combatant["auras"]:
            # Only use LLM detection if enemy has traits but no detected auras
            if traits or "Monster" in combatant.get("type", ""):
                combatant = self._detect_auras_with_llm(combatant)
                
        # Mark as processed to avoid redundant checks
        combatant["auras_processed"] = True
        return combatant
        
    def _detect_auras_with_llm(self, combatant, default_range=10):
        """
        Use LLM to analyze a combatant's traits and detect potential auras
        
        Args:
            combatant: The combatant to analyze for auras
            default_range: Default aura range if not specified
            
        Returns:
            Updated combatant with detected auras
        """
        # Skip if no LLM service available
        if not hasattr(self, "llm_service"):
            return combatant
            
        # Prepare information about the combatant for analysis
        combatant_info = {
            "name": combatant.get("name", "Unknown"),
            "type": combatant.get("type", ""),
            "traits": combatant.get("traits", {}),
            "actions": combatant.get("actions", {}),
            "abilities": combatant.get("abilities", {})
        }
        
        # Create an analysis prompt for the LLM
        prompt = f"""
You are a D&D 5e rules expert. Analyze this creature's information and identify any aura effects it might have:

{json.dumps(combatant_info, indent=2)}

Only detect auras - magical or supernatural effects that automatically affect creatures near the source.
Examples include:
- Fire auras that deal damage to nearby creatures
- Fear auras that frighten nearby enemies
- Healing auras that restore hit points to allies
- Protection auras that provide resistances or bonuses

Respond with a JSON object containing any detected auras in the following format:
{{
  "has_auras": true/false,
  "auras": {{
    "aura_name": {{
      "range": 10,
      "effect": {{
        "type": "damage/condition/healing/resistance",
        "expression": "dice expression for damage/healing",
        "damage_type": "type of damage",
        "condition": "condition name",
        "duration": duration in rounds
      }},
      "affects": "enemies/allies/all",
      "affects_self": true/false
    }}
  }}
}}

If no auras are detected, return:
{{
  "has_auras": false,
  "auras": {{}}
}}
"""

        try:
            # Request analysis from LLM
            available_models = self.llm_service.get_available_models()
            model_id = available_models[0]["id"] if available_models else None
            
            if not model_id:
                print(f"[CombatResolver] No LLM models available for aura detection")
                return combatant
                
            response = self.llm_service.generate_completion(
                model=model_id,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=800
            )
            
            # Parse the LLM response
            if response:
                # Extract JSON from response
                json_match = re.search(r'\{[\s\S]*\}', response)
                if json_match:
                    result = json.loads(json_match.group(0))
                    
                    if result.get("has_auras", False) and result.get("auras"):
                        # Add detected auras to the combatant
                        for aura_name, aura_info in result["auras"].items():
                            if not combatant.get("auras"):
                                combatant["auras"] = {}
                            
                            # Ensure aura has required fields with defaults
                            if "range" not in aura_info:
                                aura_info["range"] = default_range
                            if "affects" not in aura_info:
                                aura_info["affects"] = "enemies"
                            if "affects_self" not in aura_info:
                                aura_info["affects_self"] = False
                                
                            # Add source information
                            aura_info["source"] = "llm_detected"
                            
                            # Add to combatant's auras
                            combatant["auras"][aura_name] = aura_info
                            print(f"[CombatResolver] LLM detected aura '{aura_name}' for {combatant.get('name', 'Unknown')}")
        
        except Exception as e:
            print(f"[CombatResolver] Error during LLM aura detection: {str(e)}")
            import traceback
            traceback.print_exc()
        
        return combatant 

    def _get_active_auras(self, active_combatant, all_combatants):
        """
        Get a list of auras currently affecting a combatant
        
        Args:
            active_combatant: The combatant to check for affecting auras
            all_combatants: List of all combatants in the encounter
            
        Returns:
            List of aura objects affecting the combatant
        """
        active_auras = []
        
        # Ensure auras have been detected on all combatants
        for combatant in all_combatants:
            if "auras" not in combatant:
                self._add_auras_from_traits(combatant)
        
        # Check each combatant's auras
        for c in all_combatants:
            if "auras" not in c or not c.get("auras"):
                continue
                
            for aura_name, aura in c.get("auras", {}).items():
                # Skip self-auras that don't affect self
                if c.get("name") == active_combatant.get("name") and not aura.get("affects_self", False):
                    continue
                    
                # Skip auras that don't affect allies/enemies appropriately
                if aura.get("affects", "enemies") == "enemies" and c.get("type") == active_combatant.get("type"):
                    continue
                if aura.get("affects", "enemies") == "allies" and c.get("type") != active_combatant.get("type"):
                    continue
                
                # Check if this combatant is within the aura's range
                range_feet = aura.get("range", 10)  # Default 10 ft range
                distance = self._get_distance_between(c, active_combatant)
                
                if distance <= range_feet:
                    active_auras.append({
                        "name": aura_name,
                        "source": c.get("name", "Unknown"),
                        "range": range_feet,
                        "effect": aura.get("effect", {}),
                        "distance": distance
                    })
        
        return active_auras
    
    def _format_active_auras(self, auras):
        """
        Format a list of active auras into a readable string
        
        Args:
            auras: List of aura objects affecting a combatant
            
        Returns:
            Formatted string describing the auras
        """
        if not auras:
            return "None"
            
        aura_strings = []
        for aura in auras:
            effect = aura.get("effect", {})
            effect_type = effect.get("type", "unknown")
            source = aura.get("source", "Unknown")
            name = aura.get("name", "unnamed aura")
            distance = aura.get("distance", 0)
            
            effect_desc = ""
            if effect_type == "damage":
                damage_expr = effect.get("expression", "")
                damage_type = effect.get("damage_type", "unspecified")
                effect_desc = f"{damage_expr} {damage_type} damage"
            elif effect_type == "condition":
                condition = effect.get("condition", "")
                effect_desc = f"applies {condition} condition"
            elif effect_type == "healing":
                healing_expr = effect.get("expression", "")
                effect_desc = f"heals {healing_expr} per turn"
            elif effect_type == "resistance":
                damage_types = effect.get("damage_types", [])
                types_str = ", ".join(damage_types)
                effect_desc = f"grants resistance to {types_str}"
                
            aura_strings.append(f"{source}'s {name} ({distance}ft away) - {effect_desc}")
            
        return "\n".join(aura_strings)

    def _get_nearby_combatants(self, active_combatant, all_combatants):
        """
        Get a list of nearby combatants for the active combatant
        
        Args:
            active_combatant: The combatant to check for nearby combatants
            all_combatants: List of all combatants in the encounter
            
        Returns:
            List of nearby combatants
        """
        nearby = []
        
        # Check for nearby enemies
        for c in all_combatants:
            if c.get("type", "").lower() == "monster" and c.get("hp", 0) > 0:
                nearby.append(c)
        
        # Check for nearby allies
        for c in all_combatants:
            if c.get("type", "").lower() != "monster" and c.get("name", "") != "Add your party here!":
                nearby.append(c)
        
        return nearby

    def _format_nearby_combatants(self, nearby):
        """
        Format a list of nearby combatants into a readable string
        
        Args:
            nearby: List of nearby combatants
            
        Returns:
            Formatted string describing the nearby combatants
        """
        if not nearby:
            return "None"
        
        nearby_str = "\n".join([f"- {c.get('name', 'Unknown')} (HP: {c.get('hp', 0)}/{c.get('max_hp', c.get('hp', 0))}, AC: {c.get('ac', 10)}, Status: {c.get('status', 'OK')})" for c in nearby])
        return nearby_str

    def _format_conditions(self, combatant):
        """
        Format a list of conditions affecting the combatant
        
        Args:
            combatant: The combatant to check for conditions
            
        Returns:
            Formatted string describing the conditions
        """
        conditions = []
        
        # Check for blinded condition
        if combatant.get("blinded", False):
            conditions.append("Blinded: Cannot see, has disadvantage on attacks, grants advantage to attackers")
        
        # Check for frightened condition
        if combatant.get("frightened", False):
            conditions.append("Frightened: Has disadvantage on attacks while source of fear is in sight")
        
        # Check for invisible condition
        if combatant.get("invisible", False):
            conditions.append("Invisible: Has advantage on attacks, attacks against it have disadvantage")
        
        # Check for paralyzed condition
        if combatant.get("paralyzed", False):
            conditions.append("Paralyzed: Grants advantage on attacks, auto-crits if attacker within 5 feet")
        
        # Check for poisoned condition
        if combatant.get("poisoned", False):
            conditions.append("Poisoned: Has disadvantage on attacks and ability checks")
        
        # Check for prone condition
        if combatant.get("prone", False):
            conditions.append("Prone: Has disadvantage on attacks, grants advantage on attacks against it within 5 feet, grants disadvantage on ranged attacks against it")
        
        # Check for restrained condition
        if combatant.get("restrained", False):
            conditions.append("Restrained: Has disadvantage on attacks, grants advantage to attackers")
        
        # Check for stunned condition
        if combatant.get("stunned", False):
            conditions.append("Stunned: Grants advantage on attacks")
        
        # Check for unconscious condition
        if combatant.get("unconscious", False):
            conditions.append("Unconscious: Grants advantage on attacks, auto-crits if attacker within 5 feet")
        
        return "\n".join(conditions) if conditions else "No conditions affecting the combatant."