# D&D 5e Action Economy System

This module implements the D&D 5e action economy system, which tracks and manages the available actions for combatants during combat.

## Overview

In D&D 5e, each combatant has a limited number of actions they can take on their turn:

- **Action**: The main action for a turn (attack, cast a spell, dash, etc.)
- **Bonus Action**: An additional quick action if available from abilities or spells
- **Reaction**: An action that can be taken once per round, typically in response to a trigger
- **Movement**: Movement up to the combatant's speed
- **Free Action**: Minor interaction (draw a weapon, open a door, speak a phrase)
- **Legendary Action**: Special actions available to legendary creatures, usable after other combatants' turns

## Implementation

The action economy system is implemented in the following files:

- `app/combat/action_economy.py`: Core action economy tracking and management
- `app/core/improved_combat_resolver.py`: Integration with the combat resolver
- `app/core/combat_resolver.py`: Basic integration with the LLM decision system

## Key Features

1. **Action Tracking**: Keeps track of which actions are available to each combatant
2. **Action Usage**: Validates and processes action usage during a combatant's turn
3. **Opportunity Attacks**: Detects and processes opportunity attacks when combatants move away from melee range
4. **Legendary Actions**: Supports legendary actions for boss monsters
5. **Condition Integration**: Works with the condition system to handle effects that limit available actions

## How to Use

### 1. Initialize Action Economy

```python
from app.combat.action_economy import ActionEconomyManager

# Initialize a combatant's action economy at the start of their turn
combatant = ActionEconomyManager.initialize_action_economy(combatant)
```

### 2. Check Available Actions

```python
# Check which actions are available to a combatant
available_actions = ActionEconomyManager.check_available_actions(combatant)

if available_actions.get('action', False):
    # Combatant can take an action
    pass
    
if available_actions.get('bonus_action', False):
    # Combatant can take a bonus action
    pass
    
remaining_movement = available_actions.get('movement', 0)
```

### 3. Use an Action

```python
from app.combat.action_economy import ActionEconomyManager, ActionType

# Use an action
combatant, success = ActionEconomyManager.use_action(combatant, ActionType.ACTION)

# Use movement
combatant, success = ActionEconomyManager.use_action(combatant, ActionType.MOVEMENT, 30)  # Move 30 feet

# Use a legendary action with a cost of 2
combatant, success = ActionEconomyManager.use_action(combatant, ActionType.LEGENDARY_ACTION, 2)
```

### 4. Process a Decision

```python
# Process a complex decision with action economy
decision = {
    "action_type": "action",  # or "bonus_action", "movement", etc.
    "movement_cost": 30       # if movement is being used
}

combatant, success, reason = ActionEconomyManager.process_action_decision(combatant, decision)

if not success:
    print(f"Cannot perform action: {reason}")
```

### 5. Check for Opportunity Attacks

```python
# Save the previous position before movement
previous_position = copy.deepcopy(combatant.get("position", {}))

# After movement, check for opportunity attacks
opportunity_attacks = ActionEconomyManager.check_opportunity_attacks(
    combatant, all_combatants, previous_position
)

# Process the opportunity attacks
for attack in opportunity_attacks:
    # Handle each opportunity attack
    pass
```

## Integration with LLM

The action economy system is integrated with the LLM-based combat resolver:

1. The LLM is provided with information about available actions when making decisions
2. The LLM can specify action types in its decision response
3. The resolver processes these decisions and updates the action economy accordingly
4. Opportunity attacks are automatically detected and processed during movement

## Future Improvements

- Add support for ready actions (actions prepared to trigger on a specific event)
- Implement more granular movement tracking for tactical grid-based combat
- Add support for difficult terrain affecting movement costs
- Enhance opportunity attack processing with more detailed attack mechanics 