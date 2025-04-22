# Fast Combat Resolver Improvements

This document outlines improvements to the D&D 5e combat resolver system to make it more realistic, faster, and compliant with the 5e rules.

## 1. Proper Initiative and Combat Order Handling

**Status**: Not implemented

**Description**: The current resolver sorts combatants by initiative, but it doesn't properly manage ties or provide support for initiative-modifying features.

**Proposed Changes**:
- Implement initiative tie-breaking using DEX scores
- Support for features that modify initiative order
- Handle "Improved Initiative" and similar abilities
- Track reactions that can change initiative order

**Implementation Notes**:
```python
# Improved initiative ordering with proper tie-breaking 
active_combatants = sorted(
    range(len(combatants)), 
    key=lambda i: (-int(combatants[i].get("initiative", 0)), 
                   -int(combatants[i].get("dexterity", 0)),  # DEX as tiebreaker
                   -int(combatants[i].get("initiative_advantage", 0)))  # Some creatures have advantage
)
```

## 2. Complete Set of Conditions

**Status**: Partially implemented

**Description**: The code handles basic status effects like "Unconscious" but doesn't implement all D&D 5e conditions or their mechanical effects.

**Proposed Changes**:
- Add structured condition tracking for all official 5e conditions
- Implement mechanical effects for each condition
- Support condition duration tracking
- Add condition removal logic for saves/turns

**Implementation Notes**:
```python
# Add a conditions field to combatants
if "conditions" not in combatant:
    combatant["conditions"] = {}
    
# Update conditions with duration and source
combatant["conditions"]["stunned"] = {
    "duration": 1,  # turns or rounds
    "source": "Stunning Strike",
    "save_dc": 15,
    "save_ability": "constitution"
}
```

## 3. Action Economy Management

**Status**: Not implemented

**Description**: The current system doesn't track action economy (actions, bonus actions, reactions, movement).

**Proposed Changes**:
- Track available actions per combatant
- Implement action, bonus action, and reaction tracking
- Track movement and opportunity attacks
- Support special action types (e.g., Legendary Actions)

**Implementation Notes**:
```python
def _process_action_economy(self, decision, combatant):
    """Process and validate action economy for a turn"""
    # Initialize action economy if not present
    if "action_economy" not in combatant:
        combatant["action_economy"] = {
            "action": True,
            "bonus_action": True,
            "reaction": True,
            "movement": combatant.get("speed", 30)
        }
    
    # Reset at start of turn
    combatant["action_economy"] = {
        "action": True,
        "bonus_action": True,
        "reaction": True,
        "movement": combatant.get("speed", 30)
    }
    
    # Track used actions in the decision
    if "used_actions" in decision:
        for action_type in decision["used_actions"]:
            combatant["action_economy"][action_type] = False
    
    return combatant["action_economy"]
```

## 4. Opportunity Attack and Reaction Handling

**Status**: Not implemented

**Description**: The system doesn't handle opportunity attacks or reactions.

**Proposed Changes**:
- Implement opportunity attack detection based on movement
- Add reaction tracking for all combatants
- Support special reaction abilities
- Handle interrupt-style reactions

**Implementation Notes**:
```python
def _check_opportunity_attacks(self, moving_combatant, combatants):
    """Check if movement provokes opportunity attacks"""
    # Get enemies in melee range
    enemies_in_range = [c for c in combatants 
                        if c.get("type") != moving_combatant.get("type") 
                        and c.get("position", {}).get("distance_to", {}).get(moving_combatant["name"], 100) <= 5
                        and c.get("action_economy", {}).get("reaction", False)]
    
    for enemy in enemies_in_range:
        # Roll opportunity attack
        attack_roll = self._roll_attack(enemy, moving_combatant)
        if attack_roll["hits"]:
            # Process damage
            damage = self._roll_damage(enemy, moving_combatant, attack_roll["critical"])
            moving_combatant["hp"] = max(0, moving_combatant["hp"] - damage)
            
            # Mark reaction as used
            enemy["action_economy"]["reaction"] = False
            
            return {
                "attacker": enemy["name"],
                "target": moving_combatant["name"],
                "attack_roll": attack_roll["roll"],
                "damage": damage,
                "narrative": f"{enemy['name']} strikes {moving_combatant['name']} as they move away, dealing {damage} damage."
            }
    
    return None
```

## 5. Concentration Mechanics

**Status**: Not implemented

**Description**: The system doesn't handle concentration mechanics for spellcasters.

**Proposed Changes**:
- Add concentration tracking for spells
- Implement concentration checks when damage is taken
- Support multiple concentration effects
- Add concentration breaking

**Implementation Notes**:
```python
def _process_concentration_check(self, combatant, damage):
    """Process concentration check when a spellcaster takes damage"""
    if combatant.get("concentrating_on"):
        # Determine DC (10 or half damage, whichever is higher)
        dc = max(10, int(damage / 2))
        
        # Roll concentration save
        roll = self._roll_save(combatant, "constitution", dc)
        
        if roll["success"]:
            return {
                "maintained": True,
                "roll": roll["roll"],
                "dc": dc,
                "narrative": f"{combatant['name']} maintains concentration on {combatant['concentrating_on']}."
            }
        else:
            # End concentration effect
            spell = combatant.pop("concentrating_on")
            return {
                "maintained": False,
                "roll": roll["roll"],
                "dc": dc,
                "narrative": f"{combatant['name']} loses concentration on {spell}."
            }
    
    return None
```

## 6. Aura Effects

**Status**: Not implemented

**Description**: No support for creature and character aura effects.

**Proposed Changes**:
- Add aura effect definitions and ranges
- Process aura effects at appropriate times
- Support beneficial and harmful auras
- Handle aura interactions and stacking

**Implementation Notes**:
```python
def _process_auras(self, active_combatant, combatants):
    """Process aura effects at the start of a combatant's turn"""
    updates = []
    
    # Check for aura effects from all combatants
    for c in combatants:
        if "auras" not in c:
            continue
            
        for aura_name, aura in c.get("auras", {}).items():
            # Check if this combatant is affected by the aura
            range_feet = aura.get("range", 0)
            distance = c.get("position", {}).get("distance_to", {}).get(active_combatant["name"], 999)
            
            if distance <= range_feet:
                effect = aura.get("effect", {})
                effect_type = effect.get("type")
                
                if effect_type == "damage":
                    # Process damage aura
                    damage = self._roll_expression(effect.get("expression", "0"))
                    active_combatant["hp"] = max(0, active_combatant["hp"] - damage)
                    updates.append({
                        "source": c["name"],
                        "aura": aura_name,
                        "target": active_combatant["name"],
                        "effect": f"{damage} {effect.get('damage_type', 'unspecified')} damage"
                    })
                elif effect_type == "condition":
                    # Add condition
                    condition = effect.get("condition")
                    if "conditions" not in active_combatant:
                        active_combatant["conditions"] = {}
                    active_combatant["conditions"][condition] = {
                        "source": f"{c['name']}'s {aura_name}",
                        "duration": effect.get("duration", 1)
                    }
                    updates.append({
                        "source": c["name"],
                        "aura": aura_name,
                        "target": active_combatant["name"],
                        "effect": f"Condition: {condition}"
                    })
    
    return updates
```

## 7. Legendary Actions

**Status**: Not implemented

**Description**: No support for legendary actions used by powerful monsters.

**Proposed Changes**:
- Add legendary action tracking
- Implement legendary action resolution after other turns
- Support cost tracking for legendary actions
- Handle legendary action targeting

**Implementation Notes**:
```python
def _process_legendary_actions(self, current_combatant, legendary_creatures, combatants, dice_roller):
    """Process legendary actions after a non-legendary creature's turn"""
    results = []
    
    # Skip if current combatant is a legendary creature
    if current_combatant.get("legendary_actions", 0) > 0:
        return results
        
    # Process legendary actions for eligible creatures
    for creature in legendary_creatures:
        # Skip if no legendary actions remaining
        if creature.get("legendary_actions_used", 0) >= creature.get("legendary_actions", 0):
            continue
            
        # Generate legendary action decision using LLM
        legendary_prompt = self._create_legendary_action_prompt(creature, combatants)
        decision = self._get_legendary_decision_from_llm(legendary_prompt)
        
        if decision and "action" in decision:
            # Process dice for the legendary action
            dice_results = []
            for req in decision.get("dice_requests", []):
                expression = req.get("expression", "")
                purpose = req.get("purpose", "")
                if expression:
                    result = dice_roller(expression)
                    dice_results.append({
                        "expression": expression,
                        "result": result,
                        "purpose": purpose
                    })
            
            # Process the effects of the legendary action
            resolution = self._resolve_legendary_action(creature, decision, dice_results, combatants)
            
            # Increment used legendary actions
            creature["legendary_actions_used"] = creature.get("legendary_actions_used", 0) + decision.get("cost", 1)
            
            results.append({
                "creature": creature["name"],
                "action": decision["action"],
                "narrative": resolution.get("narrative", ""),
                "updates": resolution.get("updates", [])
            })
    
    return results
```

## 8. Damage Types, Resistances and Vulnerabilities

**Status**: Not implemented

**Description**: The system doesn't handle damage types or resistances/immunities/vulnerabilities.

**Proposed Changes**:
- Track damage types for all attacks
- Implement resistance (half damage)
- Implement immunity (no damage)
- Implement vulnerability (double damage)
- Support conditional resistances

**Implementation Notes**:
```python
def _apply_damage_with_resistances(self, target, damage, damage_type):
    """Apply damage accounting for resistances, immunities, and vulnerabilities"""
    # Get target's resistances, immunities, and vulnerabilities
    resistances = target.get("resistances", [])
    immunities = target.get("immunities", [])
    vulnerabilities = target.get("vulnerabilities", [])
    
    # Check for immunity
    if damage_type in immunities:
        return {
            "original_damage": damage,
            "final_damage": 0,
            "hp_before": target["hp"],
            "hp_after": target["hp"],
            "modifier": "immune"
        }
        
    # Check for resistance
    elif damage_type in resistances:
        modified_damage = max(1, damage // 2)  # Minimum 1 damage
        target["hp"] = max(0, target["hp"] - modified_damage)
        return {
            "original_damage": damage,
            "final_damage": modified_damage,
            "hp_before": target["hp"] + modified_damage,
            "hp_after": target["hp"],
            "modifier": "resistant"
        }
        
    # Check for vulnerability
    elif damage_type in vulnerabilities:
        modified_damage = damage * 2
        target["hp"] = max(0, target["hp"] - modified_damage)
        return {
            "original_damage": damage,
            "final_damage": modified_damage,
            "hp_before": target["hp"] + modified_damage,
            "hp_after": target["hp"],
            "modifier": "vulnerable"
        }
        
    # Normal damage
    else:
        target["hp"] = max(0, target["hp"] - damage)
        return {
            "original_damage": damage,
            "final_damage": damage,
            "hp_before": target["hp"] + damage,
            "hp_after": target["hp"],
            "modifier": "normal"
        }
```

## 9. Special Combat Rules

**Status**: Not implemented

**Description**: Missing support for cover, flanking, and critical effects.

**Proposed Changes**:
- Implement flanking (+2 bonus or advantage)
- Add cover mechanics (half, three-quarters, full)
- Support critical hit special effects
- Implement special abilities that trigger on hit

**Implementation Notes**:
```python
def _check_critical_effects(self, attacker, target, is_critical):
    """Process special effects on critical hits"""
    effects = []
    
    if is_critical:
        # Check for Brutal Critical/Savage Attacks
        if "brutal_critical" in attacker:
            extra_dice = attacker["brutal_critical"]
            effects.append(f"adds {extra_dice} extra damage dice from Brutal Critical")
            
        # Check for fighter's Improved Critical
        if attacker.get("improved_critical"):
            effects.append("critical hit range expanded to 19-20")
            
        # Check for Half-Orc's Savage Attacks
        if attacker.get("savage_attacks"):
            effects.append("adds 1 extra damage die from Savage Attacks")
    
    return effects

def _check_cover(self, attacker, target):
    """Determine if the target has cover from the attacker"""
    # This would use positional data in a real implementation
    cover_level = target.get("position", {}).get("cover", 0)
    
    if cover_level == 3:
        return {"level": "full", "ac_bonus": 5, "dex_save_bonus": True}
    elif cover_level == 2:
        return {"level": "three-quarters", "ac_bonus": 5, "dex_save_bonus": True}
    elif cover_level == 1:
        return {"level": "half", "ac_bonus": 2, "dex_save_bonus": True}
    else:
        return {"level": "none", "ac_bonus": 0, "dex_save_bonus": False}
```

## 10. Improved Death Save and Healing Mechanics

**Status**: Partially implemented

**Description**: Basic death save handling exists but doesn't handle all edge cases.

**Proposed Changes**:
- Improve healing on unconscious characters
- Handle instant death from massive damage
- Support stabilization attempts
- Implement death save modification features

**Implementation Notes**:
```python
def _process_healing_on_unconscious(self, target, healing_amount):
    """Process healing on an unconscious character"""
    if target.get("status", "").lower() == "unconscious" and target.get("hp", 0) <= 0:
        # Reset death save counts
        if "death_saves" in target:
            target["death_saves"] = {"successes": 0, "failures": 0}
            
        # Apply healing and restore consciousness
        target["hp"] = min(healing_amount, target.get("max_hp", healing_amount))
        target["status"] = "Conscious"
        
        return {
            "was_unconscious": True,
            "hp_after": target["hp"],
            "narrative": f"{target['name']} regains consciousness with {target['hp']} hit points."
        }
    else:
        # Normal healing
        old_hp = target.get("hp", 0)
        target["hp"] = min(old_hp + healing_amount, target.get("max_hp", old_hp + healing_amount))
        
        return {
            "was_unconscious": False,
            "hp_after": target["hp"],
            "narrative": f"{target['name']} is healed for {healing_amount} hit points."
        }
```

## 11. Smarter Target Selection

**Status**: Basic implementation

**Description**: The current system has minimal targeting logic.

**Proposed Changes**:
- Implement tactical target selection
- Consider HP, AC, threat level in targeting
- Support focus-fire strategies
- Handle defensive positioning

**Implementation Notes**:
```python
def _determine_optimal_target(self, attacker, combatants):
    """Determine the optimal target for an attack based on tactical considerations"""
    enemies = [c for c in combatants 
              if c.get("type") != attacker.get("type") 
              and c.get("hp", 0) > 0 
              and c.get("status", "").lower() != "dead"]
    
    if not enemies:
        return None
        
    # Score potential targets
    scored_targets = []
    for target in enemies:
        score = 0
        
        # Prioritize low HP targets
        hp_percent = target.get("hp", 0) / target.get("max_hp", 1)
        score += (1 - hp_percent) * 30  # Up to 30 points for nearly dead targets
        
        # Prioritize low AC targets
        ac = target.get("ac", 10)
        score += max(0, (20 - ac)) * 2  # Up to 20 points for AC 10
        
        # Prioritize dangerous enemies (spellcasters, high damage)
        if "spellcaster" in target.get("traits", []):
            score += 15
        if target.get("damage_per_round", 0) > 15:
            score += 10
            
        # Consider distance (prefer closest targets)
        distance = attacker.get("position", {}).get("distance_to", {}).get(target["name"], 30)
        if distance <= 5:  # Melee range
            score += 20
        else:
            score -= distance  # Penalize distant targets
            
        # Adjust for conditions
        if "conditions" in target:
            if "stunned" in target["conditions"] or "paralyzed" in target["conditions"]:
                score += 25  # Prioritize stunned/paralyzed targets
            if "unconscious" in target["conditions"]:
                score += 35  # Prioritize unconscious targets (auto-crit in melee)
                
        scored_targets.append((target, score))
    
    # Return the highest-scored target
    return max(scored_targets, key=lambda x: x[1])[0] if scored_targets else None
```

## 12. Environmental Effects and Terrain

**Status**: Not implemented

**Description**: No support for terrain or environmental effects.

**Proposed Changes**:
- Add difficult terrain tracking
- Implement environmental hazards
- Support terrain-based advantages/disadvantages
- Add environmental interaction

**Implementation Notes**:
```python
def _process_environmental_effects(self, combatant, environment):
    """Process effects from the environment"""
    effects = []
    
    # Check for difficult terrain
    if combatant.get("position", {}).get("terrain", "") == "difficult":
        # Movement is halved in difficult terrain
        combatant["action_economy"]["movement"] = combatant["action_economy"]["movement"] // 2
        effects.append("movement halved due to difficult terrain")
    
    # Check for environmental hazards
    hazards = environment.get("hazards", [])
    for hazard in hazards:
        if combatant.get("position", {}).get("in_hazard") == hazard["id"]:
            # Apply hazard effect
            if hazard["type"] == "damage":
                damage = random.randint(hazard["damage_min"], hazard["damage_max"])
                damage_type = hazard.get("damage_type", "fire")
                
                # Apply damage
                result = self._apply_damage_with_resistances(combatant, damage, damage_type)
                effects.append(f"takes {result['final_damage']} {damage_type} damage from {hazard['name']}")
    
    return effects
``` 