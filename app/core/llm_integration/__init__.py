# This file makes the 'llm_integration' directory a Python package 

import logging

from app.core.llm_service import LLMService # Correct import path
from app.core.models.monster import Monster, MonsterAction # Import both from monster module

logger = logging.getLogger(__name__)

def generate_encounter_details(llm_service, players, encounter_type, environment, difficulty):
    """
    Generates encounter details including monster list, narrative, and tactics.
    (Existing function - keeping it here)
    """
    # ... existing implementation ...
    logger.info("Generating encounter details (placeholder)...")
    # Replace with actual LLM call logic using llm_service
    # Example placeholder response
    return {
        "monsters": ["Goblin", "Orc", "Bugbear"],
        "narrative": "A motley group ambushes the party...",
        "tactics": "Goblins attack from range, Orcs engage in melee..."
    }


def generate_monster_stat_block(llm_service: LLMService, monster_name: str) -> Monster | None:
    """
    Generate a D&D 5e monster stat block using the LLM service.
    
    Args:
        llm_service: The LLM service instance.
        monster_name: The name of the monster to generate.
        
    Returns:
        A Monster object if successful, None otherwise.
    """
    if not monster_name or not llm_service:
        logger.error("Missing required parameters for monster generation")
        return None
        
    try:
        # Extract base monster type and specialization cues
        parts = monster_name.split()
        base_monster_type = parts[0] if parts else monster_name
        
        # Look for descriptors that might indicate elements or special traits
        descriptors = []
        elements = ["Fire", "Frost", "Ice", "Shadow", "Spectral", "Thunder", "Storm", "Arcane", 
                    "Fey", "Stone", "Crystal", "Void", "Thorn", "Blood", "Ancient", "Elder"]
        roles = ["Scout", "Warrior", "Mage", "Sorcerer", "Shaman", "Ranger", "Archer", "Brute", 
                "Leader", "Captain", "Chieftain", "Assassin", "Rogue", "Knight", "Guardian", "Priest"]
        
        # Check for elemental or role descriptors in the name
        for part in parts:
            if part.lower() != base_monster_type.lower():
                if any(element.lower() == part.lower() for element in elements):
                    descriptors.append(f"elemental ({part.lower()})")
                elif any(role.lower() == part.lower() for role in roles):
                    descriptors.append(f"specialized role ({part.lower()})")
                else:
                    descriptors.append(part.lower())
        
        # Create a detailed prompt for the LLM
        prompt = f"""Generate a D&D 5e monster stat block for a creature called "{monster_name}". Respond with ONLY a JSON object.

MONSTER ANALYSIS:
- Base monster type: {base_monster_type}
- Special descriptors: {', '.join(descriptors) if descriptors else 'none'}
- Monster appears to be a specialized or unique variant.

Make sure to create appropriate and interesting abilities that reflect the monster's specialization, role, or elemental affinity. This should be a UNIQUE monster with distinctive traits.

Format the response as a JSON object with these fields:
{{
  "name": "{monster_name}",
  "size": "Medium",  // One of: Tiny, Small, Medium, Large, Huge, Gargantuan
  "type": "humanoid",  // e.g., beast, monstrosity, fiend, etc.
  "alignment": "neutral",  // e.g., lawful good, chaotic evil, unaligned
  "armor_class": 15,  // AC as integer
  "hit_points": "45 (6d8 + 12)",  // HP with HD formula
  "speed": "30 ft., swim 20 ft.",  // All movement types
  "strength": 14,  // STR score (1-30)
  "dexterity": 12,  // DEX score (1-30)
  "constitution": 14,  // CON score (1-30)
  "intelligence": 10,  // INT score (1-30)
  "wisdom": 10,  // WIS score (1-30)
  "charisma": 8,  // CHA score (1-30)
  "challenge_rating": "2",  // CR as string (e.g., "1/4", "2", "10")
  "languages": "Common, Elvish",  // Languages the creature speaks
  "skills": [  // Special skill proficiencies - match these to the creature's role
    {{"name": "Perception", "modifier": 4}},
    {{"name": "Stealth", "modifier": 3}}
  ],
  "senses": [  // Special senses
    {{"name": "Darkvision", "range": "60 ft."}},
    {{"name": "Passive Perception", "range": "14"}}
  ],
  "traits": [  // Special abilities - include thematic abilities that match the creature's role
    {{"name": "Amphibious", "description": "The creature can breathe air and water."}}
  ],
  "actions": [  // Actions in combat - make these interesting and unique
    {{"name": "Multiattack", "description": "The creature makes two attacks: one with its bite and one with its claws."}},
    {{"name": "Bite", "description": "Melee Weapon Attack: +4 to hit, reach 5 ft., one target. Hit: 7 (1d8 + 3) piercing damage."}}
  ],
  "legendary_actions": [  // Optional: legendary actions (null if none)
    {{"name": "Detect", "description": "The creature makes a Wisdom (Perception) check.", "cost": 1}}
  ],
  "description": "A detailed lore description of the {monster_name}, explaining what makes it different from standard {base_monster_type}s, its unique role, and its behaviors or origins."
}}

IMPORTANT GUIDELINES:
1. This should be a UNIQUE and INTERESTING monster with distinctive traits and abilities.
2. If the monster name suggests an elemental affinity (e.g., "Frost Goblin"), add appropriate elemental damage and resistances.
3. If the monster name suggests a specialized role (e.g., "Scout", "Mage"), give it abilities that match that role.
4. Make the stats, abilities, and actions interesting, creative, and thematically appropriate.
5. Add at least one UNIQUE signature ability that makes this monster stand out.
6. Ensure CR and stats are balanced according to D&D 5e rules.
7. Be creative but consistent with D&D 5e mechanics.

IMPORTANT: Respond with ONLY the JSON object. No additional explanations.
"""

        # Try to get available models
        try:
            available_models = llm_service.get_available_models()
            if not available_models:
                logger.warning("No LLM models configured, falling back to placeholder monster")
                return _create_placeholder_monster(monster_name)
                
            model_id = available_models[0]["id"]
        except Exception as e:
            logger.error(f"Error getting available models: {e}")
            logger.warning("Falling back to placeholder monster")
            return _create_placeholder_monster(monster_name)

        # Call the LLM using synchronous method (we're in a synchronous context)
        logger.info(f"Calling LLM to generate stat block for '{monster_name}'")
        
        try:
            response = llm_service.generate_completion(
                model=model_id,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=1500
            )
            
            if not response:
                logger.error("Empty response from LLM")
                return _create_placeholder_monster(monster_name)
                
            # Log the first 100 characters of the response
            logger.debug(f"LLM response preview: {response[:100]}...")
            
            # Clean up any JSON code fences
            clean_response = response.strip()
            if clean_response.startswith("```json"):
                clean_response = clean_response[7:]
            if clean_response.endswith("```"):
                clean_response = clean_response[:-3]
            
            clean_response = clean_response.strip()
            
            # Parse the JSON response
            import json
            monster_data = json.loads(clean_response)
            
            # Convert the JSON data to a Monster object
            monster_obj = Monster.from_dict(monster_data)
            
            # Add additional metadata
            monster_obj.is_custom = True
            monster_obj.source = "AI Generated"
            
            logger.info(f"Successfully generated monster '{monster_name}' with CR {monster_obj.challenge_rating}")
            return monster_obj
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.warning(f"Response was: {response}")
            return _create_placeholder_monster(monster_name)
        except Exception as e:
            logger.error(f"Error during LLM generation: {e}")
            return _create_placeholder_monster(monster_name)
            
    except Exception as e:
        logger.error(f"Unexpected error in monster generation: {e}")
        return _create_placeholder_monster(monster_name)


def _create_placeholder_monster(monster_name: str) -> Monster:
    """
    Create a basic placeholder monster with minimal stats.
    Used as a fallback when LLM generation fails.
    
    Args:
        monster_name: The name of the monster.
        
    Returns:
        A basic Monster object.
    """
    logger.info(f"Creating placeholder monster for '{monster_name}'")
    
    # Extract potential role or type from the name
    name_parts = monster_name.lower().split()
    
    # Default values
    size = "Medium"
    monster_type = "humanoid"
    hp = "20 (3d8 + 3)"
    str_val, dex_val, con_val, int_val, wis_val, cha_val = 10, 10, 10, 10, 10, 10
    speed = "30 ft."
    cr = "1"
    
    # Adjust based on name hints
    if any(x in name_parts for x in ["tiny", "small", "diminutive"]):
        size = "Small"
        hp = "10 (3d6)"
        str_val = 8
    elif any(x in name_parts for x in ["large", "big", "great"]):
        size = "Large"
        hp = "45 (6d10 + 12)"
        str_val = 16
        con_val = 14
    
    # Adjust type based on name
    if any(x in name_parts for x in ["undead", "skeleton", "zombie", "ghoul"]):
        monster_type = "undead"
    elif any(x in name_parts for x in ["dragon", "drake", "wyrm"]):
        monster_type = "dragon"
        cr = "3"
    elif any(x in name_parts for x in ["beast", "animal", "wolf", "bear"]):
        monster_type = "beast"
    
    # Adjust abilities based on role
    actions = []
    traits = []
    
    # Basic attack
    melee_attack = MonsterAction(
        name="Slam", 
        description=f"Melee Weapon Attack: +3 to hit, reach 5 ft., one target. Hit: 5 (1d6 + 2) bludgeoning damage."
    )
    
    # Add specialized attacks and traits based on name
    if any(x in name_parts for x in ["mage", "wizard", "sorcerer", "caster", "magic"]):
        int_val = 14
        cha_val = 14
        cr = "2"
        actions.append(MonsterAction(
            name="Magic Missile",
            description="Ranged Spell Attack: The creature fires three magical darts. Each dart hits a creature of the caster's choice within 120 feet and deals 3 (1d4 + 1) force damage."
        ))
        traits.append({
            "name": "Spellcasting",
            "description": f"The {monster_name} is a 3rd-level spellcaster. Its spellcasting ability is Intelligence (spell save DC 12, +4 to hit with spell attacks)."
        })
    elif any(x in name_parts for x in ["archer", "ranger", "shooter", "sniper"]):
        dex_val = 14
        wis_val = 12
        actions.append(MonsterAction(
            name="Longbow",
            description="Ranged Weapon Attack: +4 to hit, range 150/600 ft., one target. Hit: 6 (1d8 + 2) piercing damage."
        ))
    elif any(x in name_parts for x in ["warrior", "fighter", "brute", "soldier"]):
        str_val = 14
        con_val = 12
        actions.append(MonsterAction(
            name="Greatsword",
            description="Melee Weapon Attack: +4 to hit, reach 5 ft., one target. Hit: 9 (2d6 + 2) slashing damage."
        ))
        actions.append(MonsterAction(
            name="Shield Bash",
            description="Melee Weapon Attack: +4 to hit, reach 5 ft., one target. Hit: 5 (1d4 + 3) bludgeoning damage, and the target must succeed on a DC 13 Strength saving throw or be knocked prone."
        ))
    elif any(x in name_parts for x in ["scout", "rogue", "thief", "stalker"]):
        dex_val = 15
        int_val = 12
        actions.append(MonsterAction(
            name="Dagger",
            description="Melee or Ranged Weapon Attack: +4 to hit, reach 5 ft. or range 20/60 ft., one target. Hit: 4 (1d4 + 2) piercing damage."
        ))
        traits.append({
            "name": "Sneak Attack",
            "description": "The creature deals an extra 7 (2d6) damage when it hits a target with a weapon attack and has advantage on the attack roll, or when the target is within 5 feet of an ally of the creature that isn't incapacitated and the creature doesn't have disadvantage on the attack roll."
        })
    
    # Always include at least one basic attack
    if not actions:
        actions.append(melee_attack)
    
    # Generate a more interesting description based on monster name
    description = f"A placeholder {monster_name} created when LLM generation failed. This appears to be a {size.lower()} {monster_type} with "
    
    # Add flavor based on stats
    if str_val > 12:
        description += "notable physical strength. "
    elif dex_val > 12:
        description += "quick, nimble movements. "
    elif int_val > 12:
        description += "a cunning, intelligent demeanor. "
    else:
        description += "an unremarkable appearance. "
    
    description += f"It likely serves as a {name_parts[-1] if len(name_parts) > 1 else 'standard fighter'} in its society."
    
    try:
        test_monster = Monster(
            name=monster_name.strip() or "Unknown Creature",
            size=size,
            type=monster_type,
            alignment="neutral",
            armor_class=10 + (dex_val - 10) // 2,  # Simple AC calculation
            hit_points=hp,
            speed=speed,
            strength=str_val,
            dexterity=dex_val,
            constitution=con_val,
            intelligence=int_val,
            wisdom=wis_val,
            charisma=cha_val,
            challenge_rating=cr,
            description=description,
            actions=actions,
            traits=traits,
            is_custom=True,
            source="AI Generated (Placeholder)"
        )
        
        return test_monster
    except Exception as e:
        logger.error(f"Error creating placeholder monster: {e}")
        # Create absolute minimum monster if even the placeholder fails
        return Monster(
            name=monster_name.strip() or "Emergency Fallback Monster",
            is_custom=True,
            source="Error Recovery Placeholder"
        )

# You might eventually want other LLM-related functions here, like:
# - generate_npc_details
# - generate_location_description
# - etc. 