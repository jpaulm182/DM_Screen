"""
Patching module for the combat resolver

This module provides patches for the CombatResolver class to enhance
error handling, memory tracking, and debugging during combat resolution.
"""

import logging
import traceback
import gc
import sys
from functools import wraps
import time
import threading
import functools

# Import the monster ability validator
from app.core.utils.monster_ability_validator import (
    validate_combat_prompt,
    clean_abilities_in_prompt,
    fix_mixed_abilities_in_prompt
)

logger = logging.getLogger("combat_resolver_patch")

# Process-wide lock for OpenAI API calls by model ID
_openai_api_locks = {
    "default": threading.RLock()
}

_active_resolutions = set()
_resolution_lock = threading.RLock()

# Last problem detection time to avoid spam
_last_warning_time = 0
_warning_interval = 30.0  # seconds

def patch_process_turn(combat_resolver_instance):
    """
    Patch the _process_turn method of the combat resolver to add debugging
    
    Args:
        combat_resolver_instance: The CombatResolver instance to patch
    """
    logger.info("Patching _process_turn method in CombatResolver")
    
    # Store the original method
    original_process_turn = combat_resolver_instance._process_turn
    
    # Define the patched method
    @wraps(original_process_turn)
    def patched_process_turn(combatants, active_idx, round_num, dice_roller):
        """Patched version of _process_turn with enhanced debugging"""
        # Basic validation to prevent crashes
        if active_idx >= len(combatants):
            logger.error(f"Invalid combatant index: {active_idx} (max: {len(combatants)-1})")
            return {
                "action": "Error: Invalid combatant index",
                "narrative": "An error occurred while processing this turn.",
                "dice": [],
                "updates": []
            }
        
        active_combatant = combatants[active_idx]
        combatant_name = active_combatant.get('name', 'Unknown')
        
        logger.info(f"=== TURN START: {combatant_name} (Round {round_num}) ===")
        
        # Track memory at start of turn
        if hasattr(combat_resolver_instance, '_track_memory'):
            combat_resolver_instance._track_memory(f"start_of_turn_{combatant_name}_{round_num}")
        
        # Dump stack trace for debugging
        stack_trace = ''.join(traceback.format_stack())
        logger.debug(f"Call stack entering _process_turn:\n{stack_trace}")
        
        try:
            # Try to run the original method with detailed state tracking
            logger.info(f"Processing turn for {combatant_name}")
            
            # Dump combatant state before processing
            try:
                import json
                logger.debug(f"Combatant state: {json.dumps(active_combatant, indent=2)}")
            except:
                logger.debug(f"Combatant state: {active_combatant}")
                
            # Force garbage collection before API calls
            gc.collect()
                
            # Run the original method with extensive try/except wrapping
            try:
                result = original_process_turn(combatants, active_idx, round_num, dice_roller)
                logger.info(f"Turn completed successfully for {combatant_name}")
                return result
            except Exception as e:
                logger.error(f"Error in original _process_turn for {combatant_name}: {str(e)}")
                logger.error(traceback.format_exc())
                
                # Return fallback result to prevent crash
                if hasattr(combat_resolver_instance, '_generate_fallback_decision'):
                    logger.info(f"Generating fallback decision for {combatant_name}")
                    return combat_resolver_instance._generate_fallback_decision(active_combatant)
                else:
                    logger.info(f"Using basic fallback for {combatant_name}")
                    return {
                        "action": f"{combatant_name} takes a defensive stance due to an error.",
                        "narrative": "Due to an unexpected error, the combatant takes a defensive stance.",
                        "dice": [],
                        "updates": []
                    }
        except Exception as outer_e:
            # This is a critical failure in our patch itself
            logger.critical(f"Critical error in patched _process_turn: {str(outer_e)}")
            logger.critical(traceback.format_exc())
            
            # Absolutely minimal fallback that should never fail
            return {
                "action": "Error occurred",
                "narrative": "A critical error occurred. The combatant takes no action.",
                "dice": [],
                "updates": []
            }
        finally:
            # Always track memory at end of turn
            if hasattr(combat_resolver_instance, '_track_memory'):
                combat_resolver_instance._track_memory(f"end_of_turn_{combatant_name}_{round_num}")
            
            # Always dump active API calls for debugging
            if hasattr(combat_resolver_instance, '_dump_active_calls'):
                combat_resolver_instance._dump_active_calls()
                
            logger.info(f"=== TURN END: {combatant_name} (Round {round_num}) ===")
    
    # Apply the patch
    combat_resolver_instance._process_turn = patched_process_turn
    logger.info("Successfully patched _process_turn method")


def patch_combat_resolver(resolver_instance):
    """Apply all patches to a combat resolver instance"""
    patch_process_turn(resolver_instance)
    
    # Add a patch for the dice roller segmentation fault
    patch_dice_rolling(resolver_instance)
    
    # Add a patch for multi-attack resolution
    patch_multi_attack_resolution(resolver_instance)
    
    # Add a patch for robust JSON parsing
    patch_json_parsing(resolver_instance)
    
    # Add timeout mechanism
    patch_resolution_timeout(resolver_instance)
    
    # Add additional patch methods as needed
    
    return resolver_instance

def patch_dice_rolling(combat_resolver_instance):
    """
    Patch dice rolling to prevent segmentation faults
    
    Args:
        combat_resolver_instance: The CombatResolver instance to patch
    """
    logger.info("Patching dice rolling in CombatResolver")
    
    # Store the original _process_turn method
    original_process_turn = combat_resolver_instance._process_turn
    
    # Define the patched method
    @wraps(original_process_turn)
    def patched_process_turn(combatants, active_idx, round_num, dice_roller):
        """Patched version with safe dice rolling"""
        
        # Create a safe dice roller that won't segfault
        def safe_dice_roller(expression):
            """Safe wrapper for dice roller that handles problematic expressions"""
            try:
                # Handle problematic expression formats
                if expression == "1dY+Z" or "Y" in expression or "Z" in expression or "X" in expression:
                    logger.warning(f"Received invalid dice expression: {expression}, using fallback")
                    # Use a fallback value based on the intent
                    if "damage" in expression.lower():
                        return 8  # Reasonable damage value
                    return 12  # Reasonable attack roll
                
                # Use the original dice roller for valid expressions
                return dice_roller(expression)
            except Exception as e:
                logger.error(f"Error in dice roller: {e}", exc_info=True)
                return 10  # Fallback value
        
        # Call the original method with our safe dice roller
        return original_process_turn(combatants, active_idx, round_num, safe_dice_roller)
    
    # Apply the patch
    combat_resolver_instance._process_turn = patched_process_turn
    logger.info("Successfully patched dice rolling method")

def patch_multi_attack_resolution(combat_resolver_instance):
    """
    Patch the resolution process for multi-attacks to prevent segmentation fault
    
    Args:
        combat_resolver_instance: The CombatResolver instance to patch
    """
    logger.info("Patching multi-attack resolution in CombatResolver")
    
    # Add a special handler for multi-attack patterns in responses
    def fix_multi_attack_response(response_text):
        """
        Fix the response from the LLM to prevent segmentation faults with multi-attacks
        
        Args:
            response_text: The raw response text from the LLM
            
        Returns:
            Fixed response text
        """
        # Skip if not a string
        if not isinstance(response_text, str):
            logger.warning(f"fix_multi_attack_response received non-string: {type(response_text)}")
            return response_text
            
        # Check if this is a multi-attack scenario
        if "multiattack" in response_text.lower() or "multi-attack" in response_text.lower():
            logger.info("Detected multi-attack in response, applying safety fix")
            
            # Ensure the expressions don't have placeholder variables like X, Y, Z
            response_text = response_text.replace('"expression": "1d20+X"', '"expression": "1d20+5"')
            response_text = response_text.replace('"expression": "2d8+X"', '"expression": "2d8+5"')
            response_text = response_text.replace('"expression": "1dY+Z"', '"expression": "1d8+3"')
            response_text = response_text.replace('"expression": "2dY+Z"', '"expression": "2d8+3"')
            response_text = response_text.replace('"expression": "1d8+X"', '"expression": "1d8+3"')
            
            # If more than 2 attack rolls, limit to 2 to prevent memory issues
            import re
            attack_rolls = re.findall(r'"purpose": "[^"]*attack roll[^"]*"', response_text, re.IGNORECASE)
            if len(attack_rolls) > 2:
                logger.warning(f"Found {len(attack_rolls)} attack rolls, limiting to 2 for stability")
                # Keep only first 2 attack patterns
                parts = response_text.split('"dice_requests": [')
                if len(parts) > 1:
                    dice_section = parts[1]
                    # Extract first two attacks and damages (4 dice rolls total)
                    dice_entries = re.findall(r'\{[^}]+\}', dice_section)
                    if len(dice_entries) > 4:
                        # Rebuild with only first 4 entries
                        new_dice_section = ','.join(dice_entries[:4])
                        response_text = f'{parts[0]}"dice_requests": [{new_dice_section}]'
                        # Add back the closing part
                        if response_text.endswith(']'):
                            response_text += '}'
        
        return response_text
    
    # Store the original method
    if hasattr(combat_resolver_instance, 'llm_service') and hasattr(combat_resolver_instance.llm_service, '_generate_openai_completion'):
        original_generate = combat_resolver_instance.llm_service._generate_openai_completion
        
        # Define patched method
        def patched_generate(model, messages, system_prompt, temperature, max_tokens):
            """Patched version that fixes multi-attack responses"""
            try:
                # Call original method
                result = original_generate(model, messages, system_prompt, temperature, max_tokens)
                
                # Only process string results
                if result and isinstance(result, str):
                    # Look for patterns suggesting a multi-attack response
                    if "multiattack" in result.lower() or "multi-attack" in result.lower():
                        # Apply fix
                        result = fix_multi_attack_response(result)
                
                return result
            except Exception as e:
                logger.error(f"Error in patched_generate: {e}", exc_info=True)
                # Re-raise to let regular error handling take over
                raise
        
        # Apply the patch
        combat_resolver_instance.llm_service._generate_openai_completion = patched_generate
        logger.info("Successfully patched OpenAI completion for multi-attacks")
    else:
        logger.warning("Could not patch LLM service, OpenAI completion method not found")
    
    # Also patch the _process_turn method to add extra validation for multi-attacks
    original_process_turn = combat_resolver_instance._process_turn
    
    @wraps(original_process_turn)
    def safer_process_turn(combatants, active_idx, round_num, dice_roller):
        try:
            # Defensive check for round_num
            if not isinstance(round_num, int):
                round_num = 1
                
            # Create a super-safe dice roller that handles completely invalid expressions
            def ultra_safe_dice_roller(expression):
                try:
                    if not expression or not isinstance(expression, str):
                        logger.error(f"Invalid dice expression type: {type(expression)}")
                        return 10
                    
                    # Handle special case for YdZ+W format explicitly (highest priority)
                    if "YdZ+W" in expression:
                        logger.warning(f"Received YdZ+W expression, using reliable fallback")
                        if "damage" in expression.lower():
                            return 12  # Reasonable damage value
                        else:
                            return 15  # Reasonable attack roll with modifier
                    
                    # Replace invalid characters
                    safe_expression = expression
                    for invalid_char in ['X', 'Y', 'Z', 'W', '?', '*', '%']:
                        if invalid_char in safe_expression:
                            # Use appropriate dice value based on context
                            if "d20" in safe_expression:
                                if "+" in safe_expression:
                                    safe_expression = "1d20+5"  # Standard attack bonus
                                else:
                                    safe_expression = "1d20"
                            elif "d8" in safe_expression:
                                if "+" in safe_expression:
                                    safe_expression = "1d8+3"  # Standard damage bonus
                                else:
                                    safe_expression = "1d8"
                            elif "d6" in safe_expression:
                                if "+" in safe_expression:
                                    safe_expression = "1d6+3"
                                else:
                                    safe_expression = "1d6"
                            elif "d4" in safe_expression:
                                if "+" in safe_expression:
                                    safe_expression = "1d4+2"
                                else:
                                    safe_expression = "1d4"
                            elif "d10" in safe_expression:
                                if "+" in safe_expression:
                                    safe_expression = "1d10+3"
                                else:
                                    safe_expression = "1d10"
                            elif "d12" in safe_expression:
                                if "+" in safe_expression:
                                    safe_expression = "1d12+3"
                                else:
                                    safe_expression = "1d12"
                            else:
                                # For attack rolls (used first in multi-attacks)
                                if "attack" in expression.lower():
                                    safe_expression = "1d20+5"
                                # For damage rolls (used after attack rolls)
                                elif "damage" in expression.lower():
                                    safe_expression = "2d6+3"  # Generic fallback damage
                                else:
                                    safe_expression = "1d8+3"  # Generic fallback
                            
                            logger.warning(f"Replacing invalid dice expression '{expression}' with '{safe_expression}'")
                            break
                    
                    # Final safety check - reject expressions with unknown variables
                    if any(c.isalpha() and c not in "d" for c in safe_expression):
                        logger.warning(f"Expression still contains variables after cleaning: {safe_expression}")
                        # Determine reasonable fallback based on context
                        if "attack" in expression.lower():
                            return 15  # Reasonable attack roll
                        elif "damage" in expression.lower():
                            return 12  # Reasonable damage
                        else:
                            return 10  # Generic fallback
                    
                    # Pass the safe expression to the original dice roller
                    result = dice_roller(safe_expression)
                    logger.debug(f"Dice roll for {safe_expression}: {result}")
                    return result
                except Exception as e:
                    logger.error(f"Error in ultra safe dice roller: {e}", exc_info=True)
                    return 10  # Default fallback
            
            # Run the original turn processor with our ultra-safe dice roller
            return original_process_turn(combatants, active_idx, round_num, ultra_safe_dice_roller)
        except Exception as e:
            logger.error(f"Fatal error in safer_process_turn: {e}", exc_info=True)
            # Return minimal fallback result
            return {
                "action": "Error occurred",
                "narrative": "A critical error prevented turn processing.",
                "dice": [],
                "updates": []
            }
    
    # Apply the patch
    combat_resolver_instance._process_turn = safer_process_turn
    logger.info("Successfully applied multi-attack safety patches")

def patch_json_parsing(combat_resolver_instance):
    """
    Patch JSON parsing to make it more robust
    
    Args:
        combat_resolver_instance: The CombatResolver instance to patch
    """
    logger.info("Patching JSON parsing in CombatResolver")
    
    # Find the original method that parses the LLM's decision
    if hasattr(combat_resolver_instance, '_process_turn'):
        import json
        import re
        import sys
        
        # Store the original loads function
        original_loads = json.loads
        
        # Create robust JSON parsing function
        def robust_json_parse(text):
            """Parse JSON robustly, handling common errors"""
            # Basic error handling
            if not text:
                print("Empty JSON text")
                return {
                    "action": "The combatant takes a cautious stance.",
                    "dice_requests": []
                }
                
            try:
                # Try normal parsing first
                return original_loads(text)
            except json.JSONDecodeError as e:
                # Use print instead of logger to avoid recursion
                print(f"JSON decode error: {str(e)[:100]}, attempting robust parsing")
                
                # Clean the JSON text
                cleaned_text = text
                
                # Remove code block markers
                cleaned_text = re.sub(r'```(?:json)?\s*', '', cleaned_text)
                cleaned_text = re.sub(r'```\s*$', '', cleaned_text)
                
                # Extract JSON object if embedded in other text
                json_match = re.search(r'\{[\s\S]*\}', cleaned_text)
                if json_match:
                    cleaned_text = json_match.group(0)
                
                # Fix common JSON syntax errors
                cleaned_text = re.sub(r',\s*}', '}', cleaned_text)  # Remove trailing commas in objects
                cleaned_text = re.sub(r',\s*]', ']', cleaned_text)  # Remove trailing commas in arrays
                
                # Fix unquoted keys
                for key in ["action", "dice_requests", "expression", "purpose"]:
                    cleaned_text = re.sub(rf'([{{\s,]){key}:', rf'\1"{key}":', cleaned_text)
                
                # Fix missing quotes around values
                cleaned_text = re.sub(r':\s*([^"\d\[\]{},\s][^,\[\]{}"\s]*)', r': "\1"', cleaned_text)
                
                try:
                    # Try parsing the cleaned text
                    return original_loads(cleaned_text)
                except json.JSONDecodeError:
                    # Use print instead of logger to avoid recursion
                    print(f"Failed to parse JSON even after cleanup, returning fallback result")
                    
                    # Extract key fields using regex as last resort
                    action_match = re.search(r'"action"\s*:\s*"([^"]+)"', cleaned_text)
                    action = action_match.group(1) if action_match else "The combatant takes a defensive stance."
                    
                    # Create a minimal valid result
                    return {
                        "action": action,
                        "dice_requests": [
                            {"expression": "1d20", "purpose": "Attack roll"},
                            {"expression": "1d8+3", "purpose": "Damage roll"}
                        ]
                    }

        # Create a safe non-recursive patched_loads function
        def patched_loads(text, *args, **kwargs):
            """Non-recursive version of json.loads that handles combat resolver JSON safely"""
            # For bytes input, use the original loads function
            if isinstance(text, bytes):
                try:
                    return original_loads(text, *args, **kwargs)
                except Exception as e:
                    print(f"Error parsing bytes: {e}", file=sys.stderr)
                    return {"action": "Error processing combat", "dice_requests": []}
            
            # For strings, check if it's combat related
            if isinstance(text, str):
                # Handle combat-related JSONs with our robust parser
                if "action" in text and ("dice_requests" in text or "dice" in text):
                    try:
                        # Use our robust parser
                        return robust_json_parse(text)
                    except Exception as e:
                        print(f"Error in robust_json_parse: {e}", file=sys.stderr)
                        # Return minimal valid combat response
                        return {"action": "Error in processing", "dice_requests": []}
                else:
                    # Use the original for non-combat JSONs
                    try:
                        return original_loads(text, *args, **kwargs)
                    except Exception as e:
                        print(f"Error parsing non-combat JSON: {e}", file=sys.stderr)
                        # Try to return something valid
                        return {} if args or kwargs else {}
            
            # For any other type, use original
            try:
                return original_loads(text, *args, **kwargs)
            except Exception:
                print("Unknown JSON parsing error", file=sys.stderr)
                return {}
                
        # Apply the monkey patch
        json.loads = patched_loads
        print("Successfully monkey-patched json.loads for combat resolver - FIXED recursion issue")

def patch_resolution_timeout(combat_resolver_instance):
    """
    Add timeout mechanism for combat resolution
    
    Args:
        combat_resolver_instance: The CombatResolver instance to patch
    """
    logger.info("Adding timeout mechanism to combat resolution")
    
    # Store the original resolve_combat_turn_by_turn method
    original_resolve = combat_resolver_instance.resolve_combat_turn_by_turn
    
    # Define patched method with timeout
    def patched_resolve_combat_turn_by_turn(combat_state, dice_roller, callback, update_ui_callback=None):
        """
        Patched version of resolve_combat_turn_by_turn with timeout
        """
        import threading
        import time
        import gc
        
        logger.info("Starting combat resolution with timeout protection")
        
        # Force garbage collection before starting
        gc.collect()
        
        # Create event for tracking completion
        completion_event = threading.Event()
        result_container = {"result": None, "error": None}
        
        # Create completion callback
        def timeout_completion_callback(result, error):
            result_container["result"] = result
            result_container["error"] = error
            completion_event.set()
            
            # Also call the original callback if provided
            if callback:
                try:
                    callback(result, error)
                except Exception as e:
                    logger.error(f"Error in original callback: {e}", exc_info=True)
        
        # Track connection for cleanup
        connection_made = False
        
        # Connect our callback to the resolution_complete signal
        try:
            # Disconnect any existing connections first
            try:
                # Use a safer approach that doesn't require knowing all receivers
                combat_resolver_instance.resolution_complete.disconnect()
                logger.info("Disconnected all existing signal connections")
            except Exception:
                # This is fine - might not have any connections
                pass
                
            # Make new connection
            combat_resolver_instance.resolution_complete.connect(timeout_completion_callback)
            connection_made = True
            logger.info("Connected timeout_completion_callback to resolution_complete signal")
        except Exception as e:
            logger.error(f"Error connecting signal: {e}", exc_info=True)
            # Continue anyway, we'll rely on manual callback
        
        try:
            # Start the resolution in the normal way
            original_resolve(combat_state, dice_roller, timeout_completion_callback, update_ui_callback)
            
            # Wait for completion with timeout
            max_timeout = 300  # 5 minutes max
            start_time = time.time()
            
            waiting_time = 0
            while not completion_event.is_set() and waiting_time < max_timeout:
                # Wait in small increments
                is_completed = completion_event.wait(5)  # Wait 5 seconds at a time
                waiting_time = time.time() - start_time
                
                if is_completed:
                    logger.info(f"Combat resolution completed normally after {waiting_time:.1f} seconds")
                    break
                    
                # Log progress during wait
                if waiting_time > 30 and waiting_time % 30 < 5:  # Log every ~30 seconds
                    logger.warning(f"Combat resolution still running after {waiting_time:.1f} seconds")
                    
                    # Force garbage collection during long waits
                    gc.collect()
            
            # Handle timeout
            if not completion_event.is_set():
                logger.error(f"Combat resolution timed out after {max_timeout} seconds, forcing completion")
                
                # Force completion with timeout error
                error_msg = f"Combat resolution timed out after {max_timeout} seconds"
                try:
                    combat_resolver_instance.resolution_complete.emit(None, error_msg)
                except Exception as e:
                    logger.error(f"Error emitting timeout signal: {e}", exc_info=True)
                
                # Also call the callback directly in case signal is blocked
                if callback:
                    try:
                        callback(None, error_msg)
                    except Exception as e:
                        logger.error(f"Error in callback after timeout: {e}", exc_info=True)
        finally:
            # Always clean up signal connections
            if connection_made:
                try:
                    combat_resolver_instance.resolution_complete.disconnect(timeout_completion_callback)
                    logger.info("Successfully disconnected timeout_completion_callback")
                except Exception as e:
                    logger.error(f"Error disconnecting signal: {e}", exc_info=True)
                    # Try one more explicit call to the callback for safety
                    if callback and not completion_event.is_set():
                        try:
                            completion_event.set()  # Mark as complete
                            # Call with no result and an error message to make sure it resets the UI
                            callback(None, "Combat resolver was disconnected - forcing UI reset")
                            logger.info("Manually called completion callback after disconnect failure")
                        except Exception as disconnect_callback_error:
                            logger.error(f"Error in manual callback after disconnect failure: {disconnect_callback_error}", exc_info=True)
                    
            # Always force garbage collection at the end
            gc.collect()
    
    # Apply the patch
    combat_resolver_instance.resolve_combat_turn_by_turn = patched_resolve_combat_turn_by_turn
    logger.info("Successfully patched resolve_combat_turn_by_turn with timeout protection")

def combat_resolver_patch(app_state):
    """Apply stability patches to the combat resolver."""
    if not hasattr(app_state, 'combat_resolver'):
        logger.error("Cannot apply combat_resolver_patch: app_state has no combat_resolver")
        return
        
    if hasattr(app_state.combat_resolver, '_patched'):
        logger.info("Combat resolver already patched, skipping")
        return
    
    logger.info("Applying combat resolver patches")
    
    # Patch the _process_turn method to add monitoring
    original_process_turn = app_state.combat_resolver._process_turn
    
    @functools.wraps(original_process_turn)
    def patched_process_turn(combatants, active_idx, round_num, dice_roller):
        """Add monitoring to detect long-running or stuck combat resolution."""
        resolution_id = f"Turn_{round_num}_{active_idx}_{time.time()}"
        
        with _resolution_lock:
            _active_resolutions.add(resolution_id)
        
        start_time = time.time()
        
        def check_timeout():
            global _last_warning_time
            while True:
                elapsed = time.time() - start_time
                
                if resolution_id not in _active_resolutions:
                    # Resolution completed
                    break
                    
                if elapsed > 30.0 and time.time() - _last_warning_time > _warning_interval:
                    # Log warning about long-running resolution
                    _last_warning_time = time.time()
                    logger.warning(f"Combat resolution still running after {elapsed:.1f} seconds")
                
                # Check every 5 seconds
                time.sleep(5.0)
        
        # Start monitoring thread
        monitor_thread = threading.Thread(target=check_timeout, daemon=True)
        monitor_thread.start()
        
        try:
            # Call original method
            result = original_process_turn(combatants, active_idx, round_num, dice_roller)
            return result
        except Exception as e:
            logger.error(f"Error in _process_turn: {str(e)}")
            traceback.print_exc()
            return None
        finally:
            # Remove from active resolutions
            with _resolution_lock:
                if resolution_id in _active_resolutions:
                    _active_resolutions.remove(resolution_id)
    
    # Patch the _create_decision_prompt method to add ability validation
    original_create_decision_prompt = app_state.combat_resolver._create_decision_prompt
    
    @functools.wraps(original_create_decision_prompt)
    def patched_create_decision_prompt(app_state, combat_state, turn_combatant):
        """Add monster ability validation to the decision prompt with automatic correction."""
        # Call original method
        prompt = original_create_decision_prompt(combat_state, turn_combatant)
        
        # Clean the prompt to ensure all abilities have proper tags
        prompt = clean_abilities_in_prompt(prompt)
        
        # Validate the prompt to check for ability mixing
        is_valid, result = validate_combat_prompt(prompt)
        
        if not is_valid:
            # Log the validation failure
            logger.warning(f"Ability mixing detected in prompt: {result}")
            
            # Extract the active monster name for further logging
            import re
            active_monster = "Unknown"
            active_match = re.search(r"Active Combatant: ([A-Za-z0-9_\s]+)", prompt)
            if active_match:
                active_monster = active_match.group(1).strip()
                
            logger.warning(f"Ability mixing affects monster: {active_monster}")
            
            # Apply automatic correction to fix the ability mixing
            logger.info(f"Attempting to automatically correct mixed abilities for {active_monster}")
            fixed_prompt = fix_mixed_abilities_in_prompt(prompt)
            
            # Validate the fixed prompt to ensure it worked
            fixed_is_valid, fixed_result = validate_combat_prompt(fixed_prompt)
            
            if fixed_is_valid:
                logger.info("Successfully fixed ability mixing!")
                return fixed_prompt
            else:
                logger.warning(f"Failed to fix ability mixing: {fixed_result}")
                # Continue with best effort
        
        return prompt
    
    # Replace methods with patched versions
    app_state.combat_resolver._process_turn = patched_process_turn
    app_state.combat_resolver._create_decision_prompt = functools.partial(patched_create_decision_prompt, app_state)
    
    # Mark as patched
    app_state.combat_resolver._patched = True
    
    logger.info("Combat resolver successfully patched")
    return True

# Expose patched_create_decision_prompt for import in tests and patching
__all__ = [
    'patch_process_turn',
    'patch_combat_resolver',
    'patch_dice_rolling',
    'patch_multi_attack_resolution',
    'patch_json_parsing',
    'patch_resolution_timeout',
    'combat_resolver_patch',
    'patched_create_decision_prompt',
]

# --- Module-level export for testability and patching ---
# This function is used in tests and for patching the combat resolver.
def patched_create_decision_prompt(app_state, combat_state, turn_combatant):
    """Add monster ability validation to the decision prompt with automatic correction."""
    # The implementation is copied from the function inside combat_resolver_patch
    # Call original method
    prompt = app_state.combat_resolver._create_decision_prompt(combat_state, turn_combatant)
    # Clean the prompt to ensure all abilities have proper tags
    prompt = clean_abilities_in_prompt(prompt)
    # Validate the prompt to check for ability mixing
    is_valid, result = validate_combat_prompt(prompt)
    if not is_valid:
        # Log the validation failure
        logger.warning(f"Ability mixing detected in prompt: {result}")
        # Extract the active monster name for further logging
        import re
        active_monster = "Unknown"
        active_match = re.search(r"Active Combatant: ([A-Za-z0-9_\s]+)", prompt)
        if active_match:
            active_monster = active_match.group(1).strip()
        logger.warning(f"Ability mixing affects monster: {active_monster}")
        # Apply automatic correction to fix the ability mixing
        logger.info(f"Attempting to automatically correct mixed abilities for {active_monster}")
        fixed_prompt = fix_mixed_abilities_in_prompt(prompt)
        # Validate the fixed prompt to ensure it worked
        fixed_is_valid, fixed_result = validate_combat_prompt(fixed_prompt)
        if fixed_is_valid:
            logger.info("Successfully fixed ability mixing!")
            return fixed_prompt
        else:
            logger.warning(f"Failed to fix ability mixing: {fixed_result}")
            # Continue with best effort
    return prompt

def apply_patches(app_state):
    """Apply patches to the combat resolver."""
    _patch_improved_combat_resolver(app_state)
    _patch_error_handling(app_state)
    _patch_llm_service(app_state)
    logging.info("Combat resolver patches applied")

def _patch_improved_combat_resolver(app_state):
    """Patch the ImprovedCombatResolver to expose the underlying CombatResolver."""
    if not hasattr(app_state, 'combat_resolver'):
        logging.warning("App state has no combat_resolver to patch")
        return
    
    # No patching needed if it's already a CombatResolver
    if not hasattr(app_state.combat_resolver, 'combat_resolver'):
        logging.info("App state using direct CombatResolver, no wrapper patch needed")
        return
    
    # Make the underlying resolver available on the wrapper
    # to avoid the need to use deprecated resolve_combat_turn_by_turn method
    wrapper = app_state.combat_resolver
    resolver = wrapper.combat_resolver
    
    # Add direct signal connection to the underlying resolver
    if hasattr(resolver, 'resolution_update') and not hasattr(wrapper, 'resolution_update'):
        wrapper.resolution_update = resolver.resolution_update
        logging.info("Patched ImprovedCombatResolver to expose underlying resolution_update signal")
    
    # Add direct start_resolution method for fast resolve functionality
    if hasattr(resolver, 'start_resolution') and not hasattr(wrapper, 'start_resolution'):
        wrapper.start_resolution = resolver.start_resolution
        logging.info("Patched ImprovedCombatResolver to expose underlying start_resolution method")
    
    logging.info("ImprovedCombatResolver successfully patched")

def _patch_error_handling(app_state):
    """Patch the combat resolver to add improved error handling for threads."""
    if not hasattr(app_state, 'combat_resolver'):
        logging.warning("App state has no combat_resolver to patch")
        return
    
    # Get the resolver (whether direct or wrapped)
    resolver = app_state.combat_resolver
    if hasattr(resolver, 'combat_resolver'):
        resolver = resolver.combat_resolver
    
    # Add thread error catching
    original_run_thread = resolver._run_resolution_thread
    
    def patched_run_thread(self, *args, **kwargs):
        """Add enhanced error handling to the resolution thread."""
        try:
            return original_run_thread(self, *args, **kwargs)
        except Exception as e:
            logging.error(f"Error in resolution thread: {e}")
            logging.error(traceback.format_exc())
            # Signal an error to the UI
            try:
                if hasattr(self, 'resolution_update'):
                    error_msg = f"Error in resolution thread: {e}"
                    logging.info("Emitting resolution_update signal with error")
                    self.resolution_update.emit(None, "error", error_msg)
            except Exception as signal_err:
                logging.error(f"Failed to emit error signal: {signal_err}")
    
    # Apply the patch
    resolver._run_resolution_thread = patched_run_thread.__get__(resolver, type(resolver))
    logging.info("Patched combat resolver thread error handling")

def _patch_llm_service(app_state):
    """Patch the LLM service to add improved error handling."""
    if not hasattr(app_state, 'llm_service'):
        logging.warning("App state has no llm_service to patch")
        return
    
    from app.core.llm_service import LLMService
    
    # Get the LLM service
    llm_service = app_state.llm_service
    
    # Patch the generate_completion method to add robust error handling
    original_generate = llm_service.generate_completion
    
    def patched_generate(self, model, messages, system_prompt=None, temperature=0.7, max_tokens=1000):
        """Add enhanced error handling to the LLM service."""
        try:
            # Log the request
            logging.info(f"[LLM] Sending request to {model}")
            logging.debug(f"[LLM] Messages: {messages[:1]}...")
            
            # Make the call
            response = original_generate(self, model, messages, system_prompt, temperature, max_tokens)
            
            # Log the response
            if response:
                logging.info(f"[LLM] Received response ({len(response)} chars)")
                logging.debug(f"[LLM] Response preview: {response[:100]}...")
            else:
                logging.warning("[LLM] Received empty response")
            
            return response
        except Exception as e:
            # Log the error
            logging.error(f"[LLM] Error in generate_completion: {e}")
            logging.error(traceback.format_exc())
            
            # Return a special error message that can be detected by the combat resolver
            error_response = f"""
            {{
              "error": "LLM service error: {str(e)}",
              "action": "Error",
              "target": "None",
              "explanation": "An error occurred while calling the language model."
            }}
            """
            
            # This allows the combat resolver to handle the error gracefully
            return error_response
    
    # Apply the patch
    llm_service.generate_completion = patched_generate.__get__(llm_service, type(llm_service))
    logging.info("Patched LLM service with improved error handling") 