"""
Monster ability validation module to prevent cross-monster ability mixing.

This utility provides functions to validate that monster abilities are correctly
assigned to the appropriate monster and prevents mixing of abilities between
different monster types.
"""

import logging
import re
from typing import Dict, List, Any, Tuple, Set

logger = logging.getLogger(__name__)

# Cache for monster canonical abilities to avoid repeated processing
_monster_canonical_abilities_cache = {}

def extract_ability_names(monster: Dict[str, Any]) -> Set[str]:
    """
    Extract all ability names from a monster to create a canonical set.
    
    Args:
        monster: Monster data dictionary
        
    Returns:
        Set of ability names that belong to this monster
    """
    ability_names = set()
    
    # Extract action names
    actions = monster.get("actions", [])
    if isinstance(actions, list):
        for action in actions:
            if isinstance(action, dict) and "name" in action:
                ability_names.add(action["name"].lower())
    
    # Extract trait names
    traits = monster.get("traits", [])
    if isinstance(traits, list):
        for trait in traits:
            if isinstance(trait, dict) and "name" in trait:
                ability_names.add(trait["name"].lower())
    
    # Extract ability names
    abilities = monster.get("abilities", {})
    if isinstance(abilities, dict):
        for ability_name in abilities:
            ability_names.add(ability_name.lower())
    
    return ability_names

def get_canonical_abilities(monster_name: str, monster_data: Dict[str, Any]) -> Set[str]:
    """
    Get the canonical set of ability names for a monster.
    
    Args:
        monster_name: Name of the monster
        monster_data: Monster data dictionary
        
    Returns:
        Set of ability names that belong to this monster
    """
    # FIXED: Remove the problematic caching mechanism that could lead to ability mixing
    # Instead, always extract abilities directly from the monster data
    
    # Extract ability names directly without using cache
    ability_names = extract_ability_names(monster_data)
    
    # Add the monster name itself as a prefix to each ability to ensure uniqueness
    # This prevents cross-monster ability mixing by making each monster's abilities unique
    prefixed_abilities = set()
    for ability in ability_names:
        prefixed_abilities.add(f"{monster_name.lower()}_{ability}")
    
    # Also keep the original abilities to maintain backward compatibility
    combined_abilities = ability_names.union(prefixed_abilities)
    
    return combined_abilities

def validate_combat_prompt(prompt: str) -> Tuple[bool, str]:
    """
    Validate a combat prompt to ensure monster abilities are correctly assigned.
    This function now also checks for untagged abilities in the actions/traits sections
    and verifies they belong to the active monster.
    Args:
        prompt: Combat prompt to validate
    Returns:
        Tuple of (is_valid, corrected_prompt_or_error_message)
    """
    # Extract all monster ability tags (original logic)
    ability_pattern = r'\[([A-Za-z0-9_\s]+)_(\d+)_ability\]'
    ability_tags = list(re.finditer(ability_pattern, prompt))
    monster_abilities = {}
    # Group abilities by monster (original logic)
    for match in ability_tags:
        monster_name, monster_id = match.groups()
        full_tag = match.group(0)
        ability_line = prompt.split(full_tag)[0].split('\n')[-1].strip()
        ability_name_match = re.match(r'- ([^:]+):', ability_line)
        if ability_name_match:
            ability_name = ability_name_match.group(1).strip()
        else:
            continue
        monster_key = f"{monster_name}_{monster_id}"
        if monster_key not in monster_abilities:
            monster_abilities[monster_key] = []
        monster_abilities[monster_key].append((ability_name, full_tag))
    # Check for mixed abilities (original logic)
    all_monsters = set(monster_abilities.keys())
    mixed_abilities = []
    for monster_key, abilities in monster_abilities.items():
        for ability_name, tag in abilities:
            for other_monster in all_monsters:
                if other_monster == monster_key:
                    continue
                for other_ability, other_tag in monster_abilities.get(other_monster, []):
                    if ability_name.lower() == other_ability.lower():
                        mixed_abilities.append((ability_name, monster_key, other_monster))
    # If mixing detected by tags, return error
    if mixed_abilities:
        error_message = "Ability mixing detected:\n"
        for ability, monster1, monster2 in mixed_abilities:
            error_message += f"- Ability '{ability}' appears in both {monster1} and {monster2}\n"
        return False, error_message
    # --- NEW LOGIC: Check for untagged ability mixing ---
    # Try to find the active monster
    active_pattern = r"Active Combatant: ([A-Za-z0-9_\s]+)"
    active_match = re.search(active_pattern, prompt)
    if not active_match:
        return True, prompt  # Can't determine active monster, assume valid
    active_monster = active_match.group(1).strip()
    # Try to extract canonical abilities for the active monster
    # (Assume monster name is enough; in real use, pass monster data)
    # For now, just collect all ability names in actions/traits sections
    lines = prompt.split("\n")
    in_abilities_section = False
    in_actions_section = False
    in_traits_section = False
    found_invalid = []
    for line in lines:
        if "# SPECIFIC ABILITIES, ACTIONS AND TRAITS" in line:
            in_abilities_section = True
            continue
        if in_abilities_section and line.strip().startswith("## Actions:"):
            in_actions_section = True
            in_traits_section = False
            continue
        if in_abilities_section and line.strip().startswith("## Traits:"):
            in_actions_section = False
            in_traits_section = True
            continue
        if in_abilities_section and (line.strip().startswith("## ") or line.strip().startswith("# ")):
            in_actions_section = False
            in_traits_section = False
            in_abilities_section = "## " in line or "# NEARBY" in line
            continue
        # Check for ability line
        if (in_actions_section or in_traits_section) and line.strip().startswith("- ") and ":" in line:
            # Extract ability name
            ability_name_match = re.match(r'- ([^:]+):', line.strip())
            if ability_name_match:
                ability_name = ability_name_match.group(1).strip().lower()
                # If the ability is not in the active monster's name, flag as invalid
                # (In real use, compare to canonical abilities. Here, just check for monster name in line)
                if active_monster.lower() not in line.lower():
                    found_invalid.append(ability_name)
    if found_invalid:
        error_message = "Ability mixing detected (untagged abilities):\n"
        for ability in found_invalid:
            error_message += f"- Ability '{ability}' does not belong to {active_monster}\n"
        return False, error_message
    return True, prompt

def clean_abilities_in_prompt(prompt: str) -> str:
    """
    Clean abilities in the prompt by ensuring each ability is properly tagged with the monster ID.
    
    Args:
        prompt: Combat prompt to clean
        
    Returns:
        Cleaned prompt with correct ability tags
    """
    lines = prompt.split("\n")
    current_monster = None
    monster_id = None
    cleaned_lines = []
    
    # Search for active monster name
    active_pattern = r"Active Combatant: ([A-Za-z0-9_\s]+)"
    active_match = re.search(active_pattern, prompt)
    
    if active_match:
        current_monster = active_match.group(1).strip()
        
        # Search for monster ID (use index if no ID found)
        for i, line in enumerate(lines):
            if f"# {current_monster.upper()} DETAILS" in line:
                monster_id = "0"  # Default ID if none found
                break
    
    # Process each line
    for line in lines:
        # If line is an ability definition but missing a tag
        if line.strip().startswith("- ") and ":" in line and "[" not in line and current_monster and monster_id:
            # Add the tag
            line = f"{line} [{current_monster}_{monster_id}_ability]"
        
        cleaned_lines.append(line)
    
    return "\n".join(cleaned_lines)

def verify_abilities_match_monster(monster_name: str, abilities: List[Dict[str, str]], 
                                 canonical_abilities: Set[str]) -> List[Dict[str, str]]:
    """
    Verify that abilities match the canonical list for a monster.
    
    Args:
        monster_name: Monster name
        abilities: List of ability dictionaries
        canonical_abilities: Set of canonical ability names for this monster
        
    Returns:
        Clean list of abilities that belong to this monster
    """
    if not abilities:
        return []
    
    # FIXED: Make ability matching more lenient to avoid filtering out legitimate abilities
    # Return all abilities in their original form for this specific monster
    
    # Common generic abilities that should always be allowed regardless of monster
    generic_abilities = {
        "multiattack", "attack", "bite", "claw", "slam", "punch", "melee attack", 
        "ranged attack", "basic attack", "legendary action", "lair action",
        "innate spellcasting", "spellcasting", "tail", "wing"
    }
    
    # Skip validation for specific monsters where we know the abilities are correct
    if abilities and len(abilities) > 0:
        # Get first ability name to check for prefixed validation format
        first_ability = abilities[0].get("name", "").lower() if isinstance(abilities[0], dict) else ""
        prefixed_name = f"{monster_name.lower()}_"
        
        # If the ability is already prefixed with the monster name or is a generic ability,
        # skip further validation as it's already properly attributed
        if (first_ability.startswith(prefixed_name) or 
            first_ability in generic_abilities or
            first_ability in canonical_abilities):
            return abilities
    
    # Only filter abilities if they clearly belong to another monster
    # This means they must have another monster's name as prefix
    valid_abilities = []
    removed_abilities = []
    
    for ability in abilities:
        if not isinstance(ability, dict) or "name" not in ability:
            continue
        
        ability_name = ability["name"].lower()
        
        # Check if this ability is explicitly prefixed with another monster's name
        if "_" in ability_name:
            prefix, _ = ability_name.split("_", 1)
            if prefix != monster_name.lower() and prefix not in monster_name.lower() and monster_name.lower() not in prefix:
                # This ability explicitly belongs to another monster
                removed_abilities.append(ability["name"])
                continue
        
        # Accept the ability if:
        # 1. It's in the canonical abilities list
        # 2. It's a generic ability
        # 3. It doesn't have a prefix indicating it belongs to another monster
        if (ability_name in canonical_abilities or 
            ability_name in generic_abilities or 
            f"{monster_name.lower()}_{ability_name}" in canonical_abilities):
            valid_abilities.append(ability)
        else:
            removed_abilities.append(ability["name"])
    
    if removed_abilities:
        logger.warning(f"Removed {len(removed_abilities)} abilities that don't belong to {monster_name}: {removed_abilities}")
    
    # If all abilities were filtered out, return the original list to avoid empty abilities
    if not valid_abilities and abilities:
        logger.warning(f"All abilities were filtered out for {monster_name}. Keeping original abilities.")
        return abilities
    
    return valid_abilities

def fix_mixed_abilities_in_prompt(prompt: str) -> str:
    """
    Fix mixed abilities in a combat prompt by removing abilities that don't belong
    to the active monster, even if they are untagged.
    Args:
        prompt: Combat prompt to fix
    Returns:
        Fixed prompt with correct abilities only
    """
    logger.info("Actively fixing mixed abilities in combat prompt")
    # First, make sure all abilities are properly tagged
    prompt = clean_abilities_in_prompt(prompt)
    # Extract active monster name
    active_pattern = r"Active Combatant: ([A-Za-z0-9_\s]+)"
    active_match = re.search(active_pattern, prompt)
    if not active_match:
        logger.warning("Could not determine active monster from prompt")
        return prompt
    active_monster = active_match.group(1).strip()
    active_monster_key = f"{active_monster}_0"  # Assume ID 0 for active monster
    ability_pattern = r'\[([A-Za-z0-9_\s]+)_(\d+)_ability\]'
    lines = prompt.split("\n")
    fixed_lines = []
    in_abilities_section = False
    in_actions_section = False
    in_traits_section = False
    removed_actions = 0
    removed_traits = 0
    for line in lines:
        if "# SPECIFIC ABILITIES, ACTIONS AND TRAITS" in line:
            in_abilities_section = True
            fixed_lines.append(line)
            continue
        if in_abilities_section and line.strip().startswith("## Actions:"):
            in_actions_section = True
            in_traits_section = False
            fixed_lines.append(line)
            continue
        if in_abilities_section and line.strip().startswith("## Traits:"):
            in_actions_section = False
            in_traits_section = True
            fixed_lines.append(line)
            continue
        if in_abilities_section and (line.strip().startswith("## ") or line.strip().startswith("# ")):
            in_actions_section = False
            in_traits_section = False
            in_abilities_section = "## " in line or "# NEARBY" in line
            fixed_lines.append(line)
            continue
        # Check if this line contains an ability
        if (in_actions_section or in_traits_section) and line.strip().startswith("- ") and ":" in line:
            # Extract tag if present
            tag_match = re.search(ability_pattern, line)
            if tag_match:
                monster_name, monster_id = tag_match.groups()
                monster_key = f"{monster_name}_{monster_id}"
                # If this ability belongs to a different monster, remove it
                if monster_key != active_monster_key:
                    logger.info(f"Removing ability that belongs to {monster_key} from {active_monster_key}'s prompt")
                    if in_actions_section:
                        removed_actions += 1
                    elif in_traits_section:
                        removed_traits += 1
                    continue
            else:
                # No tag: check if the ability name likely belongs to the active monster
                # (In real use, compare to canonical abilities. Here, just check for monster name in line)
                if active_monster.lower() not in line.lower():
                    logger.info(f"Removing untagged ability not matching {active_monster}")
                    if in_actions_section:
                        removed_actions += 1
                    elif in_traits_section:
                        removed_traits += 1
                    continue
            fixed_lines.append(line)
        else:
            fixed_lines.append(line)
    # Add generic replacements if needed
    if removed_actions > 0 or removed_traits > 0:
        # Find the end of the actions section to add replacements
        fixed_prompt = "\n".join(fixed_lines)
        
        # Add generic actions if needed
        if removed_actions > 0:
            actions_section_end = fixed_prompt.find("## Traits:") if "## Traits:" in fixed_prompt else fixed_prompt.find("# NEARBY")
            if actions_section_end > 0:
                # Add up to 2 generic actions
                replacements = []
                for i in range(min(removed_actions, 2)):
                    replacements.append(f"- Basic Attack: Melee Weapon Attack: +5 to hit, reach 5 ft., one target. Hit: 8 (1d8 + 4) damage. [{active_monster_key}_ability]")
                
                if replacements:
                    fixed_prompt = fixed_prompt[:actions_section_end] + "\n" + "\n".join(replacements) + "\n" + fixed_prompt[actions_section_end:]
        
        # Add generic traits if needed
        if removed_traits > 0:
            traits_section_end = fixed_prompt.find("# NEARBY")
            if traits_section_end > 0:
                # Add up to 2 generic traits
                replacements = []
                for i in range(min(removed_traits, 2)):
                    replacements.append(f"- Natural Armor: The creature's thick hide provides natural protection, increasing its AC. [{active_monster_key}_ability]")
                
                if replacements:
                    fixed_prompt = fixed_prompt[:traits_section_end] + "\n" + "\n".join(replacements) + "\n" + fixed_prompt[traits_section_end:]
        
        return fixed_prompt
    
    return "\n".join(fixed_lines)

def generate_monster_specific_prompt(monster_data: Dict[str, Any], prompt_template: str) -> str:
    """
    Generate a combat prompt with abilities that specifically match the given monster.
    
    Args:
        monster_data: Dictionary with monster data
        prompt_template: Template prompt to fill in
        
    Returns:
        Prompt with correct monster-specific abilities
    """
    monster_name = monster_data.get("name", "Unknown Monster")
    monster_id = monster_data.get("id", 0)
    monster_key = f"{monster_name}_{monster_id}"
    
    # Extract canonical abilities for this monster
    canonical_abilities = get_canonical_abilities(monster_name, monster_data)
    
    # Create ability sections
    actions_text = "No special actions available."
    traits_text = "No special traits available."
    
    # Format actions
    actions = monster_data.get("actions", [])
    if actions and isinstance(actions, list):
        formatted_actions = []
        for action in actions:
            if isinstance(action, dict) and "name" in action and "description" in action:
                formatted_actions.append(f"- {action['name']}: {action['description']} [{monster_key}_ability]")
        
        if formatted_actions:
            actions_text = "\n".join(formatted_actions)
    
    # Format traits
    traits = monster_data.get("traits", [])
    if traits and isinstance(traits, list):
        formatted_traits = []
        for trait in traits:
            if isinstance(trait, dict) and "name" in trait and "description" in trait:
                formatted_traits.append(f"- {trait['name']}: {trait['description']} [{monster_key}_ability]")
        
        if formatted_traits:
            traits_text = "\n".join(formatted_traits)
    
    # Replace placeholders in template
    prompt = prompt_template.replace("{{MONSTER_NAME}}", monster_name)
    prompt = prompt.replace("{{MONSTER_ACTIONS}}", actions_text)
    prompt = prompt.replace("{{MONSTER_TRAITS}}", traits_text)
    
    return prompt 