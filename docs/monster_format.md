# Monster Data Format Documentation

This document explains how to properly format monster data to ensure the combat AI uses their abilities correctly.

## Key Requirements

For monsters to behave properly in combat, each monster should have:

1. Basic information (name, HP, AC, etc.)
2. Explicitly defined abilities, actions, and traits
3. Proper attack bonuses and damage values for attacks

## Monster Object Format

```json
{
  "name": "Ancient Red Dragon",
  "type": "monster",
  "hp": 546,
  "max_hp": 546,
  "ac": 22,
  "speed": 40,
  "initiative": 0,
  "status": "OK",
  "attack_bonus": 17,  // Default attack bonus if not specified per action
  "damage_dice": "2d10",  // Default damage dice if not specified per action 
  "damage_bonus": 10,  // Default damage bonus if not specified per action
  "weapon": "claw",  // Default weapon name for basic attacks
  
  "actions": {
    "Multiattack": {
      "description": "The dragon can use its Frightful Presence. It then makes three attacks: one with its bite and two with its claws."
    },
    "Bite": {
      "description": "Melee Weapon Attack: +17 to hit, reach 15 ft., one target.",
      "attack_bonus": 17,
      "damage": "2d10+10 piercing plus 4d6 fire"
    },
    "Claw": {
      "description": "Melee Weapon Attack: +17 to hit, reach 10 ft., one target.",
      "attack_bonus": 17,
      "damage": "2d6+10 slashing"
    },
    "Tail": {
      "description": "Melee Weapon Attack: +17 to hit, reach 20 ft., one target.",
      "attack_bonus": 17,
      "damage": "2d8+10 bludgeoning"
    },
    "Frightful Presence": {
      "description": "Each creature of the dragon's choice within 120 ft. must make a DC 21 Wisdom saving throw or be frightened for 1 minute."
    },
    "Fire Breath": {
      "description": "The dragon exhales fire in a 90-foot cone. Each creature in that area must make a DC 24 Dexterity saving throw, taking 26d6 fire damage on a failed save, or half as much damage on a successful one."
    }
  },
  
  "legendary_actions": 3,
  
  "abilities": {
    "Legendary Resistance": {
      "description": "If the dragon fails a saving throw, it can choose to succeed instead.",
      "usage": "3/day"
    }
  },
  
  "traits": {
    "Fire Immunity": {
      "description": "The dragon is immune to fire damage."
    },
    "Amphibious": {
      "description": "The dragon can breathe both air and water."
    }
  }
}
```

## Important Structure Explanation

### 1. Actions

Actions are formatted as a dictionary with the name as the key and details as the value:

```json
"actions": {
  "ACTION_NAME": {
    "description": "Detailed description",
    "attack_bonus": 5,  // Optional, for attack actions
    "damage": "2d6+3"   // Optional, for damage-dealing actions
  }
}
```

For attack actions, include both `attack_bonus` and `damage` fields to ensure proper processing.

### 2. Abilities

Abilities are special capabilities that may have limited uses:

```json
"abilities": {
  "ABILITY_NAME": {
    "description": "What the ability does",
    "usage": "How often it can be used (e.g., '3/day', 'recharge 5-6', 'at will')"
  }
}
```

### 3. Traits

Traits are passive characteristics that may affect gameplay:

```json
"traits": {
  "TRAIT_NAME": {
    "description": "What this trait means for the monster"
  }
}
```

## Basic Attack Fallback

If no explicit actions are defined, the system will fall back to using a basic attack constructed from:

- `attack_bonus` (default: 0)
- `damage_dice` (default: "1d6")
- `damage_bonus` (default: 0)
- `weapon` (default: "weapon")

## Best Practices

1. **Be Comprehensive**: Include all abilities from the monster's stat block
2. **Be Specific**: Include details like range, area effects, and saving throws in descriptions
3. **Be Accurate**: Use the exact modifiers from the source material
4. **Be Consistent**: Use the same name format throughout
5. **Include Limitations**: Note usage limits like "3/day" or "recharge 5-6"

## Common Issues

If your monsters are using abilities they shouldn't have:

1. Check that all abilities are properly defined in the monster data
2. Ensure there are no typos in ability names
3. Verify that the JSON structure follows the format shown above
4. Make sure descriptions are clear and accurate

By following this format, the AI will use only the abilities, actions, and traits explicitly defined for the monster, resulting in more accurate and rules-compliant combat. 