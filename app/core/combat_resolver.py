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
            
            # Debug: Log all combatant HP values at start of turn
            print(f"\n[CombatResolver] DEBUG: CURRENT HP VALUES AT START OF TURN:")
            for i, c in enumerate(combatants):
                print(f"[CombatResolver] DEBUG: Combatant {i}: {c.get('name')} - HP: {c.get('hp', 0)}/{c.get('max_hp', c.get('hp', 0))}")
            
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
                        ]
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
                                ]
                            }
                
                # Validate required fields and provide defaults if missing
                if "action" not in decision:
                    print(f"[CombatResolver] Missing 'action' field in decision, adding default")
                    decision["action"] = "The combatant takes a defensive stance."
                    
                if "dice_requests" not in decision:
                    print(f"[CombatResolver] Missing 'dice_requests' field in decision, adding default")
                    decision["dice_requests"] = []
                    
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
                resolution_prompt = self._create_resolution_prompt(
                    combatants, active_idx, round_num, action, dice_results)
                    
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
                # Clean the LLM response to extract JSON properly
                resolution_text = resolution_response
                
                # Fix 1: Strip code block markers if they exist
                resolution_text = re.sub(r'```(?:json)?\s*', '', resolution_text)
                resolution_text = re.sub(r'```\s*$', '', resolution_text)
                
                # Fix 2: Try to extract JSON even if there's other text around it
                json_match = re.search(r'\{[\s\S]*\}', resolution_text)
                if not json_match:
                    print(f"[CombatResolver] Could not find JSON in LLM resolution response")
                    # Create a fallback resolution
                    resolution = {
                        "narrative": f"The {active_combatant.get('name', 'combatant')} attempted an action but the outcome was unclear.",
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
                            print(f"[CombatResolver] Failed to parse resolution JSON even after cleanup, creating fallback")
                            # Create fallback resolution
                            resolution = {
                                "narrative": f"The {active_combatant.get('name', 'combatant')} made an attempt, but a technical issue prevented recording the exact outcome.",
                                "updates": []
                            }
                
                # Validate required fields and provide defaults if missing
                if "narrative" not in resolution:
                    print(f"[CombatResolver] Missing 'narrative' field in resolution, adding default")
                    resolution["narrative"] = f"The {active_combatant.get('name', 'combatant')} completed their action."
                    
                if "updates" not in resolution:
                    print(f"[CombatResolver] Missing 'updates' field in resolution, adding default")
                    resolution["updates"] = []
                    
                # Extra safety check to ensure updates is a list
                if not isinstance(resolution.get("updates"), list):
                    print(f"[CombatResolver] 'updates' is not a list, fixing")
                    resolution["updates"] = []
                
                # CRITICAL FIX: Completely replace the narrative HP extraction with 
                # a better approach that avoids contaminating HP values between combatants
                print(f"[CombatResolver] DEBUG: Original resolution updates: {resolution.get('updates', [])}")
                
                # We will NOT use narrative HP extraction anymore - it's too error-prone
                # Instead, we'll only use the proper "updates" field from the LLM
                if "updates" in resolution and isinstance(resolution["updates"], list):
                    # Verify each update is properly formatted and has the necessary fields
                    verified_updates = []
                    for update in resolution["updates"]:
                        # Skip updates that aren't dictionaries
                        if not isinstance(update, dict):
                            print(f"[CombatResolver] WARNING: Skipping update with invalid format: {update}")
                            continue

                        # Skip updates without a name
                        if "name" not in update:
                            print(f"[CombatResolver] WARNING: Skipping update without 'name' field: {update}")
                            continue
                            
                        # Make a safe copy of the update to ensure we don't modify the original
                        verified_update = {"name": update["name"]}
                        
                        # Handle HP updates safely
                        if "hp" in update:
                            # Ensure HP is an integer using our helper function
                            try:
                                # Find the current HP for this combatant if available
                                current_hp = 0
                                for c in combatants:
                                    if c.get("name") == update["name"]:
                                        current_hp = c.get("hp", 0)
                                        break
                                        
                                # Process the HP update
                                processed_hp = self._process_hp_update(
                                    target_name=update["name"],
                                    hp_update=update["hp"],
                                    current_hp=current_hp
                                )
                                
                                # Store the processed HP in the verified update
                                verified_update["hp"] = processed_hp
                            except Exception as e:
                                print(f"[CombatResolver] Error validating HP update: {e}")
                        
                        # Copy other fields directly
                        if "status" in update:
                            verified_update["status"] = update["status"]
                        if "limited_use" in update:
                            verified_update["limited_use"] = update["limited_use"]
                        if "death_saves" in update:
                            verified_update["death_saves"] = update["death_saves"]
                            
                        verified_updates.append(verified_update)
                    
                    # Replace with verified updates
                    resolution["updates"] = verified_updates
                            
                # Add the original action and dice rolls to the resolution
                resolution["action"] = action
                resolution["dice"] = dice_results
                
                return resolution
            except Exception as e:
                print(f"[CombatResolver] Error parsing LLM resolution: {str(e)}")
                # Create a minimal valid resolution as fallback
                return {
                    "narrative": f"The {active_combatant.get('name', 'combatant')} acted, but a technical error prevented recording the outcome properly.",
                    "updates": [],
                    "action": action,
                    "dice": dice_results
                }
        
        except Exception as e:
            # This is a top-level exception handler to catch any issues in the entire turn processing
            print(f"[CombatResolver] CRITICAL ERROR in _process_turn: {str(e)}")
            import traceback
            traceback.print_exc()
            
            # Return a safe, minimal result to continue combat
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

        prompt = f"""
You are the combat AI for a D&D 5e game, serving as the tactical decision-maker.

# CURRENT COMBAT STATE AT START OF TURN
== Round {round_num} ==

"""
        # Add a clear summary of all combatants with their CURRENT HP values
        prompt += "CURRENT HP STATUS OF ALL COMBATANTS:\n"
        for i, c in enumerate(combatants):
            name = c.get('name', 'Unknown')
            hp = c.get('hp', 0)
            max_hp = c.get('max_hp', hp)
            status = c.get('status', 'OK')
            type_str = "(Active)" if i == active_idx else f"({c.get('type', 'unknown')})"
            prompt += f"- {name} {type_str}: HP {hp}/{max_hp}, Status: {status}\n"
            
        prompt += f"""
# ACTIVE COMBATANT DETAILS
Name: {active.get('name', 'Unknown')}
HP: {active.get('hp', 0)}/{active.get('max_hp', active.get('hp', 0))}
AC: {active.get('ac', 10)}
Type: {active.get('type', 'Unknown')}
Status: {active.get('status', 'OK')}

Abilities: {active.get('abilities', 'Standard abilities')}
Skills: {active.get('skills', 'Standard skills')}
Equipment: {active.get('equipment', 'Standard equipment')}
"""

        # Add information about limited-use abilities if available
        if "limited_use" in active:
            prompt += "\n# LIMITED-USE ABILITIES\n"
            if isinstance(active.get("limited_use"), dict):
                for ability, state in active.get("limited_use", {}).items():
                    prompt += f"- {ability}: {state}\n"
            else:
                prompt += "Limited-use abilities information is not in the expected format.\n"
                
        # Show spell‑slot information if present (expects a dictionary mapping
        # slot level -> remaining/total, e.g., {"1": "2/4", "2": "1/3"}).
        if "spell_slots" in active and isinstance(active["spell_slots"], dict):
            prompt += "\n# SPELL SLOTS REMAINING (level : remaining/total)\n"
            for lvl, slot_state in active["spell_slots"].items():
                prompt += f"- Level {lvl}: {slot_state}\n"
                
        # Add other combatants
        prompt += "\n# OTHER COMBATANTS\n"
        for i, c in enumerate(combatants):
            if i == active_idx:
                continue
            prompt += f"- {c.get('name', 'Unknown')} (HP: {c.get('hp', 0)}/{c.get('max_hp', c.get('hp', 0))}, AC: {c.get('ac', 10)}, Status: {c.get('status', 'OK')})\n"
            
        # Add instructions for the LLM
        prompt += """
# YOUR TASK
Decide the most appropriate action for the active combatant this turn. Consider:
1. Current HP and status - use EXACTLY the HP values shown above
2. Tactical position and opponent state
3. Available abilities, especially limited-use ones
4. D&D 5e rules for actions, bonus actions, and movement
5. Make smart, consistent tactical decisions as a competent combatant would
6. CRITICAL: Use the EXACT HP values listed at the start of this prompt - do NOT assume full health or reset HP values
7. Automatic abilities that trigger on death or at the start/end of the turn (e.g. **Death Burst**, **Death Throes**, **Relentless**, etc.) MUST be resolved when their trigger condition is met.  If a combatant with such a trait is reduced to 0 HP during someone else's turn, include a description of the triggered effect and add any damage/status updates in the "updates" array.
8. Abilities that show a **Recharge X‑Y** mechanic must track availability.  If you use such an ability this turn, add an entry in "updates" to set it to "expended" and include the recharge roll at the start of the creature's following turns.
9. Limited‑use abilities (per short/long rest, per day, etc.) must decrement their remaining uses.
10. When casting spells, you must expend an appropriate spell slot if any remain.  If no slots remain for that level you CANNOT cast a spell that requires it.
11. If an action forces saving throws (e.g., Fireball, Breath Weapon, Turn Undead), YOU must include a dice request for EACH target's saving throw with the DC in the purpose, e.g., {"expression":"1d20+2","purpose":"Goblin Dex save vs DC 13"}.

# RESPONSE FORMAT
Respond with a JSON object containing these fields:
- "action": A detailed description of what the combatant does, including targets and tactics
- "dice_requests": An array of dice expressions needed to resolve the action, each with:
  * "expression": The dice expression (e.g., "1d20+5")
  * "purpose": What this roll is for (e.g., "Attack roll against Goblin")

Example response:
{
  "action": "The Hobgoblin Captain makes a multiattack with its longsword and shield against the Fighter, focusing on dealing damage while maintaining defensive positioning.",
  "dice_requests": [
    {"expression": "1d20+5", "purpose": "Longsword attack roll"},
    {"expression": "1d8+3", "purpose": "Longsword damage if hit"},
    {"expression": "1d20+5", "purpose": "Shield bash attack roll"},
    {"expression": "1d4+3", "purpose": "Shield bash damage if hit"}
  ]
}

Your response MUST be valid JSON that can be parsed, with no extra text before or after.
"""
        return prompt

    def _create_resolution_prompt(self, combatants, active_idx, round_num, action, dice_results):
        """
        Create a prompt for the LLM to resolve the action based on dice results.
        
        Args:
            combatants: List of all combatants
            active_idx: Index of active combatant
            round_num: Current round number
            action: Action description from decision phase
            dice_results: Results of all dice rolls
            
        Returns:
            Prompt string
        """
        try:
            # Defensive check for valid active_idx
            if active_idx < 0 or active_idx >= len(combatants):
                print(f"[CombatResolver] Warning: active_idx {active_idx} out of range in _create_resolution_prompt")
                active_idx = 0  # Use the first combatant as fallback
                
            active = combatants[active_idx]
            
            # Debug: Log that we're creating a resolution prompt with current HP values
            print(f"\n[CombatResolver] DEBUG: Creating resolution prompt with these HP values:")
            print(f"[CombatResolver] DEBUG: Active combatant {active.get('name')}: HP {active.get('hp', 0)}/{active.get('max_hp', active.get('hp', 0))}")
            for i, c in enumerate(combatants):
                if i != active_idx:
                    print(f"[CombatResolver] DEBUG: Other combatant {c.get('name')}: HP {c.get('hp', 0)}/{c.get('max_hp', c.get('hp', 0))}")
            
            prompt = f"""
You are the combat AI for a D&D 5e game, serving as the battle narrator and rules arbiter.

# CURRENT COMBAT STATE AT START OF TURN
== Round {round_num} ==

"""
            # Add a clear summary of all combatants with their CURRENT HP values
            prompt += "CURRENT HP STATUS OF ALL COMBATANTS:\n"
            for i, c in enumerate(combatants):
                name = c.get('name', 'Unknown')
                hp = c.get('hp', 0)
                max_hp = c.get('max_hp', hp)
                status = c.get('status', 'OK')
                type_str = "(Active)" if i == active_idx else f"({c.get('type', 'unknown')})"
                prompt += f"- {name} {type_str}: HP {hp}/{max_hp}, Status: {status}\n"
                
            prompt += f"""
# ACTIVE COMBATANT DETAILS
Name: {active.get('name', 'Unknown')}
HP: {active.get('hp', 0)}/{active.get('max_hp', active.get('hp', 0))}
AC: {active.get('ac', 10)}
Type: {active.get('type', 'Unknown')}
Status: {active.get('status', 'OK')}

# ACTION TAKEN
{action}

# DICE RESULTS
"""
            # Add all dice results
            if dice_results:
                for roll in dice_results:
                    # Check if roll is a valid dictionary with required keys
                    if isinstance(roll, dict) and 'purpose' in roll and 'expression' in roll and 'result' in roll:
                        prompt += f"- {roll['purpose']}: {roll['expression']} = {roll['result']}\n"
                    else:
                        # Handle invalid roll format
                        prompt += f"- Invalid roll format: {roll}\n"
            else:
                prompt += "No dice were rolled for this action.\n"
                
            # Add other combatants
            prompt += "\n# OTHER COMBATANTS\n"
            for i, c in enumerate(combatants):
                if i == active_idx:
                    continue
                prompt += f"- {c.get('name', 'Unknown')} (HP: {c.get('hp', 0)}/{c.get('max_hp', c.get('hp', 0))}, AC: {c.get('ac', 10)}, Status: {c.get('status', 'OK')})\n"
                
            # Add limited-use abilities if any
            if "limited_use" in active:
                prompt += "\n# LIMITED-USE ABILITIES\n"
                if isinstance(active.get("limited_use"), dict):
                    for ability, state in active.get("limited_use", {}).items():
                        prompt += f"- {ability}: {state}\n"
                else:
                    prompt += "Limited-use abilities information is not in the expected format.\n"

            # Show spell‑slot info if present
            if "spell_slots" in active and isinstance(active["spell_slots"], dict):
                prompt += "\n# SPELL SLOTS REMAINING (level : remaining/total)\n"
                for lvl, slot_state in active["spell_slots"].items():
                    prompt += f"- Level {lvl}: {slot_state}\n"

            # Add instructions for resolution
            prompt += """
# YOUR TASK
Resolve the outcome of the action based on the dice results. Follow standard D&D 5e rules:
1. Compare attack rolls to AC to determine hits
2. For attack rolls of 20, it's a critical hit (double damage dice)
3. For attack rolls of 1, it's an automatic miss
4. Apply damage to appropriate targets when attacks hit
5. Update status effects as needed
6. Track usage of limited-use abilities
7. CRITICAL: Use the EXACT current HP values listed at the start of this prompt when calculating remaining HP

# HP AND CONDITION RULES
- When a monster reaches 0 HP, it dies and is removed from combat
- When a character (PC) reaches 0 HP, they become unconscious and must make death saves
- Each failed death save brings a character closer to death
- If a character has 3 failed death saves, they die
- If a character has 3 successful death saves, they stabilize

# ADDITIONAL RULES FOR THIS PHASE
1. If during this resolution any combatant is reduced to 0 HP **and** they possess an on‑death or death burst style trait, immediately resolve that effect (add damage, saving throws, conditions as appropriate) within the same "updates" list.
2. For each Recharge ability you use this turn, include a field "recharge_roll" in the corresponding update like {"ability":"Fire Breath","recharge_roll":"d6 roll result"} so the tracker can mark it available again on a 5‑6 (or stated value).
3. The "updates" array must fully capture changed HP, status conditions, frightened/stunned flags, limited‑use counters, and recharge state so that the UI can stay in sync.
4. If a spell was cast, include an update to the caster's spell slot tracker in the form {"name":"Wizard","spell_slots":{"6":"0/1"}} (example shows 6‑level slot expended).
5. Whenever saving throws are required, ensure the corresponding dice results are listed in the "dice" array you receive and apply half/zero damage as appropriate based on the DC and roll.

# RESPONSE FORMAT
Respond with a JSON object containing these fields:
- "narrative": An engaging, descriptive account of what happened including current HP values
- "updates": An array of combatant updates, each with:
  * "name": The combatant's name
  * "hp": The new HP value (if changed) - ALWAYS USE INTEGER VALUES ONLY, not text descriptions or relative changes like "reduce by X"
  * "status": New status (if changed)
  * "limited_use": Updates to limited-use abilities (if used)
  * "death_saves": For unconscious characters, include status of death saves

EXTREMELY IMPORTANT:
1. ONLY include combatants in the "updates" array if they were actually affected by an action (took damage, healed, etc.)
2. Do NOT include combatants in "updates" just because they were mentioned in the narrative
3. DO NOT update HP values for combatants that were not directly affected
4. For example, if a monster attacks a character, ONLY include the character (target) in the updates, NOT the monster
5. USE EXACTLY THE CURRENT HP VALUES listed above - subtract damage from or add healing to these values

Example response:
{
  "narrative": "The Hobgoblin Captain's longsword slashes across the Fighter's armor, finding a gap and drawing blood (8 damage, reducing Fighter to 24/32 HP). The fighter grimaces but remains ready for battle. The follow-up shield bash misses as the Fighter deftly steps aside.",
  "updates": [
    {
      "name": "Fighter",
      "hp": 24,
      "status": "Wounded"
    }
  ]
}

DO NOT include "Hobgoblin Captain" in the updates array since it did not take damage or have any status changes.

IMPORTANT: 
1. Always include CURRENT HP values in your narrative to help players track the battle state.
2. ALWAYS express HP updates as absolute integer values (e.g., "hp": 24), not as text like "reduce by 5" or relative changes.
3. Your response MUST be valid JSON that can be parsed, with no extra text before or after.
4. For this combat to be interesting, attacks should often hit and do damage. 
5. A roll of 15 or higher almost always hits average AC targets (around 14-16).
6. CRITICAL: Use the exact HP values provided at the start of this prompt. DO NOT RESET TO FULL HP or make up values.
7. Calculate damage from the CURRENT HP values shown at the start of this prompt, not from max HP.
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
        Process an HP update value, handling various formats.
        
        Args:
            target_name: Name of the target for logging
            hp_update: The HP update value (could be int, string, etc.)
            current_hp: Current HP value as integer
            
        Returns:
            new_hp_value: The new HP as an integer
        """
        try:
            # Ensure current_hp is a valid integer
            if not isinstance(current_hp, int):
                try:
                    current_hp = int(current_hp)
                except (ValueError, TypeError):
                    print(f"[CombatResolver] Warning: Invalid current_hp '{current_hp}' for {target_name}, defaulting to 0")
                    current_hp = 0
            
            # Default to keeping current HP
            new_hp_value = current_hp
            
            # First try to convert directly to int if it's already an integer
            if isinstance(hp_update, int):
                new_hp_value = max(0, hp_update)
                print(f"[CombatResolver] Integer HP value {new_hp_value} for {target_name}")
            elif isinstance(hp_update, str):
                # Sanitize the string - remove whitespace and non-numeric characters for better parsing
                hp_string = hp_update.strip()
                
                # Try direct conversion if it's a simple number string
                if hp_string.isdigit():
                    new_hp_value = max(0, int(hp_string))
                    print(f"[CombatResolver] String digit HP value {new_hp_value} for {target_name}")
                # Check for "reduce by X" format
                elif "reduce" in hp_string.lower():
                    import re
                    damage_match = re.search(r'\d+', hp_string)
                    if damage_match:
                        damage = int(damage_match.group(0))
                        new_hp_value = max(0, current_hp - damage)
                        print(f"[CombatResolver] Reduced {target_name}'s HP by {damage} to {new_hp_value}")
                # Check for "X damage" format
                elif "damage" in hp_string.lower():
                    import re
                    damage_match = re.search(r'\d+', hp_string)
                    if damage_match:
                        damage = int(damage_match.group(0))
                        new_hp_value = max(0, current_hp - damage)
                        print(f"[CombatResolver] Damage format: reduced {target_name}'s HP by {damage} to {new_hp_value}")
                # Check for explicit "current - X" format
                elif "-" in hp_string and not hp_string.startswith("-"):
                    # Try to parse as a subtraction expression like "50 - 10"
                    try:
                        parts = hp_string.split("-", 1)
                        if len(parts) == 2 and parts[0].strip().isdigit():
                            # Treat the first number as a base and then subtract
                            base = int(parts[0].strip())
                            subtrahend = int(parts[1].strip())
                            new_hp_value = max(0, base - subtrahend)
                            print(f"[CombatResolver] Subtraction format: {base} - {subtrahend} = {new_hp_value} for {target_name}")
                        else:
                            # Try to extract any number from the string
                            import re
                            match = re.search(r'\d+', hp_string)
                            if match:
                                extracted_hp = int(match.group(0))
                                new_hp_value = max(0, extracted_hp)
                                print(f"[CombatResolver] Extracted HP value {new_hp_value} from string '{hp_string}' for {target_name}")
                    except (ValueError, TypeError):
                        # If parsing fails, just extract any numbers
                        import re
                        match = re.search(r'\d+', hp_string)
                        if match:
                            extracted_hp = int(match.group(0))
                            new_hp_value = max(0, extracted_hp)
                            print(f"[CombatResolver] After subtraction parsing failed, extracted HP value {new_hp_value} from string '{hp_string}' for {target_name}")
                # Try to extract any number from the string as last resort
                else:
                    import re
                    match = re.search(r'\d+', hp_string)
                    if match:
                        extracted_hp = int(match.group(0))
                        # Check if it's much smaller than current HP, it might be damage
                        if extracted_hp < current_hp / 2 and "damage" in hp_string.lower():
                            new_hp_value = max(0, current_hp - extracted_hp)
                            print(f"[CombatResolver] Inferred damage: reduced {target_name}'s HP by {extracted_hp} to {new_hp_value}")
                        else:
                            new_hp_value = max(0, extracted_hp)
                            print(f"[CombatResolver] Extracted HP value {new_hp_value} from string '{hp_string}' for {target_name}")
                    else:
                        print(f"[CombatResolver] Warning: Could not extract HP value from '{hp_string}' for {target_name}")
            else:
                print(f"[CombatResolver] Warning: Unexpected HP type {type(hp_update)} for {target_name}")
                
            # Final safety check: don't allow completely unreasonable HP changes
            # If the new HP is more than triple the current HP, cap it
            if new_hp_value > current_hp * 3 and current_hp > 10:
                capped_value = int(current_hp * 3)
                print(f"[CombatResolver] Warning: Capping unreasonable HP increase for {target_name}: {current_hp} -> {new_hp_value}, capped to {capped_value}")
                new_hp_value = capped_value
                
            # If HP goes from positive to zero in one hit and it's a big creature (hp > 50)
            # that's probably an error, so keep it at 1 HP instead
            if current_hp > 50 and new_hp_value == 0:
                print(f"[CombatResolver] Warning: Preventing one-shot kill of {target_name} with {current_hp} HP, setting to 1 HP instead of 0")
                new_hp_value = 1
                
            return new_hp_value
        except Exception as e:
            print(f"[CombatResolver] Error processing HP update for {target_name}: {str(e)}")
            import traceback
            traceback.print_exc()
            # Return current HP on error to avoid changing values when errors occur
            return current_hp 