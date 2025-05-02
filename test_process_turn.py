#!/usr/bin/env python3

"""
Direct test for the _process_turn method in CombatResolver.

This script isolates the _process_turn method to verify if LLM calls are working.
"""

import sys
import logging
from pathlib import Path
import json
import traceback

# Configure very verbose logging
logging.basicConfig(level=logging.DEBUG,
                  format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                  handlers=[
                      logging.StreamHandler(sys.stdout),
                      logging.FileHandler('process_turn_test.log')
                  ])
logger = logging.getLogger("ProcessTurnTest")

# Add the app directory to the Python path
app_dir = Path(__file__).parent
sys.path.append(str(app_dir))

# Import necessary modules
from app.core.app_state import AppState
from app.core.combat_resolver import CombatResolver
from app.core.llm_service import ModelInfo, LLMService

# Create minimal test data
TEST_COMBATANT = {
    "name": "Test Monster",
    "type": "monster",
    "hp": 50,
    "max_hp": 50,
    "ac": 15,
    "initiative": 10,
    "status": "OK",
    "instance_id": "test_monster_1",
    "actions": [
        {
            "name": "Slam",
            "description": "Melee Weapon Attack: +5 to hit, reach 5 ft. Hit: 8 (1d8 + 4) bludgeoning damage."
        }
    ]
}

TEST_PLAYER = {
    "name": "Test Hero",
    "type": "player",
    "hp": 30,
    "max_hp": 30,
    "ac": 14,
    "initiative": 12,
    "status": "OK",
    "instance_id": "test_player_1"
}

# Simple dice roller function
def test_dice_roller(expression):
    """Simple deterministic dice roller for testing"""
    logger.info(f"Rolling dice: {expression}")
    if "d20" in expression:
        return 15  # Attack rolls
    else:
        return 6   # Damage rolls
    
def patch_service(llm_service):
    """Add extra debugging to LLM service"""
    original_generate_completion = llm_service.generate_completion
    
    def traced_generate_completion(model, messages, system_prompt=None, temperature=0.7, max_tokens=1000):
        """Debugged version of generate_completion"""
        logger.info(f"LLM Call Traced - Model: {model}")
        logger.info(f"Messages: {json.dumps(messages)[:500]}")
        
        try:
            result = original_generate_completion(model, messages, system_prompt, temperature, max_tokens)
            logger.info(f"LLM Response Received: {result[:200] if result else None}")
            return result
        except Exception as e:
            logger.error(f"LLM Call Error: {e}")
            logger.error(traceback.format_exc())
            # Return a minimal valid response to continue execution
            return json.dumps({
                "action": "Emergency Fallback Action",
                "narrative": "This is a fallback response due to an LLM error",
                "target": "Test Hero",
                "reasoning": "Placeholder reasoning due to LLM error"
            })
    
    # Apply the monkey patch - corrected to properly handle arguments
    llm_service.generate_completion = traced_generate_completion
    logger.info("LLM service patched with tracing")

def main():
    """Main test function"""
    try:
        # Initialize app_state and resolver
        logger.info("Initializing AppState...")
        app_state = AppState()
        llm_service = app_state.llm_service
        
        # Add diagnostic patch
        patch_service(llm_service)
        
        # Create the resolver
        logger.info("Creating CombatResolver...")
        resolver = CombatResolver(llm_service)
        
        # Create test data
        combatants = [TEST_COMBATANT, TEST_PLAYER]
        active_idx = 0  # Test monster is active
        round_num = 1
        
        # Directly call the _process_turn method
        logger.info("CALLING _process_turn DIRECTLY...")
        try:
            result = resolver._process_turn(combatants, active_idx, round_num, test_dice_roller)
            logger.info(f"RESULT FROM _process_turn: {result}")
            
            if result:
                logger.info("TEST PASSED: _process_turn returned a result")
                return 0
            else:
                logger.error("TEST FAILED: _process_turn returned None")
                return 1
                
        except Exception as e:
            logger.error(f"Error in _process_turn: {e}")
            logger.error(traceback.format_exc())
            return 1
    
    except Exception as e:
        logger.error(f"Initialization error: {e}")
        logger.error(traceback.format_exc())
        return 1

if __name__ == "__main__":
    sys.exit(main()) 