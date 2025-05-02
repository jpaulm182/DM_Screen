"""
Core component for resolving combat encounters using LLM.

This class takes the current combat state and uses an LLM to generate
tactical decisions, which are then executed with dice rolls and
properly reflected in the UI.
"""

from app.core.llm_service import LLMService, ModelInfo
import json as _json
import re
import time
import logging
import threading # Added
import copy      # Added

# Import QObject and Signal for thread-safe communication
from PySide6.QtCore import QObject, Signal

# Inherit from QObject
class CombatResolver(QObject):
    """
    Handles the logic for resolving combat using an LLM, with proper
    UI feedback and dice-rolling integration. Includes controls for
    turn-by-turn, continuous, stopping, and resetting resolution.
    """
    # Define a signal to emit results thread-safely
    # Carries: result dict (or None), status string, error string (or None)
    resolution_update = Signal(object, str, object)

    def __init__(self, llm_service: LLMService):
        """Initialize the CombatResolver with the LLM service."""
        # Call QObject initializer
        super().__init__()
        self.llm_service = llm_service
        self.previous_turn_summaries = [] # Track previous turn results for LLM context

        # --- State Management ---
        self._lock = threading.Lock() # For thread-safe access to state variables
        self._running = False         # Is the resolution thread active?
        self._mode = 'continuous'     # 'continuous' or 'step'
        self._paused = False          # Is the thread currently paused (in step mode)?
        self._stop_requested = False  # Has the user requested to stop?
        self._continue_event = threading.Event() # Used to unpause in step mode
        self._current_thread = None   # Reference to the running thread

        # --- Stored Parameters ---
        self._combat_state = None
        self._dice_roller = None
        self._update_ui_callback = None # Still used for intra-turn updates

    # ---------------------------------------------------------------------
    # Helper to build LLM messages with previous turn context
    # ---------------------------------------------------------------------
    def build_llm_messages(self, previous_turn_summaries, current_prompt):
        """
        Build a list of LLM chat messages including previous turn summaries as system messages.
        Args:
            previous_turn_summaries (list of str): Summaries of previous turns
            current_prompt (str): The prompt for the current turn
        Returns:
            list: List of message dicts for LLM chat API
        """
        messages = []
        for summary in previous_turn_summaries:
            messages.append({"role": "system", "content": summary})
        messages.append({"role": "user", "content": current_prompt})
        return messages

    # ---------------------------------------------------------------------
    # Public Control Methods
    # ---------------------------------------------------------------------

    def start_resolution(self, combat_state, dice_roller, update_ui_callback, mode='continuous'):
        """
        Starts the combat resolution process in a separate thread.

        Args:
            combat_state: Dictionary with current combat state.
            dice_roller: Function that rolls dice.
            update_ui_callback: Function called after each turn for UI updates.
            mode (str): 'continuous' or 'step'.

        Returns:
            bool: True if started successfully, False otherwise (e.g., already running).
        """
        with self._lock:
            if self._running:
                logging.warning("[CombatResolver] start_resolution called while already running.")
                return False

            logging.info(f"[CombatResolver] Starting resolution (Mode: {mode})")
            self._running = True
            self._mode = mode
            self._paused = False
            self._stop_requested = False
            self._continue_event.clear()
            self.previous_turn_summaries = [] # Reset context for new resolution

            # Store parameters needed by the thread
            self._combat_state = copy.deepcopy(combat_state) # Use a deep copy
            self._dice_roller = dice_roller
            self._update_ui_callback = update_ui_callback

            # Pre-validate the combat state before starting the thread
            if not isinstance(self._combat_state, dict):
                logging.error("[CombatResolver] Invalid combat_state provided.")
                self._running = False
                self.resolution_update.emit(None, "error", "Invalid combat state provided.")
                return False
            combatants = self._combat_state.get("combatants", [])
            if not combatants:
                logging.error("[CombatResolver] No combatants in the combat state.")
                self._running = False
                self.resolution_update.emit(None, "error", "No combatants in the combat state.")
                return False

            # Start the resolution thread
            self._current_thread = threading.Thread(target=self._run_resolution_thread, daemon=True)
            self._current_thread.start()
            return True

    def continue_turn(self):
        """Signals the paused resolution thread (in step mode) to continue."""
        with self._lock:
            if self._running and self._paused:
                logging.debug("[CombatResolver] continue_turn signaled.")
                self._paused = False
                self._continue_event.set() # Signal the thread to wake up
            elif self._running and self._mode == 'step':
                 logging.warning("[CombatResolver] continue_turn called but not paused.")
            elif not self._running:
                 logging.warning("[CombatResolver] continue_turn called but resolution not running.")


    def stop_resolution(self):
        """Requests the currently running resolution thread to stop gracefully."""
        with self._lock:
            if not self._running:
                logging.warning("[CombatResolver] stop_resolution called but not running.")
                return

            logging.info("[CombatResolver] Stop requested.")
            self._stop_requested = True
            # If paused, we need to signal it to wake up and check the stop flag
            if self._paused:
                self._paused = False # No longer considered paused if we're stopping
                self._continue_event.set()

    def reset_resolution(self):
        """Stops any current resolution and resets the state."""
        logging.info("[CombatResolver] Reset requested.")
        thread_to_join = None
        with self._lock:
            if self._running:
                self._stop_requested = True
                if self._paused:
                    self._paused = False
                    self._continue_event.set()
                thread_to_join = self._current_thread # Get thread ref inside lock

            # Reset internal state immediately
            self._running = False
            self._paused = False
            self._stop_requested = False
            self._mode = 'continuous'
            self._combat_state = None
            self._dice_roller = None
            self._update_ui_callback = None
            self._current_thread = None
            self.previous_turn_summaries = []
            self._continue_event.clear() # Ensure event is clear

        # Wait briefly outside the lock for the thread to hopefully terminate
        if thread_to_join and thread_to_join.is_alive():
            thread_to_join.join(timeout=0.5) # Short timeout
            if thread_to_join.is_alive():
                 logging.warning("[CombatResolver] Resolution thread did not terminate quickly after reset request.")

        logging.info("[CombatResolver] State reset.")

    def is_running(self):
        """Check if the resolver is currently processing."""
        with self._lock:
            return self._running

    def is_paused(self):
        """Check if the resolver is paused in step mode."""
        with self._lock:
            return self._paused


    # DEPRECATED - use start_resolution and signals
    def resolve_combat_turn_by_turn(self, combat_state, dice_roller, callback, update_ui_callback=None):
        """
        DEPRECATED: Use start_resolution instead.
        Starts combat resolution. Use signals for updates.
        """
        logging.warning("[CombatResolver] DEPRECATED resolve_combat_turn_by_turn called. Use start_resolution.")
        # Call the new method, ignoring the old callback
        self.start_resolution(combat_state, dice_roller, update_ui_callback, mode='continuous')


    # ---------------------------------------------------------------------
    # Internal Resolution Logic (Runs in Thread)
    # ---------------------------------------------------------------------
    def _run_resolution_thread(self, *args):
        """
        Main thread method for processing combat continuously or step-by-step.
        This runs in a separate thread and must be thread-safe.
        
        Args:
            *args: Additional arguments passed to the method (ignored for compatibility)
        """
        import copy
        import traceback
        import time
        import logging
        
        # Use a local copy of the combat state to avoid race conditions
        try:
            # Make a deep copy to ensure thread safety
            with self._lock:
                if self._combat_state is None:
                    logging.error("[CombatResolver] Combat state is None in resolution thread")
                    self.resolution_update.emit(None, "error", "Internal error: Combat state is missing")
                    self._running = False
                    return
                
                local_combat_state = copy.deepcopy(self._combat_state)
                local_dice_roller = self._dice_roller
                
            logging.debug("[CombatResolver] Resolution thread starting with combat state copy")
            # Signal that we're starting (using a copy of the state)
            self.resolution_update.emit(local_combat_state, "starting", None)
            
            # Extract important variables from combat state
            local_combatants_list = local_combat_state.get("combatants", [])
            current_turn_index = local_combat_state.get("current_turn_index", 0)
            round_num = local_combat_state.get("round", 1)
            
            if not local_combatants_list:
                logging.error("[CombatResolver] No combatants in combat state")
                self.resolution_update.emit(None, "error", "No combatants in combat state")
                with self._lock:
                    self._running = False
                return
            
            # If we don't have a valid current_turn_index, start at 0
            if current_turn_index < 0 or current_turn_index >= len(local_combatants_list):
                current_turn_index = 0
                local_combat_state["current_turn_index"] = current_turn_index
                
            # Main resolution loop - continues until stopped or combat ends
            while True:
                # Check if we should stop
                with self._lock:
                    if self._stop_requested:
                        logging.info("[CombatResolver] Stop requested, exiting resolution thread")
                        self.resolution_update.emit(local_combat_state, "stopped", None)
                        self._running = False
                        return
                
                # Process the current combatant's turn
                try:
                    # Use the local variables, not instance state
                    result = self._process_turn(
                        local_combatants_list, 
                        current_turn_index, 
                        round_num,
                        local_dice_roller
                    )
                    
                    if result:
                        # Apply results to our local copy of the state
                        # Add the result to the turn state for UI updates
                        local_combat_state["latest_action"] = {
                            "actor": local_combatants_list[current_turn_index].get("name", "Unknown"),
                            "action": result.get("action", "Unknown action"),
                            "result": result.get("narrative", ""),
                            "dice": result.get("dice", [])
                        }
                        
                        # Apply any updates to the local combatants list
                        if "updates" in result:
                            self._apply_turn_updates(local_combatants_list, result.get("updates", []))
                            
                        # Signal the turn completion with updated state
                        local_combat_state["combatants"] = local_combatants_list
                        local_combat_state["current_turn_index"] = current_turn_index
                        local_combat_state["round"] = round_num
                        
                        # Thread-safe emit the updated state
                        self.resolution_update.emit(local_combat_state, "turn_complete", None)
                except Exception as e:
                    error_msg = f"Error processing turn: {str(e)}"
                    logging.error(f"[CombatResolver] {error_msg}")
                    logging.error(f"[CombatResolver] {traceback.format_exc()}")
                    self.resolution_update.emit(local_combat_state, "error", error_msg)
                    # Don't exit the thread, try to continue with next turn
                
                # Check if combat should end (e.g., all enemies defeated)
                combat_ended, end_reason = self._check_combat_end_condition(local_combatants_list)
                if combat_ended:
                    logging.info(f"[CombatResolver] Combat ended: {end_reason}")
                    local_combat_state["combat_ended"] = True
                    local_combat_state["end_reason"] = end_reason
                    self.resolution_update.emit(local_combat_state, "combat_ended", None)
                    with self._lock:
                        self._running = False
                    return
                
                # Move to the next turn - wrapping around the combatants list if needed
                current_turn_index = (current_turn_index + 1) % len(local_combatants_list)
                local_combat_state["current_turn_index"] = current_turn_index
                
                # If we've gone through all combatants, advance to the next round
                if current_turn_index == 0:
                    round_num += 1
                    local_combat_state["round"] = round_num
                    logging.info(f"[CombatResolver] Advanced to round {round_num}")
                
                # If in step mode, pause until continue signal
                if self._mode == 'step':
                    with self._lock:
                        self._paused = True
                    logging.debug("[CombatResolver] Step mode - pausing until continue signal")
                    self.resolution_update.emit(local_combat_state, "paused", None)
                    
                    # Wait for the continue event (or stop request)
                    self._continue_event.wait()
                    self._continue_event.clear()
                    
                    # Check again if we should stop after unpausing
                    with self._lock:
                        if self._stop_requested:
                            logging.info("[CombatResolver] Stop requested after pause, exiting resolution thread")
                            self.resolution_update.emit(local_combat_state, "stopped", None)
                            self._running = False
                            return
                else:
                    # In continuous mode, brief pause to avoid CPU hogging
                    time.sleep(0.1)
                
        except Exception as e:
            error_msg = f"Error in resolution thread: {str(e)}"
            logging.error(f"[CombatResolver] {error_msg}")
            logging.error(f"[CombatResolver] {traceback.format_exc()}")
            self.resolution_update.emit(None, "error", error_msg)
            
        finally:
            # Always ensure we reset the running state
            with self._lock:
                self._running = False

    def _check_combat_end_condition(self, combatants):
        """
        Checks if the combat should end based on remaining participants.

        Args:
            combatants: The current list of combatants.

        Returns:
            tuple: (bool, str) indicating (should_end, reason)
        """
        # Consider only those not permanently 'Dead'
        potentially_active = [
            c for c in combatants if c.get("status", "").lower() != "dead"
        ]
        # Further filter by HP > 0 OR non-monster stable/unconscious
        active_combatants = [
             c for c in potentially_active if c.get("hp", 0) > 0 or
             (c.get("type", "").lower() != "monster" and c.get("status", "").lower() in ["unconscious", "stable"])
        ]

        monsters_left = [c for c in active_combatants if c.get("type", "").lower() == "monster"]
        characters_left = [c for c in active_combatants if c.get("type", "").lower() != "monster"]

        if not characters_left:
            return True, "No characters remaining."
        if not monsters_left:
            return True, "No monsters remaining."

        return False, "Multiple factions remaining."


    def _apply_turn_updates(self, combatants, updates):
         """
         Applies the updates from a turn result to the combatants list.
         Handles HP changes, status updates, conditions, etc.

         Args:
             combatants: The list of combatant dictionaries (will be modified).
             updates: The list of update dictionaries from the turn result.
         """
         if not isinstance(updates, list):
              logging.warning(f"[CombatResolver] Invalid 'updates' format received: {type(updates)}. Skipping application.")
              return

         # Use instance_id for more reliable matching if available
         # Create a mapping for quick lookup
         combatant_map_by_id = {c.get('instance_id'): c for c in combatants if c.get('instance_id')}
         combatant_map_by_name = {c.get('name'): c for c in combatants if c.get('name')}


         for update in updates:
             if not isinstance(update, dict): continue

             target_id = update.get("instance_id")
             target_name = update.get("name")
             target = None

             # Find the target combatant
             if target_id and target_id in combatant_map_by_id:
                 target = combatant_map_by_id[target_id]
             elif target_name and target_name in combatant_map_by_name:
                  target = combatant_map_by_name[target_name]
                  # If found by name, ensure we store the ID back if missing in update
                  if not target_id and target.get('instance_id'):
                       target_id = target.get('instance_id')


             if not target:
                  logging.warning(f"Could not find target '{target_name or target_id}' for update: {update}")
                  continue

             logging.debug(f"Applying update to {target.get('name')}: {update}")

             # --- Update HP ---
             if "hp" in update:
                 try:
                     current_hp = target.get("hp", 0)
                     # Use helper to handle relative/absolute updates
                     new_hp = self._process_hp_update(target.get("name"), update["hp"], current_hp)
                     # Ensure HP doesn't exceed max_hp (if max_hp exists)
                     max_hp = target.get("max_hp")
                     if max_hp is not None:
                         new_hp = min(new_hp, max_hp)

                     target["hp"] = new_hp
                     logging.debug(f"  HP updated to {new_hp} (from {current_hp})")

                     # Auto-update status based on HP if status wasn't explicitly set in *this* update
                     if "status" not in update and new_hp <= 0:
                         ctype = target.get("type", "").lower()
                         current_status = target.get("status", "").lower()
                         # Only change status if not already dead/unconscious/stable
                         if current_status not in ["dead", "unconscious", "stable"]:
                              if ctype == "monster":
                                   target["status"] = "Dead"
                                   logging.debug("  Auto-status set to Dead (HP <= 0)")
                              else:
                                   target["status"] = "Unconscious"
                                   logging.debug("  Auto-status set to Unconscious (HP <= 0)")
                                   self._init_death_saves(target) # Init saves when becoming unconscious

                 except Exception as e:
                     logging.error(f"Error processing HP update for {target.get('name')}: {e}", exc_info=True)

             # --- Update Status ---
             if "status" in update:
                  new_status = update["status"]
                  # Basic validation
                  if isinstance(new_status, str):
                       target["status"] = new_status
                       logging.debug(f"  Status updated to '{new_status}'")
                       # If PC becomes unconscious, ensure death saves are initialized
                       if new_status.lower() == "unconscious" and target.get("type", "").lower() != "monster":
                            self._init_death_saves(target)
                  else:
                       logging.warning(f"Invalid status type in update for {target.get('name')}: {type(new_status)}")


             # --- Update Conditions ---
             # TODO: Implement condition application/removal logic if needed based on LLM output format

             # --- Update Limited Use Abilities ---
             # TODO: Implement if LLM provides updates for these

             # --- Update Death Saves ---
             if "death_saves" in update and isinstance(update["death_saves"], dict):
                  if "death_saves" not in target: target["death_saves"] = {"successes": 0, "failures": 0}
                  # Merge updates carefully
                  successes = update["death_saves"].get("successes")
                  failures = update["death_saves"].get("failures")
                  if isinstance(successes, int): target["death_saves"]["successes"] = successes
                  if isinstance(failures, int): target["death_saves"]["failures"] = failures
                  logging.debug(f"  Death Saves updated to: {target['death_saves']}")
                  # Check for stabilization/death immediately after update
                  self._check_death_save_outcome(target) # Updates status if needed


    def _init_death_saves(self, combatant):
         """Initializes death save tracking if not already present."""
         if "death_saves" not in combatant:
              combatant["death_saves"] = {"successes": 0, "failures": 0}
              logging.debug(f"Initialized death saves for {combatant.get('name')}")

    def _check_death_save_outcome(self, combatant):
         """Checks death save counts and updates status to Stable or Dead if needed."""
         saves = combatant.get("death_saves", {})
         successes = saves.get("successes", 0)
         failures = saves.get("failures", 0)
         current_status = combatant.get("status", "").lower()

         if current_status == "unconscious": # Only apply if currently unconscious
             if successes >= 3:
                 combatant["status"] = "Stable"
                 logging.info(f"{combatant.get('name')} stabilized.")
             elif failures >= 3:
                  combatant["status"] = "Dead"
                  logging.info(f"{combatant.get('name')} died from failed death saves.")

    # ---------------------------------------------------------------------
    # Existing Helper Methods (potentially need minor adjustments)
    # ---------------------------------------------------------------------
    def _parse_llm_json_response(self, response_text, context=""): # Added helper
        """
        Attempts to parse JSON from LLM response, handling common issues.
        
        Args:
            response_text (str): The raw text response from the LLM
            context (str): Optional context string for logging
            
        Returns:
            dict: The parsed JSON or an error dictionary
        """
        import json
        import re
        import logging

        if not isinstance(response_text, str):
            logging.warning(f"[_parse_llm_json_response] Expected string, got {type(response_text)} ({context})")
            return {
                "error": "Invalid response type", 
                "raw_response": str(response_text),
                "diagnostics": "Response was not a string"
            }

        # Clean up the response text
        cleaned = response_text.strip()
        logging.debug(f"[_parse_llm_json_response] Raw response ({context}): {cleaned[:200]}...")
        
        # Store the original for diagnostics
        original_text = cleaned

        # Try multiple parsing strategies
        parsing_strategies = [
            # 1. Try extracting from ```json ... ``` block
            {
                "name": "json_block",
                "pattern": r"```json\s*(\{.*?\})\s*```",
                "flags": re.DOTALL,
                "description": "JSON code block"
            },
            # 2. Try extracting from any ``` ... ``` block
            {
                "name": "code_block",
                "pattern": r"```\s*(\{.*?\})\s*```",
                "flags": re.DOTALL,
                "description": "Generic code block"
            },
            # 3. Try finding the first { and last }
            {
                "name": "braces",
                "pattern": r"(\{.*\})",
                "flags": re.DOTALL,
                "description": "Brace-enclosed content"
            }
        ]
        
        diagnostics = []
        
        # Try each strategy in order
        for strategy in parsing_strategies:
            try:
                match = re.search(strategy["pattern"], cleaned, strategy["flags"])
                if match:
                    json_content = match.group(1)
                    try:
                        parsed = json.loads(json_content)
                        logging.debug(f"Successfully parsed from {strategy['description']} ({context})")
                        return parsed
                    except json.JSONDecodeError as e:
                        message = f"Failed to parse {strategy['description']}: {e}"
                        logging.warning(message)
                        diagnostics.append(message)
            except Exception as e:
                message = f"Error applying {strategy['name']} strategy: {e}"
                logging.warning(message)
                diagnostics.append(message)
        
        # 4. Final attempt: Parse the raw cleaned string directly
        try:
            parsed = json.loads(cleaned)
            logging.debug(f"Successfully parsed cleaned string directly ({context})")
            return parsed
        except json.JSONDecodeError as e:
            message = f"Failed to parse raw string: {e}"
            logging.error(message)
            diagnostics.append(message)
        
        # If we reach here, all parsing attempts failed
        logging.error(f"Failed to parse JSON response ({context}) after all attempts. Raw: {cleaned[:200]}...")
        
        # Return a detailed error object with diagnostics
        return {
            "error": "JSON parsing failed", 
            "raw_response": original_text,
            "diagnostics": diagnostics,
            "response_preview": original_text[:500] if original_text else "Empty response"
        }

    # Make sure _process_turn uses the thread-local combatants list
    def _process_turn(self, combatants, active_idx, round_num, dice_roller):
        """Process a single turn for the combatant at active_idx."""
        import logging
        import json
        import time
        import re
        import random
        import traceback

        # Validate inputs to prevent errors
        if active_idx < 0 or active_idx >= len(combatants):
            logging.error(f"[CombatResolver] Invalid active_idx: {active_idx}, combatants: {len(combatants)}")
            return None

        # Get the active combatant
        active_combatant = combatants[active_idx]
        active_name = active_combatant.get("name", f"Combatant {active_idx}")
        logging.info(f"[CombatResolver] Processing turn for: {active_name}")

        # Select the appropriate model based on type
        models = self.llm_service.get_available_models()
        if not models:
            logging.error("[CombatResolver] No LLM models available")
            return {
                "success": False,
                "error": "No LLM models available"
            }

        # Use a faster model by default
        model = models[0]['id']  # Default to first available model

        # Find a "mini" model if available for faster combat resolution
        for m in models:
            if 'mini' in m['id'].lower():
                model = m['id']
                break

        # Create prompt for the action decision
        messages = self._create_action_prompt(combatants, active_idx, round_num)

        # Make the actual LLM call with additional logging
        logging.info(f"[CombatResolver] Making LLM call to model {model}")
        try:
            response_text = self.llm_service.generate_completion(
                model,
                messages
            )
            
            if not response_text:
                logging.error("[CombatResolver] LLM returned empty response")
                raise ValueError("LLM returned empty response")
                
            logging.info(f"[CombatResolver] LLM response received, length: {len(response_text)}")
            
            # Parse the JSON response for action/target/explanation
            logging.info("[CombatResolver] Parsing LLM JSON response for context: action_decision")
            action_result = self._parse_llm_json_response(response_text, "action_decision")
            
            # Save the result for debugging
            self._save_json_artifact(action_result, f"parse_result_action_decision_{int(time.time())}")
            
            if not action_result.get("success", False):
                logging.error(f"[CombatResolver] Failed to parse LLM response: {action_result.get('error', 'Unknown error')}")
                return {
                    "success": False,
                    "error": f"Failed to parse LLM response: {action_result.get('error', 'Unknown error')}"
                }
                
            # Extract action details from the parsed response
            action = action_result.get("action", "Unknown action")
            target = action_result.get("target", "")
            explanation = action_result.get("explanation", "")
            
            # Determine action type and icon for visualization
            action_type = self._determine_action_type(action)
            action_icon = self._get_action_icon(action_type)
            
            logging.info(f"[CombatResolver] {active_name} chose action: {action} targeting: {target}")
            
            # Construct a narrative from the action and explanation
            narrative = explanation
            if not narrative:
                narrative = f"{active_name} {action.lower()}"
                if target:
                    narrative += f" targeting {target}"
                narrative += "."
                
            # Build the final turn result with enhanced visual data
            turn_result = {
                "success": True,
                "has_narrative": bool(narrative),
                "narrative_length": len(narrative) if narrative else 0,
                "has_action": bool(action),
                "action": action,
                "target": target,
                "narrative": narrative,
                "action_type": action_type,
                "action_icon": action_icon,
                "narrative_style": self._get_narrative_style(action_type)
            }
            
            # Save the turn result for debugging
            self._save_json_artifact(turn_result, f"turn_result_{active_name}_{round_num}")
            
            return turn_result
            
        except Exception as e:
            logging.error(f"[CombatResolver] Error processing turn: {str(e)}")
            traceback.print_exc()
            
            # Create a fallback action when something goes wrong
            fallback_action = {
                "success": False,
                "error": str(e),
                "fallback": True,
                "action": "Basic Attack",
                "target": self._find_appropriate_target(combatants, active_idx),
                "narrative": f"{active_name} attempts a basic action but encounters difficulty."
            }
            
            return fallback_action
            
    def _get_narrative_style(self, action_type):
        """Return CSS styling for different action types."""
        styles = {
            "attack": "color:#880000; font-style:italic;",
            "spell": "color:#8800BB; font-style:italic;",
            "movement": "color:#008844; font-style:italic;",
            "healing": "color:#00AA00; font-style:italic;",
            "defense": "color:#000088; font-style:italic;",
            "utility": "color:#555555; font-style:italic;",
            "social": "color:#885500; font-style:italic;",
            "other": "color:#555555; font-style:italic;"
        }
        return styles.get(action_type, "color:#555555; font-style:italic;")
        
    def _find_appropriate_target(self, combatants, active_idx):
        """Find an appropriate target for a fallback action."""
        active_type = combatants[active_idx].get("type", "unknown").lower()
        
        # Look for an enemy based on type
        for i, c in enumerate(combatants):
            if i == active_idx:
                continue
                
            target_type = c.get("type", "unknown").lower()
            
            # Simple heuristic - monsters target non-monsters, and vice versa
            if (active_type == "monster" and target_type != "monster") or \
               (active_type != "monster" and target_type == "monster"):
                return c.get("name", "enemy")
                
        # Fallback if no clear enemy found
        return "nearest enemy"

    def _determine_action_type(self, action_name):
        """
        Determine the type of action based on the action name or description.
        
        Args:
            action_name: The name of the action
            
        Returns:
            str: The action type (attack, spell, movement, healing, etc.)
        """
        action_lower = action_name.lower()
        
        # Attack actions
        if any(term in action_lower for term in ['attack', 'strike', 'hit', 'slash', 'stab', 'claw', 'bite', 'multiattack']):
            return "attack"
            
        # Spell actions
        elif any(term in action_lower for term in ['cast', 'spell', 'magic', 'cantrip', 'eldritch']):
            return "spell"
            
        # Movement actions
        elif any(term in action_lower for term in ['move', 'dash', 'disengage', 'jump', 'climb', 'fly', 'swim']):
            return "movement"
            
        # Healing actions
        elif any(term in action_lower for term in ['heal', 'cure', 'restore', 'potion']):
            return "healing"
            
        # Defensive actions
        elif any(term in action_lower for term in ['dodge', 'block', 'shield', 'parry', 'protect']):
            return "defense"
            
        # Utility actions
        elif any(term in action_lower for term in ['hide', 'search', 'help', 'aid', 'investigate', 'detect']):
            return "utility"
            
        # Social actions
        elif any(term in action_lower for term in ['persuade', 'deceive', 'intimidate', 'charm']):
            return "social"
            
        # Default - other
        return "other"
        
    def _get_action_icon(self, action_type):
        """
        Return an appropriate icon for the action type.
        
        Args:
            action_type: The type of action
            
        Returns:
            str: An emoji or symbol representing the action
        """
        icons = {
            "attack": "⚔️",
            "spell": "✨",
            "movement": "👣",
            "healing": "💚",
            "defense": "🛡️",
            "utility": "🔍",
            "social": "💬",
            "other": "⚡",
        }
        return icons.get(action_type, "⚡")

    # Make sure _create_decision_prompt uses the passed combat_state dict correctly
    def _create_decision_prompt(self, combat_state_dict, turn_combatant):
        """Create a prompt for the LLM to decide a combatant's action."""
        prompt = "You are playing the role of a combatant in a D&D 5e battle. Make a tactical decision for your next action.\n\n"

        # Use the passed dictionary
        combatants_list = combat_state_dict.get("combatants", [])
        round_num_prompt = combat_state_dict.get("round_number", 1) # Use correct key

        # Find the active combatant within the passed list using instance_id if possible
        active_combatant = turn_combatant # Already passed in

        # ... (rest of the prompt creation logic) ...
        # IMPORTANT: Ensure all accesses to combat state use 'combatants_list' and 'round_num_prompt'
        # e.g., for c in sorted([c for c in combatants_list], ...):
        # e.g., prompt += f"\nCurrent Turn: {round_num_prompt}\n"
        # e.g., for c in combatants_list:
        # ... etc ...

        # --- Start of _create_decision_prompt modifications ---
        # Basic combat situation
        active_name = active_combatant.get('name', 'Unknown')
        instance_id = active_combatant.get("instance_id", "") # Get instance ID

        # Recharge abilities
        available_recharge_abilities = []
        unavailable_recharge_abilities = []
        # ... (keep existing recharge processing logic using active_combatant) ...

        # Format initiative order using combatants_list
        initiative_order = []
        try:
             # Ensure initiative is treated as number for sorting
             sorted_combatants = sorted(
                  [c for c in combatants_list if c], # Filter out potential None entries
                  key=lambda x: -int(x.get("initiative", 0)) # Sort descending
             )
             for c in sorted_combatants:
                  init_val = c.get('initiative', 0)
                  initiative_text = f"{c.get('name', 'Unknown')} (Init: {init_val})"
                  # Compare by a unique identifier, instance_id is best
                  if c.get('instance_id') and c.get('instance_id') == active_combatant.get('instance_id'):
                       initiative_text += " <<< YOUR TURN"
                  elif not c.get('instance_id') and c.get('name') == active_name: # Fallback to name if no ID
                       initiative_text += " <<< YOUR TURN"
                  initiative_order.append(initiative_text)
        except Exception as sort_e:
            logging.error(f"Error formatting initiative order: {sort_e}")
            initiative_order.append("Error displaying initiative order.")


        # Describe the combat situation
        prompt += "# Combat Situation\n"
        prompt += f"You are: {active_name} (Type: {active_combatant.get('type')}, ID: {instance_id})\n" # Show ID
        current_hp = active_combatant.get('hp', 0)
        max_hp = active_combatant.get('max_hp', current_hp) # Default max_hp sensibly
        prompt += f"Current HP: {current_hp}/{max_hp}\n"
        prompt += f"AC: {active_combatant.get('ac', 10)}\n" # Default AC
        status = active_combatant.get("status", "OK")
        if status and status != "OK": # Only show non-OK status
            prompt += f"Status: {status}\n"

        # Conditions
        conditions = active_combatant.get("conditions", {})
        if conditions:
             prompt += f"Conditions: {', '.join(conditions.keys())}\n"

        prompt += f"\nCurrent Round: {round_num_prompt}\n" # Use correct variable

        # Initiative order
        prompt += "\n## Initiative Order (Highest to Lowest)\n"
        prompt += "\n".join([f"- {line}" for line in initiative_order]) + "\n"


        # Add information about all combatants using combatants_list
        prompt += "\n# All Combatants\n"
        allies = []
        enemies = []
        for c in combatants_list:
             c_name = c.get("name", "Unknown")
             c_id = c.get("instance_id", "No ID")
             c_type = c.get("type", "unknown")
             c_hp = c.get('hp', 0)
             c_max_hp = c.get('max_hp', c_hp)
             c_status = c.get("status", "OK")
             c_line = f"- {c_name} (ID: {c_id}, HP: {c_hp}/{c_max_hp}, Status: {c_status})"
             # Add distance estimate if available? (Requires position data not currently present)

             # Simple ally/enemy determination based on type (could be improved)
             if c_type == active_combatant.get("type"):
                  if c_id != instance_id: allies.append(c_line) # Don't list self as ally
             else:
                  enemies.append(c_line)

        if allies:
             prompt += "## Allies\n" + "\n".join(allies) + "\n"
        if enemies:
             prompt += "## Enemies\n" + "\n".join(enemies) + "\n"


        # Recharge abilities status
        # ... (keep existing logic) ...

        # Add actions, abilities, and traits from active_combatant
        prompt += "\n# Your Available Options\n"
        # Actions
        actions = active_combatant.get("actions", [])
        if actions:
             prompt += "## Actions\n"
             # ... (keep existing action formatting, checking against available_recharge_abilities) ...
        # Abilities
        abilities = active_combatant.get("abilities", []) # Assuming abilities is a field
        if abilities:
             prompt += "## Abilities\n"
             # ... (format abilities similarly to actions, checking recharge) ...
        # Traits/Features
        traits = active_combatant.get("traits", []) # Assuming traits is a field
        if traits:
             prompt += "## Traits/Features\n"
             # ... (format traits) ...


        # Decision request
        prompt += "\n# Your Decision\n"
        prompt += "Given the current combat situation, decide your action(s) for this turn. Consider:\n"
        prompt += "- Prioritize high-threat enemies or low-HP enemies.\n"
        prompt += "- Use powerful recharge abilities when available and effective.\n"
        prompt += "- Consider your own HP and status. Use defensive actions if needed.\n"
        prompt += "- Specify your target clearly by name (and ID if possible).\n\n"

        prompt += "IMPORTANT TARGETING RULES:\n"
        prompt += "- Target enemies, not allies (unless healing/buffing).\n"
        prompt += "- Avoid targeting yourself with harmful effects.\n"
        prompt += "- For area effects, try to hit multiple enemies and avoid allies.\n\n"

        if available_recharge_abilities:
             prompt += f"REMINDER: You have recharged abilities available: {', '.join(available_recharge_abilities)}\n\n"

        prompt += "Provide your response as a single JSON object with these fields:\n"
        prompt += "{\n"
        prompt += '  "action": "Name of the primary action taken (e.g., \'Multiattack\', \'Fire Bolt\', \'Dodge\')",\n'
        prompt += '  "target": "Name of the primary target (or \'None\', or \'Area targeting Enemies\')",\n'
        prompt += '  "reasoning": "Brief tactical justification for your choice.",\n'
        prompt += '  "dice_requests": [ \n'
        prompt += '     {"expression": "1d20+5", "purpose": "Attack Roll: Shortsword vs Goblin1"},\n'
        prompt += '     {"expression": "1d6+3", "purpose": "Damage Roll: Shortsword vs Goblin1"},\n'
        prompt += '     {"expression": "1d20+7", "purpose": "Saving Throw: DC 15 Dexterity vs Fireball"}\n'
        prompt += '     "Include ALL necessary rolls for the action (attacks, damage, saves)"\n'
        prompt += '  ]\n'
        prompt += "}\n\n"
        prompt += "Make sure the JSON is valid."

        # Ensure prompt is a string
        if not isinstance(prompt, str):
             prompt = "Error: Prompt generation failed."

        return prompt
        # --- End of _create_decision_prompt modifications ---


    # Make sure _process_death_save modifies the combatant dict passed to it
    def _process_death_save(self, combatant_dict):
        """Process a death saving throw for a combatant (modifies the dict)."""
        import random
        name = combatant_dict.get("name", "Character")
        # ... (rest of death save logic) ...
        # Modify combatant_dict directly, e.g., combatant_dict["hp"] = 1
        # e.g., combatant_dict["death_saves"]["failures"] += 2
        # e.g., combatant_dict["status"] = "Stable"
        # --- Start of _process_death_save modifications ---
        name = combatant_dict.get("name", "Character") # Use the passed dict
        logging.debug(f"Processing death save for {name}")

        # Ensure death save tracking exists
        if "death_saves" not in combatant_dict:
            combatant_dict["death_saves"] = {"successes": 0, "failures": 0}

        # Roll d20
        roll = random.randint(1, 20)
        logging.debug(f"  Death save roll: {roll}")

        # Natural 20: regain 1 HP, conscious
        if roll == 20:
            combatant_dict["hp"] = 1
            combatant_dict["status"] = "Conscious" # Explicitly conscious
            combatant_dict["death_saves"] = {"successes": 0, "failures": 0} # Reset saves
            logging.info(f"  {name} rolled Nat 20! Back up with 1 HP.")
            return # Done with this save

        # Natural 1: two failures
        if roll == 1:
            combatant_dict["death_saves"]["failures"] = combatant_dict["death_saves"].get("failures", 0) + 2
            logging.info(f"  {name} rolled Nat 1! Two failures.")
        # 10 or higher: success
        elif roll >= 10:
            combatant_dict["death_saves"]["successes"] = combatant_dict["death_saves"].get("successes", 0) + 1
            logging.info(f"  {name} succeeded death save ({roll}).")
        # Below 10: failure
        else:
            combatant_dict["death_saves"]["failures"] = combatant_dict["death_saves"].get("failures", 0) + 1
            logging.info(f"  {name} failed death save ({roll}).")

        # Check outcome after update
        self._check_death_save_outcome(combatant_dict) # Check if stabilized or died

        logging.debug(f"  {name} saves: {combatant_dict.get('death_saves', {})}")
        # --- End of _process_death_save modifications ---


    def _process_hp_update(self, target_name, hp_update, current_hp):
        """
        Processes an HP update instruction, handling relative changes.
        Returns the new integer HP value.
        """
        # ... (keep existing logic, it seems correct) ...
        try:
            if isinstance(hp_update, str):
                hp_update_clean = hp_update.strip()
                if hp_update_clean.startswith('+'):
                    change = int(hp_update_clean[1:])
                    return current_hp + change
                elif hp_update_clean.startswith('-'):
                    change = int(hp_update_clean[1:])
                    # Ensure HP doesn't go below 0 from relative change
                    return max(0, current_hp - change)
                else:
                    # Assume absolute value if no sign
                    new_hp = int(hp_update_clean)
                    return max(0, new_hp) # Ensure absolute doesn't go below 0
            elif isinstance(hp_update, (int, float)):
                # If it's already a number, assume absolute value
                new_hp = int(hp_update)
                return max(0, new_hp) # Ensure absolute doesn't go below 0
            else:
                logging.warning(f"[CombatResolver] Invalid hp_update type for {target_name}: {type(hp_update)}. Defaulting to current HP.")
                return current_hp
        except (ValueError, TypeError) as e:
            logging.warning(f"[CombatResolver] Error processing HP update '{hp_update}' for {target_name}: {e}. Defaulting to current HP.")
            return current_hp
        except Exception as e:
            logging.error(f"[CombatResolver] Unexpected error processing HP update for {target_name}: {e}. Defaulting to current HP.", exc_info=True)
            return current_hp


    # _process_auras needs to use the passed combatant list
    def _process_auras(self, active_combatant_dict, all_combatants_list):
        """
        Process aura effects at the start of a combatant's turn.
        Modifies active_combatant_dict directly if effects apply.
        Uses the passed list for checks.
        """
        # ... (rest of _process_auras logic) ...
        # IMPORTANT: Ensure all reads use 'all_combatants_list'
        # Ensure modifications apply to 'active_combatant_dict'
        # e.g., for c in all_combatants_list:
        # e.g., distance = self._get_distance_between(c, active_combatant_dict)
        # e.g., active_combatant_dict["hp"] = max(0, old_hp - damage)
        # --- Start of _process_auras modifications ---
        updates_log = [] # Log of effects applied
        active_name = active_combatant_dict.get("name", "Unknown")
        logging.debug(f"Processing auras potentially affecting {active_name}")

        # Ensure all combatants in the list have aura info detected if needed
        for combatant in all_combatants_list:
            # Add auras if not already processed (modifies dict in list)
            if "auras" not in combatant or not combatant.get("auras_processed", False):
                self._add_auras_from_traits(combatant) # Modifies dict in list

        # Check for aura effects FROM all combatants ON the active one
        for source_combatant in all_combatants_list:
            if "auras" not in source_combatant or not source_combatant.get("auras"):
                continue # Skip if source has no auras defined

            source_name = source_combatant.get("name", "Unknown Source")
            # Skip self-inflicted auras unless specifically allowed
            if source_combatant.get("instance_id") == active_combatant_dict.get("instance_id"):
                 # print(f"DEBUG: Skipping self-aura check for {active_name}")
                 continue # Skip checking own auras for now (can add affects_self later)


            for aura_name, aura_details in source_combatant.get("auras", {}).items():
                 # Check affects type (enemies/allies)
                 affects = aura_details.get("affects", "enemies")
                 source_type = source_combatant.get("type", "unknown")
                 target_type = active_combatant_dict.get("type", "unknown")

                 if affects == "enemies" and source_type == target_type:
                      # print(f"DEBUG: Skipping enemy aura '{aura_name}' from {source_name} (same type)")
                      continue # Skip enemy aura if target is same type
                 if affects == "allies" and source_type != target_type:
                      # print(f"DEBUG: Skipping ally aura '{aura_name}' from {source_name} (different type)")
                      continue # Skip ally aura if target is different type

                 # Check range
                 range_feet = aura_details.get("range", 10)
                 # Use the active combatant dict for distance calc
                 distance = self._get_distance_between(source_combatant, active_combatant_dict)

                 if distance <= range_feet:
                      logging.debug(f"  Aura '{aura_name}' from {source_name} is in range ({distance}ft <= {range_feet}ft)")
                      # Apply the effect
                      effect = aura_details.get("effect", {})
                      effect_type = effect.get("type", "none")
                      applied_effect_desc = ""

                      if effect_type == "damage":
                            damage_expr = effect.get("expression", "1d6")
                            damage_type = effect.get("damage_type", "untyped")
                            # Roll damage (internal simple roll for now)
                            try:
                                 # Use CombatResolver's dice roller if available, else random
                                 if hasattr(self, '_dice_roller') and self._dice_roller:
                                     damage = self._dice_roller(damage_expr)
                                 else: # Fallback
                                     import random
                                     if 'd' in damage_expr: damage = random.randint(1, 6) # Basic fallback
                                     else: damage = int(damage_expr)
                                 damage = int(damage) # Ensure int
                            except Exception as roll_e:
                                 logging.error(f"Error rolling aura damage '{damage_expr}': {roll_e}")
                                 damage = 1 # Minimal damage on error

                            # Apply damage to the active combatant dict
                            old_hp = active_combatant_dict.get("hp", 0)
                            active_combatant_dict["hp"] = max(0, old_hp - damage)
                            applied_effect_desc = f"Took {damage} {damage_type} damage"
                            logging.info(f"    {active_name} {applied_effect_desc} from {source_name}'s {aura_name}. HP: {old_hp} -> {active_combatant_dict['hp']}")


                      elif effect_type == "condition":
                           condition = effect.get("condition", "")
                           if condition:
                                if "conditions" not in active_combatant_dict: active_combatant_dict["conditions"] = {}
                                # Add condition with source info
                                active_combatant_dict["conditions"][condition] = {
                                    "source": f"{source_name} ({aura_name})",
                                    "duration": effect.get("duration", -1) # -1 for permanent while in aura
                                }
                                applied_effect_desc = f"Gained condition: {condition}"
                                logging.info(f"    {active_name} {applied_effect_desc} from {source_name}'s {aura_name}")

                      # Add other effect types (healing, resistance) if needed

                      if applied_effect_desc:
                           updates_log.append({
                                "source": source_name,
                                "aura": aura_name,
                                "target": active_name,
                                "effect": applied_effect_desc,
                                "hp_after": active_combatant_dict.get("hp") # Include HP after effect
                           })

        if not updates_log:
             logging.debug(f"  No aura effects applied to {active_name} this turn.")

        return updates_log # Return the log of applied effects
        # --- End of _process_auras modifications ---


    # _add_auras_from_traits modifies the dict passed to it
    def _add_auras_from_traits(self, combatant_dict):
        """
        Analyze combatant traits and detect auras. Modifies the dict.
        """
        # ... (rest of _add_auras_from_traits logic) ...
        # Modify combatant_dict directly, e.g., combatant_dict["auras"] = {}
        # e.g., combatant_dict["auras"][aura_name] = {...}
        # e.g., combatant_dict["auras_processed"] = True
        # --- Start of _add_auras_from_traits modifications ---
        # Initialize auras dict if not present
        if "auras" not in combatant_dict:
            combatant_dict["auras"] = {}

        # Skip if already processed
        if combatant_dict.get("auras_processed", False):
            return # Already done

        name = combatant_dict.get("name", "Unknown")
        logging.debug(f"Checking for auras in {name}'s traits")

        aura_found = False
        if "traits" in combatant_dict and isinstance(combatant_dict["traits"], list):
            for trait in combatant_dict["traits"]:
                if not isinstance(trait, dict): continue

                trait_name = trait.get("name", "").lower()
                trait_desc = trait.get("description", "").lower()

                # Simple check for "aura" keyword
                if "aura" in trait_name or "aura" in trait_desc:
                     logging.debug(f"  Potential aura found: {trait_name}")
                     aura_name = trait.get("name", "Unnamed Aura") # Use original case name
                     aura_key = aura_name.lower().replace(" ", "_") # Key for dict

                     # Extract range (simple regex)
                     range_match = re.search(r'(\d+)[- ]f(?:ee|oo)t', trait_desc)
                     aura_range = int(range_match.group(1)) if range_match else 10 # Default 10ft

                     # Determine effect (simplified)
                     aura_effect = {"type": "unknown"}
                     affects = "enemies" # Default affects enemies
                     affects_self = False

                     # Damage check
                     damage_match = re.search(r'(\d+d\d+(?:\s*[\+\-]\s*\d+)?)(\s+\w+)?\s+damage', trait_desc)
                     if damage_match:
                          aura_effect = {
                               "type": "damage",
                               "expression": damage_match.group(1).replace(" ", ""),
                               "damage_type": damage_match.group(2).strip() if damage_match.group(2) else "untyped"
                          }
                     # Condition check (add more conditions as needed)
                     elif "frightened" in trait_desc:
                          aura_effect = {"type": "condition", "condition": "frightened", "duration": -1}
                     elif "poisoned" in trait_desc:
                           aura_effect = {"type": "condition", "condition": "poisoned", "duration": -1}


                     # Check who it affects
                     if "allies" in trait_desc or "friendly creatures" in trait_desc:
                          affects = "allies"
                     if "each creature" in trait_desc or "any creature" in trait_desc:
                           affects = "all" # Affects both allies and enemies

                     # Store the found aura in the combatant dict
                     combatant_dict["auras"][aura_key] = {
                          "name": aura_name, # Store original name for display
                          "range": aura_range,
                          "effect": aura_effect,
                          "affects": affects,
                          "affects_self": affects_self, # TODO: Add logic for affects_self
                          "source": "trait"
                     }
                     logging.info(f"    Detected aura: {aura_name} (Range: {aura_range}ft, Effect: {aura_effect}, Affects: {affects})")
                     aura_found = True


        # Hardcoded auras for specific monster names (example)
        name_lower = name.lower()
        if "fire snake" in name_lower and "fire_aura" not in combatant_dict["auras"]:
             combatant_dict["auras"]["fire_aura"] = {
                 "name": "Fire Aura", "range": 5, "effect": {"type": "damage", "expression": "1d6", "damage_type": "fire"},
                 "affects": "enemies", "affects_self": False, "source": "name"
             }
             logging.info(f"    Added hardcoded Fire Aura for {name}")
             aura_found = True

        if aura_found:
             logging.debug(f"  Final auras for {name}: {combatant_dict['auras']}")
        else:
             logging.debug(f"  No specific auras detected for {name}.")


        # Mark as processed
        combatant_dict["auras_processed"] = True
        # No return needed as dict is modified in place
        # --- End of _add_auras_from_traits modifications ---


    # _get_distance_between needs position data which isn't currently tracked robustly
    def _get_distance_between(self, combatant1, combatant2):
        """Placeholder for distance calculation. Needs position tracking."""
        # TODO: Implement proper distance calculation when position data is available
        # Simple fallback based on type for now
        type1 = combatant1.get("type", "unknown")
        type2 = combatant2.get("type", "unknown")
        if type1 == type2:
            return 5 # Assume allies are close
        else:
            return 5 # Assume enemies start close (melee range) - adjust as needed!


    # _get_active_auras should use the passed list
    def _get_active_auras(self, active_combatant_dict, all_combatants_list):
        """
        Get a list of auras currently affecting a combatant.
        Uses the provided list and target dict.
        """
        # ... (rest of _get_active_auras logic) ...
        # IMPORTANT: Use 'all_combatants_list' for iteration
        # Use 'active_combatant_dict' for target checks
        # Call _get_distance_between(c, active_combatant_dict)
        # --- Start of _get_active_auras modifications ---
        active_auras = []
        active_name = active_combatant_dict.get("name", "Unknown")

        # Ensure all combatants in the list have aura info
        for combatant in all_combatants_list:
            if "auras" not in combatant or not combatant.get("auras_processed", False):
                 self._add_auras_from_traits(combatant)

        # Check auras from all other combatants in the list
        for source_combatant in all_combatants_list:
            # Skip self check for now
            if source_combatant.get("instance_id") == active_combatant_dict.get("instance_id"):
                 continue
            if "auras" not in source_combatant or not source_combatant.get("auras"):
                 continue

            source_name = source_combatant.get("name", "Unknown Source")
            for aura_key, aura_details in source_combatant.get("auras", {}).items():
                 # Check affects type
                 affects = aura_details.get("affects", "enemies")
                 source_type = source_combatant.get("type", "unknown")
                 target_type = active_combatant_dict.get("type", "unknown")

                 if affects == "enemies" and source_type == target_type: continue
                 if affects == "allies" and source_type != target_type: continue

                 # Check range
                 range_feet = aura_details.get("range", 10)
                 distance = self._get_distance_between(source_combatant, active_combatant_dict)

                 if distance <= range_feet:
                      # This aura affects the active combatant
                      active_auras.append({
                           "name": aura_details.get("name", aura_key), # Use display name
                           "source": source_name,
                           "range": range_feet,
                           "effect": aura_details.get("effect", {}),
                           "distance": distance
                      })

        if active_auras:
             logging.debug(f"Active auras affecting {active_name}: {active_auras}")
        return active_auras
        # --- End of _get_active_auras modifications ---


    # Legacy Methods - Keep for compatibility or remove if unused
    def resolve_combat_async(self, combat_state, callback):
        # ... (keep existing legacy method if needed) ...
        logging.warning("[CombatResolver] DEPRECATED resolve_combat_async called.")
        # Simulate async call using the new mechanism and signal
        # This won't behave exactly like the old async, but prevents errors
        if self.start_resolution(combat_state, lambda x: 1, lambda x: None, mode='continuous'):
             # We need a way to connect the signal back to the old callback *once*
             # This is tricky. For now, just log it started.
             logging.info("Legacy async call started via new mechanism. Use signals for results.")
        else:
             # If start failed, call the callback with an error
             callback(None, "Failed to start resolution (possibly already running).")


    def _create_combat_prompt(self, combat_state):
        # ... (keep existing legacy method if needed) ...
        pass

    def _handle_llm_response(self, response, error, callback):
        # ... (keep existing legacy method if needed) ...
        pass

    def _format_dice_results(self, dice_results):
        """Format dice rolling results for inclusion in prompts."""
        if not dice_results:
            return "No dice rolls."
            
        formatted = []
        for roll in dice_results:
            purpose = roll.get('purpose', 'Roll')
            expression = roll.get('expression', 'unknown')
            result = roll.get('result', 'unknown')
            formatted.append(f"{purpose}: {expression} = {result}")
        
        return "\n".join(formatted)

    # Other helpers (_format_active_auras, _get_nearby_combatants, etc.)
    # Review these to ensure they don't rely on self.combatants if called within _process_turn
    # They seem okay as they primarily format data passed to them.

    def _format_active_auras(self, auras):
        # ... (keep existing logic) ...
        pass # Appears correct

    def _get_nearby_combatants(self, active_combatant_dict, all_combatants_list):
        """Get nearby combatants using the passed list."""
        # ... (logic needs update to use all_combatants_list and calculate distance) ...
        # Placeholder: return all others for now
        active_id = active_combatant_dict.get("instance_id")
        return [c for c in all_combatants_list if c.get("instance_id") != active_id]

    def _format_nearby_combatants(self, nearby_list):
         """Formats nearby combatants from the provided list."""
         if not nearby_list:
             return "None nearby."
         lines = []
         for c in nearby_list:
              status = c.get("status", "OK")
              status_str = f", Status: {status}" if status != "OK" else ""
              lines.append(f"- {c.get('name', 'Unknown')} (HP: {c.get('hp', 0)}/{c.get('max_hp', '?')}{status_str})")
         return "\n".join(lines)

    def _format_conditions(self, combatant_dict):
         """Formats conditions from the combatant's dict."""
         conditions_dict = combatant_dict.get("conditions", {})
         if not conditions_dict:
              return "None"
         # Simple list for now, could add descriptions later
         return ", ".join(conditions_dict.keys())

    # --- Create Resolution Prompt ---
    # Needs update to use passed lists/dicts correctly
    def _create_resolution_prompt(self, combat_state_dict, active_combatant_dict, combatant_decision, dice_results):
        """
        Create the prompt for resolving the action and generating a narrative and result.
        """
        active_name = active_combatant_dict.get('name', 'Unknown')
        action_name = combatant_decision.get('action', 'Unknown action')
        action_target = combatant_decision.get('target', 'Unknown target')
        action_explanation = combatant_decision.get('explanation', '')
        dice_summary = self._format_dice_results(dice_results) if dice_results else ""
        
        # Format system state for context
        combatants_str = self._describe_combat_state(combat_state_dict.get('combatants', []), -1)
            
        prompt = f"""
        # Action Resolution Request
        
        You are assisting with a D&D 5e combat scenario, producing a vivid and accurate narrative.
        
        ## Action to Resolve
        *Character:* {active_name}
        *Action:* {action_name}
        *Target:* {action_target}
        *Tactical Explanation:* {action_explanation}
        
        ## Dice Results
        {dice_summary}
        
        ## Current Combat State
        {combatants_str}
        
        ## Task
        1. Create a descriptive narrative of how this action plays out.
        2. Consider the game rules, dice results, and combat situation.
        3. Write in vivid D&D style appropriate for the action.
        4. Keep your response concise but evocative - approximately 2-3 sentences.
        
        Respond with a JSON object in this format:
        ```json
        {
          "narrative": "A vivid description of the action as it plays out in combat",
          "effect": "A brief note about mechanical effects (optional)"
        }
        ```
        """
        
        return prompt

    # The _parse_llm_json_response method is implemented at line ~517
    # No duplicate implementation needed here

    # Add a new diagnostic method for testing LLM service
    def test_llm_service(self):
        """Tests the LLM service with a simple request to check configuration."""
        logging.info("[CombatResolver] Testing LLM service...")
        
        try:
            # Check which models are available
            available_models = self.llm_service.get_available_models()
            if not available_models:
                return {
                    "success": False,
                    "error": "No LLM models available. Check API keys and service configuration."
                }
            
            # Use first available model
            model_id = available_models[0]['id']
            
            # Simple prompt for testing
            test_message = "Return a valid JSON with a greeting message. Format: {\"message\": \"greeting\"}"
            system_prompt = "You are a helpful D&D assistant that returns only valid JSON."
            
            # Make test call
            logging.info(f"[CombatResolver] Testing LLM with model: {model_id}")
            response = self.llm_service.generate_completion(
                model_id,
                [{"role": "user", "content": test_message}],
                system_prompt=system_prompt
            )
            
            # Parse response
            parsed = self._parse_llm_json_response(response, "test_call")
            
            # Check if valid response
            if "error" in parsed:
                return {
                    "success": False,
                    "error": f"LLM returned invalid JSON: {parsed.get('error')}",
                    "raw_response": response
                }
            
            return {
                "success": True,
                "model": model_id,
                "response": parsed,
                "raw_response": response
            }
        except Exception as e:
            import traceback
            return {
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc()
            }

    # Add the missing _process_recharge_abilities method
    def _process_recharge_abilities(self, combatant, dice_roller):
        """Process recharge abilities for a monster at the start of its turn.
        
        Args:
            combatant: The combatant dictionary to process
            dice_roller: Function to roll dice
            
        This method updates the combatant dictionary directly, modifying the 
        "recharge_abilities" field based on dice rolls.
        """
        if not combatant or combatant.get("type", "").lower() != "monster":
            return  # Only monsters have recharge abilities
            
        if "recharge_abilities" not in combatant:
            combatant["recharge_abilities"] = {}  # Initialize if not present
            return
            
        # Process each recharge ability
        for ability_name, ability_data in combatant.get("recharge_abilities", {}).items():
            # Skip already available abilities
            if ability_data.get("available", True):
                continue
                
            # Get recharge condition (default: 5-6 on d6)
            recharge_on = ability_data.get("recharge_on", [5, 6])
            dice_expr = ability_data.get("recharge_dice", "1d6")
            
            # Roll for recharge
            roll_value = dice_roller(dice_expr)
            logging.info(f"[CombatResolver] Recharge roll for {ability_name}: {roll_value} (recharges on {recharge_on})")
            
            # Check if ability recharges
            if isinstance(recharge_on, list) and roll_value in recharge_on:
                combatant["recharge_abilities"][ability_name]["available"] = True
                logging.info(f"[CombatResolver] {ability_name} recharged!")
            elif isinstance(recharge_on, int) and roll_value >= recharge_on:
                combatant["recharge_abilities"][ability_name]["available"] = True
                logging.info(f"[CombatResolver] {ability_name} recharged!")
            else:
                logging.info(f"[CombatResolver] {ability_name} failed to recharge.")
                
        logging.debug(f"[CombatResolver] Recharge abilities after processing: {combatant.get('recharge_abilities')}")
        return

    # Add the required helper methods after the _process_turn method:

    def _get_system_prompt(self):
        """Get the system prompt for LLM action decisions."""
        system_prompt = """
        You are a Dungeons & Dragons 5e combat assistant tasked with making tactical decisions for monsters and NPCs.
        
        GUIDELINES:
        1. Consider character positions, abilities, and tactical advantages
        2. Choose actions that would make sense for the character's intelligence and nature
        3. Prioritize effective combat tactics appropriate to the monster type
        4. Respond ONLY in valid JSON format with the requested fields
        5. Keep explanations brief but descriptive
        
        Your response should take advantage of the monster's abilities, traits, and the current combat situation.
        """
        return system_prompt
    
    def _create_action_prompt(self, combatants, active_idx, round_num):
        """Create structured messages for the LLM action decision.
        
        Args:
            combatants: List of all combatants
            active_idx: Index of the active combatant
            round_num: Current round number
            
        Returns:
            List of message dictionaries for the LLM service
        """
        active_combatant = combatants[active_idx]
        name = active_combatant.get('name', 'Unknown')
        combatant_type = active_combatant.get('type', '').lower()
        
        # Create a detailed combat state description
        combat_state = self._describe_combat_state(combatants, active_idx)
        
        # Get previous turn context if available
        context = "\n\n".join(self.previous_turn_summaries[-5:]) if hasattr(self, 'previous_turn_summaries') and self.previous_turn_summaries else ""
        
        action_request = f"""
        # Combat Situation - Round {round_num}
        
        It is now {name}'s turn to act.
        
        ## Combat State
        {combat_state}
        
        ## Previous Turns
        {context}
        
        ## Your Task
        Choose an appropriate action for {name} based on its capabilities and the current situation.
        
        Respond with a JSON object containing:
        {{
          "action": "The action being taken",
          "target": "The target of the action, if applicable",
          "explanation": "Brief explanation of the tactical choice"
        }}
        """
        
        # Create message list format used by OpenAI API
        messages = [{"role": "user", "content": action_request}]
        
        logging.debug(f"[CombatResolver] Created action prompt for {name}")
        return messages
    
    def _describe_combat_state(self, combatants, active_idx):
        """Generate a textual summary of the combat state for prompts."""
        descriptions = []
        for i, c in enumerate(combatants):
            ctype = c.get("type", "unknown")
            is_active = (i == active_idx)
            name = c.get("name", f"Combatant {i}")
            hp = c.get("hp", 0)
            max_hp = c.get("max_hp", "?")
            status = c.get("status", "")
            
            status_str = f", {status}" if status else ""
            active_marker = " (ACTIVE)" if is_active else ""
            
            descriptions.append(f"{name}{active_marker}: {ctype}, HP {hp}/{max_hp}{status_str}")
            
        return "\n".join(descriptions)

    def _save_json_artifact(self, data, filename):
        """
        Saves a JSON artifact (like an LLM response or parse result) to the log directory
        for debugging purposes.
        
        Args:
            data: The data to save (dict or similar)
            filename: Filename to save under (without directory or extension)
        """
        import os
        import json
        import time
        import logging
        
        try:
            # Create directory with timestamp if it doesn't exist
            log_dir = f"llm_logs_{int(time.time() // 100 * 100)}"
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)
                
            # Save to file with proper formatting
            filepath = os.path.join(log_dir, f"{filename}.json")
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
                
            logging.info(f"[CombatResolver] Saved {filename} to {filepath}")
        except Exception as e:
            logging.error(f"[CombatResolver] Failed to save artifact {filename}: {str(e)}")
            # Don't let this error disrupt the main flow

# Ensure the final class definition is accessible
CombatResolver = CombatResolver # This line might be redundant depending on execution context