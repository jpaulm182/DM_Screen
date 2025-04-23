# Dynamic DM Screen

A comprehensive digital Dungeon Master's companion for D&D 5e, providing instant access to crucial information while offering powerful tools for dynamic content generation and campaign management.

## Features

- **Combat Tracker**: Manage initiative, HP, and conditions for player characters and monsters
- **Monster Database**: Quick access to monster stats and abilities
- **NPC Generator**: Create custom NPCs with detailed personalities and backgrounds
- **Encounter Builder**: Design balanced combat encounters for your party
- **Dice Roller**: Integrated dice rolling with history and statistics
- **Session Notes**: Take and organize campaign notes with character and encounter links
- **Rules Reference**: Quick access to common rules and spells
- **Map Viewer**: Display maps with fog of war and tokens
- **Music & Ambiance**: Integrated audio player for setting the mood

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/your-username/DM_Screen_New.git
   cd DM_Screen_New
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Run the application:
   ```bash
   python main.py
   ```

## Recent Improvements

### Monster Ability Validation System

The application now includes a monster ability validation system that prevents monsters from using abilities that belong to other monsters in combat. This ensures that each monster uses only its own abilities, maintaining tactical integrity and game balance.

Key features of this system:
- Automatic detection of ability mixing between monsters
- Logging of detected issues for troubleshooting
- Clean tagging of abilities to their respective monsters

For more information, see the [Monster Ability Validation documentation](docs/monster_ability_validation.md).

## Development

### Running Tests

Run all tests:
```bash
python -m unittest discover -s tests
```

Run specific test modules:
```bash
python -m unittest tests.core.test_monster_ability_validator
python -m unittest tests.core.test_combat_ability_mixing
```

Run ability mixing tests specifically:
```bash
python tests/run_ability_mixing_tests.py
```

### Project Structure

- `app/`: Main application code
  - `core/`: Core application logic
    - `models/`: Data models
    - `utils/`: Utility functions
    - `combat_resolver.py`: Combat resolution system
  - `ui/`: User interface components
  - `data/`: Data handling and persistence
  - `combat/`: Combat-related functionality
- `tests/`: Test code
- `docs/`: Documentation
- `data/`: Application data

## Documentation

For more information on specific features:

- [Project Specification](specification.md)
- [Monster Ability Validation](docs/monster_ability_validation.md)
- [Action Economy System](app/combat/README_action_economy.md)

## License

This project is licensed under the MIT License - see the LICENSE file for details. 