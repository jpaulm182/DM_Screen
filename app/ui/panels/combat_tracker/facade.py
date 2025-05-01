from app.ui.panels.base_panel import BasePanel
from app.ui.panels.combat_tracker.ui import _setup_ui
from app.ui.panels.combat_tracker.combatant_manager import CombatantManager
from app.ui.panels.combat_utils import roll_dice
from PySide6.QtCore import Qt, QEvent, QTimer, QMetaObject, Q_ARG, Slot
from PySide6.QtWidgets import QMessageBox, QApplication, QPushButton, QTableWidgetItem, QMenu, QInputDialog
from PySide6.QtGui import QAction

# Added imports for _fast_resolve_combat
import traceback
import threading
import gc

class CombatTrackerPanel(BasePanel):
    """Combat Tracker panel built with modular UI functions."""

    def __init__(self, app_state):
        # Initialize UI state required by ui.setup (round counter)
        self.current_round = 1
        super().__init__(app_state, "Combat Tracker")
        # Provide dice-rolling utility to combat manager
        self.roll_dice = roll_dice
        # Initialize combatant manager for MonsterPanel signals
        self.combatant_manager = CombatantManager(self)
        # Flag to prevent multiple simultaneous combat resolutions
        self._is_resolving_combat = False

    def _setup_ui(self):
        # Stub callback methods to satisfy UI signal connections
        self._initiative_changed = lambda row, col: None
        self._hp_changed = lambda row, col: None
        self._handle_cell_changed = lambda row, col: None
        self._show_context_menu = lambda pos: None
        self._on_selection_changed = lambda: None
        self._round_changed = lambda value: None
        self._toggle_timer = lambda: None
        self._next_turn = lambda: None
        self._reset_combat = lambda: None
        self._restart_combat = lambda: None
        self._handle_add_click = lambda: None
        self._update_highlight = lambda: None
        # Stub roll initiative handler for UI button
        self._roll_initiative = lambda: None
        # Append combat log entries to the text widget
        self._log_combat_action = lambda category, actor, action, target=None, result=None, round=None, turn=None: self.combat_log_text.append(f"[{category}] {actor} {action}{(' ' + str(target)) if target else ''}{(' ' + str(result)) if result else ''}")
        # Clear combat log
        self._clear_combat_log = lambda: self.combat_log_text.clear()
        # Stub sort handler so manager can sort initiative table
        self._sort_initiative = lambda: self.initiative_table.sortItems(1, Qt.DescendingOrder)
        # Build UI layout and widgets
        _setup_ui(self)
        
    # Custom event classes for safe thread communication (moved here from chunk)
    class _ProgressEvent(QEvent):
        def __init__(self, message):
            super().__init__(QEvent.Type(QEvent.User + 100))
            self.message = message
    
    class _ErrorEvent(QEvent):
        def __init__(self, title, message):
            super().__init__(QEvent.Type(QEvent.User + 101))
            self.title = title
            self.message = message
    
    class _ClearLogEvent(QEvent):
        def __init__(self):
            super().__init__(QEvent.Type(QEvent.User + 102))
    
    class _AddInitialStateEvent(QEvent):
        def __init__(self, combat_state):
            super().__init__(QEvent.Type(QEvent.User + 103))
            self.combat_state = combat_state
    
    class _LogDiceEvent(QEvent):
        def __init__(self, expr, result):
            super().__init__(QEvent.Type(QEvent.User + 104))
            self.expr = expr
            self.result = result
    
    class _ProcessResultEvent(QEvent):
        def __init__(self, result, error):
            super().__init__(QEvent.Type(QEvent.User + 105))
            self.result = result
            self.error = error
    
    class _UpdateUIEvent(QEvent):
        def __init__(self, turn_state):
            super().__init__(QEvent.Type(QEvent.User + 106))
            self.turn_state = turn_state
    
    class _SetResolvingEvent(QEvent):
        def __init__(self, is_resolving):
            super().__init__(QEvent.Type(QEvent.User + 107))
            self.is_resolving = is_resolving
    
    class _ConnectSignalEvent(QEvent):
        def __init__(self):
            super().__init__(QEvent.Type(QEvent.User + 108))
    
    class _UpdateButtonEvent(QEvent):
        def __init__(self, text, enabled=True):
            super().__init__(QEvent.Type(QEvent.User + 109))
            self.text = text
            self.enabled = enabled
            
    # ------------------------------------------------------------------
    # START: _fast_resolve_combat method implementation from chunk1.py
    # ------------------------------------------------------------------
    def _fast_resolve_combat(self):
        """Use LLM to resolve the current combat encounter (turn-by-turn, rule-correct)."""
        # Prevent multiple clicks while processing
        if self._is_resolving_combat:
            print("[CombatTracker] Already resolving combat, ignoring click.")
            return
        self._is_resolving_combat = True

        # First, update UI to indicate processing is happening
        self.fast_resolve_button.setEnabled(False)
        self.fast_resolve_button.setText("Initializing...")
        QApplication.processEvents()  # Force immediate UI update
        
        # Add a safety timer that will reset the button after 5 minutes regardless
        # of whether the combat resolver signals completion
        safety_timer = QTimer(self)
        safety_timer.setSingleShot(True)
        safety_timer.timeout.connect(lambda: self._reset_resolve_button("Fast Resolve", True))
        safety_timer.start(300000)  # 5 minutes in milliseconds
        
        # Add a second backup timer with shorter timeout (2 minutes)
        backup_timer = QTimer(self)
        backup_timer.setSingleShot(True)
        backup_timer.timeout.connect(lambda: self._check_and_reset_button())
        backup_timer.start(120000)  # 2 minutes in milliseconds
        
        # Store timers for cancellation
        self._safety_timer = safety_timer
        self._backup_timer = backup_timer
        
        # Force garbage collection before starting
        gc.collect()
        
        # Define the main processing function to run in a separate thread
        def setup_and_start_combat():
            try:
                # Step 1: Validate we have combatants
                has_monster = has_player = False
                for row in range(self.initiative_table.rowCount()):
                    type_item = self.initiative_table.item(row, 7)  # Type is now column 7
                    if type_item:
                        combatant_type = type_item.text().lower()
                        if combatant_type == "monster":
                            has_monster = True
                        elif combatant_type in ["character", "pc", "npc"]:
                            has_player = True
                
                # Update progress on UI thread
                QApplication.instance().postEvent(self, CombatTrackerPanel._ProgressEvent("Validating combatants..."))
                
                # Handle validation errors
                if not has_monster and not has_player:
                    QApplication.instance().postEvent(self, CombatTrackerPanel._ErrorEvent(
                        "Cannot Start Combat", 
                        "You need at least one combatant (monster or character) to run combat."
                    ))
                    self._is_resolving_combat = False # Reset flag
                    return
                    
                elif not has_monster and has_player:
                    QApplication.instance().postEvent(self, CombatTrackerPanel._ErrorEvent(
                        "Cannot Start Combat", 
                        "You need at least one monster to run combat against player characters.\n\n" +
                        "Add monsters from the Monster Panel."
                    ))
                    self._is_resolving_combat = False # Reset flag
                    return
                
                # Step 2: Gather combat state
                QApplication.instance().postEvent(self, CombatTrackerPanel._ProgressEvent("Gathering combat data..."))
                combat_state = self._gather_combat_state()
                if not combat_state or not combat_state.get("combatants"):
                    QApplication.instance().postEvent(self, CombatTrackerPanel._ErrorEvent(
                        "Fast Resolve", 
                        "No combatants in the tracker to resolve."
                    ))
                    self._is_resolving_combat = False # Reset flag
                    return
                
                # Step 3: Clear and prepare the combat log
                QApplication.instance().postEvent(self, CombatTrackerPanel._ProgressEvent("Preparing combat log..."))
                QApplication.instance().postEvent(self, CombatTrackerPanel._ClearLogEvent())
                
                # Step 4: Add initial combat state to log (this will be done on the UI thread)
                QApplication.instance().postEvent(self, CombatTrackerPanel._AddInitialStateEvent(combat_state))
                
                # Step 5: Setup the dice roller function that will be passed to the resolver
                def dice_roller(expr):
                    """Parse and roll a dice expression like '1d20+5'. Returns the integer result."""
                    try:
                        import re, random
                        match = re.match(r"(\d*)d(\d+)([+-]\d+)?", expr.replace(' ', ''))
                        if not match:
                            return 0
                        num, die, mod = match.groups()
                        num = int(num) if num else 1
                        die = int(die)
                        mod = int(mod) if mod else 0
                        total = sum(random.randint(1, die) for _ in range(num)) + mod
                        
                        # Log the roll to the combat log via a custom event
                        QApplication.instance().postEvent(self, CombatTrackerPanel._LogDiceEvent(expr, total))
                        return total
                    except Exception as e:
                        print(f"[CombatTracker] Error in dice roller: {e}")
                        return 10  # Provide a reasonable default
                
                # Step 6: Setup completion callback (backup for signals)
                def completion_callback(result, error):
                    """Callback for resolution completion if signals aren't working"""
                    print(f"[CombatTracker] Manual completion callback called with result={bool(result)}, error={bool(error)}")
                    
                    # Forward to our UI handler via a custom event - safest approach
                    # This will be handled by the signal connection primarily
                    QApplication.instance().postEvent(self, CombatTrackerPanel._ProcessResultEvent(result, error))
                    
                    # Update button state via event as backup
                    QApplication.instance().postEvent(self, CombatTrackerPanel._UpdateButtonEvent("Fast Resolve", True))
                    self._is_resolving_combat = False # Reset flag
                    print("[CombatTracker] Posted button update event (from callback)")
                    
                    # Create a very short timer as a last resort reset check
                    reset_timer = QTimer()
                    reset_timer.setSingleShot(True)
                    reset_timer.timeout.connect(lambda: self._check_and_reset_button())
                    reset_timer.start(1000)  # 1 second delay
                
                # Step 7: Setup turn callback (backup for signals)
                def manual_turn_callback(turn_state):
                    """Callback for per-turn updates if signals aren't working"""
                    print(f"[CombatTracker] Manual turn update callback received data with "
                          f"{len(turn_state.get('combatants', []))} combatants")
                    # Forward to our wrapper method via a custom event
                    # This will be handled by the _update_ui_wrapper primarily
                    QApplication.instance().postEvent(self, CombatTrackerPanel._UpdateUIEvent(turn_state))
                
                # Step 8: Start the actual combat resolution
                # Post event to set the resolving flag (ensures it happens on UI thread)
                QApplication.instance().postEvent(self, CombatTrackerPanel._SetResolvingEvent(True))
                
                # Post event to setup signal connection (done on UI thread)
                QApplication.instance().postEvent(self, CombatTrackerPanel._ConnectSignalEvent())
                
                # Update UI to show we're now resolving
                QApplication.instance().postEvent(self, CombatTrackerPanel._UpdateButtonEvent("Resolving...", False))
                
                # Step 9: Call the resolver with our setup
                # Ensure we are using the app_state's combat_resolver
                if not hasattr(self.app_state, 'combat_resolver'):
                     QApplication.instance().postEvent(self, CombatTrackerPanel._ErrorEvent(
                        "Error", 
                        f"Combat Resolver not found in App State."
                    ))
                     self._is_resolving_combat = False # Reset flag
                     return
                     
                resolver_callable = self.app_state.combat_resolver.resolve_combat_turn_by_turn
                
                # --- Check if resolver supports turn_update_callback --- 
                # This check is less reliable, rely on the resolver's own handling
                # accepts_turn_callback = 'turn_update_callback' in resolver_callable.__code__.co_varnames

                # Update UI with final preparation status
                QApplication.instance().postEvent(self, CombatTrackerPanel._ProgressEvent("Starting combat resolution..."))
                
                # Call the resolver (ImprovedCombatResolver handles its own signals/updates)
                # Pass the UI update wrapper as the `update_ui_callback`
                print("[CombatTracker] Calling ImprovedCombatResolver.resolve_combat_turn_by_turn")
                self.app_state.combat_resolver.resolve_combat_turn_by_turn(
                    combat_state,
                    dice_roller,
                    completion_callback, # Pass our manual callback for backup
                    self._update_ui_wrapper # Pass the wrapper for UI updates
                )
                    
            except Exception as e:
                traceback.print_exc()
                # If any error occurs, send an error event
                QApplication.instance().postEvent(self, CombatTrackerPanel._ErrorEvent(
                    "Error", 
                    f"Failed to start combat resolution: {str(e)}"
                ))
                # Reset the resolving flag on error
                QApplication.instance().postEvent(self, CombatTrackerPanel._SetResolvingEvent(False))
                QApplication.instance().postEvent(self, CombatTrackerPanel._UpdateButtonEvent("Fast Resolve", True))

        # Start the setup in a background thread
        setup_thread = threading.Thread(target=setup_and_start_combat)
        setup_thread.daemon = True  # Allow app to exit even if thread is running
        setup_thread.start()
    # ----------------------------------------------------------------
    # END: _fast_resolve_combat method implementation
    # ----------------------------------------------------------------
    
    # Override event handler to process our custom events
    def event(self, event):
        """Handle custom events posted to our panel"""
        # Need access to QEvent for type checking
        from PySide6.QtCore import QEvent

        if event.type() == QEvent.Type(QEvent.User + 1):
            # This is our UpdateUIEvent for JSON (passed from _update_ui_wrapper)
            try:
                # The event carries the JSON string, call _update_ui with it
                self._update_ui(event.json_data) 
                return True
            except Exception as e:
                print(f"[CombatTracker] Error in event handler UI update: {e}")
                return False
        elif event.type() == QEvent.Type(QEvent.User + 100):
            # Progress event
            self.fast_resolve_button.setText(event.message)
            QApplication.processEvents()
            return True
        elif event.type() == QEvent.Type(QEvent.User + 101):
            # Error event
            self._reset_resolve_button("Fast Resolve", True)
            self._is_resolving_combat = False # Ensure flag is reset
            QMessageBox.critical(self, event.title, event.message)
            return True
        elif event.type() == QEvent.Type(QEvent.User + 102):
            # Clear log event
            self._clear_combat_log()
            return True
        elif event.type() == QEvent.Type(QEvent.User + 103):
            # Add initial state event
            self._add_initial_combat_state_to_log(event.combat_state)
            return True
        elif event.type() == QEvent.Type(QEvent.User + 104):
            # Log dice event
            self._log_combat_action(
                "Dice", 
                "AI", 
                f"rolled {event.expr}", 
                result=f"Result: {event.result}"
            )
            return True
        elif event.type() == QEvent.Type(QEvent.User + 105):
            # Process result event (backup if signal fails)
            self._process_resolution_ui(event.result, event.error)
            return True
        elif event.type() == QEvent.Type(QEvent.User + 106):
            # Update UI event (backup if invokeMethod fails)
            self._update_ui_wrapper(event.turn_state)
            return True
        elif event.type() == QEvent.Type(QEvent.User + 107):
            # Set resolving event
            self._is_resolving_combat = event.is_resolving
            print(f"[CombatTracker] Setting _is_resolving_combat = {event.is_resolving} (via event)")
            return True
        elif event.type() == QEvent.Type(QEvent.User + 108):
            # Connect signal event
            try:
                # Disconnect any existing connection first to be safe
                try:
                    self.app_state.combat_resolver.resolution_complete.disconnect(self._process_resolution_ui)
                    print("[CombatTracker] Disconnected existing signal connection")
                except Exception:
                    # Connection might not exist yet, which is fine
                    pass
                
                # Connect the signal
                self.app_state.combat_resolver.resolution_complete.connect(self._process_resolution_ui)
                print("[CombatTracker] Successfully connected resolution_complete signal")
            except Exception as conn_error:
                print(f"[CombatTracker] Failed to connect signal: {conn_error}")
            return True
        elif event.type() == QEvent.Type(QEvent.User + 109):
            # Update button event
            self._reset_resolve_button(event.text, event.enabled)
            return True
            
        return super().event(event)

    # Need the _update_ui_wrapper, _update_ui, _process_resolution_ui, 
    # _reset_resolve_button, _check_and_reset_button, 
    # _gather_combat_state, _add_initial_combat_state_to_log methods defined 
    # within this class or imported/inherited for _fast_resolve_combat to work.
    # Assuming they exist elsewhere (like in other chunks or base classes)

    # ------------------------------------------------------------------
    # START: Added methods from chunks
    # ------------------------------------------------------------------

    # From chunk4.py
    def _reset_resolve_button(self, text="Fast Resolve", enabled=True):
        """Guaranteed method to reset the button state using the main UI thread"""
        # Direct update on the UI thread
        # Check if fast_resolve_button exists before accessing it
        if hasattr(self, 'fast_resolve_button') and self.fast_resolve_button:
            self.fast_resolve_button.setEnabled(enabled)
            self.fast_resolve_button.setText(text)
        else:
            print("[CombatTracker] Warning: fast_resolve_button not found in _reset_resolve_button")
            return # Exit if button doesn't exist
        
        # Force immediate UI update
        # Need to import QApplication if not already done
        # from PySide6.QtWidgets import QApplication
        QApplication.processEvents()
        
        print(f"[CombatTracker] Reset Fast Resolve button to '{text}' (enabled: {enabled})")

    # From chunk4.py (needed by _fast_resolve_combat)
    def _check_and_reset_button(self):
        """Check if the button should be reset and reset it if necessary"""
        # Check if fast_resolve_button exists before accessing it
        if not hasattr(self, 'fast_resolve_button') or not self.fast_resolve_button:
             print("[CombatTracker] Warning: fast_resolve_button not found in _check_and_reset_button")
             return # Exit if button doesn't exist
             
        # Check if the button text is still in "Initializing..." state after our timer
        if self.fast_resolve_button.text() == "Initializing..." or self.fast_resolve_button.text().startswith("Resolving"):
            print("[CombatTracker] Backup timer detected hanging button, forcing reset")
            self._reset_resolve_button("Fast Resolve", True)
            
            # Also log this to the combat log for user awareness
            # Check if combat_log_text exists before appending
            if hasattr(self, 'combat_log_text') and self.combat_log_text:
                 self.combat_log_text.append("<p style='color:orange;'><b>Notice:</b> Combat resolution timed out or is taking too long. The Fast Resolve button has been reset.</p>")
            
            # Maybe the combat resolver is still running - force all needed flag resets too
            self._is_resolving_combat = False

    # From chunk2.py
    def _gather_combat_state(self):
        """Gather the current state of the combat from the table."""
        combatants = []
        
        print(f"\n[CombatTracker] DEBUG: Gathering combat state with current HP values from table:")
        
        # Ensure initiative table exists
        if not hasattr(self, 'initiative_table'):
            print("[CombatTracker] Error: Initiative table not found in _gather_combat_state")
            return {"round": self.current_round, "current_turn_index": self.current_turn, "combatants": []}

        for row in range(self.initiative_table.rowCount()):
            # Basic combatant data
            name_item = self.initiative_table.item(row, 0)
            initiative_item = self.initiative_table.item(row, 1)
            hp_item = self.initiative_table.item(row, 2)
            max_hp_item = self.initiative_table.item(row, 3)
            ac_item = self.initiative_table.item(row, 4)
            status_item = self.initiative_table.item(row, 5)
            conc_item = self.initiative_table.item(row, 6)
            type_item = self.initiative_table.item(row, 7)
            
            # Get values or defaults
            name = name_item.text() if name_item else "Unknown"
            initiative = int(initiative_item.text() or "0") if initiative_item else 0
            hp = int(hp_item.text() or "0") if hp_item else 0
            # Get max_hp from specific max_hp column
            max_hp = int(max_hp_item.text() or str(hp)) if max_hp_item else hp
            ac = int(ac_item.text() or "10") if ac_item else 10
            status = status_item.text() if status_item else ""
            concentration = conc_item.checkState() == Qt.Checked if conc_item else False
            combatant_type = type_item.text() if type_item else "unknown"
            
            # Get monster ID from name item if it's a monster
            # --- RENAME monster_id to instance_id for clarity and consistency --- 
            instance_id = None
            if name_item:
                # Get instance_id regardless of type (both monsters and characters need consistent IDs)
                instance_id = name_item.data(Qt.UserRole + 2)
                
                if not instance_id:
                    # Generate a unique ID if none exists
                    import time
                    import hashlib
                    timestamp = int(time.time())
                    hash_base = f"{name}_{timestamp}_{row}"
                    instance_id = hashlib.md5(hash_base.encode()).hexdigest()[:8]
                    # Store the ID back on the item for future reference
                    name_item.setData(Qt.UserRole + 2, instance_id)
                    print(f"[CombatTracker] Generated new instance ID {instance_id} for {name}")
                else:
                    print(f"[CombatTracker] Using existing instance ID {instance_id} for {name}")
            
            # Debug print current HP values
            print(f"[CombatTracker] DEBUG: Table row {row}: {name} - HP: {hp}/{max_hp} {' (ID: ' + str(instance_id) + ')' if instance_id else ''}")
            
            # Create combatant dictionary
            combatant = {
                "name": name,
                "initiative": initiative,
                "hp": hp,
                "max_hp": max_hp,
                "ac": ac,
                "status": status,
                "concentration": concentration,
                "type": combatant_type,
                "instance_id": instance_id if instance_id else f"combatant_{row}"  # Ensure every combatant has a unique ID
            }
            
            # Add more detailed information if available in the self.combatant_manager.combatants_by_id dictionary
            # --- Use instance_id for lookup, not row index --- 
            stored_combatant = None
            # Ensure combatant_manager and combatants_by_id exist
            if hasattr(self, 'combatant_manager') and hasattr(self.combatant_manager, 'combatants_by_id'):
                if instance_id and instance_id in self.combatant_manager.combatants_by_id: # USE CONSISTENT instance_id
                     stored_combatant = self.combatant_manager.combatants_by_id[instance_id] # USE CONSISTENT instance_id
                     print(f"Found stored data for instance ID {instance_id}")
            else:
                print("[CombatTracker] Warning: combatant_manager or combatants_by_id not found.")

            if stored_combatant:
                # First, ensure the stored combatant has the same instance ID (sync it)
                if isinstance(stored_combatant, dict) and "instance_id" in combatant:
                    # Update the stored combatant's instance_id to match what's in the table
                    stored_combatant["instance_id"] = combatant["instance_id"]
                    
                # Add abilities if available
                if isinstance(stored_combatant, dict):
                    # Only include keys that are useful for combat resolution
                    for key in [
                        "abilities", "skills", "equipment", "features", "spells",
                        "special_traits", "traits", "actions", "legendary_actions",
                        "reactions", "on_death", "on_death_effects", "recharge_abilities",
                        "ability_recharges", "limited_use"
                    ]:
                        if key in stored_combatant:
                            # Tag each ability with the monster instance ID to prevent mixing
                            if key in ["actions", "traits", "legendary_actions", "reactions"]:
                                # These are typically lists of dictionaries
                                tagged_abilities = []
                                original_abilities = stored_combatant[key]
                                
                                if isinstance(original_abilities, list):
                                    for ability in original_abilities:
                                        if isinstance(ability, dict):
                                            # Create a copy to avoid modifying the original
                                            ability_copy = ability.copy()
                                            # Add instance ID to the ability
                                            ability_copy["monster_instance_id"] = combatant["instance_id"]
                                            ability_copy["monster_name"] = name
                                            
                                            # Check for monster_source tag
                                            if "monster_source" not in ability_copy:
                                                ability_copy["monster_source"] = name
                                                
                                            tagged_abilities.append(ability_copy)
                                        else:
                                            # Non-dict abilities are simply passed through
                                            tagged_abilities.append(ability)
                                    
                                    # Store the tagged abilities
                                    combatant[key] = tagged_abilities
                                else:
                                    # If not a list, just store as is
                                    combatant[key] = original_abilities
                            elif key == "abilities":
                                # Handle abilities which are typically a dictionary of abilities
                                if isinstance(stored_combatant[key], dict):
                                    tagged_abilities = {}
                                    for ability_name, ability in stored_combatant[key].items():
                                        if isinstance(ability, dict):
                                            # Create a copy to avoid modifying the original
                                            ability_copy = ability.copy()
                                            # Add instance ID to the ability
                                            ability_copy["monster_instance_id"] = combatant["instance_id"]
                                            ability_copy["monster_name"] = name
                                            
                                            # Check for monster_source tag
                                            if "monster_source" not in ability_copy:
                                                ability_copy["monster_source"] = name
                                                
                                            tagged_abilities[ability_name] = ability_copy
                                        else:
                                            # Non-dict abilities are simply passed through
                                            tagged_abilities[ability_name] = ability
                                    
                                    # Store the tagged abilities
                                    combatant[key] = tagged_abilities
                                else:
                                    # If not a dict, just store as is
                                    combatant[key] = stored_combatant[key]
                            else:
                                # For other attributes, copy as is
                                combatant[key] = stored_combatant[key]
                    
                    # If monster and no existing limited_use, create basic recharge placeholders
                    if combatant_type == "monster" and "limited_use" not in combatant:
                        limited_use = {}

                        # Dragons breath weapon
                        if "dragon" in name.lower():
                            limited_use["Breath Weapon"] = "Available (Recharges on 5-6)"

                        if limited_use:
                            combatant["limited_use"] = limited_use
                
                # If it's an object, try to extract useful attributes
                elif hasattr(stored_combatant, "__dict__"):
                    for attr in [
                        "abilities", "skills", "equipment", "features", "spells",
                        "special_traits", "traits", "actions", "legendary_actions",
                        "reactions", "on_death", "on_death_effects", "recharge_abilities",
                        "ability_recharges", "limited_use"
                    ]:
                        if hasattr(stored_combatant, attr):
                            attr_value = getattr(stored_combatant, attr)
                            
                            # Tag abilities with monster instance ID
                            if attr in ["actions", "traits", "legendary_actions", "reactions"]:
                                # These are typically lists of objects
                                if isinstance(attr_value, list):
                                    tagged_abilities = []
                                    
                                    for ability in attr_value:
                                        if isinstance(ability, dict):
                                            # Create a copy to avoid modifying the original
                                            ability_copy = ability.copy()
                                            # Add instance ID to the ability
                                            ability_copy["monster_instance_id"] = combatant["instance_id"]
                                            ability_copy["monster_name"] = name
                                            
                                            # Check for monster_source tag
                                            if "monster_source" not in ability_copy:
                                                ability_copy["monster_source"] = name
                                                
                                            tagged_abilities.append(ability_copy)
                                        else:
                                            # Create a dictionary from the object's attributes
                                            ability_dict = {}
                                            for ability_attr in dir(ability):
                                                if not ability_attr.startswith("_") and not callable(getattr(ability, ability_attr)):
                                                    ability_dict[ability_attr] = getattr(ability, ability_attr)
                                            
                                            # Add monster identifier
                                            ability_dict["monster_instance_id"] = combatant["instance_id"]
                                            ability_dict["monster_name"] = name
                                            ability_dict["monster_source"] = name
                                            
                                            tagged_abilities.append(ability_dict)
                                    
                                    # Store the tagged abilities
                                    combatant[attr] = tagged_abilities
                                else:
                                    # If not a list, just store as is
                                    combatant[attr] = attr_value
                            else:
                                # For other attributes, copy as is
                                combatant[attr] = attr_value
            
            combatants.append(combatant)
            
        # Validate ability mixing (ensure this method exists)
        if hasattr(self, '_validate_no_ability_mixing'):
            self._validate_no_ability_mixing(combatants)
        else:
            print("[CombatTracker] Warning: _validate_no_ability_mixing method not found.")
            
        # Ensure current_turn is a valid attribute
        current_turn_index = getattr(self, 'current_turn', 0)
        if not isinstance(current_turn_index, int):
             current_turn_index = 0 # Default if invalid
             
        return {
            "round": self.current_round,
            "current_turn_index": current_turn_index,
            "combatants": combatants
        }

    # From chunk2.py (needed by _gather_combat_state)
    def _validate_no_ability_mixing(self, combatants):
        """
        Validate that no abilities are mixed between different monster instances.
        This is an additional safety check after the main preparation.
        """
        ability_sources = {}  # Maps ability names to their source monsters
        
        for combatant in combatants:
            combatant_id = combatant.get("instance_id", "unknown")
            combatant_name = combatant.get("name", "Unknown")
            
            # Check each ability-containing attribute
            for ability_type in ["actions", "traits", "legendary_actions", "reactions"]:
                abilities = combatant.get(ability_type, [])
                if not isinstance(abilities, list):
                    continue
                
                for i, ability in enumerate(abilities):
                    if not isinstance(ability, dict):
                        continue
                        
                    ability_name = ability.get("name", f"Unknown_{i}")
                    
                    # Make sure all abilities have the instance ID and source name
                    if "monster_instance_id" not in ability:
                        print(f"[CombatTracker] WARNING: Adding missing instance ID to {ability_name} for {combatant_name}")
                        ability["monster_instance_id"] = combatant_id
                        
                    if "monster_name" not in ability:
                        print(f"[CombatTracker] WARNING: Adding missing monster name to {ability_name} for {combatant_name}")
                        ability["monster_name"] = combatant_name
                        
                    if "monster_source" not in ability:
                        ability["monster_source"] = combatant_name
                    
                    # Track the ability source
                    source_key = f"{ability_name.lower()}"
                    if source_key in ability_sources:
                        # If the ability exists, make sure it comes from the right monster instance
                        previous_source = ability_sources[source_key]
                        if previous_source != combatant_id:
                            # This is a potential mixing situation - check if names match to confirm
                            prev_name = ability.get("monster_name", "Unknown")
                            if prev_name != combatant_name:
                                print(f"[CombatTracker] WARNING: Ability {ability_name} may be mixed between {prev_name} and {combatant_name}")
                                # Ensure this ability is clearly marked with its source for the resolver
                                ability["name"] = f"{combatant_name} {ability_name}"
                    else:
                        # Register this ability with its source
                        ability_sources[source_key] = combatant_id
                        
    # From chunk4.py (needed by event handler and signal callback)
    @Slot(object, object)
    def _process_resolution_ui(self, result, error):
        """Process the combat resolution result from the resolver"""
        # Import needed modules at the start
        import copy
        import gc
        import traceback
        # Need QApplication, QTextCursor, QScrollBar
        from PySide6.QtWidgets import QApplication
        from PySide6.QtGui import QTextCursor
        
        print("[CombatTracker] _process_resolution_ui called - processing combat results")
        
        try:
            # Cancel safety timers if they exist
            if hasattr(self, '_safety_timer') and self._safety_timer:
                self._safety_timer.stop()
                print("[CombatTracker] Canceled safety timer")
                
            if hasattr(self, '_backup_timer') and self._backup_timer:
                self._backup_timer.stop()
                print("[CombatTracker] Canceled backup timer")
            
            # Reset UI elements first
            self._reset_resolve_button("Fast Resolve", True)
            
            # Ensure the _is_resolving_combat flag is reset
            self._is_resolving_combat = False
            print("[CombatTracker] Setting _is_resolving_combat = False")
            
            # Force UI update immediately
            QApplication.processEvents()
            
            # Disconnect signal to prevent memory leaks
            try:
                # Check if combat_resolver exists before disconnecting
                if hasattr(self.app_state, 'combat_resolver') and hasattr(self.app_state.combat_resolver, 'resolution_complete'):
                    self.app_state.combat_resolver.resolution_complete.disconnect(self._process_resolution_ui)
                    print("[CombatTracker] Successfully disconnected resolution_complete signal")
            except Exception as disconnect_error:
                print(f"[CombatTracker] Failed to disconnect signal: {disconnect_error}")
            
            # Ensure combat_log_text exists
            if not hasattr(self, 'combat_log_text'):
                print("[CombatTracker] Error: combat_log_text not found in _process_resolution_ui")
                gc.collect()
                return
                
            # Handle error first
            if error:
                self.combat_log_text.append(f"<p style='color:red;'><b>Error:</b> {error}</p>")
                # Force immediate UI update
                QApplication.processEvents()
                # Force garbage collection
                gc.collect()
                return
                
            if not result:
                self.combat_log_text.append("<p style='color:orange;'><b>Warning:</b> Combat resolution produced no result.</p>")
                # Force immediate UI update
                QApplication.processEvents()
                # Force garbage collection
                gc.collect()
                return
            
            # Extract results and update the UI
            # Save the existing combat log content before we modify it
            existing_log = ""
            try:
                existing_log = self.combat_log_text.toHtml()
                print("[CombatTracker] Preserved existing combat log")
            except Exception as log_error:
                print(f"[CombatTracker] Error preserving existing log: {log_error}")
            
            # Make a deep copy of result to prevent reference issues
            local_result = copy.deepcopy(result)
            
            # Clear the original reference to help GC
            result = None
            
            # Force garbage collection
            gc.collect()
            
            # Now work with local copy
            final_narrative = local_result.get("narrative", "No narrative provided.")
            combatants = local_result.get("updates", [])
            log_entries = local_result.get("log", [])
            round_count = local_result.get("rounds", 0)
            
            print(f"[CombatTracker] Processing combat results: {len(combatants)} combatants, {len(log_entries)} log entries, {round_count} rounds")
            
            # Make another deep copy of combatants to ensure no reference issues during updates
            combatants_copy = copy.deepcopy(combatants)
            
            # Clear original reference
            combatants = None
            
            # Update the UI first with an interim message
            self.combat_log_text.append("<hr>")
            self.combat_log_text.append("<h3 style='color:#000088;'>Processing Combat Results...</h3>")
            
            # Force UI update before applying updates
            QApplication.processEvents()
            
            # Apply the updates to the table, getting combatants that were removed
            # Ensure _apply_combat_updates exists
            removed_count = 0
            update_summaries = ["Updates applied..."]
            if hasattr(self, '_apply_combat_updates'):
                 removed_count, update_summaries = self._apply_combat_updates(combatants_copy)
            else:
                print("[CombatTracker] Error: _apply_combat_updates method not found.")
                # Attempt basic update without the helper
                if hasattr(self, '_update_combatants_in_table'):
                    self._update_combatants_in_table(combatants_copy)
                else:
                    print("[CombatTracker] Error: _update_combatants_in_table method also not found.")
            
            # Force UI update after applying updates
            QApplication.processEvents()
            
            # Build a detailed summary for the user
            turn_count = len(log_entries)
            survivors_details = []
            casualties = []
            
            # Ensure initiative table exists
            if not hasattr(self, 'initiative_table'):
                 print("[CombatTracker] Error: initiative_table not found for summary.")
                 final_log = existing_log + "<p style='color:red;'>Error generating summary: Table not found.</p>"
                 self.combat_log_text.setHtml(final_log)
                 QApplication.processEvents()
                 gc.collect()
                 return
                 
            # Process each combatant in the table
            for row in range(self.initiative_table.rowCount()):
                name_item = self.initiative_table.item(row, 0)
                hp_item = self.initiative_table.item(row, 2)
                status_item = self.initiative_table.item(row, 5)
                
                if name_item and hp_item:
                    name = name_item.text()
                    hp = hp_item.text()
                    status_text = status_item.text() if status_item else ""
                    
                    # Add death saves info for unconscious characters
                    death_saves_text = ""
                    # Check if death_saves exists
                    if hasattr(self, 'death_saves'):
                         saves = self.death_saves.get(row, None)
                         if saves:
                             successes = saves.get("successes", 0)
                             failures = saves.get("failures", 0)
                             death_saves_text = f" [DS: {successes}S/{failures}F]"

                    # Add to survivors/casualties list
                    if status_text and "dead" in status_text.lower():
                        casualties.append(name)
                    else:
                        survivors_details.append(f"{name}: {hp} HP ({status_text}){death_saves_text}")

            # Prepare final combat log with the original content preserved
            final_log = existing_log
            
            # Check if we should append to existing log or start fresh
            if "Combat Concluded" in final_log:
                # Previous combat summary exists, clear the log and start fresh
                final_log = ""
            
            # Build summary content
            summary_content = "<hr>\n"
            summary_content += "<h3 style='color:#000088;'>Combat Concluded</h3>\n"
            summary_content += f"<p>{final_narrative}</p>\n"
            summary_content += f"<p><b>Duration:</b> {round_count} rounds, {turn_count} turns</p>\n"
            
            # Add turn-by-turn log if available
            if log_entries:
                summary_content += "<p><b>Combat Log:</b></p>\n<div style='max-height: 200px; overflow-y: auto; border: 1px solid #ccc; padding: 5px; margin: 5px 0;'>\n"
                for entry in log_entries:
                    round_num = entry.get("round", "?")
                    actor = entry.get("actor", "Unknown")
                    action = entry.get("action", "")
                    result_text = entry.get("result", "")
                    
                    summary_content += f"<p><b>Round {round_num}:</b> {actor} {action}"
                    if result_text:
                        summary_content += f" - {result_text}"
                    summary_content += "</p>\n"
                summary_content += "</div>\n"
            
            # Add survivors
            if survivors_details:
                summary_content += "<p><b>Survivors:</b></p>\n<ul>\n"
                for survivor in survivors_details:
                    summary_content += f"<li>{survivor}</li>\n"
                summary_content += "</ul>\n"
            else:
                summary_content += "<p><b>Survivors:</b> None!</p>\n"
                
            # Add casualties
            if casualties:
                summary_content += "<p><b>Casualties:</b></p>\n<ul>\n"
                for casualty in casualties:
                    summary_content += f"<li>{casualty}</li>\n"
                summary_content += "</ul>\n"
        
            # Always append full summary, keeping prior log intact
            self.combat_log_text.append("<hr><h3 style='color:#000088;'>Combat Concluded</h3>")
            self.combat_log_text.append(summary_content)
            
            # Explicitly set cursor to end and scroll to bottom
            cursor = self.combat_log_text.textCursor()
            cursor.movePosition(QTextCursor.End)
            self.combat_log_text.setTextCursor(cursor)
            
            # Scroll to the bottom to see the summary
            # Check if scrollbar exists
            if hasattr(self.combat_log_text, 'verticalScrollBar'):
                 scrollbar = self.combat_log_text.verticalScrollBar()
                 scrollbar.setValue(scrollbar.maximum())
            
            # Final UI update
            QApplication.processEvents()
            
            # Clean up the rest of the references
            local_result = None
            log_entries = None
            combatants_copy = None
            survivors_details = None
            casualties = None
            
            # Final garbage collection
            gc.collect()
            
            print("[CombatTracker] Combat results processing completed successfully")
            
        except Exception as e:
            traceback.print_exc()
            print(f"[CombatTracker] Error in _process_resolution_ui: {e}")
            
            # Always reset button state no matter what
            self._reset_resolve_button("Fast Resolve", True)
            self._is_resolving_combat = False
            
            # Log the error
            # Ensure combat_log_text exists
            if hasattr(self, 'combat_log_text'):
                 self.combat_log_text.append(f"<p style='color:red;'><b>Error:</b> An error occurred while processing the combat result: {str(e)}</p>")
            
            # Force garbage collection
            gc.collect()

    # From chunk2.py (needed by _fast_resolve_combat completion callback and turn callback)
    def _update_ui_wrapper(self, turn_state):
        """Thread-safe wrapper to update UI during combat (used by the resolver)"""
        # Serialize the turn state to JSON
        try:
            import json
            import traceback
            from PySide6.QtCore import QMetaObject, Qt, Q_ARG
            from PySide6.QtWidgets import QApplication
            from PySide6.QtCore import QEvent
            
            # Debug count of combatants
            combatants = turn_state.get("combatants", [])
            print(f"[CombatTracker] _update_ui_wrapper called with turn state containing {len(combatants)} combatants")
            
            # Ensure the turn state is serializable by sanitizing it
            def sanitize_object(obj):
                """Recursively sanitize an object to ensure it's JSON serializable"""
                if isinstance(obj, dict):
                    return {str(k): sanitize_object(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [sanitize_object(item) for item in obj]
                elif isinstance(obj, (int, float, bool, str)) or obj is None:
                    return obj
                else:
                    return str(obj)  # Convert any other types to strings
            
            # Apply sanitization
            sanitized_turn_state = sanitize_object(turn_state)
            
            # Serialize to JSON with error handling
            try:
                json_string = json.dumps(sanitized_turn_state)
                print(f"[CombatTracker] Successfully serialized turn state to JSON ({len(json_string)} chars)")
            except Exception as e:
                print(f"[CombatTracker] Error serializing turn state: {e}")
                traceback.print_exc()
                # Create a minimal valid JSON object as fallback
                json_string = json.dumps({
                    "round": turn_state.get("round", 1),
                    "current_turn_index": turn_state.get("current_turn_index", 0),
                    "combatants": []
                })
            
            # Pass the JSON string as an argument
            print("[CombatTracker] Using QMetaObject.invokeMethod for thread-safe UI update")
            try:
                result = QMetaObject.invokeMethod(
                    self, 
                    '_update_ui', 
                    Qt.QueuedConnection,  # Ensures it queues in the main thread's event loop
                    Q_ARG(str, json_string)  # Pass JSON string instead of dict/object
                )
                if not result:
                    print("[CombatTracker] WARNING: QMetaObject.invokeMethod returned False, trying alternative method")
                    # Try direct call with a slight delay (as fallback)
                    def delayed_update():
                        try:
                            self._update_ui(json_string)
                        except Exception as e:
                            print(f"[CombatTracker] Error in delayed update: {e}")
                    
                    # Schedule for execution in main thread after a slight delay
                    # Need timer reference, use QTimer.singleShot
                    from PySide6.QtCore import QTimer
                    QTimer.singleShot(100, delayed_update)
                
                # Force process events to ensure UI updates (helps with thread sync issues)
                QApplication.processEvents()
                
            except Exception as e:
                print(f"[CombatTracker] Critical error in invokeMethod: {e}")
                traceback.print_exc()
                # As a last resort, try to post a user event to update UI
                try:
                    # Use the existing custom event class
                    QApplication.postEvent(self, CombatTrackerPanel._UpdateUIEvent(json_string))
                    print("[CombatTracker] Posted custom event as last resort for UI update")
                except Exception as e2:
                    print(f"[CombatTracker] All UI update methods failed: {e2}")
                    traceback.print_exc()
                    
        except Exception as e:
            print(f"[CombatTracker] Unhandled error in _update_ui_wrapper: {e}")
            traceback.print_exc()

    # From chunk2.py (needed by _update_ui_wrapper)
    @Slot(str)
    def _update_ui(self, turn_state_json):
        """Update UI after each turn (runs in main thread via _update_ui_wrapper)."""
        # Deserialize the JSON string back into a dictionary
        try:
            # First check if the JSON string is valid
            if not turn_state_json or turn_state_json == '{}':
                print(f"[CombatTracker] Error: Empty or invalid turn_state_json")
                return
            
            # Clean the JSON string to remove any invalid characters
            import re
            turn_state_json = re.sub(r'[\x00-\x1F\x7F]', '', turn_state_json)
            
            # Additional safety for broken JSON
            if not turn_state_json.strip().startswith('{'):
                print(f"[CombatTracker] Error: Invalid JSON format, does not start with '{{'. First 100 chars: {turn_state_json[:100]}")
                # Try to extract a JSON object if present
                json_match = re.search(r'(\{.*\})', turn_state_json)
                if json_match:
                    turn_state_json = json_match.group(1)
                    print(f"[CombatTracker] Extracted potential JSON object: {turn_state_json[:50]}...")
                else:
                    # Create a minimal valid state
                    turn_state_json = '{}'
            
            # Attempt to parse JSON
            import json
            import traceback
            from PySide6.QtWidgets import QApplication
            from PySide6.QtGui import QTextCursor # Need this
            turn_state = json.loads(turn_state_json)
            if not isinstance(turn_state, dict):
                print(f"[CombatTracker] Error: Deserialized turn_state is not a dict: {type(turn_state)}")
                turn_state = {} # Use empty dict on error
        except json.JSONDecodeError as e:
            print(f"[CombatTracker] Error deserializing turn_state JSON: {e}")
            print(f"[CombatTracker] JSON string causing error (first 100 chars): {turn_state_json[:100]}")
            # Fallback to an empty dict
            turn_state = {} 
        except Exception as e:
            print(f"[CombatTracker] Unexpected error in deserializing turn_state: {e}")
            traceback.print_exc()
            # Fallback to an empty dict
            turn_state = {} 
            
        # Existing logic from the original update_ui function
        try:
            # Ensure required UI elements exist
            if not hasattr(self, 'round_spin') or not hasattr(self, 'initiative_table') or not hasattr(self, 'combat_log_text'):
                 print("[CombatTracker] Error: Missing UI elements in _update_ui")
                 return
                 
            # Extract state
            round_num = turn_state.get("round", 1)
            current_idx = turn_state.get("current_turn_index", 0)
            combatants = turn_state.get("combatants", [])
            latest_action = turn_state.get("latest_action", {})
            
            # Debug logging
            print(f"\n[CombatTracker] DEBUG: Received updated turn state with {len(combatants)} combatants")
            
            # Update round counter
            self.round_spin.setValue(round_num)
            
            # Update current turn highlight
            # Ensure current_turn exists
            if not hasattr(self, '_current_turn'):
                 self._current_turn = 0
            self._current_turn = current_idx
            # Ensure _update_highlight exists
            if hasattr(self, '_update_highlight'):
                self._update_highlight()
            else:
                print("[CombatTracker] Warning: _update_highlight method not found.")
            
            # Apply combatant updates to the table
            if combatants:
                # Ensure _update_combatants_in_table exists
                if hasattr(self, '_update_combatants_in_table'):
                    # Make a copy of combatants to avoid any reference issues
                    import copy
                    combatants_copy = copy.deepcopy(combatants)
                    self._update_combatants_in_table(combatants_copy)
                    combatants_copy = None # Release copy
                else:
                     print("[CombatTracker] Warning: _update_combatants_in_table method not found.")
                
                # Force UI refresh after table update
                QApplication.processEvents()
            
            # Log the action to combat log
            if latest_action:
                # Extract action details
                actor = latest_action.get("actor", "Unknown")
                action = latest_action.get("action", "")
                result = latest_action.get("result", "")
                dice = latest_action.get("dice", [])
                
                # Create a descriptive result string
                result_str = result
                dice_summary = ""
                if dice:
                    dice_strs = [f"{d.get('purpose', 'Roll')}: {d.get('expression', '')} = {d.get('result', '')}" 
                                for d in dice]
                    dice_summary = "\n".join(dice_strs)
                    
                    # Ensure _log_combat_action exists
                    if hasattr(self, '_log_combat_action'):
                         self._log_combat_action(
                            "Turn", 
                            actor, 
                            action, 
                            result=f"{result}\n\nDice Rolls:\n{dice_summary}"
                        )
                else:
                     # Ensure _log_combat_action exists
                     if hasattr(self, '_log_combat_action'):
                         self._log_combat_action(
                            "Turn", 
                            actor, 
                            action, 
                            result=result
                        )
                
                # Update the combat log with high contrast colors - use the persistent log instead of popup
                turn_text = f"<div style='margin-bottom:10px;'>"
                turn_text += f"<h4 style='color:#000088; margin:0;'>Round {round_num} - {actor}'s Turn:</h4>"
                turn_text += f"<p style='color:#000000; margin-top:5px;'>{action}</p>"
                if result:
                    turn_text += f"<p style='color:#000000; margin-top:5px;'><strong>Result:</strong> {result}</p>"
                if dice_summary:
                    dice_html = dice_summary.replace('\n', '<br>')
                    turn_text += f"<p style='color:#000000; margin-top:5px;'><strong>Dice:</strong><br>{dice_html}</p>"
                turn_text += f"<hr style='border:1px solid #cccccc; margin:10px 0;'></div>"
                
                # Add to the persistent combat log
                current_text = self.combat_log_text.toHtml()
                if "Combat Concluded" in current_text:
                    # Previous combat summary exists, clear it and start fresh
                    self.combat_log_text.clear()
                    
                # Append the new turn text
                self.combat_log_text.append(turn_text)
                
                # Ensure cursor is at the end
                cursor = self.combat_log_text.textCursor()
                cursor.movePosition(QTextCursor.End)
                self.combat_log_text.setTextCursor(cursor)
                
                # Scroll to the bottom to see latest entries
                # Ensure scrollbar exists
                if hasattr(self.combat_log_text, 'verticalScrollBar'):
                    scrollbar = self.combat_log_text.verticalScrollBar()
                    scrollbar.setValue(scrollbar.maximum())
                
                # Force UI update after appending to combat log
                QApplication.processEvents()
            
            # Process any UI events to ensure the table updates
            QApplication.processEvents()
            
            # Force garbage collection
            import gc
            gc.collect()
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"[CombatTracker] Error in UI update: {str(e)}")

            # Force UI refresh even on error
            from PySide6.QtWidgets import QApplication
            QApplication.processEvents()
            
    # From chunk2.py (needed by _fast_resolve_combat)
    def _add_initial_combat_state_to_log(self, combat_state):
        """Add initial combat state to the log at the start of combat"""
        # Ensure combat_log_text exists
        if not hasattr(self, 'combat_log_text'):
            print("[CombatTracker] Error: combat_log_text not found in _add_initial_combat_state_to_log")
            return
            
        # Clear any previous combat log content
        if self.combat_log_text:
            # Check if we already have a "Combat Concluded" message
            current_text = self.combat_log_text.toHtml()
            if "Combat Concluded" in current_text:
                # Previous combat summary exists, clear it
                self.combat_log_text.clear()
            
        # Create summary HTML with better contrast colors
        html = "<h3 style='color: #000088;'>Initial Combat State</h3>"
        html += "<p style='color: #000000;'>Combatants in initiative order:</p>"
        html += "<ul style='color: #000000;'>"
        
        # Get combatants and build a summary
        combatants = combat_state.get("combatants", [])
        if not combatants:
            html += "<li>No combatants found</li>"
            html += "</ul>"
            html += "<p style='color: #000000;'><strong>Combat cannot begin with no combatants.</strong></p>"
            
            # Add to local log
            self.combat_log_text.append(html)
            
            # Force UI update
            from PySide6.QtWidgets import QApplication
            QApplication.processEvents()
            return
            
        # Sort by initiative
        try:
            sorted_combatants = sorted(combatants, key=lambda c: -c.get("initiative", 0))
        except Exception as e:
            print(f"[CombatTracker] Error sorting combatants: {e}")
            sorted_combatants = combatants
        
        for c in sorted_combatants:
            name = c.get("name", "Unknown")
            hp = c.get("hp", 0)
            max_hp = c.get("max_hp", hp)
            ac = c.get("ac", 10)
            initiative = c.get("initiative", 0)
            combatant_type = c.get("type", "unknown")
            
            # Different display for monsters vs characters with better styling
            if combatant_type.lower() == "monster":
                html += f"<li><strong style='color: #880000;'>{name}</strong> (Monster) - Initiative: {initiative}, AC: {ac}, HP: {hp}/{max_hp}</li>"
            else:
                html += f"<li><strong style='color: #000088;'>{name}</strong> (PC) - Initiative: {initiative}, AC: {ac}, HP: {hp}/{max_hp}</li>"
                
        html += "</ul>"
        html += "<p style='color: #000000;'><strong>Combat begins now!</strong></p>"
        html += "<hr style='border: 1px solid #000088;'>"
        
        # Add to the log
        self.combat_log_text.append(html)
        
        # Ensure cursor is at the end and scroll to the bottom
        # Check if text cursor exists
        if hasattr(self.combat_log_text, 'textCursor'):
             cursor = self.combat_log_text.textCursor()
             # Check if movePosition exists
             if hasattr(cursor, 'movePosition'):
                from PySide6.QtGui import QTextCursor # Need this import
                cursor.movePosition(QTextCursor.End)
                self.combat_log_text.setTextCursor(cursor)
        
        # Check if scrollbar exists
        if hasattr(self.combat_log_text, 'verticalScrollBar'):
            scrollbar = self.combat_log_text.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
        
        # Force UI update
        from PySide6.QtWidgets import QApplication
        QApplication.processEvents()
        
    # From chunk2.py (needed by _update_ui)
    # We need _update_combatants_in_table
    def _update_combatants_in_table(self, combatants):
        """
        Update the initiative table with new combatant data.
        
        Args:
            combatants: List of combatant dictionaries with updated values
        """
        print(f"\n[CombatTracker] DEBUG: Updating table with HP values from resolver:")
        for c in combatants:
            print(f"[CombatTracker] DEBUG: Incoming update for {c.get('name', 'Unknown')}: HP {c.get('hp', 'N/A')}")
            
        # Collect the combatants by name for easier lookup
        combatants_by_name = {}
        for combatant in combatants:
            name = combatant.get("name", "")
            if name and name not in ["Nearest Enemy", "Enemy", "Target"] and "Enemy" not in name:
                combatants_by_name[name] = combatant
        
        # Block signals during programmatic updates
        # Ensure initiative table exists
        if not hasattr(self, 'initiative_table'):
            print("[CombatTracker] Error: initiative_table not found in _update_combatants_in_table")
            return
        self.initiative_table.blockSignals(True)
        try:
            # Loop through rows in the table and update with corresponding combatant data
            for row in range(self.initiative_table.rowCount()):
                name_item = self.initiative_table.item(row, 0)
                if not name_item:
                    continue
                    
                name = name_item.text()
                if not name or name not in combatants_by_name:
                    continue
                
                # Get the corresponding combatant data
                combatant = combatants_by_name[name]
                
                # Update HP
                if "hp" in combatant:
                    hp_item = self.initiative_table.item(row, 2)
                    if hp_item:
                        old_hp = hp_item.text()
                        hp_value = combatant["hp"]
                        
                        # Track max_hp for consistency check
                        max_hp_item = self.initiative_table.item(row, 3)
                        max_hp = 0
                        if max_hp_item and max_hp_item.text():
                            try:
                                max_hp = int(max_hp_item.text())
                            except (ValueError, TypeError):
                                pass
                        
                        try:
                            # Convert to integer - use clear, strict parsing here
                            if isinstance(hp_value, int):
                                new_hp = hp_value
                                # print(f"[CombatTracker] DEBUG: Integer HP value {hp_value} for {name}") # Verbose
                            elif isinstance(hp_value, str) and hp_value.strip().isdigit():
                                new_hp = int(hp_value.strip())
                                # print(f"[CombatTracker] DEBUG: String HP value '{hp_value}' converted to {new_hp} for {name}") # Verbose
                            else:
                                # More complex string - extract first integer
                                import re
                                match = re.search(r'\d+', str(hp_value))
                                if match:
                                    new_hp = int(match.group(0))
                                    # print(f"[CombatTracker] DEBUG: Extracted HP value {new_hp} from complex string '{hp_value}' for {name}") # Verbose
                                else:
                                    # Keep existing HP if parsing fails
                                    new_hp = int(old_hp) if old_hp.isdigit() else 0
                                    print(f"[CombatTracker] DEBUG: Failed to parse HP from '{hp_value}', keeping {new_hp} for {name}")
                                
                            # Ensure HP is not greater than max_hp (if max_hp is known and positive)
                            if max_hp > 0 and "max_hp" not in combatant and new_hp > max_hp:
                                print(f"[CombatTracker] WARNING: HP value {new_hp} exceeds max_hp {max_hp} for {name}, setting HP = max_hp")
                                new_hp = max_hp
                                
                            # Set HP in table
                            if str(new_hp) != old_hp:
                                hp_item.setText(str(new_hp))
                                print(f"[CombatTracker] Updated {name} HP from {old_hp} to {new_hp}")
                                
                                # Also update self.combatant_manager.combatants_by_id dictionary if this row is in it
                                if hasattr(self, 'combatant_manager') and hasattr(self.combatant_manager, 'combatants_by_id'):
                                    instance_id = name_item.data(Qt.UserRole + 2) # Get ID from name item
                                    if instance_id and instance_id in self.combatant_manager.combatants_by_id and isinstance(self.combatant_manager.combatants_by_id[instance_id], dict):
                                        self.combatant_manager.combatants_by_id[instance_id]['current_hp'] = new_hp
                                        # print(f"[CombatTracker] Updated internal combatants dictionary for {name}: HP = {new_hp}") # Verbose
                        except Exception as e:
                            print(f"[CombatTracker] Error processing HP update for {name}: {e}")
                
                # Update status (this code remains the same)
                if "status" in combatant:
                    status_item = self.initiative_table.item(row, 5)
                    if status_item:
                        old_status = status_item.text()
                        new_status = combatant["status"]
                        if old_status != new_status:
                            status_item.setText(new_status)
                            print(f"[CombatTracker] Updated {name} status from '{old_status}' to '{new_status}'")
                
                # Update concentration if present
                if "concentration" in combatant:
                    conc_item = self.initiative_table.item(row, 6)
                    if conc_item:
                        new_state = Qt.Checked if combatant["concentration"] else Qt.Unchecked
                        if conc_item.checkState() != new_state:
                            conc_item.setCheckState(new_state)
                
                # Handle death saves if present
                if "death_saves" in combatant:
                    # Store for later tracking
                    # Ensure death_saves exists
                    if not hasattr(self, 'death_saves'):
                         self.death_saves = {} # Initialize if missing
                    self.death_saves[row] = combatant["death_saves"]
                    
                    # Display in status (if not already shown)
                    status_item = self.initiative_table.item(row, 5)
                    if status_item:
                        current_status = status_item.text()
                        successes = combatant["death_saves"].get("successes", 0)
                        failures = combatant["death_saves"].get("failures", 0)
                        
                        # If status doesn't already mention death saves, add them
                        if "death save" not in current_status.lower():
                            death_saves_text = f"Death Saves: {successes}S/{failures}F"
                            if current_status:
                                new_status = f"{current_status}, {death_saves_text}"
                            else:
                                new_status = death_saves_text
                            status_item.setText(new_status)
                            
                            # Log death save progress
                            # Ensure _log_combat_action exists
                            if hasattr(self, '_log_combat_action'):
                                 self._log_combat_action(
                                    "Death Save", 
                                    name, 
                                    "death saves", 
                                    result=f"{successes} successes, {failures} failures"
                                )
        finally:
            # Ensure signals are unblocked
            self.initiative_table.blockSignals(False)
        
        # Ensure the table is updated visually - moved outside the loop
        self.initiative_table.viewport().update()
        from PySide6.QtWidgets import QApplication
        QApplication.processEvents()
        
    # From chunk4.py (needed by _process_resolution_ui)
    def _apply_combat_updates(self, updates):
        """Apply final combatant updates from the resolution result."""
        # Import necessary modules
        import time
        import gc
        from PySide6.QtWidgets import QApplication
        
        # Initialize rows_to_remove and update_summaries
        rows_to_remove = []
        update_summaries = []
        start_time = time.time()

        print(f"[CombatTracker] Applying {len(updates)} combat updates from LLM")
        
        # Ensure the update is a list
        if not isinstance(updates, list):
            print(f"[CombatTracker] Warning: updates is not a list (type: {type(updates)})")
            if isinstance(updates, dict):
                # Convert single dict to list containing one dict
                updates = [updates]
            else:
                # Return empty results for invalid updates
                return 0, ["No valid updates to apply"]
        
        # Skip if empty
        if not updates:
            return 0, ["No updates to apply"]
            
        # Ensure initiative table exists
        if not hasattr(self, 'initiative_table'):
             print("[CombatTracker] Error: Initiative table not found in _apply_combat_updates")
             return 0, ["Error: Initiative table missing"]

        # Block signals during updates to prevent unexpected handlers
        self.initiative_table.blockSignals(True)
        try:
            # Process updates with a timeout mechanism
            max_process_time = 5.0  # Max seconds to spend processing updates
            updates_processed = 0
            
            for update_index, update in enumerate(updates):
                # Check processing time limit
                elapsed = time.time() - start_time
                if elapsed > max_process_time:
                    print(f"[CombatTracker] Update processing time limit reached ({elapsed:.1f}s). Processed {updates_processed}/{len(updates)} updates.")
                    update_summaries.append(f"WARNING: Only processed {updates_processed}/{len(updates)} updates due to time limit.")
                    break
                
                # Process update in a try block to handle errors individually
                try:
                    name_to_find = update.get("name")
                    if not name_to_find:
                        continue

                    # Periodically update UI and force GC during long operations
                    if update_index > 0 and update_index % 5 == 0:
                        print(f"[CombatTracker] Processed {update_index}/{len(updates)} updates...")
                        self.initiative_table.blockSignals(False)
                        QApplication.processEvents()
                        self.initiative_table.blockSignals(True)
                        gc.collect()

                    # print(f"[CombatTracker] Processing update for {name_to_find}") # Verbose
                    # Find the row for the combatant
                    found_row = -1
                    for row in range(self.initiative_table.rowCount()):
                        name_item = self.initiative_table.item(row, 0)
                        if name_item and name_item.text() == name_to_find:
                            found_row = row
                            break

                    if found_row != -1:
                        # print(f"[CombatTracker] Found {name_to_find} at row {found_row}") # Verbose
                        # Apply HP update
                        if "hp" in update:
                            hp_item = self.initiative_table.item(found_row, 2)
                            if hp_item:
                                old_hp = hp_item.text()
                                try:
                                    new_hp_value = 0
                                    # First try to convert directly to int
                                    if isinstance(update["hp"], int):
                                        new_hp_value = max(0, update["hp"])
                                    elif isinstance(update["hp"], str) and update["hp"].strip().isdigit():
                                        new_hp_value = max(0, int(update["hp"].strip()))
                                    else:
                                        # Handle other formats - extract numbers
                                        import re
                                        match = re.search(r'\d+', str(update["hp"]))
                                        if match:
                                            new_hp_value = max(0, int(match.group(0)))
                                        else:
                                            # If we can't extract a number, keep old HP
                                            print(f"[CombatTracker] Warning: Could not extract HP value from '{update['hp']}'")
                                            if old_hp and old_hp.isdigit():
                                                new_hp_value = int(old_hp)
                                            else:
                                                new_hp_value = 0
                                    
                                    new_hp_str = str(new_hp_value)
                                    if new_hp_str != old_hp:
                                         hp_item.setText(new_hp_str)
                                         # print(f"[CombatTracker] Set {name_to_find} HP to {new_hp_str} in row {found_row} (was {old_hp})") # Verbose
                                         update_summaries.append(f"- {name_to_find}: HP changed from {old_hp} to {new_hp_str}")
                                    
                                    # Handle death/unconscious status if HP reaches 0
                                    if new_hp_value <= 0 and "status" not in update:
                                        # Add Unconscious status
                                        status_item = self.initiative_table.item(found_row, 5)  # Status is now column 5
                                        if status_item:
                                            current_statuses = []
                                            if status_item.text():
                                                current_statuses = [s.strip() for s in status_item.text().split(',')]
                                            
                                            # Only add if not already present
                                            if "Unconscious" not in current_statuses and "Dead" not in current_statuses:
                                                current_statuses.append("Unconscious")
                                                status_item.setText(', '.join(current_statuses))
                                                update_summaries.append(f"- {name_to_find}: Added 'Unconscious' status due to 0 HP")
                                except Exception as e:
                                    print(f"[CombatTracker] Error processing HP update for {name_to_find}: {str(e)}")
                        # Apply Status update
                        if "status" in update:
                            status_item = self.initiative_table.item(found_row, 5)
                            if status_item:
                                old_status_text = status_item.text()
                                old_statuses = [s.strip() for s in old_status_text.split(',')] if old_status_text else []

                                new_status = update["status"]
                                new_status_text = ""

                                # Handle different status update formats
                                if isinstance(new_status, list):
                                    # If status is a list, replace all existing statuses
                                    new_statuses = new_status
                                    new_status_text = ', '.join(new_statuses)
                                elif new_status == "clear":
                                    # Special case to clear all statuses
                                    new_status_text = ""
                                elif isinstance(new_status, str) and new_status.startswith("+"):
                                    # Add a status (e.g., "+Poisoned")
                                    status_to_add = new_status[1:].strip()
                                    if status_to_add and status_to_add not in old_statuses:
                                        old_statuses.append(status_to_add)
                                    new_status_text = ', '.join(old_statuses)
                                elif isinstance(new_status, str) and new_status.startswith("-"):
                                    # Remove a status (e.g., "-Poisoned")
                                    status_to_remove = new_status[1:].strip()
                                    if status_to_remove and status_to_remove in old_statuses:
                                        old_statuses.remove(status_to_remove)
                                    new_status_text = ', '.join(old_statuses)
                                else:
                                    # Otherwise, directly set the new status (backward compatibility)
                                    new_status_text = new_status
                                    
                                # Update the table item if changed
                                if status_item.text() != new_status_text:
                                    status_item.setText(new_status_text)
                                    update_summaries.append(f"- {name_to_find}: Status changed from '{old_status_text}' to '{new_status_text}'")

                                # If status contains "Dead" or "Fled", mark for removal
                                current_statuses = new_status_text.split(',')
                                if any(s.strip().lower() in ["dead", "fled"] for s in current_statuses): # Use lower() for case-insensitivity
                                    if found_row not in rows_to_remove: # Avoid duplicates
                                        rows_to_remove.append(found_row)
                                        
                    updates_processed += 1
                except Exception as update_error:
                    print(f"[CombatTracker] Error processing update for index {update_index}: {update_error}")
                    import traceback
                    traceback.print_exc()
                    update_summaries.append(f"ERROR: Failed to process update for index {update_index}")
                    continue  # Skip to next update
        finally:
            # Ensure signals are unblocked even if an error occurs
            self.initiative_table.blockSignals(False)
            
            # Force UI update after all individual updates
            QApplication.processEvents()

        # Process removal separately with a new timeout check
        start_removal_time = time.time()
        removal_time_limit = 3.0  # Limit time spent on removals
        
        # Remove combatants marked for removal (in reverse order)
        if rows_to_remove:
            # Block signals again during row removal for safety
            self.initiative_table.blockSignals(True)
            turn_adjusted = False # Track if current turn needs adjusting
            try:
                print(f"[CombatTracker] Removing {len(rows_to_remove)} combatants...")
                # Ensure current_turn exists and is int
                if not hasattr(self, 'current_turn') or not isinstance(self.current_turn, int):
                     self.current_turn = 0
                     
                for i, row in enumerate(sorted(list(set(rows_to_remove)), reverse=True)): # Use set() to ensure unique rows
                    # Check timeout for removals
                    if time.time() - start_removal_time > removal_time_limit:
                        print(f"[CombatTracker] Removal time limit reached. Processed {i}/{len(rows_to_remove)} removals.")
                        update_summaries.append(f"WARNING: Only removed {i}/{len(rows_to_remove)} combatants due to time limit.")
                        break
                        
                    # Skip invalid rows
                    if row >= self.initiative_table.rowCount() or row < 0:
                        print(f"[CombatTracker] Skipping invalid row {row}")
                        continue
                        
                    print(f"[CombatTracker] Removing row {row}")
                    self.initiative_table.removeRow(row)
                    # Adjust current turn if needed
                    if row < self.current_turn:
                        self.current_turn -= 1
                        turn_adjusted = True
                    elif row == self.current_turn:
                        # If removing the current turn, reset it (e.g., to -1 or 0 if combatants remain)
                        self.current_turn = 0 if self.initiative_table.rowCount() > 0 else -1
                        turn_adjusted = True

                    # Clean up tracking
                    # Ensure death_saves and concentrating exist
                    if hasattr(self, 'death_saves'):
                        self.death_saves.pop(row, None)
                    if hasattr(self, 'concentrating'):
                        self.concentrating.discard(row) # Use discard for sets
                    # Ensure combatant_manager exists
                    if hasattr(self, 'combatant_manager') and hasattr(self.combatant_manager, 'combatants_by_id'):
                        # Remove by ID if possible, fallback to row
                        combatant_id = None
                        # Find ID based on row before removing
                        # This needs to be done carefully if rows shift
                        # Better: find ID before loop, remove by ID after loop
                        self.combatant_manager.combatants_by_id.pop(row, None) # Clean up combatants dict (fallback by row)

                # Update highlight ONLY if turn was adjusted
                if turn_adjusted:
                    # Ensure _update_highlight exists
                    if hasattr(self, '_update_highlight'):
                         self._update_highlight()
                    else:
                         print("[CombatTracker] Warning: _update_highlight method not found after removal.")
            finally:
                 self.initiative_table.blockSignals(False) # Unblock after removals

        # Calculate elapsed time
        total_time = time.time() - start_time
        print(f"[CombatTracker] Combat updates applied in {total_time:.2f} seconds: {updates_processed} updates, {len(rows_to_remove)} removals")
        
        # Ensure the UI table is refreshed after all updates and removals
        self.initiative_table.viewport().update()
        QApplication.processEvents()

        # Force garbage collection
        gc.collect()

        # Return the initialized variables
        return len(rows_to_remove), update_summaries
        
    # ------------------------------------------------------------------
    # END: Added methods
    # ------------------------------------------------------------------

    # ... (rest of the class if any)
