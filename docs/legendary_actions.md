# Legendary Actions System in DM Screen

## D&D 5e Legendary Actions

Legendary Actions are a special mechanic in D&D 5e that allows powerful creatures (typically bosses) to act outside of their normal turn in the initiative order. This creates more dynamic and challenging encounters, preventing the "boss monster" from being overwhelmed by the action economy when facing multiple player characters.

Key features of Legendary Actions in the D&D 5e rules:

1. **Legendary Action Pool**: A legendary creature typically has 3 legendary actions per round (though this can vary by creature).

2. **Reset Timing**: Legendary actions reset at the start of the creature's turn, not at the start of the round.

3. **Usage Timing**: Legendary actions can be used at the end of another creature's turn.

4. **Action Cost**: Different legendary actions may cost 1, 2, or 3 legendary actions from the pool.

5. **Limitations**: Legendary actions cannot be used while incapacitated or otherwise unable to take actions.

## Implementation in DM Screen

In our DM Screen application, we've implemented legendary actions with the following approach:

### Core Components

1. **ActionEconomyManager**: The central class that manages all action economy including legendary actions.

2. **Action Type Tracking**: We track legendary actions in the combatant's `action_economy` dictionary:
   - `legendary_actions`: The maximum number of legendary actions available
   - `legendary_actions_used`: How many have been used in the current round

3. **Reset Mechanism**: Unlike the D&D 5e rules (which reset at the start of the creature's turn), our system resets legendary actions at the start of each round for all legendary creatures.

### Code Implementation

The implementation in the codebase includes:

```python
# In improved_combat_resolver.py
# At the start of each combat round:
combatants = ActionEconomyManager.reset_legendary_actions(combatants)
```

The `reset_legendary_actions` method resets the legendary actions count for all combatants that have legendary actions.

### Usage in Combat

When a legendary creature wants to use a legendary action:

1. The AI makes a decision to use a legendary action at the end of another creature's turn
2. The system checks if the creature has enough legendary actions remaining using `check_available_actions`
3. The legendary action is executed and the `legendary_actions_used` counter is incremented
4. At the start of the next round, all legendary action counters are reset to zero

### Future Enhancements

Potential enhancements to consider:

1. **Rules-Accurate Timing**: Modify the system to reset legendary actions at the start of the legendary creature's turn (as per official D&D 5e rules) rather than at the start of each round.

2. **Improved Legendary Action Selection**: Enhanced AI decision-making to choose the most tactically appropriate legendary actions.

3. **Custom Legendary Actions**: Allow DMs to create custom legendary actions for their creatures.

4. **UI Indicators**: Clearly show how many legendary actions a creature has remaining.

## Example Legendary Creature

Here's an example of how a legendary creature might be defined in our system:

```json
{
  "name": "Ancient Red Dragon",
  "type": "monster",
  "legendary_actions": 3,
  "available_legendary_actions": [
    {
      "name": "Detect",
      "description": "The dragon makes a Wisdom (Perception) check.",
      "cost": 1
    },
    {
      "name": "Tail Attack",
      "description": "The dragon makes a tail attack.",
      "cost": 1
    },
    {
      "name": "Wing Attack",
      "description": "The dragon beats its wings. Each creature within 15 feet must succeed on a DC 22 Dexterity saving throw or take 15 bludgeoning damage and be knocked prone.",
      "cost": 2
    }
  ]
}
``` 