"""
Unit tests for the improved combat resolver.
"""

import unittest
from unittest.mock import MagicMock, patch
from app.core.improved_combat_resolver import ImprovedCombatResolver

class TestImprovedCombatResolver(unittest.TestCase):
    """Test cases for the ImprovedCombatResolver class"""
    
    def setUp(self):
        """Set up test data"""
        # Create a mock LLM service
        self.mock_llm_service = MagicMock()
        
        # Set up a basic LLM response
        self.mock_llm_service.generate_completion.return_value = """
{
  "action": "The Fighter attacks the Goblin with a longsword.",
  "narrative": "The Fighter swings their longsword at the Goblin, striking it for 8 damage. The Goblin is wounded but still standing.",
  "updates": [
    {
      "name": "Goblin",
      "hp": 5
    }
  ]
}
"""
        
        # Create a simple dice roller function
        self.dice_roller = MagicMock(return_value=15)
        
        # Create the improved combat resolver
        self.resolver = ImprovedCombatResolver(self.mock_llm_service)
        
        # Create a basic combat state
        self.combat_state = {
            "round": 1,
            "combatants": [
                {
                    "name": "Fighter",
                    "type": "character",
                    "hp": 40,
                    "max_hp": 40,
                    "initiative": 15,
                    "dexterity": 14,
                    "ac": 18
                },
                {
                    "name": "Goblin",
                    "type": "monster",
                    "hp": 13,
                    "max_hp": 13,
                    "initiative": 10,
                    "dexterity": 14,
                    "ac": 15
                }
            ]
        }
        
        # Set up a mock UI callback
        self.mock_ui_callback = MagicMock()
    
    @patch('threading.Thread')
    def test_resolve_combat_initialization(self, mock_thread):
        """Test that combat resolution initializes correctly with improved initiative"""
        # Setup the mock thread to execute the target function immediately
        mock_thread.side_effect = lambda target, **kwargs: target()
        
        # Mock the _process_combat_with_improved_initiative method
        self.resolver._process_combat_with_improved_initiative = MagicMock()
        
        # Call the resolver
        self.resolver.resolve_combat_turn_by_turn(
            self.combat_state,
            self.dice_roller,
            None,  # callback is deprecated
            self.mock_ui_callback
        )
        
        # Verify _process_combat_with_improved_initiative was called
        self.resolver._process_combat_with_improved_initiative.assert_called_once()
        
        # Check the state passed to _process_combat_with_improved_initiative
        args, _ = self.resolver._process_combat_with_improved_initiative.call_args
        enhanced_state = args[0]
        
        # Verify combat state was enhanced with initiative information
        self.assertIn("initiative_order", enhanced_state)
        self.assertIn("active_combatants", enhanced_state)
        self.assertIn("surprise_status", enhanced_state)
        
        # Check initiative order is as expected
        self.assertEqual(len(enhanced_state["initiative_order"]), 2)
        # Fighter should go first with higher initiative
        self.assertEqual(enhanced_state["initiative_order"][0], 0)
    
    def test_process_death_save(self):
        """Test death save processing for unconscious characters"""
        # Create an unconscious character
        unconscious_character = {
            "name": "Downed Fighter",
            "type": "character",
            "hp": 0,
            "max_hp": 40,
            "status": "unconscious"
        }
        
        # Set up the original combat resolver's _process_death_save method to simulate a death save
        def mock_process_death_save(combatant):
            # Simulate a successful death save
            if "death_saves" not in combatant:
                combatant["death_saves"] = {"successes": 0, "failures": 0}
            combatant["death_saves"]["successes"] += 1
        
        self.resolver.combat_resolver._process_death_save = mock_process_death_save
        
        # Mock time.sleep to avoid delays in tests
        with patch('time.sleep'):
            # Process a death save
            log = []
            state = {"combatants": [unconscious_character]}
            
            self.resolver._process_death_save(
                unconscious_character, 
                state, 
                0,  # combatant index
                1,  # round number
                log,
                self.mock_ui_callback
            )
            
            # Verify death save was processed
            self.assertEqual(unconscious_character["death_saves"]["successes"], 1)
            
            # Verify log entry was created
            self.assertEqual(len(log), 1)
            self.assertEqual(log[0]["action"], "Makes a death saving throw")
            
            # Verify UI was updated
            self.mock_ui_callback.assert_called_once()
    
    def test_apply_combatant_updates(self):
        """Test applying updates to combatants"""
        # Create a state with combatants
        state = {
            "combatants": [
                {
                    "name": "Fighter",
                    "type": "character",
                    "hp": 40,
                    "max_hp": 40
                },
                {
                    "name": "Goblin",
                    "type": "monster",
                    "hp": 13,
                    "max_hp": 13
                }
            ]
        }
        
        # Create updates
        updates = [
            {
                "name": "Goblin",
                "hp": 5,
                "status": "Wounded"
            }
        ]
        
        # Apply updates
        self.resolver._apply_combatant_updates(state, updates)
        
        # Verify updates were applied
        self.assertEqual(state["combatants"][1]["hp"], 5)
        self.assertEqual(state["combatants"][1]["status"], "Wounded")
        
        # Test update that would bring HP to 0
        updates = [
            {
                "name": "Goblin",
                "hp": 0
            }
        ]
        
        # Apply updates
        self.resolver._apply_combatant_updates(state, updates)
        
        # Verify monster was marked as dead
        self.assertEqual(state["combatants"][1]["hp"], 0)
        self.assertEqual(state["combatants"][1]["status"], "Dead")
        
        # Test update that would bring character to 0
        updates = [
            {
                "name": "Fighter",
                "hp": 0
            }
        ]
        
        # Apply updates
        self.resolver._apply_combatant_updates(state, updates)
        
        # Verify character was marked as unconscious and death saves initialized
        self.assertEqual(state["combatants"][0]["hp"], 0)
        self.assertEqual(state["combatants"][0]["status"], "Unconscious")
        self.assertIn("death_saves", state["combatants"][0])
        self.assertEqual(state["combatants"][0]["death_saves"]["successes"], 0)
        self.assertEqual(state["combatants"][0]["death_saves"]["failures"], 0)
        
        # Test update for condition
        updates = [
            {
                "name": "Fighter",
                "conditions": {
                    "stunned": {
                        "duration": 1,
                        "source": "Stunning Strike"
                    }
                }
            }
        ]
        
        # Apply updates
        self.resolver._apply_combatant_updates(state, updates)
        
        # Verify condition was applied
        self.assertIn("conditions", state["combatants"][0])
        self.assertIn("stunned", state["combatants"][0]["conditions"])
        self.assertEqual(state["combatants"][0]["conditions"]["stunned"]["duration"], 1)
    
    def test_should_end_combat(self):
        """Test end of combat detection logic"""
        # Case 1: Combat continues with monsters and characters
        state = {
            "combatants": [
                {
                    "name": "Fighter",
                    "type": "character",
                    "hp": 40,
                    "status": "OK"
                },
                {
                    "name": "Goblin",
                    "type": "monster",
                    "hp": 5,
                    "status": "OK"
                }
            ]
        }
        
        self.assertFalse(self.resolver._should_end_combat(state))
        
        # Case 2: All monsters defeated
        state = {
            "combatants": [
                {
                    "name": "Fighter",
                    "type": "character",
                    "hp": 40,
                    "status": "OK"
                },
                {
                    "name": "Goblin",
                    "type": "monster",
                    "hp": 0,
                    "status": "Dead"
                }
            ]
        }
        
        self.assertTrue(self.resolver._should_end_combat(state))
        
        # Case 3: All characters defeated
        state = {
            "combatants": [
                {
                    "name": "Fighter",
                    "type": "character",
                    "hp": 0,
                    "status": "Dead"
                },
                {
                    "name": "Goblin",
                    "type": "monster",
                    "hp": 5,
                    "status": "OK"
                }
            ]
        }
        
        self.assertTrue(self.resolver._should_end_combat(state))
        
        # Case 4: Characters are unconscious but not dead (combat continues)
        state = {
            "combatants": [
                {
                    "name": "Fighter",
                    "type": "character",
                    "hp": 0,
                    "status": "Unconscious"
                },
                {
                    "name": "Goblin",
                    "type": "monster",
                    "hp": 5,
                    "status": "OK"
                }
            ]
        }
        
        self.assertFalse(self.resolver._should_end_combat(state))
        
        # Case 5: No combatants left
        state = {
            "combatants": []
        }
        
        self.assertTrue(self.resolver._should_end_combat(state))

if __name__ == '__main__':
    unittest.main() 