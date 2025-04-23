"""
Tests for the monster ability validator module.
"""

import unittest
import sys
import os

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.core.utils.monster_ability_validator import (
    extract_ability_names,
    get_canonical_abilities,
    validate_combat_prompt,
    clean_abilities_in_prompt,
    verify_abilities_match_monster
)

class TestMonsterAbilityValidator(unittest.TestCase):
    """Tests for the monster ability validator module."""
    
    def test_extract_ability_names(self):
        """Test extracting ability names from a monster."""
        monster = {
            "name": "Dragon",
            "actions": [
                {"name": "Multiattack", "description": "The dragon makes three attacks."},
                {"name": "Bite", "description": "Melee weapon attack."}
            ],
            "traits": [
                {"name": "Amphibious", "description": "The dragon can breathe air and water."}
            ],
            "abilities": {
                "Fire Breath": {"description": "The dragon exhales fire."}
            }
        }
        
        ability_names = extract_ability_names(monster)
        
        self.assertEqual(len(ability_names), 4)
        self.assertIn("multiattack", ability_names)
        self.assertIn("bite", ability_names)
        self.assertIn("amphibious", ability_names)
        self.assertIn("fire breath", ability_names)
    
    def test_get_canonical_abilities(self):
        """Test getting canonical abilities with caching."""
        monster = {
            "name": "Goblin",
            "actions": [
                {"name": "Scimitar", "description": "Melee weapon attack."}
            ]
        }
        
        abilities1 = get_canonical_abilities("Goblin", monster)
        self.assertEqual(len(abilities1), 1)
        self.assertIn("scimitar", abilities1)
        
        # Test that the cache works by modifying monster and checking it doesn't affect cached result
        monster["actions"].append({"name": "Shortbow", "description": "Ranged weapon attack."})
        abilities2 = get_canonical_abilities("Goblin", monster)
        self.assertEqual(len(abilities2), 1)  # Should still be 1 from cache
        
        # But a new monster should use new data
        new_monster = {
            "name": "Goblin",
            "actions": [
                {"name": "Scimitar", "description": "Melee weapon attack."},
                {"name": "Shortbow", "description": "Ranged weapon attack."}
            ]
        }
        abilities3 = get_canonical_abilities("New Goblin", new_monster)
        self.assertEqual(len(abilities3), 2)
    
    def test_validate_combat_prompt(self):
        """Test validating a combat prompt for ability mixing."""
        # Valid prompt with no mixing
        valid_prompt = """
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
- Multiattack: The dragon makes three attacks. [Dragon_0_ability]
- Bite: Melee weapon attack. [Dragon_0_ability]

## Traits:
- Fire Resistance: The dragon has resistance to fire damage. [Dragon_0_ability]

# NEARBY COMBATANTS
- Goblin (HP: 7/7, AC: 15, Status: )
- Knight (HP: 52/52, AC: 18, Status: )
"""
        
        is_valid, message = validate_combat_prompt(valid_prompt)
        self.assertTrue(is_valid)
        
        # Invalid prompt with ability mixing
        invalid_prompt = """
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
- Multiattack: The dragon makes three attacks. [Dragon_0_ability]
- Bite: Melee weapon attack. [Dragon_0_ability]
- Scimitar: The goblin attacks with its scimitar. [Goblin_1_ability]

## Traits:
- Fire Resistance: The dragon has resistance to fire damage. [Dragon_0_ability]

# NEARBY COMBATANTS
- Goblin (HP: 7/7, AC: 15, Status: )
- Knight (HP: 52/52, AC: 18, Status: )
"""
        
        is_valid, message = validate_combat_prompt(invalid_prompt)
        self.assertFalse(is_valid)
        self.assertIn("Ability mixing detected", message)
        self.assertIn("Scimitar", message)
    
    def test_clean_abilities_in_prompt(self):
        """Test cleaning abilities in a prompt."""
        prompt_without_tags = """
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
- Multiattack: The dragon makes three attacks.
- Bite: Melee weapon attack.

## Traits:
- Fire Resistance: The dragon has resistance to fire damage.

# NEARBY COMBATANTS
- Goblin (HP: 7/7, AC: 15, Status: )
- Knight (HP: 52/52, AC: 18, Status: )
"""
        
        cleaned_prompt = clean_abilities_in_prompt(prompt_without_tags)
        
        self.assertIn("[Dragon_0_ability]", cleaned_prompt)
        self.assertEqual(cleaned_prompt.count("[Dragon_0_ability]"), 3)  # 3 abilities should be tagged
    
    def test_verify_abilities_match_monster(self):
        """Test verifying abilities match a monster."""
        canonical_abilities = {"multiattack", "bite", "fire breath"}
        
        # Valid abilities
        abilities = [
            {"name": "Multiattack", "description": "The dragon makes multiple attacks."},
            {"name": "Bite", "description": "Melee weapon attack."}
        ]
        
        valid_abilities = verify_abilities_match_monster("Dragon", abilities, canonical_abilities)
        self.assertEqual(len(valid_abilities), 2)
        
        # Mixed abilities
        mixed_abilities = [
            {"name": "Multiattack", "description": "The dragon makes multiple attacks."},
            {"name": "Scimitar", "description": "The goblin attacks with its scimitar."}  # Not a dragon ability
        ]
        
        filtered_abilities = verify_abilities_match_monster("Dragon", mixed_abilities, canonical_abilities)
        self.assertEqual(len(filtered_abilities), 1)
        self.assertEqual(filtered_abilities[0]["name"], "Multiattack")

if __name__ == "__main__":
    unittest.main() 