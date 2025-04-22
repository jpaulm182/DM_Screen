"""
Unit tests for the initiative integration module.
"""

import unittest
from app.core.initiative_integration import (
    initialize_combat_with_improved_initiative,
    update_combat_state_for_next_round,
    record_ready_action,
    trigger_held_action,
    get_next_combatant
)

class TestInitiativeIntegration(unittest.TestCase):
    """Test cases for the initiative integration module"""
    
    def setUp(self):
        """Set up test data"""
        # Create a basic combat state for testing
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
                    "name": "Wizard",
                    "type": "character",
                    "hp": 25,
                    "max_hp": 25,
                    "initiative": 18,
                    "dexterity": 16,
                    "ac": 14,
                    "has_alert_feat": True  # +5 to initiative from Alert feat
                },
                {
                    "name": "Goblin 1",
                    "type": "monster",
                    "hp": 7,
                    "max_hp": 7,
                    "initiative": 12,
                    "dexterity": 14,
                    "ac": 15,
                    "surprised": True  # Surprised in the first round
                },
                {
                    "name": "Goblin 2",
                    "type": "monster",
                    "hp": 7,
                    "max_hp": 7,
                    "initiative": 10,
                    "dexterity": 14,
                    "ac": 15,
                    "surprised": True  # Surprised in the first round
                }
            ]
        }
    
    def test_initialize_combat(self):
        """Test initializing combat with improved initiative"""
        # Initialize combat
        enhanced_state = initialize_combat_with_improved_initiative(self.combat_state)
        
        # Check that initiative modifiers were applied
        self.assertEqual(enhanced_state["combatants"][1]["initiative"], 23)  # Wizard: 18 + 5 from Alert
        
        # Verify surprise status
        self.assertEqual(len(enhanced_state["surprise_status"]), 4)
        self.assertFalse(enhanced_state["surprise_status"][0])  # Fighter not surprised
        self.assertFalse(enhanced_state["surprise_status"][1])  # Wizard not surprised
        self.assertTrue(enhanced_state["surprise_status"][2])   # Goblin 1 surprised
        self.assertTrue(enhanced_state["surprise_status"][3])   # Goblin 2 surprised
        
        # Check initiative order
        # Expected: Wizard (23) > Fighter (15)
        # Goblins are in the initiative order but surprised
        self.assertEqual(enhanced_state["initiative_order"][0], 1)  # Wizard
        self.assertEqual(enhanced_state["initiative_order"][1], 0)  # Fighter
        self.assertEqual(enhanced_state["initiative_order"][2], 2)  # Goblin 1
        self.assertEqual(enhanced_state["initiative_order"][3], 3)  # Goblin 2
        
        # Check active combatants (only non-surprised in round 1)
        # Only the Wizard and Fighter can act in the first round
        self.assertEqual(len(enhanced_state["active_combatants"]), 2)
        self.assertEqual(enhanced_state["active_combatants"][0], 1)  # Wizard
        self.assertEqual(enhanced_state["active_combatants"][1], 0)  # Fighter
    
    def test_next_round_transition(self):
        """Test transitioning to the next round"""
        # Initialize combat
        enhanced_state = initialize_combat_with_improved_initiative(self.combat_state)
        
        # Update for the next round
        next_round_state = update_combat_state_for_next_round(enhanced_state)
        
        # Check round counter
        self.assertEqual(next_round_state["round"], 2)
        
        # In round 2, all combatants should be active (no longer surprised)
        self.assertEqual(len(next_round_state["active_combatants"]), 4)
        self.assertEqual(next_round_state["active_combatants"][0], 1)  # Wizard
        self.assertEqual(next_round_state["active_combatants"][1], 0)  # Fighter
        self.assertEqual(next_round_state["active_combatants"][2], 2)  # Goblin 1
        self.assertEqual(next_round_state["active_combatants"][3], 3)  # Goblin 2
    
    def test_ready_action(self):
        """Test recording and triggering a ready action"""
        # Initialize combat
        enhanced_state = initialize_combat_with_improved_initiative(self.combat_state)
        
        # Record Fighter readying an action
        ready_state = record_ready_action(
            enhanced_state,
            combatant_idx=0,  # Fighter
            trigger_condition="When a goblin moves",
            trigger_initiative=10  # Trigger after Goblin 2
        )
        
        # Check combat events
        self.assertEqual(len(ready_state["combat_events"]), 1)
        self.assertEqual(ready_state["combat_events"][0]["type"], "ready")
        self.assertEqual(ready_state["combat_events"][0]["combatant_idx"], 0)
        
        # Trigger the Fighter's readied action during Goblin 2's turn
        triggered_state = trigger_held_action(
            ready_state,
            combatant_idx=0,  # Fighter
            current_turn_position=3  # During Goblin 2's turn
        )
        
        # Check combat events
        self.assertEqual(len(triggered_state["combat_events"]), 2)
        self.assertEqual(triggered_state["combat_events"][1]["type"], "held_action_triggered")
        self.assertEqual(triggered_state["combat_events"][1]["combatant_idx"], 0)
        
        # Update for the next round should apply the changes to initiative order
        next_round_state = update_combat_state_for_next_round(triggered_state)
        
        # Events should be cleared for the new round
        self.assertEqual(len(next_round_state["combat_events"]), 0)
    
    def test_get_next_combatant(self):
        """Test getting the next combatant in the initiative order"""
        # Initialize combat
        enhanced_state = initialize_combat_with_improved_initiative(self.combat_state)
        
        # Get first combatant (should be Wizard)
        first_idx, end_of_round = get_next_combatant(enhanced_state)
        self.assertEqual(first_idx, 1)  # Wizard
        self.assertFalse(end_of_round)
        
        # Get next combatant after Wizard (should be Fighter)
        next_idx, end_of_round = get_next_combatant(enhanced_state, 1)
        self.assertEqual(next_idx, 0)  # Fighter
        self.assertFalse(end_of_round)
        
        # Get next combatant after Fighter (should be end of round in round 1)
        next_idx, end_of_round = get_next_combatant(enhanced_state, 0)
        self.assertIsNone(next_idx)
        self.assertTrue(end_of_round)
        
        # For round 2, all combatants are active
        round2_state = update_combat_state_for_next_round(enhanced_state)
        
        # Get next combatant after Fighter in round 2 (should be Goblin 1)
        next_idx, end_of_round = get_next_combatant(round2_state, 0)
        self.assertEqual(next_idx, 2)  # Goblin 1
        self.assertFalse(end_of_round)
        
        # Get next combatant after Goblin 1 (should be Goblin 2)
        next_idx, end_of_round = get_next_combatant(round2_state, 2)
        self.assertEqual(next_idx, 3)  # Goblin 2
        self.assertFalse(end_of_round)
        
        # Get next combatant after Goblin 2 (should be end of round)
        next_idx, end_of_round = get_next_combatant(round2_state, 3)
        self.assertIsNone(next_idx)
        self.assertTrue(end_of_round)
    
    def test_condition_duration(self):
        """Test condition duration tracking between rounds"""
        # Initialize combat
        enhanced_state = initialize_combat_with_improved_initiative(self.combat_state)
        
        # Add a condition to the Fighter that lasts 1 round
        enhanced_state["combatants"][0]["conditions"] = {
            "stunned": {
                "duration": 1,
                "source": "Stunning Strike"
            }
        }
        
        # Update for the next round (condition should expire)
        next_round_state = update_combat_state_for_next_round(enhanced_state)
        
        # Check that the condition was removed
        self.assertNotIn("stunned", next_round_state["combatants"][0].get("conditions", {}))
        
        # Add a condition that lasts 2 rounds
        next_round_state["combatants"][0]["conditions"] = {
            "frightened": {
                "duration": 2,
                "source": "Fear Spell"
            }
        }
        
        # Update for the next round (condition should still be present with duration 1)
        third_round_state = update_combat_state_for_next_round(next_round_state)
        
        # Check that the condition is still present with reduced duration
        self.assertIn("frightened", third_round_state["combatants"][0].get("conditions", {}))
        self.assertEqual(third_round_state["combatants"][0]["conditions"]["frightened"]["duration"], 1)
        
        # Update for another round (condition should expire)
        fourth_round_state = update_combat_state_for_next_round(third_round_state)
        
        # Check that the condition was removed
        self.assertNotIn("frightened", fourth_round_state["combatants"][0].get("conditions", {}))

if __name__ == '__main__':
    unittest.main() 