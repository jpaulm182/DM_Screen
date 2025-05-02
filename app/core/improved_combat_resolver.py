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
        
        # Forward the base resolver's resolution_update (result, status, error) to our resolution_complete (result, error)
        self.combat_resolver.resolution_update.connect(
            lambda state, status, error: self.resolution_complete.emit(state, error)
        )
        
    def reset_resolution(self):
        """
        Stop any current resolution and reset the state.
        Delegates to the inner combat_resolver's reset_resolution method.
        """
        import logging
        logging.info("[ImprovedCombatResolver] Delegating reset_resolution to inner resolver")
        return self.combat_resolver.reset_resolution()

    def is_running(self):
        """Check if the resolver is currently processing."""
        return self.combat_resolver.is_running()

    def is_paused(self):
        """Check if the resolver is paused in step mode."""
        return self.combat_resolver.is_paused()

    def continue_turn(self):
        """Signal to continue to the next turn when in step mode."""
        return self.combat_resolver.continue_turn()

    def stop_resolution(self):
        """Stop the resolution process."""
        return self.combat_resolver.stop_resolution()

    def start_resolution(self, combat_state, dice_roller, update_ui_callback, mode='continuous'):
        """
        Start the combat resolution process.
        Delegates to the inner combat_resolver's start_resolution method.
        """
        return self.combat_resolver.start_resolution(
            combat_state, 
            dice_roller, 
            update_ui_callback, 
            mode
        )

    def resolve_combat_turn_by_turn(self, combat_state, dice_roller, callback=None, update_ui_callback=None):
        """
        Start continuous combat resolution using the original CombatResolver.
        Passes per-turn UI updates to the provided callback.
        """
        # Use start_resolution to leverage LLM per-turn updates
        return self.combat_resolver.start_resolution(
            combat_state,
            dice_roller,
            update_ui_callback,
            mode='continuous'
        )

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

        # --- ENHANCED MONSTER AI INSTRUCTIONS ---
        low_hp_behavior = """
--- MONSTER LOW HP BEHAVIOR ---
If you are a monster and your HP is low (below 25% of max HP), you must either:
- Make a final aggressive attack,
- Attempt to flee (describe escape attempt and remove yourself from combat if successful),
- Or surrender (describe surrender and remove yourself from combat if accepted).
Do NOT endlessly defend or take only defensive actions. Do NOT stall combat.
"""
        prompt += low_hp_behavior

        legendary_action_instructions = """
--- LEGENDARY ACTIONS ---
If you are a legendary creature (such as a dragon), you MUST use your legendary actions at the end of other creatures' turns, as per D&D 5e rules. Always list and describe the legendary actions you use in your response. Do not skip legendary actions if you have any left.
"""
        prompt += legendary_action_instructions

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