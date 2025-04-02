# app/core/llm_integration/monster_generator.py

import json
from typing import Optional, Dict, Any
import logging

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


async def generate_monster_from_prompt(llm_service: LLMService, user_prompt: str) -> Optional[Monster]:
    """
    Uses the LLM service to generate a monster stat block from a user prompt.

    Args:
        llm_service: An instance of the LLMService.
        user_prompt: The user's concept for the monster.

    Returns:
        A Monster object if generation and parsing are successful, otherwise None.
    """
    if not user_prompt:
        logger.warning("generate_monster_from_prompt called with empty prompt.")
        return None

    full_prompt = GENERATION_PROMPT_TEMPLATE.format(user_prompt=user_prompt)

    # Get the current model ID from app_state (using placeholder method name)
    # TODO: Replace with actual method if different
    try:
        model_id = llm_service.app_state.get_setting("selected_llm_model", ModelInfo.OPENAI_GPT4O_MINI)
        if not model_id: # Fallback if setting is somehow empty
            model_id = ModelInfo.OPENAI_GPT4O_MINI
            logger.warning(f"No LLM model selected in settings, defaulting to {model_id}")
    except AttributeError:
        logger.error("LLMService does not have access to app_state or get_setting. Cannot determine model.")
        model_id = ModelInfo.OPENAI_GPT4O_MINI # Hardcoded fallback
        logger.warning(f"Defaulting to {model_id} due to app_state access issue.")

    # Format the prompt as messages list
    messages = [{"role": "user", "content": full_prompt}]

    try:
        logger.info(f"Sending generation prompt to LLM ({model_id}) for concept: '{user_prompt}'")

        # Call the correct method: generate_completion
        # Since generate_completion is synchronous, but we are in an async function
        # and running this via AsyncWorker which expects an awaitable,
        # we should ideally make generate_completion async or use run_in_executor.
        # For now, assuming LLMService handles threading or is called via the worker,
        # let's just call it directly. If it blocks, the AsyncWorker setup is needed.
        # Let's assume generate_completion might be async or we adapt the worker call later.

        # **If generate_completion is sync:**
        # response_text = llm_service.generate_completion(model=model_id, messages=messages)
        
        # **If generate_completion needs to be awaited (preferred if possible):**
        # For now, let's assume it is synchronous based on the signature read
        # but log a warning. The AsyncWorker should handle the blocking.
        logger.warning("Calling synchronous generate_completion from async function. Ensure it runs in a thread (e.g., via AsyncWorker).")
        response_text = llm_service.generate_completion(model=model_id, messages=messages)


        if not response_text:
            logger.error("Received empty response from LLM for monster generation.")
            return None

        logger.info("Received response from LLM, attempting to parse JSON.")
        monster_data = _parse_llm_json_output(response_text)

        if monster_data:
            logger.info("Successfully parsed JSON from LLM response.")
            # Add default source if missing
            monster_data['source'] = monster_data.get('source', 'LLM Generated')
            monster_data['is_custom'] = True # Mark as custom/generated
            monster = Monster.from_dict(monster_data)
            logger.info(f"Successfully created Monster object: {monster.name}")
            return monster
        else:
            logger.error("Failed to parse monster data JSON from LLM response.")
            return None

    except Exception as e:
        logger.error(f"Error during LLM monster generation: {e}", exc_info=True)
        return None


async def extract_monster_from_text(llm_service: LLMService, user_text: str) -> Optional[Monster]:
    """
    Uses the LLM service to extract a monster stat block from unstructured text.

    Args:
        llm_service: An instance of the LLMService.
        user_text: The text containing the monster stat block.

    Returns:
        A Monster object if extraction and parsing are successful, otherwise None.
    """
    if not user_text:
        logger.warning("extract_monster_from_text called with empty text.")
        return None

    full_prompt = EXTRACTION_PROMPT_TEMPLATE.format(user_text_placeholder=user_text)

    # Get the current model ID (similar logic as above)
    try:
        model_id = llm_service.app_state.get_setting("selected_llm_model", ModelInfo.OPENAI_GPT4O_MINI)
        if not model_id:
            model_id = ModelInfo.OPENAI_GPT4O_MINI
            logger.warning(f"No LLM model selected in settings, defaulting to {model_id}")
    except AttributeError:
        logger.error("LLMService does not have access to app_state or get_setting. Cannot determine model.")
        model_id = ModelInfo.OPENAI_GPT4O_MINI
        logger.warning(f"Defaulting to {model_id} due to app_state access issue.")

    # Format the prompt as messages list
    messages = [{"role": "user", "content": full_prompt}]

    try:
        logger.info(f"Sending extraction prompt to LLM ({model_id}).")
        
        # Call the correct method: generate_completion (assuming sync as above)
        logger.warning("Calling synchronous generate_completion from async function. Ensure it runs in a thread (e.g., via AsyncWorker).")
        response_text = llm_service.generate_completion(model=model_id, messages=messages)

        if not response_text:
            logger.error("Received empty response from LLM for monster extraction.")
            return None

        logger.info("Received response from LLM, attempting to parse JSON.")
        monster_data = _parse_llm_json_output(response_text)

        if monster_data:
            logger.info("Successfully parsed JSON from LLM response.")
             # Add default source if missing
            monster_data['source'] = monster_data.get('source', 'LLM Extracted')
            monster_data['is_custom'] = True # Mark as custom/extracted
            monster = Monster.from_dict(monster_data)
            logger.info(f"Successfully created Monster object from extraction: {monster.name}")
            return monster
        else:
            logger.error("Failed to parse monster data JSON from LLM response for extraction.")
            return None

    except Exception as e:
        logger.error(f"Error during LLM monster extraction: {e}", exc_info=True)
        return None 