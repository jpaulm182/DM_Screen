"""
Improved Combat Resolver with enhanced D&D 5e initiative mechanics.

This module integrates the ImprovedInitiative system with the original CombatResolver
to create a more realistic and rule-compliant combat experience in D&D 5e.
It now uses a hybrid approach with LLM for strategic decisions and a rules engine
for mechanical execution.
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
# Import our new modules
try:
    print("[DEBUG] Attempting to import rules_engine")
    from app.core.rules_engine import RulesEngine, ActionResult
    print("[DEBUG] Successfully imported rules_engine")
    
    print("[DEBUG] Attempting to import structured_output")
    from app.core.structured_output import StructuredOutputHandler
    print("[DEBUG] Successfully imported structured_output")
except ImportError as e:
    print(f"[DEBUG] ERROR importing modules: {e}")
    import sys
    print(f"[DEBUG] Python path: {sys.path}")
    import traceback
    print(traceback.format_exc())

import copy
import logging
import re
import random
import time
from typing import Dict, List, Any, Optional, Tuple

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
        
        # Initialize our new components
        self.structured_output_handler = StructuredOutputHandler()
        self.rules_engine = None  # Will be initialized when dice_roller is available
        
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
        
    def resolve_combat_turn_by_turn(self, combat_state, dice_roller, callback=None, update_ui_callback=None):
        """
        Start continuous combat resolution using the original CombatResolver.
        Passes per-turn UI updates to the provided callback.
        """
        # Initialize the rules engine with the dice_roller if not already initialized
        if not self.rules_engine:
            self.rules_engine = RulesEngine(dice_roller)
            
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
            active_idx: Index of the active combatant
            round_num: Current round number
            
        Returns:
            Validated prompt string with no ability mixing
        """
        if not hasattr(self.combat_resolver, '_create_decision_prompt'):
            logger.error("Combat resolver doesn't have _create_decision_prompt method - was it patched correctly?")
            return ""
        
        # Start timing the prompt creation
        start_time = time.time()
        
        # First, get the original prompt
        original_prompt = self.combat_resolver._create_decision_prompt(combatants, active_idx, round_num)
        
        # Check if we need to enhance the prompt with function calling instructions
        # Add structured output instructions and examples
        function_definition = self.structured_output_handler.create_function_calling_definition()
        examples = self.structured_output_handler.create_few_shot_examples()
        
        # Add instructions for structured output
        enhanced_prompt = original_prompt + "\n\n"
        enhanced_prompt += "You MUST respond with a structured JSON object containing your action decision.\n"
        enhanced_prompt += "Ensure your response contains these required fields:\n"
        enhanced_prompt += "- 'action': What you're doing (e.g., 'Attack with longsword', 'Cast Fireball')\n"
        enhanced_prompt += "- 'target': Who/what you're targeting (if applicable)\n"
        enhanced_prompt += "- 'explanation': Brief tactical reasoning\n\n"
        
        # Add example for clarity
        enhanced_prompt += "Example response format:\n"
        enhanced_prompt += """```json
{
  "action": "Attack with Greataxe",
  "target": "Goblin Archer",
  "explanation": "The goblin is closest and looks injured."
}
```"""
        
        # Validate the prompt for ability mixing
        validated_prompt = validate_combat_prompt(enhanced_prompt)
        
        # Check for any mixed abilities in the prompt
        if validated_prompt != enhanced_prompt:
            logger.info("Fixed mixed abilities in prompt")
        
        # Clean any remaining inconsistencies
        cleaned_prompt = clean_abilities_in_prompt(validated_prompt)
        final_prompt = fix_mixed_abilities_in_prompt(cleaned_prompt)
        
        # Log timing for monitoring performance
        end_time = time.time()
        logger.debug(f"Decision prompt creation took {end_time - start_time:.2f} seconds")
        
        return final_prompt
        
    def process_llm_response(self, response_text: str, active_combatant: Dict[str, Any], 
                             all_combatants: List[Dict[str, Any]]) -> Tuple[Dict[str, Any], bool]:
        """
        Process LLM response using the hybrid approach:
        1. Parse LLM response to extract action intent
        2. Pass intent to rules engine for mechanical execution
        
        Args:
            response_text: Raw response from the LLM
            active_combatant: The combatant taking the action
            all_combatants: All combatants in the encounter
            
        Returns:
            Tuple containing:
            - Action result as a dictionary
            - Success flag (bool)
        """
        # Step 1: Parse the LLM response to extract structured data
        json_data, success, error_msg = self.structured_output_handler.parse_llm_json_response(
            response_text, f"Turn for {active_combatant.get('name', 'Unknown')}"
        )
        
        # Step 2: Validate the parsed data against our schema
        valid, validation_error, action_schema = self.structured_output_handler.validate_action(json_data)
        
        # If parsing or validation failed, implement fallback logic (Tier 1)
        if not success or not valid:
            logger.warning(f"Failed to parse LLM response: {error_msg or validation_error}")
            # Try to extract simple action/target
            basic_action = self._extract_basic_action(response_text, active_combatant)
            if basic_action:
                json_data = basic_action
            else:
                # If still failing, use a very simple fallback action (Tier 3)
                json_data = self._generate_fallback_action(active_combatant, all_combatants)
        
        # Step 3: Execute the action using the rules engine
        if self.rules_engine:
            result = self.rules_engine.execute_action(json_data, active_combatant, all_combatants)
            return self._format_action_result(result, json_data, active_combatant), True
        else:
            # If rules engine not available, format the action manually
            fallback_result = {
                "action": json_data.get("action", "Acts"),
                "target": json_data.get("target", ""),
                "result": json_data.get("explanation", ""),
                "success": True,
                "damage": 0,
                "dice": []
            }
            return fallback_result, True
            
    def _extract_basic_action(self, text: str, combatant: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Extract basic action/target from free text response."""
        # Try to extract action using pattern matching
        action_match = re.search(r'(?:I\s+)?(attack|cast|move|dodge|dash|disengage|help|hide|use)\s+(?:with\s+)?([^\.]*)(?:\.|\n|$)', 
                                text, re.IGNORECASE)
        if action_match:
            action_verb = action_match.group(1).strip()
            action_object = action_match.group(2).strip()
            
            # Extract target if present
            target_match = re.search(r'(?:target|against|at|on)\s+(?:the\s+)?([^\.\,]+)', text, re.IGNORECASE)
            target = target_match.group(1).strip() if target_match else ""
            
            # Create basic action data
            return {
                "action": f"{action_verb} {action_object}".strip(),
                "target": target,
                "explanation": f"{combatant.get('name', 'Creature')} chooses to {action_verb.lower()} {action_object}."
            }
        return None
        
    def _generate_fallback_action(self, active_combatant: Dict[str, Any], 
                                 all_combatants: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate a simple fallback action when LLM parsing fails."""
        # Find a target (first enemy)
        target = None
        active_type = active_combatant.get("type", "").lower()
        for combatant in all_combatants:
            combatant_type = combatant.get("type", "").lower()
            if combatant == active_combatant:
                continue
            if (active_type == "monster" and combatant_type != "monster") or \
               (active_type != "monster" and combatant_type == "monster"):
                target = combatant
                break
                
        if target:
            return {
                "action": "Attack",
                "target": target.get("name", "enemy"),
                "explanation": f"Fallback: {active_combatant.get('name', 'Creature')} attacks the nearest enemy."
            }
        else:
            return {
                "action": "Dodge",
                "explanation": f"Fallback: {active_combatant.get('name', 'Creature')} takes the Dodge action."
            }
            
    def _format_action_result(self, action_result: ActionResult, intent: Dict[str, Any], 
                            active_combatant: Dict[str, Any]) -> Dict[str, Any]:
        """Format the rules engine result into the expected format for the UI."""
        # Convert ActionResult to the format expected by the UI
        result_dict = {
            "action": intent.get("action", "Unknown action"),
            "target": intent.get("target", ""),
            "result": action_result.narrative,
            "narrative": action_result.narrative,
            "success": action_result.success,
            "damage": action_result.damage,
            "healing": action_result.healing, 
            "dice": action_result.dice_rolls,
            "effects": action_result.effects,
            "action_type": self._determine_action_type(intent.get("action", "")),
            "action_icon": self._get_action_icon(intent.get("action", "")),
            "actor": active_combatant.get("name", "Unknown"),
            "fallback": "fallback" in intent.get("explanation", "").lower()
        }
        
        return result_dict
        
    def _determine_action_type(self, action_text: str) -> str:
        """Determine the type of action (attack, spell, etc)."""
        action_text = action_text.lower()
        
        if any(x in action_text for x in ["attack", "strike", "slash", "stab", "shoot"]):
            return "attack"
        elif any(x in action_text for x in ["cast", "spell"]):
            return "spell"
        elif any(x in action_text for x in ["move", "position"]):
            return "movement"
        elif any(x in action_text for x in ["heal", "cure"]):
            return "healing"
        elif "dodge" in action_text:
            return "defense"
        else:
            return "standard"
            
    def _get_action_icon(self, action_text: str) -> str:
        """Get an icon representing the action type."""
        action_type = self._determine_action_type(action_text)
        
        icons = {
            "attack": "⚔️",
            "spell": "✨",
            "movement": "👣",
            "healing": "❤️",
            "defense": "🛡️",
            "standard": "⚡"
        }
        
        return icons.get(action_type, "⚡")

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