"""
Improved Combat Resolver with enhanced D&D 5e initiative mechanics.

This module integrates the ImprovedInitiative system with the original CombatResolver
to create a more realistic and rule-compliant combat experience in D&D 5e.
"""

from app.core.combat_resolver import CombatResolver
from app.core.improved_initiative import ImprovedInitiative
from app.combat.action_economy import ActionEconomyManager, ActionType
from app.core.initiative_integration import (
    initialize_combat_with_improved_initiative,
    update_combat_state_for_next_round,
    record_ready_action,
    trigger_held_action,
    get_next_combatant
)
import copy
import logging
import re
from typing import Dict, List, Any, Optional

# Import QObject and Signal for thread-safe communication
from PySide6.QtCore import QObject, Signal

# Import the monster ability validator
from app.core.utils.monster_ability_validator import (
    extract_ability_names,
    get_canonical_abilities,
    validate_combat_prompt,
    clean_abilities_in_prompt,
    fix_mixed_abilities_in_prompt,
    verify_abilities_match_monster
)

logger = logging.getLogger(__name__)

class ImprovedCombatResolver(QObject):
    """
    Enhanced combat resolver that integrates improved initiative handling.
    """
    # Define a signal to emit results thread-safely
    resolution_complete = Signal(object, object)
    
    def __init__(self, llm_service):
        """Initialize the ImprovedCombatResolver with the LLM service."""
        super().__init__()
        self.llm_service = llm_service
        self.combat_resolver = CombatResolver(llm_service)
        
        # Apply patches to the combat resolver to ensure ability validation
        from app.core.combat_resolver_patch import combat_resolver_patch
        
        # Create mock app_state for patching
        class MockAppState:
            def __init__(self, resolver):
                self.combat_resolver = resolver
        
        app_state = MockAppState(self.combat_resolver)
        combat_resolver_patch(app_state)
        
        # Connect the combat resolver's signal to our own signal
        self.combat_resolver.resolution_complete.connect(
            lambda result, error: self.resolution_complete.emit(result, error)
        )
        
    def resolve_combat_turn_by_turn(self, combat_state, dice_roller, callback, update_ui_callback=None):
        """
        Resolve combat turn-by-turn with enhanced initiative handling.
        
        Args:
            combat_state: Dictionary with current combat state (combatants, round, etc.)
            dice_roller: Function that rolls dice (takes expression, returns result)
            callback: Function called with final result or error (DEPRECATED)
            update_ui_callback: Function called after each turn to update UI
        """
        import threading
        
        def run_resolution():
            try:
                # First, clean the combat state by validating all monster abilities
                validated_state = self.prepare_combat_data(combat_state)
                
                # Next, enhance the combat state with improved initiative handling
                enhanced_state = initialize_combat_with_improved_initiative(validated_state)
                
                # We'll use our own turn processing logic instead of delegating to the original resolver
                self._process_combat_with_improved_initiative(
                    enhanced_state, dice_roller, update_ui_callback
                )
                
            except Exception as e:
                import traceback
                traceback.print_exc()
                # Emit signal with no result and the error message
                self.resolution_complete.emit(None, f"Error in improved turn-by-turn resolution: {str(e)}")
        
        # Run in a background thread
        threading.Thread(target=run_resolution).start()
        
    def _process_combat_with_improved_initiative(self, state, dice_roller, update_ui_callback=None):
        """
        Process combat turns using the improved initiative system.
        
        Args:
            state: Enhanced combat state with initiative information
            dice_roller: Function to roll dice
            update_ui_callback: Function to update the UI between turns
        """
        import time
        
        # Extract necessary components
        combatants = state.get("combatants", [])
        round_num = state.get("round", 1)
        max_rounds = 50  # Failsafe to prevent infinite loops
        log = []  # Combat log for transparency
        
        # Main combat loop
        while round_num <= max_rounds:
            print(f"[ImprovedCombatResolver] Starting round {round_num}")
            
            # Reset reactions for all combatants at the start of a new round
            combatants = ActionEconomyManager.reset_reactions(combatants)
            
            # Reset legendary actions for all legendary creatures at the start of a new round
            combatants = ActionEconomyManager.reset_legendary_actions(combatants)
            print(f"[ImprovedCombatResolver] Reset legendary actions for all legendary creatures at the start of round {round_num}")
            
            # Get active combatants for this round
            active_combatants = state.get("active_combatants", [])
            
            # Check if combat should end
            if not active_combatants:
                print("[ImprovedCombatResolver] No active combatants, ending combat")
                break
                
            # Check if all monsters or all characters are defeated
            remaining_monsters = [i for i in active_combatants if 
                                 combatants[i].get("type", "").lower() == "monster"]
            remaining_characters = [i for i in active_combatants if 
                                   combatants[i].get("type", "").lower() != "monster"]
            
            if not remaining_monsters:
                print("[ImprovedCombatResolver] All monsters defeated, ending combat")
                break
                
            if not remaining_characters:
                print("[ImprovedCombatResolver] All characters defeated, ending combat")
                break
            
            # Process each combatant's turn in initiative order
            current_idx = None
            while True:
                # Get the next combatant in the initiative order
                next_idx, end_of_round = get_next_combatant(state, current_idx)
                
                # If we've reached the end of the round, break to the next round
                if end_of_round:
                    break
                    
                current_idx = next_idx
                combatant = combatants[current_idx]
                
                # Check if the combatant is dead or inactive
                if combatant.get("hp", 0) <= 0 and combatant.get("status", "").lower() == "dead":
                    continue
                
                # For unconscious characters, process death saves
                if combatant.get("type", "").lower() != "monster" and combatant.get("hp", 0) <= 0 and combatant.get("status", "").lower() in ["unconscious", ""]:
                    self._process_death_save(combatant, state, current_idx, round_num, log, update_ui_callback)
                    continue
                
                # Process normal turn for conscious combatants
                self._process_turn_with_improved_initiative(
                    state, current_idx, round_num, dice_roller, log, update_ui_callback
                )
                
                # Check if combat should end after this turn
                if self._should_end_combat(state):
                    break
            
            # If combat should end, break out of the round loop
            if self._should_end_combat(state):
                break
            
            # End of round, update state for the next round
            state = update_combat_state_for_next_round(state)
            round_num = state.get("round", round_num + 1)
            
            # Check if we've hit the maximum rounds
            if round_num > max_rounds:
                print(f"[ImprovedCombatResolver] Maximum rounds ({max_rounds}) reached, ending combat")
                break
        
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
    
    def _process_death_save(self, combatant, state, combatant_idx, round_num, log, update_ui_callback=None):
        """
        Process death saves for unconscious characters using the original implementation.
        
        Args:
            combatant: The unconscious combatant
            state: Current combat state
            combatant_idx: Index of the combatant
            round_num: Current round number
            log: Combat log to append to
            update_ui_callback: Function to update the UI
        """
        # Call the original implementation
        self.combat_resolver._process_death_save(combatant)
        
        # Create a log entry
        turn_log_entry = {
            "round": round_num,
            "turn": combatant_idx,
            "actor": combatant.get("name", "Unknown"),
            "action": "Makes a death saving throw",
            "dice": [{"expression": "1d20", "result": "See death saves", "purpose": "Death Save"}],
            "result": f"Current death saves: {combatant.get('death_saves', {}).get('successes', 0)} successes, {combatant.get('death_saves', {}).get('failures', 0)} failures"
        }
        log.append(turn_log_entry)
        
        # Update the UI
        if update_ui_callback:
            # Create a display state that includes the latest action
            combat_display_state = {
                "round": round_num,
                "current_turn_index": combatant_idx,
                "combatants": state.get("combatants", []),
                "latest_action": turn_log_entry
            }
            update_ui_callback(combat_display_state)
            import time
            time.sleep(0.5)
    
    def _process_turn_with_improved_initiative(self, state, combatant_idx, round_num, dice_roller, log, update_ui_callback=None):
        """
        Process a single combatant's turn with improved initiative handling.
        
        Args:
            state: Current combat state with initiative information
            combatant_idx: Index of the active combatant
            round_num: Current round number
            dice_roller: Function to roll dice
            log: Combat log to append to
            update_ui_callback: Function to update the UI
        """
        import time
        import json
        
        combatants = state.get("combatants", [])
        combatant = combatants[combatant_idx]
        
        # Validate monster abilities if this is a monster
        if combatant.get("type", "").lower() == "monster":
            # Validate abilities to ensure no mixing
            combatant = self.validate_monster_abilities(combatant)
            # Update the combatant in the state
            combatants[combatant_idx] = combatant
            
        # Initialize action economy for this combatant's turn
        combatant = ActionEconomyManager.initialize_action_economy(combatant)
        
        # Check for conditions that affect this turn
        has_condition_effects = False
        condition_effects = []
        
        if "conditions" in combatant:
            # Process condition effects
            for condition_name, condition_data in combatant.get("conditions", {}).items():
                if condition_name == "stunned":
                    # Stunned creatures can't take actions
                    turn_log_entry = {
                        "round": round_num,
                        "turn": combatant_idx,
                        "actor": combatant.get("name", "Unknown"),
                        "action": "Is stunned and cannot act",
                        "dice": [],
                        "result": f"{combatant.get('name', 'Unknown')} is stunned and loses their turn."
                    }
                    log.append(turn_log_entry)
                    has_condition_effects = True
                    
                    # Update UI
                    if update_ui_callback:
                        combat_display_state = {
                            "round": round_num,
                            "current_turn_index": combatant_idx,
                            "combatants": combatants,
                            "latest_action": turn_log_entry
                        }
                        update_ui_callback(combat_display_state)
                        time.sleep(0.5)
                    
                    # Skip this turn
                    return
                
                # Add other condition effects as needed
                
                # Track condition effects for LLM prompt
                condition_effects.append(condition_name)
        
        try:
            # Use our own decision prompt method to ensure ability validation
            decision_prompt = self._create_decision_prompt(combatants, combatant_idx, round_num)
            
            # Send the prompt to the LLM
            model = self.llm_service.get_available_models()[0]["id"]
            
            # Format the prompt as a message for the LLM
            messages = [{
                "role": "user",
                "content": decision_prompt
            }]
            
            # Get the LLM response
            response_text = self.llm_service.generate_completion(
                model=model,
                messages=messages,
                temperature=0.7,
                max_tokens=1000
            )
            
            # Parse the response
            try:
                decision = json.loads(response_text)
                
                # Create a turn result in the expected format
                turn_result = {
                    "action": decision.get("action", f"{combatant.get('name', 'Unknown')} takes no action."),
                    "narrative": decision.get("narrative", decision.get("action", "")),
                    "dice": [], 
                    "updates": []
                }
                
                # Process dice rolls if requested
                if "dice_requests" in decision and isinstance(decision["dice_requests"], list):
                    dice_rolls = []
                    
                    for request in decision["dice_requests"]:
                        if "expression" in request and "purpose" in request:
                            result = dice_roller(request["expression"])
                            dice_rolls.append({
                                "expression": request["expression"],
                                "result": result,
                                "purpose": request["purpose"]
                            })
                    
                    turn_result["dice"] = dice_rolls
                
                # Process target updates
                if "target" in decision:
                    target_name = decision["target"]
                    for i, target in enumerate(combatants):
                        if target.get("name", "") == target_name:
                            # Found the target, apply damage or effects
                            if "damage" in decision:
                                damage = int(decision["damage"]) if isinstance(decision["damage"], (int, float)) else 0
                                if damage > 0:
                                    # Apply damage to the target
                                    current_hp = target.get("hp", 0)
                                    new_hp = max(0, current_hp - damage)
                                    
                                    # Check if the target is defeated
                                    status = target.get("status", "")
                                    if new_hp == 0 and status != "dead":
                                        status = "unconscious" if target.get("type", "").lower() != "monster" else "dead"
                                    
                                    # Create an update
                                    update = {
                                        "name": target_name,
                                        "hp": new_hp,
                                        "status": status
                                    }
                                    turn_result["updates"].append(update)
                            break
            except json.JSONDecodeError:
                # Fallback for invalid JSON
                logger.error(f"Error parsing LLM response as JSON: {response_text[:100]}...")
                turn_result = {
                    "action": f"{combatant.get('name', 'Unknown')} takes no action due to confusion.",
                    "narrative": f"{combatant.get('name', 'Unknown')} looks confused and takes no action this turn.",
                    "updates": []
                }
        except Exception as e:
            # Error processing turn - create a basic result to continue
            logger.error(f"[ImprovedCombatResolver] Error processing turn for {combatant.get('name', 'Unknown')}: {str(e)}")
            turn_result = {
                "action": f"{combatant.get('name', 'Unknown')} takes no action due to confusion.",
                "narrative": f"{combatant.get('name', 'Unknown')} looks confused and takes no action this turn.",
                "updates": []
            }
        
        # Process action economy for the turn
        turn_result = self._process_action_economy_for_turn(combatant, turn_result, state)
        
        # Add turn to log
        turn_log_entry = {
            "round": round_num,
            "turn": combatant_idx,
            "actor": combatant.get("name", "Unknown"),
            "action": turn_result.get("action", ""),
            "dice": turn_result.get("dice", []),
            "result": turn_result.get("narrative", ""),
            "action_economy": combatant.get("action_economy", {})  # Include action economy info in log
        }
        log.append(turn_log_entry)
        
        # Apply combatant updates
        if "updates" in turn_result:
            # Apply updates to combatants
            self._apply_combatant_updates(state, turn_result["updates"])
        
        # Update the UI
        if update_ui_callback:
            import copy
            combat_display_state = {
                "round": round_num,
                "current_turn_index": combatant_idx,
                "combatants": copy.deepcopy(combatants),
                "latest_action": turn_log_entry
            }
            update_ui_callback(combat_display_state)
            time.sleep(0.5)
    
    def _process_action_economy_for_turn(self, combatant, turn_result, state):
        """
        Process action economy for a combatant's turn.
        
        Args:
            combatant: The active combatant
            turn_result: The result of processing the turn
            state: Current combat state
            
        Returns:
            Updated turn result with action economy information
        """
        # Extract the decision from the turn result
        action_description = turn_result.get("action", "")
        
        # Create a simplified decision object based on the action description
        decision = {"action_type": "action"}  # Default to standard action
        
        # Check for specific action types in the description
        lower_action = action_description.lower()
        
        # Bonus action detection
        if "bonus action" in lower_action:
            decision["action_type"] = "bonus_action"
        
        # Movement detection - try to extract distance
        movement_detected = False
        movement_dist = 0
        
        if "moves" in lower_action or "movement" in lower_action:
            import re
            # Look for patterns like "moves 30 feet" or "moves 15'"
            movement_match = re.search(r'moves (\d+)\s*(?:feet|ft|\')?', lower_action)
            if movement_match:
                movement_dist = int(movement_match.group(1))
                decision["action_type"] = "movement"
                decision["movement_cost"] = movement_dist
                movement_detected = True
        
        # Save previous position for opportunity attack checks
        previous_position = None
        if movement_detected and "position" in combatant:
            import copy
            previous_position = copy.deepcopy(combatant.get("position", {}))
        
        # Apply the action economy for this decision
        combatant, success, reason = ActionEconomyManager.process_action_decision(
            combatant, decision
        )
        
        # Update the turn result with action economy information
        if not success:
            # Append action economy failure reason to narrative
            turn_result["narrative"] = f"{turn_result.get('narrative', '')}\nHowever, {reason}."
        
        # Check for opportunity attacks if movement was successful
        opportunity_attacks = []
        if movement_detected and success and previous_position:
            # Apply position updates from the turn result first
            if "updates" in turn_result:
                for update in turn_result["updates"]:
                    if update.get("name") == combatant.get("name") and "position" in update:
                        # Position has been updated, check for opportunity attacks
                        opportunity_attacks = self._process_opportunity_attacks(
                            combatant, 
                            state.get("combatants", []), 
                            previous_position
                        )
                        break
            
            # If opportunity attacks occurred, append them to the turn result
            if opportunity_attacks:
                # Add opportunity attack narratives to the turn result
                opportunity_text = "\n".join([attack.get("narrative", "") for attack in opportunity_attacks])
                turn_result["narrative"] = f"{turn_result.get('narrative', '')}\n\n{opportunity_text}"
                
                # Add opportunity attacks to the turn result for processing
                if "opportunity_attacks" not in turn_result:
                    turn_result["opportunity_attacks"] = []
                turn_result["opportunity_attacks"].extend(opportunity_attacks)
        
        # Add action economy info to the result
        turn_result["action_economy"] = {
            "action_type": decision["action_type"],
            "success": success,
            "reason": reason if not success else "",
            "available_actions": ActionEconomyManager.check_available_actions(combatant),
            "opportunity_attacks": len(opportunity_attacks) if opportunity_attacks else 0
        }
        
        return turn_result
        
    def _process_opportunity_attacks(self, moving_combatant, combatants, previous_position):
        """
        Process opportunity attacks triggered by movement.
        
        Args:
            moving_combatant: The combatant that moved
            combatants: All combatants in the encounter
            previous_position: The combatant's position before movement
            
        Returns:
            List of processed opportunity attack results
        """
        import random
        
        # Check if any opportunity attacks are triggered
        opportunity_attacks = ActionEconomyManager.check_opportunity_attacks(
            moving_combatant, combatants, previous_position
        )
        
        processed_attacks = []
        
        # Process each opportunity attack
        for attack in opportunity_attacks:
            # Find the attacker and target combatants
            attacker = None
            target = moving_combatant  # The moving combatant is always the target
            
            for c in combatants:
                if c.get("name") == attack["attacker"]:
                    attacker = c
                    break
                    
            if not attacker:
                continue
                
            # Simplified attack roll simulation
            # In a real implementation, this would use the proper attack calculations
            attack_bonus = attacker.get("attack_bonus", 0)
            target_ac = target.get("ac", 10)
            
            # Roll d20 + attack bonus
            attack_roll = random.randint(1, 20)
            total_attack = attack_roll + attack_bonus
            
            critical = attack_roll == 20
            hit = critical or total_attack >= target_ac
            
            if hit:
                # Calculate damage (simplified)
                damage_dice = attacker.get("damage_dice", "1d6")
                damage_bonus = attacker.get("damage_bonus", 0)
                
                # Parse damage dice (e.g., "2d6+3" becomes 2 rolls of d6 + 3)
                import re
                dice_match = re.match(r'(\d+)?d(\d+)(?:\+(\d+))?', damage_dice)
                if dice_match:
                    num_dice = int(dice_match.group(1) or 1)
                    die_size = int(dice_match.group(2))
                    bonus = int(dice_match.group(3) or 0)
                    
                    # Roll damage
                    damage = sum(random.randint(1, die_size) for _ in range(num_dice)) + bonus + damage_bonus
                    
                    # Double damage on critical hit
                    if critical:
                        damage = damage * 2
                        
                    # Apply damage to target
                    target["hp"] = max(0, target["hp"] - damage)
                    
                    # Update the attack result
                    attack["hit"] = True
                    attack["critical"] = critical
                    attack["damage"] = damage
                    attack["attack_roll"] = total_attack
                    attack["target_ac"] = target_ac
                    attack["narrative"] = f"{attacker['name']} makes an opportunity attack against {target['name']} as they move away! {attacker['name']} hits with a {total_attack} vs AC {target_ac}" + (f" (CRITICAL HIT!)" if critical else "") + f", dealing {damage} damage."
                else:
                    # Default damage if dice format is invalid
                    damage = random.randint(1, 6) + damage_bonus
                    target["hp"] = max(0, target["hp"] - damage)
                    
                    attack["hit"] = True
                    attack["damage"] = damage
                    attack["attack_roll"] = total_attack
                    attack["target_ac"] = target_ac
                    attack["narrative"] = f"{attacker['name']} makes an opportunity attack against {target['name']} as they move away! {attacker['name']} hits with a {total_attack} vs AC {target_ac}, dealing {damage} damage."
            else:
                # Attack missed
                attack["hit"] = False
                attack["attack_roll"] = total_attack
                attack["target_ac"] = target_ac
                attack["narrative"] = f"{attacker['name']} makes an opportunity attack against {target['name']} as they move away, but misses with a {total_attack} vs AC {target_ac}."
                
            processed_attacks.append(attack)
            
        return processed_attacks
    
    def _apply_combatant_updates(self, state, updates):
        """
        Apply updates to combatants with validation.
        
        Args:
            state: Current combat state
            updates: List of update dictionaries
        """
        combatants = state.get("combatants", [])
        
        # Create a copy of the original HP values for verification
        original_hp_values = {i: c.get("hp", 0) for i, c in enumerate(combatants) if "name" in c}
        
        # Track HP changes for debugging
        hp_changes = {}
        
        for update in updates:
            # Skip updates without a name
            if "name" not in update:
                print(f"[ImprovedCombatResolver] WARNING: Skipping update without 'name' field: {update}")
                continue
            
            # Find the combatant
            target_name = update["name"]
            target_idx = None
            
            for i, c in enumerate(combatants):
                if c.get("name") == target_name:
                    target_idx = i
                    break
            
            if target_idx is None:
                print(f"[ImprovedCombatResolver] WARNING: Combatant {target_name} not found, skipping update")
                continue
            
            # Apply updates
            combatant = combatants[target_idx]
            
            # Update HP if specified
            hp_changed = False
            if "hp" in update:
                # Validate HP update
                try:
                    current_hp = combatant.get("hp", 0)
                    new_hp = update["hp"]
                    
                    # Convert to integer if needed
                    if isinstance(new_hp, str):
                        try:
                            new_hp = int(new_hp)
                        except ValueError:
                            print(f"[ImprovedCombatResolver] WARNING: Invalid HP value {new_hp}, skipping")
                            continue
                    
                    # Check if HP change is reasonable
                    max_hp = combatant.get("max_hp", current_hp * 2)
                    hp_change = new_hp - current_hp
                    
                    # Cap healing at max HP
                    if new_hp > max_hp:
                        new_hp = max_hp
                    
                    # Apply the change
                    combatant["hp"] = new_hp
                    hp_changed = True
                    
                    # Track change for debugging
                    hp_changes[target_idx] = {
                        "before": current_hp,
                        "after": new_hp,
                        "change": hp_change
                    }
                    
                except Exception as e:
                    print(f"[ImprovedCombatResolver] ERROR applying HP update: {e}")
            
            # Update status if specified
            status_updated = False
            if "status" in update:
                combatant["status"] = update["status"]
                status_updated = True
            
            # If HP changed to 0 or below and status wasn't updated, apply default status
            if hp_changed and combatant["hp"] <= 0 and not status_updated:
                if combatant.get("type", "").lower() == "monster":
                    combatant["status"] = "Dead"
                else:
                    combatant["status"] = "Unconscious"
                    # Initialize death saves
                    if "death_saves" not in combatant:
                        combatant["death_saves"] = {"successes": 0, "failures": 0}
            
            # Update conditions if specified
            if "conditions" in update:
                if "conditions" not in combatant:
                    combatant["conditions"] = {}
                
                # Apply each condition
                for condition_name, condition_data in update.get("conditions", {}).items():
                    combatant["conditions"][condition_name] = condition_data
            
            # Update other attributes as needed
            for key, value in update.items():
                if key not in ["name", "hp", "status", "conditions"]:
                    combatant[key] = value
        
        # Debug: Print HP changes
        for idx, change in hp_changes.items():
            name = combatants[idx].get("name", f"Combatant {idx}")
            print(f"[ImprovedCombatResolver] HP change for {name}: {change['before']} -> {change['after']} (Δ{change['change']})")
    
    def _should_end_combat(self, state):
        """
        Determine if combat should end based on the current state.
        
        Args:
            state: Current combat state
            
        Returns:
            True if combat should end, False otherwise
        """
        combatants = state.get("combatants", [])
        
        # Check remaining combatants
        remaining_monsters = [c for c in combatants if 
                             c.get("type", "").lower() == "monster" and 
                             c.get("hp", 0) > 0 and 
                             c.get("status", "").lower() != "dead"]
        
        remaining_characters = [c for c in combatants if 
                               c.get("type", "").lower() != "monster" and 
                               (c.get("hp", 0) > 0 or 
                                c.get("status", "").lower() in ["unconscious", "stable"])]
        
        # End combat if no combatants remain
        if not remaining_monsters and not remaining_characters:
            return True
            
        # End combat if no monsters remain
        if not remaining_monsters:
            return True
            
        # End combat if no characters remain
        if not remaining_characters:
            return True
            
        # Combat continues
        return False

    def validate_monster_abilities(self, monster_data):
        """
        Validate that a monster's abilities are consistent and not mixed with other monsters.
        This method performs a thorough cleaning of the monster's abilities to ensure
        it only has abilities that canonically belong to it.
        
        Args:
            monster_data: Dictionary with monster data
            
        Returns:
            Validated monster data with any invalid abilities removed
        """
        if not monster_data or not isinstance(monster_data, dict):
            logger.warning("Cannot validate abilities for invalid monster data")
            return monster_data
        
        monster_name = monster_data.get("name", "Unknown Monster")
        logger.info(f"Validating abilities for monster: {monster_name}")
        
        # Extract canonical abilities for this specific monster type
        canonical_abilities = get_canonical_abilities(monster_name, monster_data)
        logger.info(f"Found {len(canonical_abilities)} canonical abilities for {monster_name}")
        
        # Get typical abilities for this monster type from our database or template
        # This helps with monsters that might be missing their standard abilities
        monster_type = monster_data.get("type", "").lower()
        
        # Add type-specific canonical abilities if needed
        if monster_type == "dragon" or "dragon" in monster_name.lower():
            dragon_abilities = {"breath weapon", "frightful presence", "multiattack", "bite", "claw", "tail"}
            canonical_abilities.update(dragon_abilities)
            logger.info(f"Added dragon-specific abilities to {monster_name}")
        elif monster_type == "undead" or "skeleton" in monster_name.lower() or "zombie" in monster_name.lower():
            undead_abilities = {"undead fortitude", "undead nature", "multiattack", "claw", "bone attack"}
            canonical_abilities.update(undead_abilities)
            logger.info(f"Added undead-specific abilities to {monster_name}")
        elif "elemental" in monster_type or "elemental" in monster_name.lower() or "mephit" in monster_name.lower():
            elemental_abilities = {"elemental nature", "innate spellcasting", "multiattack", "slam", "touch"}
            # Add element-specific abilities based on name
            if "fire" in monster_name.lower() or "magma" in monster_name.lower() or "flame" in monster_name.lower():
                elemental_abilities.update({"fire form", "heated body", "fire breath", "fire bolt", "ignite", "magma form"})
            elif "water" in monster_name.lower():
                elemental_abilities.update({"water form", "freeze", "water jet"})
            elif "air" in monster_name.lower():
                elemental_abilities.update({"air form", "whirlwind", "lightning strike"})
            elif "earth" in monster_name.lower():
                elemental_abilities.update({"earth form", "stone camouflage", "stone grip"})
            
            canonical_abilities.update(elemental_abilities)
            logger.info(f"Added elemental-specific abilities to {monster_name}")
        
        # Check and clean actions
        if "actions" in monster_data:
            original_actions_count = len(monster_data["actions"]) if isinstance(monster_data["actions"], list) else 0
            monster_data["actions"] = verify_abilities_match_monster(
                monster_name, monster_data.get("actions", []), canonical_abilities)
            new_actions_count = len(monster_data["actions"])
            
            if original_actions_count > new_actions_count:
                logger.warning(f"Removed {original_actions_count - new_actions_count} invalid actions from {monster_name}")
                
                # If we removed all actions, add some basic ones
                if new_actions_count == 0:
                    logger.warning(f"All actions were invalid! Adding generic actions for {monster_name}")
                    monster_data["actions"] = [
                        {
                            "name": "Basic Attack",
                            "description": f"Melee Weapon Attack: +4 to hit, reach 5 ft., one target. Hit: 7 (1d8 + 3) damage."
                        }
                    ]
        
        # Check and clean traits
        if "traits" in monster_data:
            original_traits_count = len(monster_data["traits"]) if isinstance(monster_data["traits"], list) else 0
            monster_data["traits"] = verify_abilities_match_monster(
                monster_name, monster_data.get("traits", []), canonical_abilities)
            new_traits_count = len(monster_data["traits"])
            
            if original_traits_count > new_traits_count:
                logger.warning(f"Removed {original_traits_count - new_traits_count} invalid traits from {monster_name}")
                
                # If we removed all traits, add some basic ones based on monster type
                if new_traits_count == 0 and monster_type:
                    logger.warning(f"All traits were invalid! Adding generic traits for {monster_name}")
                    if "dragon" in monster_type or "dragon" in monster_name.lower():
                        monster_data["traits"] = [
                            {
                                "name": "Draconic Nature",
                                "description": f"The {monster_name} has advantage on saving throws against frightened."
                            }
                        ]
                    elif "undead" in monster_type or "skeleton" in monster_name.lower():
                        monster_data["traits"] = [
                            {
                                "name": "Undead Nature",
                                "description": f"The {monster_name} doesn't require air, food, drink, or sleep."
                            }
                        ]
                    elif "elemental" in monster_type or "mephit" in monster_name.lower():
                        monster_data["traits"] = [
                            {
                                "name": "Elemental Nature",
                                "description": f"The {monster_name} doesn't require air, food, drink, or sleep."
                            }
                        ]
                    else:
                        monster_data["traits"] = [
                            {
                                "name": "Keen Senses",
                                "description": f"The {monster_name} has advantage on Wisdom (Perception) checks."
                            }
                        ]
        
        # Check and clean abilities dictionary
        if "abilities" in monster_data and isinstance(monster_data["abilities"], dict):
            abilities_dict = monster_data["abilities"]
            original_abilities_count = len(abilities_dict)
            cleaned_abilities = {}
            
            for name, ability_data in abilities_dict.items():
                if name.lower() in canonical_abilities:
                    cleaned_abilities[name] = ability_data
                else:
                    logger.warning(f"Removed ability '{name}' that doesn't belong to {monster_name}")
            
            # Update the monster data with cleaned abilities
            monster_data["abilities"] = cleaned_abilities
            
            if original_abilities_count > len(cleaned_abilities):
                logger.warning(f"Removed {original_abilities_count - len(cleaned_abilities)} invalid special abilities from {monster_name}")
        
        return monster_data

    def prepare_combat_data(self, combat_state):
        """
        Prepare combat data by validating all monsters' abilities before combat starts.
        
        Args:
            combat_state: Dictionary with combat state including combatants
            
        Returns:
            Validated combat state
        """
        if not combat_state or not isinstance(combat_state, dict):
            logger.warning("Cannot prepare invalid combat state")
            return combat_state
        
        # Make a deep copy to avoid modifying the original
        import copy
        state_copy = copy.deepcopy(combat_state)
        
        # Get combatants
        combatants = state_copy.get("combatants", [])
        if not combatants:
            return state_copy
        
        # Validate each monster's abilities
        cleaned_count = 0
        for i, combatant in enumerate(combatants):
            if isinstance(combatant, dict) and combatant.get("type", "").lower() == "monster":
                # Validate and clean the monster's abilities
                before_actions = len(combatant.get("actions", []))
                before_traits = len(combatant.get("traits", []))
                
                # Clean the monster abilities
                combatants[i] = self.validate_monster_abilities(combatant)
                
                after_actions = len(combatants[i].get("actions", []))
                after_traits = len(combatants[i].get("traits", []))
                
                if before_actions > after_actions or before_traits > after_traits:
                    cleaned_count += 1
        
        # Log results
        if cleaned_count > 0:
            logger.info(f"Cleaned abilities for {cleaned_count} out of {len(combatants)} combatants")
        
        # Update the combat state with validated combatants
        state_copy["combatants"] = combatants
        return state_copy 

    def _create_decision_prompt(self, combatants, active_idx, round_num):
        """
        Create a decision prompt for a combatant's turn with thorough ability validation.
        
        This wraps the combat resolver's patched _create_decision_prompt with 
        additional validation to ensure no ability mixing occurs.
        
        Args:
            combatants: List of all combatants
            active_idx: Index of active combatant
            round_num: Current round number
            
        Returns:
            Validated prompt string with no ability mixing
        """
        # First, validate the active combatant's abilities
        active_combatant = combatants[active_idx]
        if active_combatant.get("type", "").lower() == "monster":
            combatants[active_idx] = self.validate_monster_abilities(active_combatant)
            
        # Use the patched version from the combat resolver to create the basic prompt
        prompt = self.combat_resolver._create_decision_prompt(combatants, active_idx, round_num)
        
        # Clean the prompt to ensure all abilities have proper tags
        prompt = clean_abilities_in_prompt(prompt)
        
        # Double-check for ability mixing
        is_valid, result = validate_combat_prompt(prompt)
        
        if not is_valid:
            logger.warning(f"Ability mixing detected in improved resolver: {result}")
            # Apply automatic correction
            fixed_prompt = fix_mixed_abilities_in_prompt(prompt)
            
            # Validate the fixed prompt to ensure it worked
            fixed_is_valid, fixed_result = validate_combat_prompt(fixed_prompt)
            
            if fixed_is_valid:
                logger.info("Successfully fixed ability mixing in improved resolver!")
                return fixed_prompt
            else:
                logger.warning(f"Failed to fix ability mixing in improved resolver: {fixed_result}")
                
                # As a last resort, generate a completely new prompt for this monster
                monster_name = active_combatant.get("name", "Unknown")
                logger.info(f"Attempting to generate clean prompt for {monster_name}")
                
                # Create a simplified template
                template = """
You are the tactical combat AI for a D&D 5e game. You decide actions for {{MONSTER_NAME}}.

# COMBAT SITUATION
Round: {round_num}
Active Combatant: {{MONSTER_NAME}}

# {{MONSTER_NAME}} DETAILS
HP: {hp}/{max_hp}
AC: {ac}
Type: monster
Status: {status}

# SPECIFIC ABILITIES, ACTIONS AND TRAITS
## Actions:
{{MONSTER_ACTIONS}}

## Traits:
{{MONSTER_TRAITS}}

# NEARBY COMBATANTS
{nearby}

# YOUR TASK
Decide the most appropriate action for {{MONSTER_NAME}} this turn.
"""
                # Fill in template values
                monster_prompt_template = template.format(
                    round_num=round_num,
                    hp=active_combatant.get("hp", 0),
                    max_hp=active_combatant.get("max_hp", active_combatant.get("hp", 0)),
                    ac=active_combatant.get("ac", 10),
                    status=active_combatant.get("status", "OK"),
                    nearby=self.combat_resolver._format_nearby_combatants(
                        self.combat_resolver._get_nearby_combatants(active_combatant, combatants)
                    )
                )
                
                # Generate a monster-specific prompt
                return generate_monster_specific_prompt(active_combatant, monster_prompt_template)
        
        return prompt 

    @staticmethod
    def validate_monster_data(monster_data):
        """
        Static method to validate monster data before it's even added to combat.
        This prevents ability mixing at the data creation stage.
        
        Args:
            monster_data: Dictionary with monster data
            
        Returns:
            Validated monster data with any invalid abilities removed
        """
        import logging
        logger = logging.getLogger(__name__)
        
        if not monster_data or not isinstance(monster_data, dict):
            logger.warning("Cannot validate invalid monster data")
            return monster_data
        
        # Import validation functions in case this is called from another module
        try:
            from app.core.utils.monster_ability_validator import (
                extract_ability_names,
                get_canonical_abilities,
                verify_abilities_match_monster
            )
        except ImportError:
            logger.error("Cannot import monster ability validator - skipping validation")
            return monster_data
        
        monster_name = monster_data.get("name", "Unknown Monster")
        logger.info(f"Validating data for monster: {monster_name}")
        
        # Extract canonical abilities for this specific monster type
        canonical_abilities = get_canonical_abilities(monster_name, monster_data)
        logger.info(f"Found {len(canonical_abilities)} canonical abilities for {monster_name}")
        
        # Get typical abilities for this monster type from our database or template
        monster_type = monster_data.get("type", "").lower()
        
        # Add type-specific canonical abilities if needed
        if monster_type == "dragon" or "dragon" in monster_name.lower():
            dragon_abilities = {"breath weapon", "frightful presence", "multiattack", "bite", "claw", "tail"}
            canonical_abilities.update(dragon_abilities)
            logger.info(f"Added dragon-specific abilities to {monster_name}")
        elif monster_type == "undead" or "skeleton" in monster_name.lower() or "zombie" in monster_name.lower():
            undead_abilities = {"undead fortitude", "undead nature", "multiattack", "claw", "bone attack"}
            canonical_abilities.update(undead_abilities)
            logger.info(f"Added undead-specific abilities to {monster_name}")
        elif "elemental" in monster_type or "elemental" in monster_name.lower() or "mephit" in monster_name.lower():
            elemental_abilities = {"elemental nature", "innate spellcasting", "multiattack", "slam", "touch"}
            # Add element-specific abilities based on name
            if "fire" in monster_name.lower() or "magma" in monster_name.lower() or "flame" in monster_name.lower():
                elemental_abilities.update({"fire form", "heated body", "fire breath", "fire bolt", "ignite", "magma form"})
            elif "water" in monster_name.lower():
                elemental_abilities.update({"water form", "freeze", "water jet"})
            elif "air" in monster_name.lower():
                elemental_abilities.update({"air form", "whirlwind", "lightning strike"})
            elif "earth" in monster_name.lower():
                elemental_abilities.update({"earth form", "stone camouflage", "stone grip"})
            
            canonical_abilities.update(elemental_abilities)
            logger.info(f"Added elemental-specific abilities to {monster_name}")
        
        # Check and clean actions
        if "actions" in monster_data:
            original_actions_count = len(monster_data["actions"]) if isinstance(monster_data["actions"], list) else 0
            monster_data["actions"] = verify_abilities_match_monster(
                monster_name, monster_data.get("actions", []), canonical_abilities)
            new_actions_count = len(monster_data["actions"])
            
            if original_actions_count > new_actions_count:
                logger.warning(f"Removed {original_actions_count - new_actions_count} invalid actions from {monster_name}")
                
                # If we removed all actions, add some basic ones
                if new_actions_count == 0:
                    logger.warning(f"All actions were invalid! Adding generic actions for {monster_name}")
                    monster_data["actions"] = [
                        {
                            "name": "Basic Attack",
                            "description": f"Melee Weapon Attack: +4 to hit, reach 5 ft., one target. Hit: 7 (1d8 + 3) damage."
                        }
                    ]
        
        # Check and clean traits
        if "traits" in monster_data:
            original_traits_count = len(monster_data["traits"]) if isinstance(monster_data["traits"], list) else 0
            monster_data["traits"] = verify_abilities_match_monster(
                monster_name, monster_data.get("traits", []), canonical_abilities)
            new_traits_count = len(monster_data["traits"])
            
            if original_traits_count > new_traits_count:
                logger.warning(f"Removed {original_traits_count - new_traits_count} invalid traits from {monster_name}")
                
                # If we removed all traits, add some basic ones based on monster type
                if new_traits_count == 0 and monster_type:
                    logger.warning(f"All traits were invalid! Adding generic traits for {monster_name}")
                    if "dragon" in monster_type or "dragon" in monster_name.lower():
                        monster_data["traits"] = [
                            {
                                "name": "Draconic Nature",
                                "description": f"The {monster_name} has advantage on saving throws against frightened."
                            }
                        ]
                    elif "undead" in monster_type or "skeleton" in monster_name.lower():
                        monster_data["traits"] = [
                            {
                                "name": "Undead Nature",
                                "description": f"The {monster_name} doesn't require air, food, drink, or sleep."
                            }
                        ]
                    elif "elemental" in monster_type or "mephit" in monster_name.lower():
                        monster_data["traits"] = [
                            {
                                "name": "Elemental Nature",
                                "description": f"The {monster_name} doesn't require air, food, drink, or sleep."
                            }
                        ]
                    else:
                        monster_data["traits"] = [
                            {
                                "name": "Keen Senses",
                                "description": f"The {monster_name} has advantage on Wisdom (Perception) checks."
                            }
                        ]
        
        # Check and clean abilities dictionary
        if "abilities" in monster_data and isinstance(monster_data["abilities"], dict):
            abilities_dict = monster_data["abilities"]
            original_abilities_count = len(abilities_dict)
            cleaned_abilities = {}
            
            for name, ability_data in abilities_dict.items():
                if name.lower() in canonical_abilities:
                    cleaned_abilities[name] = ability_data
                else:
                    logger.warning(f"Removed ability '{name}' that doesn't belong to {monster_name}")
            
            # Update the monster data with cleaned abilities
            monster_data["abilities"] = cleaned_abilities
            
            if original_abilities_count > len(cleaned_abilities):
                logger.warning(f"Removed {original_abilities_count - len(cleaned_abilities)} invalid special abilities from {monster_name}")
        
        return monster_data 