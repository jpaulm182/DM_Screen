"""
Conditions Module for D&D 5e Combat Resolver

This module defines all official D&D 5e conditions and their mechanical effects.
Each condition includes:
- Description: Rules text describing the condition
- Effects: Programmatic representation of mechanical effects
- Duration handling: Logic for condition removal
- Save handling: Logic for saves that can end conditions
"""

from enum import Enum, auto
from typing import Dict, List, Optional, Any, Tuple


class ConditionType(Enum):
    """Enumeration of all official D&D 5e conditions"""
    BLINDED = auto()
    CHARMED = auto()
    DEAFENED = auto()
    EXHAUSTION = auto()  # Special case with levels 1-6
    FRIGHTENED = auto()
    GRAPPLED = auto()
    INCAPACITATED = auto()
    INVISIBLE = auto()
    PARALYZED = auto()
    PETRIFIED = auto()
    POISONED = auto()
    PRONE = auto()
    RESTRAINED = auto()
    STUNNED = auto()
    UNCONSCIOUS = auto()
    
    # Additional common status effects that aren't official conditions
    CONCENTRATION = auto()
    SURPRISED = auto()
    HEXED = auto()
    BLESSED = auto()
    HUNTER_MARKED = auto()


class DurationType(Enum):
    """Types of condition duration tracking"""
    INSTANTANEOUS = auto()  # One-time effect
    ROUNDS = auto()         # Lasts for X rounds
    MINUTES = auto()        # Lasts for X minutes (10 rounds per minute)
    TURNS = auto()          # Lasts until after X of the affected creature's turns
    PERMANENT = auto()      # Lasts until removed
    SAVE_ENDS = auto()      # Lasts until a successful save
    CONCENTRATION = auto()  # Lasts until concentration ends
    SPECIAL = auto()        # Special duration logic


class Condition:
    """Represents a single instance of a condition affecting a creature"""
    
    def __init__(
        self,
        condition_type: ConditionType,
        source: str,
        duration_type: DurationType = DurationType.PERMANENT,
        duration_value: int = 0,
        save_dc: Optional[int] = None,
        save_ability: Optional[str] = None,
        source_id: Optional[str] = None,
        custom_effects: Optional[Dict[str, Any]] = None,
        level: int = 1  # For exhaustion
    ):
        self.condition_type = condition_type
        self.source = source
        self.source_id = source_id
        self.duration_type = duration_type
        self.duration_value = duration_value
        self.save_dc = save_dc
        self.save_ability = save_ability
        self.custom_effects = custom_effects or {}
        self.level = level if condition_type == ConditionType.EXHAUSTION else 1
        self.remaining_duration = duration_value
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert condition to dictionary representation"""
        return {
            "condition_type": self.condition_type.name,
            "source": self.source,
            "source_id": self.source_id,
            "duration_type": self.duration_type.name,
            "duration_value": self.duration_value,
            "remaining_duration": self.remaining_duration,
            "save_dc": self.save_dc,
            "save_ability": self.save_ability,
            "level": self.level,
            "custom_effects": self.custom_effects
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Condition":
        """Create condition from dictionary representation"""
        return cls(
            condition_type=ConditionType[data["condition_type"]],
            source=data["source"],
            source_id=data.get("source_id"),
            duration_type=DurationType[data["duration_type"]],
            duration_value=data["duration_value"],
            save_dc=data.get("save_dc"),
            save_ability=data.get("save_ability"),
            custom_effects=data.get("custom_effects", {}),
            level=data.get("level", 1)
        )
    
    def decrement_duration(self) -> bool:
        """
        Decrement the remaining duration of this condition
        
        Returns:
            bool: True if condition should be removed, False otherwise
        """
        if self.duration_type in (DurationType.PERMANENT, DurationType.SAVE_ENDS, 
                                DurationType.CONCENTRATION, DurationType.SPECIAL):
            return False
        
        self.remaining_duration -= 1
        return self.remaining_duration <= 0
    
    def process_save(self, save_result: int) -> bool:
        """
        Process a saving throw against this condition
        
        Args:
            save_result: The total result of the saving throw
            
        Returns:
            bool: True if condition should be removed, False otherwise
        """
        if self.duration_type != DurationType.SAVE_ENDS or self.save_dc is None:
            return False
        
        return save_result >= self.save_dc


class ConditionManager:
    """Manages tracking and application of conditions to combatants"""
    
    @staticmethod
    def add_condition(
        combatant: Dict[str, Any],
        condition_type: ConditionType,
        source: str,
        duration_type: DurationType = DurationType.PERMANENT,
        duration_value: int = 0,
        save_dc: Optional[int] = None,
        save_ability: Optional[str] = None,
        source_id: Optional[str] = None,
        custom_effects: Optional[Dict[str, Any]] = None,
        level: int = 1
    ) -> Dict[str, Any]:
        """
        Add a condition to a combatant
        
        Args:
            combatant: The combatant to affect
            condition_type: Type of condition to apply
            source: Source of the condition (spell, ability, etc)
            duration_type: How duration is measured
            duration_value: Value for duration
            save_dc: DC for saves against the condition
            save_ability: Ability used for saves
            source_id: Unique ID for the source (for specific removal)
            custom_effects: Additional custom effects
            level: Level for exhaustion
            
        Returns:
            Dict with the updated combatant
        """
        # Initialize conditions dict if not present
        if "conditions" not in combatant:
            combatant["conditions"] = {}
        
        # Create condition object
        condition = Condition(
            condition_type=condition_type,
            source=source,
            duration_type=duration_type,
            duration_value=duration_value,
            save_dc=save_dc,
            save_ability=save_ability,
            source_id=source_id,
            custom_effects=custom_effects,
            level=level
        )
        
        # Special handling for exhaustion (track level)
        if condition_type == ConditionType.EXHAUSTION:
            if ConditionType.EXHAUSTION.name in combatant["conditions"]:
                # Increment existing exhaustion
                existing = Condition.from_dict(combatant["conditions"][ConditionType.EXHAUSTION.name])
                existing.level = min(6, existing.level + level)
                combatant["conditions"][ConditionType.EXHAUSTION.name] = existing.to_dict()
            else:
                # Add new exhaustion
                combatant["conditions"][ConditionType.EXHAUSTION.name] = condition.to_dict()
        else:
            # Add or replace other conditions
            combatant["conditions"][condition_type.name] = condition.to_dict()
        
        return combatant
    
    @staticmethod
    def remove_condition(
        combatant: Dict[str, Any],
        condition_type: ConditionType,
        source_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Remove a condition from a combatant
        
        Args:
            combatant: The combatant to affect
            condition_type: Type of condition to remove
            source_id: If provided, only remove if source ID matches
            
        Returns:
            Dict with the updated combatant
        """
        if "conditions" not in combatant:
            return combatant
            
        if condition_type.name in combatant["conditions"]:
            # Check if we need to match source_id
            if source_id:
                condition = Condition.from_dict(combatant["conditions"][condition_type.name])
                if condition.source_id == source_id:
                    del combatant["conditions"][condition_type.name]
            else:
                # Remove regardless of source
                del combatant["conditions"][condition_type.name]
        
        return combatant
    
    @staticmethod
    def reduce_exhaustion(combatant: Dict[str, Any], levels: int = 1) -> Dict[str, Any]:
        """
        Reduce exhaustion levels on a combatant
        
        Args:
            combatant: The combatant to affect
            levels: Number of exhaustion levels to reduce
            
        Returns:
            Dict with the updated combatant
        """
        if "conditions" not in combatant:
            return combatant
            
        if ConditionType.EXHAUSTION.name in combatant["conditions"]:
            condition = Condition.from_dict(combatant["conditions"][ConditionType.EXHAUSTION.name])
            condition.level = max(0, condition.level - levels)
            
            if condition.level == 0:
                del combatant["conditions"][ConditionType.EXHAUSTION.name]
            else:
                combatant["conditions"][ConditionType.EXHAUSTION.name] = condition.to_dict()
        
        return combatant
    
    @staticmethod
    def has_condition(combatant: Dict[str, Any], condition_type: ConditionType) -> bool:
        """Check if a combatant has a specific condition"""
        return "conditions" in combatant and condition_type.name in combatant["conditions"]
    
    @staticmethod
    def get_condition_level(combatant: Dict[str, Any], condition_type: ConditionType) -> int:
        """Get the level of a condition (useful for exhaustion)"""
        if not ConditionManager.has_condition(combatant, condition_type):
            return 0
            
        condition = Condition.from_dict(combatant["conditions"][condition_type.name])
        return condition.level
    
    @staticmethod
    def process_start_of_turn(combatant: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Process condition effects at the start of a combatant's turn
        
        Args:
            combatant: The combatant whose turn is starting
            
        Returns:
            Tuple of (updated combatant, list of condition effects)
        """
        if "conditions" not in combatant:
            return combatant, []
            
        effects = []
        conditions_to_remove = []
        
        for condition_name, condition_data in combatant["conditions"].items():
            condition = Condition.from_dict(condition_data)
            
            # Process duration for turn-based conditions
            if condition.duration_type == DurationType.TURNS:
                if condition.decrement_duration():
                    conditions_to_remove.append(condition.condition_type)
                    effects.append({
                        "type": "condition_expired",
                        "condition": condition.condition_type.name,
                        "source": condition.source
                    })
            
            # Apply start-of-turn effects for specific conditions
            if condition.condition_type == ConditionType.POISONED:
                # Some poisons cause damage at start of turn
                if "damage" in condition.custom_effects:
                    damage = condition.custom_effects["damage"]
                    combatant["hp"] = max(0, combatant["hp"] - damage)
                    effects.append({
                        "type": "poison_damage",
                        "condition": condition.condition_type.name,
                        "damage": damage
                    })
        
        # Remove expired conditions
        for condition_type in conditions_to_remove:
            combatant = ConditionManager.remove_condition(combatant, condition_type)
        
        return combatant, effects
    
    @staticmethod
    def process_end_of_turn(combatant: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Process condition effects at the end of a combatant's turn
        
        Args:
            combatant: The combatant whose turn is ending
            
        Returns:
            Tuple of (updated combatant, list of condition effects)
        """
        if "conditions" not in combatant:
            return combatant, []
            
        effects = []
        conditions_to_remove = []
        
        for condition_name, condition_data in combatant["conditions"].items():
            condition = Condition.from_dict(condition_data)
            
            # Process automatic saves at end of turn
            if condition.duration_type == DurationType.SAVE_ENDS and condition.save_ability:
                # TODO: Implement actual save rolling
                save_bonus = combatant.get("saves", {}).get(condition.save_ability.lower(), 0)
                save_result = 10 + save_bonus  # Simplified for now
                
                if condition.process_save(save_result):
                    conditions_to_remove.append(condition.condition_type)
                    effects.append({
                        "type": "condition_saved",
                        "condition": condition.condition_type.name,
                        "save_result": save_result,
                        "save_dc": condition.save_dc
                    })
        
        # Remove conditions that were saved against
        for condition_type in conditions_to_remove:
            combatant = ConditionManager.remove_condition(combatant, condition_type)
        
        return combatant, effects
    
    @staticmethod
    def apply_condition_effects(combatant: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply mechanical effects of conditions to a combatant's statistics
        
        Args:
            combatant: The combatant to process
            
        Returns:
            Dict with the updated combatant stats
        """
        if "conditions" not in combatant:
            return combatant
        
        # Create temporary modified stats
        modified_stats = {
            "attack_advantage": {},
            "attack_disadvantage": {},
            "saving_advantage": {},
            "saving_disadvantage": {},
            "ability_check_advantage": {},
            "ability_check_disadvantage": {},
            "speed_multiplier": 1.0,
            "ac_modifier": 0
        }
        
        # Process each condition's effects
        for condition_name, condition_data in combatant["conditions"].items():
            condition_type = ConditionType[condition_name]
            
            if condition_type == ConditionType.BLINDED:
                # Blinded creatures automatically fail ability checks requiring sight
                # Attack rolls against the creature have advantage
                # The creature's attack rolls have disadvantage
                for target in combatant.get("potential_targets", []):
                    modified_stats["attack_disadvantage"][target] = True
                combatant["grants_advantage"] = True
            
            elif condition_type == ConditionType.CHARMED:
                # A charmed creature can't attack its charmer or target them with harmful abilities
                # The charmer has advantage on ability checks to interact socially with the creature
                # (Implemented in decision-making logic)
                pass
            
            elif condition_type == ConditionType.DEAFENED:
                # A deafened creature automatically fails ability checks requiring hearing
                # (Implemented in ability check resolution)
                pass
            
            elif condition_type == ConditionType.EXHAUSTION:
                # Apply exhaustion effects based on level
                level = ConditionManager.get_condition_level(combatant, ConditionType.EXHAUSTION)
                if level >= 1:
                    # Level 1: Disadvantage on ability checks
                    for ability in ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]:
                        modified_stats["ability_check_disadvantage"][ability] = True
                
                if level >= 2:
                    # Level 2: Speed halved
                    modified_stats["speed_multiplier"] *= 0.5
                
                if level >= 3:
                    # Level 3: Disadvantage on attack rolls and saving throws
                    for target in combatant.get("potential_targets", []):
                        modified_stats["attack_disadvantage"][target] = True
                    for ability in ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]:
                        modified_stats["saving_disadvantage"][ability] = True
                
                if level >= 4:
                    # Level 4: Hit point maximum halved
                    combatant["temp_max_hp_multiplier"] = 0.5
                
                if level >= 5:
                    # Level 5: Speed reduced to 0
                    modified_stats["speed_multiplier"] = 0
                
                if level >= 6:
                    # Level 6: Death
                    combatant["hp"] = 0
                    combatant["status"] = "Dead"
            
            elif condition_type == ConditionType.FRIGHTENED:
                # A frightened creature has disadvantage on ability checks and attack rolls 
                # while the source of its fear is within line of sight
                for ability in ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]:
                    modified_stats["ability_check_disadvantage"][ability] = True
                for target in combatant.get("potential_targets", []):
                    modified_stats["attack_disadvantage"][target] = True
            
            elif condition_type == ConditionType.GRAPPLED:
                # A grappled creature's speed becomes 0
                modified_stats["speed_multiplier"] = 0
            
            elif condition_type == ConditionType.INCAPACITATED:
                # An incapacitated creature can't take actions or reactions
                combatant["can_take_actions"] = False
                combatant["can_take_reactions"] = False
            
            elif condition_type == ConditionType.INVISIBLE:
                # Attack rolls against the creature have disadvantage
                # The creature's attack rolls have advantage
                for target in combatant.get("potential_targets", []):
                    modified_stats["attack_advantage"][target] = True
                combatant["grants_disadvantage"] = True
            
            elif condition_type == ConditionType.PARALYZED:
                # A paralyzed creature is incapacitated and can't move or speak
                # The creature automatically fails Strength and Dexterity saving throws
                # Attack rolls against the creature have advantage
                # Any attack that hits the creature is a critical hit if attacker is within 5 feet
                combatant["can_take_actions"] = False
                combatant["can_take_reactions"] = False
                modified_stats["speed_multiplier"] = 0
                modified_stats["saving_auto_fail"] = ["strength", "dexterity"]
                combatant["grants_advantage"] = True
                combatant["grants_critical"] = 5  # Within 5 feet
            
            elif condition_type == ConditionType.PETRIFIED:
                # A petrified creature is transformed into a solid inanimate substance
                # It is incapacitated, can't move or speak, and is unaware of surroundings
                # Attack rolls against the creature have advantage
                # The creature automatically fails Strength and Dexterity saving throws
                # The creature has resistance to all damage
                # The creature is immune to poison and disease
                combatant["can_take_actions"] = False
                combatant["can_take_reactions"] = False
                modified_stats["speed_multiplier"] = 0
                modified_stats["saving_auto_fail"] = ["strength", "dexterity"]
                combatant["grants_advantage"] = True
                combatant["resistances"] = combatant.get("resistances", []) + ["all"]
                combatant["immunities"] = combatant.get("immunities", []) + ["poison"]
            
            elif condition_type == ConditionType.POISONED:
                # A poisoned creature has disadvantage on attack rolls and ability checks
                for ability in ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]:
                    modified_stats["ability_check_disadvantage"][ability] = True
                for target in combatant.get("potential_targets", []):
                    modified_stats["attack_disadvantage"][target] = True
            
            elif condition_type == ConditionType.PRONE:
                # A prone creature's only movement option is to crawl
                # The creature has disadvantage on attack rolls
                # Attack rolls against the creature have advantage if attacker is within 5 feet
                # Attack rolls against the creature have disadvantage if attacker is farther away
                modified_stats["speed_multiplier"] *= 0.5  # Crawling uses half speed
                for target in combatant.get("potential_targets", []):
                    modified_stats["attack_disadvantage"][target] = True
                combatant["grants_melee_advantage"] = True
                combatant["grants_ranged_disadvantage"] = True
            
            elif condition_type == ConditionType.RESTRAINED:
                # A restrained creature's speed becomes 0
                # Attack rolls against the creature have advantage
                # The creature's attack rolls have disadvantage
                # The creature has disadvantage on Dexterity saving throws
                modified_stats["speed_multiplier"] = 0
                for target in combatant.get("potential_targets", []):
                    modified_stats["attack_disadvantage"][target] = True
                combatant["grants_advantage"] = True
                modified_stats["saving_disadvantage"]["dexterity"] = True
            
            elif condition_type == ConditionType.STUNNED:
                # A stunned creature is incapacitated, can't move, and can speak only falteringly
                # The creature automatically fails Strength and Dexterity saving throws
                # Attack rolls against the creature have advantage
                combatant["can_take_actions"] = False
                combatant["can_take_reactions"] = False
                modified_stats["speed_multiplier"] = 0
                modified_stats["saving_auto_fail"] = ["strength", "dexterity"]
                combatant["grants_advantage"] = True
            
            elif condition_type == ConditionType.UNCONSCIOUS:
                # An unconscious creature is incapacitated, can't move or speak, and is unaware of surroundings
                # The creature drops whatever it's holding and falls prone
                # The creature automatically fails Strength and Dexterity saving throws
                # Attack rolls against the creature have advantage
                # Any attack that hits the creature is a critical hit if attacker is within 5 feet
                combatant["can_take_actions"] = False
                combatant["can_take_reactions"] = False
                modified_stats["speed_multiplier"] = 0
                modified_stats["saving_auto_fail"] = ["strength", "dexterity"]
                combatant["grants_advantage"] = True
                combatant["grants_critical"] = 5  # Within 5 feet
        
        # Apply consolidated modifiers to the combatant
        combatant["modified_stats"] = modified_stats
        
        # Apply speed modifications
        if "speed" in combatant:
            combatant["effective_speed"] = int(combatant["speed"] * modified_stats["speed_multiplier"])
        
        return combatant


# Utility functions for condition application
def apply_blinded(combatant: Dict[str, Any], source: str, **kwargs) -> Dict[str, Any]:
    """Apply the Blinded condition to a combatant"""
    return ConditionManager.add_condition(
        combatant=combatant,
        condition_type=ConditionType.BLINDED,
        source=source,
        **kwargs
    )

def apply_charmed(combatant: Dict[str, Any], source: str, **kwargs) -> Dict[str, Any]:
    """Apply the Charmed condition to a combatant"""
    return ConditionManager.add_condition(
        combatant=combatant,
        condition_type=ConditionType.CHARMED,
        source=source,
        **kwargs
    )

def apply_frightened(combatant: Dict[str, Any], source: str, **kwargs) -> Dict[str, Any]:
    """Apply the Frightened condition to a combatant"""
    return ConditionManager.add_condition(
        combatant=combatant,
        condition_type=ConditionType.FRIGHTENED,
        source=source,
        **kwargs
    )

def apply_paralyzed(combatant: Dict[str, Any], source: str, **kwargs) -> Dict[str, Any]:
    """Apply the Paralyzed condition to a combatant"""
    return ConditionManager.add_condition(
        combatant=combatant,
        condition_type=ConditionType.PARALYZED,
        source=source,
        **kwargs
    )

def apply_stunned(combatant: Dict[str, Any], source: str, **kwargs) -> Dict[str, Any]:
    """Apply the Stunned condition to a combatant"""
    return ConditionManager.add_condition(
        combatant=combatant,
        condition_type=ConditionType.STUNNED,
        source=source,
        **kwargs
    )

def apply_exhaustion(combatant: Dict[str, Any], source: str, level: int = 1, **kwargs) -> Dict[str, Any]:
    """Apply Exhaustion to a combatant"""
    return ConditionManager.add_condition(
        combatant=combatant,
        condition_type=ConditionType.EXHAUSTION,
        source=source,
        level=level,
        **kwargs
    ) 