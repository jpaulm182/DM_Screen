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
import random
import time
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
            update_ui_callback: Function to update the UI
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
            time.sleep(0.5)
    
    
            import copy
            combat_display_state = {
                "round": round_num,
                "current_turn_index": combatant_idx,
                "combatants": copy.deepcopy(combatants),
                "latest_action": turn_log_entry
            }
            update_ui_callback(combat_display_state)
            time.sleep(0.5)
    
    def _process_saving_throws(self, state, target_names, save_ability, save_dc, damage, half_on_save, dice_roller):
        """
        Process saving throws for one or more targets.
        
        Args:
            state: Current combat state
            target_names: List of target names that need to make saving throws
            save_ability: The ability used for the save (str, dex, con, int, wis, cha)
            save_dc: The DC for the saving throw
            damage: The damage to apply (modified by saving throw result)
            half_on_save: Whether a successful save halves damage (True) or negates it (False)
            dice_roller: Function to roll dice
            
        Returns:
            Dictionary with updates, narrative, and dice rolls
        """
        from app.combat.condition_resolver import ConditionResolver
        
        combatants = state.get("combatants", [])
        updates = []
        narrative = ""
        dice_rolls = []
        
        # If no specific targets are provided but we have a target field, use that instead
        if not target_names:
            logger.warning("No target names provided for saving throws, checking for single target")
            target_name = state.get("target", None)
            if target_name:
                target_names = [target_name]

        # If target_names is empty but we have living enemies, target them
        if not target_names:
            logger.warning("No target names provided, targeting all living enemies")
            # Get all living enemies
            for combatant in combatants:
                # Skip dead or allied creatures
                if (combatant.get("hp", 0) <= 0 or 
                    combatant.get("status", "").lower() == "dead"):
                    continue
                
                target_names.append(combatant.get("name", ""))
        
        logger.info(f"Processing saving throws for targets: {target_names}")
        
        for target_name in target_names:
            # Find the target
            target = None
            for c in combatants:
                if c.get("name", "") == target_name:
                    target = c
                    break
                    
            if not target:
                logger.warning(f"Target {target_name} not found")
                continue
            
            # Skip dead targets
            if target.get("hp", 0) <= 0 or target.get("status", "").lower() == "dead":
                logger.info(f"Skipping dead target: {target_name}")
                continue
                
            # Get save bonus for the ability
            save_bonus = target.get("saves", {}).get(save_ability, 0)
            
            # Check for advantage/disadvantage/auto-fail based on conditions
            has_advantage, has_disadvantage, auto_fail = ConditionResolver.check_saving_throw_modifiers(
                target, save_ability
            )
            
            # Roll the saving throw
            if auto_fail:
                save_succeeded = False
                roll1 = 1  # Auto-fail represented as a 1
                total = 1
                roll_description = f"{target_name} automatically fails the {save_ability} save due to conditions!"
            else:
                # Roll with advantage/disadvantage
                roll1 = dice_roller("1d20")
                roll_description = f"{target_name} rolls a {save_ability} save: {roll1}"
                
                if has_advantage or has_disadvantage:
                    roll2 = dice_roller("1d20")
                    if has_advantage:
                        roll_to_use = max(roll1, roll2)
                        roll_description += f" with advantage (rolls: {roll1}, {roll2}, using {roll_to_use})"
                    else:  # disadvantage
                        roll_to_use = min(roll1, roll2)
                        roll_description += f" with disadvantage (rolls: {roll1}, {roll2}, using {roll_to_use})"
                else:
                    roll_to_use = roll1
                
                total = roll_to_use + save_bonus
                save_succeeded = total >= save_dc
            
            # Record the dice roll
            dice_rolls.append({
                "expression": "1d20",
                "result": roll1,
                "purpose": f"{target_name}'s {save_ability} save (DC {save_dc})"
            })
            
            # Calculate damage based on save result
            applied_damage = 0
            if not save_succeeded:
                # Failed save - full damage
                applied_damage = damage
                narrative += f"{roll_description} → Total: {total} vs DC {save_dc}: Failed! Takes {damage} damage.\n"
            else:
                # Successful save
                if half_on_save:
                    applied_damage = damage // 2
                    narrative += f"{roll_description} → Total: {total} vs DC {save_dc}: Success! Takes {applied_damage} damage (half).\n"
                else:
                    applied_damage = 0
                    narrative += f"{roll_description} → Total: {total} vs DC {save_dc}: Success! Takes no damage.\n"
            
            # Apply damage
            current_hp = target.get("hp", 0)
            new_hp = max(0, current_hp - applied_damage)
            
            # Check if the target is defeated
            status = target.get("status", "")
            if new_hp == 0 and status != "dead":
                status = "unconscious" if target.get("type", "").lower() != "monster" else "dead"
            
            # Create an update
            update = {
                "name": target_name,
                "hp": new_hp
            }
            
            if new_hp == 0:
                update["status"] = status
                
            updates.append(update)
            
        return {
            "updates": updates,
            "narrative": narrative.strip(),
            "dice": dice_rolls
        }
    
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
        
        # Initialize spell slot tracking for monsters by parsing their Spellcasting trait
        for combatant in state_copy["combatants"]:
            if isinstance(combatant, dict) and combatant.get("type", "").lower() == "monster":
                for trait in combatant.get("traits", []):
                    if isinstance(trait, dict) and trait.get("name", "").lower() == "spellcasting":
                        desc = trait.get("description", "")
                        # Extract patterns like '1st level (4 slots)'
                        slots_found = re.findall(r"(\d+)(?:st|nd|rd|th)[ -]level\s*\((\d+)\s*slots?\)", desc, flags=re.IGNORECASE)
                        if slots_found:
                            slot_dict = {int(lvl): int(cnt) for lvl, cnt in slots_found}
                            combatant["spell_slots_max"] = slot_dict.copy()
                            combatant["spell_slots"] = slot_dict.copy()
                        break

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
                prompt = fixed_prompt
            else:
                # If fixing failed, just use the original
                logger.error(f"Failed to fix ability mixing: {fixed_result}")
        
        # Add instructions for handling saving throws in area effect attacks
        # Make these instructions much clearer and more insistent
        saving_throw_instructions = """
--- AREA OF EFFECT (AoE) ABILITY INSTRUCTIONS ---

**MANDATORY FORMAT FOR AoE ABILITIES (e.g., Breath Weapons, Fireball):**

If you choose an AoE ability that requires saving throws, your JSON response **MUST** include these specific top-level fields:

1.  `"area_effect": true` (Exactly this key and value)
2.  `"save_dc": [DC Number]` (e.g., `"save_dc": 15`)
3.  `"save_ability": "[Full Ability Name]"` (e.g., `"save_ability": "dexterity"`) - Use lowercase full name.
4.  `"damage_expr": "[Dice Expression]"` (e.g., `"damage_expr": "8d6"`) - Just the dice, NO bonuses here.
5.  `"half_on_save": true` OR `"half_on_save": false` (Indicates if a successful save takes half damage or no damage)
6.  `"affected_targets": ["[Target Name 1]", "[Target Name 2]", ...]` (List all creatures in the area who must save)

**DO NOT** put the save DC or damage expression inside the `dice_requests` list for AoE attacks. The system handles rolling saves and damage automatically based on the fields above.

**EXAMPLE FOR GLACIAL BREATH (targeting Lich and Dragon):**

```json
{
  "action": "Glacial Breath",
  "target": null, // Target field is not used for AoE, use affected_targets instead
  "reasoning": "Using Glacial Breath on the clustered Lich and Dragon to maximize damage.",
  "area_effect": true,
  "save_dc": 23,
  "save_ability": "constitution",
  "damage_expr": "16d10", // Just the dice expression for damage
  "half_on_save": true,
  "affected_targets": ["Lich of a Mad Mage", "Adult Red Dragon"],
  "dice_requests": [] // No dice requests needed here, system handles AoE rolls
}
```

--- SINGLE-TARGET ATTACKS/ABILITIES ---

*   For **regular attacks** (like Multiattack, Slam), provide the `"target"` and include attack/damage rolls in `"dice_requests"` as usual.
*   For **single-target abilities requiring a save** (e.g., Ray of Sickness), provide the `"target"`, `"save_dc"`, `"save_ability"`, `"half_on_save"`, and any effect dice in `"dice_requests"`.

The system will handle the mechanics based on the structure you provide. **Follow the AoE structure strictly when applicable.**
"""
        
        # Add the saving throw instructions to the prompt
        prompt += saving_throw_instructions
        
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
        
        # FIXED: Improved handling to prevent ability mixing between monsters
        # Make a deep copy of monster data to avoid modifying the original
        import copy
        monster_data_copy = copy.deepcopy(monster_data)
        
        # Store original monster name for consistency
        monster_name = monster_data_copy.get("name", "Unknown Monster")
        monster_type = monster_data_copy.get("type", "").lower()
        logger.info(f"Validating data for {monster_type} monster: {monster_name}")
        
        # Tag each monster ability with the monster's ID to ensure no mixing
        monster_id = monster_data_copy.get("id", None)
        if not monster_id:
            # Generate a unique ID based on name and timestamp if none exists
            import time
            import hashlib
            timestamp = int(time.time())
            hash_base = f"{monster_name}_{timestamp}"
            monster_id = hashlib.md5(hash_base.encode()).hexdigest()[:8]
            monster_data_copy["id"] = monster_id
            logger.info(f"Generated unique ID {monster_id} for monster {monster_name}")

        try:
            # Import validation functions in case this is called from another module
            try:
                # This import might fail if the module is not available
                from app.core.utils.monster_ability_validator import (
                    extract_ability_names,
                    get_canonical_abilities,
                    verify_abilities_match_monster
                )
            except ImportError:
                logger.error("Cannot import monster ability validator - skipping validation")
                return monster_data_copy
            
            # Extract canonical abilities for this specific monster type
            canonical_abilities = get_canonical_abilities(monster_name, monster_data_copy)
            logger.info(f"Found {len(canonical_abilities)} canonical abilities for {monster_name}")
            
            # Validate each part of the monster data that contains abilities
            
            # Check and clean actions
            if "actions" in monster_data_copy:
                if not isinstance(monster_data_copy["actions"], list):
                    # Convert to list if not already
                    logger.warning(f"Actions for {monster_name} is not a list, converting")
                    if isinstance(monster_data_copy["actions"], dict):
                        actions_list = []
                        for name, desc in monster_data_copy["actions"].items():
                            actions_list.append({"name": name, "description": str(desc)})
                        monster_data_copy["actions"] = actions_list
                    else:
                        monster_data_copy["actions"] = []
                
                # Now validate
                if isinstance(monster_data_copy["actions"], list):
                    original_actions_count = len(monster_data_copy["actions"])
                    
                    # Tag each action with the monster_id before validation
                    for action in monster_data_copy["actions"]:
                        if isinstance(action, dict) and "name" in action:
                            action["monster_id"] = monster_id
                    
                    # Now validate
                    monster_data_copy["actions"] = verify_abilities_match_monster(
                        monster_name, monster_data_copy["actions"], canonical_abilities)
                    new_actions_count = len(monster_data_copy["actions"])
                    
                    if original_actions_count > new_actions_count:
                        logger.warning(f"Removed {original_actions_count - new_actions_count} invalid actions from {monster_name}")
                    
                    # If we removed all actions, add some basic ones
                    if new_actions_count == 0 and original_actions_count > 0:
                        logger.warning(f"All actions were removed! Adding generic actions for {monster_name}")
                        monster_data_copy["actions"] = [
                            {
                                "name": f"{monster_name} Basic Attack",
                                "description": f"Melee Weapon Attack: +4 to hit, reach 5 ft., one target. Hit: 7 (1d8 + 3) damage.",
                                "monster_id": monster_id
                            }
                        ]
            
            # Check and clean traits
            if "traits" in monster_data_copy:
                if not isinstance(monster_data_copy["traits"], list):
                    # Convert to list if not already
                    logger.warning(f"Traits for {monster_name} is not a list, converting")
                    if isinstance(monster_data_copy["traits"], dict):
                        traits_list = []
                        for name, desc in monster_data_copy["traits"].items():
                            traits_list.append({"name": name, "description": str(desc)})
                        monster_data_copy["traits"] = traits_list
                    else:
                        monster_data_copy["traits"] = []
                
                # Now validate
                if isinstance(monster_data_copy["traits"], list):
                    original_traits_count = len(monster_data_copy["traits"])
                    
                    # Tag each trait with the monster_id before validation
                    for trait in monster_data_copy["traits"]:
                        if isinstance(trait, dict) and "name" in trait:
                            trait["monster_id"] = monster_id
                    
                    # Now validate
                    monster_data_copy["traits"] = verify_abilities_match_monster(
                        monster_name, monster_data_copy["traits"], canonical_abilities)
                    new_traits_count = len(monster_data_copy["traits"])
                    
                    if original_traits_count > new_traits_count:
                        logger.warning(f"Removed {original_traits_count - new_traits_count} invalid traits from {monster_name}")
                    
                    # If we removed all traits but had some originally, add generic ones
                    if new_traits_count == 0 and original_traits_count > 0:
                        logger.warning(f"All traits were removed! Adding generic traits for {monster_name}")
                        monster_data_copy["traits"] = [
                            {
                                "name": f"{monster_name} Trait",
                                "description": f"This {monster_type or 'creature'} has natural abilities suited to its environment.",
                                "monster_id": monster_id
                            }
                        ]
            
            # Check and clean abilities dictionary
            if "abilities" in monster_data_copy and isinstance(monster_data_copy["abilities"], dict):
                abilities_dict = monster_data_copy["abilities"]
                original_abilities_count = len(abilities_dict)
                cleaned_abilities = {}
                
                for name, ability_data in abilities_dict.items():
                    # Add monster_id to each ability
                    if isinstance(ability_data, dict):
                        ability_data["monster_id"] = monster_id
                    
                    # Only include abilities that belong to this monster or are generic
                    if name.lower() in canonical_abilities:
                        cleaned_abilities[name] = ability_data
                
                # Update the monster data with cleaned abilities
                monster_data_copy["abilities"] = cleaned_abilities
                
                if original_abilities_count > len(cleaned_abilities) and original_abilities_count > 0:
                    logger.warning(f"Removed {original_abilities_count - len(cleaned_abilities)} invalid special abilities from {monster_name}")
                    
                    # If all abilities were removed but we had some, add back the original ones
                    if len(cleaned_abilities) == 0:
                        logger.warning(f"All abilities were removed! Keeping original abilities for {monster_name}")
                        monster_data_copy["abilities"] = abilities_dict
            
            # Stamp monster name and ID on the monster data for future validation
            monster_data_copy["_validation_id"] = monster_id
            monster_data_copy["_validation_name"] = monster_name
            
            return monster_data_copy
            
        except Exception as e:
            logger.error(f"Error during monster data validation: {e}")
            # In case of any error, return the original data (safety mechanism)
            return monster_data 

    def _process_turn_with_improved_initiative(self, state, active_idx, round_num, dice_roller, log, update_ui_callback=None):
        """
        Process a single turn with improved initiative handling.
        
        Args:
            state: Current combat state
            active_idx: Index of the active combatant
            round_num: Current round number
            dice_roller: Function to roll dice
            log: Combat log to append to
            update_ui_callback: Function to update the UI
        """
        import logging
        
        # Extract necessary components
        combatants = state.get("combatants", [])
        active_combatant = combatants[active_idx]
        action_name = active_combatant.get("action", "")
        targets = active_combatant.get("targets", [])
        dice_requests = active_combatant.get("dice_requests", [])
        updates = []
        
        # Log turn processing
        logging.info(f"[TurnProc] Processing turn for {active_combatant['name']} in round {round_num}")
        
        # Process turn based on action type
        if action_name.lower() == "area_effect":
            # Process AoE action
            logging.debug(f"[TurnProc] Handling AoE action: {action_name}. Targets from LLM: {targets}") # Log targets received
            updates = self._process_saving_throws(state, targets, active_combatant.get("save_ability", ""), active_combatant.get("save_dc", 10), active_combatant.get("damage", 0), active_combatant.get("half_on_save", True), dice_roller)
        else:
            # Process single-target attack or ability
            logging.debug(f"[TurnProc] Handling non-AoE action: {action_name}. Targets from LLM: {targets}") # Log targets received
            target = None
            target_name = None

            if targets and isinstance(targets, list) and len(targets) > 0:
                target_name = targets[0] # Assuming single target for non-AoE for now
                logging.debug(f"[TurnProc] Trying to find target (list): '{target_name}'")
                target = next((c for c in self.combat_state.combatants if c.name == target_name and c.current_hp > 0), None)
                
                if target:
                    logging.info(f"[TurnProc] Found target '{target.name}' (ID: {target.id}). Preparing to call _process_attack_or_ability.") # Log before call
                    attack_update = self._process_attack_or_ability(combatant, target, action_name, dice_requests)
                    logging.debug(f"[TurnProc] Result from _process_attack_or_ability: {attack_update}") # Log after call
                    if attack_update:
                        updates.append(attack_update)
                else:
                    logging.warning(f"[TurnProc] Target '{target_name}' from list not found or is defeated.")
                    updates.append({"type": "log", "message": f"{combatant.name} tries to target {target_name} with {action_name}, but they cannot be found or are already defeated."})
            elif targets: # Handle single target string
                target_name = targets

        # Update the combat state with processed turn results
        state["updates"] = updates
        state["round"] = round_num + 1
        
        # Update the UI
        if update_ui_callback:
            update_ui_callback(state)
        
        # Log turn processing
        logging.info(f"[TurnProc] Turn processed successfully. Updates: {updates}")

    def _process_attack_or_ability(self, attacker, target, action_name, dice_requests):
        """
        Process an attack or ability against a specific target.
        
        Args:
            attacker (Combatant): The combatant performing the attack/ability
            target (Combatant): The target of the attack/ability
            action_name (str): The name of the action being performed
            dice_requests (list): Dice roll requests for the attack
            
        Returns:
            dict: An update entry for the frontend, or None if no update needed
        """
        logging.debug(f"[AttackProc] Entered _process_attack_or_ability.") # Log entry
        logging.debug(f"[AttackProc] Attacker: {attacker.name}, Target: {target.name}, Action: {action_name}, Dice Requests: {dice_requests}") # Log inputs

        # Find the action in the attacker's action list
        action = None
        # Use lower() for case-insensitive matching
        for a in attacker.actions:
            if a.get("name", "").lower() == action_name.lower(): 
                action = a
                break

        if not action:
            logging.warning(f"[AttackProc] Action '{action_name}' not found for {attacker.name}")
            return {"type": "log", "message": f"{attacker.name} attempts to use {action_name} but doesn't know this ability."}

        # Check if this is a healing action
        is_healing = False
        for dice_req in dice_requests:
            purpose = dice_req.get("purpose", "").lower()
            if "heal" in purpose or "healing" in purpose:
                is_healing = True
                break

        # Process healing
        if is_healing:
            healing = 0
            # Extract healing amount from dice requests
            for dice_req in dice_requests:
                purpose = dice_req.get("purpose", "").lower()
                if "heal" in purpose or "healing" in purpose:
                    # Extract dice expression
                    dice_expr = dice_req.get("expression", "0")
                    # Use the combat resolver's dice roller
                    healing += self.combat_resolver._roll_dice(dice_expr) 

            if healing > 0:
                # Apply healing to target
                old_hp = target.current_hp
                target.current_hp = min(target.current_hp + healing, target.max_hp)

                # Create update message
                update = {
                    "type": "log",
                    "message": f"{attacker.name} heals {target.name} for {healing} HP. "
                               f"HP: {old_hp} → {target.current_hp}/{target.max_hp}"
                }
                logging.debug(f"[AttackProc] Healing processed. Update: {update}") # Log return
                return update
            else:
                update = {"type": "log", "message": f"{attacker.name} attempts to heal {target.name} but fails."}
                logging.debug(f"[AttackProc] Healing failed. Update: {update}") # Log return
                return update

        # Process attack
        else:
            # Check if this action has a to_hit or attack_bonus
            attack_bonus = action.get("attack_bonus", 0)
            # Fallback check for older format
            if not attack_bonus and "to_hit" in action: 
                attack_bonus = action["to_hit"]

            # If it's an attack that requires a roll
            # Ensure attack_bonus is treated as numeric
            if isinstance(attack_bonus, (int, float)) and attack_bonus != 0: 
                # Roll to hit (using random for now, could use dice_roller)
                attack_roll = random.randint(1, 20) 
                total_attack = attack_roll + attack_bonus

                # Determine if hit or miss
                # Ensure AC defaults reasonably if not present
                ac = target.ac if hasattr(target, "ac") else 10 
                hit = (attack_roll == 20) or (total_attack >= ac)

                # Process hit or miss
                if hit:
                    damage = 0
                    damage_type = "damage" # Default damage type

                    # Look for damage in dice requests
                    for dice_req in dice_requests:
                        purpose = dice_req.get("purpose", "").lower()
                        if "damage" in purpose:
                            dice_expr = dice_req.get("expression", "0")
                            # Use the combat resolver's dice roller
                            damage += self.combat_resolver._roll_dice(dice_expr) 

                            # Try to determine damage type from purpose
                            for d_type in ["acid", "cold", "fire", "force", "lightning", "necrotic",
                                          "poison", "psychic", "radiant", "thunder", "bludgeoning",
                                          "piercing", "slashing"]:
                                if d_type in purpose:
                                    damage_type = d_type
                                    break

                    # If no explicit damage in dice requests but action has damage_dice
                    if damage == 0 and "damage_dice" in action:
                        damage_dice = action["damage_dice"]
                        # Use the combat resolver's dice roller
                        damage += self.combat_resolver._roll_dice(damage_dice) 
                        if "damage_type" in action:
                            damage_type = action["damage_type"]

                    # Apply damage
                    if damage > 0:
                        old_hp = target.current_hp
                        target.current_hp = max(0, target.current_hp - damage)

                        # Create hit message
                        crit_text = " (CRITICAL HIT!)" if attack_roll == 20 else ""
                        message = (f"{attacker.name} hits {target.name} with {action_name}{crit_text} "
                                  f"for {damage} {damage_type} damage. "
                                  f"HP: {old_hp} → {target.current_hp}/{target.max_hp}")

                        # Check if target died
                        if target.current_hp <= 0:
                            message += f" {target.name} is defeated!"
                            # Optionally set status here if needed
                            target.status = "Dead" # Or "Unconscious" based on rules

                        update = {"type": "log", "message": message}
                        logging.debug(f"[AttackProc] Attack hit. Update: {update}") # Log return
                        return update
                    else:
                        update = {"type": "log", "message": f"{attacker.name} hits {target.name} with {action_name} but deals no damage."}
                        logging.debug(f"[AttackProc] Attack hit (no damage). Update: {update}") # Log return
                        return update
                else:
                    update = {"type": "log", "message": f"{attacker.name} misses {target.name} with {action_name}. (Rolled {total_attack} vs AC {ac})"}
                    logging.debug(f"[AttackProc] Attack missed. Update: {update}") # Log return
                    return update

            # For non-attack abilities (no attack roll needed, or handled differently)
            else:
                damage = 0

                # Look for damage in dice requests (e.g., Magic Missile)
                for dice_req in dice_requests:
                    purpose = dice_req.get("purpose", "").lower()
                    if "damage" in purpose:
                        dice_expr = dice_req.get("expression", "0")
                        # Use the combat resolver's dice roller
                        damage += self.combat_resolver._roll_dice(dice_expr) 

                # Apply damage if any
                if damage > 0:
                    old_hp = target.current_hp
                    target.current_hp = max(0, target.current_hp - damage)

                    message = (f"{attacker.name} uses {action_name} on {target.name} for {damage} damage. "
                              f"HP: {old_hp} → {target.current_hp}/{target.max_hp}")

                    # Check if target died
                    if target.current_hp <= 0:
                        message += f" {target.name} is defeated!"
                        target.status = "Dead" # Or "Unconscious"

                    update = {"type": "log", "message": message}
                    logging.debug(f"[AttackProc] Non-attack ability damage. Update: {update}") # Log return
                    return update

                # Just a narrative ability with no mechanical effect processed here
                update = {"type": "log", "message": f"{attacker.name} uses {action_name} on {target.name}."}
                logging.debug(f"[AttackProc] Narrative ability. Update: {update}") # Log return
                return update

        logging.debug("[AttackProc] Reached end of method, returning None.") # Log fallback return
        return None