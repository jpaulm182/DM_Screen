#!/usr/bin/env python3
"""
Test script for combat resolution

This script isolates the combat resolution functionality to help diagnose
segmentation faults and crashes.
"""

import sys
import logging
import gc
import os
import time
import traceback
import random
from pathlib import Path

# Add debug environment variables
os.environ["PYTHONMALLOC"] = "debug"
os.environ["PYTHONFAULTHANDLER"] = "1"

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('test_combat.log', 'w')
    ]
)
logger = logging.getLogger("test_combat")

# Add the app directory to the Python path
app_dir = Path(__file__).parent
sys.path.append(str(app_dir))

# Force garbage collection
gc.collect()

# Import app components
try:
    from app.core.app_state import AppState
    from app.core.combat_resolver import CombatResolver
    from app.core.patched_app_state import apply_patches
    
    # Apply stability patches
    apply_patches()
    
    logger.info("Imports successful")
except ImportError as e:
    logger.error(f"Import error: {e}")
    sys.exit(1)

def dice_roller(expression):
    """Simple dice roller function"""
    logger.info(f"Rolling dice: {expression}")
    
    # Parse dice expression like "2d6+3"
    try:
        if 'd' not in expression:
            return int(expression)
            
        parts = expression.split('d')
        num_dice = int(parts[0]) if parts[0] else 1
        
        # Handle modifiers
        if '+' in parts[1]:
            dice_parts = parts[1].split('+')
            dice_type = int(dice_parts[0])
            modifier = int(dice_parts[1])
        elif '-' in parts[1]:
            dice_parts = parts[1].split('-')
            dice_type = int(dice_parts[0])
            modifier = -int(dice_parts[1])
        else:
            dice_type = int(parts[1])
            modifier = 0
            
        # Roll the dice
        result = sum(random.randint(1, dice_type) for _ in range(num_dice)) + modifier
        logger.info(f"Dice result: {result}")
        return result
    except Exception as e:
        logger.error(f"Error rolling dice: {e}")
        return 10  # Fallback result

def create_test_combat_state():
    """Create a test combat state with a few combatants"""
    logger.info("Creating test combat state")
    
    state = {
        "round": 1,
        "current_turn_index": 0,
        "combatants": [
            # A player character
            {
                "name": "Test Fighter",
                "type": "character",
                "initiative": 18,
                "hp": 50,
                "max_hp": 50,
                "ac": 17,
                "status": "",
                "stats": {
                    "str": 16,
                    "dex": 14,
                    "con": 16,
                    "int": 10,
                    "wis": 12,
                    "cha": 8
                },
                "attacks": [
                    {"name": "Longsword", "bonus": 5, "damage": "1d8+3"}
                ]
            },
            # A monster
            {
                "name": "Goblin",
                "type": "monster",
                "initiative": 14,
                "hp": 7,
                "max_hp": 7,
                "ac": 15,
                "status": "",
                "stats": {
                    "str": 8,
                    "dex": 14,
                    "con": 10,
                    "int": 10,
                    "wis": 8,
                    "cha": 8
                },
                "attacks": [
                    {"name": "Scimitar", "bonus": 4, "damage": "1d6+2"}
                ]
            }
        ]
    }
    
    logger.info(f"Test combat state created with {len(state['combatants'])} combatants")
    return state

def ui_callback(state):
    """Simple callback for UI updates"""
    combatants = state.get("combatants", [])
    latest_action = state.get("latest_action", {})
    
    logger.info("UI update:")
    logger.info(f"Round: {state.get('round', 0)}")
    logger.info(f"Current turn: {state.get('current_turn_index', 0)}")
    
    if latest_action:
        logger.info(f"Latest action: {latest_action.get('actor', 'Unknown')} - {latest_action.get('action', 'No action')}")
    
    logger.info("Combatants:")
    for c in combatants:
        logger.info(f"  {c.get('name', 'Unknown')}: HP {c.get('hp', 0)}/{c.get('max_hp', 0)}")
    
    # Add a small delay to simulate UI
    time.sleep(0.5)

def process_result(result, error):
    """Process the result from combat resolution"""
    if error:
        logger.error(f"Combat resolution error: {error}")
        return
        
    if not result:
        logger.error("No result returned from combat resolution")
        return
        
    logger.info("Combat resolution completed successfully")
    logger.info(f"Narrative: {result.get('narrative', 'No narrative')}")
    logger.info(f"Rounds: {result.get('rounds', 0)}")
    
    # Print log entries
    log_entries = result.get("log", [])
    logger.info(f"Combat log entries: {len(log_entries)}")
    for i, entry in enumerate(log_entries):
        logger.info(f"  {i+1}. {entry.get('actor', 'Unknown')}: {entry.get('action', 'No action')}")

def main():
    """Main test function"""
    logger.info("Starting combat resolution test")
    
    try:
        # Create app state
        logger.info("Initializing app state")
        app_state = AppState()
        
        # Check if the combat resolver was patched
        if hasattr(app_state.combat_resolver, '_safe_api_call'):
            logger.info("Combat resolver successfully patched")
        else:
            logger.warning("Combat resolver not patched")
        
        # Create test combat state
        combat_state = create_test_combat_state()
        
        # Force garbage collection before combat
        gc.collect()
        
        # Get a reference to the resolver
        resolver = app_state.combat_resolver
        
        # Set up callback for results
        resolver.resolution_complete.connect(process_result)
        
        # Run the combat resolution
        logger.info("Starting combat resolution")
        resolver.resolve_combat_turn_by_turn(
            combat_state=combat_state,
            dice_roller=dice_roller,
            callback=None,  # Using signal instead
            update_ui_callback=ui_callback
        )
        
        # Wait for combat to complete (simple approach)
        logger.info("Waiting for combat to complete...")
        for _ in range(60):  # Wait up to 60 seconds
            time.sleep(1)
            gc.collect()  # Force garbage collection every second
        
        logger.info("Test completed")
        
    except Exception as e:
        logger.error(f"Error in test: {e}")
        logger.error(traceback.format_exc())
        
if __name__ == "__main__":
    main() 