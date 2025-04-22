"""
Action Economy Module for D&D 5e Combat System

This module handles tracking and management of the D&D 5e action economy system,
including actions, bonus actions, reactions and movement during combat.
"""

from typing import Dict, Any, Optional, List, Tuple
from enum import Enum, auto


class ActionType(Enum):
    """Types of actions in D&D 5e"""
    ACTION = auto()
    BONUS_ACTION = auto()
    REACTION = auto()
    MOVEMENT = auto()
    FREE_ACTION = auto()  # For object interactions, talking, etc.
    LEGENDARY_ACTION = auto()
    LAIR_ACTION = auto()


class ActionEconomyManager:
    """Manages the action economy for combatants"""
    
    @staticmethod
    def initialize_action_economy(combatant: Dict[str, Any]) -> Dict[str, Any]:
        """
        Initialize action economy for a combatant or reset it at the start of their turn
        
        Args:
            combatant: The combatant to initialize action economy for
            
        Returns:
            The updated combatant with initialized action economy
        """
        # Get base speed from combatant stats
        base_speed = combatant.get("speed", 30)
        
        # Initialize action economy dict if not present
        if "action_economy" not in combatant:
            combatant["action_economy"] = {}
        
        # Reset action economy for a new turn
        combatant["action_economy"] = {
            "action": True,
            "bonus_action": True,
            "reaction": True,
            "movement": base_speed,
            "movement_used": 0,
            "free_actions": 1,  # Typically one free object interaction per turn
            "legendary_actions": combatant.get("legendary_actions", 0),
            "legendary_actions_used": 0
        }
        
        # Handle legendary actions that might be a list instead of an integer
        if isinstance(combatant["action_economy"]["legendary_actions"], list):
            combatant["action_economy"]["legendary_actions"] = len(combatant["action_economy"]["legendary_actions"])
        elif not isinstance(combatant["action_economy"]["legendary_actions"], int):
            combatant["action_economy"]["legendary_actions"] = 0
        
        return combatant
    
    @staticmethod
    def use_action(combatant: Dict[str, Any], action_type: ActionType, 
                  resource_cost: int = 1) -> Tuple[Dict[str, Any], bool]:
        """
        Use an action, checking if it's available and marking it as used
        
        Args:
            combatant: The combatant using the action
            action_type: The type of action being used
            resource_cost: For movement, the amount of movement used
                          For legendary actions, the cost in legendary actions
                          
        Returns:
            Tuple of (updated combatant, success)
        """
        if "action_economy" not in combatant:
            combatant = ActionEconomyManager.initialize_action_economy(combatant)
        
        success = False
        
        if action_type == ActionType.ACTION:
            if combatant["action_economy"].get("action", False):
                combatant["action_economy"]["action"] = False
                success = True
                
        elif action_type == ActionType.BONUS_ACTION:
            if combatant["action_economy"].get("bonus_action", False):
                combatant["action_economy"]["bonus_action"] = False
                success = True
                
        elif action_type == ActionType.REACTION:
            if combatant["action_economy"].get("reaction", False):
                combatant["action_economy"]["reaction"] = False
                success = True
                
        elif action_type == ActionType.MOVEMENT:
            available_movement = combatant["action_economy"].get("movement", 0)
            movement_used = combatant["action_economy"].get("movement_used", 0)
            
            if movement_used + resource_cost <= available_movement:
                combatant["action_economy"]["movement_used"] = movement_used + resource_cost
                success = True
                
        elif action_type == ActionType.FREE_ACTION:
            free_actions = combatant["action_economy"].get("free_actions", 0)
            if free_actions > 0:
                combatant["action_economy"]["free_actions"] = free_actions - 1
                success = True
                
        elif action_type == ActionType.LEGENDARY_ACTION:
            legendary_actions = combatant["action_economy"].get("legendary_actions", 0) or 0
            legendary_actions_used = combatant["action_economy"].get("legendary_actions_used", 0) or 0
            
            # Handle legendary actions that might be a list
            if isinstance(legendary_actions, list):
                legendary_actions = len(legendary_actions)
            elif not isinstance(legendary_actions, int):
                legendary_actions = 0
                
            # Ensure legendary_actions_used is an integer
            if not isinstance(legendary_actions_used, int):
                legendary_actions_used = 0
            
            if legendary_actions - legendary_actions_used >= resource_cost:
                combatant["action_economy"]["legendary_actions_used"] = legendary_actions_used + resource_cost
                success = True
        
        return combatant, success
    
    @staticmethod
    def reset_reactions(combatants: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Reset reactions for all combatants at the start of a new round
        
        Args:
            combatants: List of all combatants
            
        Returns:
            Updated list of combatants
        """
        for i, combatant in enumerate(combatants):
            if "action_economy" in combatant:
                combatant["action_economy"]["reaction"] = True
                combatants[i] = combatant
        
        return combatants
    
    @staticmethod
    def reset_legendary_actions(combatants: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Reset legendary actions for legendary creatures at the start of their turn
        
        Args:
            combatants: List of all combatants
            
        Returns:
            Updated list of combatants
        """
        for i, combatant in enumerate(combatants):
            legendary_actions = combatant.get("legendary_actions", 0)
            
            # Handle case when legendary_actions is a list
            if isinstance(legendary_actions, list):
                has_legendary = len(legendary_actions) > 0
            else:
                has_legendary = legendary_actions > 0
                
            if has_legendary and "action_economy" in combatant:
                combatant["action_economy"]["legendary_actions_used"] = 0
                combatants[i] = combatant
        
        return combatants
    
    @staticmethod
    def check_available_actions(combatant: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check which actions are available to a combatant
        
        Args:
            combatant: The combatant to check
            
        Returns:
            Dictionary of available action types and resources
        """
        if "action_economy" not in combatant:
            combatant = ActionEconomyManager.initialize_action_economy(combatant)
        
        action_economy = combatant["action_economy"]
        
        # Check for conditions that prevent actions
        can_take_actions = combatant.get("can_take_actions", True)
        can_take_reactions = combatant.get("can_take_reactions", True) 
        
        # Get legendary actions safely with default values to prevent None subtraction
        legendary_actions = action_economy.get("legendary_actions", 0) or 0
        legendary_actions_used = action_economy.get("legendary_actions_used", 0) or 0
        
        # Handle case when legendary_actions is a list (containing actions) instead of an integer
        if isinstance(legendary_actions, list):
            # If it's a list, count the number of actions available
            legendary_actions = len(legendary_actions)
        elif not isinstance(legendary_actions, int):
            # If it's neither a list nor an int, default to 0
            legendary_actions = 0
            
        # Ensure legendary_actions_used is an integer
        if not isinstance(legendary_actions_used, int):
            legendary_actions_used = 0
        
        return {
            "action": action_economy.get("action", False) and can_take_actions,
            "bonus_action": action_economy.get("bonus_action", False) and can_take_actions,
            "reaction": action_economy.get("reaction", False) and can_take_reactions,
            "movement": action_economy.get("movement", 0) - action_economy.get("movement_used", 0),
            "free_actions": action_economy.get("free_actions", 0),
            "legendary_actions": legendary_actions - legendary_actions_used
        }
    
    @staticmethod
    def process_action_decision(combatant: Dict[str, Any], 
                               decision: Dict[str, Any]) -> Tuple[Dict[str, Any], bool, str]:
        """
        Process a combat decision and apply it to the action economy
        
        Args:
            combatant: The combatant taking the action
            decision: The decision object with action details
            
        Returns:
            Tuple of (updated combatant, success, failure reason)
        """
        # Ensure action economy is initialized
        if "action_economy" not in combatant:
            combatant = ActionEconomyManager.initialize_action_economy(combatant)
        
        # Check if decision includes action economy information
        if "action_type" not in decision:
            # Default to standard action if not specified
            decision["action_type"] = "action"
        
        # Map string action types to enum
        action_type_map = {
            "action": ActionType.ACTION,
            "bonus_action": ActionType.BONUS_ACTION,
            "reaction": ActionType.REACTION,
            "movement": ActionType.MOVEMENT,
            "free_action": ActionType.FREE_ACTION,
            "legendary_action": ActionType.LEGENDARY_ACTION,
            "lair_action": ActionType.LAIR_ACTION
        }
        
        action_type = action_type_map.get(decision["action_type"].lower(), ActionType.ACTION)
        
        # Get resource cost if applicable
        resource_cost = 1
        if action_type == ActionType.MOVEMENT:
            resource_cost = decision.get("movement_cost", 5)
        elif action_type == ActionType.LEGENDARY_ACTION:
            resource_cost = decision.get("legendary_action_cost", 1)
        
        # Try to use the action
        combatant, success = ActionEconomyManager.use_action(
            combatant, action_type, resource_cost
        )
        
        if not success:
            # Determine reason for failure
            if action_type == ActionType.ACTION:
                reason = "Already used action this turn"
            elif action_type == ActionType.BONUS_ACTION:
                reason = "Already used bonus action this turn"
            elif action_type == ActionType.REACTION:
                reason = "Already used reaction this round"
            elif action_type == ActionType.MOVEMENT:
                reason = f"Not enough movement remaining (need {resource_cost}ft, has {combatant['action_economy']['movement'] - combatant['action_economy']['movement_used']}ft)"
            elif action_type == ActionType.LEGENDARY_ACTION:
                reason = "Not enough legendary actions remaining"
            else:
                reason = "Action unavailable"
                
            return combatant, False, reason
        
        return combatant, True, ""
        
    @staticmethod
    def check_opportunity_attacks(moving_combatant: Dict[str, Any], 
                                  combatants: List[Dict[str, Any]], 
                                  previous_position: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Check if a combatant's movement provokes opportunity attacks and process them
        
        Args:
            moving_combatant: The combatant that is moving
            combatants: All combatants in the encounter
            previous_position: The combatant's position before movement (optional)
            
        Returns:
            List of opportunity attack results
        """
        opportunity_attacks = []
        
        # If no previous position provided, we can't determine if movement provokes
        if not previous_position:
            return opportunity_attacks
            
        current_position = moving_combatant.get("position", {})
        
        # Find all enemies that might be able to make opportunity attacks
        for potential_attacker in combatants:
            # Skip if it's the same combatant or same type (allies)
            if potential_attacker.get("name") == moving_combatant.get("name"):
                continue
                
            if potential_attacker.get("type") == moving_combatant.get("type"):
                continue
                
            # Skip if attacker can't take reactions (dead, unconscious, etc.)
            if not potential_attacker.get("can_take_reactions", True):
                continue
                
            if potential_attacker.get("hp", 0) <= 0:
                continue
                
            # Check if the attacker has a reaction available
            if not ActionEconomyManager.check_available_actions(potential_attacker).get("reaction", False):
                continue
                
            # Check if the moving combatant was previously within melee range
            was_in_range = False
            previous_distance = previous_position.get("distance_to", {}).get(potential_attacker.get("name"), 100)
            current_distance = current_position.get("distance_to", {}).get(potential_attacker.get("name"), 100)
            
            # Consider melee range to be 5 feet by default, but allow for reach weapons
            attacker_reach = potential_attacker.get("reach", 5)
            
            if previous_distance <= attacker_reach and current_distance > attacker_reach:
                was_in_range = True
                
            # If the combatant moved out of melee range, trigger opportunity attack
            if was_in_range:
                # Use the reaction
                potential_attacker, success = ActionEconomyManager.use_action(
                    potential_attacker, ActionType.REACTION
                )
                
                if success:
                    # Record the opportunity attack result for processing
                    opportunity_attack = {
                        "attacker": potential_attacker["name"],
                        "target": moving_combatant["name"],
                        "type": "opportunity_attack",
                        "narrative": f"{potential_attacker['name']} makes an opportunity attack against {moving_combatant['name']}!"
                    }
                    opportunity_attacks.append(opportunity_attack)
                    
        return opportunity_attacks 