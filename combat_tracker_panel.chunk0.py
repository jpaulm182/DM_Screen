# app/ui/panels/combat_tracker_panel.py - Combat tracker panel
"""
Combat tracker panel for managing initiative and combat encounters

Features:
- Initiative tracking with auto-sorting
- HP and AC management
- Status conditions with quick apply
- Death saving throws tracking
- Concentration tracking
- Combat timer
- Round/turn tracking
- Keyboard shortcuts
- Quick HP updates
- Combat log integration
- View monster and character details
- Inline details panel for quick reference
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QLabel,
    QSpinBox, QLineEdit, QPushButton, QHeaderView, QComboBox, QCheckBox,
    QGroupBox, QWidget, QStyledItemDelegate, QStyle, QToolButton,
    QTabWidget, QScrollArea, QFormLayout, QFrame, QSplitter, QApplication,
    QSizePolicy, QTextEdit, QMenu, QMessageBox, QDialog, QDialogButtonBox,
    QAbstractItemView, QInputDialog
)
from PySide6.QtCore import Qt, QTimer, Signal, Slot, QSize, QMetaObject, Q_ARG, QObject, QPoint, QRect, QEvent, QThread
from PySide6.QtGui import QColor, QFont, QTextCharFormat, QBrush, QPixmap, QImage, QTextCursor, QPalette, QAction, QKeySequence
import random
import re
import json
import copy
import time
import threading
import gc
import hashlib
import logging # Add logging import

from .combat_dialogs import (
    DamageDialog, DeathSavesDialog, ConcentrationDialog,
    CombatantDetailsDialog, # Ensure this line is not commented out
    SavingThrowDialog, ABILITIES
)

from .combat_utils import get_attr, roll_dice, extract_dice_formula

from app.ui.panels.base_panel import BasePanel
from app.ui.panels.panel_category import PanelCategory

# --- Modularized imports ---
from app.ui.panels.combat_constants import CONDITIONS
# Around line 48
from app.ui.panels.combat_tracker_delegates import CurrentTurnDelegate, HPUpdateDelegate, InitiativeUpdateDelegate
from app.ui.panels.combat_utils import extract_dice_formula, roll_dice, get_attr
from app.ui.panels.combatant_manager import CombatantManager

# Import dialogs from the new location
from .combat_tracker.combat_tracker_dialogs import DeathSavesDialog
# Import the new Combatant Manager
from .combat_tracker.combatant_manager import CombatantManager


# --- End modularized imports ---

# Remove: In-file CONDITIONS, CurrentTurnDelegate, HPUpdateDelegate, etc.
# Use the imported versions throughout your file.




# --- Dialog Classes --- 


class DeathSavesDialog(QDialog):
    """Dialog for tracking death saving throws"""
    def __init__(self, parent=None, current_saves=None):
        super().__init__(parent)
        self.setWindowTitle("Death Saving Throws")
        self.current_saves = current_saves or {"successes": 0, "failures": 0}
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout()
        
        # Successes
        success_group = QGroupBox("Successes")
        success_layout = QHBoxLayout()
        self.success_checks = []
        for i in range(3):
            check = QCheckBox()
            check.setChecked(i < self.current_saves["successes"])
            self.success_checks.append(check)
            success_layout.addWidget(check)
        success_group.setLayout(success_layout)
        layout.addWidget(success_group)
        
        # Failures
        failure_group = QGroupBox("Failures")
        failure_layout = QHBoxLayout()
        self.failure_checks = []
        for i in range(3):
            check = QCheckBox()
            check.setChecked(i < self.current_saves["failures"])
            self.failure_checks.append(check)
            failure_layout.addWidget(check)
        failure_group.setLayout(failure_layout)
        layout.addWidget(failure_group)
        
        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        self.setLayout(layout)
    
    def get_saves(self):
        """Get the current death saves state"""
        return {
            "successes": sum(1 for c in self.success_checks if c.isChecked()),
            "failures": sum(1 for c in self.failure_checks if c.isChecked())
        }


# --- Main Panel Class --- 

class CombatTrackerPanel(BasePanel):
    """Panel for tracking combat initiative, HP, and conditions"""
    
    # Signal to emit when combat resolution is complete (or failed)
    # Carries the result dict and error string (one will be None)
    resolution_complete = Signal(dict, str)
    
    # New signal for showing turn results
    show_turn_result_signal = Signal(str, str, str, str, str)
    
    # Add missing combat_log_signal for panel connection
    combat_log_signal = Signal(str, str, str, str, str)  # category, actor, action, target, result

    # Signal to request character details from PlayerCharacterPanel
    request_character_details = Signal(str) # Emits character name

    # Signal to request monster details from MonsterPanel
    request_monster_details = Signal(str) # Emits monster name or ID

    @property
    def current_turn(self):
        """Get the current turn index"""
        return getattr(self, '_current_turn', -1)
    
    @current_turn.setter
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

    def _ensure_table_ready(self):
        """Ensure the table exists and has the correct number of columns"""
        # First check if table exists
        if not hasattr(self, 'initiative_table'):
            print("[CombatTracker] ERROR: initiative_table not found during initialization")
            return
            
        # Ensure the vertical header is hidden (row numbers)
        self.initiative_table.verticalHeader().setVisible(False)
        
        # Make sure horizontal headers are visible
        self.initiative_table.horizontalHeader().setVisible(True)
        
        # Adjust column widths for better display
        self.initiative_table.resizeColumnsToContents()
        
        # Add test combatant if table is empty and we're in development
        if self.initiative_table.rowCount() == 0:
            # Restore state first if available
            state = self.app_state.get_setting("combat_tracker_state", None)
            if state:
                print("[CombatTracker] Restoring combat tracker state from settings")
                self.restore_state(state)
                # Force a table update after restoring state
                self.initiative_table.viewport().update()
                self.initiative_table.update()
            
            # If still empty after restore attempt, add placeholder
            if self.initiative_table.rowCount() == 0:
                # Add a demo player character if table is still empty
                print("[CombatTracker] Adding placeholder character to empty table for visibility")
                self.combatant_manager.add_combatant("Add your party here!", 20, 30, 15, "character")
        
        # Ensure viewport is updated
        self.initiative_table.viewport().update()
        
        # Force application to process events
        QApplication.processEvents()
    
    def _setup_delegates(self):
        """Set up custom delegates for the initiative table"""
        # Set custom delegates for initiative and HP columns
        self.init_delegate = InitiativeUpdateDelegate(self)
        self.init_delegate.initChanged.connect(self._initiative_changed)
        self.initiative_table.setItemDelegateForColumn(1, self.init_delegate)
        
        self.hp_delegate = HPUpdateDelegate(self)
        self.hp_delegate.hpChanged.connect(self._hp_changed)
        self.initiative_table.setItemDelegateForColumn(2, self.hp_delegate)
        
        # Set delegate for highlighting current turn
        self.current_turn_delegate = CurrentTurnDelegate()
        for col in range(8):  # Apply to all columns (including the new Max HP column)
            self.initiative_table.setItemDelegateForColumn(col, self.current_turn_delegate)
        
        # When cell content changes, update internal data
        self.initiative_table.cellChanged.connect(self._handle_cell_changed)
    
    def _setup_ui(self):
        """Setup the UI components"""
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Create a splitter to allow manual resizing between the table and log
        self.main_splitter = QSplitter(Qt.Vertical)
        
        # --- Initiative Table Area ---
        table_container = QWidget()
        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create initiative table
        self.initiative_table = QTableWidget(0, 8)  # Changed to 8 columns
        self.initiative_table.setHorizontalHeaderLabels(["Name", "Initiative", "HP", "Max HP", "AC", "Status", "Conc.", "Type"])
        self.initiative_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.initiative_table.setSelectionMode(QTableWidget.ExtendedSelection)
        # Allow editing via double‑click or pressing a key, but NOT on single
        # mouse right‑clicks so the context menu can appear reliably.
        self.initiative_table.setEditTriggers(
            QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed
        )
        
        # Set column widths
        self.initiative_table.setColumnWidth(0, 150)  # Name
        self.initiative_table.setColumnWidth(1, 80)   # Initiative
        self.initiative_table.setColumnWidth(2, 80)   # HP
        self.initiative_table.setColumnWidth(3, 80)   # Max HP
        self.initiative_table.setColumnWidth(4, 60)   # AC
        self.initiative_table.setColumnWidth(5, 120)  # Status
        self.initiative_table.setColumnWidth(6, 60)   # Conc
        self.initiative_table.setColumnWidth(7, 100)  # Type
        
        # Set header behavior
        header = self.initiative_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)       # Name stretches
        header.setSectionResizeMode(5, QHeaderView.Stretch)       # Status stretches
        header.setSectionResizeMode(1, QHeaderView.Fixed)         # Initiative fixed
        header.setSectionResizeMode(2, QHeaderView.Fixed)         # HP fixed
        header.setSectionResizeMode(3, QHeaderView.Fixed)         # Max HP fixed  
        header.setSectionResizeMode(4, QHeaderView.Fixed)         # AC fixed
        header.setSectionResizeMode(6, QHeaderView.Fixed)         # Conc fixed
        header.setSectionResizeMode(7, QHeaderView.Fixed)         # Type fixed
        
        # Connect context menu
        self.initiative_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.initiative_table.customContextMenuRequested.connect(self._show_context_menu)
        
        # Connect change signals
        self.initiative_table.cellChanged.connect(self._handle_cell_changed)
        
        # Set up the custom delegates
        self._setup_delegates()
        
        # --- Control Area with three rows: Round/Timer, Buttons, Add Combatant ---
        control_layout = self._setup_control_area()
        table_layout.addLayout(control_layout)
        
        # Add add combatant controls if needed
        add_combatant_layout = self._setup_add_combatant_controls()
        table_layout.addLayout(add_combatant_layout)
        
        # Add table to layout
        table_layout.addWidget(self.initiative_table)
        
        # Add table to main splitter
        self.main_splitter.addWidget(table_container)
        
        # --- Combat Log Area (NEW) ---
        self.log_container = QWidget()
        log_layout = QVBoxLayout(self.log_container)
        log_layout.setContentsMargins(0, 0, 0, 0)
        
        # Header for combat log
        log_header = QHBoxLayout()
        log_header.addWidget(QLabel("<b>Combat Log & Results</b>"))
        
        # Add clear button for log
        clear_log_btn = QPushButton("Clear Log")
        clear_log_btn.setMaximumWidth(100)
        clear_log_btn.clicked.connect(self._clear_combat_log)
        log_header.addWidget(clear_log_btn)
        
        log_layout.addLayout(log_header)
        
        # Create text area for combat log
        self.combat_log_text = QTextEdit()
        self.combat_log_text.setReadOnly(True)
        self.combat_log_text.setMinimumHeight(100)
        self.combat_log_text.setStyleSheet("""
            QTextEdit { 
                background-color: white;
                color: #000000;
                font-family: Arial, sans-serif;
                font-size: 12px;
            }
        """)
        log_layout.addWidget(self.combat_log_text)
        
        # Add log container to splitter
        self.main_splitter.addWidget(self.log_container)
        
        # Set reasonable initial sizes
        self.main_splitter.setSizes([600, 200])
        
        # Add the splitter to the main layout
        layout.addWidget(self.main_splitter)
        
        self.setLayout(layout)
        
        # Initialize UI components
        self.initiative_table.setMinimumHeight(200)
        
        # Connect signals
        self.initiative_table.itemSelectionChanged.connect(self._on_selection_changed)
        
        # Create keyboard shortcuts
        QAction("Next Turn", self, triggered=self._next_turn, shortcut=QKeySequence("N")).setShortcutContext(Qt.WidgetWithChildrenShortcut)
        self.addAction(QAction("Next Turn", self, triggered=self._next_turn, shortcut=QKeySequence("N")))
        
        # Set table stretch 
        self.main_splitter.setStretchFactor(0, 3)  # Combat tracker gets 3 parts
        self.main_splitter.setStretchFactor(1, 2)  # Details gets 2 parts
        
        # Initialize the table
        self._update_highlight()
    
    def _setup_control_area(self):
        """Set up the combat control area"""
        control_layout = QHBoxLayout()
        
        # Combat info group
        combat_info = QGroupBox("Combat Info")
        info_layout = QHBoxLayout()
        
        # Round counter
        round_layout = QVBoxLayout()
        round_layout.addWidget(QLabel("Round:"))
        self.round_spin = QSpinBox()
        self.round_spin.setMinimum(1)
        self.round_spin.setValue(self.current_round)
        self.round_spin.valueChanged.connect(self._round_changed)
        round_layout.addWidget(self.round_spin)
        info_layout.addLayout(round_layout)
        
        # Combat duration
        duration_layout = QVBoxLayout()
        duration_layout.addWidget(QLabel("Duration:"))
        duration_widget = QWidget()
        duration_inner = QHBoxLayout()
        
        self.timer_label = QLabel("00:00:00")
        duration_inner.addWidget(self.timer_label)
        
        self.timer_button = QPushButton("Start")
        self.timer_button.clicked.connect(self._toggle_timer)
        duration_inner.addWidget(self.timer_button)
        
        duration_widget.setLayout(duration_inner)
        duration_layout.addWidget(duration_widget)
        info_layout.addLayout(duration_layout)
        
        # In-game time
        game_time_layout = QVBoxLayout()
        game_time_layout.addWidget(QLabel("In-Game Time:"))
        self.game_time_label = QLabel("0 rounds (0 minutes)")
        game_time_layout.addWidget(self.game_time_label)
        info_layout.addLayout(game_time_layout)
        
        combat_info.setLayout(info_layout)
        control_layout.addWidget(combat_info)
        
        control_layout.addStretch(1)
        
        # Next combatant button (previously Next Turn)
        self.next_turn_button = QPushButton("Next Combatant")
        self.next_turn_button.clicked.connect(self._next_turn)
        control_layout.addWidget(self.next_turn_button)

        # Add Fast Resolve button
        self.fast_resolve_button = QPushButton("Fast Resolve")
        self.fast_resolve_button.setToolTip("Resolve the current combat using AI (Experimental)")
        # Connection is now handled in _connect_signals to prevent duplicate connections
        # DO NOT connect here: self.fast_resolve_button.clicked.connect(self._fast_resolve_combat)
        control_layout.addWidget(self.fast_resolve_button)

        # Reset Combat button
        self.reset_button = QPushButton("Reset Combat")
        self.reset_button.clicked.connect(self._reset_combat)
        control_layout.addWidget(self.reset_button)
        
        # Restart Combat button
        self.restart_button = QPushButton("Restart Combat")
        self.restart_button.clicked.connect(self._restart_combat)
        control_layout.addWidget(self.restart_button)
        
        return control_layout
    
    def _setup_add_combatant_controls(self):
        """Set up the controls for adding new combatants"""
        add_layout = QHBoxLayout()
        
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Name")
        add_layout.addWidget(self.name_input)
        
        init_layout = QHBoxLayout()
        self.initiative_input = QSpinBox()
        self.initiative_input.setRange(-20, 30)  # Allow for negative initiative
        self.initiative_input.setPrefix("Init: ")
        init_layout.addWidget(self.initiative_input)
        
        # Add quick roll button
        roll_init_button = QPushButton("🎲")
        roll_init_button.setToolTip("Roll initiative (1d20)")
        roll_init_button.clicked.connect(self._roll_initiative)
        roll_init_button.setMaximumWidth(30)
        init_layout.addWidget(roll_init_button)
        
        init_widget = QWidget()
        init_widget.setLayout(init_layout)
        add_layout.addWidget(init_widget)
        
        self.hp_input = QSpinBox()
        self.hp_input.setRange(1, 999)
        self.hp_input.setPrefix("HP: ")
        add_layout.addWidget(self.hp_input)
        
        self.ac_input = QSpinBox()
        self.ac_input.setRange(0, 30)
        self.ac_input.setPrefix("AC: ")
        add_layout.addWidget(self.ac_input)
        
        # Add modifier input for initiative
        self.init_mod_input = QSpinBox()
        self.init_mod_input.setRange(-10, 10)
        self.init_mod_input.setPrefix("Init Mod: ")
        self.init_mod_input.setValue(0)
        add_layout.addWidget(self.init_mod_input)
        
        # Create Add button with new connection approach
        add_button = QPushButton("Add Manual Combatant")
        add_button.clicked.connect(self._handle_add_click)
        add_layout.addWidget(add_button)
        
        return add_layout
    
    def _handle_add_click(self):
        """Handle the Add button click to add a new combatant from form fields"""
        try:
            name = self.name_input.text().strip()
            if not name:
                # Don't add combatants without a name
                QMessageBox.warning(self, "Missing Name", "Please enter a name for the combatant.")
                return
            
            # Get values from input fields
            initiative = self.initiative_input.value()
            hp = self.hp_input.value()
            max_hp = hp  # Set max_hp to same as current hp for manually added combatants
            ac = self.ac_input.value()
            
            # Add the combatant (no specific type for manual adds)
            row = self.combatant_manager.add_combatant(name, initiative, hp, max_hp, ac, "manual")
            
            # Only reset fields and log if the add was successful
            if row >= 0:
                # Reset fields for next entry (except initiative modifier)
                self.name_input.clear()
                self.initiative_input.setValue(0)
                
                # Log to combat log
                self._log_combat_action("Setup", "DM", "added manual combatant", name, f"(Initiative: {initiative})")
                
                return row
            else:
                QMessageBox.warning(self, "Add Failed", f"Failed to add {name} to the combat tracker.")
                return -1
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"An error occurred adding the combatant: {str(e)}")
            return -1
    
        """Add a combatant to the initiative table"""
        print(f"[CombatTracker] _add_combatant called: name={name}, initiative={initiative}, hp={hp}, max_hp={max_hp}, ac={ac}, type={combatant_type}, id={monster_id}")
        logging.debug(f"[CombatTracker] Adding combatant: Name={name}, Init={initiative}, HP={hp}/{max_hp}, AC={ac}, Type={combatant_type}, ID={monster_id}") # Add DEBUG log
        
        # Get current row count
        row = self.initiative_table.rowCount()
        self.initiative_table.insertRow(row)
        
        # Create name item with combatant type stored in user role
        name_item = QTableWidgetItem(name)
        name_item.setData(Qt.UserRole, combatant_type)  # Store type with the name item
        
        # If this is a monster with ID, store the ID in UserRole+2
        if monster_id is not None:
            name_item.setData(Qt.UserRole + 2, monster_id)
            print(f"[CombatTracker] Set monster ID {monster_id} for {name}")
        
        # Ensure no checkbox
        name_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
        self.initiative_table.setItem(row, 0, name_item)
        
        # Set initiative
        init_item = QTableWidgetItem(str(initiative))
        init_item.setData(Qt.DisplayRole, initiative)  # For sorting
        init_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
        self.initiative_table.setItem(row, 1, init_item)
        
        # Set current HP - Make extra sure we're dealing with valid values
        hp_str = str(hp) if hp is not None else "10"
        print(f"[CombatTracker] Setting HP for {name} to {hp_str}")
        hp_item = QTableWidgetItem(hp_str)
        hp_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
        self.initiative_table.setItem(row, 2, hp_item)
        
        # Set Max HP - Make extra sure we're dealing with valid values
        max_hp_str = str(max_hp) if max_hp is not None else "10"
        print(f"[CombatTracker] Setting Max HP for {name} to {max_hp_str}")
        max_hp_item = QTableWidgetItem(max_hp_str)
        max_hp_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
        self.initiative_table.setItem(row, 3, max_hp_item)
        
        # Set AC
        ac_str = str(ac) if ac is not None else "10"
        ac_item = QTableWidgetItem(ac_str)
        ac_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
        self.initiative_table.setItem(row, 4, ac_item)
        
        # Set status as empty initially
        status_item = QTableWidgetItem("")
        status_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
        self.initiative_table.setItem(row, 5, status_item)
        
        # Set concentration as unchecked initially - only column with checkbox
        conc_item = QTableWidgetItem()
        conc_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
        conc_item.setCheckState(Qt.Unchecked)
        self.initiative_table.setItem(row, 6, conc_item)
        
        # Set type (monster, character, etc.) for filtering
        type_item = QTableWidgetItem(combatant_type)
        type_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
        self.initiative_table.setItem(row, 7, type_item)
        
        # Store current row before sorting
        current_row = row
        
        # Sort the initiative order
        self._sort_initiative()
        
        # Verify the final result
        final_hp_item = self.initiative_table.item(row, 2)
        if final_hp_item:
            final_hp = final_hp_item.text()
            print(f"[CombatTracker] Final verification - {name} HP after sorting: {final_hp}")
        
        # After sorting, find this monster's new row by its ID
        sorted_row = -1
        if monster_id is not None:
            sorted_row = self._find_monster_by_id(monster_id)
            if sorted_row >= 0:
                print(f"[CombatTracker] After sorting, monster {name} (ID {monster_id}) is at row {sorted_row}")
            else:
                print(f"[CombatTracker] WARNING: Could not find monster {name} (ID {monster_id}) after sorting")
                sorted_row = row  # Fall back to original row
        
        # Return the row where the combatant was added (post-sorting if monster with ID)
        return sorted_row if sorted_row >= 0 else row
    
        """Find the row of a monster by its unique ID"""
        if monster_id is None:
            return -1
            
        for row in range(self.initiative_table.rowCount()):
            name_item = self.initiative_table.item(row, 0)
            if name_item and name_item.data(Qt.UserRole + 2) == monster_id:
                return row
                
        return -1
    
    def _sort_initiative(self):
        """Sort the initiative list in descending order."""
        # --- Check flag: Prevent sorting during LLM resolution --- 
        if self._is_resolving_combat:
            print("[CombatTracker] _sort_initiative: Skipping sort because _is_resolving_combat is True.")
            return
            
        print(f"[CombatTracker] _sort_initiative ENTRY with {self.initiative_table.rowCount()} rows")
        # Block signals to prevent recursive calls during sorting
        self.initiative_table.blockSignals(True)
        
        try:
            # Get the number of rows
            row_count = self.initiative_table.rowCount()
            if row_count <= 1:
                # Nothing to sort if there's 0 or 1 row
                print("[CombatTracker] _sort_initiative: Nothing to sort (≤1 row)")
                return
                
            # Save all monsters IDs and stats before sorting
            monster_stats = {}
            monster_instance_ids = {}  # NEW: Track instance IDs for each row
            for row in range(row_count):
                name_item = self.initiative_table.item(row, 0)
                if name_item:
                    # Save monster ID if it exists
                    if name_item.data(Qt.UserRole + 2) is not None:
                        monster_id = name_item.data(Qt.UserRole + 2)
                        monster_stats[monster_id] = {
                            "id": monster_id,
                            "name": name_item.text(),
                            "hp": self.initiative_table.item(row, 2).text() if self.initiative_table.item(row, 2) else "10",
                            "max_hp": self.initiative_table.item(row, 3).text() if self.initiative_table.item(row, 3) else "10",
                            "ac": self.initiative_table.item(row, 4).text() if self.initiative_table.item(row, 4) else "10"
                        }
                    
                    # NEW: Store instance ID for this row
                    monster_instance_ids[row] = name_item.data(Qt.UserRole + 2) or f"combatant_{row}"
                    print(f"[CombatTracker] Row {row} has instance ID: {monster_instance_ids[row]}")
            
            # Store pre-sort HP and AC data for verification
            pre_sort_values = {}
            for row in range(row_count):
                name_item = self.initiative_table.item(row, 0)
                hp_item = self.initiative_table.item(row, 2)
                ac_item = self.initiative_table.item(row, 4)
                
                name = name_item.text() if name_item else f"Row {row}"
                hp = hp_item.text() if hp_item else "?"
                ac = ac_item.text() if ac_item else "?"
                
                pre_sort_values[name] = {"hp": hp, "ac": ac, "instance_id": monster_instance_ids.get(row, f"combatant_{row}")}
            
            # Collect all the data from the table first
            print(f"[CombatTracker] Collecting data from {row_count} rows")
            
            # Store all row data before clearing
            rows_data = []
            initiative_values = []
            
            for row in range(row_count):
                # Get the initiative value and row number
                initiative_item = self.initiative_table.item(row, 1)
                if initiative_item and initiative_item.text():
                    try:
                        initiative = int(initiative_item.text())
                    except (ValueError, TypeError):
                        initiative = 0
                else:
                    initiative = 0
                    
                # Gather all row data
                row_data = {}
                for col in range(self.initiative_table.columnCount()):
                    item = self.initiative_table.item(row, col)
                    if item:
                        row_data[col] = {
                            'text': item.text(),
                            'data': item.data(Qt.UserRole),
                            'checkState': item.checkState() if col == 6 else None,  # Only save checkState for concentration column
                            'currentTurn': item.data(Qt.UserRole + 1),
                            'instanceId': item.data(Qt.UserRole + 2) if col == 0 else None  # Save monster ID/instance ID
                        }
                        
                # Add this row's data to our collection
                rows_data.append(row_data)
                initiative_values.append((initiative, row))
                hp_value = row_data.get(2, {}).get('text', '?')
                ac_value = row_data.get(4, {}).get('text', '?')
                instance_id = row_data.get(0, {}).get('instanceId', f"combatant_{row}")
                print(f"[CombatTracker] Row {row}: initiative={initiative}, hp={hp_value}, ac={ac_value}, instance_id={instance_id}")
                
            # Execute the rest of the original sort code
            # Sort the initiative values in descending order
            initiative_values.sort(key=lambda x: x[0], reverse=True)
            
            # Remap original rows to their new position after sorting
            row_map = {old_row: new_row for new_row, (_, old_row) in enumerate(initiative_values)}
            # NEW: Also create reverse mapping
            new_to_old_map = {new_row: old_row for old_row, new_row in row_map.items()}
            
            # Remember the current selection and turn
            current_row = self.initiative_table.currentRow()
            current_turn = self._current_turn if hasattr(self, '_current_turn') else None
            
            # Clear the table (but don't update combat stats yet)
            self.initiative_table.setRowCount(0)
            self.initiative_table.setRowCount(row_count)
            
            # Add the sorted rows back to the table
            for old_row, new_row in row_map.items():
                row_data = rows_data[old_row]
                
                # Debug HP and AC for this row
                hp_value = row_data.get(2, {}).get('text', '?')
                ac_value = row_data.get(4, {}).get('text', '?')
                instance_id = row_data.get(0, {}).get('instanceId', f"combatant_{old_row}")
                print(f"[CombatTracker] Moving HP value: {hp_value} from old_row={old_row} to new_row={new_row}")
                print(f"[CombatTracker] Moving AC value: {ac_value} from old_row={old_row} to new_row={new_row}")
                print(f"[CombatTracker] Moving instance ID: {instance_id} from old_row={old_row} to new_row={new_row}")
                
                for col, item_data in row_data.items():
                    # Create a new item with the right flags for each column
                    new_item = QTableWidgetItem()
                    
                    # Set text data
                    if 'text' in item_data:
                        new_item.setText(item_data['text'])
                    
                    # Set appropriate flags based on column - ENSURE ONLY CONCENTRATION HAS CHECKBOXES
                    if col == 6:  # Concentration column - the only one with checkboxes
                        new_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
                        if 'checkState' in item_data and item_data['checkState'] is not None:
                            new_item.setCheckState(item_data['checkState'])
                        else:
                            new_item.setCheckState(Qt.Unchecked)
                    elif col == 0:  # Name column - should be editable
                        new_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
                    elif col == 1:  # Initiative column - should be editable
                        new_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
                    elif col == 2:  # HP column - should be editable
                        new_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
                    elif col == 3:  # Max HP column - should be editable
                        new_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
                    elif col == 4:  # AC column - should be editable
                        new_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
                    elif col == 5:  # Status column - should be editable
                        new_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable)
                    else:  # Any other columns - make selectable but not editable by default
                        new_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                    
                    # Restore UserRole data (like combatant type)
                    if 'data' in item_data and item_data['data'] is not None:
                        new_item.setData(Qt.UserRole, item_data['data'])
                    
                    # Restore current turn highlight data
                    if 'currentTurn' in item_data and item_data['currentTurn'] is not None:
                        new_item.setData(Qt.UserRole + 1, item_data['currentTurn'])
                    
                    # IMPORTANT: Restore instance ID for the name column
                    if col == 0 and 'instanceId' in item_data and item_data['instanceId'] is not None:
                        new_item.setData(Qt.UserRole + 2, item_data['instanceId'])
                        print(f"[CombatTracker] Set instance ID {item_data['instanceId']} for new_row={new_row}")
                    
                    # Set the item in the table
                    self.initiative_table.setItem(new_row, col, new_item)
            
            # Update current selection and turn if needed
            if current_row >= 0 and current_row < row_count:
                new_current_row = row_map.get(current_row, 0)
                self.initiative_table.setCurrentCell(new_current_row, 0)
            
            if current_turn is not None and current_turn >= 0 and current_turn < row_count:
                self._current_turn = row_map.get(current_turn, 0)
            
            # NEW: Update the self.combatant_manager.combatants_by_id dictionary to keep instance IDs aligned
            if hasattr(self, 'combatants') and isinstance(self.combatant_manager.combatants_by_id, dict):
                new_combatants = {}
                for old_row, combatant_data in self.combatant_manager.combatants_by_id.items():
                    if old_row in row_map:
                        new_row = row_map[old_row]
                        new_combatants[new_row] = combatant_data
                        
                        # If combatant_data is a dictionary, update its instance_id
                        if isinstance(combatant_data, dict):
                            instance_id = monster_instance_ids.get(old_row, f"combatant_{old_row}")
                            combatant_data['instance_id'] = instance_id
                            print(f"[CombatTracker] Updated instance_id in combatants dict: {old_row} -> {new_row} with ID {instance_id}")
                
                self.combatant_manager.combatants_by_id = new_combatants
            
            # Verify HP and AC values after sorting
            post_sort_values = {}
            for row in range(row_count):
                name_item = self.initiative_table.item(row, 0)
                hp_item = self.initiative_table.item(row, 2)
                ac_item = self.initiative_table.item(row, 4)
                
                name = name_item.text() if name_item else f"Row {row}"
                hp = hp_item.text() if hp_item else "?"
                ac = ac_item.text() if ac_item else "?"
                instance_id = name_item.data(Qt.UserRole + 2) if name_item else f"combatant_{row}"
                
                post_sort_values[name] = {"hp": hp, "ac": ac, "instance_id": instance_id}
            
            # Compare pre and post sort values
            for name, pre_values in pre_sort_values.items():
                post_values = post_sort_values.get(name, {"hp": "MISSING", "ac": "MISSING", "instance_id": "MISSING"})
                
                # Check HP
                pre_hp = pre_values["hp"]
                post_hp = post_values["hp"]
                if pre_hp != post_hp:
                    print(f"[CombatTracker] WARNING: HP changed during sort for {name}: {pre_hp} -> {post_hp}")
                else:
                    print(f"[CombatTracker] HP preserved for {name}: {pre_hp}")
                
                # Check AC
                pre_ac = pre_values["ac"]
                post_ac = post_values["ac"]
                if pre_ac != post_ac:
                    print(f"[CombatTracker] WARNING: AC changed during sort for {name}: {pre_ac} -> {post_ac}")
                else:
                    print(f"[CombatTracker] AC preserved for {name}: {pre_ac}")
                    
                # Check instance ID
                pre_instance_id = pre_values["instance_id"]
                post_instance_id = post_values["instance_id"]
                if pre_instance_id != post_instance_id:
                    print(f"[CombatTracker] WARNING: Instance ID changed during sort for {name}: {pre_instance_id} -> {post_instance_id}")
                else:
                    print(f"[CombatTracker] Instance ID preserved for {name}: {pre_instance_id}")

            # At the end of the sort function, add the monster stats verification
            # Schedule verification for all monsters after sorting is complete
            for monster_id, stats in monster_stats.items():
                QTimer.singleShot(100, lambda stats=stats: self._verify_monster_stats(stats))
            
            # Force a UI update - IMPORTANT
            self.initiative_table.viewport().update()
            self.update()  # Update the whole combat tracker panel
        
        except Exception as e:
            print(f"[CombatTracker] ERROR in _sort_initiative: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            # Always unblock signals
            print("[CombatTracker] Unblocking table signals")
            self.initiative_table.blockSignals(False)
            print("[CombatTracker] _sort_initiative completed")
            
            # Force the UI to update one more time
            QApplication.processEvents()  # Process pending events to ensure UI updates
    
    def _quick_damage(self, amount):
        """Apply quick damage to selected combatants"""
        if amount <= 0:
            return
            
        # Get selected rows
        selected_rows = [index.row() for index in 
                        self.initiative_table.selectionModel().selectedRows()]
        
        if not selected_rows:
            if 0 <= self.current_turn < self.initiative_table.rowCount():
                # If no selection, apply to current turn
                selected_rows = [self.current_turn]
            else:
                return
                
        for row in selected_rows:
            hp_item = self.initiative_table.item(row, 2)  # HP is now column 2
            max_hp_item = self.initiative_table.item(row, 3)  # Max HP is column 3
            
            if hp_item:
                try:
                    # Safely get current HP
                    hp_text = hp_item.text().strip()
                    current_hp = int(hp_text) if hp_text else 0
                    max_hp = int(max_hp_item.text()) if max_hp_item and max_hp_item.text() else current_hp
                    
                    new_hp = max(current_hp - amount, 0)
                    hp_item.setText(str(new_hp))
                    
                    # Check for concentration
                    if amount > 0:
                        self._check_concentration(row, amount)
                        
                    # Check for death saves if 0 HP
                    if new_hp == 0:
                        name = self.initiative_table.item(row, 0).text()
                        QMessageBox.information(
                            self,
                            "HP Reduced to 0",
                            f"{name} is down! Remember to track death saves."
                        )
                except ValueError:
                    # Handle invalid HP value
                    pass
    
    def _quick_heal(self, amount):
        """Apply quick healing to selected combatants"""
        if amount <= 0:
            return
            
        # Get selected rows
        selected_rows = [index.row() for index in 
                        self.initiative_table.selectionModel().selectedRows()]
        
        if not selected_rows:
            if 0 <= self.current_turn < self.initiative_table.rowCount():
                # If no selection, apply to current turn
                selected_rows = [self.current_turn]
            else:
                return
                
        for row in selected_rows:
            hp_item = self.initiative_table.item(row, 2)  # HP is now column 2
            max_hp_item = self.initiative_table.item(row, 3)  # Max HP is column 3
            
            if hp_item and max_hp_item:
                try:
                    # Safely get current HP
                    hp_text = hp_item.text().strip()
                    current_hp = int(hp_text) if hp_text else 0
                    
                    # Get max HP from the max HP column
                    max_hp_text = max_hp_item.text().strip()
                    max_hp = int(max_hp_text) if max_hp_text else 999
                    
                    new_hp = min(current_hp + amount, max_hp)
                    hp_item.setText(str(new_hp))
                except ValueError:
                    # Handle invalid HP value
                    pass
    
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
    
    def _handle_cell_changed(self, row, column):
        """Handle when a cell in the initiative table is changed."""
        # Prevent handling during program-initiated changes
        if self.initiative_table.signalsBlocked():
            return
            
        # Prevent recursive calls
        self.initiative_table.blockSignals(True)
        
        try:
            # Get the updated item
            item = self.initiative_table.item(row, column)
            if not item:
                return
                
            # Only sort if the Initiative column (column 1) changed
            if column == 1:
                try:
                    # Validate the initiative value
                    int(item.text()) # Try converting to int
                    if self.initiative_table.rowCount() > 1:
                        self._sort_initiative()
                except (ValueError, TypeError):
                    item.setText("0") # Reset invalid input

            # Handle Max HP changes (column 3) without sorting
            elif column == 3:
                hp_item = self.initiative_table.item(row, 2)
                max_hp_item = self.initiative_table.item(row, 3)
                if hp_item and max_hp_item:
                    try:
                        current_hp = int(hp_item.text())
                        max_hp = int(max_hp_item.text())
                        if current_hp > max_hp:
                            hp_item.setText(str(max_hp))
                    except (ValueError, TypeError):
                        pass # Ignore if values aren't integers

            # Update combatant data dictionary if it exists
            if row in self.combatant_manager.combatants_by_id:
                self._update_combatant_hp_and_status(row)
        
        finally:
            self.initiative_table.blockSignals(False)
    
    def _update_combatant_hp_and_status(self, row):
        """Update the HP and status of a combatant in the data dictionary based on the table"""
        if row not in self.combatant_manager.combatants_by_id:
            return
            
        # Get HP from table
        hp_item = self.initiative_table.item(row, 2)  # Current HP
        max_hp_item = self.initiative_table.item(row, 3)  # Max HP
        
        if hp_item:
            hp_text = hp_item.text().strip()
            try:
                hp = int(hp_text) if hp_text else 0
                
                # Update the hp in the combatant data if it's a dictionary
                if isinstance(self.combatant_manager.combatants_by_id[row], dict):
                    self.combatant_manager.combatants_by_id[row]['current_hp'] = hp
                elif hasattr(self.combatant_manager.combatants_by_id[row], 'current_hp'):
                    self.combatant_manager.combatants_by_id[row].current_hp = hp
            except (ValueError, TypeError):
                # Ignore if not a valid number
                pass
        
        # Update max HP if available
        if max_hp_item:
            max_hp_text = max_hp_item.text().strip()
            try:
                max_hp = int(max_hp_text) if max_hp_text else 0
                
                # Update the max_hp in the combatant data if it's a dictionary
                if isinstance(self.combatant_manager.combatants_by_id[row], dict):
                    self.combatant_manager.combatants_by_id[row]['max_hp'] = max_hp
                elif hasattr(self.combatant_manager.combatants_by_id[row], 'max_hp'):
                    self.combatant_manager.combatants_by_id[row].max_hp = max_hp
            except (ValueError, TypeError):
                # Ignore if not a valid number
                pass
                
        # Get status from table
        status_item = self.initiative_table.item(row, 5)  # Status is now column 5
        if status_item:
            status = status_item.text()
            
            # Update the status in the combatant data if it's a dictionary
            if isinstance(self.combatant_manager.combatants_by_id[row], dict):
                if 'conditions' not in self.combatant_manager.combatants_by_id[row]:
                    self.combatant_manager.combatants_by_id[row]['conditions'] = []
                if status and status not in self.combatant_manager.combatants_by_id[row]['conditions']:
                    self.combatant_manager.combatants_by_id[row]['conditions'].append(status)
                elif not status and self.combatant_manager.combatants_by_id[row]['conditions']:
                    self.combatant_manager.combatants_by_id[row]['conditions'] = []
            elif hasattr(self.combatant_manager.combatants_by_id[row], 'conditions'):
                pass
    
    def _next_turn(self):
        """Move to the next combatant's turn"""
        if self.initiative_table.rowCount() == 0:
            return
        
        # Set combat as started when first advancing turns
        if not self.combat_started:
            self.combat_started = True
        
        # Store the index of the last combatant
        last_combatant_index = self.initiative_table.rowCount() - 1
        
        # Check if the current turn is the last combatant
        if self.current_turn == last_combatant_index:
            # End of the round: Increment round, reset turn to 0
            self.current_turn = 0
            self.current_round += 1
            self.round_spin.setValue(self.current_round)
            self._update_game_time()
            print(f"--- End of Round {self.current_round - 1}, Starting Round {self.current_round} ---") # Debug
        else:
            # Not the end of the round: Just advance to the next combatant
            self.current_turn += 1
        
        # Highlight the new current combatant
        self._update_highlight()
        
        # Log the turn change
        if self.initiative_table.rowCount() > 0 and self.current_turn < self.initiative_table.rowCount():
            combatant_name = self.initiative_table.item(self.current_turn, 0).text()
            self._log_combat_action("Initiative", combatant_name, "started their turn")
            
        # If this is the first turn of a new round, log the round start
        if self.current_turn == 0:
            self._log_combat_action("Initiative", f"Round {self.current_round}", "started")
    
    def _update_highlight(self):
        """Update the highlight state using item data and trigger repaint via dataChanged."""
        rows = self.initiative_table.rowCount()
        if rows == 0:
            return

        # Clear the data from the previous turn's row
        if 0 <= self.previous_turn < rows:
            for col in range(self.initiative_table.columnCount()):
                item = self.initiative_table.item(self.previous_turn, col)
                if item:
                    item.setData(Qt.UserRole + 1, False) # Use setData with Boolean False
            # Emit dataChanged for the previous row to trigger delegate repaint
            start_index = self.initiative_table.model().index(self.previous_turn, 0)
            end_index = self.initiative_table.model().index(self.previous_turn, self.initiative_table.columnCount() - 1)
            self.initiative_table.model().dataChanged.emit(start_index, end_index, [Qt.UserRole + 1])

        # Set the data on the current turn's row
        if 0 <= self.current_turn < rows:
            for col in range(self.initiative_table.columnCount()):
                item = self.initiative_table.item(self.current_turn, col)
                if item:
                    item.setData(Qt.UserRole + 1, True) # Use setData with Boolean True
            # Emit dataChanged for the current row to trigger delegate repaint
            start_index = self.initiative_table.model().index(self.current_turn, 0)
            end_index = self.initiative_table.model().index(self.current_turn, self.initiative_table.columnCount() - 1)
            self.initiative_table.model().dataChanged.emit(start_index, end_index, [Qt.UserRole + 1])
            
            # Ensure the current row is visible
            self.initiative_table.scrollToItem(
                self.initiative_table.item(self.current_turn, 0),
                QAbstractItemView.EnsureVisible
            )