"""
Combat resolver initialization utilities.

Provides functions for initializing combat resolver with stability patches.
"""

import gc
import logging
import threading
import traceback

# Set up module logger
logger = logging.getLogger("combat_initializer")

def init_stabilized_resolver(llm_service):
    """
    Create and initialize a combat resolver with stability patches
    
    Args:
        llm_service: The LLM service to use
        
    Returns:
        A patched CombatResolver instance
    """
    from app.core.combat_resolver import CombatResolver
    
    try:
        # Create a new resolver instance
        resolver = CombatResolver(llm_service)
        
        # Add API semaphore for thread safety
        resolver._api_semaphore = threading.Semaphore(1)
        
        # Add memory tracking
        try:
            import psutil
            resolver._has_memory_tracker = True
            
            # Add memory tracking method
            def track_memory(tag=""):
                mem = psutil.Process().memory_info().rss / 1024 / 1024
                logger.debug(f"Memory usage {tag}: {mem:.2f} MB")
                return mem
            
            resolver._track_memory = track_memory
            
        except ImportError:
            logger.warning("psutil not available for memory tracking")
            resolver._has_memory_tracker = False
        
        # Set preferred model
        from app.core.llm_service import ModelInfo
        available_models = llm_service.get_available_models()
        for m in available_models:
            if m["id"] == ModelInfo.OPENAI_GPT4O_MINI:
                resolver.model = m["id"]
                logger.info(f"Setting combat resolver to use {m['name']} model")
                break
        
        # Add fallback methods
        def generate_fallback_decision(combatant):
            """Generate a fallback decision when LLM call fails"""
            logger.info(f"Generating fallback decision for {combatant.get('name', 'Unknown')}")
            return {
                "action": f"{combatant.get('name', 'The combatant')} takes a cautious defensive action.",
                "narrative": f"Due to a technical issue, {combatant.get('name', 'the combatant')} takes a defensive stance.",
                "updates": [],
                "dice": []
            }
        
        def generate_fallback_resolution(combatant, action=None, dice_results=None):
            """Generate a fallback resolution when LLM call fails"""
            action = action or "take a defensive action"
            dice_results = dice_results or []
            
            logger.info(f"Generating fallback resolution for {combatant.get('name', 'Unknown')}")
            
            narrative = f"{combatant.get('name', 'The combatant')} attempts to {action}. "
            if dice_results:
                dice_summary = ", ".join([f"{d.get('purpose', 'roll')}: {d.get('result', '?')}" for d in dice_results])
                narrative += f"Results: {dice_summary}. "
            narrative += "No significant effect occurs due to a technical issue."
            
            return {
                "action": action,
                "narrative": narrative,
                "updates": [],
                "dice": dice_results
            }
        
        # Add methods to resolver
        resolver._generate_fallback_decision = generate_fallback_decision
        resolver._generate_fallback_resolution = generate_fallback_resolution
        
        # Force garbage collection
        gc.collect()
        
        logger.info("Successfully initialized stabilized combat resolver")
        return resolver
    except Exception as e:
        logger.error(f"Error initializing stabilized combat resolver: {e}", exc_info=True)
        # Fall back to standard resolver
        return CombatResolver(llm_service) 