# Combat Resolver Bug Fixes

## Issue Overview

The combat resolver's "fast resolve" feature was encountering errors that prevented it from completing. There were several issues:

1. A missing `_process_recharge_abilities` method was causing an `AttributeError`
2. The `goto_post_turn_logic` variable was not properly initialized
3. The code did not properly handle cases where `turn_result` was `None`
4. The UI was not properly integrated with the updated combat resolver API

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

### 4. Updated UI Integration

The combat tracker UI was still using the old `resolve_combat_turn_by_turn` API, which has been deprecated in favor of the newer `start_resolution` method. We updated the code to:

1. Directly access the underlying `CombatResolver` instance when using `ImprovedCombatResolver`
2. Connect to the correct signal (`resolution_update` instead of `resolution_complete`)
3. Properly handle the different signal signature (state, status, error)
4. Add robust signal connection and disconnection logic to prevent memory leaks

```python
# Get direct access to CombatResolver instance
if hasattr(self.app_state.combat_resolver, 'combat_resolver'):
    # Using ImprovedCombatResolver (which has a combat_resolver attribute)
    resolver = self.app_state.combat_resolver.combat_resolver
else:
    # Using CombatResolver directly
    resolver = self.app_state.combat_resolver

# Connect to resolution_update signal (state, status, error)
resolver.resolution_update.connect(
    lambda state, status, error: self._process_resolution_ui(state, error)
)

# Start resolution with the modern API
success = resolver.start_resolution(
    combat_state,
    dice_roller,
    self._update_ui_wrapper, 
    mode='continuous'
)
```

## Testing

The fixes were verified with dedicated test scripts and manual testing. The tests confirmed that:

1. The LLM service is working correctly
2. The `_process_turn` method returns valid results
3. The call to the LLM service is made successfully
4. The UI correctly connects to the CombatResolver API

## How to Apply Fixes

The fixes are automatically applied at application startup through the `fix_fast_resolve.py` script, which is called from `main.py`.

## Conclusion

These fixes ensure that the "fast resolve" feature works reliably by:

1. Handling missing methods
2. Properly initializing variables
3. Adding robust error handling
4. Ensuring LLM calls are made correctly
5. Properly integrating with the modern CombatResolver API

The combat resolver now properly handles edge cases, provides better error messages when something goes wrong, and correctly integrates with the combat tracker UI. 