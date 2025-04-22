"""
Unit tests for the improved initiative module.
"""

import unittest
from app.core.improved_initiative import ImprovedInitiative

class TestImprovedInitiative(unittest.TestCase):
    """Test cases for the ImprovedInitiative class"""
    
    def test_sort_combatants_by_initiative(self):
        """Test sorting combatants by initiative with tie-breaking"""
        # Create test combatants
        combatants = [
            {"name": "Fighter", "initiative": 15, "dexterity": 14},
            {"name": "Wizard", "initiative": 15, "dexterity": 12},
            {"name": "Rogue", "initiative": 20, "dexterity": 18},
            {"name": "Cleric", "initiative": 10, "dexterity": 10},
            {"name": "Monk", "initiative": 15, "dexterity": 14, "initiative_advantage": 1}
        ]
        
        # Get sorted initiative order
        initiative_order = ImprovedInitiative.sort_combatants_by_initiative(combatants)
        
        # Expected order: Rogue (20) > Monk (15, DEX 14, advantage) > Fighter (15, DEX 14) > Wizard (15, DEX 12) > Cleric (10)
        expected_order = [2, 4, 0, 1, 3]
        
        self.assertEqual(initiative_order, expected_order)
        
    def test_get_surprise_status(self):
        """Test determining surprise status for combatants"""
        # Create test combatants
        combatants = [
            {"name": "Fighter", "surprised": True},
            {"name": "Wizard", "surprised": False},
            {"name": "Rogue", "surprised": True, "has_alert_feat": True},  # Alert feat prevents surprise
            {"name": "Goblin", "surprised": True}
        ]
        
        # Get surprise status
        surprise_status = ImprovedInitiative.get_surprise_status(combatants)
        
        # Expected status: Fighter (surprised), Wizard (not surprised), Rogue (not surprised due to Alert), Goblin (surprised)
        expected_status = {0: True, 1: False, 2: False, 3: True}
        
        self.assertEqual(surprise_status, expected_status)
        
    def test_apply_initiative_modifiers(self):
        """Test applying initiative modifiers from features and abilities"""
        # Create test combatants
        combatants = [
            {"name": "Fighter", "initiative": 10},
            {"name": "Wizard", "initiative": 12, "has_alert_feat": True},  # +5 from Alert
            {"name": "Bard", "initiative": 14, "has_jack_of_all_trades": True, "proficiency_bonus": 4},  # +2 from Jack of All Trades
            {"name": "Champion", "initiative": 16, "has_remarkable_athlete": True, "proficiency_bonus": 6}  # +3 from Remarkable Athlete
        ]
        
        # Apply modifiers
        modified_combatants = ImprovedInitiative.apply_initiative_modifiers(combatants)
        
        # Check modified initiative values
        self.assertEqual(modified_combatants[0]["initiative"], 10)  # No modifiers
        self.assertEqual(modified_combatants[1]["initiative"], 17)  # +5 from Alert
        self.assertEqual(modified_combatants[2]["initiative"], 16)  # +2 from Jack of All Trades
        self.assertEqual(modified_combatants[3]["initiative"], 19)  # +3 from Remarkable Athlete
        
    def test_determine_active_combatants_no_surprise(self):
        """Test determining active combatants with no surprise"""
        # Create test combatants
        combatants = [
            {"name": "Fighter", "initiative": 15, "type": "character", "hp": 30},
            {"name": "Wizard", "initiative": 12, "type": "character", "hp": 0, "status": "unconscious"},  # Unconscious but can make death saves
            {"name": "Goblin 1", "initiative": 10, "type": "monster", "hp": 7},
            {"name": "Goblin 2", "initiative": 8, "type": "monster", "hp": 0, "status": "dead"}  # Dead, should be excluded
        ]
        
        # Determine active combatants (round 1, no surprise)
        active_combatants = ImprovedInitiative.determine_active_combatants(combatants, 1)
        
        # Expected order: Fighter (15) > Wizard (12, unconscious but makes death saves) > Goblin 1 (10)
        # Goblin 2 is dead and should be excluded
        expected_active = [0, 1, 2]
        
        self.assertEqual(active_combatants, expected_active)
        
    def test_determine_active_combatants_with_surprise(self):
        """Test determining active combatants with surprise in first round"""
        # Create test combatants
        combatants = [
            {"name": "Fighter", "initiative": 18, "type": "character", "hp": 30},
            {"name": "Wizard", "initiative": 15, "type": "character", "hp": 20},
            {"name": "Rogue", "initiative": 20, "type": "character", "hp": 25},
            {"name": "Goblin 1", "initiative": 10, "type": "monster", "hp": 7},
            {"name": "Goblin 2", "initiative": 12, "type": "monster", "hp": 8}
        ]
        
        # Create surprise status: PCs are surprised, monsters are not
        surprise_status = {0: True, 1: True, 2: True, 3: False, 4: False}
        
        # Determine active combatants (round 1, with surprise)
        active_combatants = ImprovedInitiative.determine_active_combatants(combatants, 1, surprise_status)
        
        # Expected order: Only non-surprised combatants can act in first round
        # Goblin 2 (12) > Goblin 1 (10)
        expected_active = [4, 3]
        
        self.assertEqual(active_combatants, expected_active)
        
        # Round 2, everyone can act
        active_combatants_round_2 = ImprovedInitiative.determine_active_combatants(combatants, 2, surprise_status)
        
        # Expected order: Rogue (20) > Fighter (18) > Wizard (15) > Goblin 2 (12) > Goblin 1 (10)
        expected_active_round_2 = [2, 0, 1, 4, 3]
        
        self.assertEqual(active_combatants_round_2, expected_active_round_2)
        
    def test_update_initiative_order_ready_action(self):
        """Test updating initiative order when a combatant readies an action"""
        # Create test combatants
        combatants = [
            {"name": "Fighter", "initiative": 18},
            {"name": "Wizard", "initiative": 15},
            {"name": "Rogue", "initiative": 20},
            {"name": "Goblin", "initiative": 10}
        ]
        
        # Initial initiative order: Rogue (20) > Fighter (18) > Wizard (15) > Goblin (10)
        current_order = [2, 0, 1, 3]
        
        # Fighter readies an action to go after the Goblin
        events = [
            {
                "type": "ready",
                "combatant_idx": 0,  # Fighter
                "trigger_initiative": 5  # Trigger after Goblin
            }
        ]
        
        # Update initiative order
        updated_order = ImprovedInitiative.update_initiative_order(combatants, current_order, events)
        
        # Expected order: Rogue (20) > Wizard (15) > Goblin (10) > Fighter (readied)
        expected_order = [2, 1, 3, 0]
        
        self.assertEqual(updated_order, expected_order)
        
    def test_update_initiative_order_held_action_triggered(self):
        """Test updating initiative order when a held action is triggered"""
        # Create test combatants
        combatants = [
            {"name": "Fighter", "initiative": 18},
            {"name": "Wizard", "initiative": 15},
            {"name": "Rogue", "initiative": 20},
            {"name": "Goblin", "initiative": 10}
        ]
        
        # Current initiative order with Fighter having readied an action
        current_order = [2, 1, 3, 0]
        
        # Fighter's readied action triggers during Goblin's turn (position 2)
        events = [
            {
                "type": "held_action_triggered",
                "combatant_idx": 0,  # Fighter
                "current_position": 2  # Trigger at Goblin's position
            }
        ]
        
        # Update initiative order
        updated_order = ImprovedInitiative.update_initiative_order(combatants, current_order, events)
        
        # Expected order: Rogue (20) > Wizard (15) > Fighter (triggered) > Goblin (10)
        expected_order = [2, 1, 0, 3]
        
        self.assertEqual(updated_order, expected_order)

if __name__ == '__main__':
    unittest.main() 