from app.ui.panels.base_panel import BasePanel
from app.ui.panels.combat_tracker.ui import _setup_ui
from app.ui.panels.combat_tracker.combatant_manager import CombatantManager
from app.ui.panels.combat_utils import roll_dice
from PySide6.QtCore import Qt, QEvent, QTimer, QMetaObject, Q_ARG, Slot
from PySide6.QtWidgets import QMessageBox, QApplication, QPushButton, QTableWidgetItem, QMenu, QInputDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QHeaderView, QLabel, QWidget, QTextEdit, QSplitter
from PySide6.QtGui import QAction

# Added imports for _fast_resolve_combat
import traceback
import threading
import gc
import logging

class CombatTrackerPanel(BasePanel):
    """Combat Tracker panel built with modular UI functions."""

    # Define column constants to ensure consistency
    COL_NAME = 0
    COL_INITIATIVE = 1
    COL_HP = 2
    COL_AC = 3
    COL_TYPE = 4
    COL_STATUS = 5
    
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
        """Set up the combat tracker user interface"""
        import logging
        from PySide6.QtWidgets import (QVBoxLayout, QHBoxLayout, QPushButton, 
                                      QTableWidget, QTableWidgetItem, QHeaderView,
                                      QLabel, QWidget, QTextEdit, QSplitter)
        from PySide6.QtCore import Qt, QSize
        
        # Main layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(10)
        
        # Create a splitter for the main panels
        self.main_splitter = QSplitter(Qt.Vertical)
        self.layout.addWidget(self.main_splitter)
        
        # Top section - Initiative table
        self.top_widget = QWidget()
        self.top_layout = QVBoxLayout(self.top_widget)
        self.top_layout.setContentsMargins(0, 0, 0, 0)
        
        # Initiative tracking table
        self.initiative_table = QTableWidget()
        self.initiative_table.setColumnCount(6)
        self.initiative_table.setHorizontalHeaderLabels(["Name", "Init", "HP", "AC", "Type", "Status"])
        self.initiative_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.top_layout.addWidget(self.initiative_table)
        
        # Button bar
        self.button_bar = QHBoxLayout()
        self.add_pc_button = QPushButton("Add PC")
        self.next_button = QPushButton("Next Turn")
        self.resolve_button = QPushButton("Resolve Combat")
        self.fast_resolve_button = QPushButton("Fast Resolve")
        self.fast_resolve_button.setToolTip("Resolve combat using AI (Experimental)")
        # DO NOT connect signals here - they will be connected in _connect_signals
        self.reset_button = QPushButton("Reset")
        
        # Add buttons to button bar
        self.button_bar.addWidget(self.add_pc_button)
        self.button_bar.addWidget(self.next_button)
        self.button_bar.addWidget(self.resolve_button)
        self.button_bar.addWidget(self.fast_resolve_button)
        self.button_bar.addWidget(self.reset_button)
        self.top_layout.addLayout(self.button_bar)
        
        # Add top widget to splitter
        self.main_splitter.addWidget(self.top_widget)
        
        # Add combat log section
        self.log_widget = QWidget()
        self.log_layout = QVBoxLayout(self.log_widget)
        self.log_layout.setContentsMargins(0, 0, 0, 0)
        
        # Combat log label
        self.log_label = QLabel("Combat Log")
        self.log_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.log_layout.addWidget(self.log_label)
        
        # Combat log text area
        self.combat_log_widget = QTextEdit()
        self.combat_log_widget.setReadOnly(True)
        self.combat_log_widget.setMinimumHeight(150)
        self.combat_log_widget.setStyleSheet("background-color: #f5f5f5;")
        self.log_layout.addWidget(self.combat_log_widget)
        
        # Add log widget to splitter
        self.main_splitter.addWidget(self.log_widget)
        
        # Connect signals after all UI elements are set up
        self._connect_signals()
        
        logging.debug("[CombatTracker] UI setup complete")
        
    def _setup_initiative_table(self):
        """Set up the initiative tracking table with proper configuration"""
        from PySide6.QtWidgets import QHeaderView
        
        # Set column widths
        header = self.initiative_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)  # Name column stretches
        header.setSectionResizeMode(1, QHeaderView.Fixed)    # Initiative
        header.setSectionResizeMode(2, QHeaderView.Fixed)    # HP
        header.setSectionResizeMode(3, QHeaderView.Fixed)    # AC
        header.setSectionResizeMode(4, QHeaderView.Fixed)    # Type
        header.setSectionResizeMode(5, QHeaderView.Fixed)    # Status
        
        # Set column widths for fixed columns
        self.initiative_table.setColumnWidth(1, 60)  # Initiative
        self.initiative_table.setColumnWidth(2, 70)  # HP
        self.initiative_table.setColumnWidth(3, 50)  # AC
        self.initiative_table.setColumnWidth(4, 80)  # Type
        self.initiative_table.setColumnWidth(5, 100) # Status
        
        # Other table settings
        self.initiative_table.setSelectionBehavior(QHeaderView.SelectRows)
        self.initiative_table.setAlternatingRowColors(True)
        self.initiative_table.verticalHeader().setVisible(False)
        
    def _connect_signals(self):
        """Connect UI signals to their handlers"""
        import logging
        
        try:
            # Disconnect any existing signals first to prevent duplicates
            logging.debug("[CombatTracker] Disconnecting existing signals")
            
            try:
                # Try to disconnect only if the attribute exists and is a method
                self.add_pc_button.clicked.disconnect()
                logging.debug("[CombatTracker] Disconnected add_pc_button signals")
            except (RuntimeError, AttributeError):
                # Signal was not connected
                pass
                
            try:
                self.next_button.clicked.disconnect()
                logging.debug("[CombatTracker] Disconnected next_button signals")
            except (RuntimeError, AttributeError):
                pass
                
            try:
                self.resolve_button.clicked.disconnect()
                logging.debug("[CombatTracker] Disconnected resolve_button signals")
            except (RuntimeError, AttributeError):
                pass
                
            try:
                self.reset_button.clicked.disconnect()
                logging.debug("[CombatTracker] Disconnected reset_button signals")
            except (RuntimeError, AttributeError):
                pass
                
            # CRITICAL: Clear all existing connections for fast_resolve_button
            try:
                self.fast_resolve_button.clicked.disconnect()
                logging.debug("[CombatTracker] Disconnected fast_resolve_button signals")
            except (RuntimeError, AttributeError):
                logging.debug("[CombatTracker] No signals to disconnect for fast_resolve_button")
                pass
            
            # Connect signals to handlers
            logging.debug("[CombatTracker] Connecting new signals")
            self.add_pc_button.clicked.connect(self._handle_add_pc_click)
            self.next_button.clicked.connect(self._handle_next_turn)
            self.resolve_button.clicked.connect(self._handle_resolve_click)
            self.reset_button.clicked.connect(self._handle_reset_click)
            
            # CRITICAL: Connect the fast resolve button to our handler
            self.fast_resolve_button.clicked.connect(self._handle_fast_resolve_click)
            logging.debug("[CombatTracker] Fast resolve button signal connected to _handle_fast_resolve_click")
            
            # Table signals
            self.initiative_table.cellChanged.connect(self._handle_cell_changed)
            self.initiative_table.customContextMenuRequested.connect(self._handle_context_menu)
            self.initiative_table.itemSelectionChanged.connect(self._handle_selection_changed)
            
            logging.debug("[CombatTracker] All signals connected successfully")
        except Exception as e:
            import traceback
            logging.error(f"[CombatTracker] Error connecting signals: {e}")
            logging.error(traceback.format_exc())

    # Default handler methods that will be implemented elsewhere or overridden
    def _handle_add_pc_click(self):
        """Handle add PC button click"""
        print("[CombatTracker] Add PC button clicked")
    
    def _handle_next_turn(self):
        """Handle next turn button click"""
        print("[CombatTracker] Next Turn button clicked")
    
    def _handle_resolve_click(self):
        """Handle resolve combat button click"""
        print("[CombatTracker] Resolve Combat button clicked")
    
    def _handle_fast_resolve_click(self):
        """Handle clicks on the 'Fast Resolve' button."""
        from PySide6.QtWidgets import QMessageBox
        
        print("[CombatTracker] Fast Resolve button clicked!")
        QMessageBox.information(self, "Fast Resolve", "Fast Resolve button clicked. Initializing combat resolution...")
        
        # Call the fast resolve combat method
        self._fast_resolve_combat()

    def _handle_reset_click(self):
        """Handle reset button click"""
        print("[CombatTracker] Reset button clicked")
    
    def _handle_cell_changed(self, row, column):
        """Handle cell value changes in the initiative table"""
        print(f"[CombatTracker] Cell changed: row={row}, column={column}")
    
    def _handle_context_menu(self, position):
        """Show context menu for initiative table"""
        print(f"[CombatTracker] Context menu requested at {position}")
    
    def _handle_selection_changed(self):
        """Handle selection changes in the initiative table"""
        print("[CombatTracker] Selection changed")

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
        
        print("\n=============== FAST_RESOLVE_COMBAT INITIATED ===============")
        print("[CombatTracker] Fast Resolve button clicked, starting resolver.")
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
                print("[CombatTracker] setup_and_start_combat thread started")
                # Step 1: Validate we have combatants
                has_monster = has_player = False
                for row in range(self.initiative_table.rowCount()):
                    type_item = self.initiative_table.item(row, self.COL_TYPE)  # Type is now column 4
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
                
                # Call the resolver with our updated approach
                print("[CombatTracker] Calling combat_resolver.start_resolution() method")
                
                # Get a direct reference to the CombatResolver 
                # Check if using ImprovedCombatResolver (which wraps CombatResolver)
                if hasattr(self.app_state, 'combat_resolver'):
                    if hasattr(self.app_state.combat_resolver, 'combat_resolver'):
                        # Using ImprovedCombatResolver (which has a combat_resolver attribute)
                        # Access the underlying CombatResolver directly
                        resolver = self.app_state.combat_resolver.combat_resolver
                        print("[CombatTracker] Using underlying CombatResolver from ImprovedCombatResolver")
                        print(f"[DEBUG] resolver type: {type(resolver)}")
                        print(f"[DEBUG] resolver methods: {dir(resolver)}")
                    else:
                        # Using CombatResolver directly
                        resolver = self.app_state.combat_resolver
                        print("[CombatTracker] Using CombatResolver directly")
                        print(f"[DEBUG] resolver type: {type(resolver)}")
                else:
                    QApplication.instance().postEvent(self, CombatTrackerPanel._ErrorEvent(
                        "Error", 
                        f"Combat Resolver not found in App State."
                    ))
                    self._is_resolving_combat = False # Reset flag
                    return
                
                # Connect the resolution_update signal directly to our _process_resolution_ui slot
                try:
                    # Disconnect any existing connection first to be safe
                    try:
                        resolver.resolution_update.disconnect(self._process_resolution_ui)
                        print("[CombatTracker] Disconnected existing signal connection")
                    except Exception as e:
                        # Connection might not exist yet, which is fine
                        print(f"[CombatTracker] No existing connection to disconnect: {e}")
                        pass
                    
                    # Connect the signal
                    resolver.resolution_update.connect(
                        lambda state, status, error: self._process_resolution_ui(state, error)
                    )
                    print("[CombatTracker] Successfully connected resolution_update signal")
                except Exception as conn_error:
                    print(f"[CombatTracker] Failed to connect signal: {conn_error}")
                    
                # Start the resolution using the modern start_resolution API
                print(f"[DEBUG] Starting combat resolution with {len(combat_state.get('combatants', []))} combatants")
                print(f"[DEBUG] Combat state keys: {list(combat_state.keys())}")
                success = resolver.start_resolution(
                    combat_state,
                    dice_roller,
                    self._update_ui_wrapper, # Pass the wrapper for UI updates
                    mode='continuous'
                )
                print(f"[DEBUG] start_resolution returned: {success}")
                
                if not success:
                    # Failed to start resolution
                    print("[DEBUG] Failed to start resolution!")
                    QApplication.instance().postEvent(self, CombatTrackerPanel._ErrorEvent(
                        "Error", 
                        f"Failed to start combat resolution - it might already be running."
                    ))
                    self._is_resolving_combat = False # Reset flag
                    QApplication.instance().postEvent(self, CombatTrackerPanel._UpdateButtonEvent("Fast Resolve", True))
                    return
                    
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
                # Get the appropriate resolver instance
                if hasattr(self.app_state, 'combat_resolver'):
                    if hasattr(self.app_state.combat_resolver, 'combat_resolver'):
                        # Using ImprovedCombatResolver - get the underlying CombatResolver
                        resolver = self.app_state.combat_resolver.combat_resolver
                        print("[CombatTracker] Connecting signal to underlying CombatResolver")
                    else:
                        # Using CombatResolver directly
                        resolver = self.app_state.combat_resolver
                        print("[CombatTracker] Connecting signal to CombatResolver directly")
                else:
                    print("[CombatTracker] Combat Resolver not found - cannot connect signal")
                    return True
                    
                # Disconnect any existing connection first to be safe
                try:
                    resolver.resolution_update.disconnect(self._process_resolution_ui)
                    print("[CombatTracker] Disconnected existing signal connection")
                except Exception:
                    # Connection might not exist yet, which is fine
                    pass
                
                # Connect to the resolution_update signal (state, status, error)
                resolver.resolution_update.connect(
                    lambda state, status, error: self._process_resolution_ui(state, error)
                )
                print("[CombatTracker] Successfully connected resolution_update signal")
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
            name_item = self.initiative_table.item(row, self.COL_NAME)
            initiative_item = self.initiative_table.item(row, self.COL_INITIATIVE)
            hp_item = self.initiative_table.item(row, self.COL_HP)
            ac_item = self.initiative_table.item(row, self.COL_AC)
            status_item = self.initiative_table.item(row, self.COL_STATUS)
            type_item = self.initiative_table.item(row, self.COL_TYPE)
            
            # Get values or defaults
            name = name_item.text() if name_item else "Unknown"
            initiative = int(initiative_item.text() or "0") if initiative_item else 0
            hp = int(hp_item.text() or "0") if hp_item else 0
            ac = int(ac_item.text() or "10") if ac_item else 10
            status = status_item.text() if status_item else ""
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
            print(f"[CombatTracker] DEBUG: Table row {row}: {name} - HP: {hp} {' (ID: ' + str(instance_id) + ')' if instance_id else ''}")
            
            # Create combatant dictionary
            combatant = {
                "name": name,
                "initiative": initiative,
                "hp": hp,
                "ac": ac,
                "status": status,
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
    def _process_resolution_ui(self, *args):
        """Process UI updates from the combat resolution system"""
        # Cancel timers to prevent duplicate processing
        self._cancel_safety_timer()
        self._cancel_backup_timer()
        
        try:
            # Reset UI elements first
            self._reset_resolve_button()
            self._is_resolving_combat = False
        except Exception as e:
            logging.error(f"[CombatTracker] Error resetting UI: {e}")
    
    def _update_ui_wrapper(self, turn_state):
        """Thread-safe wrapper to update UI during combat (used by the resolver)"""
        try:
            # This method now just passes the state directly to _update_ui
            # Serialize if needed, but simplified from previous version
            self._update_ui(turn_state)
        except Exception as e:
            logging.error(f"[CombatTracker] Error in UI wrapper: {e}")
    
    def _add_initial_combat_state_to_log(self, combat_state):
        """Add initial combat state to the log at the start of combat"""
        try:
            # Header
            header = "<h3 style='color: #000088;'>Combat Begins</h3>"
            self.combat_log_widget.append(header)
            
            # Combatants list
            combatants = combat_state.get("combatants", [])
            if combatants:
                combatant_list = "<ul>"
                for c in combatants:
                    name = c.get("name", "Unknown")
                    hp = c.get("hp", "?")
                    ac = c.get("ac", "?")
                    combatant_list += f"<li><b>{name}</b> - AC: {ac}, HP: {hp}</li>"
                combatant_list += "</ul>"
                self.combat_log_widget.append(combatant_list)
            else:
                self.combat_log_widget.append("<p>No combatants in combat!</p>")
                
            # Force scroll to bottom
            scrollbar = self.combat_log_widget.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
        except Exception as e:
            logging.error(f"[CombatTracker] Error adding initial state: {e}")
    
    def _cancel_safety_timer(self):
        """Cancel the safety timer if it exists"""
        if hasattr(self, '_safety_timer') and self._safety_timer:
            try:
                self._safety_timer.stop()
                logging.debug("[CombatTracker] Canceled safety timer")
            except Exception:
                pass
    
    def _cancel_backup_timer(self):
        """Cancel the backup timer if it exists"""
        if hasattr(self, '_backup_timer') and self._backup_timer:
            try:
                self._backup_timer.stop()
                logging.debug("[CombatTracker] Canceled backup timer")
            except Exception:
                pass

    def _update_ui(self, combat_state):
        """Update the UI with the latest combat state."""
        import html
        
        # Safety check
        if not combat_state or not isinstance(combat_state, dict):
            logging.warning("[CombatTracker] Invalid combat state received in _update_ui")
            return
            
        # Extract information from combat state
        combatants = combat_state.get("combatants", [])
        round_num = combat_state.get("round", 1)
        current_turn_index = combat_state.get("current_turn_index", 0)
        latest_action = combat_state.get("latest_action", {})
        
        # Get combatant details
        if not combatants or current_turn_index >= len(combatants):
            logging.warning(f"[CombatTracker] Invalid combatant index: {current_turn_index}, count: {len(combatants)}")
            return
            
        actor = combatants[current_turn_index].get("name", "Unknown")
        action = latest_action.get("action", "No action")
        target = latest_action.get("target", "")  # Add target extraction
        result = latest_action.get("narrative", latest_action.get("result", ""))  # Prefer narrative if available
        dice_rolls = latest_action.get("dice", [])
        action_type = latest_action.get("action_type", "standard")
        action_icon = latest_action.get("action_icon", "⚡")
        narrative_style = latest_action.get("narrative_style", "")
        is_fallback = latest_action.get("fallback", False)
        
        # Update the combat log with high contrast colors
        # Add this turn's information to the combat log panel
        turn_text = f"<div style='margin-bottom:15px; padding:8px; border-radius:5px; background-color:#f9f9f9;'>"
        
        # Header with round/turn info
        turn_text += f"<h4 style='color:#000088; margin:0 0 5px 0; border-bottom:1px solid #ddd; padding-bottom:3px;'>Round {round_num} - {actor}'s Turn {action_icon}</h4>"
        
        # Check if this is a fallback action due to an error
        if is_fallback:
            # This is a fallback action due to an error
            error_message = latest_action.get("error", "Unknown error")
            turn_text += f"<p style='color:#880000; margin:5px 0;'><i>Technical note: {html.escape(error_message)}</i></p>"
            turn_text += f"<p style='color:#000000; margin:5px 0;'>{html.escape(result)}</p>"
        else:
            # Regular action display with enhanced styling based on action type
            # Action title with icon and target
            turn_text += f"<div style='font-weight:bold; margin:5px 0;'>{action_icon} <span>{html.escape(action)}</span>"
            if target:
                turn_text += f" <span style='color:#555;'>→ {html.escape(target)}</span>"
            turn_text += "</div>"
            
            # Narrative with custom styling
            if narrative_style:
                turn_text += f"<p style='{narrative_style} margin:5px 0;'>{html.escape(result)}</p>"
            else:
                turn_text += f"<p style='margin:5px 0;'>{html.escape(result)}</p>"
            
            # Dice section if any dice were rolled
            if dice_rolls:
                turn_text += f"<div style='margin-top:5px; font-size:0.9em; color:#555; background-color:#f0f0f0; padding:4px; border-radius:3px;'>"
                turn_text += "<span style='font-weight:bold;'>🎲 Dice:</span> "
                
                dice_details = []
                for roll in dice_rolls:
                    purpose = roll.get("purpose", "Roll")
                    expression = roll.get("expression", "?")
                    result = roll.get("result", "?")
                    dice_details.append(f"<span title='{html.escape(purpose)}'>{html.escape(expression)}={html.escape(str(result))}</span>")
                
                turn_text += " | ".join(dice_details)
                turn_text += "</div>"
        
        # Close the div
        turn_text += "</div>"
        
        # Update the log
        self.combat_log_widget.append(turn_text)
        
        # Make sure the log scrolls to the bottom
        scrollbar = self.combat_log_widget.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _sort_initiative(self):
        """Sort the initiative table by initiative values (highest first)."""
        print("[CombatTracker] Sorting initiative table")
        try:
            # Get current number of rows
            rows = self.initiative_table.rowCount()
            if rows <= 1:
                # Nothing to sort with 0 or 1 rows
                return
                
            # Build a list of (row, initiative) tuples
            initiative_data = []
            for row in range(rows):
                initiative_item = self.initiative_table.item(row, self.COL_INITIATIVE)  # Initiative is in column 1
                if initiative_item and initiative_item.text():
                    try:
                        initiative = float(initiative_item.text())
                    except ValueError:
                        initiative = 0
                else:
                    initiative = 0
                initiative_data.append((row, initiative))
                
            # Sort by initiative (highest first)
            initiative_data.sort(key=lambda x: x[1], reverse=True)
            
            # Apply the sort by rearranging rows
            for new_row, (old_row, _) in enumerate(initiative_data):
                if new_row != old_row:
                    # Need to move this row
                    self._move_table_row(old_row, new_row)
                    
            # Update the current_turn to match the sorted order
            if hasattr(self, 'current_turn'):
                # Find the new position of the current turn
                for new_row, (old_row, _) in enumerate(initiative_data):
                    if old_row == self.current_turn:
                        self.current_turn = new_row
                        break
            
            print(f"[CombatTracker] Initiative sorted, {rows} combatants")
        except Exception as e:
            import traceback
            print(f"[DEBUG] Error sorting initiative: {e}")
            print(traceback.format_exc())
    
    def _move_table_row(self, from_row, to_row):
        """Move a row in the initiative table from one position to another."""
        # If rows are the same, nothing to do
        if from_row == to_row:
            return
            
        # Get number of columns
        cols = self.initiative_table.columnCount()
        
        # Temporarily remove the row being moved
        items = []
        for col in range(cols):
            item = self.initiative_table.takeItem(from_row, col)
            items.append(item)
            
        # Insert the row at the new position
        if from_row < to_row:
            # Moving down, insert at to_row
            self.initiative_table.insertRow(to_row)
            for col in range(cols):
                self.initiative_table.setItem(to_row, col, items[col])
            # Remove the original row, adjusted for the new row we added
            self.initiative_table.removeRow(from_row)
        else:
            # Moving up, insert at to_row
            self.initiative_table.insertRow(to_row)
            for col in range(cols):
                self.initiative_table.setItem(to_row, col, items[col])
            # Remove the original row, adjusted for the new row we added
            self.initiative_table.removeRow(from_row + 1)

    def _log_combat_action(self, action_type, actor, action, target=None, details=None):
        """
        Add an entry to the combat log.
        
        Args:
            action_type (str): Type of action (e.g., "Attack", "Move", "Spell", "Setup")
            actor (str): Name of the entity performing the action
            action (str): Description of the action
            target (str, optional): Target of the action, if any
            details (str, optional): Additional details about the action
        """
        import datetime
        from PySide6.QtGui import QTextCursor, QColor
        
        # Format the log entry
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] "
        
        # Add action type with color based on type
        color_map = {
            "Attack": "crimson",
            "Move": "blue",
            "Spell": "purple",
            "Heal": "green",
            "Damage": "red",
            "Status": "orange",
            "Setup": "gray"
        }
        color = color_map.get(action_type, "black")
        log_entry += f"<span style='color: {color};'>[{action_type}]</span> "
        
        # Add actor and action
        log_entry += f"<b>{actor}</b> {action} "
        
        # Add target if provided
        if target:
            log_entry += f"<b>{target}</b> "
            
        # Add details if provided
        if details:
            log_entry += f"{details}"
            
        # Add the entry to the log
        try:
            # Get the QTextEdit widget for the combat log
            if hasattr(self, 'combat_log_widget') and self.combat_log_widget:
                # Append the HTML formatted text
                self.combat_log_widget.append(log_entry)
                
                # Scroll to the bottom
                self.combat_log_widget.moveCursor(QTextCursor.End)
                
                print(f"[CombatTracker] Added log entry: {action_type} - {actor} {action} {target or ''} {details or ''}")
            else:
                print(f"[DEBUG] Cannot log combat action: No combat_log_widget found")
        except Exception as e:
            import traceback
            print(f"[DEBUG] Error logging combat action: {e}")
            print(traceback.format_exc())
