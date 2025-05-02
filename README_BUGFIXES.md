# Combat Resolver Bug Fixes

## Issue Overview

The combat resolver's "fast resolve" feature was encountering errors that prevented it from completing. There were several issues:

1. A missing `_process_recharge_abilities` method was causing an `AttributeError`
2. The `goto_post_turn_logic` variable was not properly initialized
3. The code did not properly handle cases where `turn_result` was `None`

## Fixes Applied

### 1. Added Missing Method

Added the `_process_recharge_abilities` method to the `CombatResolver` class, which handles monster abilities that recharge on dice rolls (e.g., "recharges on 5-6").

```python
def _process_recharge_abilities(self, combatant, dice_roller):
    """Process recharge abilities for a monster at the start of its turn."""
    # Checks if the combatant is a monster, otherwise returns early
    # Processes each recharge ability, rolling dice to determine if they recharge
```

### 2. Properly Initialize Variables

Added proper initialization for the `goto_post_turn_logic` variable to prevent `NameError` exceptions:

```python
# Added near the start of the turn processing logic
skip_turn = False
skip_reason = ""
goto_post_turn_logic = False  # Initialize this variable to prevent NameError
```

### 3. Added Null Checking for turn_result

Fixed the code to properly handle cases where `turn_result` is `None`:

```python
# Before:
turn_summary = f"Round {round_num}, {combatant_name}'s turn: {turn_result.get('narrative', 'No action.')}"

# After:
turn_summary = f"Round {round_num}, {combatant_name}'s turn: {turn_result.get('narrative', 'No action.') if turn_result else 'No result available.'}"
```

## Testing

The fixes were verified with a dedicated test script that directly calls the problematic methods. The tests confirmed that:

1. The LLM service is working correctly
2. The `_process_turn` method returns valid results
3. The call to the LLM service is made successfully

## How to Apply Fixes

The fixes are automatically applied at application startup through the `fix_fast_resolve.py` script, which is called from `main.py`.

## Conclusion

These fixes ensure that the "fast resolve" feature works reliably by:

1. Handling missing methods
2. Properly initializing variables
3. Adding robust error handling
4. Ensuring LLM calls are made correctly

The combat resolver now properly handles edge cases and provides better error messages when something goes wrong. 