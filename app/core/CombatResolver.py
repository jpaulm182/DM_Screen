# Modularized CombatResolver (auto-generated)

from .combatresolver_process_helpers import *  # _process_ helpers
from .combatresolver_create_helpers import *  # _create_ helpers
from .combatresolver_add_helpers import *  # _add_ helpers
from .combatresolver_get_helpers import *  # _get_ helpers
from .combatresolver_format_helpers import *  # _format_ helpers
from .combatresolver_handle_helpers import *  # _handle_ helpers
class CombatResolver(QObject):
    """
    # ... see helpers for most methods ...

        def __init__(self, llm_service: LLMService):
            """Initialize the CombatResolver with the LLM service."""
            # Call QObject initializer
            super().__init__()
            self.llm_service = llm_service
            self.previous_turn_summaries = []  # NEW: Track previous turn results for LLM context
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
    
                                            # --- BEGIN STATUS-CONDITIONS SYNC PATCH ---
                                            # Always synchronize conditions list to status string for UI
                                            if isinstance(c.get("conditions", None), list):
                                                c["status"] = ", ".join(c["conditions"]) if c["conditions"] else ""
                                            # --- END STATUS-CONDITIONS SYNC PATCH ---
    
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

