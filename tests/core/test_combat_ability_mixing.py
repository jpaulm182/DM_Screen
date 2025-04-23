"""
Integration test for the monster ability validation in combat.

This test verifies that the ability mixing prevention system works correctly
in actual combat scenarios.
"""

import unittest
import sys
import os
import json
import re
import logging
from unittest.mock import MagicMock, patch
import pytest

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.core.combat_resolver import CombatResolver
from app.core.utils.monster_ability_validator import (
    validate_combat_prompt,
    clean_abilities_in_prompt,
    fix_mixed_abilities_in_prompt,
    get_canonical_abilities
)
from app.core.llm_service import LLMService
from app.core.combat_resolver_patch import patched_create_decision_prompt
from app.core.improved_combat_resolver import ImprovedCombatResolver

# Disable logging during tests
logging.disable(logging.CRITICAL)

class MockLLMService:
    """Mock LLM service for testing."""
    
    def __init__(self):
        self.requests = []
        
    def generate_completion(self, model, messages, temperature=None, max_tokens=None):
        """Mock completion that just records the request and returns a basic response."""
        content = messages[0]["content"] if messages else ""
        self.requests.append({
            "model": model,
            "content": content
        })
        
        # Extract the monster name from the prompt
        monster_match = re.search(r"Active Combatant: ([A-Za-z0-9_\s]+)", content)
        monster_name = monster_match.group(1) if monster_match else "Unknown"
        
        # Return a simple action JSON
        return json.dumps({
            "action": f"The {monster_name} attacks with its basic attack.",
            "dice_requests": [
                {"expression": "1d20+5", "purpose": "Attack roll"},
                {"expression": "1d8+3", "purpose": "Damage roll"}
            ],
            "action_type": "action",
            "target": "Enemy"
        })
    
    def get_available_models(self):
        """Return a list of mock models."""
        return [{"id": "test-model"}]

class TestCombatAbilityMixing(unittest.TestCase):
    """Tests for the ability mixing prevention system in combat."""
    
    def setUp(self):
        """Set up test case with a mock LLM service."""
        self.llm_service = MockLLMService()
        self.resolver = CombatResolver(self.llm_service)
        
        # Create sample monsters with distinct abilities
        self.dragon = {
            "name": "Dragon",
            "type": "monster",
            "hp": 100,
            "max_hp": 100,
            "ac": 18,
            "initiative": 20,
            "actions": [
                {"name": "Multiattack", "description": "The dragon makes 3 attacks: one with its bite and two with its claws."},
                {"name": "Bite", "description": "Melee Weapon Attack: +10 to hit, reach 5 ft., one target. Hit: 17 (2d10 + 6) piercing damage."},
                {"name": "Claw", "description": "Melee Weapon Attack: +10 to hit, reach 5 ft., one target. Hit: 13 (2d6 + 6) slashing damage."}
            ],
            "traits": [
                {"name": "Fire Breath", "description": "The dragon exhales fire in a 30-foot cone. Each creature in that area must make a DC 16 Dexterity saving throw, taking 55 (10d10) fire damage on a failed save, or half as much damage on a successful one."}
            ]
        }
        
        self.goblin = {
            "name": "Goblin",
            "type": "monster",
            "hp": 7,
            "max_hp": 7,
            "ac": 15,
            "initiative": 10,
            "actions": [
                {"name": "Scimitar", "description": "Melee Weapon Attack: +4 to hit, reach 5 ft., one target. Hit: 5 (1d6 + 2) slashing damage."},
                {"name": "Shortbow", "description": "Ranged Weapon Attack: +4 to hit, range 80/320 ft., one target. Hit: 5 (1d6 + 2) piercing damage."}
            ],
            "traits": [
                {"name": "Nimble Escape", "description": "The goblin can take the Disengage or Hide action as a bonus action on each of its turns."}
            ]
        }
        
        # Create a mixed monster with abilities from both
        self.mixed_monster = {
            "name": "Mixed Monster",
            "type": "monster",
            "hp": 50,
            "max_hp": 50,
            "ac": 16,
            "initiative": 15,
            "actions": [
                {"name": "Multiattack", "description": "The mixed monster makes 2 attacks."},
                {"name": "Bite", "description": "Melee Weapon Attack: +8 to hit, reach 5 ft., one target. Hit: 15 (2d8 + 6) piercing damage."}, # From dragon
                {"name": "Scimitar", "description": "Melee Weapon Attack: +4 to hit, reach 5 ft., one target. Hit: 5 (1d6 + 2) slashing damage."}, # From goblin
                {"name": "Claw", "description": "Melee Weapon Attack: +10 to hit, reach 5 ft., one target. Hit: 13 (2d6 + 6) slashing damage."} # From dragon
            ],
            "traits": [
                {"name": "Fire Breath", "description": "The mixed monster exhales fire."}, # From dragon
                {"name": "Nimble Escape", "description": "The mixed monster can take the Disengage or Hide action as a bonus action."}, # From goblin
                {"name": "Death Burst", "description": "When the mixed monster dies, it explodes in a burst of fire and magma."} # From dragon
            ]
        }
        
    def mock_dice_roller(self, expression):
        """Simple dice roller returning a fixed value."""
        return 15  # A reasonable roll for most dice
    
    def test_validate_prompt_detects_ability_mixing(self):
        """Test that the validator correctly detects ability mixing in a prompt."""
        # Create a combat prompt with mixed abilities
        prompt = f"""
You are the tactical combat AI for a D&D 5e game. You decide actions for Dragon.

# COMBAT SITUATION
Round: 1
Active Combatant: Dragon

# DRAGON DETAILS
HP: 100/100
AC: 18
Type: monster
Status: 

# SPECIFIC ABILITIES, ACTIONS AND TRAITS
## Actions:
- Multiattack: The dragon makes multiple attacks. [Dragon_0_ability]
- Bite: Melee weapon attack. [Dragon_0_ability]
- Scimitar: The goblin attacks with its scimitar. [Goblin_1_ability]

## Traits:
- Fire Breath: The dragon breathes fire. [Dragon_0_ability]

# NEARBY COMBATANTS
- Goblin (HP: 7/7, AC: 15, Status: )
"""
        
        is_valid, message = validate_combat_prompt(prompt)
        self.assertFalse(is_valid)
        self.assertIn("Ability mixing detected", message)
        self.assertIn("Scimitar", message)
    
    def test_combat_turn_prevents_ability_mixing(self):
        """
        Test that the combat resolver correctly prevents ability mixing when 
        processing a monster's turn.
        """
        # Create a combat state with the mixed monster
        combat_state = {
            "round": 1,
            "current_turn_index": 0,
            "combatants": [self.mixed_monster, self.dragon, self.goblin]
        }
        
        # Apply patch to integrate ability validation
        from app.core.combat_resolver_patch import combat_resolver_patch
        
        # Create a mock app_state with the resolver
        app_state = MagicMock()
        app_state.combat_resolver = self.resolver
        
        # Apply the patch
        with patch("app.core.utils.monster_ability_validator.validate_combat_prompt") as mock_validate:
            # Set up the mock to track calls
            mock_validate.return_value = (True, "Valid prompt")
            
            # Apply the patch
            combat_resolver_patch(app_state)
            
            # Process a turn for the mixed monster
            self.resolver._process_turn(combat_state["combatants"], 0, 1, self.mock_dice_roller)
            
            # Verify that validate_combat_prompt was called
            mock_validate.assert_called()
            
            # Verify that the prompt was checked for mixing
            call_args = mock_validate.call_args[0][0]
            self.assertIn("Mixed Monster", call_args)

def test_fix_mixed_abilities_in_prompt():
    """Test the ability to automatically fix mixed abilities in a prompt."""
    # Create a combat prompt with mixed abilities
    mixed_prompt = """
    Combat state:
    - Active monster: Magma Mephit (HP: 22/30)
    - Players: Fighter (HP: 45/50), Wizard (HP: 30/30)
    
    Abilities:
    - Magma Breath: The Magma Mephit exhales a 15-foot cone of hot magma. Each creature in that area must make a DC 12 Dexterity saving throw, taking 4d6 fire damage on a failed save, or half as much damage on a successful one.
    - Skeletal Claws: The Magma Mephit makes a clawing attack with skeletal hands. Melee Weapon Attack: +4 to hit, reach 5 ft., one target. Hit: 5 (1d4 + 3) bludgeoning damage.
    - Bone Barrage: The Magma Mephit flings bones in a 10-foot radius. Each creature in that area must succeed on a DC 12 Dexterity saving throw or take 3d6 bludgeoning damage.
    - Heat Metal: The Magma Mephit heats a metal object. Any creature in contact with the object takes 2d8 fire damage.
    
    What should the Magma Mephit do on its turn?
    """
    
    # Fix the mixed abilities in the prompt
    fixed_prompt = fix_mixed_abilities_in_prompt(mixed_prompt)
    
    # Check that skeletal abilities were removed
    assert "Skeletal Claws" not in fixed_prompt
    assert "Bone Barrage" not in fixed_prompt
    
    # Check that fire-based abilities were preserved
    assert "Magma Breath" in fixed_prompt
    assert "Heat Metal" in fixed_prompt
    
    # Verify that the prompt is still valid
    validation_result = validate_combat_prompt(fixed_prompt)
    assert validation_result["success"] == True

def test_patched_decision_prompt_automatic_correction():
    """Test that the patched create_decision_prompt function automatically corrects mixed abilities."""
    # Create test monster data
    magma_mephit = {
        "name": "Magma Mephit",
        "type": "elemental",
        "actions": [
            {"name": "Magma Breath", "description": "The Magma Mephit exhales a 15-foot cone of hot magma."},
            {"name": "Heat Metal", "description": "The Magma Mephit heats a metal object."},
            {"name": "Claws", "description": "Melee Weapon Attack: +4 to hit, reach 5 ft., one target."}
        ]
    }
    
    skeleton = {
        "name": "Skeleton",
        "type": "undead",
        "actions": [
            {"name": "Skeletal Claws", "description": "The Skeleton makes a clawing attack."},
            {"name": "Bone Barrage", "description": "The Skeleton flings bones in a 10-foot radius."},
            {"name": "Shortsword", "description": "Melee Weapon Attack: +4 to hit, reach 5 ft., one target."}
        ]
    }
    
    # Create a mixed combat state with the wrong abilities in the active monster
    combat_state = {
        "active_monster": {
            "name": "Magma Mephit",
            "type": "elemental",
            "actions": [
                {"name": "Magma Breath", "description": "The Magma Mephit exhales a 15-foot cone of hot magma."},
                {"name": "Skeletal Claws", "description": "The Magma Mephit makes a clawing attack with skeletal hands."},
                {"name": "Bone Barrage", "description": "The Magma Mephit flings bones in a 10-foot radius."}
            ]
        },
        "players": [
            {"name": "Fighter", "hp": 45, "max_hp": 50},
            {"name": "Wizard", "hp": 30, "max_hp": 30}
        ]
    }
    
    # Create a simple combat resolver object to use the patched function
    resolver = ImprovedCombatResolver()
    
    # Use the patched function to create a decision prompt
    prompt = patched_create_decision_prompt(combat_state, resolver)
    
    # Verify that skeletal abilities are not in the prompt
    assert "Skeletal Claws" not in prompt
    assert "Bone Barrage" not in prompt
    
    # Verify that magma abilities are in the prompt
    assert "Magma Breath" in prompt
    
    # Validation should pass for the prompt
    validation_result = validate_combat_prompt(prompt)
    assert validation_result["success"] == True

def test_improved_resolver_combat_preparation():
    """Test that the ImprovedCombatResolver properly prepares combat data by fixing mixed abilities."""
    # Create a combat state with mixed abilities
    combat_state = {
        "combatants": [
            {
                "name": "Magma Mephit",
                "type": "monster",
                "monster_type": "elemental",
                "actions": [
                    {"name": "Magma Breath", "description": "The Magma Mephit exhales a 15-foot cone of hot magma."},
                    {"name": "Skeletal Claws", "description": "The Magma Mephit makes a clawing attack with skeletal hands."},
                    {"name": "Bone Barrage", "description": "The Magma Mephit flings bones in a 10-foot radius."}
                ],
                "traits": [
                    {"name": "Death Burst", "description": "When the Magma Mephit dies, it explodes in a burst of fire and magma."},
                    {"name": "Undead Nature", "description": "The Magma Mephit doesn't require air, food, drink, or sleep."}
                ]
            },
            {
                "name": "Fighter",
                "type": "player",
                "hp": 45,
                "max_hp": 50
            }
        ],
        "active_combatant_index": 0
    }
    
    # Create the resolver
    resolver = ImprovedCombatResolver()
    
    # Prepare the combat data
    cleaned_state = resolver.prepare_combat_data(combat_state)
    
    # Get the magma mephit from the cleaned state
    magma_mephit = cleaned_state["combatants"][0]
    
    # Check that skeletal abilities were removed
    action_names = [action["name"] for action in magma_mephit["actions"]]
    assert "Skeletal Claws" not in action_names
    assert "Bone Barrage" not in action_names
    
    # Check that undead traits were removed
    trait_names = [trait["name"] for trait in magma_mephit["traits"]]
    assert "Undead Nature" not in trait_names
    
    # Check that valid abilities remain
    assert "Magma Breath" in action_names
    assert "Death Burst" in trait_names

if __name__ == "__main__":
    unittest.main() 