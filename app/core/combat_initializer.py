"""
Combat resolver initialization utilities.

Provides functions for initializing combat resolver with stability patches.
"""

import gc
import logging
import threading
import traceback
import sys
import os
import time

# Set up module logger with more verbose debugging
logger = logging.getLogger("combat_initializer")

# Track current active API calls
active_api_calls = {}
api_call_lock = threading.Lock()

def register_api_call(source, details):
    """Register an active API call for tracking"""
    with api_call_lock:
        call_id = id(threading.current_thread())
        active_api_calls[call_id] = {
            "thread": threading.current_thread().name,
            "source": source,
            "details": details,
            "start_time": time.time()
        }
        logger.debug(f"Started API call {call_id} from {source}: {details}")
        return call_id

def unregister_api_call(call_id):
    """Unregister an API call that has completed"""
    with api_call_lock:
        if call_id in active_api_calls:
            call_info = active_api_calls[call_id]
            duration = time.time() - call_info["start_time"]
            logger.debug(f"Completed API call {call_id} from {call_info['source']} in {duration:.2f}s")
            del active_api_calls[call_id]

def dump_active_calls():
    """Dump all active API calls for debugging"""
    with api_call_lock:
        if active_api_calls:
            logger.warning(f"Active API calls: {len(active_api_calls)}")
            for call_id, info in active_api_calls.items():
                duration = time.time() - info["start_time"]
                logger.warning(f"  Call {call_id} from {info['source']}, running for {duration:.2f}s: {info['details']}")
        else:
            logger.debug("No active API calls")

def enhanced_memory_tracking(tag=""):
    """Enhanced memory tracking with detailed breakdown"""
    try:
        import psutil
        process = psutil.Process()
        
        # Basic memory info
        mem_info = process.memory_info()
        rss_mb = mem_info.rss / 1024 / 1024
        vms_mb = mem_info.vms / 1024 / 1024
        
        # Open file handles
        try:
            open_files = len(process.open_files())
        except (psutil.AccessDenied, psutil.ZombieProcess):
            open_files = -1
        
        # Thread count
        thread_count = threading.active_count()
        
        # Force garbage collection and get counts
        gc.collect()
        gc_counts = gc.get_count()
        
        logger.debug(f"Memory usage {tag}: RSS={rss_mb:.2f}MB, VMS={vms_mb:.2f}MB, Threads={thread_count}, Files={open_files}, GC={gc_counts}")
        
        # Dump active API calls
        dump_active_calls()
        
        return {
            "rss_mb": rss_mb,
            "vms_mb": vms_mb,
            "threads": thread_count,
            "open_files": open_files,
            "gc_counts": gc_counts
        }
    except ImportError:
        logger.warning("psutil not available for enhanced memory tracking")
        return None
    except Exception as e:
        logger.error(f"Error in enhanced memory tracking: {e}")
        return None

def init_stabilized_resolver(llm_service):
    """
    Create and initialize a combat resolver with stability patches
    
    Args:
        llm_service: The LLM service to use
        
    Returns:
        A patched CombatResolver instance
    """
    from app.core.combat_resolver import CombatResolver
    from app.core.combat_resolver_patch import patch_combat_resolver, combat_resolver_patch
    
    # Track initial memory state
    enhanced_memory_tracking("before_resolver_init")
    
    try:
        # Create a new resolver instance
        resolver = CombatResolver(llm_service)
        
        # Add API semaphore for thread safety - limit to 1 concurrent call
        resolver._api_semaphore = threading.Semaphore(1)
        
        # Add enhanced API call tracking
        resolver._register_api_call = register_api_call
        resolver._unregister_api_call = unregister_api_call
        resolver._dump_active_calls = dump_active_calls
        
        # Add enhanced memory tracking
        resolver._track_memory = enhanced_memory_tracking
        
        # Set preferred model
        from app.core.llm_service import ModelInfo
        available_models = llm_service.get_available_models()
        model_set = False
        for m in available_models:
            if m["id"] == ModelInfo.OPENAI_GPT4O_MINI:
                resolver.model = m["id"]
                logger.info(f"Setting combat resolver to use {m['name']} model")
                model_set = True
                break
        
        if not model_set and available_models:
            resolver.model = available_models[0]["id"]
            logger.info(f"Falling back to {available_models[0]['name']} model")
        
        # Add safe API call method
        def safe_api_call(func, *args, timeout=30, **kwargs):
            """Make an API call with memory tracking and error handling"""
            # Track memory before call
            call_id = register_api_call(func.__name__, str(args)[:100])
            enhanced_memory_tracking(f"before_api_call_{call_id}")
            
            # Force garbage collection
            gc.collect()
            
            try:
                # Use semaphore to limit concurrent calls
                with resolver._api_semaphore:
                    from concurrent.futures import ThreadPoolExecutor, TimeoutError
                    
                    # Use executor with timeout
                    with ThreadPoolExecutor(max_workers=1) as executor:
                        future = executor.submit(func, *args, **kwargs)
                        try:
                            result = future.result(timeout=timeout)
                        except TimeoutError:
                            logger.error(f"API call {call_id} timed out after {timeout} seconds")
                            raise TimeoutError(f"API call timed out after {timeout} seconds")
                
                # Track memory after call
                enhanced_memory_tracking(f"after_api_call_{call_id}")
                
                # Force garbage collection
                gc.collect()
                
                # Unregister the API call
                unregister_api_call(call_id)
                
                return result
            except Exception as e:
                logger.error(f"API call {call_id} failed: {str(e)}", exc_info=True)
                
                # Force garbage collection after error
                gc.collect()
                
                # Unregister the API call
                unregister_api_call(call_id)
                
                raise
        
        # Add safe_api_call to resolver
        resolver._safe_api_call = safe_api_call
        
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
            logger.info(f"Generating fallback resolution for {combatant.get('name', 'Unknown')}")
            
            action_text = "takes a cautious action" if not action else action
            
            return {
                "action": action_text,
                "narrative": f"Technical difficulty occurred - A technical issue occurred during this turn. Combat continues.",
                "updates": [],
                "dice": dice_results or []
            }
        
        # Add fallback methods to resolver
        resolver._generate_fallback_decision = generate_fallback_decision
        resolver._generate_fallback_resolution = generate_fallback_resolution
        
        # Apply combat resolver patch with ability mixing prevention
        logger.info("Applying ability mixing prevention patch to combat resolver")
        try:
            # Create a mock app_state object with just the resolver
            class MockAppState:
                def __init__(self, resolver):
                    self.combat_resolver = resolver

            mock_app_state = MockAppState(resolver)
            
            # Apply the patch
            combat_resolver_patch(mock_app_state)
            
            logger.info("Successfully applied ability mixing prevention patch")
        except Exception as e:
            logger.error(f"Failed to apply ability mixing prevention patch: {e}", exc_info=True)
        
        # Return the patched resolver
        logger.info("Initialized stabilized combat resolver")
        return resolver
    except Exception as e:
        logger.error(f"Error initializing stabilized resolver: {e}")
        traceback.print_exc()
        logger.warning("Falling back to standard resolver")
        return CombatResolver(llm_service) 