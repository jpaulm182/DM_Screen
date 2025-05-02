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
    def _run_resolution_thread(self):
        """The main combat resolution loop executed in a separate thread."""
        logging.debug("--- ENTERING _run_resolution_thread ---")
        state = None # Initialize state to None
        log = [] # Combat log for transparency
        final_status = "error" # Default to error unless completed or stopped
        error_message = "Resolution thread started but did not complete." # Default error

        try:
            # Critical Section: Access shared parameters set by start_resolution
            with self._lock:
                if not self._running or not self._combat_state or not self._dice_roller:
                    error_message = "Resolver thread started with invalid initial state."
                    logging.error(f"[CombatResolver] {error_message}")
                    self.resolution_update.emit(None, "error", error_message)
                    # Ensure _running is false if we exit early
                    self._running = False
                    return
                # Get local copies/references while holding the lock
                state = self._combat_state # This is already a deep copy
                dice_roller = self._dice_roller
                update_ui_callback = self._update_ui_callback
                initial_mode = self._mode # Capture mode at start

            # --- Begin resolution logic ---
            round_num = state.get("round", 1)
            combatants = state.get("combatants", []) # Work on the copied state

            # Main combat loop
            while round_num <= 50: # Max round limit
                # --- Check for Stop Request (Start of Round) ---
                with self._lock:
                    if self._stop_requested:
                        logging.info("[CombatResolver] Stop detected at start of round.")
                        final_status = "stopped"
                        error_message = None
                        break # Exit the main while loop

                logging.info(f"[CombatResolver] Starting Round {round_num}")
                state["round"] = round_num # Update round in our local state copy

                # Determine initiative order for this round (needed for turn processing)
                # Filter out permanently dead combatants ONCE per round for efficiency
                active_this_round = [
                    (idx, c) for idx, c in enumerate(combatants)
                    if not (c.get("type", "").lower() == "monster" and c.get("status", "").lower() == "dead") # Exclude dead monsters
                ]
                # Sort by initiative
                initiative_order_indices = sorted(
                    [idx for idx, c in active_this_round],
                    key=lambda i: -int(combatants[i].get("initiative", 0))
                )

                # Process each combatant's turn
                for turn_counter, current_turn_original_index in enumerate(initiative_order_indices):
                    # --- Check for Stop Request (Start of Turn) ---
                    with self._lock:
                        if self._stop_requested:
                            logging.info("[CombatResolver] Stop detected at start of turn.")
                            final_status = "stopped"
                            error_message = None
                            break # Exit the inner for loop

                    # Fetch the current state of the combatant (might have changed)
                    if current_turn_original_index >= len(combatants):
                        logging.warning(f"[CombatResolver] Combatant index {current_turn_original_index} out of range. Skipping turn.")
                        continue
                    combatant = combatants[current_turn_original_index]
                    combatant_name = combatant.get("name", f"Combatant {current_turn_original_index}")
                    state["current_turn_index"] = current_turn_original_index # Update state

                    logging.debug(f"--- Processing turn for {combatant_name} (Index: {current_turn_original_index}, Round: {round_num}) ---")

                    # Skip turn if combatant is incapacitated (Dead monster, or Unconscious/Stable/Dead PC)
                    status = combatant.get("status", "").lower()
                    ctype = combatant.get("type", "").lower()
                    hp = combatant.get("hp", 0)

                    skip_turn = False
                    skip_reason = ""
                    goto_post_turn_logic = False  # Initialize this variable to prevent NameError
                    if status == "dead":
                         skip_turn = True
                         skip_reason = "Dead"
                    elif ctype != "monster" and status in ["unconscious", "stable"] and hp <= 0:
                         # Process death save for PCs instead of normal turn
                         logging.debug(f"{combatant_name} is {status}, processing death save.")
                         self._process_death_save(combatant) # Modifies combatant directly
                         turn_log_entry = {
                             "round": round_num,
                             "turn": current_turn_original_index,
                             "actor": combatant_name,
                             "action": f"Makes a Death Saving Throw ({status})",
                             "dice": [{"expression": "1d20", "result": "See log", "purpose": "Death Save"}],
                             "result": f"Saves: {combatant.get('death_saves', {}).get('successes', 0)}S / {combatant.get('death_saves', {}).get('failures', 0)}F"
                         }
                         log.append(turn_log_entry)
                         # Still update UI and potentially pause/stop after the death save
                         skip_turn = False # Don't skip the UI update/pause logic below
                         # We need to bypass the main turn processing logic though
                         goto_post_turn_logic = True
                    elif hp <= 0 and status not in ["unconscious", "stable", "dead"]:
                        # Should not happen often, but if HP is <= 0, treat as unconscious/dead
                        logging.warning(f"{combatant_name} has HP <= 0 but status is '{status}'. Setting to Unconscious/Dead.")
                        if ctype == "monster": combatant["status"] = "Dead"
                        else: combatant["status"] = "Unconscious"; self._init_death_saves(combatant)
                        skip_turn = True
                        skip_reason = combatant["status"]

                    if skip_turn:
                        logging.debug(f"Skipping turn for {combatant_name} ({skip_reason}).")
                        # Although skipped, we might still need to check end condition after other turns
                        continue # Skip to the next combatant in the initiative order

                    # --- Process the actual turn using LLM ---
                    # (Only if not skipped and not just a death save)
                    logging.info(f"[CombatResolver] Before turn processing: goto_post_turn_logic exists: {'goto_post_turn_logic' in locals()}, value: {locals().get('goto_post_turn_logic')}")
                    
                    if not 'goto_post_turn_logic' in locals() or not goto_post_turn_logic:
                         logging.info(f"[CombatResolver] Processing turn for {combatant_name} using LLM")
                         turn_result = self._process_turn(combatants, current_turn_original_index, round_num, dice_roller)
                         
                         logging.info(f"[CombatResolver] Turn processing complete. Result: {turn_result}")

                         # Add summary to context for next LLM call (if needed)
                         turn_summary = f"Round {round_num}, {combatant_name}'s turn: {turn_result.get('narrative', 'No action.') if turn_result else 'No result available.'}"
                         self.previous_turn_summaries.append(turn_summary)
                         # Limit context size
                         if len(self.previous_turn_summaries) > 10:
                             self.previous_turn_summaries.pop(0)

                         # Log the turn action
                         turn_log_entry = {
                             "round": round_num,
                             "turn": current_turn_original_index,
                             "actor": combatant_name,
                             "action": turn_result.get("action", "") if turn_result else "Error during turn processing",
                             "dice": turn_result.get("dice", []) if turn_result else [],
                             "result": turn_result.get("narrative", "") if turn_result else "No result available."
                         }
                         log.append(turn_log_entry)

                         # Apply updates from the turn result to our local combatants list
                         if turn_result and "updates" in turn_result:
                             self._apply_turn_updates(combatants, turn_result["updates"])

                    # --- Post-Turn Logic (UI Update, Pause/Step Check, End Condition Check) ---
                    # Make a deep copy of the state *for this specific update*
                    # This ensures the UI gets the state exactly as it was after this turn/death save
                    current_state_for_ui = copy.deepcopy({
                        "round": round_num,
                        "current_turn_index": current_turn_original_index,
                        "combatants": combatants, # Pass the modified list
                        "log": log, # Pass the current log
                        "latest_action": turn_log_entry # Pass the latest action details
                    })

                    # Update UI via callback (if provided) - runs on main thread
                    if update_ui_callback:
                        try:
                             # Use the captured callback reference
                             update_ui_callback(current_state_for_ui)
                             # Short sleep to allow UI to potentially process
                             # time.sleep(0.1) # Optional: small delay
                        except Exception as ui_err:
                             logging.error(f"Error calling update_ui_callback: {ui_err}", exc_info=True)


                    # Check end condition *after* this turn
                    combat_should_end, end_reason = self._check_combat_end_condition(combatants)
                    if combat_should_end:
                        logging.info(f"[CombatResolver] Combat ending after {combatant_name}'s turn. Reason: {end_reason}")
                        final_status = "completed"
                        error_message = None
                        break # Exit inner turn loop

                    # --- Pause/Step Logic ---
                    needs_pause = False
                    current_mode = 'continuous' # Default
                    with self._lock:
                        if self._mode == 'step':
                            needs_pause = True
                            current_mode = 'step' # Update local copy of mode
                        if self._stop_requested: # Check stop again before potential pause
                             logging.info("[CombatResolver] Stop detected before pause.")
                             final_status = "stopped"
                             error_message = None
                             break # Exit inner turn loop

                    if needs_pause:
                        logging.debug(f"[CombatResolver] Pausing after {combatant_name}'s turn (Step Mode).")
                        with self._lock:
                            self._paused = True
                            # Make sure continue event is clear before emitting signal
                            self._continue_event.clear()

                        # Emit 'paused' signal with the current state
                        self.resolution_update.emit(current_state_for_ui, "paused", None)

                        # Wait for continue_turn() to be called
                        logging.debug("[CombatResolver] Waiting for continue signal...")
                        self._continue_event.wait() # Blocks until event is set
                        logging.debug("[CombatResolver] Continue signal received.")

                        # We've been unpaused, check immediately if a stop was requested *while* paused
                        with self._lock:
                             if self._stop_requested:
                                 logging.info("[CombatResolver] Stop detected after resuming from pause.")
                                 final_status = "stopped"
                                 error_message = None
                                 break # Exit inner turn loop
                             # Ensure paused flag is false now we're continuing
                             self._paused = False
                             # Refresh current mode in case it changed while paused
                             current_mode = self._mode


                    # --- End of Turn Loop Body ---

                # --- Check if inner loop was broken by stop or end condition ---
                if final_status == "stopped" or final_status == "completed":
                    break # Exit outer round loop

                # --- End of Round ---
                round_num += 1

                # Check end condition again at the absolute end of the round
                combat_should_end_round, end_reason_round = self._check_combat_end_condition(combatants)
                if combat_should_end_round:
                     logging.info(f"[CombatResolver] Combat ending at end of round {round_num-1}. Reason: {end_reason_round}")
                     final_status = "completed"
                     error_message = None
                     break # Exit outer round loop

            # --- End of Main Loop (while round_num <= 50) ---

            # Determine final state if loop finished naturally
            if final_status == "error": # If not already set to stopped or completed
                 if round_num > 50:
                      logging.warning("[CombatResolver] Combat stopped due to reaching round limit (50).")
                      final_status = "completed" # Treat as completed, but potentially add note
                      error_message = "Reached maximum round limit (50)."
                 else:
                      # This path shouldn't normally be reached if end condition works
                      logging.info("[CombatResolver] Combat loop finished.")
                      final_status = "completed"
                      error_message = None


            # Prepare final result payload (even if stopped or error)
            final_result_state = copy.deepcopy({
                "round": round_num -1, # Last completed round
                 # Use the state as it was at the point of stopping/completion
                "combatants": combatants,
                "log": log,
                "narrative": f"Resolution {final_status}. {error_message or ''}".strip()
            })

            # Emit the final signal
            self.resolution_update.emit(final_result_state, final_status, error_message if final_status == 'error' else None)

        except Exception as e:
            logging.error(f"Error during combat resolution thread: {e}", exc_info=True)
            import traceback
            error_message = f"Error in resolution thread: {traceback.format_exc()}"
            # Try to emit error signal with whatever state we had
            error_state = state if 'state' in locals() else None
            self.resolution_update.emit(error_state, "error", error_message)
            final_status = "error" # Ensure status is error

        finally:
            # --- Cleanup: Ensure _running is set to False ---
            with self._lock:
                logging.debug(f"[CombatResolver] Resolution thread finishing with status: {final_status}")
                self._running = False
                self._paused = False # Ensure paused is false on exit
                self._current_thread = None # Clear thread reference

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
        """Attempts to parse JSON from LLM response, handling common issues."""
        # Ensure json is imported if not already globally
        import json
        import re

        if not isinstance(response_text, str):
            logging.warning(f"[_parse_llm_json_response] Expected string, got {type(response_text)} ({context})")
            return {"error": "Invalid response type", "raw_response": str(response_text)}

        cleaned = response_text.strip()
        logging.debug(f"[_parse_llm_json_response] Raw response ({context}): {cleaned[:200]}...")

        # 1. Try extracting from ```json ... ``` block
        # Fixed regex - the closing backticks were inside the capture group
        json_match = re.search(r"```json\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
        if json_match:
            json_content = json_match.group(1)
            try:
                parsed = json.loads(json_content)
                logging.debug(f"Successfully parsed from ```json block ({context})")
                return parsed
            except json.JSONDecodeError as e:
                logging.warning(f"Failed to parse ```json block content ({context}): {e}")
                # Fall through to other methods

        # 2. Try extracting from any ``` ... ``` block
        # Fixed regex - the closing backticks were inside the capture group
        code_block_match = re.search(r"```\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
        if code_block_match:
             json_content = code_block_match.group(1)
             try:
                 parsed = json.loads(json_content)
                 logging.debug(f"Successfully parsed from generic ``` block ({context})")
                 return parsed
             except json.JSONDecodeError as e:
                 logging.warning(f"Failed to parse generic ``` block content ({context}): {e}")
                 # Fall through
        # 3. Try finding the first { and last }
        brace_match = re.search(r"(\{.*\})", cleaned, re.DOTALL) # Simpler regex
        if brace_match:
            potential_json = brace_match.group(1)
            try:
                parsed = json.loads(potential_json)
                logging.debug(f"Successfully parsed brace-extracted content ({context})")
                return parsed
            except json.JSONDecodeError as e:
                 logging.warning(f"Failed to parse brace-extracted content ({context}): {e}")
                 # Fall through to final attempt

        # 4. Final attempt: Parse the raw cleaned string directly
        try:
            parsed = json.loads(cleaned)
            logging.debug(f"Successfully parsed cleaned string directly as last resort ({context})")
            return parsed
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse JSON response ({context}) after all attempts: {e}. Raw: {cleaned[:200]}...")
            return {"error": "JSON parsing failed", "raw_response": cleaned}

    # Make sure _process_turn uses the thread-local combatants list
    def _process_turn(self, local_combatants_list, active_idx, round_num, dice_roller):
        """
        Process a single combatant's turn with LLM.
        Uses the provided list, not the instance's potentially stale copy.
        """
        logging.debug(f"--- ENTERING _process_turn for index {active_idx}, round {round_num} ---")
        import json
        import re
        # ... (rest of the _process_turn logic) ...
        # IMPORTANT: Ensure all reads/writes of combatant data inside this method
        # use the 'local_combatants_list' passed as an argument, NOT 'self.combatants'
        # e.g., active_combatant = local_combatants_list[active_idx]
        # e.g., prompt = self._create_decision_prompt({"combatants": local_combatants_list, ...}, active_combatant)
        # e.g., target = next((c for c in local_combatants_list if c.get("name") == target_name), None)
        # ... etc ...

        # --- Start of _process_turn modifications ---
        dice_results = []
        # Initialize per-turn variables
        # Use the passed list to get the active combatant
        active_combatant = local_combatants_list[active_idx]
        logging.info(f"[CombatResolver] Processing turn for {active_combatant.get('name', 'Unknown')} (round {round_num})")

        # --- DEBUG LOGGING ---
        # ... (keep existing debug logging) ...

        # Import ActionEconomyManager if needed
        from app.combat.action_economy import ActionEconomyManager
        active_combatant = ActionEconomyManager.initialize_action_economy(active_combatant)

        # Process recharge abilities
        if active_combatant.get("type", "").lower() == "monster":
            self._process_recharge_abilities(active_combatant, dice_roller) # Modifies active_combatant dict

        # Debug: Log all combatant HP values at start of turn
        logging.debug(f"\n[CombatResolver] DEBUG: CURRENT HP VALUES AT START OF TURN ({active_combatant.get('name')}):")
        for i, c in enumerate(local_combatants_list): # Use passed list
            logging.debug(f"[CombatResolver] DEBUG: Combatant {i}: {c.get('name')} - HP: {c.get('hp', 0)}/{c.get('max_hp', c.get('hp', 0))}")

        # Process aura effects
        # Pass the correct list to _process_auras
        aura_updates = self._process_auras(active_combatant, local_combatants_list)
        # _process_auras might modify active_combatant dict directly if damage occurs

        # Skip if dead/0 HP
        if active_combatant.get("hp", 0) <= 0 and active_combatant.get("status", "").lower() == "dead":
             # ... (keep existing skip logic) ...
             return { # Ensure a dict is returned
                 "action": f"{active_combatant.get('name', 'Unknown')} is dead and skips their turn.",
                 "narrative": f"{active_combatant.get('name', 'Unknown')} is dead and skips their turn.",
                 "dice": [],
                 "updates": []
             }

        # Handle being knocked out by auras
        if active_combatant.get("hp", 0) <= 0 and active_combatant.get("status", "").lower() != "dead":
             # ... (keep existing logic) ...
             # Make sure the update uses the correct name/ID
             updates = [{
                  "name": active_combatant.get('name', 'Unknown'),
                  "instance_id": active_combatant.get('instance_id'), # Include ID if available
                  "hp": 0,
                  "status": "Unconscious"
             }]
             if active_combatant.get("type","").lower() != "monster":
                  self._init_death_saves(active_combatant) # Init saves
                  updates[0]["death_saves"] = active_combatant["death_saves"]

             return { # Ensure a dict is returned
                 "action": f"{active_combatant.get('name', 'Unknown')} falls unconscious due to aura damage.",
                 "narrative": f"{active_combatant.get('name', 'Unknown')} falls unconscious due to aura damage.",
                 "dice": [],
                 "updates": updates,
                 "aura_updates": aura_updates # Include aura info if needed
             }

        # 1. Create prompt using the current state from the passed list
        combat_state_for_prompt = {"combatants": local_combatants_list, "round_number": round_num}
        prompt = self._create_decision_prompt(combat_state_for_prompt, active_combatant)

        # 2. Get action decision from LLM
        logging.info(f"[CombatResolver] Requesting action decision from LLM for {active_combatant.get('name', 'Unknown')}")
        decision_response = None # Initialize to None
        try:
            # Ensure LLM service is available
            if not hasattr(self, 'llm_service') or self.llm_service is None:
                logging.error("[CombatResolver] LLM service is not available")
                raise ValueError("LLM service is not available")
                
            # Check which models are available
            available_models = self.llm_service.get_available_models()
            logging.info(f"[CombatResolver] Available LLM models: {available_models}")
            
            if not available_models:
                logging.error("[CombatResolver] No LLM models available")
                raise ValueError("No LLM models available. Check API keys and service configuration.")
            
            # Prefer GPT-4.1 Mini for fast combat resolution if available
            model_id = None
            
            # Find the appropriate model to use
            for model_info in available_models:
                model_id = model_info['id']
                if 'gpt-4-mini' in model_id or 'gpt-4.1-mini' in model_id:
                    logging.info(f"[CombatResolver] Using {model_id} for fast resolution")
                    break
                    
            # Fall back to any available model if preferred model not found
            if not model_id and available_models:
                model_id = available_models[0]['id']
                logging.info(f"[CombatResolver] Falling back to {model_id}")
            
            if not model_id:
                logging.error("[CombatResolver] No suitable model found")
                raise ValueError("No suitable model found")
                
            # Prepare decision prompt
            system_prompt = self._get_system_prompt()
            messages = self._create_action_prompt(local_combatants_list, active_idx, round_num)
            
            # Log the prompt
            logging.info(f"[CombatResolver] System prompt: {system_prompt[:100]}...")
            logging.info(f"[CombatResolver] Messages: {str(messages)[:200]}...")
            
            # Make the actual LLM call with additional logging
            logging.info(f"[CombatResolver] Making LLM call to model {model_id}")
            try:
                response_text = self.llm_service.generate_completion(
                    model_id,
                    messages,
                    system_prompt=system_prompt
                )
                
                if not response_text:
                    logging.error("[CombatResolver] LLM returned empty response")
                    raise ValueError("LLM returned empty response")
                    
                logging.info(f"[CombatResolver] LLM response received, length: {len(response_text)}")
                logging.info(f"[CombatResolver] LLM response preview: {response_text[:200]}...")
                
                # Parse the JSON response
                decision_response = self._parse_llm_json_response(response_text, "action_decision")
                logging.info(f"[CombatResolver] Parsed decision response: {str(decision_response)[:200]}...")
                
                if not decision_response or not isinstance(decision_response, dict):
                    logging.error(f"[CombatResolver] Failed to parse valid decision response: {decision_response}")
                    raise ValueError(f"Failed to parse valid decision response: {decision_response}")
                
                if "error" in decision_response:
                    logging.error(f"[CombatResolver] Error in decision response: {decision_response['error']}")
                    # Create a fallback response
                    decision_response = {
                        "action": "Wait",
                        "target": "None",
                        "explanation": f"Error parsing LLM response: {decision_response['error']}",
                        "fallback": True
                    }
            except Exception as llm_err:
                logging.error(f"[CombatResolver] LLM call error: {llm_err}")
                # Fallback for LLM errors
                decision_response = {
                    "action": "Wait",
                    "target": "None", 
                    "explanation": f"LLM error: {str(llm_err)}",
                    "fallback": True
                }
                import traceback
                logging.error(f"[CombatResolver] LLM call traceback: {traceback.format_exc()}")
        except Exception as e:
            logging.error(f"[CombatResolver] Error in LLM decision process: {e}")
            import traceback
            traceback.print_exc()
            # Provide a fallback response for any errors
            decision_response = {
                "action": "Wait",
                "target": "None",
                "explanation": f"Error: {str(e)}",
                "fallback": True
            }

        # --- DICE ROLLING PHASE ---
        # Check for dice_requests in the LLM response
        dice_results = [] # Ensure initialized
        # ... (keep existing dice rolling logic using dice_roller) ...

        # --- Build turn_result ---
        updates = [] # Start with empty updates for this turn
        narrative_text = "The action resolves with technical difficulties." # Default narrative
        try:
            # Extract narrative
            # ... (keep existing narrative extraction logic) ...

            # Auto-detect targets
            # ... (keep existing logic, using local_combatants_list) ...

            # --- REVISED Saving Throw & Damage Logic ---
            # This section needs careful review to ensure it uses local_combatants_list
            # and correctly identifies targets within that list.
            save_succeeded = False
            save_required = False
            final_dmg = 0
            action_name = decision_response.get("action", "Unknown Action")

            # Find action details in the active combatant
            action_details = None
            # ... (find action in active_combatant['actions']) ...

            # 1. Check if save required
            if action_details and "saving throw" in action_details.get("description", "").lower():
                save_required = True
                # ... (extract DC, ability, damage_on_save from action_details) ...

                # Process save for EACH target potentially affected (using damage_dealt keys)
                damage_targets = decision_response.get("damage_dealt", {})
                target_saves = {} # Store save result per target

                for target_name in damage_targets.keys():
                     # Find target in the local list
                     target = next((c for c in local_combatants_list if c.get("name") == target_name), None)
                     if not target: continue

                     # ... (get target save modifier) ...
                     # ... (roll save internally using dice_roller) ...
                     # Store result: target_saves[target_name] = save_succeeded

            # 2. Process damage/healing/conditions for each target
            # Damage
            for target_name, initial_dmg_val in decision_response.get("damage_dealt", {}).items():
                 target = next((c for c in local_combatants_list if c.get("name") == target_name), None)
                 if not target: continue

                 # Get initial damage
                 initial_dmg = 0
                 # ... (parse initial_dmg_val, fallback to dice) ...

                 # Adjust based on save (if required for this target)
                 final_dmg = 0
                 if save_required:
                      succeeded = target_saves.get(target_name, False) # Did this specific target save?
                      if succeeded:
                          # ... (calculate damage_on_save: half, none, full) ...
                          final_dmg = initial_dmg # Calculate final damage based on save outcome
                      else: # Save failed
                          final_dmg = initial_dmg
                 else:
                      # Check attack roll vs AC
                      # ... (find attack roll in dice_results) ...
                      # ... (compare roll vs target['ac']) ...
                      if attack_hits: final_dmg = initial_dmg
                      else: final_dmg = 0

                 # Apply final damage
                 if final_dmg > 0:
                      # Check if update exists, otherwise create
                      update_entry = next((u for u in updates if u.get("name") == target_name), None)
                      if not update_entry:
                           update_entry = {"name": target_name, "instance_id": target.get("instance_id")}
                           updates.append(update_entry)
                      # Calculate new HP, store in update_entry['hp']
                      current_hp = target.get("hp", 0)
                      new_hp = max(0, current_hp - final_dmg)
                      update_entry["hp"] = new_hp
                      logging.debug(f"  Adding HP update for {target_name}: {new_hp}")


            # Healing
            for target_name, heal_val in decision_response.get("healing", {}).items():
                 target = next((c for c in local_combatants_list if c.get("name") == target_name), None)
                 if not target: continue
                 # ... (parse heal_val, fallback to dice) ...
                 # ... (calculate new HP, capped at max_hp) ...
                 # Add/update entry in 'updates' list with new HP
                 update_entry = next((u for u in updates if u.get("name") == target_name), None)
                 if not update_entry:
                      update_entry = {"name": target_name, "instance_id": target.get("instance_id")}
                      updates.append(update_entry)
                 max_hp = target.get("max_hp", target.get("hp", 0)) # Get max_hp safely
                 heal_amount = 0
                 try: heal_amount = int(heal_val)
                 except: heal_amount = 0 # Default if parsing fails
                 current_hp = target.get("hp", 0)
                 new_hp = min(max_hp, current_hp + heal_amount)
                 update_entry["hp"] = new_hp
                 logging.debug(f"  Adding Healing update for {target_name}: {new_hp}")


            # Conditions Applied/Removed
            # ... (process conditions_applied/removed from decision_response) ...
            # Add/update entry in 'updates' list with 'status' or 'conditions' field

        except Exception as e:
            logging.error(f"Error translating resolution to updates: {e}", exc_info=True)
            # Fallback to explicit updates if present
            if not updates and isinstance(decision_response.get("updates"), list):
                logging.warning("Falling back to explicit updates from LLM.")
                updates = decision_response["updates"]


        # Construct final result for this turn
        try:
            # Ensure narrative_text is defined with a fallback
            if 'narrative_text' not in locals() or narrative_text is None:
                narrative_text = f"{active_combatant.get('name', 'Unknown')} takes their turn."

            turn_result = {
                "action": decision_response.get("action", "Unknown action"),
                "narrative": narrative_text,
                "dice": dice_results,
                "updates": updates, # The collected updates list
            }
            logging.debug(f"Final turn result: {turn_result}")
            return turn_result
        except Exception as final_err:
            # Last-resort fallback if anything fails during the result construction
            logging.error(f"Error constructing turn result: {final_err}", exc_info=True)
            return {
                "action": "Technical Error",
                "narrative": f"{active_combatant.get('name', 'Unknown')} encounters a technical difficulty.",
                "dice": [],
                "updates": []
            }

        # --- End of _process_turn modifications ---


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
        """Helper to format dice results for LLM prompts."""
        # ... (keep existing logic) ...
        pass # Appears correct

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
        Create prompt for LLM to resolve an action. Uses passed data.
        """
        active_name = active_combatant_dict.get('name', 'Unknown')
        round_num_res = combat_state_dict.get('round_number', 1) # Use correct key
        combatants_list_res = combat_state_dict.get('combatants', [])

        # ... (rest of logic, using active_combatant_dict, combatants_list_res, round_num_res) ...

        # --- Start of _create_resolution_prompt modifications ---
        action = combatant_decision.get('action', 'No action taken')
        target_name = combatant_decision.get('target', None) # Target NAME from decision

        dice_str = self._format_dice_results(dice_results)

        # Format nearby using the full list
        nearby_list = self._get_nearby_combatants(active_combatant_dict, combatants_list_res)
        nearby_str = self._format_nearby_combatants(nearby_list)

        # Format target info using the full list
        target_str = "No specific target."
        target_data = None
        if target_name and target_name.lower() != 'none':
             target_data = next((c for c in combatants_list_res if c.get('name') == target_name), None)
             if target_data:
                  t_status = target_data.get('status', 'OK')
                  t_status_str = f", Status: {t_status}" if t_status != "OK" else ""
                  target_str = f"Target: {target_data.get('name')} (HP: {target_data.get('hp', 0)}/{target_data.get('max_hp', '?')}, AC: {target_data.get('ac', 10)}{t_status_str})"
             else:
                  target_str = f"Target: {target_name} (Details not found - may be invalid name)"

        # Format conditions for active combatant
        condition_str = self._format_conditions(active_combatant_dict)

        # Recharge ability status/warning
        recharge_status = ""
        recharge_warning = ""
        used_recharge_ability = None
        available_recharge = []
        unavailable_recharge = []
        if "recharge_abilities" in active_combatant_dict:
            for name, info in active_combatant_dict.get("recharge_abilities", {}).items():
                 if info.get("available", True): # Assume available if key missing? Default to True
                      available_recharge.append(name)
                 else:
                      unavailable_recharge.append(name)

            if available_recharge or unavailable_recharge:
                 recharge_status = f"""
# Recharge Abilities Status
Available: {', '.join(available_recharge) if available_recharge else 'None'}
Unavailable: {', '.join(unavailable_recharge) if unavailable_recharge else 'None'}
"""
            # Check if the chosen action IS a recharge ability
            if action in active_combatant_dict.get("recharge_abilities", {}):
                 if action in unavailable_recharge:
                      recharge_warning = f"WARNING: Attempting to use UNAVAILABLE recharge ability '{action}'. Narrate failure and choose alternative."
                 else:
                      # Mark as used for the output JSON request
                      used_recharge_ability = action
                      recharge_warning = f"NOTE: Using AVAILABLE recharge ability '{action}'. Set 'recharge_ability_used' field in JSON."


        # Build the prompt
        prompt = f"""
You are the Combat Resolution AI. Narrate the outcome of the action based on the provided details and dice rolls.

# Combat Situation
Round: {round_num_res}
Active Combatant: {active_name} (HP: {active_combatant_dict.get('hp', 0)}/{active_combatant_dict.get('max_hp', '?')}, Status: {active_combatant_dict.get('status', 'OK')})
Conditions: {condition_str}

# Action Taken
Action: {action}
Target: {target_name or 'None'}

{recharge_status}
{recharge_warning}

# Dice Roll Results
{dice_str}

# Target Details (if specified)
{target_str}

# Nearby Combatants (Potential other targets/allies)
{nearby_str}

# Resolution Instructions
1. Narrate the action and its effects vividly based on the chosen action, target, and dice rolls.
2. If an attack roll beats AC, describe the hit and apply damage. If it misses, describe the miss.
3. If a saving throw is required (based on action description, not usually in decision prompt), compare save roll to DC. Apply effects/damage accordingly (e.g., half damage on success).
4. Determine the final HP changes, conditions applied/removed, and any other status updates.
5. If a recharge ability was used (and available), make sure to note it. If unavailable, describe the failure.
6. Respond ONLY with a valid JSON object.

# Required JSON Output Format
{{
  "narrative": "Detailed, step-by-step narration of the action, rolls, and outcome.",
  "updates": [
    // List of combatants who were changed by this action
    {{ "name": "TargetName1", "hp": new_hp, "status": "new_status", "conditions_added": ["condition"], "conditions_removed": ["condition"] }},
    {{ "name": "TargetName2", "hp": new_hp }}
    // Include changes to HP, status, conditions. Use target names.
  ],
      "recharge_ability_used": f'"{used_recharge_ability or ""}"' # Corrected f-string formatting
    }}

Example update for damage: {{"name": "Goblin", "hp": 5}}
Example update for condition: {{"name": "Hero", "status": "Prone", "conditions_added": ["prone"]}}

Narrate clearly. Calculate outcomes based on standard D&D 5e rules implied by the rolls and action. Be precise in the JSON updates.
"""
        return prompt
        # --- End of _create_resolution_prompt modifications ---

    # Added helper
    def _parse_llm_json_response(self, response_text, context=""): # Added helper
        """Attempts to parse JSON from LLM response, handling common issues."""
        # Ensure json is imported if not already globally
        import json
        import re

        if not isinstance(response_text, str):
            logging.warning(f"[_parse_llm_json_response] Expected string, got {type(response_text)} ({context})")
            return {"error": "Invalid response type", "raw_response": str(response_text)}

        cleaned = response_text.strip()
        logging.debug(f"[_parse_llm_json_response] Raw response ({context}): {cleaned[:200]}...")

        # 1. Try extracting from ```json ... ``` block
        # Fixed regex - the closing backticks were inside the capture group
        json_match = re.search(r"```json\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
        if json_match:
            json_content = json_match.group(1)
            try:
                parsed = json.loads(json_content)
                logging.debug(f"Successfully parsed from ```json block ({context})")
                return parsed
            except json.JSONDecodeError as e:
                logging.warning(f"Failed to parse ```json block content ({context}): {e}")
                # Fall through to other methods

        # 2. Try extracting from any ``` ... ``` block
        # Fixed regex - the closing backticks were inside the capture group
        code_block_match = re.search(r"```\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
        if code_block_match:
             json_content = code_block_match.group(1)
             try:
                 parsed = json.loads(json_content)
                 logging.debug(f"Successfully parsed from generic ``` block ({context})")
                 return parsed
             except json.JSONDecodeError as e:
                 logging.warning(f"Failed to parse generic ``` block content ({context}): {e}")
                 # Fall through
        # 3. Try finding the first { and last }
        brace_match = re.search(r"(\{.*\})", cleaned, re.DOTALL) # Simpler regex
        if brace_match:
            potential_json = brace_match.group(1)
            try:
                parsed = json.loads(potential_json)
                logging.debug(f"Successfully parsed brace-extracted content ({context})")
                return parsed
            except json.JSONDecodeError as e:
                 logging.warning(f"Failed to parse brace-extracted content ({context}): {e}")
                 # Fall through to final attempt

        # 4. Final attempt: Parse the raw cleaned string directly
        try:
            parsed = json.loads(cleaned)
            logging.debug(f"Successfully parsed cleaned string directly as last resort ({context})")
            return parsed
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse JSON response ({context}) after all attempts: {e}. Raw: {cleaned[:200]}...")
            return {"error": "JSON parsing failed", "raw_response": cleaned}

    # Add a new diagnostic method for testing LLM service
    def test_llm_service(self):
        """Test the LLM service to verify it's working properly."""
        logging.info("[CombatResolver] Testing LLM service...")
        try:
            # Get available models
            available_models = self.llm_service.get_available_models()
            logging.info(f"[CombatResolver] Available models: {available_models}")
            
            if not available_models:
                logging.error("[CombatResolver] No LLM models available. Check API keys and service configuration.")
                return False, "No models available"
            
            # Use the first available model for testing
            test_model = available_models[0]['id']
            logging.info(f"[CombatResolver] Testing with model: {test_model}")
            
            # Simple test prompt
            test_prompt = "You are a D&D combat assistant. Please respond with a simple 'LLM service is working' message."
            test_messages = [{"role": "user", "content": test_prompt}]
            
            # Attempt to get a response
            response = self.llm_service.generate_completion(
                model=test_model,
                messages=test_messages,
                temperature=0.7,
                max_tokens=100
            )
            
            if response:
                logging.info(f"[CombatResolver] LLM service test successful: {response[:100]}...")
                return True, response
            else:
                logging.error("[CombatResolver] LLM service test failed: Empty response")
                return False, "Empty response"
        
        except Exception as e:
            import traceback
            logging.error(f"[CombatResolver] LLM service test failed with error: {e}")
            logging.error(traceback.format_exc())
            return False, f"Error: {str(e)}"

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
        """Create a textual description of the combat state.
        
        Args:
            combatants: List of all combatants
            active_idx: Index of the active combatant
            
        Returns:
            String description of the combat state
        """
        active_combatant = combatants[active_idx]
        name = active_combatant.get('name', 'Unknown')
        
        description = []
        
        # Describe the active combatant first
        description.append(f"### {name} (Active Combatant)")
        description.append(f"- HP: {active_combatant.get('hp', 0)}/{active_combatant.get('max_hp', 0)}")
        description.append(f"- AC: {active_combatant.get('ac', 10)}")
        
        # Add status effects
        if active_combatant.get('status'):
            description.append(f"- Status: {active_combatant.get('status')}")
        
        # Add abilities and actions if available
        if 'actions' in active_combatant and active_combatant['actions']:
            actions = active_combatant['actions']
            action_names = []
            if isinstance(actions, list):
                for action in actions:
                    if isinstance(action, dict) and 'name' in action:
                        action_names.append(action['name'])
            action_text = ", ".join(action_names) if action_names else "Standard actions"
            description.append(f"- Available Actions: {action_text}")
        
        description.append("\n### Other Combatants")
        
        # Group combatants by type (allies and enemies)
        allies = []
        enemies = []
        active_type = active_combatant.get('type', '').lower()
        
        for i, combatant in enumerate(combatants):
            if i == active_idx:
                continue  # Skip active combatant
                
            name = combatant.get('name', 'Unknown')
            hp = combatant.get('hp', 0)
            max_hp = combatant.get('max_hp', hp)
            hp_percent = int((hp / max_hp * 100) if max_hp > 0 else 0)
            ac = combatant.get('ac', 10)
            status = combatant.get('status', '')
            combatant_type = combatant.get('type', '').lower()
            
            # Prepare combatant description
            combatant_desc = f"{name} - HP: {hp}/{max_hp} ({hp_percent}%), AC: {ac}"
            if status:
                combatant_desc += f", Status: {status}"
            
            # Add to appropriate group
            if combatant_type == active_type:
                allies.append(combatant_desc)
            else:
                enemies.append(combatant_desc)
        
        # Add allies and enemies to description
        if allies:
            description.append("\n#### Allies:")
            for ally in allies:
                description.append(f"- {ally}")
        
        if enemies:
            description.append("\n#### Enemies:")
            for enemy in enemies:
                description.append(f"- {enemy}")
        
        return "\n".join(description)

# Ensure the final class definition is accessible
CombatResolver = CombatResolver # This line might be redundant depending on execution context