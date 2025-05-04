"""
Rules Engine for D&D 5e Combat Resolution.

This module provides a deterministic rules engine that handles the mechanical
execution of combat actions based on high-level intents from an LLM.
It ensures rule compliance for standard actions like attacks, spells,
movement, and status effects.
"""

import logging
import random
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple, Union, Any, Callable


class ActionType(Enum):
    """Enumeration of possible action types in combat."""
    ATTACK = auto()
    SPELL = auto()
    MOVEMENT = auto()
    HEAL = auto()
    BUFF = auto()
    DEBUFF = auto()
    DODGE = auto()
    DASH = auto()
    DISENGAGE = auto()
    HELP = auto()
    HIDE = auto()
    READY = auto()
    OTHER = auto()
    UNKNOWN = auto()


class ActionResult:
    """Container for the result of executing an action."""
    
    def __init__(self):
        self.success = False
        self.damage = 0
        self.healing = 0
        self.effects = []
        self.narrative = ""
        self.details = {}
        self.dice_rolls = []
    
    def add_roll(self, purpose: str, expression: str, result: int):
        """Add a dice roll to the result."""
        self.dice_rolls.append({
            "purpose": purpose,
            "expression": expression,
            "result": result
        })
        return self
    
    def as_dict(self):
        """Convert to dictionary for JSON serialization."""
        return {
            "success": self.success,
            "damage": self.damage,
            "healing": self.healing,
            "effects": self.effects,
            "narrative": self.narrative,
            "details": self.details,
            "dice_rolls": self.dice_rolls
        }


class RulesEngine:
    """
    D&D 5e Rules Engine for executing combat actions.
    
    This engine takes high-level intents from an LLM and executes them
    according to the D&D 5e rules. It handles:
    - Attack rolls and damage calculation
    - Spell casting and effects
    - Movement and positioning
    - Status effects and conditions
    """
    
    def __init__(self, dice_roller: Callable[[str], int]):
        """
        Initialize the rules engine.
        
        Args:
            dice_roller: Function that takes a dice expression (e.g., '1d20+5')
                         and returns the roll result.
        """
        self.dice_roller = dice_roller
        self.logger = logging.getLogger("RulesEngine")
    
    def execute_action(self, action_intent: Dict[str, Any], 
                      active_combatant: Dict[str, Any],
                      all_combatants: List[Dict[str, Any]]) -> ActionResult:
        """
        Execute a combat action based on the intent from the LLM.
        
        Args:
            action_intent: The intent from the LLM (parsed JSON)
            active_combatant: The combatant taking the action
            all_combatants: All combatants in the encounter
            
        Returns:
            ActionResult object with the outcome of the action
        """
        # Extract action details from intent
        action_type = self._determine_action_type(action_intent.get("action", ""))
        target_name = action_intent.get("target", "")
        explanation = action_intent.get("explanation", "")
        
        # Find target combatant if specified
        target = self._find_target(target_name, all_combatants)
        
        # Create result object
        result = ActionResult()
        
        # Execute based on action type
        if action_type == ActionType.ATTACK:
            self._execute_attack(action_intent, active_combatant, target, result)
        elif action_type == ActionType.SPELL:
            self._execute_spell(action_intent, active_combatant, target, all_combatants, result)
        elif action_type == ActionType.HEAL:
            self._execute_heal(action_intent, active_combatant, target, result)
        elif action_type == ActionType.DODGE:
            self._execute_dodge(active_combatant, result)
        elif action_type == ActionType.MOVEMENT:
            self._execute_movement(action_intent, active_combatant, result)
        else:
            # Default handling for other action types
            result.success = True
            result.narrative = f"{active_combatant['name']} {action_intent.get('action', 'takes an action')}"
            if target:
                result.narrative += f" targeting {target['name']}"
            if explanation:
                result.narrative += f". {explanation}"
        
        return result
    
    def _determine_action_type(self, action_text: str) -> ActionType:
        """
        Determine the type of action from the action text.
        
        Args:
            action_text: The action text from the LLM
            
        Returns:
            ActionType enum value
        """
        action_text = action_text.lower()
        
        # Check for attacks
        if any(x in action_text for x in ["attack", "strike", "slash", "stab", "shoot", "fire"]):
            return ActionType.ATTACK
        
        # Check for spells
        if any(x in action_text for x in ["cast", "spell", "magic"]):
            return ActionType.SPELL
        
        # Check for healing
        if any(x in action_text for x in ["heal", "cure", "restore"]):
            return ActionType.HEAL
        
        # Check for movement
        if any(x in action_text for x in ["move", "position", "approach", "retreat"]):
            return ActionType.MOVEMENT
        
        # Check for dodge
        if "dodge" in action_text:
            return ActionType.DODGE
        
        # Default to unknown
        return ActionType.UNKNOWN
    
    def _find_target(self, target_name: str, combatants: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Find a target combatant by name.
        
        Args:
            target_name: The name of the target
            combatants: List of all combatants
            
        Returns:
            The target combatant dict or None if not found
        """
        if not target_name:
            return None
            
        # Try exact match first
        for combatant in combatants:
            if combatant.get("name", "").lower() == target_name.lower():
                return combatant
                
        # Try partial match
        for combatant in combatants:
            if target_name.lower() in combatant.get("name", "").lower():
                return combatant
                
        return None
    
    def _execute_attack(self, action_intent: Dict[str, Any], 
                       attacker: Dict[str, Any], 
                       target: Optional[Dict[str, Any]], 
                       result: ActionResult) -> None:
        """Execute an attack action."""
        if not target:
            result.success = False
            result.narrative = f"{attacker['name']} attempts to attack but finds no valid target."
            return
            
        # Get target AC
        target_ac = target.get("ac", 10)
        
        # Calculate attack bonus (could be based on the weapon/ability)
        attack_bonus = action_intent.get("attack_bonus", 0)
        if "attack_bonus" not in action_intent:
            # Try to infer a reasonable attack bonus from attacker's abilities
            attack_bonus = self._infer_attack_bonus(attacker, action_intent)
        
        # Roll to hit
        attack_roll_expr = f"1d20+{attack_bonus}"
        attack_roll = self.dice_roller(attack_roll_expr)
        result.add_roll("Attack Roll", attack_roll_expr, attack_roll)
        
        # Determine hit/miss
        if attack_roll >= target_ac:
            # Hit! Roll damage
            damage_expr = action_intent.get("damage_dice", "1d6+0")
            if "damage_dice" not in action_intent:
                # Infer damage dice
                damage_expr = self._infer_damage_dice(attacker, action_intent)
                
            damage = self.dice_roller(damage_expr)
            result.add_roll("Damage", damage_expr, damage)
            
            result.success = True
            result.damage = damage
            
            # Create narrative
            result.narrative = (
                f"{attacker['name']} attacks {target['name']} "
                f"({attack_roll} vs AC {target_ac}) and hits for {damage} damage!"
            )
        else:
            # Miss
            result.success = False
            result.narrative = (
                f"{attacker['name']} attacks {target['name']} "
                f"({attack_roll} vs AC {target_ac}) but misses."
            )
    
    def _execute_spell(self, action_intent: Dict[str, Any], 
                      caster: Dict[str, Any], 
                      target: Optional[Dict[str, Any]],
                      all_combatants: List[Dict[str, Any]], 
                      result: ActionResult) -> None:
        """Execute a spell casting action."""
        spell_name = action_intent.get("spell_name", "a spell")
        
        # Spell targeting logic depends on spell type
        if target:
            # Single-target spell
            save_dc = action_intent.get("save_dc", 13)  # Default save DC
            if "save_dc" not in action_intent:
                # Try to infer save DC from caster's abilities
                save_dc = self._infer_save_dc(caster)
                
            save_ability = action_intent.get("save_ability", "dex")
            
            # Roll saving throw for target
            save_bonus = target.get(f"{save_ability}_save", 0)
            save_roll_expr = f"1d20+{save_bonus}"
            save_roll = self.dice_roller(save_roll_expr)
            result.add_roll(f"{save_ability.capitalize()} Save", save_roll_expr, save_roll)
            
            # Determine effect based on save
            if save_roll >= save_dc:
                # Save successful
                damage_expr = action_intent.get("damage_dice", "1d6+0")
                damage = self.dice_roller(damage_expr) // 2  # Half damage on save
                result.add_roll("Damage (Half on Save)", damage_expr, damage)
                
                result.success = True
                result.damage = damage
                result.narrative = (
                    f"{caster['name']} casts {spell_name} at {target['name']}. "
                    f"{target['name']} rolls a {save_ability.upper()} save ({save_roll} vs DC {save_dc}) "
                    f"and succeeds, taking {damage} damage."
                )
            else:
                # Save failed
                damage_expr = action_intent.get("damage_dice", "1d6+0")
                damage = self.dice_roller(damage_expr)
                result.add_roll("Damage", damage_expr, damage)
                
                result.success = True
                result.damage = damage
                result.narrative = (
                    f"{caster['name']} casts {spell_name} at {target['name']}. "
                    f"{target['name']} rolls a {save_ability.upper()} save ({save_roll} vs DC {save_dc}) "
                    f"and fails, taking {damage} damage."
                )
                
                # Add effects based on spell
                effect = action_intent.get("effect", "")
                if effect:
                    result.effects.append(effect)
                    result.narrative += f" {target['name']} is now {effect}."
        else:
            # Area effect or self-targeting spell
            result.success = True
            result.narrative = f"{caster['name']} casts {spell_name}"
            
            # Add explanation if provided
            explanation = action_intent.get("explanation", "")
            if explanation:
                result.narrative += f". {explanation}"
    
    def _execute_heal(self, action_intent: Dict[str, Any], 
                     healer: Dict[str, Any], 
                     target: Optional[Dict[str, Any]], 
                     result: ActionResult) -> None:
        """Execute a healing action."""
        # If no target specified, assume self-healing
        actual_target = target if target else healer
        
        # Roll healing amount
        healing_expr = action_intent.get("healing_dice", "1d8+2")
        healing_amount = self.dice_roller(healing_expr)
        result.add_roll("Healing", healing_expr, healing_amount)
        
        result.success = True
        result.healing = healing_amount
        
        # Create narrative
        if actual_target == healer:
            result.narrative = f"{healer['name']} heals themselves for {healing_amount} hit points."
        else:
            result.narrative = f"{healer['name']} heals {actual_target['name']} for {healing_amount} hit points."
    
    def _execute_dodge(self, combatant: Dict[str, Any], result: ActionResult) -> None:
        """Execute a dodge action."""
        result.success = True
        result.effects.append("Dodge")
        result.narrative = f"{combatant['name']} takes the Dodge action, gaining advantage on DEX saves and imposing disadvantage on attacks against them until their next turn."
    
    def _execute_movement(self, action_intent: Dict[str, Any], 
                         combatant: Dict[str, Any], 
                         result: ActionResult) -> None:
        """Execute a movement action."""
        # Simple movement narrative for now
        # In a full implementation, this would track position on a grid
        position = action_intent.get("position", "")
        if position:
            result.success = True
            result.narrative = f"{combatant['name']} moves to {position}."
        else:
            result.success = True
            result.narrative = f"{combatant['name']} moves."
            
        # Add explanation if provided
        explanation = action_intent.get("explanation", "")
        if explanation:
            result.narrative += f" {explanation}"
    
    def _infer_attack_bonus(self, attacker: Dict[str, Any], action_intent: Dict[str, Any]) -> int:
        """Infer a reasonable attack bonus based on the attacker and action."""
        # Default to a modest bonus
        default_bonus = 4
        
        # Try to extract from attacker data if available
        abilities = attacker.get("abilities", {})
        
        # For monsters, use a computed attack bonus based on CR if available
        cr = attacker.get("challenge_rating", 0)
        if cr and isinstance(cr, (int, float)):
            # Approximate attack bonus based on CR
            return min(2 + int(cr / 4), 14)  # Caps at +14 for high CR
        
        # If we have STR/DEX, use the higher one for physical attacks
        str_mod = abilities.get("str", 0) // 2 - 5 if abilities.get("str") else 0
        dex_mod = abilities.get("dex", 0) // 2 - 5 if abilities.get("dex") else 0
        
        # Proficiency bonus based on level/CR
        prof_bonus = 2
        
        # For weapons, use STR or DEX
        weapon_attack = action_intent.get("action", "").lower()
        if any(x in weapon_attack for x in ["sword", "axe", "hammer", "maul"]):
            return str_mod + prof_bonus if str_mod > 0 else default_bonus
        elif any(x in weapon_attack for x in ["bow", "arrow", "shot", "throw"]):
            return dex_mod + prof_bonus if dex_mod > 0 else default_bonus
        
        # Default
        return max(str_mod, dex_mod) + prof_bonus if max(str_mod, dex_mod) > 0 else default_bonus
    
    def _infer_damage_dice(self, attacker: Dict[str, Any], action_intent: Dict[str, Any]) -> str:
        """Infer damage dice based on the attacker and action."""
        # Default to a simple damage die
        default_damage = "1d6+2"
        
        # Try to extract from attacker data if available
        abilities = attacker.get("abilities", {})
        
        # For monsters, scale by CR if available
        cr = attacker.get("challenge_rating", 0)
        if cr and isinstance(cr, (int, float)):
            if cr <= 1:
                return "1d6+2"
            elif cr <= 5:
                return "2d6+3"
            elif cr <= 10:
                return "3d6+5"
            else:
                return "4d6+6"
        
        # For specific weapons, use appropriate dice
        action = action_intent.get("action", "").lower()
        if "greatsword" in action:
            return "2d6+3"
        elif "greataxe" in action:
            return "1d12+3"
        elif "longsword" in action or "long sword" in action:
            return "1d8+3"
        elif "shortbow" in action or "short bow" in action:
            return "1d6+2"
        elif "longbow" in action or "long bow" in action:
            return "1d8+2"
        elif "dagger" in action:
            return "1d4+2"
        
        # Default
        return default_damage
    
    def _infer_save_dc(self, caster: Dict[str, Any]) -> int:
        """Infer spell save DC based on the caster."""
        # Default DC
        default_dc = 13
        
        # Try to extract from caster data if available
        abilities = caster.get("abilities", {})
        
        # For monsters, scale by CR if available
        cr = caster.get("challenge_rating", 0)
        if cr and isinstance(cr, (int, float)):
            # Approximate DC based on CR
            return min(8 + 2 + int(cr / 4), 19)  # Caps at DC 19 for high CR
        
        # If we have casting ability scores, calculate properly
        int_mod = abilities.get("int", 0) // 2 - 5 if abilities.get("int") else 0
        wis_mod = abilities.get("wis", 0) // 2 - 5 if abilities.get("wis") else 0
        cha_mod = abilities.get("cha", 0) // 2 - 5 if abilities.get("cha") else 0
        
        # Proficiency bonus based on level/CR
        prof_bonus = 2
        
        # 8 + proficiency + ability modifier
        spellcasting_ability_mod = max(int_mod, wis_mod, cha_mod)
        if spellcasting_ability_mod > 0:
            return 8 + prof_bonus + spellcasting_ability_mod
        
        # Default
        return default_dc
