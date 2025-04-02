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
        # Create a detailed prompt for the LLM
        prompt = f"""Generate a D&D 5e monster stat block for a creature called "{monster_name}". Respond with ONLY a JSON object.

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
  "skills": [  // Special skill proficiencies
    {{"name": "Perception", "modifier": 4}},
    {{"name": "Stealth", "modifier": 3}}
  ],
  "senses": [  // Special senses
    {{"name": "Darkvision", "range": "60 ft."}},
    {{"name": "Passive Perception", "range": "14"}}
  ],
  "traits": [  // Special abilities
    {{"name": "Amphibious", "description": "The creature can breathe air and water."}}
  ],
  "actions": [  // Actions in combat
    {{"name": "Multiattack", "description": "The creature makes two attacks: one with its bite and one with its claws."}},
    {{"name": "Bite", "description": "Melee Weapon Attack: +4 to hit, reach 5 ft., one target. Hit: 7 (1d8 + 3) piercing damage."}}
  ],
  "legendary_actions": [  // Optional: legendary actions (null if none)
    {{"name": "Detect", "description": "The creature makes a Wisdom (Perception) check.", "cost": 1}}
  ],
  "description": "A brief lore description of the {monster_name} and its habits or origins."
}}

Be creative but consistent with D&D 5e rules. Ensure CR and stats are balanced.
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
    
    # For testing, create a minimal valid Monster object
    try:
        test_monster = Monster(
            name=monster_name.strip() or "Unknown Creature",
            size="Medium",
            type="humanoid",
            alignment="neutral",
            armor_class=12,
            hit_points="20 (3d8 + 3)",
            speed="30 ft.",
            strength=10,
            dexterity=10,
            constitution=10,
            intelligence=10,
            wisdom=10,
            charisma=10,
            challenge_rating="1",
            description=f"A placeholder {monster_name}. This is a test monster generated as a fallback when LLM generation failed.",
            actions=[
                MonsterAction(
                    name="Basic Attack", 
                    description="Melee Weapon Attack: +3 to hit, reach 5 ft., one target. Hit: 5 (1d6 + 2) slashing damage."
                )
            ],
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