# app/core/llm_integration/monster_generator.py

import json
from typing import Optional, Dict, Any
import logging
import asyncio

from app.core.llm_service import LLMService # Assuming LLMService is importable
from app.core.models.monster import Monster # Import the new Monster class
from app.core.llm_service import ModelInfo

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Prompt Templates ---

# Prompt for generating a full monster stat block based on a concept
# We request JSON output matching our Monster dataclass structure closely.
GENERATION_PROMPT_TEMPLATE = """
Generate a Dungeons & Dragons 5th Edition monster stat block based on the following concept:
Concept: "{user_prompt}"

Output the stat block as a JSON object. The JSON structure should match the following format,
omitting fields that are not applicable or cannot be reasonably determined.
Use standard 5e terminology and conventions. Calculate ability modifiers implicitly.
Ensure the Challenge Rating (CR) is appropriate if specified, otherwise make a reasonable estimate.

JSON Format Example (use appropriate values based on the concept):
{{
  "name": "Generated Monster Name",
  "size": "Medium", // e.g., Tiny, Small, Medium, Large, Huge, Gargantuan
  "type": "beast", // e.g., humanoid, monstrosity, fiend, undead, etc.
  "alignment": "chaotic evil", // e.g., lawful good, neutral, unaligned, etc.
  "ac": 15, // Armor Class (number)
  "hp": "110 (15d10 + 30)", // Hit Points (dice expression)
  "speed": "30 ft., fly 60 ft.", // Speeds string
  "str": 18, "dex": 14, "con": 16, "int": 8, "wis": 12, "cha": 10, // Ability scores (numbers)
  "cr": "7", // Challenge Rating (string, e.g., "1/2", "5")
  "skills": [ // List of skill proficiencies with total modifier
    {{"name": "Perception", "modifier": 5}},
    {{"name": "Stealth", "modifier": 6}}
  ],
  "senses": [ // List of senses
    {{"name": "Darkvision", "range": "120 ft."}},
    {{"name": "Passive Perception", "range": "15"}} // Calculate based on Wis + Perception proficiency if applicable
  ],
  "languages": "Common, Draconic", // Languages string
  "traits": [ // List of special traits
    {{"name": "Amphibious", "description": "The monster can breathe air and water."}},
    {{"name": "Sunlight Sensitivity", "description": "While in sunlight, the monster has disadvantage..."}}
  ],
  "actions": [ // List of actions
    {{
      "name": "Multiattack",
      "description": "The monster makes two attacks: one with its bite and one with its claws."
    }},
    {{
      "name": "Bite",
      "description": "Melee Weapon Attack: +7 to hit, reach 5 ft., one target. Hit: 11 (2d6 + 4) piercing damage."
    }}
  ],
  "legendary_actions": [ // Optional list of legendary actions
     {{
       "name": "Detect",
       "description": "The monster makes a Wisdom (Perception) check.",
       "cost": 1
     }},
     {{
        "name": "Tail Attack (Costs 2 Actions)",
        "description": "The monster makes one tail attack.",
        "cost": 2
     }}
  ],
  "description": "A brief description or lore about the monster.", // Optional
  "source": "LLM Generated" // Source is always LLM Generated
}}

Provide ONLY the JSON object as the output, starting with {{ and ending with }}.
"""

# Prompt for extracting a stat block from unstructured text
# Requests JSON output matching the Monster dataclass.
EXTRACTION_PROMPT_TEMPLATE = """
Extract the Dungeons & Dragons 5th Edition monster stat block information from the text below
and format it as a JSON object. Adhere strictly to the following JSON structure,
omitting fields if the information is not present in the text.
Use standard 5e terminology. Infer ability modifiers if only scores are given.

JSON Format Example:
{{
  "name": "Monster Name from Text",
  "size": "Large", "type": "giant", "alignment": "neutral evil",
  "ac": 13, "hp": "59 (7d10 + 21)", "speed": "40 ft.",
  "str": 17, "dex": 10, "con": 16, "int": 8, "wis": 11, "cha": 9,
  "cr": "3",
  "skills": [{{"name": "Perception", "modifier": 2}}], // Include total modifier if available/calculable
  "senses": [{{"name": "Passive Perception", "range": "12"}}],
  "languages": "Giant",
  "traits": [{{"name": "Keen Smell", "description": "The ogre has advantage on Wisdom (Perception) checks that rely on smell."}}],
  "actions": [
    {{"name": "Greatclub", "description": "Melee Weapon Attack: +5 to hit, reach 5 ft., one target. Hit: 10 (2d8 + 3) bludgeoning damage."}},
    {{"name": "Javelin", "description": "Melee or Ranged Weapon Attack: +5 to hit, reach 5 ft. or range 30/120 ft., one target. Hit: 6 (1d6 + 3) piercing damage."}}
   ],
   "legendary_actions": null, // Use null if none are mentioned
   "description": "Optional description extracted from text.",
   "source": "LLM Extracted" // Source is always LLM Extracted
}}

Input Text:
\"\"\"
{user_text_placeholder}
\"\"\"

Provide ONLY the JSON object as the output, starting with {{ and ending with }}.
"""


def _parse_llm_json_output(llm_output: str) -> Optional[Dict[str, Any]]:
    """
    Safely parses JSON output from the LLM, handling potential markdown fences.

    Args:
        llm_output: The raw string output from the LLM.

    Returns:
        A dictionary parsed from the JSON, or None if parsing fails.
    """
    try:
        # Clean potential markdown code blocks ```json ... ```
        if llm_output.strip().startswith("```json"):
            llm_output = llm_output.strip()[7:] # Remove ```json
            if llm_output.strip().endswith("```"):
                llm_output = llm_output.strip()[:-3] # Remove ```
        elif llm_output.strip().startswith("```"):
             llm_output = llm_output.strip()[3:] # Remove ```
             if llm_output.strip().endswith("```"):
                llm_output = llm_output.strip()[:-3] # Remove ```


        # Find the first '{' and the last '}' to isolate the JSON object
        start_index = llm_output.find('{')
        end_index = llm_output.rfind('}')

        if start_index == -1 or end_index == -1 or start_index >= end_index:
            logger.error(f"Could not find valid JSON object delimiters {{ }} in LLM output: {llm_output[:100]}...")
            return None

        json_string = llm_output[start_index:end_index+1]

        # Parse the identified JSON string
        parsed_json = json.loads(json_string)
        return parsed_json

    except json.JSONDecodeError as e:
        logger.error(f"Failed to decode JSON from LLM output: {e}")
        logger.debug(f"Problematic LLM output snippet: {llm_output[:500]}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred during JSON parsing: {e}")
        logger.debug(f"LLM output snippet: {llm_output[:500]}")
        return None


async def generate_monster_from_prompt(prompt: str, llm_service: LLMService = None) -> Optional[Monster]:
    """
    Generate a monster stat block from a user prompt using LLM.
    
    This is a placeholder implementation that returns a basic monster.
    
    Args:
        prompt: User description of the monster to generate.
        llm_service: The LLM service to use.
        
    Returns:
        A Monster object, or None on failure.
    """
    logger.warning(f"Placeholder 'generate_monster_from_prompt' called with prompt: {prompt}")
    
    try:
        # In a real implementation:
        # 1. Construct a detailed prompt for the LLM.
        # 2. Call llm_service.generate_completion_async(...).
        # 3. Parse the response into a Monster object.
        
        # Extract a name from the first few words of the prompt
        words = prompt.split()
        if len(words) >= 2:
            name = " ".join(words[:2]).title()  # Use first two words as name
        else:
            name = f"{prompt.strip().title()} Creature"
            
        # For testing, create a minimal valid Monster
        test_monster = Monster(
            name=name,
            size="Medium",
            type="humanoid",
            alignment="neutral",
            armor_class=12,
            hit_points=20,
            speed="30 ft.",
            strength=10,
            dexterity=10,
            constitution=10,
            intelligence=10,
            wisdom=10,
            charisma=10,
            challenge_rating="1",
            xp=200,
            description=f"A placeholder monster created from prompt: {prompt}",
            actions=[{
                "name": "Basic Attack", 
                "description": f"Melee Weapon Attack: +3 to hit, reach 5 ft., one target. Hit: 5 (1d6 + 2) slashing damage."
            }],
            is_custom=True,
            source="AI Generated (Placeholder)"
        )
        
        logger.info(f"Created placeholder monster '{name}' for testing")
        return test_monster
        
    except Exception as e:
        logger.error(f"Error in placeholder monster generation from prompt: {e}")
        return None


async def extract_monster_from_text(text: str, llm_service: LLMService = None) -> Optional[Monster]:
    """
    Extract a monster stat block from pasted text using LLM.
    
    This is a placeholder implementation that returns a basic monster.
    
    Args:
        text: Text containing the monster stat block to extract.
        llm_service: The LLM service to use.
        
    Returns:
        A Monster object, or None on failure.
    """
    logger.warning(f"Placeholder 'extract_monster_from_text' called with text length: {len(text)}")
    
    try:
        # Try to extract a name from the first line of text
        lines = text.split('\n')
        first_line = lines[0] if lines else "Unknown Creature"
        name = first_line.strip()
        
        if not name:
            name = "Extracted Creature"
        
        # For testing, create a minimal valid Monster
        test_monster = Monster(
            name=name,
            size="Medium",
            type="humanoid",
            alignment="neutral",
            armor_class=12,
            hit_points=20,
            speed="30 ft.",
            strength=10,
            dexterity=10,
            constitution=10,
            intelligence=10,
            wisdom=10,
            charisma=10,
            challenge_rating="1",
            xp=200,
            description=f"A placeholder monster extracted from text.",
            actions=[{
                "name": "Basic Attack", 
                "description": f"Melee Weapon Attack: +3 to hit, reach 5 ft., one target. Hit: 5 (1d6 + 2) slashing damage."
            }],
            is_custom=True,
            source="AI Generated (Placeholder)"
        )
        
        logger.info(f"Created placeholder monster '{name}' from text extraction")
        return test_monster
        
    except Exception as e:
        logger.error(f"Error in placeholder monster extraction from text: {e}")
        return None 