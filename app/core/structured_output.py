"""
Structured Output Handler for LLM responses.

This module provides utilities for parsing, validating, and repairing
structured outputs (primarily JSON) from LLM responses to ensure robust
handling of potentially malformed responses.
"""

import json
import re
import logging
from typing import Dict, Any, Optional, List, Union, Tuple
from dataclasses import dataclass, field


@dataclass
class ActionSchema:
    """Schema for validating combat action data."""
    action: str
    target: Optional[str] = None
    explanation: Optional[str] = None
    
    # Optional fields for attack actions
    attack_bonus: Optional[int] = None
    damage_dice: Optional[str] = None
    
    # Optional fields for spell actions
    spell_name: Optional[str] = None
    save_dc: Optional[int] = None
    save_ability: Optional[str] = None
    effect: Optional[str] = None
    
    # Optional fields for healing actions
    healing_dice: Optional[str] = None
    
    # Optional fields for movement actions
    position: Optional[str] = None
    
    # Catch-all for any other fields the LLM might include
    additional_fields: Dict[str, Any] = field(default_factory=dict)


class StructuredOutputHandler:
    """
    Handles parsing, validation, and repair of structured outputs from LLMs.
    Specifically designed to work with JSON outputs in combat resolution context.
    """
    
    def __init__(self):
        """Initialize the structured output handler."""
        self.logger = logging.getLogger("StructuredOutputHandler")
    
    def parse_llm_json_response(self, response_text: str, context: str = "") -> Tuple[Dict[str, Any], bool, str]:
        """
        Parse JSON from LLM response, handling common formatting issues.
        
        Args:
            response_text: Raw text response from the LLM
            context: Optional context string for logging
            
        Returns:
            Tuple containing:
            - The parsed JSON data (dict)
            - Success flag (bool)
            - Error message if any (str)
        """
        if not response_text or not isinstance(response_text, str):
            return {}, False, "Empty or invalid response"
            
        # Step 1: Try standard JSON parsing first (fastest path)
        try:
            json_data = json.loads(response_text)
            return json_data, True, ""
        except json.JSONDecodeError:
            pass  # Continue to repair attempts
            
        # Step 2: Extract JSON blocks if present (handling markdown code blocks)
        json_match = re.search(r'```(?:json)?\s*({[\s\S]*?})\s*```', response_text)
        if json_match:
            try:
                json_data = json.loads(json_match.group(1))
                return json_data, True, ""
            except json.JSONDecodeError:
                # Continue to next repair method
                extracted_json = json_match.group(1)
        else:
            # Look for anything that looks like a JSON object
            json_match = re.search(r'({[\s\S]*?})', response_text)
            extracted_json = json_match.group(1) if json_match else response_text
            
        # Step 3: Fix common JSON formatting issues
        repaired_json = self._repair_json(extracted_json)
        
        # Try parsing the repaired JSON
        try:
            json_data = json.loads(repaired_json)
            return json_data, True, "JSON required repair"
        except json.JSONDecodeError as e:
            error_msg = f"Failed to parse JSON after repair: {str(e)}"
            self.logger.error(f"{error_msg} - Context: {context}")
            
            # Last resort: Try to extract key-value pairs using regex
            extracted_data = self._extract_key_values(response_text)
            if extracted_data:
                return extracted_data, True, "Used regex extraction fallback"
            
            return {}, False, error_msg
    
    def _repair_json(self, json_text: str) -> str:
        """
        Attempt to repair common JSON formatting issues.
        
        Args:
            json_text: The potentially malformed JSON text
            
        Returns:
            Repaired JSON text
        """
        # Replace single quotes with double quotes (common LLM mistake)
        json_text = re.sub(r"(?<![\\])(')", r'"', json_text)
        
        # Fix trailing commas in objects and arrays
        json_text = re.sub(r',\s*}', '}', json_text)
        json_text = re.sub(r',\s*\]', ']', json_text)
        
        # Fix missing quotes around property names
        json_text = re.sub(r'([{,]\s*)([a-zA-Z0-9_]+)(\s*:)', r'\1"\2"\3', json_text)
        
        # Replace None/null variations with proper JSON null
        json_text = re.sub(r':\s*None\s*([,}])', r': null\1', json_text)
        json_text = re.sub(r':\s*none\s*([,}])', r': null\1', json_text)
        
        # Fix unquoted strings
        def quote_unquoted_strings(match):
            key = match.group(1)
            value = match.group(2)
            # Don't quote values that look like numbers, booleans or null
            if (re.match(r'^-?\d+(\.\d+)?$', value) or 
                value in ('true', 'false', 'null')):
                return f'"{key}": {value}'
            return f'"{key}": "{value}"'
            
        json_text = re.sub(r'"([^"]+)"\s*:\s*([^",{}\[\]\s][^,{}\[\]]*?)([,}\]])', 
                          lambda m: f'"{m.group(1)}": "{m.group(2)}"{m.group(3)}', 
                          json_text)
        
        return json_text
    
    def _extract_key_values(self, text: str) -> Dict[str, Any]:
        """
        Extract key-value pairs using regex as a last resort.
        
        Args:
            text: The text to extract from
            
        Returns:
            Dictionary of extracted key-value pairs
        """
        result = {}
        
        # Look for patterns like "key: value" or "key = value"
        patterns = [
            r'"?([a-zA-Z0-9_]+)"?\s*:\s*"?([^",{}\[\]\n]+)"?',  # "key": "value" or key: value
            r'"?([a-zA-Z0-9_]+)"?\s*=\s*"?([^",{}\[\]\n]+)"?'   # "key" = "value" or key = value
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text)
            for key, value in matches:
                # Clean up the value
                value = value.strip()
                # Try to convert to appropriate type
                if value.lower() == 'true':
                    result[key] = True
                elif value.lower() == 'false':
                    result[key] = False
                elif value.lower() in ('none', 'null'):
                    result[key] = None
                elif re.match(r'^-?\d+$', value):
                    result[key] = int(value)
                elif re.match(r'^-?\d+\.\d+$', value):
                    result[key] = float(value)
                else:
                    result[key] = value
        
        return result
    
    def validate_action(self, data: Dict[str, Any]) -> Tuple[bool, str, ActionSchema]:
        """
        Validate action data against the schema.
        
        Args:
            data: The parsed JSON data
            
        Returns:
            Tuple containing:
            - Success flag (bool)
            - Error message if any (str)
            - Validated schema object or default object
        """
        # Required fields
        if "action" not in data or not data["action"]:
            return False, "Missing required field: action", ActionSchema(action="Unknown")
        
        # Create schema object from data
        action_obj = ActionSchema(
            action=data.get("action", ""),
            target=data.get("target"),
            explanation=data.get("explanation")
        )
        
        # Add optional fields if present
        for field in ["attack_bonus", "damage_dice", "spell_name", "save_dc", 
                      "save_ability", "effect", "healing_dice", "position"]:
            if field in data:
                setattr(action_obj, field, data[field])
        
        # Add any additional fields to the catch-all
        known_fields = {"action", "target", "explanation", "attack_bonus", "damage_dice", 
                        "spell_name", "save_dc", "save_ability", "effect", 
                        "healing_dice", "position"}
                        
        for key, value in data.items():
            if key not in known_fields:
                action_obj.additional_fields[key] = value
        
        return True, "", action_obj
    
    def create_function_calling_definition(self) -> Dict[str, Any]:
        """
        Create a function calling definition for the LLM to use.
        This can be used with API function calling features.
        
        Returns:
            Function definition compatible with OpenAI function calling
        """
        return {
            "name": "decide_combat_action",
            "description": "Decide on the most appropriate combat action for the current turn.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "The action being taken (e.g. 'Attack with Longsword', 'Cast Fireball', 'Move to flank')"
                    },
                    "target": {
                        "type": "string",
                        "description": "The target of the action, if applicable"
                    },
                    "explanation": {
                        "type": "string",
                        "description": "Brief explanation of the tactical choice"
                    },
                    "attack_bonus": {
                        "type": "integer",
                        "description": "The attack bonus to use (for attacks)"
                    },
                    "damage_dice": {
                        "type": "string",
                        "description": "The damage dice expression (e.g. '2d6+3')"
                    },
                    "spell_name": {
                        "type": "string",
                        "description": "The name of the spell being cast"
                    },
                    "save_dc": {
                        "type": "integer",
                        "description": "The save DC for the spell"
                    },
                    "save_ability": {
                        "type": "string",
                        "description": "The ability used for the saving throw (e.g. 'dex', 'wis')"
                    },
                    "effect": {
                        "type": "string",
                        "description": "Any special effect applied by the action"
                    },
                    "healing_dice": {
                        "type": "string",
                        "description": "The healing dice expression (e.g. '2d8+4')"
                    },
                    "position": {
                        "type": "string",
                        "description": "The position to move to"
                    }
                },
                "required": ["action"]
            }
        }
    
    def create_few_shot_examples(self) -> List[Dict[str, Any]]:
        """
        Create few-shot examples for the LLM to learn from.
        
        Returns:
            List of example action objects
        """
        return [
            {
                "action": "Attack with Greataxe",
                "target": "Orc Warrior",
                "explanation": "The orc is the closest threat and looks weakened.",
                "attack_bonus": 7,
                "damage_dice": "1d12+4"
            },
            {
                "action": "Cast Fireball",
                "target": "Group of goblins",
                "explanation": "The goblins are clustered together, making them vulnerable to area damage.",
                "spell_name": "Fireball",
                "save_dc": 15,
                "save_ability": "dex",
                "damage_dice": "8d6"
            },
            {
                "action": "Move to flank",
                "target": "Hobgoblin Captain",
                "explanation": "Moving to flank the captain will give our rogue advantage on their next attack.",
                "position": "Behind the Hobgoblin Captain"
            },
            {
                "action": "Heal wounded ally",
                "target": "Paladin",
                "explanation": "The paladin is heavily wounded and needs immediate healing.",
                "spell_name": "Cure Wounds",
                "healing_dice": "1d8+4"
            },
            {
                "action": "Dodge",
                "explanation": "Surrounded by multiple enemies, dodging will improve chances of survival until allies can help."
            }
        ]
