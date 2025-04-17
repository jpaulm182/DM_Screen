"""
Patched version of app_state.py to use the stabilized combat resolver

This module contains functions to patch the AppState class for better 
stability during combat resolution.
"""

import logging
import gc

# Module logger
logger = logging.getLogger("patched_app_state")

def apply_patches():
    """Apply patches to the AppState class"""
    from app.core.app_state import AppState
    from app.core.combat_initializer import init_stabilized_resolver
    from app.core.llm_service_patch import apply_llm_service_patches
    
    # Save original __init__ method
    original_init = AppState.__init__
    
    # Define patched __init__ method
    def patched_init(self):
        # Call original __init__ first to set up basic state
        original_init(self)
        
        logger.info("Applying stability patches")
        
        # Apply LLM service patches first (they need to be applied before any use)
        logger.info("Applying LLM service patches")
        try:
            apply_llm_service_patches(self)
            logger.info("LLM service patches applied successfully")
        except Exception as e:
            logger.error(f"Failed to apply LLM service patches: {e}", exc_info=True)
        
        # Replace the combat resolver with our stabilized version
        logger.info("Applying combat resolver patches")
        try:
            # Create a new stabilized resolver
            new_resolver = init_stabilized_resolver(self.llm_service)
            
            # Replace the existing resolver
            self.combat_resolver = new_resolver
            
            # Force garbage collection
            gc.collect()
            
            logger.info("Combat resolver successfully patched")
        except Exception as e:
            logger.error(f"Failed to patch combat resolver: {e}", exc_info=True)
            logger.warning("Using original unpatched resolver")
    
    # Apply the patch
    AppState.__init__ = patched_init
    logger.info("AppState patched successfully") 