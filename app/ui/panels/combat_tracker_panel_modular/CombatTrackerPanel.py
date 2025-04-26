# Modularized CombatTrackerPanel (auto-generated)

from .combattrackerpanel_ensure_helpers import *  # _ensure_ helpers
from .combattrackerpanel_setup_helpers import *  # _setup_ helpers
from .combattrackerpanel_handle_helpers import *  # _handle_ helpers
from .combattrackerpanel_sort_helpers import *  # _sort_ helpers
from .combattrackerpanel_quick_helpers import *  # _quick_ helpers
from .combattrackerpanel_update_helpers import *  # _update_ helpers
from .combattrackerpanel_next_helpers import *  # _next_ helpers
from .combattrackerpanel_show_helpers import *  # _show_ helpers
from .combattrackerpanel_add_helpers import *  # _add_ helpers
from .combattrackerpanel_remove_helpers import *  # _remove_ helpers
from .combattrackerpanel_clear_helpers import *  # _clear_ helpers
from .combattrackerpanel_round_helpers import *  # _round_ helpers
from .combattrackerpanel_toggle_helpers import *  # _toggle_ helpers
from .combattrackerpanel_roll_helpers import *  # _roll_ helpers
from .combattrackerpanel_reset_helpers import *  # _reset_ helpers
from .combattrackerpanel_restart_helpers import *  # _restart_ helpers
from .combattrackerpanel_check_helpers import *  # _check_ helpers
class CombatTrackerPanel(BasePanel):
    """Panel for tracking combat initiative, HP, and conditions"""
    # ... see helpers for most methods ...

        def current_turn(self):
            """Get the current turn index"""
            return getattr(self, '_current_turn', -1)
        def current_turn(self, value):
            """Set the current turn index"""
            self._current_turn = value
        def __init__(self, app_state):
            """Initialize the combat tracker panel"""
            # Store app state and get services
            self.app_state = app_state
            self.db = app_state.db_manager
            self.llm_service = app_state.llm_service
            
            # Initialize combat state (attributes not moved to manager)
            self.current_round = 1
            self._current_turn = 0 # Use _current_turn internally
            self.previous_turn = -1
            self.combat_time = 0
            self.combat_started = False
            self.death_saves = {}  # Store by row index: {successes: int, failures: int}
            self.concentrating = set()  # Store row indices of concentrating combatants
            
            # --- NEW: Instantiate CombatantManager ---
            self.combatant_manager = CombatantManager(self)
            
            # REMOVED: self.combatant_manager.combatants_by_id = {} 
            # REMOVED: self.monster_id_counter = 0 
            
            # Add missing property initialization
            self.show_details_pane = False
            self._is_resolving_combat = False 
            
            # Initialize timers
            self.timer = QTimer()
            self.timer.timeout.connect(self._update_timer)
            self.timer.setInterval(1000)  # 1 second interval
            self.combat_log = []  # List of combat log entries
            self.combat_log_widget = None
            
            # Initialize base panel (calls _setup_ui)
            super().__init__(app_state, "Combat Tracker")
            
            print("[CombatTracker] Basic attributes initialized")
            
            # Set up our custom delegates after the table is created
            self._setup_delegates()
            
            # Ensure table is ready for display
            self._ensure_table_ready()
            
            # After state is restored, fix missing types (using manager)
            # Make sure this call happens after potential state restore in _ensure_table_ready
            QTimer.singleShot(500, self.combatant_manager.fix_missing_types)
            
            print("[CombatTracker] Initialization completed successfully")
            
            # Connect the turn result signal to the slot
            self.show_turn_result_signal.connect(self._show_turn_result_slot)
            
            # Connect to combat resolver if available
            if hasattr(self.app_state, 'combat_resolver') and self.app_state.combat_resolver:
                try:
                    if isinstance(self.app_state.combat_resolver, QObject):
                        self.app_state.combat_resolver.resolution_complete.connect(self._process_resolution_ui)
                        if hasattr(self.app_state.combat_resolver, 'turn_update'):
                            self.app_state.combat_resolver.turn_update.connect(self._update_ui_wrapper)
                            print("[CombatTracker] Connected turn_update signal to _update_ui_wrapper")
                        else:
                            print("[CombatTracker] Warning: CombatResolver has no turn_update signal")
                        print("[CombatTracker] Connected resolution_complete signal to _process_resolution_ui slot.")
                    else:
                        print("[CombatTracker] Warning: CombatResolver is not a QObject, cannot connect signals.")
                except Exception as e:
                    print(f"[CombatTracker] Error connecting to combat resolver: {e}")
        def _hp_changed(self, row, new_hp):
            """Handle HP changes from delegate editing"""
            if 0 <= row < self.initiative_table.rowCount():
                # Get current HP
                hp_item = self.initiative_table.item(row, 2)  # HP is now column 2
                if hp_item:
                    # Already updated via setModelData, check for special cases
                    if new_hp == 0:
                        name = self.initiative_table.item(row, 0).text()
                        QMessageBox.information(
                            self,
                            "HP Reduced to 0",
                            f"{name} is down! Remember to track death saves."
                        )
        def _initiative_changed(self, row, new_initiative):
            """Handle initiative changes from delegate editing"""
            if 0 <= row < self.initiative_table.rowCount():
                # Log the initiative change
                name = self.initiative_table.item(row, 0).text() if self.initiative_table.item(row, 0) else "Unknown"
                print(f"[CombatTracker] Initiative changed: {name} now has initiative {new_initiative}")
                self._log_combat_action("Initiative", name, "changed initiative", result=f"New value: {new_initiative}")
                
                # Auto-sort the initiative table
                self._sort_initiative()
        def _set_status(self, status):
            """Apply a status condition to selected combatants (legacy method)"""
            if not status:
                # If empty status, clear all
                self._clear_statuses()
            else:
                # Otherwise add the status
                self._add_status(status)
        def _fast_resolve_combat(self):
            """Use LLM to resolve the current combat encounter (turn-by-turn, rule-correct)."""
            import traceback
            import threading
            import gc
            from PySide6.QtWidgets import QApplication, QMessageBox
    
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
                        return
                        
                    elif not has_monster and has_player:
                        QApplication.instance().postEvent(self, CombatTrackerPanel._ErrorEvent(
                            "Cannot Start Combat", 
                            "You need at least one monster to run combat against player characters.\n\n" +
                            "Add monsters from the Monster Panel."
                        ))
                        return
                    
                    # Step 2: Gather combat state
                    QApplication.instance().postEvent(self, CombatTrackerPanel._ProgressEvent("Gathering combat data..."))
                    combat_state = self._gather_combat_state()
                    if not combat_state or not combat_state.get("combatants"):
                        QApplication.instance().postEvent(self, CombatTrackerPanel._ErrorEvent(
                            "Fast Resolve", 
                            "No combatants in the tracker to resolve."
                        ))
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
                    
                    # Step 6: Setup completion callback
                    def completion_callback(result, error):
                        """Callback for resolution completion if signals aren't working"""
                        print(f"[CombatTracker] Manual completion callback called with result={bool(result)}, error={bool(error)}")
                        
                        # Forward to our UI handler via a custom event - safest approach
                        QApplication.instance().postEvent(self, CombatTrackerPanel._ProcessResultEvent(result, error))
                        
                        # Directly update button state via event
                        QApplication.instance().postEvent(self, CombatTrackerPanel._UpdateButtonEvent("Fast Resolve", True))
                        print("[CombatTracker] Posted button update event")
                        
                        # Create a very short timer as a last resort
                        reset_timer = QTimer()
                        reset_timer.setSingleShot(True)
                        reset_timer.timeout.connect(lambda: self._check_and_reset_button())
                        reset_timer.start(1000)  # 1 second delay
                    
                    # Step 7: Setup turn callback
                    def manual_turn_callback(turn_state):
                        """Callback for per-turn updates if signals aren't working"""
                        print(f"[CombatTracker] Manual turn update callback received data with "
                              f"{len(turn_state.get('combatants', []))} combatants")
                        # Forward to our wrapper method via a custom event
                        QApplication.instance().postEvent(self, CombatTrackerPanel._UpdateUIEvent(turn_state))
                    
                    # Step 8: Start the actual combat resolution
                    QApplication.instance().postEvent(self, CombatTrackerPanel._SetResolvingEvent(True))
                    
                    # Setup signal connection (done on UI thread)
                    QApplication.instance().postEvent(self, CombatTrackerPanel._ConnectSignalEvent())
                    
                    # Update UI to show we're now resolving
                    QApplication.instance().postEvent(self, CombatTrackerPanel._UpdateButtonEvent("Resolving...", False))
                    
                    # Step 9: Call the resolver with our setup
                    resolver_callable = self.app_state.combat_resolver.resolve_combat_turn_by_turn
                    accepts_turn_callback = 'turn_update_callback' in resolver_callable.__code__.co_varnames
    
                    # Update UI with final preparation status
                    QApplication.instance().postEvent(self, CombatTrackerPanel._ProgressEvent("Starting combat resolution..."))
                    
                    # Call with appropriate arguments based on what the resolver supports
                    if accepts_turn_callback:
                        print("[CombatTracker] Resolver supports turn_update_callback, using it")
                        # This resolver takes a turn callback directly
                        self.app_state.combat_resolver.resolve_combat_turn_by_turn(
                            combat_state,
                            dice_roller,
                            completion_callback,  # Use our manual callback
                            manual_turn_callback  # Pass the callback for turns
                        )
                    else:
                        print("[CombatTracker] Using standard resolver with update_ui_callback, relying on signals")
                        # Standard resolver - use it with our update_ui_wrapper and rely on signals
                        self.app_state.combat_resolver.resolve_combat_turn_by_turn(
                            combat_state,
                            dice_roller,
                            completion_callback,  # Pass our manual callback for backup
                            self._update_ui_wrapper  # This might be treated as update_ui_callback depending on interface
                        )
                        
                except Exception as e:
                    traceback.print_exc()
                    # If any error occurs, send an error event
                    QApplication.instance().postEvent(self, CombatTrackerPanel._ErrorEvent(
                        "Error", 
                        f"Failed to start combat resolution: {str(e)}"
                    ))
            
            # Start the setup in a background thread
            setup_thread = threading.Thread(target=setup_and_start_combat)
            setup_thread.daemon = True  # Allow app to exit even if thread is running
            setup_thread.start()
        def event(self, event):
            """Handle custom events posted to our panel"""
            from PySide6.QtWidgets import QApplication, QMessageBox
            
            if event.type() == QEvent.Type(QEvent.User + 1):
                # This is our UpdateUIEvent for JSON
                try:
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
                QMessageBox.critical(self, event.title, event.message)
                return True
            elif event.type() == QEvent.Type(QEvent.User + 102):
                # Clear log event
                self.combat_log_text.clear()
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
                # Process result event
                self._process_resolution_ui(event.result, event.error)
                return True
            elif event.type() == QEvent.Type(QEvent.User + 106):
                # Update UI event
                self._update_ui_wrapper(event.turn_state)
                return True
            elif event.type() == QEvent.Type(QEvent.User + 107):
                # Set resolving event
                self._is_resolving_combat = event.is_resolving
                print(f"[CombatTracker] Setting _is_resolving_combat = {event.is_resolving}")
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
        def _event_duplicate_backup(self, event):
            """Handle custom events posted to our panel"""
            if event.type() == QEvent.Type(QEvent.User + 1):
                # This is our UpdateUIEvent
                try:
                    self._update_ui(event.json_data)
                    return True
                except Exception as e:
                    print(f"[CombatTracker] Error in event handler UI update: {e}")
                    return False
            return super().event(event)
        def _create_live_combat_log(self):
            """Create a live combat log widget that displays during combat resolution"""
            try:
                from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QDialogButtonBox, QPushButton
                
                # Create the dialog
                self.combat_log_widget = QDialog(self)
                self.combat_log_widget.setWindowTitle("Combat In Progress")
                self.combat_log_widget.setWindowFlags(
                    self.combat_log_widget.windowFlags() | Qt.Tool | Qt.WindowStaysOnTopHint
                )
                self.combat_log_widget.setMinimumSize(500, 500)
                
                # Create layout
                layout = QVBoxLayout(self.combat_log_widget)
                
                # Add text display for combat log with improved contrast
                self.combat_log_widget.log_text = QTextEdit()
                self.combat_log_widget.log_text.setReadOnly(True)
                self.combat_log_widget.log_text.setStyleSheet("""
                    QTextEdit { 
                        background-color: white;
                        color: #000000;
                        font-family: Arial, sans-serif;
                        font-size: 14px;
                        font-weight: 500;
                    }
                """)
                layout.addWidget(self.combat_log_widget.log_text)
                
                # Add header text
                header_text = "<h2 style='color: #000088;'>Combat In Progress</h2>"
                header_text += "<p style='color: #000000;'><strong>Watch as the battle unfolds turn by turn! Combat details will appear here and in popups.</strong></p>"
                header_text += "<hr style='border: 1px solid #000088;'>"
                self.combat_log_widget.log_text.setHtml(header_text)
                
                # Add a close button that just hides the dialog (combat continues)
                btn_box = QDialogButtonBox()
                close_btn = QPushButton("Hide Log")
                close_btn.clicked.connect(self.combat_log_widget.hide)
                btn_box.addButton(close_btn, QDialogButtonBox.ActionRole)
                layout.addWidget(btn_box)
                
                # Add create_entry method to make it compatible with the combat log interface
                def create_entry(category=None, actor=None, action=None, target=None, result=None, round=None, turn=None):
                    # Create a simple entry representation
                    entry = {
                        "category": category,
                        "actor": actor,
                        "action": action,
                        "target": target,
                        "result": result,
                        "round": round,
                        "turn": turn
                    }
                    # Format the entry into HTML
                    html = f"<p><strong>{actor}:</strong> {action}"
                    if target:
                        html += f" <strong>{target}</strong>"
                    if result:
                        html += f" - {result}"
                    html += "</p>"
                    # Add it to the log text if possible
                    if hasattr(self.combat_log_widget, 'log_text'):
                        self.combat_log_widget.log_text.append(html)
                    return entry
                    
                # Add the method to the widget
                self.combat_log_widget.create_entry = create_entry
                
            except Exception as e:
                print(f"[CombatTracker] Error creating live combat log: {e}")
                self.combat_log_widget = None
        def _gather_combat_state(self):
            """Gather the current state of the combat from the table."""
            combatants = []
            
            print(f"\n[CombatTracker] DEBUG: Gathering combat state with current HP values from table:")
            
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
                if instance_id and instance_id in self.combatant_manager.combatants_by_id: # USE CONSISTENT instance_id
                     stored_combatant = self.combatant_manager.combatants_by_id[instance_id] # USE CONSISTENT instance_id
                     logging.debug(f"Found stored data for instance ID {instance_id}")
                # REMOVED Fallback to row index lookup to strictly enforce ID matching
                # elif row in self.combatant_manager.combatants_by_id: 
    
                if stored_combatant:
                    # ... (rest of the merging/tagging logic - ENSURE IT USES 'stored_combatant') ...
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
                                # FIXED: Tag each ability with the monster instance ID to prevent mixing
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
                                
                                # FIXED: Tag abilities with monster instance ID
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
                
            # FIXED: Add a validation step to ensure no ability mixing
            self._validate_no_ability_mixing(combatants)
                
            return {
                "round": self.current_round,
                "current_turn_index": self.current_turn,
                "combatants": combatants
            }
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
    
                        print(f"[CombatTracker] Processing update for {name_to_find}")
                        # Find the row for the combatant
                        found_row = -1
                        for row in range(self.initiative_table.rowCount()):
                            name_item = self.initiative_table.item(row, 0)
                            if name_item and name_item.text() == name_to_find:
                                found_row = row
                                break
    
                        if found_row != -1:
                            print(f"[CombatTracker] Found {name_to_find} at row {found_row}")
                            # Apply HP update
                            if "hp" in update:
                                hp_item = self.initiative_table.item(found_row, 2)
                                if hp_item:
                                    old_hp = hp_item.text()
                                    try:
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
                                        
                                        new_hp = str(new_hp_value)
                                        hp_item.setText(new_hp)
                                        print(f"[CombatTracker] Set {name_to_find} HP to {new_hp} in row {found_row} (was {old_hp})")
                                        update_summaries.append(f"- {name_to_find}: HP changed from {old_hp} to {new_hp}")
                                        
                                        # Handle death/unconscious status if HP reaches 0
                                        if new_hp_value <= 0 and "status" not in update:
                                            # Add Unconscious status
                                            status_item = self.initiative_table.item(found_row, 5)  # Status is now column 5
                                            if status_item:
                                                current_statuses = []
                                                if status_item.text():
                                                    current_statuses = [s.strip() for s in status_item.text().split(',')]
                                                
                                                # Only add if not already present
                                                if "Unconscious" not in current_statuses:
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
    
                                    # Handle different status update formats
                                    if isinstance(new_status, list):
                                        # If status is a list, replace all existing statuses
                                        new_statuses = new_status
                                        status_item.setText(', '.join(new_statuses))
                                        update_summaries.append(f"- {name_to_find}: Status changed from '{old_status_text}' to '{', '.join(new_statuses)}'")
                                    elif new_status == "clear":
                                        # Special case to clear all statuses
                                        status_item.setText("")
                                        update_summaries.append(f"- {name_to_find}: All statuses cleared (was '{old_status_text}')")
                                    elif new_status.startswith("+"):
                                        # Add a status (e.g., "+Poisoned")
                                        status_to_add = new_status[1:].strip()
                                        if status_to_add and status_to_add not in old_statuses:
                                            old_statuses.append(status_to_add)
                                            status_item.setText(', '.join(old_statuses))
                                            update_summaries.append(f"- {name_to_find}: Added '{status_to_add}' status")
                                    elif new_status.startswith("-"):
                                        # Remove a status (e.g., "-Poisoned")
                                        status_to_remove = new_status[1:].strip()
                                        if status_to_remove and status_to_remove in old_statuses:
                                            old_statuses.remove(status_to_remove)
                                            status_item.setText(', '.join(old_statuses))
                                            update_summaries.append(f"- {name_to_find}: Removed '{status_to_remove}' status")
                                    else:
                                        # Otherwise, directly set the new status (backward compatibility)
                                        status_item.setText(new_status)
                                        update_summaries.append(f"- {name_to_find}: Status changed from '{old_status_text}' to '{new_status}'")
    
                                    # If status contains "Dead" or "Fled", mark for removal
                                    current_statuses = status_item.text().split(',')
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
                        self.death_saves.pop(row, None)
                        self.concentrating.discard(row) # Use discard for sets
                        self.combatant_manager.combatants_by_id.pop(row, None) # Clean up combatants dict
    
                    # Update highlight ONLY if turn was adjusted
                    if turn_adjusted:
                         self._update_highlight()
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
        def _get_combat_log(self):
            """Get reference to the combat log panel for integration or create a local fallback"""
            # If we already have a valid combat log widget with create_entry method, return it
            if hasattr(self, 'combat_log_widget') and self.combat_log_widget:
                if hasattr(self.combat_log_widget, 'create_entry'):
                    return self.combat_log_widget
                else:
                    print("[CombatTracker] Warning: Cached combat_log_widget doesn't have create_entry method")
                    # Clear the invalid reference - we'll try to create a fallback
                    self.combat_log_widget = None
                
            # Try to get the combat log panel from panel_manager
            try:
                panel_manager = getattr(self.app_state, 'panel_manager', None)
                if panel_manager:
                    combat_log_panel = panel_manager.get_panel("combat_log")
                    if combat_log_panel:
                        print("[CombatTracker] Found combat_log panel, checking interface...")
                        
                        # Check if it has the expected create_entry method
                        if hasattr(combat_log_panel, 'create_entry'):
                            print("[CombatTracker] Combat log panel has required create_entry method")
                            self.combat_log_widget = combat_log_panel
                            return self.combat_log_widget
                        else:
                            print("[CombatTracker] Combat log panel doesn't have required interface, creating adapter...")
                            # Create an adapter that wraps the panel
                            try:
                                self._create_combat_log_adapter(combat_log_panel)
                                if hasattr(self.combat_log_widget, 'create_entry'):
                                    return self.combat_log_widget
                            except Exception as e:
                                print(f"[CombatTracker] Error creating combat log adapter: {e}")
            except Exception as e:
                print(f"[CombatTracker] Error getting combat log panel: {e}")
            
            # Create a local fallback if needed
            if not hasattr(self, 'combat_log_widget') or not self.combat_log_widget:
                print("[CombatTracker] Creating local fallback combat log")
                self._create_fallback_combat_log()
                
            # Return whatever we have at this point (might still be None in worst case)
            return self.combat_log_widget
        def _create_combat_log_adapter(self, panel):
            """Create an adapter for the combat log panel to provide the create_entry method"""
            # Store the panel reference
            self.combat_log_widget = panel
            
            # Add the create_entry method to the panel
            def create_entry(category=None, actor=None, action=None, target=None, result=None, round=None, turn=None):
                try:
                    # Create a simple entry representation
                    entry = {
                        "category": category,
                        "actor": actor,
                        "action": action,
                        "target": target,
                        "result": result,
                        "round": round,
                        "turn": turn
                    }
                    
                    # Format the entry into HTML
                    html = "<p>"
                    if round is not None:
                        html += f"<span style='color:#555555;'>[R{round}]</span> "
                    html += f"<strong>{actor}:</strong> {action} "
                    if target:
                        html += f"<strong>{target}</strong> "
                    if result:
                        html += f"- {result}"
                    html += "</p>"
                    
                    # Add to the log text if the panel has appropriate properties
                    if hasattr(panel, 'log_text'):
                        panel.log_text.append(html)
                    elif hasattr(panel, 'text'):
                        panel.text.append(html)
                    elif hasattr(panel, 'append') and callable(panel.append):
                        panel.append(html)
                    
                    # Always update our local log as a backup
                    if hasattr(self, 'combat_log_text') and self.combat_log_text:
                        self.combat_log_text.append(html)
                        
                    return entry
                except Exception as e:
                    print(f"[CombatTracker] Error in create_entry adapter: {e}")
                    return {"error": str(e)}
                    
            # Add the method to the panel
            setattr(self.combat_log_widget, 'create_entry', create_entry)
        def _create_fallback_combat_log(self):
            """Create a fallback combat log that stores entries for when external log isn't available"""
            try:
                # Create a simple object with the required interface
                from types import SimpleNamespace
                log = SimpleNamespace()
                
                # Add a list to store entries
                log.entries = []
                
                # Add the create_entry method
                def create_entry(category=None, actor=None, action=None, target=None, result=None, round=None, turn=None):
                    # Create entry object
                    entry = {
                        "category": category,
                        "actor": actor,
                        "action": action,
                        "target": target,
                        "result": result,
                        "round": round,
                        "turn": turn,
                        "timestamp": time.time()
                    }
                    
                    # Store the entry
                    log.entries.append(entry)
                    
                    # Format the entry and add to our local combat log text widget
                    try:
                        if hasattr(self, 'combat_log_text') and self.combat_log_text:
                            # Determine text color based on category
                            color_map = {
                                "Attack": "#8B0000",   # Dark Red
                                "Damage": "#A52A2A",   # Brown
                                "Healing": "#006400",  # Dark Green
                                "Status Effect": "#4B0082",  # Indigo
                                "Death Save": "#000080",  # Navy
                                "Initiative": "#2F4F4F",  # Dark Slate Gray
                                "Turn": "#000000",  # Black
                                "Other": "#708090",  # Slate Gray
                                "Dice": "#696969",  # Dim Gray
                                "Setup": "#708090",  # Slate Gray
                                "Concentration Check": "#800080"  # Purple
                            }
                            
                            text_color = color_map.get(category, "#000000")
                            
                            # Format the HTML
                            round_text = f"R{round}" if round is not None else ""
                            
                            html = f"<p style='margin-top:5px; margin-bottom:5px;'>"
                            if round_text:
                                html += f"<span style='color:#555555;'>[{round_text}]</span> "
                            html += f"<span style='font-weight:bold; color:{text_color};'>{actor}</span> "
                            html += f"{action} "
                            
                            if target:
                                html += f"<span style='font-weight:bold;'>{target}</span> "
                                
                            if result:
                                html += f"<span style='color:#555555;'>{result}</span>"
                                
                            html += "</p>"
                            
                            self.combat_log_text.append(html)
                            
                            # Scroll to the bottom to see latest entries
                            scrollbar = self.combat_log_text.verticalScrollBar()
                            scrollbar.setValue(scrollbar.maximum())
                    except Exception as e:
                        print(f"[CombatTracker] Error formatting log entry for display: {e}")
                    
                    return entry
                    
                # Add the method
                log.create_entry = create_entry
                
                # Store the log
                self.combat_log_widget = log
                
                print("[CombatTracker] Created fallback combat log")
            except Exception as e:
                print(f"[CombatTracker] Error creating fallback combat log: {e}")
                self.combat_log_widget = None
        def _log_combat_action(self, category, actor, action, target=None, result=None, round=None, turn=None):
            """Log a combat action and update the persistent combat log"""
            # Safely get the combat log with all our fallback mechanisms
            try:
                combat_log = self._get_combat_log()
                log_entry = None
                
                # Emit the combat_log_signal for panel connections
                try:
                    self.combat_log_signal.emit(
                        category or "",
                        actor or "",
                        action or "",
                        target or "",
                        result or ""
                    )
                except Exception as e:
                    print(f"[CombatTracker] Error emitting combat_log_signal: {e}")
                
                # Try to create an entry using the combat log
                if combat_log and hasattr(combat_log, 'create_entry'):
                    try:
                        log_entry = combat_log.create_entry(
                            category=category,
                            actor=actor,
                            action=action,
                            target=target,
                            result=result,
                            round=round if round is not None else self.round_spin.value(),
                            turn=turn
                        )
                    except Exception as e:
                        print(f"[CombatTracker] Error creating combat log entry: {str(e)}")
                else:
                    # Direct display to our local combat log if external log not available
                    try:
                        # Only proceed if we have a local log text widget
                        if hasattr(self, 'combat_log_text') and self.combat_log_text:
                            # Determine text color based on category
                            color_map = {
                                "Attack": "#8B0000",   # Dark Red
                                "Damage": "#A52A2A",   # Brown
                                "Healing": "#006400",  # Dark Green
                                "Status Effect": "#4B0082",  # Indigo
                                "Death Save": "#000080",  # Navy
                                "Initiative": "#2F4F4F",  # Dark Slate Gray
                                "Turn": "#000000",  # Black
                                "Other": "#708090",  # Slate Gray
                                "Dice": "#696969",  # Dim Gray
                                "Setup": "#708090",  # Slate Gray
                                "Concentration Check": "#800080"  # Purple
                            }
                            
                            text_color = color_map.get(category, "#000000")
                            
                            # Format the HTML
                            round_text = f"R{self.round_spin.value()}" if round is None else f"R{round}"
                            
                            html = f"<p style='margin-top:5px; margin-bottom:5px;'>"
                            html += f"<span style='color:#555555;'>[{round_text}]</span> "
                            html += f"<span style='font-weight:bold; color:{text_color};'>{actor}</span> "
                            html += f"{action} "
                            
                            if target:
                                html += f"<span style='font-weight:bold;'>{target}</span> "
                                
                            if result:
                                html += f"<span style='color:#555555;'>{result}</span>"
                                
                            html += "</p>"
                            
                            self.combat_log_text.append(html)
                            
                            # Scroll to the bottom to see latest entries
                            scrollbar = self.combat_log_text.verticalScrollBar()
                            scrollbar.setValue(scrollbar.maximum())
                    except Exception as e:
                        print(f"[CombatTracker] Error updating local combat log display: {str(e)}")
                
                return log_entry
            except Exception as e:
                # Extra safety to prevent crashes
                print(f"[CombatTracker] Critical error in _log_combat_action: {str(e)}")
                return None
        def save_state(self):
            """Save the current state of the combat tracker panel."""
            # Initialize the state dictionary with basic combat info
            state = {
                "round": self.current_round,
                "turn": self.current_turn,
                "elapsed_time": self.combat_time,
                "combatants": [], # List to hold state of each combatant
                "death_saves": self.death_saves, # Store death saves data (dict: row -> {successes, failures})
                "concentrating": list(self.concentrating) # Store concentrating combatants (set of row indices)
            }
            
            # Iterate through each row in the initiative table to save combatant data
            for row in range(self.initiative_table.rowCount()):
                # Dictionary to store the state of the current combatant
                combatant_state = {}
                
                # Define the keys corresponding to table columns for easy iteration
                # Columns: Name, Init, HP, Max HP, AC, Status, Conc, Type
                keys = ["name", "initiative", "hp", "max_hp", "ac", "status", "concentration", "type"]
                
                # Extract data for each relevant column
                for col, key in enumerate(keys):
                    # Get the QTableWidgetItem from the current cell
                    item = self.initiative_table.item(row, col)
                    
                    # Handle different data types based on column
                    if col == 6:  # Concentration column (index 6)
                        # Store boolean based on checkbox state
                        combatant_state[key] = item.checkState() == Qt.Checked if item else False
                    elif col == 0: # Name column (index 0)
                        # Store text and also UserRole data (combatant type)
                        combatant_state[key] = item.text() if item else ""
                        # Save the type stored in UserRole if available, otherwise use the 'type' column later
                        user_role_type = item.data(Qt.UserRole) if item else None
                        if user_role_type:
                             combatant_state["user_role_type"] = user_role_type # Store separately for restore logic
                    else:
                        # For other columns, store the text content
                        combatant_state[key] = item.text() if item else ""
                
                # Ensure 'type' is saved correctly (prioritize UserRole, then column, then default)
                combatant_state["type"] = combatant_state.pop("user_role_type", combatant_state.get("type", "manual"))
    
                # Retrieve and save the detailed combatant data stored in self.combatant_manager.combatants_by_id dictionary
                if row in self.combatant_manager.combatants_by_id:
                    # Store the associated data object/dictionary
                    # Note: Ensure this data is serializable (e.g., dict, list, primitives)
                    # If it's a complex object, you might need a custom serialization method
                    combatant_state["data"] = self.combatant_manager.combatants_by_id[row] 
                
                # Add the combatant's state to the main state list
                state["combatants"].append(combatant_state)
                
            # Return the complete state dictionary
            return state
        def restore_state(self, state):
            """Restore the combat tracker state from a saved state dictionary."""
            # Check if the provided state is valid (not None and is a dictionary)
            if not state or not isinstance(state, dict):
                print("[CombatTracker] Restore Error: Invalid or missing state data.")
                return # Exit if state is invalid
    
            print("[CombatTracker] Restoring combat tracker state...")
            # Block signals during restoration to prevent unwanted side effects
            self.initiative_table.blockSignals(True)
            
            try:
                # --- Clear Existing State ---
                self.initiative_table.setRowCount(0) # Clear all rows from the table
                self.death_saves.clear()            # Clear tracked death saves
                self.concentrating.clear()          # Clear tracked concentration
                self.combatant_manager.combatants_by_id.clear()             # Clear stored combatant data
                
                # --- Restore Basic Combat Info ---
                self.current_round = state.get("round", 1)
                self.round_spin.setValue(self.current_round) # Update UI spinner
                
                # Restore current turn, ensuring it's within bounds of restored combatants later
                self._current_turn = state.get("turn", 0) 
                
                self.combat_time = state.get("elapsed_time", 0)
                # Update timer display immediately (will show 00:00:00 if time is 0)
                hours = self.combat_time // 3600
                minutes = (self.combat_time % 3600) // 60
                seconds = self.combat_time % 60
                self.timer_label.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
                # Reset timer button state (assume stopped on restore)
                if self.timer.isActive():
                    self.timer.stop()
                self.timer_button.setText("Start") 
                
                # Restore game time display based on restored round
                self._update_game_time()
    
                # --- Restore Tracking Dictionaries ---
                # Restore death saves - keys (row indices) might need remapping if table structure changes significantly
                self.death_saves = state.get("death_saves", {}) 
                # Restore concentration - convert list back to set
                self.concentrating = set(state.get("concentrating", [])) 
    
                # --- Restore Combatants ---
                restored_combatants_list = state.get("combatants", [])
                for idx, combatant_state in enumerate(restored_combatants_list):
                    # Insert a new row for each combatant
                    row = self.initiative_table.rowCount()
                    self.initiative_table.insertRow(row)
                    
                    # Restore detailed combatant data if it exists
                    if "data" in combatant_state:
                        self.combatant_manager.combatants_by_id[row] = combatant_state["data"]
                        # If it's a monster, try to assign a unique ID
                        if combatant_state.get("type") == "monster":
                             # Create a unique ID for this monster instance
                             monster_id = self.combatant_manager.monster_id_counter
                             self.combatant_manager.monster_id_counter += 1
                             # Store the ID with the name item's UserRole + 2
                             # We create the name item below
                             
                    # Determine combatant type (use saved 'type' field)
                    combatant_type = combatant_state.get("type", "manual") # Default to manual if missing
    
                    # --- Create and set items for each column ---
                    # Column 0: Name
                    name_item = QTableWidgetItem(combatant_state.get("name", f"Combatant {row+1}"))
                    name_item.setData(Qt.UserRole, combatant_type) # Store type in UserRole
                    # Assign monster ID if applicable
                    if combatant_type == "monster" and "data" in combatant_state:
                        name_item.setData(Qt.UserRole + 2, monster_id) # Store the generated monster ID
                    name_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
                    self.initiative_table.setItem(row, 0, name_item)
                    
                    # Column 1: Initiative
                    init_item = QTableWidgetItem(str(combatant_state.get("initiative", "0")))
                    init_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
                    self.initiative_table.setItem(row, 1, init_item)
                    
                    # Column 2: Current HP
                    hp_item = QTableWidgetItem(str(combatant_state.get("hp", "1")))
                    hp_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
                    self.initiative_table.setItem(row, 2, hp_item)
                    
                    # Column 3: Max HP
                    # Use saved max_hp, fallback to current hp if max_hp is missing/invalid
                    max_hp_val = combatant_state.get("max_hp", combatant_state.get("hp", "1")) 
                    # Ensure max_hp is at least current hp if both are numbers
                    try:
                        current_hp_int = int(hp_item.text())
                        max_hp_int = int(str(max_hp_val)) # Convert to string first for safety
                        if max_hp_int < current_hp_int:
                             max_hp_val = hp_item.text() # Set max HP to current HP if inconsistent
                    except ValueError:
                         pass # Ignore conversion errors, use the value as is
                    max_hp_item = QTableWidgetItem(str(max_hp_val))
                    max_hp_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
                    self.initiative_table.setItem(row, 3, max_hp_item)
                    
                    # Column 4: AC
                    ac_item = QTableWidgetItem(str(combatant_state.get("ac", "10")))
                    ac_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
                    self.initiative_table.setItem(row, 4, ac_item)
                    
                    # Column 5: Status
                    status_item = QTableWidgetItem(combatant_state.get("status", ""))
                    status_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
                    self.initiative_table.setItem(row, 5, status_item)
                    
                    # Column 6: Concentration (Checkbox)
                    conc_item = QTableWidgetItem()
                    conc_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
                    # Set check state based on saved boolean value
                    is_concentrating = combatant_state.get("concentration", False)
                    conc_item.setCheckState(Qt.Checked if is_concentrating else Qt.Unchecked)
                    self.initiative_table.setItem(row, 6, conc_item)
                    
                    # Column 7: Type (Read-only display, actual type stored in Name item UserRole)
                    type_item = QTableWidgetItem(combatant_type)
                    type_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled) # Generally not editable directly
                    self.initiative_table.setItem(row, 7, type_item)
    
                # Adjust current_turn if it's out of bounds after restoring
                if self._current_turn >= self.initiative_table.rowCount():
                    self._current_turn = 0 if self.initiative_table.rowCount() > 0 else -1
                
                # --- Final Steps ---
                # Re-apply highlighting based on the restored current turn
                self.previous_turn = -1 # Reset previous turn before updating highlight
                self._update_highlight()
                
                # Optional: Re-sort the table based on restored initiative values
                # self._sort_initiative() # Might be desired, but could change turn order if initiatives were edited before save
    
                # Optional: Fix any inconsistencies in types (should be less needed now)
                # self._fix_missing_types()
                
                print(f"[CombatTracker] State restoration complete. {self.initiative_table.rowCount()} combatants restored.")
    
            except Exception as e:
                # Catch any unexpected errors during restoration
                print(f"[CombatTracker] CRITICAL ERROR during state restoration: {e}")
                import traceback
                traceback.print_exc()
                # Optionally, clear the tracker completely to avoid a corrupted state
                # self._reset_combat() 
                QMessageBox.critical(self, "Restore Error", f"Failed to restore combat state: {e}")
            finally:
                # ALWAYS unblock signals, even if an error occurred
                self.initiative_table.blockSignals(False)
                # Force UI refresh after restoration
                self.initiative_table.viewport().update()
                QApplication.processEvents()
        def roll_dice(self, dice_formula):
            """Roll dice based on a formula like "3d8+4" or "2d6-1" """
            print(f"[CombatTracker] Rolling dice formula: {dice_formula}")
            if not dice_formula or not isinstance(dice_formula, str):
                print("[CombatTracker] Invalid dice formula")
                return 10
                
            # Parse the dice formula
            dice_match = re.search(r'(\d+)d(\d+)([+-]\d+)?', dice_formula)
            if not dice_match:
                print(f"[CombatTracker] Could not parse dice formula: {dice_formula}")
                return 10
                
            try:
                # Extract dice components
                count = int(dice_match.group(1))
                sides = int(dice_match.group(2))
                modifier = 0
                if dice_match.group(3):
                    modifier = int(dice_match.group(3))
                    
                # Roll the dice
                rolls = [random.randint(1, sides) for _ in range(count)]
                total = sum(rolls) + modifier
                print(f"[CombatTracker] Dice rolls: {rolls}, modifier: {modifier}, total: {total}")
                return max(1, total)  # Ensure at least 1 HP
            except (ValueError, TypeError, IndexError) as e:
                print(f"[CombatTracker] Error rolling dice: {e}")
                return 10
        def extract_dice_formula(self, hp_value):
            """Extract a dice formula from various HP value formats"""
            dice_formula = None
            
            if isinstance(hp_value, dict) and 'hit_dice' in hp_value:
                dice_formula = hp_value['hit_dice']
                print(f"[CombatTracker] Found hit_dice in dict: {dice_formula}")
            elif isinstance(hp_value, str):
                # Try to extract formula from string like "45 (6d10+12)"
                match = re.search(r'\(\s*([0-9d+\-\s]+)\s*\)', hp_value)
                if match:
                    # Remove any spaces from the formula before processing
                    dice_formula = re.sub(r'\s+', '', match.group(1))
                    print(f"[CombatTracker] Extracted dice formula from parentheses: {dice_formula}")
                # If the string itself is a dice formula
                elif re.match(r'^\d+d\d+([+-]\d+)?$', hp_value):
                    dice_formula = hp_value
                    print(f"[CombatTracker] String is directly a dice formula: {dice_formula}")
                    
            return dice_formula
    
            """Add a monster from monster panel to the tracker"""
            if not monster_data:
                return -1
                
            # Block signals to prevent race conditions during adding
            self.initiative_table.blockSignals(True)
            
            try:
                # Diagnostic: Log information about this monster
                monster_name = "Unknown"
                if isinstance(monster_data, dict) and 'name' in monster_data:
                    monster_name = monster_data['name']
                elif hasattr(monster_data, 'name'):
                    monster_name = monster_data.name
                    
                print(f"[CombatTracker] Adding monster '{monster_name}' (type: {type(monster_data)})")
                
                # Validate monster data to prevent ability mixing
                try:
                    # Import the validator
                    from app.core.improved_combat_resolver import ImprovedCombatResolver
                    
                    # Only validate if it's a dictionary (proper format)
                    if isinstance(monster_data, dict):
                        # Check if this monster has already been validated
                        if "_validation_id" in monster_data:
                            # Already validated, skip further validation to preserve abilities
                            print(f"[CombatTracker] Monster {monster_name} already validated with ID {monster_data['_validation_id']}")
                            validated_monster_data = monster_data
                        else:
                            # Validate monster data
                            print(f"[CombatTracker] Validating monster data for '{monster_name}'")
                            validated_monster_data = ImprovedCombatResolver.validate_monster_data(monster_data)
                        
                        # Check if validation changed anything
                        actions_before = len(monster_data.get('actions', [])) if 'actions' in monster_data else 0
                        actions_after = len(validated_monster_data.get('actions', [])) if 'actions' in validated_monster_data else 0
                        
                        traits_before = len(monster_data.get('traits', [])) if 'traits' in monster_data else 0
                        traits_after = len(validated_monster_data.get('traits', [])) if 'traits' in validated_monster_data else 0
                        
                        if actions_before != actions_after or traits_before != traits_after:
                            print(f"[CombatTracker] Validation modified abilities for {monster_name}")
                            print(f"[CombatTracker] Actions: {actions_before} -> {actions_after}, Traits: {traits_before} -> {traits_after}")
                            
                            # If validation retained most abilities, use the validated data
                            # Otherwise, keep the original to avoid losing legitimate abilities
                            if actions_after >= actions_before * 0.5 and traits_after >= traits_before * 0.5:
                                monster_data = validated_monster_data
                                print(f"[CombatTracker] Using validated monster data (most abilities retained)")
                            else:
                                print(f"[CombatTracker] Validation removed too many abilities, keeping original data")
                                # Still use the validation ID for consistency
                                if "_validation_id" in validated_monster_data:
                                    monster_data["_validation_id"] = validated_monster_data["_validation_id"]
                except Exception as e:
                    # If validation fails, log the error but continue with the original data
                    print(f"[CombatTracker] Error validating monster data: {e}")
                    # Don't block combat addition due to validation error
                
                # Helper function to get attribute from either dict or object
                def get_attr(obj, attr, default=None, alt_attrs=None):
                    """Get attribute from object or dict, trying alternate attribute names if specified"""
                    alt_attrs = alt_attrs or []
                    result = default
                    
                    try:
                        # Implementation remains the same
                        # Just a helper function to retrieve attributes from different object types
                        if isinstance(obj, dict):
                            if attr in obj:
                                return obj[attr]
                            for alt_attr in alt_attrs:
                                if alt_attr in obj:
                                    return obj[alt_attr]
                            # Additional checks for nested structures, etc.
                            # ...
                        else:
                            if hasattr(obj, attr):
                                return getattr(obj, attr)
                            for alt_attr in alt_attrs:
                                if hasattr(obj, alt_attr):
                                    return getattr(obj, alt_attr)
                            # Additional checks for object attributes, etc.
                            # ...
                        
                        return default
                    except Exception as e:
                        print(f"[CombatTracker] Error in get_attr({attr}): {e}")
                        return default
                    
                # Get monster name
                name = get_attr(monster_data, "name", "Unknown Monster")
                
                # Generate a unique ID for this monster instance using the correct counter attribute
                monster_id = self.combatant_manager.monster_id_counter
                self.combatant_manager.monster_id_counter += 1
                
                # Get a reasonable initiative modifier from DEX
                dex = get_attr(monster_data, "dexterity", 10, ["dex", "DEX"])
                init_mod = (dex - 10) // 2
                
                # Roll initiative
                initiative_roll = random.randint(1, 20) + init_mod
                
                # Get monster HP data and AC in various formats
                hp_value = get_attr(monster_data, "hp", 10, ["hit_points", "hitPoints", "hit_points_roll", "hit_dice"])
                print(f"[CombatTracker] Retrieved HP value: {hp_value} (type: {type(hp_value)})")
                
                # Calculate average HP (for Max HP display)
                max_hp = 0
                if isinstance(hp_value, int):
                    max_hp = hp_value
                elif isinstance(hp_value, dict) and 'average' in hp_value:
                    max_hp = int(hp_value['average'])
                elif isinstance(hp_value, str):
                    # Try to extract average value from string like "45 (6d10+12)"
                    match = re.match(r'(\d+)\s*\(', hp_value)
                    if match:
                        max_hp = int(match.group(1))
                    elif hp_value.isdigit():
                        max_hp = int(hp_value)
                
                if max_hp <= 0:
                    max_hp = 10
                    
                print(f"[CombatTracker] Max HP: {max_hp}")
                
                # IMPORTANT PART: EXTRACT DICE FORMULA AND ROLL HP
                dice_formula = self.extract_dice_formula(hp_value)
                
                # ALWAYS ROLL RANDOM HP
                if dice_formula:
                    # Roll random HP using the dice formula
                    hp = self.roll_dice(dice_formula)
                    print(f"[CombatTracker] RANDOM HP ROLL: {hp} using formula {dice_formula}")
                else:
                    # If no dice formula, create a better one based on monster CR and average HP
                    # For dragons and high-HP monsters, a better approximation would be:
                    # d12 for big monsters, d10 for medium monsters, d8 for small monsters
                    
                    # Determine the creature size based on max HP
                    if max_hp > 200:  # Large/Huge creatures like dragons
                        die_size = 12
                        num_dice = max(1, int(max_hp * 0.75 / (die_size/2 + 0.5)))  # Scale dice count to match HP
                    elif max_hp > 100:  # Medium creatures
                        die_size = 10
                        num_dice = max(1, int(max_hp * 0.8 / (die_size/2 + 0.5)))
                    else:  # Small creatures
                        die_size = 8
                        num_dice = max(1, int(max_hp * 0.85 / (die_size/2 + 0.5)))
                    
                    # Add a small modifier to account for Constitution
                    modifier = int(max_hp * 0.1)
                    estimated_formula = f"{num_dice}d{die_size}+{modifier}"
                    hp = self.roll_dice(estimated_formula)
                    print(f"[CombatTracker] NO FORMULA FOUND - Created estimated formula {estimated_formula} and rolled: {hp}")
                    
                    # Limit HP to a reasonable range (50%-125% of average)
                    min_hp = int(max_hp * 0.5)
                    max_possible_hp = int(max_hp * 1.25)
                    hp = max(min_hp, min(hp, max_possible_hp))
                    print(f"[CombatTracker] Adjusted HP to {hp} (limited to {min_hp}-{max_possible_hp})")
                
                # Set max_hp to the randomly rolled hp value so they match
                max_hp = hp
                
                ac = get_attr(monster_data, "ac", 10, ["armor_class", "armorClass", "AC"])
                print(f"[CombatTracker] Retrieved AC value: {ac}")
                
                # Save monster stats for later verification
                monster_stats = {
                    "id": monster_id,
                    "name": name,
                    "hp": hp,
                    "max_hp": max_hp,
                    "ac": ac
                }
                
                # Add to tracker with our randomly rolled HP
                row = self.combatant_manager.add_combatant(name, initiative_roll, hp, max_hp, ac, "monster", monster_id)
                
                # Ensure row is valid, default to -1 if None
                if row is None:
                    row = -1
                
                # Store monster data for future reference
                if row >= 0:
                    self.combatant_manager.combatants_by_id[row] = monster_data
                    
                # Force a refresh of the entire table
                self.initiative_table.viewport().update()
                QApplication.processEvents()
                        
                # Make absolutely sure this monster's values are correctly set (with delay)
                QTimer.singleShot(50, lambda: self._verify_monster_stats(monster_stats))
                        
                # Log to combat log
                self._log_combat_action("Setup", "DM", "added monster", name, f"(Init: {initiative_roll}, HP: {hp}/{max_hp})")
                
                return row
                
            finally:
                # Always unblock signals even if there's an error
                self.initiative_table.blockSignals(False)
                
            """Double-check that monster stats are properly set after adding and sorting"""
            monster_id = monster_stats["id"]
            name = monster_stats["name"]
            hp = monster_stats["hp"]
            max_hp = monster_stats["max_hp"]
            ac = monster_stats["ac"]
            
            # Find the current row for this monster
            row = self._find_monster_by_id(monster_id)
            if row < 0:
                print(f"[CombatTracker] Warning: Cannot verify stats for monster {name} (ID {monster_id}) - not found")
                return
                
            # Verify all stats are correctly set
            hp_item = self.initiative_table.item(row, 2)
            max_hp_item = self.initiative_table.item(row, 3)
            ac_item = self.initiative_table.item(row, 4)
            
            # Prepare values as strings
            hp_str = str(hp) if hp is not None else "10"
            max_hp_str = str(max_hp) if max_hp is not None else "10"
            ac_str = str(ac) if ac is not None else "10"
            
            # Check and fix values if needed
            changes_made = False
            
            # Check HP
            if not hp_item or hp_item.text() != hp_str:
                print(f"[CombatTracker] Fixing HP for {name} (ID {monster_id}) at row {row}: setting to {hp_str}")
                new_hp_item = QTableWidgetItem(hp_str)
                new_hp_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
                self.initiative_table.setItem(row, 2, new_hp_item)
                changes_made = True
                
            # Check Max HP
            if not max_hp_item or max_hp_item.text() != max_hp_str:
                print(f"[CombatTracker] Fixing Max HP for {name} (ID {monster_id}) at row {row}: setting to {max_hp_str}")
                new_max_hp_item = QTableWidgetItem(max_hp_str)
                new_max_hp_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
                self.initiative_table.setItem(row, 3, new_max_hp_item)
                changes_made = True
                
            # Check AC
            if not ac_item or ac_item.text() != ac_str:
                print(f"[CombatTracker] Fixing AC for {name} (ID {monster_id}) at row {row}: setting to {ac_str}")
                new_ac_item = QTableWidgetItem(ac_str)
                new_ac_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
                self.initiative_table.setItem(row, 4, new_ac_item)
                changes_made = True
                
            # If any changes were made, update the table
            if changes_made:
                self.initiative_table.viewport().update()
                print(f"[CombatTracker] Stats verified and fixed for {name} (ID {monster_id})")
            else:
                print(f"[CombatTracker] All stats correct for {name} (ID {monster_id})")
        def _apply_damage(self, is_healing=False):
            """Apply damage or healing to selected combatants"""
            # Get selected rows
            selected_rows = set(index.row() for index in self.initiative_table.selectedIndexes())
            if not selected_rows:
                return
                
            # Get name of first selected combatant for dialog
            first_row = min(selected_rows)
            name_item = self.initiative_table.item(first_row, 0)
            target_name = name_item.text() if name_item else "combatant"
            
            # Open damage/healing dialog
            dialog = DamageDialog(self, is_healing=is_healing)
            if dialog.exec_():
                amount = dialog.get_amount()
                
                # Apply to each selected row
                for row in selected_rows:
                    hp_item = self.initiative_table.item(row, 2)  # HP is now column 2
                    max_hp_item = self.initiative_table.item(row, 3)  # Max HP is now column 3
                    if not hp_item or not max_hp_item:
                        continue
                        
                    name_item = self.initiative_table.item(row, 0)
                    if not name_item:
                        continue
                        
                    combatant_name = name_item.text()
                    
                    try:
                        # Safely get current HP
                        hp_text = hp_item.text().strip()
                        current_hp = int(hp_text) if hp_text else 0
                        
                        # Get max HP
                        max_hp_text = max_hp_item.text().strip()
                        max_hp = int(max_hp_text) if max_hp_text else 999
                        
                        if is_healing:
                            new_hp = current_hp + amount
                            if max_hp > 0:  # Don't exceed max HP
                                new_hp = min(new_hp, max_hp)
                            
                            # Log healing action
                            self._log_combat_action(
                                "Healing", 
                                "DM", 
                                "healed", 
                                combatant_name, 
                                f"{amount} HP (to {new_hp})"
                            )
                        else:
                            new_hp = current_hp - amount
                            
                            # Check concentration if damaged
                            if row in self.concentrating and amount > 0:
                                self._check_concentration(row, amount)
                            
                            # Log damage action
                            self._log_combat_action(
                                "Damage", 
                                "DM", 
                                "dealt damage to", 
                                combatant_name, 
                                f"{amount} damage (to {new_hp})"
                            )
                        
                        # Update HP
                        hp_item.setText(str(new_hp))
                        
                        # Check for unconsciousness/death
                        if new_hp <= 0:
                            # Mark as unconscious - add to existing statuses
                            status_item = self.initiative_table.item(row, 5)  # Status is now column 5
                            if status_item:
                                current_statuses = []
                                if status_item.text():
                                    current_statuses = [s.strip() for s in status_item.text().split(',')]
                                
                                # Only add if not already present
                                if "Unconscious" not in current_statuses:
                                    current_statuses.append("Unconscious")
                                    status_item.setText(', '.join(current_statuses))
                                    
                                    # Log status change
                                    self._log_combat_action(
                                        "Status Effect", 
                                        "DM", 
                                        "applied status", 
                                        combatant_name, 
                                        "Unconscious"
                                    )
                            
                            # Check if player character (has max HP) for death saves
                            if max_hp > 0:
                                # Set up death saves tracking if not already
                                if row not in self.death_saves:
                                    self.death_saves[row] = {"successes": 0, "failures": 0}
                    except ValueError:
                        # Handle invalid HP value
                        pass
        def _manage_death_saves(self, row):
            """Manage death saving throws for a character"""
            current_saves = self.death_saves.get(row, {"successes": 0, "failures": 0})
            dialog = DeathSavesDialog(self, current_saves)
            
            if dialog.exec_():
                dialog_result = dialog.get_saves()
                self.death_saves[row] = dialog_result
                saves = self.death_saves[row]
                
                name_item = self.initiative_table.item(row, 0)
                if name_item:
                    name = name_item.text()
                    
                    # Log death save changes
                    if saves:
                        successes = saves.get("successes", 0)
                        failures = saves.get("failures", 0)
                        
                        if successes >= 3:
                            self._log_combat_action(
                                "Death Save", 
                                name, 
                                "stabilized", 
                                result=f"{successes} successes"
                            )
                            QMessageBox.information(self, "Stabilized", 
                                f"{name} has stabilized!")
                            self.death_saves.pop(row)
                            
                            # Update status - add Stable, remove Unconscious
                            status_item = self.initiative_table.item(row, 5)  # Status is now column 5
                            if status_item:
                                current_statuses = []
                                if status_item.text():
                                    current_statuses = [s.strip() for s in status_item.text().split(',')]
                                
                                # Remove Unconscious if present
                                if "Unconscious" in current_statuses:
                                    current_statuses.remove("Unconscious")
                                
                                # Add Stable if not present
                                if "Stable" not in current_statuses:
                                    current_statuses.append("Stable")
                                    
                                status_item.setText(', '.join(current_statuses))
                                
                        elif failures >= 3:
                            self._log_combat_action(
                                "Death Save", 
                                name, 
                                "failed death saves", 
                                result=f"{failures} failures"
                            )
                            QMessageBox.warning(self, "Death", 
                                f"{name} has died!")
                            self.death_saves.pop(row)
                            
                            # Update status - add Dead, remove Unconscious
                            status_item = self.initiative_table.item(row, 5)  # Status is now column 5
                            if status_item:
                                current_statuses = []
                                if status_item.text():
                                    current_statuses = [s.strip() for s in status_item.text().split(',')]
                                
                                # Remove Unconscious if present
                                if "Unconscious" in current_statuses:
                                    current_statuses.remove("Unconscious")
                                
                                # Add Dead if not present
                                if "Dead" not in current_statuses:
                                    current_statuses.append("Dead")
                                    
                                status_item.setText(', '.join(current_statuses))
                        else:
                            self._log_combat_action(
                                "Death Save", 
                                name, 
                                "updated death saves", 
                                result=f"{successes} successes, {failures} failures"
                            )
    
                def _prompt_saving_throw(self):
                    """Prompt user for saving throw details and apply to selected combatants."""
                    # Get selected rows first
                    selected_rows = sorted(list(set(index.row() for index in self.initiative_table.selectedIndexes())))
    
                    if not selected_rows:
                        QMessageBox.warning(self, "Selection Error", "Please select one or more combatants to apply the saving throw.")
                        return
    
            # 1. Prompt for Ability
            ability_name, ok1 = QInputDialog.getItem(self, "Select Saving Throw Ability",
                                                     "Ability:", ABILITIES, 0, False)
            if not ok1 or not ability_name:
                return # User cancelled
    
            # 2. Prompt for DC
            dc, ok2 = QInputDialog.getInt(self, "Enter Saving Throw DC",
                                          "DC:", 10, 1, 30, 1)
            if not ok2:
                return # User cancelled
    
            # 3. Process each selected combatant
            for row in selected_rows:
                name_item = self.initiative_table.item(row, 0)
                if not name_item:
                    continue
                combatant_name = name_item.text()
    
                combatant_data = self.combatant_manager.get_combatant_data(row)
                save_bonus = self._get_save_bonus(combatant_data, ability_name)
    
                # Show the dialog for this combatant
                dialog = SavingThrowDialog(combatant_name, ability_name, save_bonus, dc, self)
    
                if dialog.exec_(): # User confirmed roll in the dialog
                    roll = dialog.final_roll
                    total_save = roll + save_bonus # Recalculate total for logging clarity
                    succeeded = dialog.succeeded # Use the outcome stored by the dialog
    
                    outcome_text = "succeeded on" if succeeded else "failed"
                    # Log the action
                    self._log_combat_action(
                        "Saving Throw", # New category
                        combatant_name,
                        f"{outcome_text} DC {dc} {ability_name} save", # Describe action
                        target=None, # Save is against an effect/DC
                        result=f"(Rolled {roll}, Total: {total_save})" # Show roll and total
                    )
                    # Future: Apply effects based on failure (e.g., status condition)
                    # if not succeeded:
                    #     # Example: apply 'Burning' status on failed DEX save vs Fire Breath
                    #     if ability_name == "Dexterity" and dc > 10: # Simplistic check
                    #          self._add_status("Burning", row=row) # Need _add_status to accept row
    
                else: # User cancelled the roll dialog for this specific combatant
                     self._log_combat_action(
                        "Saving Throw",
                        combatant_name,
                        f"DC {dc} {ability_name} save cancelled",
                        target=None, result=None
                     )
                     # Loop continues to the next selected combatant
    
    
            def _check_concentration(self, row, damage):
                """Check if a combatant needs to make a concentration save, get bonus, and log correctly."""
                # Check if the combatant in this row is actually concentrating
                concentration_item = self.initiative_table.item(row, 6) # Concentration is column 6
                if not concentration_item or concentration_item.checkState() != Qt.Checked:
                    # Also check our internal tracking set, though the checkbox should be the source of truth
                    if row not in self.concentrating:
                     return # Not concentrating, no check needed
    
            # Get combatant name
            name_item = self.initiative_table.item(row, 0)
            if not name_item:
                return
            combatant_name = name_item.text()
    
            # --- Get Combatant Data to find CON Save Bonus ---
            combatant_data = self.combatant_manager.get_combatant_data(row)
            con_save_bonus = 0 # Default bonus
            if combatant_data:
                # Try to get Constitution score and calculate modifier
                con_score_str = get_attr(combatant_data, 'constitution', None)
                if con_score_str is not None:
                    try:
                        con_score = int(con_score_str)
                        con_save_bonus = (con_score - 10) // 2
                        # TODO: Add proficiency bonus if proficient in CON saves?
                        # Need proficiency bonus and save proficiencies from combatant_data
                    except (ValueError, TypeError):
                        print(f"[CombatTracker] Warning: Could not parse CON score '{con_score_str}' for {combatant_name}")
                else:
                     # Maybe the bonus is stored directly? (Less likely based on SRD format)
                     con_save_bonus_str = get_attr(combatant_data, 'constitution_save', '0')
                     try:
                          con_save_bonus = int(con_save_bonus_str)
                     except (ValueError, TypeError):
                          print(f"[CombatTracker] Warning: Could not parse CON save bonus '{con_save_bonus_str}' for {combatant_name}")
    
            # Calculate DC for concentration check
            dc = max(10, damage // 2)
    
            # --- Corrected call to ConcentrationDialog ---
            # Pass combatant_name, con_save_bonus, damage
            dialog = ConcentrationDialog(combatant_name, con_save_bonus, damage, self)
    
            if dialog.exec_():
                # --- Retrieve roll using the new final_roll attribute ---
                save_roll = dialog.final_roll
                total_save = save_roll + con_save_bonus # Calculate total here
                passed = total_save >= dc
    
                # Log result of concentration check using the correct roll
                outcome = "passed" if passed else "failed"
                self._log_combat_action(
                    "Concentration Check",
                    combatant_name,
                    f"{outcome} DC {dc} concentration check", # Put DC in action text
                    target=None, # No target for a self-save
                    result=f"(Rolled {save_roll}, Total: {total_save})" # Show roll and total
                )
    
                # If failed, update concentration state and log
                if not passed:
                    if concentration_item:
                        concentration_item.setCheckState(Qt.Unchecked)
    
                    # Update internal tracking set
                    if row in self.concentrating:
                        self.concentrating.remove(row)
    
                    # Log concentration broken
                    self._log_combat_action(
                        "Effect Ended",
                        combatant_name,
                        "lost concentration",
                        target=None, result=None
                    )
            else:
                 # User cancelled the dialog
                 self._log_combat_action(
                      "Concentration Check",
                      combatant_name,
                      f"DC {dc} concentration check cancelled",
                      target=None, result=None
                 )
        def _cleanup_dead_combatants(self):
            """Iterate through the table and remove combatants marked as Dead or Fled."""
            rows_to_remove = []
            for row in range(self.initiative_table.rowCount()):
                status_item = self.initiative_table.item(row, 5) # Status column
                if status_item:
                    # Check status case-insensitively
                    statuses = [s.strip().lower() for s in status_item.text().split(',')]
                    if "dead" in statuses or "fled" in statuses:
                        rows_to_remove.append(row)
    
            if not rows_to_remove:
                print("[CombatTracker] Cleanup: No dead/fled combatants found.")
                return # Nothing to remove
    
            print(f"[CombatTracker] Cleanup: Removing {len(rows_to_remove)} dead/fled combatants.")
            
            # Block signals during row removal for safety
            self.initiative_table.blockSignals(True)
            turn_adjusted = False
            try:
                # --- Remove Rows Phase --- 
                for row in sorted(rows_to_remove, reverse=True):
                    # Log removal before actually removing
                    name_item = self.initiative_table.item(row, 0)
                    name = name_item.text() if name_item else f"Row {row}"
                    print(f"[CombatTracker] Cleanup: Removing row {row} ({name})")
                    self._log_combat_action("Setup", "DM", "removed dead/fled combatant", name)
    
                    self.initiative_table.removeRow(row)
                    
                    # --- State Adjustment Phase (after each removal) ---
                    # Adjust current turn index if it was affected by the removal
                    if row < self.current_turn:
                        self.current_turn -= 1
                        turn_adjusted = True
                        print(f"[CombatTracker] Cleanup: Adjusted current_turn to {self.current_turn} (was < {row})")
                    elif row == self.current_turn:
                        # If removing the current turn, reset it (e.g., to 0 or -1)
                        self.current_turn = 0 if self.initiative_table.rowCount() > 0 else -1
                        turn_adjusted = True
                        print(f"[CombatTracker] Cleanup: Reset current_turn to {self.current_turn} (was == {row})")
    
                    # Clean up tracking
                    self.death_saves.pop(row, None)
                    self.concentrating.discard(row) # Use discard for sets
                    self.combatant_manager.combatants_by_id.pop(row, None) # Clean up combatants dict
                    
            finally:
                self.initiative_table.blockSignals(False) # Unblock after removals
                print("[CombatTracker] Cleanup: Finished removing rows.")
                
            # --- Re-indexing Phase (after ALL removals) --- 
            # Only reindex if rows were actually removed
            if rows_to_remove:
                print("[CombatTracker] Cleanup: Re-indexing remaining combatant data.")
                new_combatants = {}
                new_concentrating = set()
                new_death_saves = {}
                
                # Map old rows to new rows efficiently
                current_row_count = self.initiative_table.rowCount()
                old_to_new_map = {}
                original_indices = sorted(self.combatant_manager.combatants_by_id.keys()) # Get keys before modifying
                
                current_new_row = 0
                for old_row in range(max(original_indices) + 1): # Iterate through potential old indices
                    if old_row not in rows_to_remove and old_row in original_indices:
                        old_to_new_map[old_row] = current_new_row
                        current_new_row += 1
    
                # Apply the mapping
                for old_row, new_row in old_to_new_map.items():
                    if old_row in self.combatant_manager.combatants_by_id:
                        new_combatants[new_row] = self.combatant_manager.combatants_by_id[old_row]
                    if old_row in self.concentrating:
                        new_concentrating.add(new_row)
                    if old_row in self.death_saves:
                        new_death_saves[new_row] = self.death_saves[old_row]
                         
                self.combatant_manager.combatants_by_id = new_combatants
                self.concentrating = new_concentrating
                self.death_saves = new_death_saves
                print(f"[CombatTracker] Cleanup: Re-indexing complete. New combatants dict size: {len(self.combatant_manager.combatants_by_id)}")
                
            # --- Final UI Update Phase --- 
            # Update highlight ONLY if turn was adjusted OR the table is now empty
            if turn_adjusted or self.initiative_table.rowCount() == 0:
                print("[CombatTracker] Cleanup: Updating highlight.")
                self._update_highlight()
                
            # Final UI refresh
            print("[CombatTracker] Cleanup: Refreshing viewport.")
            self.initiative_table.viewport().update()
            QApplication.processEvents()
            print("[CombatTracker] Cleanup: Finished.")
        def _view_combatant_details(self, row, col=0): # Added col default
            """Show the details for the combatant at the given row"""
            # Ensure row is valid
            if row < 0 or row >= self.initiative_table.rowCount():
                print(f"[Combat Tracker] Invalid row provided to _view_combatant_details: {row}")
                return
                
            name_item = self.initiative_table.item(row, 0) # Name is in column 0
            if not name_item:
                print(f"[Combat Tracker] No name item found at row {row}")
                return
                
            combatant_name = name_item.text()
            # Get type from UserRole data first
            combatant_type = name_item.data(Qt.UserRole)
            
            # If type is None or empty, try to get it from the type column (index 7)
            if not combatant_type:
                 type_item = self.initiative_table.item(row, 7) 
                 if type_item:
                     combatant_type = type_item.text().lower()
                     # Store it back in the name item for future use
                     name_item.setData(Qt.UserRole, combatant_type)
                     print(f"[Combat Tracker] Inferred type '{combatant_type}' for {combatant_name} from column 7")
                
            # If still None, default to custom
            if not combatant_type:
                combatant_type = "custom"
                name_item.setData(Qt.UserRole, combatant_type) # Store default
                print(f"[Combat Tracker] Defaulting type to 'custom' for {combatant_name}")
                
            print(f"[Combat Tracker] Viewing details for {combatant_type} '{combatant_name}'")
            
            panel_manager = getattr(self.app_state, 'panel_manager', None)
            if not panel_manager:
                 print("[Combat Tracker] No panel_manager found in app_state, falling back to dialog.")
                 self._show_combatant_dialog(row, combatant_name, combatant_type)
                 return
    
            # Redirect to appropriate panel based on combatant type
            panel_found = False
            if combatant_type == "monster":
                monster_panel = self.get_panel("monster")
                if monster_panel:
                    panel_manager.show_panel("monster")
                    # Now search and select the monster
                    result = monster_panel.search_and_select_monster(combatant_name)
                    panel_found = True
                    if not result:
                        print(f"[Combat Tracker] Monster '{combatant_name}' not found in monster browser. Showing dialog.")
                        self._show_combatant_dialog(row, combatant_name, combatant_type)
                else:
                     print("[Combat Tracker] Monster panel not found. Showing dialog.")
                     self._show_combatant_dialog(row, combatant_name, combatant_type)
                     panel_found = True # Dialog shown, counts as handled
                     
            elif combatant_type == "character":
                character_panel = self.get_panel("player_character")
                if character_panel:
                    panel_manager.show_panel("player_character")
                    # Now search and select the character
                    result = character_panel.select_character_by_name(combatant_name)
                    panel_found = True
                    if not result:
                        print(f"[Combat Tracker] Character '{combatant_name}' not found in character panel. Showing dialog.")
                        self._show_combatant_dialog(row, combatant_name, combatant_type)
                else:
                    print("[Combat Tracker] Character panel not found. Showing dialog.")
                    self._show_combatant_dialog(row, combatant_name, combatant_type)
                    panel_found = True # Dialog shown, counts as handled
    
            # Fallback for custom types or if panels failed
            if not panel_found:
                print(f"[Combat Tracker] Type is '{combatant_type}' or panel redirection failed. Showing dialog.")
                self._show_combatant_dialog(row, combatant_name, combatant_type)
            
            def _get_save_bonus(self, combatant_data, ability_name):
                """Calculate the saving throw bonus for a given ability."""
                if not combatant_data or not ability_name:
                    return 0
    
                ability_lower = ability_name.lower()
                bonus = 0
    
            # 1. Check for explicit save bonus (e.g., "dexterity_save")
            save_key = f"{ability_lower}_save"
            if save_key in combatant_data:
                try:
                    # Use get_attr for safe retrieval
                    bonus = int(get_attr(combatant_data, save_key, '0'))
                    # print(f"[DEBUG] Found explicit save bonus {save_key}: {bonus}") # Optional Debug
                    return bonus
                except (ValueError, TypeError):
                     print(f"[CombatTracker] Warning: Could not parse explicit save bonus '{save_key}' for {combatant_data.get('name', 'Unknown')}")
    
            # 2. If no explicit bonus, calculate from ability score
            score_key = ability_lower
            if score_key in combatant_data:
                 # Use get_attr for safe retrieval
                 score_str = get_attr(combatant_data, score_key, None)
                 if score_str is not None:
                     try:
                         score = int(score_str)
                         bonus = (score - 10) // 2
                         # print(f"[DEBUG] Calculated save bonus from {score_key}={score}: {bonus}") # Optional Debug
                     except (ValueError, TypeError):
                         print(f"[CombatTracker] Warning: Could not parse ability score '{score_key}' for {combatant_data.get('name', 'Unknown')}")
                 else:
                     # Log if the key exists but the value is None or empty
                     print(f"[CombatTracker] Warning: Ability score key '{score_key}' present but value is None/empty for {combatant_data.get('name', 'Unknown')}")
            else:
                 # Log if the ability score key itself is missing
                 print(f"[CombatTracker] Warning: Ability score key '{score_key}' not found for {combatant_data.get('name', 'Unknown')}")
    
    
            # TODO: Add proficiency bonus if proficient? Requires proficiency data.
            # This depends heavily on how proficiency information is stored in combatant_data
            # prof_bonus = get_attr(combatant_data, 'proficiency_bonus', 0)
            # save_proficiencies = get_attr(combatant_data, 'proficiencies', []) # Example structure
            # is_proficient = any(p.get('proficiency', {}).get('name', '') == f"Saving Throw: {ability_name}" for p in save_proficiencies)
            # if is_proficient:
            #     try:
            #          bonus += int(prof_bonus)
            #          print(f"[DEBUG] Added proficiency bonus {prof_bonus}, total {bonus}")
            #     except (ValueError, TypeError):
            #          print(f"[CombatTracker] Warning: Could not parse proficiency bonus '{prof_bonus}'")
    
            return bonus
        def _on_selection_changed(self):
            """Handle when the selection in the initiative table changes"""
            selected_items = self.initiative_table.selectedItems()
            if not selected_items:
                # If selection is cleared, potentially clear details pane or do nothing
                # self.current_details_combatant = None
                # self._clear_details_layouts() 
                return
                
            # Get the selected row (selectedItems gives all cells in the row)
            row = selected_items[0].row()
            
            # If details pane is visible, update it with the selected combatant
            # Avoid calling _view_combatant_details directly if it causes loops
            # Store selected combatant info and call update method
            if row in self.combatant_manager.combatants_by_id:
                 self.current_details_combatant = self.combatant_manager.combatants_by_id[row]
                 name_item = self.initiative_table.item(row, 0)
                 self.current_details_type = name_item.data(Qt.UserRole) if name_item else "custom" 
            else:
                # Handle cases where there's no stored data (e.g., manually added)
                # Create temporary data from table for display
                 name_item = self.initiative_table.item(row, 0)
                 type_item = self.initiative_table.item(row, 7)
                 self.current_details_combatant = {
                     "name": name_item.text() if name_item else "Manual Entry",
                     "hp": self.initiative_table.item(row, 2).text() if self.initiative_table.item(row, 2) else "0",
                     "max_hp": self.initiative_table.item(row, 3).text() if self.initiative_table.item(row, 3) else "0",
                     "ac": self.initiative_table.item(row, 4).text() if self.initiative_table.item(row, 4) else "10",
                     "status": self.initiative_table.item(row, 5).text() if self.initiative_table.item(row, 5) else "",
                 }
                 self.current_details_type = type_item.text().lower() if type_item else "custom"
            
            if self.show_details_pane:
                 self._update_details_pane() # Update the pane content
        def closeEvent(self, event):
            # Call parent closeEvent
            super().closeEvent(event)
        def _process_resolution_ui(self, result, error):
            """Process the combat resolution result from the resolver"""
            # Import needed modules at the start
            import copy
            import gc
            import traceback
            from PySide6.QtWidgets import QApplication
            
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
                    self.app_state.combat_resolver.resolution_complete.disconnect(self._process_resolution_ui)
                    print("[CombatTracker] Successfully disconnected resolution_complete signal")
                except Exception as disconnect_error:
                    print(f"[CombatTracker] Failed to disconnect signal: {disconnect_error}")
                
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
                removed_count, update_summaries = self._apply_combat_updates(combatants_copy)
                
                # Force UI update after applying updates
                QApplication.processEvents()
                
                # Build a detailed summary for the user
                turn_count = len(log_entries)
                survivors_details = []
                casualties = []
                
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
                self.combat_log_text.append(f"<p style='color:red;'><b>Error:</b> An error occurred while processing the combat result: {str(e)}</p>")
                
                # Force garbage collection
                gc.collect()

