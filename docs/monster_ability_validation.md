# Monster Ability Validation System

## Overview

The Monster Ability Validation System is designed to prevent the mixing of abilities between different monster types during combat. This ensures that each monster uses only its own abilities, preventing tactical confusion and maintaining game balance.

## The Problem

During combat resolution, an issue was observed where monsters were occasionally using abilities that belonged to other monsters in the encounter. For example:

- A Magma Mephit was using skeletal abilities like "Skeletal Claws" and "Bone Barrage"
- A Hoard of Skeletons was using fire-based attacks like "Magma Breath"

This mixing of abilities created confusion and undermined the tactical integrity of combat encounters.

## Solution Components

The solution consists of multiple components working together:

1. **Monster Ability Validator Module** (`app/core/utils/monster_ability_validator.py`)
   - Core validation logic to detect and prevent ability mixing
   - Functions to extract canonical abilities for each monster
   - Tools to clean and verify ability lists

2. **Combat Resolver Patch** (`app/core/combat_resolver_patch.py`)
   - Integration with the core combat system
   - Hooks into the prompt generation process to validate abilities
   - Logging of detected ability mixing

3. **ImprovedCombatResolver Integration** (`app/core/improved_combat_resolver.py`)
   - Additional methods to validate monster data before combat
   - Pre-combat cleaning of monster abilities

4. **Unit and Integration Tests**
   - Comprehensive test suite for the validator
   - Integration tests for the combat resolver
   - Test utility for verifying the solution

## How It Works

### Tagging Monster Abilities

Each monster's abilities are tagged with a unique identifier in the format:
`[Monster_Name_MonsterID_ability]`

For example:
```
- Fire Breath: The dragon exhales fire. [Dragon_0_ability]
```

This tagging enables the system to track which abilities belong to which monsters.

### Validation Process

1. **Extract Canonical Abilities**:
   - Create a set of all abilities that belong to a monster
   - Store this in a cache to avoid repeated processing

2. **Prompt Cleaning**:
   - Ensure all abilities in the prompt are properly tagged
   - Add missing tags where necessary

3. **Validation**:
   - Check if abilities are being mixed across different monsters
   - Alert when mixing is detected

4. **Preventive Measures**:
   - Log detailed information about ability mixing
   - In future versions, automatically remove mixed abilities

## Usage

The system is automatically applied at application startup through the combat resolver patch system. No manual intervention is needed.

## Testing

Run the validation tests to verify the system is working:

```bash
python tests/run_ability_mixing_tests.py
```

## Future Improvements

1. **Automatic Ability Correction**:
   - Instead of just detecting mixing, automatically remove abilities that don't belong
   - Replace with appropriate abilities from the monster's own set

2. **UI Warning**:
   - Add a user interface element to show when ability mixing has been detected
   - Allow manual correction

3. **Enhanced Logging**:
   - More detailed logs to help identify the source of ability mixing
   - Statistics on frequency and patterns

## Troubleshooting

If you notice monster ability mixing still occurring:

1. Check the debug log for warnings from the validator
2. Ensure the patches are being properly applied during startup
3. Verify that monster data is correctly formatted in the database

For persistent issues, refer to the integration tests which demonstrate correct behavior. 