"""
Condition Resolver for D&D 5e Combat System

This module handles the application and resolution of conditions during combat.
It serves as the integration layer between the conditions module and the combat resolver.
"""

from typing import Dict, List, Any, Tuple, Optional
from app.combat.conditions import (
    ConditionManager, ConditionType, DurationType,
    apply_blinded, apply_charmed, apply_frightened, 
    apply_paralyzed, apply_stunned, apply_exhaustion
)


class ConditionResolver:
    """
    Handles condition resolution during combat encounters.
    Acts as an interface between the combat resolver and the condition system.
    """
    
    @staticmethod
    def resolve_start_of_turn(combatant: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Process all condition effects that trigger at the start of a combatant's turn
        
        Args:
            combatant: The combatant whose turn is starting
            
        Returns:
            Tuple of (updated combatant, list of effects that occurred)
        """
        # Process standard condition effects
        combatant, effects = ConditionManager.process_start_of_turn(combatant)
        
        # Apply condition mechanical effects to stats
        combatant = ConditionManager.apply_condition_effects(combatant)
        
        return combatant, effects
    
    @staticmethod
    def resolve_end_of_turn(combatant: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Process all condition effects that trigger at the end of a combatant's turn
        
        Args:
            combatant: The combatant whose turn is ending
            
        Returns:
            Tuple of (updated combatant, list of effects that occurred)
        """
        return ConditionManager.process_end_of_turn(combatant)
    
    @staticmethod
    def resolve_round_end(combatants: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Process condition effects that trigger at the end of a combat round
        
        Args:
            combatants: List of all combatants
            
        Returns:
            Updated list of combatants
        """
        updated_combatants = []
        
        for combatant in combatants:
            if "conditions" not in combatant:
                updated_combatants.append(combatant)
                continue
                
            conditions_to_remove = []
            
            # Check each condition for round-based duration
            for condition_name, condition_data in combatant["conditions"].items():
                from app.combat.conditions import Condition
                condition = Condition.from_dict(condition_data)
                
                if condition.duration_type == DurationType.ROUNDS:
                    if condition.decrement_duration():
                        conditions_to_remove.append(condition.condition_type)
            
            # Remove expired conditions
            for condition_type in conditions_to_remove:
                combatant = ConditionManager.remove_condition(combatant, condition_type)
            
            updated_combatants.append(combatant)
        
        return updated_combatants
    
    @staticmethod
    def check_can_take_action(combatant: Dict[str, Any]) -> bool:
        """
        Check if a combatant can take an action based on their conditions
        
        Args:
            combatant: The combatant to check
            
        Returns:
            True if the combatant can take an action, False otherwise
        """
        # Apply condition effects to ensure up-to-date stats
        combatant = ConditionManager.apply_condition_effects(combatant)
        
        # Check if explicitly prevented from taking actions
        if not combatant.get("can_take_actions", True):
            return False
        
        # Specific condition checks that prevent actions
        incapacitating_conditions = [
            ConditionType.INCAPACITATED,
            ConditionType.PARALYZED,
            ConditionType.PETRIFIED,
            ConditionType.STUNNED,
            ConditionType.UNCONSCIOUS
        ]
        
        for condition in incapacitating_conditions:
            if ConditionManager.has_condition(combatant, condition):
                return False
        
        return True
    
    @staticmethod
    def check_can_take_reaction(combatant: Dict[str, Any]) -> bool:
        """
        Check if a combatant can take a reaction based on their conditions
        
        Args:
            combatant: The combatant to check
            
        Returns:
            True if the combatant can take a reaction, False otherwise
        """
        # Apply condition effects to ensure up-to-date stats
        combatant = ConditionManager.apply_condition_effects(combatant)
        
        # Check if explicitly prevented from taking reactions
        if not combatant.get("can_take_reactions", True):
            return False
        
        # Specific condition checks that prevent reactions
        reaction_preventing_conditions = [
            ConditionType.INCAPACITATED,
            ConditionType.PARALYZED,
            ConditionType.PETRIFIED,
            ConditionType.STUNNED,
            ConditionType.UNCONSCIOUS
        ]
        
        for condition in reaction_preventing_conditions:
            if ConditionManager.has_condition(combatant, condition):
                return False
        
        return True
    
    @staticmethod
    def check_can_move(combatant: Dict[str, Any]) -> bool:
        """
        Check if a combatant can move based on their conditions
        
        Args:
            combatant: The combatant to check
            
        Returns:
            True if the combatant can move, False otherwise
        """
        # Apply condition effects to ensure up-to-date stats
        combatant = ConditionManager.apply_condition_effects(combatant)
        
        # Check effective speed
        if combatant.get("effective_speed", 0) <= 0:
            return False
        
        # Specific condition checks that prevent movement
        movement_preventing_conditions = [
            ConditionType.GRAPPLED,
            ConditionType.PARALYZED,
            ConditionType.PETRIFIED,
            ConditionType.RESTRAINED,
            ConditionType.STUNNED,
            ConditionType.UNCONSCIOUS
        ]
        
        for condition in movement_preventing_conditions:
            if ConditionManager.has_condition(combatant, condition):
                return False
        
        # Special check for exhaustion level 5+
        if (ConditionManager.has_condition(combatant, ConditionType.EXHAUSTION) and
            ConditionManager.get_condition_level(combatant, ConditionType.EXHAUSTION) >= 5):
            return False
        
        return True
    
    @staticmethod
    def check_attack_modifiers(attacker: Dict[str, Any], target: Dict[str, Any], 
                              is_melee: bool = True, distance_ft: int = 5) -> Tuple[bool, bool]:
        """
        Check for advantage or disadvantage on an attack based on conditions
        
        Args:
            attacker: The attacking combatant
            target: The target combatant
            is_melee: Whether this is a melee attack
            distance_ft: Distance between attacker and target in feet
            
        Returns:
            Tuple of (has_advantage, has_disadvantage)
        """
        # Apply condition effects to ensure up-to-date stats
        attacker = ConditionManager.apply_condition_effects(attacker)
        target = ConditionManager.apply_condition_effects(target)
        
        has_advantage = False
        has_disadvantage = False
        
        # Attacker conditions
        if ConditionManager.has_condition(attacker, ConditionType.BLINDED):
            has_disadvantage = True
        
        if ConditionManager.has_condition(attacker, ConditionType.INVISIBLE):
            has_advantage = True
        
        if ConditionManager.has_condition(attacker, ConditionType.POISONED):
            has_disadvantage = True
        
        if ConditionManager.has_condition(attacker, ConditionType.PRONE):
            has_disadvantage = True
        
        if ConditionManager.has_condition(attacker, ConditionType.RESTRAINED):
            has_disadvantage = True
            
        # Check exhaustion level 3+
        if (ConditionManager.has_condition(attacker, ConditionType.EXHAUSTION) and 
            ConditionManager.get_condition_level(attacker, ConditionType.EXHAUSTION) >= 3):
            has_disadvantage = True
        
        # Target conditions
        if target.get("grants_advantage", False):
            has_advantage = True
            
        if target.get("grants_disadvantage", False):
            has_disadvantage = True
            
        # Handle special cases for ranged/melee and distance
        if ConditionManager.has_condition(target, ConditionType.PRONE):
            if is_melee and distance_ft <= 5:
                has_advantage = True
            elif not is_melee:
                has_disadvantage = True
                
        # Check for critical hit granting conditions when in range
        if (ConditionManager.has_condition(target, ConditionType.PARALYZED) or
            ConditionManager.has_condition(target, ConditionType.UNCONSCIOUS)):
            if is_melee and distance_ft <= 5:
                # Auto-crit is handled elsewhere, but we definitely have advantage
                has_advantage = True
        
        return has_advantage, has_disadvantage
    
    @staticmethod
    def check_saving_throw_modifiers(combatant: Dict[str, Any], 
                                    save_ability: str) -> Tuple[bool, bool, bool]:
        """
        Check for advantage, disadvantage, or auto-fail on a saving throw based on conditions
        
        Args:
            combatant: The combatant making the save
            save_ability: The ability used for the save (str, dex, con, int, wis, cha)
            
        Returns:
            Tuple of (has_advantage, has_disadvantage, auto_fail)
        """
        # Apply condition effects to ensure up-to-date stats
        combatant = ConditionManager.apply_condition_effects(combatant)
        
        has_advantage = False
        has_disadvantage = False
        auto_fail = False
        
        # Check for auto-fail conditions
        if save_ability.lower() in ["strength", "dexterity"]:
            auto_fail_conditions = [
                ConditionType.PARALYZED,
                ConditionType.PETRIFIED,
                ConditionType.STUNNED,
                ConditionType.UNCONSCIOUS
            ]
            
            for condition in auto_fail_conditions:
                if ConditionManager.has_condition(combatant, condition):
                    auto_fail = True
                    break
        
        # Check for disadvantage on Dexterity saves
        if save_ability.lower() == "dexterity" and ConditionManager.has_condition(combatant, ConditionType.RESTRAINED):
            has_disadvantage = True
        
        # Check exhaustion level 3+
        if (ConditionManager.has_condition(combatant, ConditionType.EXHAUSTION) and 
            ConditionManager.get_condition_level(combatant, ConditionType.EXHAUSTION) >= 3):
            has_disadvantage = True
        
        return has_advantage, has_disadvantage, auto_fail
    
    @staticmethod
    def resolve_concentration_check(combatant: Dict[str, Any], damage: int) -> Tuple[Dict[str, Any], bool]:
        """
        Resolve a concentration check after taking damage
        
        Args:
            combatant: The combatant concentrating on a spell
            damage: The amount of damage taken
            
        Returns:
            Tuple of (updated combatant, successfully maintained concentration)
        """
        if not ConditionManager.has_condition(combatant, ConditionType.CONCENTRATION):
            return combatant, True
        
        # Calculate DC (10 or half damage, whichever is higher)
        dc = max(10, damage // 2)
        
        # Get Constitution save bonus
        con_save = combatant.get("saves", {}).get("constitution", 0)
        
        # Check for advantage/disadvantage
        has_advantage, has_disadvantage, auto_fail = ConditionResolver.check_saving_throw_modifiers(
            combatant, "constitution"
        )
        
        # Auto-fail
        if auto_fail:
            # Remove concentration condition
            combatant = ConditionManager.remove_condition(combatant, ConditionType.CONCENTRATION)
            return combatant, False
        
        # Simulate the roll (simplified for now)
        # TODO: Implement actual roll with advantage/disadvantage
        # This is a simplified version that uses a fixed value (10) instead of a random roll
        roll = 10  # Simplified
        total = roll + con_save
        
        # Check if concentration is maintained
        if total >= dc:
            return combatant, True
        else:
            # Remove concentration condition
            combatant = ConditionManager.remove_condition(combatant, ConditionType.CONCENTRATION)
            return combatant, False
    
    @staticmethod
    def apply_effect_with_conditions(
        effect_name: str,
        combatant: Dict[str, Any],
        source: str,
        save_dc: Optional[int] = None,
        save_ability: Optional[str] = None,
        duration_type: DurationType = DurationType.PERMANENT,
        duration_value: int = 0,
        custom_effects: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Apply a named effect with appropriate conditions to a combatant
        
        Args:
            effect_name: The name of the effect to apply
            combatant: The combatant to affect
            source: The source of the effect
            save_dc: DC for saves against the effect
            save_ability: Ability used for saves
            duration_type: How the duration is measured
            duration_value: Value for the duration
            custom_effects: Additional custom effects
            
        Returns:
            Dict with the updated combatant
        """
        # Map common effects to their condition implementations
        effect_mappings = {
            "hold_person": lambda: apply_paralyzed(
                combatant, source, duration_type=duration_type, 
                duration_value=duration_value, save_dc=save_dc, 
                save_ability=save_ability
            ),
            "fear": lambda: apply_frightened(
                combatant, source, duration_type=duration_type, 
                duration_value=duration_value, save_dc=save_dc, 
                save_ability=save_ability
            ),
            "blindness": lambda: apply_blinded(
                combatant, source, duration_type=duration_type, 
                duration_value=duration_value, save_dc=save_dc, 
                save_ability=save_ability
            ),
            "charm_person": lambda: apply_charmed(
                combatant, source, duration_type=duration_type, 
                duration_value=duration_value, save_dc=save_dc, 
                save_ability=save_ability
            ),
            "stun": lambda: apply_stunned(
                combatant, source, duration_type=duration_type, 
                duration_value=duration_value, save_dc=save_dc, 
                save_ability=save_ability
            )
        }
        
        # Apply the effect if it's in our mappings
        if effect_name.lower() in effect_mappings:
            return effect_mappings[effect_name.lower()]()
        
        # For unknown effects, return the combatant unchanged
        return combatant 