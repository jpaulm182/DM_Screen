#!/usr/bin/env python3

"""
LLM Call Monitor for Combat Resolver

This script patches the LLM service to log all calls and responses during combat resolution.
Import and call init_monitoring() from your main application to enable detailed monitoring.
"""

import sys
import logging
import os
from pathlib import Path
import json
import time
import functools

# Configure logging
logging.basicConfig(level=logging.DEBUG,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                   handlers=[
                       logging.StreamHandler(),
                       logging.FileHandler('llm_calls.log')
                   ])
logger = logging.getLogger("LLM-Monitor")

# Add the app directory to the Python path
app_dir = Path(__file__).parent
sys.path.append(str(app_dir))

# Output directory for call logs
output_dir = None
call_counter = 0

def _create_output_dir():
    """Create a timestamped output directory for call logs"""
    global output_dir
    output_dir = app_dir / f"llm_logs_{int(time.time())}"
    os.makedirs(output_dir, exist_ok=True)
    logger.info(f"Created output directory for LLM logs: {output_dir}")
    return output_dir

def patch_llm_service():
    """
    Patch the LLM service to log all calls and responses.
    """
    try:
        from app.core.llm_service import LLMService, ModelInfo
        
        # Save the original generate_completion method
        original_generate_completion = LLMService.generate_completion
        
        # Create a wrapper that logs calls and responses
        @functools.wraps(original_generate_completion)
        def logged_generate_completion(self, model, messages, system_prompt=None, temperature=0.7, max_tokens=1000):
            global call_counter
            call_counter += 1
            
            # Create a unique ID for this call
            call_id = f"call_{call_counter:04d}"
            
            # Log the call details
            logger.info(f"[{call_id}] LLM Call - Model: {model}")
            
            # Save the call to a JSON file
            call_data = {
                "timestamp": time.time(),
                "call_id": call_id,
                "model": model,
                "messages": messages,
                "system_prompt": system_prompt,
                "temperature": temperature,
                "max_tokens": max_tokens
            }
            
            call_file = output_dir / f"{call_id}_request.json"
            with open(call_file, 'w') as f:
                json.dump(call_data, f, indent=2)
            
            logger.info(f"[{call_id}] Saved call details to {call_file}")
            
            # Make the actual call
            try:
                start_time = time.time()
                logger.info(f"[{call_id}] Sending request to LLM service...")
                
                # Call the original method
                response = original_generate_completion(self, model, messages, system_prompt, temperature, max_tokens)
                
                end_time = time.time()
                elapsed = end_time - start_time
                
                logger.info(f"[{call_id}] LLM response received in {elapsed:.2f}s")
                
                # Save the response to a JSON file
                response_data = {
                    "timestamp": time.time(),
                    "call_id": call_id,
                    "elapsed_seconds": elapsed,
                    "response_length": len(response) if response else 0,
                    "response": response
                }
                
                response_file = output_dir / f"{call_id}_response.json"
                with open(response_file, 'w') as f:
                    json.dump(response_data, f, indent=2)
                
                logger.info(f"[{call_id}] Saved response to {response_file}")
                
                return response
            except Exception as e:
                logger.error(f"[{call_id}] Error in LLM call: {e}")
                
                # Save the error to a JSON file
                error_data = {
                    "timestamp": time.time(),
                    "call_id": call_id,
                    "error": str(e),
                    "error_type": type(e).__name__
                }
                
                error_file = output_dir / f"{call_id}_error.json"
                with open(error_file, 'w') as f:
                    json.dump(error_data, f, indent=2)
                
                logger.error(f"[{call_id}] Saved error details to {error_file}")
                
                # Re-raise the exception
                raise
        
        # Replace the original method with our logged version
        LLMService.generate_completion = logged_generate_completion
        logger.info("Patched LLM service with logging wrapper")
        
        return True
    except ImportError as e:
        logger.error(f"Failed to import LLMService: {e}")
        return False
    except Exception as e:
        logger.error(f"Error patching LLM service: {e}", exc_info=True)
        return False

def patch_combat_resolver():
    """
    Patch the CombatResolver to add extra logging around turn processing.
    """
    try:
        from app.core.combat_resolver import CombatResolver
        
        # Save the original _process_turn method
        original_process_turn = CombatResolver._process_turn
        
        # Create a wrapper with additional logging
        @functools.wraps(original_process_turn)
        def logged_process_turn(self, local_combatants_list, active_idx, round_num, dice_roller):
            logger.info(f"[CombatResolver] _process_turn ENTRY - idx={active_idx}, round={round_num}")
            active_combatant = local_combatants_list[active_idx] if 0 <= active_idx < len(local_combatants_list) else None
            combatant_name = active_combatant.get('name', 'Unknown') if active_combatant else 'Unknown'
            logger.info(f"[CombatResolver] Processing turn for: {combatant_name}")
            
            try:
                # Call the original method
                result = original_process_turn(self, local_combatants_list, active_idx, round_num, dice_roller)
                
                # Log the result
                result_info = {
                    "success": bool(result),
                    "has_narrative": "narrative" in result if result else False,
                    "narrative_length": len(result.get("narrative", "")) if result and "narrative" in result else 0,
                    "has_action": "action" in result if result else False,
                    "action": result.get("action", None) if result else None
                }
                logger.info(f"[CombatResolver] _process_turn EXIT - Result: {json.dumps(result_info)}")
                
                # Save the full result to a file
                if result:
                    result_file = output_dir / f"turn_result_{combatant_name}_{round_num}.json"
                    with open(result_file, 'w') as f:
                        # Convert result to a serializable format
                        serializable_result = json.dumps(result, default=str)
                        f.write(serializable_result)
                    logger.info(f"[CombatResolver] Saved turn result to {result_file}")
                
                return result
            except Exception as e:
                logger.error(f"[CombatResolver] Error in _process_turn: {e}", exc_info=True)
                
                # Save the error details
                error_data = {
                    "timestamp": time.time(),
                    "combatant": combatant_name,
                    "round": round_num,
                    "error": str(e),
                    "error_type": type(e).__name__
                }
                
                error_file = output_dir / f"turn_error_{combatant_name}_{round_num}.json"
                with open(error_file, 'w') as f:
                    json.dump(error_data, f, indent=2)
                
                logger.error(f"[CombatResolver] Saved error details to {error_file}")
                
                # Re-raise the exception
                raise
        
        # Replace the original method with our logged version
        CombatResolver._process_turn = logged_process_turn
        logger.info("Patched CombatResolver._process_turn with logging wrapper")
        
        # Now also patch _parse_llm_json_response for additional insights
        original_parse_llm = CombatResolver._parse_llm_json_response
        
        @functools.wraps(original_parse_llm)
        def logged_parse_llm(self, response_text, context=""):
            logger.info(f"[CombatResolver] Parsing LLM JSON response for context: {context}")
            logger.info(f"[CombatResolver] Response text first 100 chars: {response_text[:100] if response_text else 'None'}")
            
            try:
                result = original_parse_llm(self, response_text, context)
                
                # Log the result
                success = not (isinstance(result, dict) and "error" in result)
                logger.info(f"[CombatResolver] Parse result success: {success}")
                
                if not success and isinstance(result, dict):
                    logger.error(f"[CombatResolver] Parse error: {result.get('error', 'Unknown error')}")
                    
                # Save parse result to file
                parse_file = output_dir / f"parse_result_{context}_{int(time.time())}.json"
                with open(parse_file, 'w') as f:
                    json.dump({
                        "context": context,
                        "success": success,
                        "result": result,
                        "response_text_length": len(response_text) if response_text else 0,
                        "response_preview": response_text[:200] if response_text else None
                    }, f, indent=2, default=str)
                
                return result
            except Exception as e:
                logger.error(f"[CombatResolver] Error parsing LLM JSON: {e}", exc_info=True)
                
                # Save the error and response text
                error_file = output_dir / f"parse_error_{context}_{int(time.time())}.txt"
                with open(error_file, 'w') as f:
                    f.write(f"ERROR: {str(e)}\n\n")
                    f.write("RESPONSE TEXT:\n")
                    f.write(response_text if response_text else "None")
                
                # Re-raise to preserve original behavior
                raise
        
        # Replace the original parse method
        CombatResolver._parse_llm_json_response = logged_parse_llm
        logger.info("Patched CombatResolver._parse_llm_json_response with logging wrapper")
        
        return True
    except ImportError as e:
        logger.error(f"Failed to import CombatResolver: {e}")
        return False
    except Exception as e:
        logger.error(f"Error patching CombatResolver: {e}", exc_info=True)
        return False

def monitor_ui_updates():
    """
    Patch the UI update methods to track if results are making it to the UI.
    """
    try:
        from app.ui.panels.combat_tracker.facade import CombatTrackerPanel
        
        # Patch _update_ui_wrapper
        original_update_wrapper = CombatTrackerPanel._update_ui_wrapper
        
        @functools.wraps(original_update_wrapper)
        def logged_update_wrapper(self, turn_state):
            logger.info(f"[UI] _update_ui_wrapper called with turn state")
            if turn_state:
                current_turn = turn_state.get("current_turn_index", -1)
                round_num = turn_state.get("round", -1)
                combatants = turn_state.get("combatants", [])
                logger.info(f"[UI] Turn state - Round: {round_num}, Turn: {current_turn}, Combatants: {len(combatants)}")
                
                # Log latest action if present
                latest_action = turn_state.get("latest_action", {})
                if latest_action:
                    actor = latest_action.get("actor", "Unknown")
                    action = latest_action.get("action", "Unknown action")
                    logger.info(f"[UI] Latest action - Actor: {actor}, Action: {action}")
                    
                    # Save action to file
                    action_file = output_dir / f"ui_action_{actor}_{round_num}_{int(time.time())}.json"
                    with open(action_file, 'w') as f:
                        json.dump(latest_action, f, indent=2, default=str)
            
            # Call original method
            result = original_update_wrapper(self, turn_state)
            return result
        
        # Replace the original method
        CombatTrackerPanel._update_ui_wrapper = logged_update_wrapper
        logger.info("Patched CombatTrackerPanel._update_ui_wrapper with logging wrapper")
        
        # Also patch _update_ui to track JSON deserialization
        original_update_ui = CombatTrackerPanel._update_ui
        
        @functools.wraps(original_update_ui)
        def logged_update_ui(self, turn_state_json):
            logger.info(f"[UI] _update_ui called with JSON of length {len(turn_state_json) if turn_state_json else 0 if isinstance(turn_state_json, str) else 'N/A (dict)'}")
            
            # Save the JSON to check what's coming in
            json_file = output_dir / f"ui_json_{int(time.time())}.json"
            with open(json_file, 'w') as f:
                # Fix: Convert dictionary to string using json.dumps if it's a dict
                if isinstance(turn_state_json, dict):
                    try:
                        f.write(json.dumps(turn_state_json, default=str, indent=2))
                        logger.info(f"[UI] Saved dictionary input as JSON to {json_file}")
                    except Exception as e:
                        logger.error(f"[UI] Error converting dictionary to JSON: {e}")
                        f.write(f"ERROR: Failed to serialize: {str(e)}\nOriginal data: {str(turn_state_json)}")
                else:
                    f.write(turn_state_json if turn_state_json else "None")
                    logger.info(f"[UI] Saved string input to {json_file}")
            
            # Call original method
            try:
                result = original_update_ui(self, turn_state_json)
                logger.info("[UI] _update_ui completed successfully")
                return result
            except Exception as e:
                logger.error(f"[UI] Error in _update_ui: {e}", exc_info=True)
                # Re-raise to preserve original behavior
                raise
        
        # Replace the original method
        CombatTrackerPanel._update_ui = logged_update_ui
        logger.info("Patched CombatTrackerPanel._update_ui with logging wrapper")
        
        return True
    except ImportError as e:
        logger.error(f"Failed to import CombatTrackerPanel: {e}")
        return False
    except Exception as e:
        logger.error(f"Error patching UI methods: {e}", exc_info=True)
        return False

def init_monitoring():
    """Initialize all monitoring patches"""
    global output_dir
    
    logger.info("Starting LLM call monitoring setup")
    
    # HOTFIX - DISABLE MONITORING TO PREVENT CRASHES
    logger.warning("LLM monitoring has been disabled to prevent crashes")
    return False
    
    # Comment out the rest of the function
    """
    # Create output directory
    _create_output_dir()
    
    # Apply patches
    llm_patched = patch_llm_service()
    combat_patched = patch_combat_resolver()
    ui_patched = monitor_ui_updates()
    
    logger.info(f"Monitoring initialization complete:")
    logger.info(f"- LLM service patched: {llm_patched}")
    logger.info(f"- Combat resolver patched: {combat_patched}")
    logger.info(f"- UI updates monitored: {ui_patched}")
    logger.info(f"All LLM calls will be logged to: {output_dir}")
    
    return llm_patched or combat_patched or ui_patched
    """

def main():
    """Main function when run as a script"""
    success = init_monitoring()
    if success:
        logger.info("LLM monitoring setup complete. Import this module and call init_monitoring() in your main.py")
        logger.info("Example: import monitor_llm_calls; monitor_llm_calls.init_monitoring()")
    else:
        logger.error("Failed to set up LLM monitoring")

if __name__ == "__main__":
    main() 