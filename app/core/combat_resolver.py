"""
Core component for resolving combat encounters using LLM.

This class takes the current combat state and uses an LLM to generate
tactical decisions, which are then executed with dice rolls and
properly reflected in the UI.
"""

from app.core.llm_service import LLMService, ModelInfo
import json as _json
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
        self.previous_turn_summaries = []  # NEW: Track previous turn results for LLM context

    # ---------------------------------------------------------------------
    # Helper to build LLM messages with previous turn context
    # ---------------------------------------------------------------------
    def build_llm_messages(self, previous_turn_summaries, current_prompt):
        """
        Build a list of LLM chat messages including previous turn summaries as system messages.
        Args:
            previous_turn_summaries (list of str): Summaries of previous turns
            current_prompt (str): The prompt for the current turn
        Returns:
            list: List of message dicts for LLM chat API
        """
        messages = []
        for summary in previous_turn_summaries:
            messages.append({"role": "system", "content": summary})
        messages.append({"role": "user", "content": current_prompt})
        return messages

    def resolve_combat_turn_by_turn(self, combat_state, dice_roller, callback, update_ui_callback=None):
        """
        Resolve combat turn-by-turn, with proper UI feedback.
        
        Args:
            combat_state: Dictionary with current combat state (combatants, round, etc.)
            dice_roller: Function that rolls dice (takes expression, returns result)
            callback: Function called with final result or error (DEPRECATED - Use resolution_complete signal)
            update_ui_callback: Function called after each turn to update UI (optional)
        """
        logging.debug("--- ENTERING resolve_combat_turn_by_turn ---") # TEST LOG
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
                    parsed = _json.loads(combat_state)
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
        
        def run_resolution():
            logging.debug("--- ENTERING run_resolution thread ---") # TEST LOG
            try:
                state = state_copy
                if not isinstance(state, dict):
                    print(f"[CombatResolver] Error: state is not a dictionary in run_resolution, type: {type(state)}")
                    self.resolution_complete.emit(None, f"Invalid combat state: {type(state)}")
                    return
                round_num = state.get("round", 1)
                combatants = state.get("combatants", [])
                turn_idx = state.get("current_turn_index", 0)
                
                # Main combat loop - continue until only one type of combatant remains or max rounds reached
                while round_num <= 50:
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
                    
                    # End combat if necessary
                    if combat_should_end:
                        break
                    
                    # Process each combatant's turn in initiative order
                    for idx in sorted(range(len(combatants)), key=lambda i: -int(combatants[i].get("initiative", 0))):
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
                            print(f"\n[CombatResolver] ORIGINAL HP VALUES BEFORE UPDATES:")
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
                                                print(f"[CombatResolver] WARNING: Unreasonable HP increase for {target_name}: {orig_hp} → {new_hp} (max: {max_hp})")
                                                new_hp = max_hp  # Cap at max HP
                                                update["hp"] = new_hp
                                        elif hp_change < 0:  # Damage
                                            # Check if damage is too extreme
                                            if abs(hp_change) > max_hp * 0.9 and max_hp > 20:  # Should not lose more than 90% in one hit for larger creatures
                                                print(f"[CombatResolver] WARNING: Unreasonable HP decrease for {target_name}: {orig_hp} → {new_hp} (change: {hp_change})")
                                                # Limit damage to 50% of max
                                                new_hp = max(0, orig_hp - int(max_hp * 0.5))
                                                update["hp"] = new_hp
                                        
                                        print(f"[CombatResolver] VALIDATED HP change for {target_name}: {orig_hp} → {new_hp} (change: {hp_change})")
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
                        
                        # Update the UI *before* checking end condition based on this turn's results
                        if update_ui_callback:
                            import copy
                            combatants_updated = copy.deepcopy(combatants)
                            combat_display_state = {
                                "round": round_num,
                                "current_turn_index": idx,
                                "combatants": combatants_updated,
                                "latest_action": turn_log_entry
                            }
                            print(f"\n[CombatResolver] DEBUG: HP VALUES BEING SENT TO UI (End of {combatant.get('name')}'s turn):")
                            for c in combatants_updated:
                                print(f"[CombatResolver] DEBUG:   {c.get('name', 'Unknown')}: HP {c.get('hp', 0)}/{c.get('max_hp', c.get('hp', 0))}, Status: {c.get('status', '')}")
                            update_ui_callback(combat_display_state)
                            time.sleep(0.5) # Small delay

                        # --- BEGIN ADDED DEBUG LOGGING (Moved after UI update) ---
                        print(f"\n[CombatResolver] DEBUG: STATE BEFORE END CHECK (Round {round_num}, After Actor: {combatant.get('name')}'s turn)")
                        for check_c in combatants: # Check the main combatants list
                            print(f"[CombatResolver] DEBUG:   {check_c.get('name', 'Unknown')}: HP {check_c.get('hp', 'N/A')}, Status '{check_c.get('status', 'N/A')}', Type '{check_c.get('type', 'N/A')}'")
                        # --- END ADDED DEBUG LOGGING ---

                        # After each turn, check if combat is over
                        remaining_monsters = [c for c in combatants if c.get("type", "").lower() == "monster" and c.get("hp", 0) > 0 and c.get("status", "").lower() != "dead"]
                        remaining_characters = [c for c in combatants if c.get("type", "").lower() != "monster" and (c.get("hp", 0) > 0 or c.get("status", "").lower() in ["unconscious", "stable"])]

                        # Check end condition again after turn
                        combat_should_end_after_turn = False
                        if not remaining_monsters and not remaining_characters: # Both sides wiped?
                            print("[CombatResolver] Ending check: Both sides wiped.")
                            combat_should_end_after_turn = True
                        elif not remaining_characters: # Only monsters left?
                            # Only end if 1 or 0 monsters are left
                            if len(remaining_monsters) <= 1:
                                print("[CombatResolver] Ending check: No characters remaining and <=1 monster left (Monsters win/Last monster standing).")
                                combat_should_end_after_turn = True
                            else:
                                print(f"[CombatResolver] End check: No characters, but {len(remaining_monsters)} monsters remain. Combat continues.")
                        elif not remaining_monsters: # Only characters left?
                             print("[CombatResolver] Ending check: No monsters remaining (Characters win).")
                             combat_should_end_after_turn = True

                        if combat_should_end_after_turn:
                            print(f"[CombatResolver] Combat ending after turn: Monsters alive={len(remaining_monsters)}, Characters alive={len(remaining_characters)}")
                            break # Break inner turn loop

                    # --- End of turn loop ('for idx in ...') ---

                    # Check if the inner loop was broken by an end condition
                    if combat_should_end_after_turn:
                        print(f"[CombatResolver] Breaking outer round loop due to end condition after turn.")
                        break # Break outer round loop

                    # End of round processing (only if inner loop completed naturally)
                    # ... (existing end of round code: increment round_num, update state, etc.) ...

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

                    # --- BEGIN ADDED DEBUG LOGGING ---
                    print(f"\n[CombatResolver] DEBUG: STATE BEFORE END CHECK (Round {round_num}, Actor: {combatant.get('name')})")
                    for check_c in combatants:
                        print(f"[CombatResolver] DEBUG:   {check_c.get('name', 'Unknown')}: HP {check_c.get('hp', 'N/A')}, Status '{check_c.get('status', 'N/A')}', Type '{check_c.get('type', 'N/A')}'")
                    # --- END ADDED DEBUG LOGGING ---

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
                
                # Prepare final summary
                survivors = [c for c in combatants if c.get("hp", 0) > 0]
                summary = {
                    "narrative": f"Combat ended after {round_num-1} rounds. Survivors: {[c.get('name', 'Unknown') for c in survivors]}",
                    "updates": combatants,
                    "log": log,
                    "rounds": round_num-1
                }
                
                if round_num > 50:
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

    def _process_recharge_abilities(self, combatant, dice_roller):
        """Process recharge abilities: roll d6 to recharge limited-use abilities based on recharge_text."""
        import re
        # Iterate through each limited-use ability and attempt recharge if not already available
        for name, info in combatant.get("recharge_abilities", {}).items():
            if not info.get("available", False):
                recharge_text = info.get("recharge_text", "")
                # Determine recharge range e.g. '5-6'
                match = re.search(r'(\d+)\s*-\s*(\d+)', recharge_text)
                if match:
                    low, high = int(match.group(1)), int(match.group(2))
                else:
                    low, high = 6, 6
                # Roll a d6 to check for recharge
                try:
                    roll = dice_roller("1d6")
                except Exception as e:
                    print(f"[CombatResolver] Error rolling recharge d6 for {combatant.get('name')}'s {name}: {e}")
                    continue
                # Check roll outcome
                if isinstance(roll, int) and low <= roll <= high:
                    info["available"] = True
                    print(f"[CombatResolver] {combatant.get('name')} recharge roll for '{name}': {roll} (in {low}-{high}), now AVAILABLE")
                else:
                    print(f"[CombatResolver] {combatant.get('name')} recharge roll for '{name}': {roll} (not in {low}-{high}), still unavailable")
        # Return combatant with updated availability flags
        return combatant

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
        logging.debug(f"--- ENTERING _process_turn for index {active_idx}, round {round_num} ---") # TEST LOG
        import json  # Import json at the function level to ensure it's available
        import re
        
        # Ensure dice_results is always defined to prevent NameError in error/fallback cases
        dice_results = []
        try:
            active_combatant = combatants[active_idx]
            print(f"[CombatResolver] Processing turn for {active_combatant.get('name', 'Unknown')} (round {round_num})")
            
            # Import ActionEconomyManager if needed
            from app.combat.action_economy import ActionEconomyManager
            
            # Initialize or reset action economy at the start of the turn
            active_combatant = ActionEconomyManager.initialize_action_economy(active_combatant)
            
            # Process recharge abilities for monsters
            if active_combatant.get("type", "").lower() == "monster":
                self._process_recharge_abilities(active_combatant, dice_roller)
            
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
            # Prepare combat_state and turn_combatant for prompt creation
            combat_state = {"combatants": combatants, "turn_number": round_num}
            turn_combatant = combatants[active_idx]
            prompt = self._create_decision_prompt(combat_state, turn_combatant)
            
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
                print(f"[CombatResolver] Sending prompt to LLM:\n{prompt}\n---END PROMPT---")
                decision_response = self.llm_service.generate_completion(
                    model=model_id,
                    messages=self.build_llm_messages(self.previous_turn_summaries, prompt),
                    temperature=0.7,
                    max_tokens=800
                )
                print(f"[CombatResolver] Received LLM decision for {active_combatant.get('name', 'Unknown')}")
                print(f"[CombatResolver] Raw decision response TYPE: {type(decision_response).__name__}")
                print(f"[CombatResolver] Raw decision response VALUE: {decision_response!r}")
                
                # Extended debugging to understand resolution response
                print(f"[CombatResolver] *** RESOLUTION DEBUG ***")
                print(f"[CombatResolver] Resolution type: {type(decision_response).__name__}")
                if isinstance(decision_response, str):
                    print(f"[CombatResolver] First 100 chars: {decision_response[:100]}...")
                    if "```json" in decision_response or "```" in decision_response:
                        print(f"[CombatResolver] Contains code block markers")
                
                # --- FIX: Parse JSON if needed (strip code block markers first) ---
                if isinstance(decision_response, str):
                    cleaned = decision_response.strip()
                    # Multiple cleanup attempts in sequence, from most specific to general
                    
                    # 1. Try to extract JSON specifically marked with ```json
                    if "```json" in cleaned:
                        json_parts = cleaned.split("```json")
                        if len(json_parts) > 1:
                            json_content = json_parts[1].split("```")[0].strip()
                            print(f"[CombatResolver] Extracted JSON from ```json block: {json_content[:100]}...")
                            try:
                                parsed_decision = json.loads(json_content)
                                print(f"[CombatResolver] Successfully parsed JSON from ```json block")
                                decision_response = parsed_decision
                            except Exception as e:
                                print(f"[CombatResolver] Error parsing JSON from ```json block: {e}")
                                # Continue to next cleanup approach
                        
                    # 2. Try to extract content from any ``` code block
                    if isinstance(decision_response, str) and "```" in cleaned:
                        # Get content between first ``` and last ```
                        parts = cleaned.split("```")
                        if len(parts) >= 3:  # At least one complete code block
                            # Take the first complete code block (parts[1])
                            code_content = parts[1].strip()
                            print(f"[CombatResolver] Extracted from generic code block: {code_content[:100]}...")
                            try:
                                parsed_decision = json.loads(code_content)
                                print(f"[CombatResolver] Successfully parsed JSON from generic code block")
                                decision_response = parsed_decision
                            except Exception as e:
                                print(f"[CombatResolver] Error parsing content from generic code block: {e}")
                                # Continue to next cleanup approach
                        
                    # 3. Try standard cleanup (removing all code markers)
                    if isinstance(decision_response, str):
                        cleaned = re.sub(r'```(?:json)?\s*', '', cleaned)
                        cleaned = re.sub(r'```\s*$', '', cleaned)
                        cleaned = cleaned.strip()
                        print(f"[CombatResolver] Standard cleanup result: {cleaned[:100]}...")
                        try:
                            parsed_decision = json.loads(cleaned)
                            print(f"[CombatResolver] Successfully parsed JSON after standard cleanup")
                            decision_response = parsed_decision
                        except Exception as e:
                            print(f"[CombatResolver] Failed to parse JSON after standard cleanup: {e}")
                                
                            # 4. Try to find JSON object pattern anywhere in the string
                            json_match = re.search(r'\{[\s\S]*\}', cleaned)
                            if json_match:
                                json_str = json_match.group(0)
                                print(f"[CombatResolver] Found JSON-like pattern: {json_str[:100]}...")
                                try:
                                    parsed_decision = json.loads(json_str)
                                    print(f"[CombatResolver] Successfully parsed JSON from pattern match")
                                    decision_response = parsed_decision
                                except Exception as e:
                                    print(f"[CombatResolver] Error parsing JSON pattern: {e}")
                
                    # If still a string after all attempts, log this clearly
                    if isinstance(decision_response, str):
                        print(f"[CombatResolver] WARNING: All JSON parsing attempts failed. Using string as fallback.")
                    else:
                        print(f"[CombatResolver] Successfully converted LLM decision to dictionary")
                    
                    # ---END FIX ---
            except Exception as e:
                import traceback
                print(f"[CombatResolver] Error getting LLM decision: {str(e)}")
                traceback.print_exc()
                
                # Create a minimal valid result instead of returning None
                result = {
                    "action": "The combatant takes a defensive stance.",
                    "narrative": f"The {active_combatant.get('name', 'combatant')} acted, but a technical issue prevented recording the outcome.",
                        "updates": [],
                        "dice": []
                    }
                    
                    # Try to salvage some outcome based on the dice that were rolled
                if 'dice_results' in locals() and 'target' in locals() and dice_results and target and target.lower() != "none":
                        damage_dice = [d for d in dice_results if "damage" in d.get("purpose", "").lower()]
                        attack_rolls = [d for d in dice_results if "attack" in d.get("purpose", "").lower()]
                        
                        if damage_dice:
                            damage_amount = int(damage_dice[0].get("result", 0))
                                # If we have attack rolls and a target with AC, check if it hit
                            if attack_rolls:
                                try:
                                    attack_value = int(attack_rolls[0].get("result", 0))
                                    target_obj = next((c for c in combatants if c.get("name") == target), None)
                                    if target_obj:
                                        target_ac = target_obj.get("ac", 15)
                                        if attack_value >= target_ac:
                                            # Attack hit, apply damage
                                            current_hp = target_obj.get("hp", 0)
                                            new_hp = max(0, current_hp - damage_amount)
                                            print(f"[CombatResolver] Salvaging outcome: {attack_value} hits AC {target_ac}, applying {damage_amount} damage")
                                            result["updates"] = [{"name": target, "hp": new_hp}]
                                            result["narrative"] = f"{active_combatant.get('name')} attacks {target} and hits ({attack_value} vs AC {target_ac}), dealing {damage_amount} damage."
                                        else:
                                            # Attack missed
                                            print(f"[CombatResolver] Salvaging outcome: {attack_value} misses AC {target_ac}")
                                            result["narrative"] = f"{active_combatant.get('name')} attacks {target} but misses ({attack_value} vs AC {target_ac})."
                                except (ValueError, TypeError):
                                    print(f"[CombatResolver] Could not parse attack roll when salvaging outcome")
                        if damage_dice:
                            try:
                                damage_amount = int(damage_dice[0].get("result", 0))
                                # If we have attack rolls and a target with AC, check if it hit
                                if attack_rolls:
                                    try:
                                        attack_value = int(attack_rolls[0].get("result", 0))
                                        target_obj = next((c for c in combatants if c.get("name") == target), None)
                                        if target_obj:
                                            target_ac = target_obj.get("ac", 15)
                                            if attack_value >= target_ac:
                                                # Attack hit, apply damage
                                                current_hp = target_obj.get("hp", 0)
                                                new_hp = max(0, current_hp - damage_amount)
                                                print(f"[CombatResolver] Salvaging outcome in fallback: {attack_value} hits AC {target_ac}, applying {damage_amount} damage")
                                                result["updates"] = [{"name": target, "hp": new_hp}]
                                                result["narrative"] = f"{active_combatant.get('name')} attacks {target} and hits ({attack_value} vs AC {target_ac}), dealing {damage_amount} damage."
                                            else:
                                                # Attack missed
                                                print(f"[CombatResolver] Salvaging outcome in fallback: {attack_value} misses AC {target_ac}")
                                                result["narrative"] = f"{active_combatant.get('name')} attacks {target} but misses ({attack_value} vs AC {target_ac})."
                                    except (ValueError, TypeError):
                                        print(f"[CombatResolver] Could not parse attack roll when salvaging outcome in fallback")
                            except (ValueError, TypeError):
                                print(f"[CombatResolver] Could not parse damage roll when salvaging outcome in fallback")
                
                print(f"[CombatResolver] Returning salvaged result: {result}")
                return result
            except Exception as e:
                print(f"[CombatResolver] Error getting LLM decision: {str(e)}")
                import traceback
                traceback.print_exc()
                
                # Create a minimal valid result instead of returning None
                result = {
                    "action": "The combatant takes a defensive stance.",
                    "narrative": f"The {active_combatant.get('name', 'combatant')} acted, but a technical issue prevented recording the outcome.",
                    "updates": [],
                    "dice": []
                }
                
                # Try to salvage some outcome based on the dice that were rolled
                if 'dice_results' in locals() and 'target' in locals() and dice_results and target and target.lower() != "none":
                    damage_dice = [d for d in dice_results if "damage" in d.get("purpose", "").lower()]
                    attack_rolls = [d for d in dice_results if "attack" in d.get("purpose", "").lower()]
                    
                    if damage_dice:
                        try:
                            damage_amount = int(damage_dice[0].get("result", 0))
                            # If we have attack rolls and a target with AC, check if it hit
                            if attack_rolls:
                                try:
                                    attack_value = int(attack_rolls[0].get("result", 0))
                                    target_obj = next((c for c in combatants if c.get("name") == target), None)
                                    if target_obj:
                                        target_ac = target_obj.get("ac", 15)
                                        if attack_value >= target_ac:
                                            # Attack hit, apply damage
                                            current_hp = target_obj.get("hp", 0)
                                            new_hp = max(0, current_hp - damage_amount)
                                            print(f"[CombatResolver] Salvaging outcome in fallback: {attack_value} hits AC {target_ac}, applying {damage_amount} damage")
                                            result["updates"] = [{"name": target, "hp": new_hp}]
                                            result["narrative"] = f"{active_combatant.get('name')} attacks {target} and hits ({attack_value} vs AC {target_ac}), dealing {damage_amount} damage."
                                        else:
                                            # Attack missed
                                            print(f"[CombatResolver] Salvaging outcome in fallback: {attack_value} misses AC {target_ac}")
                                            result["narrative"] = f"{active_combatant.get('name')} attacks {target} but misses ({attack_value} vs AC {target_ac})."
                                except (ValueError, TypeError):
                                    print(f"[CombatResolver] Could not parse attack roll when salvaging outcome in fallback")
                        except (ValueError, TypeError):
                            print(f"[CombatResolver] Could not parse damage roll when salvaging outcome in fallback")
                
                print(f"[CombatResolver] Returning salvaged fallback result: {result}")
                return result
            # 6. Parse the resolution 
            try:
                # Parse the LLM's resolution 
                print(f"[CombatResolver] About to parse LLM resolution: {decision_response!r}")
                resolution_text = decision_response
                # If already a dict, use it directly
                if isinstance(resolution_text, dict):
                    resolution = resolution_text
                    print(f"[CombatResolver] Using parsed LLM resolution as dict: {resolution}")
                else:
                    # One more attempt to handle string responses robustly
                    print(f"[CombatResolver] Last attempt to parse string resolution: {resolution_text[:150]}...")
                    
                    # Try to extract JSON object
                    json_match = re.search(r'\{[\s\S]*\}', resolution_text)
                    if not json_match:
                        print(f"[CombatResolver] Could not find JSON in LLM resolution response")
                        # Create a minimal valid resolution with the full text as description
                        resolution = {
                            "description": resolution_text,
                            "narrative": resolution_text,
                            "updates": []
                        }
                        
                        # Try to extract damage information from plain text
                        damage_match = re.search(r'(\d+)\s*damage', resolution_text)
                        if damage_match and 'target' in locals() and target and target.lower() != "none":
                            damage_amount = int(damage_match.group(1))
                            # Create or update damage value for target
                            resolution["damage_dealt"] = {target: damage_amount}
                            print(f"[CombatResolver] Extracted damage amount from text: {damage_amount}")
                    else:
                        json_str = json_match.group(0)
                        print(f"[CombatResolver] Found JSON string: {json_str[:100]}...")
                        try:
                            resolution = json.loads(json_str)
                            print(f"[CombatResolver] Parsed LLM resolution as JSON (from string): {resolution}")
                        except json.JSONDecodeError as e:  # Use json instead of _json
                            print(f"[CombatResolver] JSON decode error in resolution: {e}")
                            # Try to clean up the JSON string further
                            cleaned_json = re.sub(r',\s*}', '}', json_str)  # Remove trailing commas
                            cleaned_json = re.sub(r',\s*]', ']', cleaned_json)  # Remove trailing commas in arrays
                            print(f"[CombatResolver] Cleaned JSON: {cleaned_json[:100]}...")
                            try:
                                resolution = json.loads(cleaned_json)  # Use json instead of _json
                                print(f"[CombatResolver] Parsed cleaned LLM resolution as JSON: {resolution}")
                            except json.JSONDecodeError as e2:  # Use json instead of _json
                                print(f"[CombatResolver] Failed to parse JSON resolution even after cleanup: {e2}")
                                # Use a simpler approach - construct a minimal resolution with description field
                                resolution = {
                                    "description": "The action resolves with technical difficulties.",
                                    "narrative": "The action resolves with technical difficulties.",
                                    "updates": []
                                }
                                
                                # Try to extract potential targets and damage from dice results
                                potential_target = target if 'target' in locals() and target and target.lower() != "none" else None
                                if not potential_target:
                                    # Find first enemy
                                    for c in combatants:
                                        if c.get("name") != active_combatant.get("name"):
                                            potential_target = c.get("name")
                                            break
                                
                                if potential_target and 'dice_results' in locals() and dice_results:
                                    # Look for damage dice
                                    damage_dice = [d for d in dice_results if "damage" in d.get("purpose", "").lower()]
                                    if damage_dice:
                                        try:
                                            damage_amount = int(damage_dice[0].get("result", 0))
                                            # Create or update damage value for target
                                            resolution["damage_dealt"] = {potential_target: damage_amount}
                                            print(f"[CombatResolver] Created damage_dealt with {damage_amount} to {potential_target}")
                                        except (ValueError, TypeError):
                                            print(f"[CombatResolver] Could not extract damage value from dice")
                # --- ENSURE resolution is a dict ---
                if not isinstance(resolution, dict):
                    print(f"[CombatResolver] LLM resolution is not a dict, using fallback.")
                    resolution = {
                        "description": str(resolution),
                        "narrative": str(resolution),
                        "updates": []
                    }

                # DEBUG: Print raw LLM output for troubleshooting
                if 'raw_llm_output' in locals():
                    print(f"[CombatResolver] RAW LLM OUTPUT (first 500 chars): {str(raw_llm_output)[:500]}")

                # --- DICE ROLLING PHASE ---
                dice_results = []
                # Check for dice_requests in the LLM response
                dice_requests = resolution.get('dice_requests', [])
                for req in dice_requests:
                    expr = req.get('expression')
                    purpose = req.get('purpose', '')
                    if expr:
                        try:
                            result = dice_roller(expr)
                        except Exception as e:
                            print(f"[CombatResolver] Dice roll error for '{expr}': {e}")
                            result = 'error'
                        dice_results.append({
                            'expression': expr,
                            'result': result,
                            'purpose': purpose
                        })
                # Attach dice_results to locals for downstream logic
                # (the rest of the function already tries to use dice_results)

                # ------------------------------------------------------------------
                # NEW: Build and RETURN the turn_result so the caller can log it
                # ------------------------------------------------------------------
                
                # Build updates list based on damage/healing information if provided
                updates = []

                try:
                    # Extract a narrative/description in a tolerant manner
                    narrative_text = None
                    # Prefer 'reasoning', then 'description', then 'narrative', then 'action', then 'result' for the combat log
                    for field in ["reasoning", "description", "narrative", "action", "result"]:
                        if field in resolution and resolution[field]:
                            narrative_text = resolution[field]
                            print(f"[CombatResolver] Found narrative in field '{field}': {narrative_text[:50]}...")
                            break
                    # If no appropriate field was found, use a default
                    if not narrative_text:
                        narrative_text = "The action resolves with technical difficulties."
                        print(f"[CombatResolver] Using fallback narrative: {narrative_text}")

                    # Auto-detect targets if no damage_dealt is specified but there's a narrative
                    if (not resolution.get("damage_dealt") or len(resolution.get("damage_dealt", {})) == 0) and narrative_text:
                        print(f"[CombatResolver] No damage specified in resolution, attempting to extract from narrative")
                        # Find potential targets mentioned in the narrative
                        potential_targets = []
                        for c in combatants:
                            if c.get("name") != active_combatant.get("name") and c.get("name") in narrative_text:
                                potential_targets.append(c.get("name"))
                        
                        if potential_targets:
                            print(f"[CombatResolver] Found potential targets in narrative: {potential_targets}")
                            # Add the first found target to damage_dealt
                            if "damage_dealt" not in resolution:
                                resolution["damage_dealt"] = {}
                            
                            # Check if attack/damage dice were rolled
                            damage_dice = [d for d in dice_results if "damage" in d.get("purpose", "").lower()]
                            if damage_dice:
                                try:
                                    damage_value = int(damage_dice[0].get("result", 0))
                                    # Create or update damage value for target
                                    resolution["damage_dealt"][potential_targets[0]] = damage_value
                                    print(f"[CombatResolver] Auto-assigned {damage_value} damage to {potential_targets[0]}")
                                except (ValueError, TypeError):
                                    print(f"[CombatResolver] Could not extract damage value from dice")
                    
                    # If there are damage dice but no damage_dealt section at all, create one
                    if not resolution.get("damage_dealt") and 'dice_results' in locals() and dice_results:
                        damage_dice = [d for d in dice_results if "damage" in d.get("purpose", "").lower()]
                        if damage_dice:
                            # Try to find the most likely target
                            if 'target' in locals() and target and target != "none" and target != "None":
                                # Target was specified in the decision
                                try:
                                    damage_value = int(damage_dice[0].get("result", 0))
                                    resolution["damage_dealt"] = {target: damage_value}
                                    print(f"[CombatResolver] Created damage_dealt with {damage_value} to {target}")
                                except (ValueError, TypeError):
                                    print(f"[CombatResolver] Could not extract damage value from dice")
                            else:
                                # Try to find enemy targets
                                enemies = [c.get("name") for c in combatants 
                                          if c.get("name") != active_combatant.get("name")]
                                if enemies:
                                    try:
                                        damage_value = int(damage_dice[0].get("result", 0))
                                        resolution["damage_dealt"] = {enemies[0]: damage_value}
                                        print(f"[CombatResolver] Created damage_dealt with {damage_value} to {enemies[0]}")
                                    except (ValueError, TypeError):
                                        print(f"[CombatResolver] Could not extract damage value from dice")

                    # Handle damage dealt (reduce HP for targets)
                    for target_name, dmg in resolution.get("damage_dealt", {}).items():
                        target = next((c for c in combatants if c.get("name") == target_name), None)
                        if not target:
                            print(f"[CombatResolver] Target '{target_name}' not found for damage.")
                            continue

                        # --- REVISED Saving Throw & Damage Logic ---
                        save_succeeded = False
                        save_required = False
                        final_dmg = 0
                        action_name = resolution.get("action", "Unknown Action")
                        
                        # Find the action definition for the active combatant
                        action_details = None
                        if "actions" in active_combatant:
                             action_details = next((a for a in active_combatant["actions"] if isinstance(a, dict) and a.get("name") == action_name), None)
                        
                        # 1. Check if the action requires a saving throw based on its description
                        if action_details and "saving throw" in action_details.get("description", "").lower():
                            save_required = True
                            print(f"[CombatResolver] Action '{action_name}' requires a saving throw.")
                            
                            # Extract DC and Ability from action description (more reliable)
                            save_dc = 15 # Default fallback DC
                            save_ability_name = "Dexterity" # Default fallback ability
                            damage_on_save = "half" # Default assumption
                            
                            # Regex to find "DC X Ability saving throw"
                            save_match = re.search(r"DC\s*(\d+)\s*(\w+)\s*saving throw", action_details["description"], re.IGNORECASE)
                            if save_match:
                                save_dc = int(save_match.group(1))
                                save_ability_name = save_match.group(2).capitalize()
                                print(f"[CombatResolver] Extracted Save DC {save_dc} and Ability {save_ability_name} from action description.")
                            else:
                                print(f"[CombatResolver] WARNING: Could not extract DC/Ability from action description: {action_details['description']}. Using defaults DC {save_dc} {save_ability_name}.")

                            # Determine damage on save from description
                            if "half as much damage on a successful one" in action_details["description"].lower():
                                damage_on_save = "half"
                            elif "no damage on a successful save" in action_details["description"].lower(): # Check for 'no damage' case
                                damage_on_save = "none"
                            else:
                                damage_on_save = "full" # Assume full damage on fail, maybe half on success if not specified
                                print(f"[CombatResolver] Assuming '{damage_on_save}' damage on successful save for {action_name}")

                            # Get target's save modifier
                            # Map ability name to stat abbreviation (e.g., Dexterity -> dex)
                            ability_abbr_map = {"Strength": "str", "Dexterity": "dex", "Constitution": "con", "Intelligence": "int", "Wisdom": "wis", "Charisma": "cha"}
                            ability_abbr = ability_abbr_map.get(save_ability_name, "dex") # Default to dex if name is weird
                            
                            target_stat_value = target.get(ability_abbr, 10) # Default to 10 if stat missing
                            save_modifier = (target_stat_value - 10) // 2
                            print(f"[CombatResolver] Target {target_name}'s {save_ability_name} modifier: {save_modifier}")
                            
                            # Roll the save INTERNALLY
                            save_roll_expr = f"1d20+{save_modifier}"
                            try:
                                save_roll_result = dice_roller(save_roll_expr)
                                if isinstance(save_roll_result, (int, float)): # Check if roll succeeded
                                     save_roll_result = int(save_roll_result)
                                     # Append this internally rolled save to dice_results for logging
                                     dice_results.append({
                                         'expression': save_roll_expr,
                                         'result': save_roll_result,
                                         'purpose': f"{target_name}'s {save_ability_name} save vs DC {save_dc}"
                                     })
                                     print(f"[CombatResolver] Internally rolled save for {target_name}: {save_roll_result} vs DC {save_dc}")
                                     if save_roll_result >= save_dc:
                                         save_succeeded = True
                                         print(f"[CombatResolver] {target_name} succeeded on the internal save!")
                                     else:
                                         save_succeeded = False
                                         print(f"[CombatResolver] {target_name} failed the internal save.")
                                else:
                                     print(f"[CombatResolver] ERROR: Internal save roll failed or returned invalid type: {save_roll_result}. Assuming failure.")
                                     save_succeeded = False
                                     # Log the failed roll attempt
                                     dice_results.append({
                                         'expression': save_roll_expr,
                                         'result': 'Error',
                                         'purpose': f"{target_name}'s {save_ability_name} save vs DC {save_dc} (Roll Failed)"
                                     })
                            except Exception as e:
                                print(f"[CombatResolver] CRITICAL ERROR rolling internal save '{save_roll_expr}': {e}. Assuming failure.")
                                save_succeeded = False
                                # Log the failed roll attempt
                                dice_results.append({
                                    'expression': save_roll_expr,
                                    'result': 'Error',
                                    'purpose': f"{target_name}'s {save_ability_name} save vs DC {save_dc} (Roll Exception)"
                                })
                        
                        # 2. Validate and get initial damage amount (from LLM or dice)
                        initial_dmg = 0
                        if isinstance(dmg, (int, float)):
                            initial_dmg = int(dmg)
                        else:
                            try:
                                initial_dmg = int(dmg)
                            except (ValueError, TypeError):
                                print(f"[CombatResolver] Invalid initial damage value: {dmg} for target {target_name}. Trying dice fallback.")
                                # Fallback: Try extracting from dice results directly
                                damage_dice = [d for d in dice_results if "damage" in d.get("purpose", "").lower()]
                                if damage_dice:
                                    try:
                                        initial_dmg = int(damage_dice[0].get("result", 0))
                                        print(f"[CombatResolver] Using damage from dice result: {initial_dmg}")
                                    except (ValueError, TypeError):
                                        print(f"[CombatResolver] Could not parse damage dice result.")
                                        initial_dmg = 0
                                else:
                                    initial_dmg = 0
                        
                        # 3. Adjust damage based on saving throw outcome
                        if save_required:
                            if save_succeeded:
                                if damage_on_save == "half":
                                    final_dmg = initial_dmg // 2
                                    print(f"[CombatResolver] Applying half damage ({final_dmg}) due to successful save.")
                                elif damage_on_save == "none":
                                    final_dmg = 0
                                    print(f"[CombatResolver] Applying no damage due to successful save.")
                                else: # Includes 'full' which implies full damage on fail, half on success? Revisit this assumption if needed.
                                     final_dmg = initial_dmg // 2 # Default to half damage on save if not specified otherwise
                                     print(f"[CombatResolver] Applying default half damage ({final_dmg}) due to successful save.")
                            else: # Save failed
                                final_dmg = initial_dmg
                                print(f"[CombatResolver] Applying full damage ({final_dmg}) due to failed save.")
                        else: 
                            # 4. If no save required, check attack roll vs AC
                            final_dmg = 0 # Default to 0 unless attack hits
                            attack_rolls = [d for d in dice_results if "attack" in d.get("purpose", "").lower()]
                            if attack_rolls:
                                try:
                                    attack_value = int(attack_rolls[0].get("result", 0))
                                    target_ac = target.get("ac", 15) # Use target's AC
                                    print(f"[CombatResolver] Checking attack roll {attack_value} vs AC {target_ac} for {target_name}")
                                    if attack_value >= target_ac:
                                        final_dmg = initial_dmg # Apply full damage if attack hits
                                        print(f"[CombatResolver] Attack hit! Applying damage {final_dmg}.")
                                    else:
                                        final_dmg = 0 # Ensure damage is zero if attack missed
                                        print(f"[CombatResolver] Attack missed. No damage applied.")
                                except (ValueError, TypeError, IndexError) as e:
                                    print(f"[CombatResolver] Could not parse attack roll for damage check: {e}. Assuming miss.")
                                    final_dmg = 0
                            else:
                                # If no attack roll found for non-save action, assume it hits? Or apply 0 damage?
                                # Let's assume 0 damage if no attack roll present for a non-save action.
                                print(f"[CombatResolver] No attack roll found for action '{action_name}'. Applying 0 damage.")
                                final_dmg = 0
                        
                        # 5. Apply the final calculated damage
                        if final_dmg > 0:
                            new_hp = max(0, target.get("hp", 0) - final_dmg)
                            # Check if update already exists for this target
                            existing_update = next((u for u in updates if u.get("name") == target_name), None)
                            if existing_update:
                                existing_update["hp"] = new_hp # Update existing entry
                            else:
                                updates.append({"name": target_name, "hp": new_hp}) # Add new entry
                            print(f"[CombatResolver] Applying {final_dmg} damage to {target_name}: HP {target.get('hp', 0)} -> {new_hp}")
                        else:
                            print(f"[CombatResolver] No damage applied to {target_name}.")

                        # --- End REVISED Logic ---

                    # Handle healing (increase HP up to max)
                    for target_name, heal in resolution.get("healing", {}).items():
                        if not isinstance(heal, (int, float)):
                            try:
                                # Attempt to convert to int
                                heal = int(heal)
                            except (ValueError, TypeError):
                                print(f"[CombatResolver] Invalid healing value: {heal} for target {target_name}")
                                # Try to extract healing from dice results
                                healing_dice = [d for d in dice_results if "heal" in d.get("purpose", "").lower()]
                                if healing_dice:
                                    try:
                                        heal = int(healing_dice[0].get("result", 0))
                                        print(f"[CombatResolver] Using healing from dice result: {heal}")
                                    except (ValueError, TypeError):
                                        heal = 0
                                        print(f"[CombatResolver] Could not use dice healing value")
                                else:
                                    # Default healing amount
                                    heal = 10
                                    print(f"[CombatResolver] Using default healing amount of {heal}")
                                    
                        target = next((c for c in combatants if c.get("name") == target_name), None)
                        if target:
                            max_hp = target.get("max_hp", target.get("hp", 0))
                            new_hp = min(max_hp, target.get("hp", 0) + int(heal))
                            updates.append({"name": target_name, "hp": new_hp})
                            print(f"[CombatResolver] Applying {heal} healing to {target_name}: HP {target.get('hp', 0)} → {new_hp}")
                    
                    # Apply conditions if specified
                    for target_name, conditions in resolution.get("conditions_applied", {}).items():
                        target = next((c for c in combatants if c.get("name") == target_name), None)
                        if target and isinstance(conditions, list):
                            if "conditions" not in target:
                                target["conditions"] = {}
                            
                            # Add each condition
                            for condition in conditions:
                                if isinstance(condition, str):
                                    target["conditions"][condition.lower()] = {"source": active_combatant.get("name", "Unknown")}
                                    print(f"[CombatResolver] Applied condition '{condition}' to {target_name}")
                                    
                            # Add condition update to updates list
                            condition_update = {"name": target_name, "conditions": target["conditions"]}
                            updates.append(condition_update)
                            
                    # Remove conditions if specified
                    for target_name, conditions in resolution.get("conditions_removed", {}).items():
                        target = next((c for c in combatants if c.get("name") == target_name), None)
                        if target and "conditions" in target and isinstance(conditions, list):
                            # Remove each condition
                            for condition in conditions:
                                if isinstance(condition, str) and condition.lower() in target["conditions"]:
                                    del target["conditions"][condition.lower()]
                                    print(f"[CombatResolver] Removed condition '{condition}' from {target_name}")
                            
                            # Add condition update to updates list
                            condition_update = {"name": target_name, "conditions": target["conditions"]}
                            updates.append(condition_update)
                except Exception as e:
                    # Defensive: Never let update generation crash the turn
                    print(f"[CombatResolver] WARNING: Error translating resolution to updates: {e}")
                    import traceback
                    traceback.print_exc()

                # Fall back to any explicit updates provided by the LLM
                if not updates and isinstance(resolution.get("updates"), list):
                    updates = resolution["updates"]
                    print(f"[CombatResolver] Using explicit updates from resolution: {updates}")

                turn_result = {
                    "action": resolution.get("action", "Unknown action"),
                    "narrative": narrative_text,
                    "dice": dice_results,
                    "updates": updates,
                }

                print(f"[CombatResolver] Final turn result: {turn_result}")
                return turn_result
            except Exception as e:
                print(f"[CombatResolver] Error processing turn resolution: {str(e)}")
                import traceback
                traceback.print_exc()
                
                # Even in case of error, return a valid turn result
                fallback_result = {
                    "action": resolution.get("action", "Unknown action"),
                    "narrative": f"The {active_combatant.get('name', 'combatant')} acted, but a technical issue prevented recording the outcome.",
                    "dice": dice_results,
                    "updates": []
                }
                print(f"[CombatResolver] Using fallback turn result due to error: {fallback_result}")
                return fallback_result
        except Exception as e:
            # Final fallback - this should never be reached, but just in case
            print(f"[CombatResolver] Critical error in _process_turn: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                "action": "Unknown action",
                "narrative": f"The {active_combatant.get('name', 'Unknown')} attempted to act, but a critical error occurred.",
                "dice": [],
                "updates": []
            }

    def _create_decision_prompt(self, combat_state, turn_combatant):
        """Create a prompt for the LLM to decide a combatant's action."""
        prompt = "You are playing the role of a combatant in a D&D 5e battle. Make a tactical decision for your next action.\n\n"
        
        # Basic combat situation
        active_combatant = next((c for c in combat_state.get("combatants", []) if c.get("id") == turn_combatant.get("id")), None)
        if not active_combatant:
            return "Error: Could not find active combatant in combat state."
            
        instance_id = active_combatant.get("instance_id", "")
        
        # Get lists of available and unavailable recharge abilities
        available_recharge_abilities = []
        unavailable_recharge_abilities = []
        # Use try-except for potential errors during processing
        try: 
            for name, info in active_combatant.get("recharge_abilities", {}).items():
                if info.get("available", False):
                    available_recharge_abilities.append(f"{name} ({info.get('recharge_text', 'Recharge ability')})")
                else:
                    unavailable_recharge_abilities.append(f"{name} ({info.get('recharge_text', 'Recharge ability')})")
        except Exception as e:
            print(f"[CombatResolver] Error processing recharge abilities: {e}")
            # Handle error case gracefully, e.g., log or default behavior
            pass  # Example: continue without adding abilities
        
        # Format initiative order
        initiative_order = []
        for c in sorted([c for c in combat_state.get("combatants", [])], key=lambda x: x.get("initiative", 0), reverse=True):
            initiative_text = f"{c.get('name')} (Initiative: {c.get('initiative')})"
            if c.get("id") == active_combatant.get("id"):
                initiative_text += " - ACTIVE TURN"
            initiative_order.append(initiative_text)
        
        # Describe the combat situation
        prompt += "# Combat Situation\n"
        prompt += f"You are playing as: {active_combatant.get('name')} (Type: {active_combatant.get('type')})\n"
        # Use 'hp' as the canonical current HP field (fixes bug where HP was always 0)
        # Fallback to 'current_hp' only if 'hp' is missing, for robustness
        current_hp = active_combatant.get('hp', active_combatant.get('current_hp', 0))
        max_hp = active_combatant.get('max_hp', 0)
        prompt += f"Current HP: {current_hp}/{max_hp}\n"
        prompt += f"AC: {active_combatant.get('ac', 0)}\n"
        
        # Add status effects if any
        status_effects = active_combatant.get("status_effects", [])
        if status_effects:
            prompt += f"Status Effects: {', '.join(status_effects)}\n"
        
        # Initiative order
        prompt += "\n## Initiative Order\n"
        for init in initiative_order:
            prompt += f"- {init}\n"
        
        # Current turn number
        prompt += f"\nCurrent Turn: {combat_state.get('turn_number', 1)}\n"
        
        # Add information about all combatants
        prompt += "\n# Combatants\n"
        for c in combat_state.get("combatants", []):
            name = c.get("name", "Unknown")
            ctype = c.get("type", "unknown")
            c_current_hp = c.get('hp', c.get('current_hp', 0))
            c_max_hp = c.get('max_hp', c_current_hp)
            status = c.get("status", "Healthy")
            prompt += f"- {name} (Type: {ctype}, HP: {c_current_hp}/{c_max_hp}, Status: {status})\n"
        
        # Recharge abilities status
        if available_recharge_abilities or unavailable_recharge_abilities:
            prompt += "\n# Recharge Abilities Status\n"
            
            if available_recharge_abilities:
                prompt += "## Available Recharge Abilities\n"
                for ability in available_recharge_abilities:
                    prompt += f"- {ability} (AVAILABLE NOW)\n"
                    
            if unavailable_recharge_abilities:
                prompt += "## Unavailable Recharge Abilities\n"
                for ability in unavailable_recharge_abilities:
                    prompt += f"- {ability} (NOT YET RECHARGED - unavailable this turn)\n"
                    
            prompt += "\n"
        
        # Add actions, abilities, and traits
        prompt += "\n# Your Available Options\n"
        
        # Actions
        actions = active_combatant.get("actions", [])
        if actions:
            prompt += "## Actions\n"
            for action in actions:
                if isinstance(action, dict):
                    name = action.get("name", "Unknown")
                    desc = action.get("description", "No description")
                    
                    # Check if this is a recharge ability
                    recharge_info = ""
                    is_recharge = False
                    is_available = True
                    
                    if "recharge_abilities" in active_combatant:
                        if name in active_combatant["recharge_abilities"]:
                            is_recharge = True
                            recharge_data = active_combatant["recharge_abilities"][name]
                            is_available = recharge_data.get("available", False)
                            recharge_text = recharge_data.get("recharge_text", "Recharge ability")
                            
                            if is_available:
                                recharge_info = f" - {recharge_text} (AVAILABLE)"
                            else:
                                recharge_info = f" - {recharge_text} (NOT AVAILABLE THIS TURN)"
                    
                    # Skip unavailable recharge abilities in the prompt (to avoid confusion)
                    if is_recharge and not is_available:
                        continue
                        
                    # Check for instance ID to ensure this is for the right monster
                    # Use 'monster_instance_id' which is added during combat state gathering
                    action_instance_id = action.get("monster_instance_id", "") 
                    if action_instance_id and action_instance_id != instance_id:
                        print(f"[Prompt] Skipping action '{name}' (ID: {action_instance_id}) for combatant {active_combatant.get('name')}({instance_id})")
                        continue  # Skip actions belonging to different instances
                    
                    attack_bonus = action.get("attack_bonus", "")
                    if attack_bonus:
                        attack_text = f"Attack Bonus: {attack_bonus}"
                    else:
                        attack_text = ""
                        
                    damage = action.get("damage", "")
                    if damage:
                        damage_text = f"Damage: {damage}"
                    else:
                        damage_text = ""
                        
                    prompt += f"- {name}{recharge_info}\n"
                    prompt += f"  {desc}\n"
                    if attack_text:
                        prompt += f"  {attack_text}\n"
                    if damage_text:
                        prompt += f"  {damage_text}\n"
                    prompt += "\n"
        
        # Abilities
        abilities = active_combatant.get("abilities", [])
        if abilities:
            prompt += "## Abilities\n"
            for ability in abilities:
                if isinstance(ability, dict):
                    name = ability.get("name", "Unknown")
                    desc = ability.get("description", "No description")
                    
                    # Check if this is a recharge ability
                    recharge_info = ""
                    is_recharge = False
                    is_available = True
                    
                    if "recharge_abilities" in active_combatant:
                        if name in active_combatant["recharge_abilities"]:
                            is_recharge = True
                            recharge_data = active_combatant["recharge_abilities"][name]
                            is_available = recharge_data.get("available", False)
                            recharge_text = recharge_data.get("recharge_text", "Recharge ability")
                            
                            if is_available:
                                recharge_info = f" - {recharge_text} (AVAILABLE)"
                            else:
                                recharge_info = f" - {recharge_text} (NOT AVAILABLE THIS TURN)"
                    
                    # Skip unavailable recharge abilities in the prompt
                    if is_recharge and not is_available:
                        continue
                        
                    # Check for instance ID to ensure this is for the right monster
                    # Use 'monster_instance_id' which is added during combat state gathering
                    ability_instance_id = ability.get("monster_instance_id", "") 
                    if ability_instance_id and ability_instance_id != instance_id:
                        print(f"[Prompt] Skipping ability '{name}' (ID: {ability_instance_id}) for combatant {active_combatant.get('name')}({instance_id})")
                        continue  # Skip abilities belonging to different instances
                    
                    prompt += f"- {name}{recharge_info}\n"
                    prompt += f"  {desc}\n\n"
        
        # Traits/Features
        traits = active_combatant.get("traits", [])
        if traits:
            prompt += "## Traits/Features\n"
            for trait in traits:
                if isinstance(trait, dict):
                    name = trait.get("name", "Unknown")
                    desc = trait.get("description", "No description")
                    
                    # Check for instance ID to ensure this is for the right monster
                    # Use 'monster_instance_id' which is added during combat state gathering
                    trait_instance_id = trait.get("monster_instance_id", "") 
                    if trait_instance_id and trait_instance_id != instance_id:
                        print(f"[Prompt] Skipping trait '{name}' (ID: {trait_instance_id}) for combatant {active_combatant.get('name')}({instance_id})")
                        continue  # Skip traits belonging to different instances
                    
                    prompt += f"- {name}\n"
                    prompt += f"  {desc}\n\n"
        
        # Decision request
        prompt += "\n# Your Decision\n"
        prompt += "Given the current combat situation, decide what action to take. Consider the following:\n"
        prompt += "1. Which available action would be most effective tactically?\n"
        prompt += "2. Consider using any available recharged abilities (like breath weapons) when they're available\n"
        prompt += "3. Consider the positioning of allies and enemies\n"
        prompt += "4. If you have low HP, consider defensive actions or targeting dangerous opponents first\n\n"
        
        # Add explicit targeting guidance
        prompt += "IMPORTANT TARGETING RULES:\n"
        prompt += "- NEVER target yourself with attacks or harmful abilities\n"
        prompt += "- Target enemies, not allies (unless using a beneficial ability like healing)\n"
        prompt += "- Vary your actions when possible for dynamic combat\n"
        prompt += "- For area effects like breath weapons, target clusters of enemies\n\n"
        
        if available_recharge_abilities:
            prompt += f"IMPORTANT: You have {len(available_recharge_abilities)} recharged special abilities available now! Consider using them!\n\n"
        
        prompt += "Reply with a single JSON object in this format:\n"
        prompt += '{\n  "action": "[action name]",\n  "target": "[target name or none]",\n  "reasoning": "[brief tactical reasoning for this choice]",\n'
        
        # Add details about requesting dice rolls
        prompt += '  "dice_requests": [\n    {"expression": "1d20+5", "purpose": "Attack roll"},\n    {"expression": "2d6+3", "purpose": "Damage roll"}\n  ]\n}\n\n'
        
        # Ensure prompt is a string, even if errors occurred
        if not isinstance(prompt, str):
            prompt = "Error: Prompt generation failed."
        
        return prompt

    def _process_death_save(self, combatant):
        """Process a death saving throw for a combatant."""
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

    def _process_hp_update(self, target_name, hp_update, current_hp):
        """
        Processes an HP update instruction, handling relative changes.
        
        Args:
            target_name: Name of the target combatant.
            hp_update: The HP update value (can be int, '+X', '-X').
            current_hp: The current HP of the target.
            
        Returns:
            The new HP value (int).
        """
        try:
            if isinstance(hp_update, str):
                if hp_update.startswith('+'):
                    change = int(hp_update[1:])
                    return current_hp + change
                elif hp_update.startswith('-'):
                    change = int(hp_update[1:])
                    return max(0, current_hp - change)
                else:
                    # Assume absolute value if no sign
                    return int(hp_update)
            elif isinstance(hp_update, (int, float)):
                # If it's already a number, assume absolute value
                return int(hp_update)
            else:
                print(f"[CombatResolver] Invalid hp_update type for {target_name}: {type(hp_update)}. Defaulting to current HP.")
                return current_hp
        except (ValueError, TypeError) as e:
            print(f"[CombatResolver] Error processing HP update '{hp_update}' for {target_name}: {e}. Defaulting to current HP.")
            return current_hp
        except Exception as e:
            # Catch any other unexpected errors during HP processing
            print(f"[CombatResolver] Unexpected error processing HP update for {target_name}: {e}. Defaulting to current HP.")
            return current_hp

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
                    print(f"[CombatResolver] {c.get('name')} aura '{aura_name}' is in range ({distance}/{range_feet}ft) to affect {active_combatant.get('name')}")
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
                                print(f"[CombatResolver] Rolled aura damage: {damage_expr} = {damage}")
                            else:
                                # Default to fixed damage if expression parsing fails
                                damage = int(damage_expr) if damage_expr.isdigit() else 1
                                print(f"[CombatResolver] Using fixed aura damage: {damage}")
                        except Exception as e:
                            print(f"[CombatResolver] Error rolling aura damage: {str(e)}")
                            # Continue to next aura
                            continue
                        
                        # Apply damage to active combatant
                        damage_type = effect.get("damage_type", "fire")
                        old_hp = active_combatant.get("hp", 0)
                        active_combatant["hp"] = max(0, old_hp - damage)
                        
                        print(f"[CombatResolver] {c.get('name')}'s {aura_name} deals {damage} {damage_type} damage to {active_combatant.get('name')}")
                        print(f"[CombatResolver] {active_combatant.get('name')} HP: {old_hp} → {active_combatant['hp']}")
                        
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
        
        if not updates:
            print(f"[CombatResolver] No aura effects applied to {active_combatant.get('name', 'Unknown')}")
        
        return updates
    
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
            
        # Get combatant name for better logging
        name = combatant.get("name", "Unknown")
        print(f"[CombatResolver] Checking for auras in {name}'s traits")
            
        # Check for aura-related traits by name and description
        if "traits" in combatant and isinstance(combatant["traits"], list):
            for trait in combatant["traits"]:
                if not isinstance(trait, dict):
                    continue

                trait_name = trait.get("name", "")
                trait_desc = trait.get("description", "")
                
                # Check if it's an aura by name
                if "aura" in trait_name.lower():
                    print(f"[CombatResolver] Found aura trait by name: {trait_name}")
                    aura_name = trait_name.lower().replace(" ", "_")
                    aura_range = 10  # Default range
                    
                    # Try to extract range from description
                    import re
                    range_match = re.search(r'(\d+)[- ]feet?', trait_desc, re.IGNORECASE)
                    if range_match:
                        aura_range = int(range_match.group(1))
                        
                    # Determine effect type and details from description
                    effect_type = "damage" if any(x in trait_desc.lower() for x in ["damage", "takes", "hurt"]) else "condition"
                    
                    # Create damage effect
                    if effect_type == "damage":
                        # Extract damage amount from description
                        damage_match = re.search(r'(\d+)d(\d+)(?:\s*\+\s*(\d+))?', trait_desc)
                        damage_expr = "1d6"  # Default damage
                        damage_type = "fire"  # Default type
                        
                        if damage_match:
                            dice_count = damage_match.group(1)
                            dice_size = damage_match.group(2)
                            bonus = damage_match.group(3) or "0"
                            damage_expr = f"{dice_count}d{dice_size}+{bonus}"
                            
                        # Extract damage type if present
                        type_match = re.search(r'(\w+) damage', trait_desc.lower())
                        if type_match:
                            damage_type = type_match.group(1)
                            
                        # Create the aura effect
                        combatant["auras"][aura_name] = {
                            "range": aura_range,
                            "effect": {
                                "type": "damage",
                                "expression": damage_expr,
                                "damage_type": damage_type
                            },
                            "affects": "enemies",
                            "affects_self": False,
                            "source": "trait"
                        }
                        
                        print(f"[CombatResolver] Created {damage_type} damage aura '{aura_name}' with range {aura_range}ft, damage {damage_expr}")
                    
                    # Create condition effect
                    else:
                        # Extract condition from description
                        condition_match = re.search(r'(?:becomes?|is) (frightened|poisoned|stunned|blinded|deafened)', trait_desc.lower())
                        condition = "frightened" if not condition_match else condition_match.group(1)
                        
                        # Create the aura effect
                        combatant["auras"][aura_name] = {
                            "range": aura_range,
                            "effect": {
                                "type": "condition",
                                "condition": condition,
                                "duration": 1
                            },
                            "affects": "enemies",
                            "affects_self": False,
                            "source": "trait"
                        }
                        
                        print(f"[CombatResolver] Created condition aura '{aura_name}' with range {aura_range}ft, condition {condition}")
        
        # Special handling for known monsters with auras regardless of traits
        name_lower = name.lower()
        if "fire" in name_lower or "infernal" in name_lower or "tyrant" in name_lower:
            print(f"[CombatResolver] Adding fire aura to {name} based on name")
            
            # Only add if not already present
            if "fire_aura" not in combatant["auras"]:
                combatant["auras"]["fire_aura"] = {
                    "range": 10,
                    "effect": {
                        "type": "damage", 
                        "expression": "3d6", 
                        "damage_type": "fire"
                    },
                    "affects": "enemies",
                    "affects_self": False,
                    "source": "infernal_nature"
                }
                
                print(f"[CombatResolver] Added fire_aura to {name}")
        
        # Mark as processed to avoid redundant checks
        combatant["auras_processed"] = True
        return combatant
    
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

    def _create_resolution_prompt(self, combatants, active_idx, combatant_decision, dice_results, round_num):
        """
        Create a prompt for the LLM to resolve a combatant's action.
        
        This method generates a detailed prompt to help the LLM narrate and resolve
        the outcome of a combatant's action, including handling damage, conditions,
        and special ability effects, including recharge ability tracking.
        
        Args:
            combatants: List of all combatants
            active_idx: Index of active combatant
            combatant_decision: The decision made by the LLM for the active combatant
            dice_results: Results of any dice rolls requested by the decision LLM
            round_num: Current round number
            
        Returns:
            Prompt string for the resolution LLM
        """
        active = combatants[active_idx]
        active_name = active.get('name', 'Unknown')
        
        # Get the instance ID for this combatant
        instance_id = active.get('instance_id', f"combatant_{active_idx}")
        
        # Extract the decision components
        action = combatant_decision.get('action', 'No action taken')
        target = combatant_decision.get('target', None)
        action_type = combatant_decision.get('action_type', 'none')
        
        # Format dice results
        dice_str = self._format_dice_results(dice_results)
        
        # Format nearby combatants
        nearby = self._get_nearby_combatants(active, combatants)
        nearby_str = self._format_nearby_combatants(nearby)
        
        # Format the target information
        target_str = "No specific target."
        target_data = None
        
        if target:
            # Find the target in the list of combatants
            for combatant in combatants:
                if combatant.get('name') == target:
                    target_data = combatant
                    break
            
            if target_data:
                target_str = f"""
Target: {target_data.get('name', 'Unknown')}
HP: {target_data.get('hp', 0)}/{target_data.get('max_hp', target_data.get('hp', 0))}
AC: {target_data.get('ac', 10)}
Type: {target_data.get('type', 'Unknown')}
Status: {target_data.get('status', 'OK')}
"""
            else:
                target_str = f"Target: {target} (details unknown)"
        
        # Get and format conditions affecting the active combatant
        condition_str = self._format_conditions(active)
        
        # Check for recharge ability usage
        recharge_warning = ""
        recharge_status = ""
        used_ability_name = None
        
        # First, compile a list of available and unavailable recharge abilities
        available_recharge = []
        unavailable_recharge = []
        
        if "recharge_abilities" in active and active["recharge_abilities"]:
            for ability_name, info in active["recharge_abilities"].items():
                if info.get("available", False):
                    available_recharge.append(ability_name)
                else:
                    unavailable_recharge.append(ability_name)
        
            # Add recharge status information
            recharge_status = f"""
# RECHARGE ABILITIES STATUS
Available now: {', '.join(available_recharge) if available_recharge else 'None'}
NOT available (needs recharge): {', '.join(unavailable_recharge) if unavailable_recharge else 'None'}
"""
            
        # Try to identify which ability is being used from the action description
        if "recharge_abilities" in active and active["recharge_abilities"]:
            for ability_name in active["recharge_abilities"].keys():
                # Check if the ability name appears in the action text
                if ability_name.lower() in action.lower():
                    used_ability_name = ability_name
                    break
            
            # If we identified a recharge ability being used
            if used_ability_name:
                is_available = active["recharge_abilities"][used_ability_name].get("available", False)
                
                # If the ability is not available, add a warning
                if not is_available:
                    recharge_warning = f"""
⚠️ WARNING - RECHARGE ABILITY NOT AVAILABLE ⚠️
The combatant is attempting to use {used_ability_name}, but this ability has not recharged yet!
This ability cannot be used until it recharges (typically on a roll of 5-6 on a d6 at the start of the creature's turn).
Please adjust the resolution to indicate the creature attempted to use this ability but couldn't, and had to choose a different action instead.
"""
                else:
                    # If the ability is available, mark it as used (unavailable for next turn)
                    active["recharge_abilities"][used_ability_name]["available"] = False
                    recharge_warning = f"""
RECHARGE ABILITY USED: {used_ability_name} has been used and is now unavailable until recharged.
Make sure to reflect this in your resolution by setting "recharge_ability_used" to "{used_ability_name}".
"""
        
        # Start constructing the prompt
        prompt = f"""
You are the combat resolution AI for a D&D 5e game. Your task is to resolve {active_name}'s action this turn and narrate the outcome.

# COMBAT SITUATION
Round: {round_num}
Active Combatant: {active_name}

# {active_name.upper()} DETAILS
HP: {active.get('hp', 0)}/{active.get('max_hp', active.get('hp', 0))}
AC: {active.get('ac', 10)}
Type: {active.get('type', 'Unknown')}
Status: {active.get('status', 'OK')}

# CHOSEN ACTION
{action}
Action Type: {action_type}

{recharge_status}
{recharge_warning}

# DICE RESULTS
{dice_str}

# TARGET INFORMATION
{target_str}

# NEARBY COMBATANTS
{nearby_str}

# CURRENT CONDITIONS
{condition_str}

# RESOLUTION INSTRUCTIONS
1. Narrate what happens when {active_name} takes their action.
2. Determine outcomes based on dice results.
3. Calculate damage dealt or healing provided.
4. Apply any conditions that result from the action.
5. Note any resource usage (spell slots, limited use abilities, etc.).

Your response MUST be a JSON object containing:
{{
  "description": "A vivid narration of what happens when the action is taken and its immediate effects",
  "damage_dealt": {{"target_name": damage_amount, ...}},
  "damage_taken": {{"source_name": damage_amount, ...}},
  "healing": {{"target_name": healing_amount, ...}},
  "conditions_applied": {{"target_name": ["condition1", "condition2", ...], ...}},
  "conditions_removed": {{"target_name": ["condition1", "condition2", ...], ...}},
  "recharge_ability_used": ""
}}

IMPORTANT GUIDELINES:
- Provide a detailed, vivid description of the action's outcome
- In "damage_dealt", use specific target names and numerical damage values
- Use dice results to determine hits/misses and damage amounts
- If attack rolls beat the target's AC, apply appropriate damage
- Apply appropriate conditions based on the attack type and narrative
- For healing effects, specify the target and amount in the "healing" field
- ALWAYS format your response as a proper JSON object

DESCRIPTION: A detailed narrative of what happens
DAMAGE_DEALT: A mapping of target names to damage amounts
DAMAGE_TAKEN: A mapping of damage sources to damage amounts
HEALING: A mapping of target names to healing amounts
CONDITIONS_APPLIED: A mapping of target names to lists of conditions applied
CONDITIONS_REMOVED: A mapping of target names to lists of conditions removed
RECHARGE_ABILITY_USED: If a recharge ability was used, set this to the name of the ability (e.g. "Fire Breath")

IMPORTANT: If the action involves using a recharge ability that is not available, adjust your narration to describe how the creature attempted to use that ability but couldn't, and then chose an alternative action instead.
"""
        return prompt

    # ---------------------------------------------------------------------
    # NEW: Helper to format dice results for the resolution prompt
    # ---------------------------------------------------------------------
    def _format_dice_results(self, dice_results):
        """Return dice results in a concise, readable string for the LLM prompt.

        Args:
            dice_results: List of dicts with keys `expression`, `result`, and optional `purpose`.

        Returns:
            A newline-separated string summarizing each dice roll. If no dice were rolled,
            returns a friendly placeholder message.
        """
        # If nothing was rolled, keep the prompt clean and explicit
        if not dice_results:
            return "No dice were rolled this turn."

        # Build a line for each result: "1d20 => 17 (Attack roll)"
        formatted_lines = []
        for roll in dice_results:
            # Safely fetch each field with sensible fallbacks
            expr = str(roll.get("expression", "?"))
            res = str(roll.get("result", "?"))
            purpose = roll.get("purpose", "")

            # Add purpose in parentheses only when provided
            if purpose:
                formatted_lines.append(f"{expr} ⇒ {res} ({purpose})")
            else:
                formatted_lines.append(f"{expr} ⇒ {res}")

        return "\n".join(formatted_lines)

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
  \"narrative\": \"Brief description of combat outcome\",
  \"updates\": [
    {{\"name\": \"Combatant1\", \"hp\": 25, \"status\": \"OK\"}},
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
                result = _json.loads(json_str)
                callback(result, None)
            else:
                callback(None, f"Could not find JSON in LLM response: {response}")
        except Exception as e:
            callback(None, f"Error parsing LLM response: {str(e)}\nResponse: {response}")