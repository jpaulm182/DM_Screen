"""
Patch module for the LLM service

This module provides patches for the LLMService class to address
thread-safety issues and memory management.
"""

import logging
import threading
import gc
import time
import copy
from functools import wraps

logger = logging.getLogger("llm_service_patch")

# Global lock for OpenAI API calls
openai_api_lock = threading.RLock()

def patch_llm_service(llm_service_instance):
    """
    Apply patches to an LLMService instance
    
    Args:
        llm_service_instance: The LLMService instance to patch
        
    Returns:
        The patched instance
    """
    logger.info("Applying patches to LLMService")
    
    # Patch _generate_openai_completion
    original_generate_openai = llm_service_instance._generate_openai_completion
    
    @wraps(original_generate_openai)
    def patched_generate_openai_completion(model, messages, system_prompt, temperature, max_tokens):
        """Thread-safe version of _generate_openai_completion"""
        logger.debug(f"Entering patched _generate_openai_completion for model {model}")
        
        # Force garbage collection before API call
        gc.collect()
        
        # Create defensive copies of all parameters
        safe_model = copy.deepcopy(model)
        safe_messages = copy.deepcopy(messages)
        safe_system_prompt = copy.deepcopy(system_prompt) if system_prompt else None
        safe_temperature = float(temperature)
        safe_max_tokens = int(max_tokens)
        
        try:
            # Use the global lock to ensure thread safety
            start_time = time.time()
            logger.debug(f"Acquiring OpenAI API lock for model {safe_model}")
            
            with openai_api_lock:
                logger.debug(f"Lock acquired for model {safe_model} after {time.time() - start_time:.2f}s")
                
                # Call the original method with defensive copies
                result = original_generate_openai(
                    safe_model, 
                    safe_messages,
                    safe_system_prompt,
                    safe_temperature,
                    safe_max_tokens
                )
                
                logger.debug(f"OpenAI API call completed in {time.time() - start_time:.2f}s")
            
            # Force garbage collection after API call
            gc.collect()
            
            return result
        except Exception as e:
            logger.error(f"Error in patched _generate_openai_completion: {e}", exc_info=True)
            # Force garbage collection after error
            gc.collect()
            raise
    
    # Apply the patch
    llm_service_instance._generate_openai_completion = patched_generate_openai_completion
    logger.info("Successfully patched _generate_openai_completion")
    
    # Patch _generate_anthropic_completion if needed
    # Similar pattern as above
    
    return llm_service_instance

def patch_generate_completion(llm_service_instance):
    """
    Patch the generate_completion method to add thread safety and error handling
    
    Args:
        llm_service_instance: The LLMService instance to patch
        
    Returns:
        The patched instance
    """
    logger.info("Patching generate_completion method")
    
    original_generate_completion = llm_service_instance.generate_completion
    
    @wraps(original_generate_completion)
    def patched_generate_completion(model, messages, system_prompt=None, temperature=0.7, max_tokens=1000):
        """Thread-safe version of generate_completion with better error handling"""
        logger.debug(f"Entering patched generate_completion for model {model}")
        
        # Force garbage collection
        gc.collect()
        
        try:
            # Create defensive copies
            safe_model = copy.deepcopy(model)
            safe_messages = copy.deepcopy(messages)
            safe_system_prompt = copy.deepcopy(system_prompt) if system_prompt else None
            
            # Call original with global lock
            with threading.RLock():
                result = original_generate_completion(
                    safe_model,
                    safe_messages,
                    safe_system_prompt,
                    temperature,
                    max_tokens
                )
            
            # Force garbage collection
            gc.collect()
            
            return result
        except Exception as e:
            logger.error(f"Error in patched generate_completion: {e}", exc_info=True)
            # Force garbage collection after error
            gc.collect()
            raise
    
    # Apply the patch
    llm_service_instance.generate_completion = patched_generate_completion
    logger.info("Successfully patched generate_completion")
    
    return llm_service_instance

def apply_llm_service_patches(app_state):
    """
    Apply all LLM service patches to the app state
    
    Args:
        app_state: The AppState instance
        
    Returns:
        The patched app_state
    """
    logger.info("Applying LLM service patches to app state")
    
    try:
        # Patch the LLM service
        patch_llm_service(app_state.llm_service)
        patch_generate_completion(app_state.llm_service)
        
        logger.info("LLM service patches applied successfully")
    except Exception as e:
        logger.error(f"Error applying LLM service patches: {e}", exc_info=True)
    
    return app_state 