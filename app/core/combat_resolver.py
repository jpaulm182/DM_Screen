"""
Core component for resolving combat encounters using LLM.

This class takes the current combat state and uses an LLM to generate
tactical decisions, which are then executed with dice rolls and
properly reflected in the UI.
"""

from app.core.llm_service import LLMService
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
                                        # Update HP if specified
                                        hp_changed = False
                                        if "hp" in update:
                                            # Check if the update is a string like "reduce by 5"
                                            hp_update = update["hp"]
                                            current_hp = c.get("hp", 0)
                                            new_hp = current_hp # Default to current HP

                                            if isinstance(hp_update, str) and "reduce" in hp_update.lower():
                                                # Extract damage amount
                                                import re
                                                damage_match = re.search(r'\d+', hp_update)
                                                if damage_match:
                                                    damage = int(damage_match.group(0))
                                                    new_hp = max(0, current_hp - damage)
                                                    print(f"[CombatResolver] Reduced {target_name}'s HP by {damage} to {new_hp}")
                                            else:
                                                try:
                                                    new_hp = int(update["hp"])
                                                except (ValueError, TypeError):
                                                    print(f"[CombatResolver] Invalid HP value: {update['hp']}")
                                                    new_hp = current_hp # Keep current HP if update is invalid

                                            # Apply the new HP if it changed
                                            if new_hp != current_hp:
                                                c["hp"] = new_hp
                                                hp_changed = True

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
                            combat_display_state = {
                                "round": round_num,
                                "current_turn_index": idx,
                                "combatants": combatants,
                                "latest_action": turn_log_entry
                            }
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
        active_combatant = combatants[active_idx]
        print(f"[CombatResolver] Processing turn for {active_combatant.get('name', 'Unknown')} (round {round_num})")
        
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
            model_id = self.llm_service.get_available_models()[0]["id"]
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
            # Extract the first JSON object from the response
            json_match = re.search(r'\{[\s\S]*\}', decision_response)
            if not json_match:
                print(f"[CombatResolver] Could not find JSON in LLM decision response")
                return None
                
            json_str = json_match.group(0)
            decision = json.loads(json_str)
            
            # Validate required fields
            if "action" not in decision or "dice_requests" not in decision:
                print(f"[CombatResolver] Missing required fields in decision: {decision}")
                return None
                
            action = decision["action"]
            dice_requests = decision.get("dice_requests", [])
        except Exception as e:
            print(f"[CombatResolver] Error parsing LLM decision: {str(e)}")
            return None
            
        # 4. Roll dice as requested
        dice_results = []
        for req in dice_requests:
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
                    return None
        
        # 5. Send dice results to LLM for resolution
        resolution_prompt = self._create_resolution_prompt(
            combatants, active_idx, round_num, action, dice_results)
            
        try:
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
            return None
            
        # 6. Parse the resolution
        try:
            # Extract the first JSON object from the response
            json_match = re.search(r'\{[\s\S]*\}', resolution_response)
            if not json_match:
                print(f"[CombatResolver] Could not find JSON in LLM resolution response")
                return None
                
            json_str = json_match.group(0)
            resolution = json.loads(json_str)
            
            # Add the original action and dice rolls to the resolution
            resolution["action"] = action
            resolution["dice"] = dice_results
            
            return resolution
        except Exception as e:
            print(f"[CombatResolver] Error parsing LLM resolution: {str(e)}")
            return None
            
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

# COMBAT STATE
Round: {round_num}
Active combatant: {active.get('name', 'Unknown')} (currently taking their turn)

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
            prompt += "\nLimited-use abilities:\n"
            for ability, state in active.get("limited_use", {}).items():
                prompt += f"- {ability}: {state}\n"
                
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
1. Current HP and status
2. Tactical position and opponent state
3. Available abilities, especially limited-use ones
4. D&D 5e rules for actions, bonus actions, and movement
5. Make smart, consistent tactical decisions as a competent combatant would

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
        active = combatants[active_idx]
        
        prompt = f"""
You are the combat AI for a D&D 5e game, serving as the battle narrator and rules arbiter.

# COMBAT STATE
Round: {round_num}
Active combatant: {active.get('name', 'Unknown')} (currently taking their turn)

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
        for roll in dice_results:
            prompt += f"- {roll['purpose']}: {roll['expression']} = {roll['result']}\n"
            
        # Add other combatants
        prompt += "\n# OTHER COMBATANTS\n"
        for i, c in enumerate(combatants):
            if i == active_idx:
                continue
            prompt += f"- {c.get('name', 'Unknown')} (HP: {c.get('hp', 0)}/{c.get('max_hp', c.get('hp', 0))}, AC: {c.get('ac', 10)}, Status: {c.get('status', 'OK')})\n"
            
        # Add limited-use abilities if any
        if "limited_use" in active:
            prompt += "\n# LIMITED-USE ABILITIES\n"
            for ability, state in active.get("limited_use", {}).items():
                prompt += f"- {ability}: {state}\n"
                
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

# HP AND CONDITION RULES
- When a monster reaches 0 HP, it dies and is removed from combat
- When a character (PC) reaches 0 HP, they become unconscious and must make death saves
- Each failed death save brings a character closer to death
- If a character has 3 failed death saves, they die
- If a character has 3 successful death saves, they stabilize

# RESPONSE FORMAT
Respond with a JSON object containing these fields:
- "narrative": An engaging, descriptive account of what happened including current HP values
- "updates": An array of combatant updates, each with:
  * "name": The combatant's name
  * "hp": The new HP value (if changed)
  * "status": New status (if changed)
  * "limited_use": Updates to limited-use abilities (if used)
  * "death_saves": For unconscious characters, include status of death saves

Example response:
{
  "narrative": "The Hobgoblin Captain's longsword slashes across the Fighter's armor, finding a gap and drawing blood (8 damage, reducing Fighter to 24/32 HP). The fighter grimaces but remains ready for battle. The follow-up shield bash misses as the Fighter deftly steps aside.",
  "updates": [
    {
      "name": "Fighter",
      "hp": 24,
      "status": "Wounded"
    },
    {
      "name": "Hobgoblin Captain",
      "limited_use": {
        "Leadership Ability": "Used (0/1 remaining)"
      }
    }
  ]
}

IMPORTANT: Always include CURRENT HP values in your narrative to help players track the battle state.
Your response MUST be valid JSON that can be parsed, with no extra text before or after.
For this combat to be interesting, attacks should often hit and do damage. 
A roll of 15 or higher almost always hits average AC targets (around 14-16).
"""
        return prompt

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