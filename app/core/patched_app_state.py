"""
Application state and class patches

Applies runtime patches to fix issues or extend functionality in the app.
"""

import logging
import gc
import threading
import time
import traceback

# Module logger
logger = logging.getLogger(__name__)

def apply_patches():
    """
    Apply patches to the application state and other classes.
    Called at application startup.
    """
    logger.info("Applying application patches...")
    
    # Apply AppState patches
    _patch_app_state()
    
    # Apply threading patches 
    _patch_threading()
    
    # Apply LLM service patches
    _patch_llm_service()
    
    logger.info("All patches applied successfully")

def _patch_app_state():
    """Patch the AppState class to fix issues."""
    from app.core.app_state import AppState
    
    # Store original init
    original_init = AppState.__init__
    
    # Patched initialization function
    def patched_init(self):
        """Patched initialization with additional stability measures."""
        # Pre-patch operations
        logger.info("Applying AppState initialization patches")
        
        # Call original initialization
        original_init(self)
        
        # Post-initialization patches
        
        # Force garbage collection after initialization
        gc.collect()
        
        logger.info("AppState initialization patches applied")
    
    # Apply the patch
    AppState.__init__ = patched_init
    logger.info("AppState patched successfully")

def _patch_threading():
    """Apply threading patches."""
    # Increase thread stack size if not already set
    current_stack_size = threading.stack_size()
    if current_stack_size < 8 * 1024 * 1024:  # 8MB
        logging.info(f"Increasing thread stack size from {current_stack_size/1024:.1f}KB to 8MB")
        threading.stack_size(8 * 1024 * 1024)  # 8MB stack size
    
    # Monkey patch Thread.start to add error handling
    original_start = threading.Thread.start
    
    def safe_thread_start(self):
        """Safe version of Thread.start that catches exceptions."""
        try:
            return original_start(self)
        except Exception as e:
            logging.error(f"Error starting thread: {e}")
            logging.error(traceback.format_exc())
            return None
    
    threading.Thread.start = safe_thread_start
    logging.info("Thread safety patches applied.")

def _patch_llm_service():
    """Apply patches to the LLM service."""
    try:
        from app.core.llm_service import LLMService
        
        # Store the original generate_completion method
        original_generate_completion = LLMService.generate_completion
        
        def safe_generate_completion(self, model, messages, system_prompt=None, temperature=0.7, max_tokens=1000):
            """
            Safe version of generate_completion with better error handling and retries.
            """
            max_retries = 2
            retry_delay = 1  # seconds
            
            for attempt in range(max_retries + 1):
                try:
                    if attempt > 0:
                        logging.info(f"Retry attempt {attempt} for LLM call (model: {model})")
                    
                    result = original_generate_completion(self, model, messages, system_prompt, temperature, max_tokens)
                    
                    # Check for valid response
                    if result:
                        return result
                    else:
                        logging.warning(f"Empty response from LLM (attempt {attempt+1}/{max_retries+1})")
                        if attempt < max_retries:
                            time.sleep(retry_delay)
                            continue
                        return "Error: Empty response from LLM after retries"
                
                except Exception as e:
                    logging.error(f"Error in LLM call (attempt {attempt+1}/{max_retries+1}): {e}")
                    if attempt < max_retries:
                        time.sleep(retry_delay)
                        continue
                    logging.error(traceback.format_exc())
                    return f"Error: {str(e)}"
            
            return "Error: Failed to get LLM response after retries"
        
        # Apply the monkey patch
        LLMService.generate_completion = safe_generate_completion
        logging.info("LLM service patches applied.")
        
    except Exception as e:
        logging.error(f"Failed to patch LLM service: {e}")
        logging.error(traceback.format_exc()) 