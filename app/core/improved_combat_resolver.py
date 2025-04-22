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

# Import QObject and Signal for thread-safe communication
from PySide6.QtCore import QObject, Signal

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
                # First, enhance the combat state with improved initiative handling
                enhanced_state = initialize_combat_with_improved_initiative(combat_state)
                
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
        combatants = state.get("combatants", [])
        combatant = combatants[combatant_idx]
        
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
        
        # Reset legendary actions for legendary creatures at the start of their turn
        if combatant.get("legendary_actions", 0) > 0:
            combatant = ActionEconomyManager.initialize_action_economy(combatant)
        
        # Use the original turn processor but with additional context
        # Create a temporary state to pass to the original processor
        temp_state = {
            "round": round_num,
            "current_turn_index": combatant_idx,
            "combatants": combatants
        }
        
        # Process the turn with the original combat resolver's _process_turn method
        turn_result = self.combat_resolver._process_turn(combatants, combatant_idx, round_num, dice_roller)
        
        if not turn_result:
            # Error or timeout processing turn - create a basic result to continue
            print(f"[ImprovedCombatResolver] Error processing turn for {combatant.get('name', 'Unknown')} - using fallback")
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