#!/usr/bin/env python3

"""
Debug script to trace LLM API calls in combat resolution.

This script creates a simple combat scenario and directly invokes the combat resolver
to verify that LLM calls are being made and responses are actually received.
"""

import sys
import logging
from pathlib import Path
import json
import traceback

# Configure logging
logging.basicConfig(level=logging.DEBUG, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Combat-LLM-Debug")

# Add the app directory to the Python path
app_dir = Path(__file__).parent
sys.path.append(str(app_dir))

# Import necessary modules
from app.core.app_state import AppState
from app.core.combat_resolver import CombatResolver
from app.core.llm_service import ModelInfo

# Create a simple combat state for testing
TEST_COMBAT_STATE = {
    "round": 1,
    "combatants": [
        {
            "name": "Infernal Tyrant",
            "type": "monster",
            "hp": 100,
            "max_hp": 100,
            "ac": 18,
            "initiative": 18,
            "status": "OK",
            "instance_id": "monster_1",
            "actions": [
                {
                    "name": "Multiattack",
                    "description": "The tyrant makes two attacks with its claws."
                },
                {
                    "name": "Claw",
                    "description": "Melee Weapon Attack: +8 to hit, reach 5 ft. Hit: 10 (1d10 + 5) slashing damage."
                },
                {
                    "name": "Infernal Blast",
                    "description": "The tyrant unleashes a blast of hellfire. Each creature in a 15-foot cone must make a DC 15 Dexterity saving throw, taking 14 (4d6) fire damage on a failed save, or half as much damage on a successful one."
                }
            ]
        },
        {
            "name": "Heroic Fighter",
            "type": "player",
            "hp": 75,
            "max_hp": 75,
            "ac": 17,
            "initiative": 15,
            "status": "OK",
            "instance_id": "player_1"
        }
    ]
}

# Simple dice roller function for testing
def test_dice_roller(dice_expression):
    """Return a simple fixed value for dice rolls during testing"""
    logger.info(f"Rolling dice: {dice_expression}")
    if "d20" in dice_expression:
        return 15  # Attack rolls and saving throws
    elif "d10" in dice_expression:
        return 10  # Claw damage
    elif "d6" in dice_expression:
        return 12  # Fire damage
    else:
        return 5   # Default for any other dice
    
# Callback function for updates
def update_callback(state):
    """Print updates from combat resolution"""
    logger.info(f"Combat update received: round {state.get('round', 0)}")
    if 'latest_action' in state:
        action = state['latest_action']
        logger.info(f"Action: {action.get('action', 'Unknown')}")
        logger.info(f"Result: {action.get('result', 'No result')}")

# Monkeypatch LLMService.generate_completion to track calls
def patch_llm_service(app_state):
    """Add tracing to LLM service calls"""
    from app.core.llm_service import LLMService
    
    original_generate_completion = LLMService.generate_completion
    
    def traced_generate_completion(self, model, messages, system_prompt=None, temperature=0.7, max_tokens=1000):
        """Trace all LLM service calls"""
        logger.info(f"### LLM CALL TRACED ###")
        logger.info(f"Model: {model}")
        logger.info(f"Temperature: {temperature}")
        logger.info(f"Max tokens: {max_tokens}")
        logger.info(f"Message count: {len(messages)}")
        
        try:
            result = original_generate_completion(self, model, messages, system_prompt, temperature, max_tokens)
            logger.info(f"### LLM RESPONSE RECEIVED ###")
            logger.info(f"Response length: {len(result) if result else 0}")
            logger.info(f"Response preview: {result[:50] if result else 'None'}")
            return result
        except Exception as e:
            logger.error(f"### LLM CALL ERROR ###")
            logger.error(f"Error: {e}")
            logger.error(traceback.format_exc())
            raise
    
    # Apply the patch
    LLMService.generate_completion = traced_generate_completion
    logger.info("LLM service tracing enabled")

def main():
    """Main debug function"""
    try:
        logger.info("Initializing app state...")
        app_state = AppState()
        
        # Apply tracing patch to LLM service
        patch_llm_service(app_state)
        
        # Confirm we can see models
        llm_service = app_state.llm_service
        available_models = llm_service.get_available_models()
        logger.info(f"Available models: {available_models}")
        
        # Create resolver
        logger.info("Creating combat resolver...")
        resolver = CombatResolver(llm_service)
        
        # Verify test LLM service works
        success, test_result = resolver.test_llm_service()
        logger.info(f"LLM test result: {success}, Response: {test_result}")
        
        if not success:
            logger.error("LLM test failed, aborting combat test")
            return 1
        
        # Start resolution with test state
        logger.info("Starting combat resolution...")
        result = resolver.start_resolution(
            TEST_COMBAT_STATE,
            test_dice_roller,
            update_callback,
            mode='step'  # Use step mode to analyze one turn at a time
        )
        
        logger.info(f"Resolution started: {result}")
        
        # Wait for first step
        # This would typically pause in step mode
        input("Press Enter to continue turn...")
        
        # Continue the next turn
        logger.info("Continuing turn...")
        resolver.continue_turn()
        
        # Wait for user to see results
        input("Press Enter to exit...")
        
        # Stop and clean up
        resolver.stop_resolution()
        
        return 0
    
    except Exception as e:
        logger.error(f"Error in debug script: {e}")
        logger.error(traceback.format_exc())
        return 1

if __name__ == "__main__":
    sys.exit(main()) 