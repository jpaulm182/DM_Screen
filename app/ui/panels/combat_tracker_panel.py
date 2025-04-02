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
"""

from PySide6.QtWidgets import (
    QTableWidget, QTableWidgetItem, QHeaderView, QPushButton,
    QLineEdit, QSpinBox, QHBoxLayout, QVBoxLayout, QComboBox,
    QLabel, QCheckBox, QMenu, QMessageBox, QDialog, QDialogButtonBox,
    QGroupBox, QWidget, QStyledItemDelegate, QStyle, QToolButton
)
from PySide6.QtCore import Qt, QTimer, Signal, Slot, QSize
from PySide6.QtGui import QAction, QColor, QIcon, QKeySequence, QBrush, QPalette
import random

from app.ui.panels.base_panel import BasePanel

# D&D 5e Conditions
CONDITIONS = [
    "Blinded", "Charmed", "Deafened", "Frightened", "Grappled",
    "Incapacitated", "Invisible", "Paralyzed", "Petrified",
    "Poisoned", "Prone", "Restrained", "Stunned", "Unconscious"
]

# --- Custom Delegates for Table Cell Display ---

class CurrentTurnDelegate(QStyledItemDelegate):
    '''Delegate to handle custom painting for the current turn row.'''
    def paint(self, painter, option, index):
        # Check if this item belongs to the current turn using UserRole + 1
        is_current = index.data(Qt.UserRole + 1)
        
        if is_current == True: # Explicit check for True
            # Save painter state
            painter.save()
            
            # Define highlight colors
            highlight_bg = QColor(0, 51, 102) # Dark blue background (#003366)
            highlight_fg = QColor(Qt.white) # White text
            
            # Fill background
            painter.fillRect(option.rect, highlight_bg)
            
            # Set text color
            pen = painter.pen()
            pen.setColor(highlight_fg)
            painter.setPen(pen)
            
            # Draw text (adjusting rect slightly for padding)
            text_rect = option.rect.adjusted(5, 0, -5, 0) # Add horizontal padding
            painter.drawText(text_rect, option.displayAlignment, index.data(Qt.DisplayRole))
            
            # Restore painter state
            painter.restore()
        else:
            # Default painting for non-current turns
            super().paint(painter, option, index)

class HPUpdateDelegate(QStyledItemDelegate):
    """Delegate to handle HP updates with quick buttons"""
    
    # Signal to notify HP changes
    hpChanged = Signal(int, int)  # row, new_hp
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.buttons = {}  # Store buttons for each cell
    
    def createEditor(self, parent, option, index):
        """Create editor for HP cell (SpinBox)"""
        editor = QSpinBox(parent)
        editor.setMinimum(0)
        editor.setMaximum(999)
        
        # Get max HP from UserRole
        max_hp = index.data(Qt.UserRole) or 999
        editor.setMaximum(max_hp)
        
        return editor
    
    def setEditorData(self, editor, index):
        """Set editor data from the model"""
        value = int(index.data(Qt.DisplayRole) or 0)
        editor.setValue(value)
    
    def setModelData(self, editor, model, index):
        """Set model data from the editor"""
        value = editor.value()
        model.setData(index, str(value), Qt.DisplayRole)
        
        # Emit signal for hp changed
        self.hpChanged.emit(index.row(), value)

# --- Dialog Classes --- 

class DamageDialog(QDialog):
    """Dialog for applying damage or healing"""
    def __init__(self, parent=None, is_healing=False):
        super().__init__(parent)
        self.is_healing = is_healing
        self.setWindowTitle("Apply Healing" if is_healing else "Apply Damage")
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout()
        
        # Amount input
        amount_layout = QHBoxLayout()
        amount_layout.addWidget(QLabel("Amount:"))
        self.amount_spin = QSpinBox()
        self.amount_spin.setRange(0, 999)
        amount_layout.addWidget(self.amount_spin)
        layout.addLayout(amount_layout)
        
        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        self.setLayout(layout)
    
    def get_amount(self):
        """Get the entered amount"""
        return self.amount_spin.value()

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

class CombatTrackerPanel(BasePanel):
    """Panel for tracking combat initiative, HP, and conditions"""
    
    # Signal to emit when combat resolution is complete (or failed)
    # Carries the result dict and error string (one will be None)
    resolution_complete = Signal(dict, str)
    
    def __init__(self, app_state):
        """Initialize the combat tracker panel"""
        # Initialize combat state before calling super().__init__
        self.current_round = 1
        self.current_turn = 0
        self.previous_turn = -1 # Track the previous turn index for highlighting
        self.elapsed_time = 0  # Time in seconds
        self.combat_started = False  # Track if combat has started
        
        # Initialize tracking sets/dicts
        self.concentrating = set()  # Set of row indices tracking concentration
        self.death_saves = {}  # Dictionary of row indices to death saves state
        
        # Initialize timer
        self.timer = QTimer()
        
        # Now call super().__init__ which will call _setup_ui
        super().__init__(app_state, "Combat Tracker")
        
        # Connect timer after UI is set up
        self.timer.timeout.connect(self._update_timer)
        
        # Connect the resolution complete signal to the UI processing slot
        self.resolution_complete.connect(self._process_resolution_ui)
        
    def _setup_ui(self):
        """Set up the combat tracker UI"""
        # Add keyboard shortcuts
        next_turn_shortcut = QKeySequence(Qt.CTRL | Qt.Key_Space)
        self.next_turn_action = QAction("Next Combatant", self)
        self.next_turn_action.setShortcut(next_turn_shortcut)
        self.next_turn_action.triggered.connect(self._next_turn)
        self.addAction(self.next_turn_action)

        sort_shortcut = QKeySequence(Qt.CTRL | Qt.Key_S)
        self.sort_action = QAction("Sort Initiative", self)
        self.sort_action.setShortcut(sort_shortcut)
        self.sort_action.triggered.connect(self._sort_initiative)
        self.addAction(self.sort_action)

        timer_shortcut = QKeySequence(Qt.CTRL | Qt.Key_T)
        self.timer_action = QAction("Toggle Timer", self)
        self.timer_action.setShortcut(timer_shortcut)
        self.timer_action.triggered.connect(self._toggle_timer)
        self.addAction(self.timer_action)
        
        # HP adjustment shortcuts
        damage_1_shortcut = QKeySequence(Qt.Key_1)
        self.damage_1_action = QAction("Damage 1", self)
        self.damage_1_action.setShortcut(damage_1_shortcut)
        self.damage_1_action.triggered.connect(lambda: self._quick_damage(1))
        self.addAction(self.damage_1_action)
        
        damage_5_shortcut = QKeySequence(Qt.Key_2)
        self.damage_5_action = QAction("Damage 5", self)
        self.damage_5_action.setShortcut(damage_5_shortcut)
        self.damage_5_action.triggered.connect(lambda: self._quick_damage(5))
        self.addAction(self.damage_5_action)
        
        damage_10_shortcut = QKeySequence(Qt.Key_3)
        self.damage_10_action = QAction("Damage 10", self)
        self.damage_10_action.setShortcut(damage_10_shortcut)
        self.damage_10_action.triggered.connect(lambda: self._quick_damage(10))
        self.addAction(self.damage_10_action)
        
        heal_1_shortcut = QKeySequence(Qt.SHIFT | Qt.Key_1)
        self.heal_1_action = QAction("Heal 1", self)
        self.heal_1_action.setShortcut(heal_1_shortcut)
        self.heal_1_action.triggered.connect(lambda: self._quick_heal(1))
        self.addAction(self.heal_1_action)
        
        heal_5_shortcut = QKeySequence(Qt.SHIFT | Qt.Key_2)
        self.heal_5_action = QAction("Heal 5", self)
        self.heal_5_action.setShortcut(heal_5_shortcut)
        self.heal_5_action.triggered.connect(lambda: self._quick_heal(5))
        self.addAction(self.heal_5_action)
        
        heal_10_shortcut = QKeySequence(Qt.SHIFT | Qt.Key_3)
        self.heal_10_action = QAction("Heal 10", self)
        self.heal_10_action.setShortcut(heal_10_shortcut)
        self.heal_10_action.triggered.connect(lambda: self._quick_heal(10))
        self.addAction(self.heal_10_action)

        # Create main layout
        main_layout = QVBoxLayout()
        
        # Add shortcuts info
        shortcuts_label = QLabel(
            "Shortcuts: Next Combatant (Ctrl+Space) | Sort (Ctrl+S) | Timer (Ctrl+T) | "
            "Damage (1,2,3) | Heal (Shift+1,2,3)"
        )
        shortcuts_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(shortcuts_label)
        
        # Control area
        control_layout = self._setup_control_area()
        main_layout.addLayout(control_layout)
        
        # Initiative table
        self.initiative_table = QTableWidget(0, 7)  # Added Concentration column
        self.initiative_table.setHorizontalHeaderLabels([
            "Name", "Initiative", "HP", "AC", "Status", "Concentration", "Notes"
        ])
        
        # Set column widths
        header = self.initiative_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)  # Name
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Initiative
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # HP
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # AC
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # Status
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)  # Concentration
        header.setSectionResizeMode(6, QHeaderView.Stretch)  # Notes
        
        # Context menu
        self.initiative_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.initiative_table.customContextMenuRequested.connect(self._show_context_menu)
        
        # Enable item editing for HP column
        self.initiative_table.setEditTriggers(QTableWidget.DoubleClicked | QTableWidget.SelectedClicked)
        
        # Set HP column delegate for direct editing
        self.hp_delegate = HPUpdateDelegate(self)
        self.hp_delegate.hpChanged.connect(self._hp_changed)
        self.initiative_table.setItemDelegateForColumn(2, self.hp_delegate)
        
        main_layout.addWidget(self.initiative_table)
        
        # Add combatant controls
        add_layout = self._setup_add_combatant_controls()
        main_layout.addLayout(add_layout)
        
        # Sort button
        sort_button = QPushButton("Sort Initiative")
        sort_button.clicked.connect(self._sort_initiative)
        main_layout.addWidget(sort_button)
        
        # Set the main layout
        self.setLayout(main_layout)
        
        # Initialize the table with proper size
        self.initiative_table.horizontalHeader().setStretchLastSection(True)
        self.initiative_table.verticalHeader().setVisible(False)
        self.initiative_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.initiative_table.setSelectionMode(QTableWidget.ExtendedSelection)
        
        # Apply custom stylesheet for basic appearance (delegate handles highlight)
        self.initiative_table.setStyleSheet('''
            QTableWidget {
                alternate-background-color: #f8f8f8; /* Very light gray for alternates */
                background-color: #ffffff; /* White base */
                gridline-color: #e0e0e0; /* Lighter gray grid lines */
                selection-background-color: #a0c4ff; /* Color for selected row (non-active turn) */
                selection-color: black; /* Text color for selected row */
            }
            QTableWidget::item {
                padding: 5px; /* Add some padding */
                color: black; /* Default text color */
                /* Alternating background handled by QTableWidget */
            }
            /* Highlight rule removed - handled by delegate */
            /* QTableWidget::item[is_current_turn="true"] { ... } */
        ''')
        
        # Set the custom delegate for painting
        self.initiative_table.setItemDelegate(CurrentTurnDelegate(self.initiative_table))
        
        # Set minimum sizes
        self.setMinimumSize(800, 400)
        self.initiative_table.setMinimumHeight(200)
    
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
        self.fast_resolve_button.clicked.connect(self._fast_resolve_combat)
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
        
        add_button = QPushButton("Add")
        add_button.clicked.connect(self._add_combatant)
        add_layout.addWidget(add_button)
        
        return add_layout
    
    def _add_combatant(self, name, initiative, hp, ac):
        """Add a new combatant to initiative order"""
        table = self.initiative_table
        row = table.rowCount()
        table.insertRow(row)
        
        # Name
        name_item = QTableWidgetItem(name)
        table.setItem(row, 0, name_item)
        
        # Initiative
        init_item = QTableWidgetItem(str(initiative))
        init_item.setTextAlignment(Qt.AlignCenter)
        table.setItem(row, 1, init_item)
        
        # HP
        hp_item = QTableWidgetItem(str(hp))
        hp_item.setTextAlignment(Qt.AlignCenter)
        hp_item.setData(Qt.UserRole, hp)  # Store max HP
        table.setItem(row, 2, hp_item)
        
        # AC
        ac_item = QTableWidgetItem(str(ac))
        ac_item.setTextAlignment(Qt.AlignCenter)
        table.setItem(row, 3, ac_item)
        
        # Status - empty initially
        table.setItem(row, 4, QTableWidgetItem(""))
        
        # Concentration checkbox
        conc_item = QTableWidgetItem()
        conc_item.setCheckState(Qt.Unchecked)
        conc_item.setTextAlignment(Qt.AlignCenter)
        table.setItem(row, 5, conc_item)
        
        # Empty notes
        table.setItem(row, 6, QTableWidgetItem(""))
        
        # Sort after adding
        self._sort_initiative()
        
        # Return the row where it was inserted after sorting
        for row in range(table.rowCount()):
            if table.item(row, 0).text() == name and table.item(row, 1).text() == str(initiative):
                return row
        
        return -1  # Not found (shouldn't happen)
    
    def _sort_initiative(self):
        """Sort the initiative tracker by initiative value (descending)"""
        if self.initiative_table.rowCount() <= 1:
            return
        
        # Get current selection
        selected_rows = [index.row() for index in self.initiative_table.selectionModel().selectedRows()]
        selected_names = [self.initiative_table.item(row, 0).text() for row in selected_rows]
        
        # Remember current turn
        current_name = ""
        if 0 <= self.current_turn < self.initiative_table.rowCount():
            current_name = self.initiative_table.item(self.current_turn, 0).text()
        
        # Create a list of rows with their initiative values
        rows = []
        for row in range(self.initiative_table.rowCount()):
            init_item = self.initiative_table.item(row, 1)
            if init_item:
                init_value = float(init_item.text())
                rows.append((row, init_value))
        
        # Sort by initiative (highest first)
        rows.sort(key=lambda x: (x[1], random.random()), reverse=True)
        
        # Remember items to restore
        items = []
        for old_row, _ in rows:
            row_items = []
            for col in range(self.initiative_table.columnCount()):
                item = self.initiative_table.takeItem(old_row, col)
                # Clone item to avoid issues
                new_item = QTableWidgetItem()
                new_item.setText(item.text())
                if hasattr(item, 'checkState'):
                    new_item.setCheckState(item.checkState())
                for role in [Qt.UserRole, Qt.UserRole + 1]:
                    if item.data(role) is not None:
                        new_item.setData(role, item.data(role))
                new_item.setTextAlignment(item.textAlignment())
                row_items.append(new_item)
            items.append(row_items)
        
        # Clear the table and add items back in sorted order
        self.initiative_table.setRowCount(0)
        for row_items in items:
            row = self.initiative_table.rowCount()
            self.initiative_table.insertRow(row)
            for col, item in enumerate(row_items):
                self.initiative_table.setItem(row, col, item)
        
        # Restore selection
        if selected_names:
            self.initiative_table.clearSelection()
            for row in range(self.initiative_table.rowCount()):
                name = self.initiative_table.item(row, 0).text()
                if name in selected_names:
                    self.initiative_table.selectRow(row)
        
        # Update current turn index if combat has started
        if current_name and self.combat_started:
            for row in range(self.initiative_table.rowCount()):
                if self.initiative_table.item(row, 0).text() == current_name:
                    self.current_turn = row
                    break
        
        # Update the highlighting
        self._update_highlight()
    
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
            hp_item = self.initiative_table.item(row, 2)
            if hp_item:
                current_hp = int(hp_item.text())
                max_hp = hp_item.data(Qt.UserRole)
                
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
            hp_item = self.initiative_table.item(row, 2)
            if hp_item:
                current_hp = int(hp_item.text())
                max_hp = hp_item.data(Qt.UserRole)
                
                new_hp = min(current_hp + amount, max_hp)
                hp_item.setText(str(new_hp))
    
    def _hp_changed(self, row, new_hp):
        """Handle HP changes from delegate editing"""
        if 0 <= row < self.initiative_table.rowCount():
            # Get current HP
            hp_item = self.initiative_table.item(row, 2)
            if hp_item:
                # Already updated via setModelData, check for special cases
                if new_hp == 0:
                    name = self.initiative_table.item(row, 0).text()
                    QMessageBox.information(
                        self,
                        "HP Reduced to 0",
                        f"{name} is down! Remember to track death saves."
                    )
    
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
                QTableWidget.ScrollHint.EnsureVisible
            )

        # Update the style to reflect property changes. 
        # setProperty should handle this, but polish/unpolish is safer.
        self.initiative_table.style().unpolish(self.initiative_table)
        self.initiative_table.style().polish(self.initiative_table)
        self.initiative_table.viewport().update() 

        # Update previous_turn for the next call
        self.previous_turn = self.current_turn
    
    def _show_context_menu(self, position):
        """Show custom context menu for the initiative table"""
        # Get row under cursor
        row = self.initiative_table.rowAt(position.y())
        if row < 0:
            return
        
        # Create menu
        menu = QMenu(self)
        
        # Add menu actions
        remove_action = QAction("Remove", self)
        remove_action.triggered.connect(self._remove_selected)
        menu.addAction(remove_action)
        
        # HP adjustment submenu
        hp_menu = menu.addMenu("Adjust HP")
        
        # Quick damage options
        damage_menu = hp_menu.addMenu("Damage")
        d1_action = damage_menu.addAction("1 HP")
        d1_action.triggered.connect(lambda: self._quick_damage(1))
        d5_action = damage_menu.addAction("5 HP")
        d5_action.triggered.connect(lambda: self._quick_damage(5))
        d10_action = damage_menu.addAction("10 HP")
        d10_action.triggered.connect(lambda: self._quick_damage(10))
        
        damage_custom = damage_menu.addAction("Custom...")
        damage_custom.triggered.connect(lambda: self._apply_damage(False))
        
        # Quick healing options
        heal_menu = hp_menu.addMenu("Heal")
        h1_action = heal_menu.addAction("1 HP")
        h1_action.triggered.connect(lambda: self._quick_heal(1))
        h5_action = heal_menu.addAction("5 HP")
        h5_action.triggered.connect(lambda: self._quick_heal(5))
        h10_action = heal_menu.addAction("10 HP")
        h10_action.triggered.connect(lambda: self._quick_heal(10))
        
        heal_custom = heal_menu.addAction("Custom...")
        heal_custom.triggered.connect(lambda: self._apply_damage(True))
        
        menu.addSeparator()
        
        # Death saves
        hp_item = self.initiative_table.item(row, 2)
        if hp_item and int(hp_item.text()) <= 0:
            death_saves = QAction("Death Saves...", self)
            death_saves.triggered.connect(lambda: self._manage_death_saves(row))
            menu.addAction(death_saves)
            menu.addSeparator()
        
        # Status submenu
        status_menu = menu.addMenu("Set Status")
        status_menu.addAction("None").triggered.connect(lambda: self._set_status(""))
        
        for condition in CONDITIONS:
            action = status_menu.addAction(condition)
            action.triggered.connect(lambda checked, c=condition: self._set_status(c))
        
        # Show the menu
        menu.exec_(self.initiative_table.mapToGlobal(position))
    
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
                hp_item = self.initiative_table.item(row, 2)
                if not hp_item:
                    continue
                    
                name_item = self.initiative_table.item(row, 0)
                if not name_item:
                    continue
                    
                combatant_name = name_item.text()
                
                try:
                    current_hp = int(hp_item.text() or "0")
                    
                    if is_healing:
                        new_hp = current_hp + amount
                        max_hp = hp_item.data(Qt.UserRole) or 0
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
                        # Mark as unconscious
                        status_item = self.initiative_table.item(row, 4)
                        if status_item:
                            old_status = status_item.text()
                            status_item.setText("Unconscious")
                            
                            if old_status != "Unconscious":
                                # Log status change
                                self._log_combat_action(
                                    "Status Effect", 
                                    "DM", 
                                    "applied status", 
                                    combatant_name, 
                                    "Unconscious"
                                )
                        
                        # Check if player character (has max HP) for death saves
                        max_hp = hp_item.data(Qt.UserRole)
                        if max_hp:
                            # Set up death saves tracking if not already
                            if row not in self.death_saves:
                                self.death_saves[row] = {"successes": 0, "failures": 0}
                except ValueError:
                    # Handle invalid HP value
                    pass
    
    def _check_concentration(self, row, damage):
        """Check if concentration is maintained after taking damage"""
        conc_item = self.initiative_table.item(row, 5)
        if conc_item and conc_item.checkState() == Qt.Checked:
            dc = max(10, damage // 2)
            name = self.initiative_table.item(row, 0).text()
            
            # Roll the concentration check
            roll = random.randint(1, 20)
            success = roll >= dc
            
            # Log concentration check
            self._log_combat_action(
                "Status Effect", 
                name, 
                "rolled concentration check", 
                result=f"DC {dc}, Roll: {roll}, {'Success' if success else 'Failure'}"
            )
            
            # If concentration check failed
            if not success:
                conc_item.setCheckState(Qt.Unchecked)
                self.concentrating.discard(row)
                
                # Log concentration lost
                self._log_combat_action(
                    "Status Effect", 
                    name, 
                    "lost concentration", 
                    result="Failed check"
                )
                
                # Show message
                QMessageBox.information(
                    self,
                    "Concentration Lost",
                    f"{name} failed DC {dc} concentration check with roll of {roll}."
                )
            else:
                # Show message for successful check
                QMessageBox.information(
                    self,
                    "Concentration Maintained",
                    f"{name} passed DC {dc} concentration check with roll of {roll}."
                )
    
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
                        
                        # Update status to stable
                        status_item = self.initiative_table.item(row, 4)
                        if status_item:
                            status_item.setText("Stable")
                            
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
                        
                        # Update status to dead
                        status_item = self.initiative_table.item(row, 4)
                        if status_item:
                            status_item.setText("Dead")
                    else:
                        self._log_combat_action(
                            "Death Save", 
                            name, 
                            "updated death saves", 
                            result=f"{successes} successes, {failures} failures"
                        )
    
    def _set_status(self, status):
        """Apply a status condition to selected combatants"""
        # Get selected rows
        selected_rows = set(index.row() for index in self.initiative_table.selectedIndexes())
        if not selected_rows:
            return
        
        # Apply status to each selected row
        for row in selected_rows:
            if row < self.initiative_table.rowCount():
                status_item = self.initiative_table.item(row, 4)
                if status_item:
                    status_item.setText(status)
                
                # Log status change if there's a name
                name_item = self.initiative_table.item(row, 0)
                if name_item:
                    name = name_item.text()
                    
                    # Log status change
                    self._log_combat_action(
                        "Status Effect", 
                        "DM", 
                        "applied status", 
                        name, 
                        status
                    )
    
    def _round_changed(self, value):
        """Handle round number change"""
        self.current_round = value
        self._update_game_time()
    
    def _toggle_timer(self):
        """Toggle the combat timer"""
        if self.timer.isActive():
            self.timer.stop()
            self.timer_button.setText("Start")
        else:
            self.timer.start(1000)  # Update every second
            self.timer_button.setText("Stop")
    
    def _update_timer(self):
        """Update the combat timer display"""
        self.elapsed_time += 1
        hours = self.elapsed_time // 3600
        minutes = (self.elapsed_time % 3600) // 60
        seconds = self.elapsed_time % 60
        self.timer_label.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
    
    def _roll_initiative(self):
        """Roll initiative for the current combatant"""
        from random import randint
        modifier = self.init_mod_input.value()
        roll = randint(1, 20)
        total = roll + modifier
        self.initiative_input.setValue(total)
        
        # Show roll details
        QMessageBox.information(
            self,
            "Initiative Roll",
            f"Roll: {roll}\nModifier: {modifier:+d}\nTotal: {total}"
        )
        
        # Log the initiative roll if a name is entered
        name = self.name_input.text()
        if name:
            self._log_combat_action(
                "Initiative", 
                name, 
                "rolled initiative", 
                result=f"{roll} + {modifier} = {total}"
            )
    
    def _update_game_time(self):
        """Update the in-game time display"""
        # In D&D 5e, a round is 6 seconds
        total_seconds = (self.current_round - 1) * 6
        minutes = total_seconds // 60
        self.game_time_label.setText(
            f"{self.current_round - 1} rounds ({minutes} minutes)"
        )
    
    def _reset_combat(self):
        """Reset the entire combat tracker to its initial state."""
        # Log combat reset
        self._log_combat_action(
            "Other", 
            "DM", 
            "reset combat", 
            result="Combat tracker reset to initial state"
        )
        
        reply = QMessageBox.question(
            self,
            'Reset Combat',
            "Are you sure you want to reset the combat tracker? \nThis will clear all combatants and reset the round/timer.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Clear the table
            self.initiative_table.setRowCount(0)
            
            # Reset combat state variables
            self.current_round = 1
            self.current_turn = 0
            self.previous_turn = -1
            self.elapsed_time = 0
            self.combat_started = False
            self.death_saves.clear()
            self.concentrating.clear()
            
            # Reset UI elements
            self.round_spin.setValue(self.current_round)
            if self.timer.isActive():
                self.timer.stop()
            self.timer_label.setText("00:00:00")
            self.timer_button.setText("Start")
            self._update_game_time()
    
    def _restart_combat(self):
        """Restart the current combat (reset turn/round counter but keep combatants)."""
        # Log combat restart
        self._log_combat_action(
            "Other", 
            "DM", 
            "restarted combat", 
            result="Combat restarted with same combatants"
        )
        
        if self.initiative_table.rowCount() == 0:
            QMessageBox.information(self, "Restart Combat", "No combatants to restart.")
            return
            
        reply = QMessageBox.question(
            self,
            'Restart Combat',
            "Are you sure you want to restart the combat? \nThis will reset HP, status, round, and timer, but keep all combatants.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Reset combat state variables
            self.current_round = 1
            self.current_turn = 0
            self.previous_turn = -1
            self.elapsed_time = 0
            self.combat_started = False
            self.death_saves.clear()
            self.concentrating.clear()
            
            # Reset UI elements
            self.round_spin.setValue(self.current_round)
            if self.timer.isActive():
                self.timer.stop()
            self.timer_label.setText("00:00:00")
            self.timer_button.setText("Start")
            self._update_game_time()
            
            # Reset combatant state in the table
            for row in range(self.initiative_table.rowCount()):
                # Reset HP to max
                hp_item = self.initiative_table.item(row, 2)
                if hp_item:
                    max_hp = hp_item.data(Qt.UserRole)
                    if max_hp:
                        hp_item.setText(str(max_hp))
                    else: # Fallback if max_hp wasn't stored
                        hp_item.setText("1") 
                        
                # Clear status
                status_item = self.initiative_table.item(row, 4)
                if status_item:
                    status_item.setText("")
                    
                # Reset concentration
                conc_item = self.initiative_table.item(row, 5)
                if conc_item:
                    conc_item.setCheckState(Qt.Unchecked)
            
            # Re-sort based on original initiative (just in case)
            # And update highlight to the first combatant
            self._sort_initiative()
    
    def _fast_resolve_combat(self):
        """Use LLM to resolve the current combat encounter."""
        # Log fast resolve request
        self._log_combat_action(
            "Other", 
            "DM", 
            "requested fast combat resolution"
        )
        
        # Check if combat resolver is available
        if not hasattr(self.app_state, 'combat_resolver'):
            QMessageBox.warning(self, "Error", "Combat Resolver service not available.")
            return

        # Gather current combat state
        combat_state = self._gather_combat_state()
        if not combat_state or not combat_state.get("combatants"):
            QMessageBox.information(self, "Fast Resolve", "No combatants in the tracker to resolve.")
            return
            
        # Disable button while processing
        self.fast_resolve_button.setEnabled(False)
        self.fast_resolve_button.setText("Resolving...")

        # Call the resolver asynchronously
        self.app_state.combat_resolver.resolve_combat_async(
            combat_state,
            self._handle_resolution_result
        )
    
    def _gather_combat_state(self):
        """Gather the current state of the combat from the table."""
        combatants = []
        for row in range(self.initiative_table.rowCount()):
            combatant = {
                "name": self.initiative_table.item(row, 0).text() if self.initiative_table.item(row, 0) else "Unknown",
                "initiative": int(self.initiative_table.item(row, 1).text() or "0") if self.initiative_table.item(row, 1) else 0,
                "hp": int(self.initiative_table.item(row, 2).text() or "0") if self.initiative_table.item(row, 2) else 0,
                "max_hp": self.initiative_table.item(row, 2).data(Qt.UserRole) if self.initiative_table.item(row, 2) else 0,
                "ac": int(self.initiative_table.item(row, 3).text() or "10") if self.initiative_table.item(row, 3) else 10,
                "status": self.initiative_table.item(row, 4).text() if self.initiative_table.item(row, 4) else "",
                "concentration": self.initiative_table.item(row, 5).checkState() == Qt.Checked if self.initiative_table.item(row, 5) else False,
                "notes": self.initiative_table.item(row, 6).text() if self.initiative_table.item(row, 6) else ""
            }
            combatants.append(combatant)
            
        return {
            "round": self.current_round,
            "current_turn_index": self.current_turn,
            "combatants": combatants
        }

    def _handle_resolution_result(self, result, error):
        """Handle the result from the combat resolver (runs in background thread!)."""
        # *** CRITICAL: DO NOT update UI directly here! ***
        # Emit signal to pass data safely to the main GUI thread.
        self.resolution_complete.emit(result, error)

    def _process_resolution_ui(self, result, error):
        """Process the combat resolution result in the main GUI thread."""
        # Re-enable button
        self.fast_resolve_button.setEnabled(True)
        self.fast_resolve_button.setText("Fast Resolve")
        
        if error:
            QMessageBox.critical(self, "Fast Resolve Error", f"Error resolving combat: {error}")
            return
            
        if result:
            # Log resolution result
            narrative = result.get("narrative", "No narrative provided.")
            updates = result.get("updates", [])
            
            self._log_combat_action(
                "Other", 
                "DM", 
                "resolved combat with AI", 
                result=f"Applied {len(updates)} updates"
            )
            
            # Then log each update
            for update in updates:
                name = update.get("name", "Unknown")
                
                if "hp" in update:
                    self._log_combat_action(
                        "Damage" if update["hp"] < 0 else "Healing", 
                        "AI", 
                        "updated HP for", 
                        name, 
                        f"New HP: {update['hp']}"
                    )
                
                if "status" in update:
                    self._log_combat_action(
                        "Status Effect", 
                        "AI", 
                        "applied status to", 
                        name, 
                        update["status"]
                    )
            
            # Apply updates first
            num_removed, update_summary = self._apply_combat_updates(updates)
            
            # Display results in a more informative message box
            summary_text = f"Combat Resolved:\n\n{narrative}\n\nApplied {len(updates)} updates:"
            if update_summary:
                summary_text += "\n" + "\n".join(update_summary)
            if num_removed > 0:
                summary_text += f"\nRemoved {num_removed} combatants."
                
            QMessageBox.information(
                self,
                "Fast Resolve Result",
                summary_text
            )
    
    def _apply_combat_updates(self, updates):
        """Apply updates from the combat resolution to the table.
        
        Returns:
            tuple: (number_of_rows_removed, list_of_summary_strings)
        """
        rows_to_remove = []
        update_summaries = []
        
        for update_index, update in enumerate(updates):
            name_to_find = update.get("name")
            if not name_to_find:
                continue
                
            # Find the row for the combatant
            found_row = -1
            for row in range(self.initiative_table.rowCount()):
                name_item = self.initiative_table.item(row, 0)
                if name_item and name_item.text() == name_to_find:
                    found_row = row
                    break
            
            if found_row != -1:
                # Apply HP update
                if "hp" in update:
                    hp_item = self.initiative_table.item(found_row, 2)
                    if hp_item:
                        old_hp = hp_item.text()
                        new_hp = str(update["hp"])
                        hp_item.setText(new_hp)
                        update_summaries.append(f"- {name_to_find}: HP changed from {old_hp} to {new_hp}")
                        # Handle death/unconscious status if HP reaches 0
                        if update["hp"] <= 0 and "status" not in update:
                            update["status"] = "Unconscious" # Or "Dead"
                        
                # Apply Status update
                if "status" in update:
                    status_item = self.initiative_table.item(found_row, 4)
                    if status_item:
                        old_status = status_item.text()
                        new_status = update["status"]
                        status_item.setText(new_status)
                        if old_status != new_status:
                             update_summaries.append(f"- {name_to_find}: Status changed from '{old_status}' to '{new_status}'")
                        # If status is Dead or Fled, mark for removal
                        if update["status"] in ["Dead", "Fled"]:
                            rows_to_remove.append(found_row)
        
        # Remove combatants marked for removal (in reverse order)
        if rows_to_remove:
            for row in sorted(list(set(rows_to_remove)), reverse=True):
                self.initiative_table.removeRow(row)
                # Adjust current turn if needed
                if row < self.current_turn:
                    self.current_turn -= 1
                elif row == self.current_turn:
                    self._update_highlight()
            
                # Clean up tracking
                self.death_saves.pop(row, None)
                if row in self.concentrating:
                    self.concentrating.remove(row)
            
            # Reset highlight if current turn was removed or index shifted
            self._update_highlight()
        
        return len(rows_to_remove), update_summaries

    def _get_combat_log(self):
        """Get the combat log panel if available"""
        if hasattr(self.app_state, 'panel_manager') and hasattr(self.app_state.panel_manager, 'get_panel_widget'):
            return self.app_state.panel_manager.get_panel_widget("combat_log")
        return None
    
    def _log_combat_action(self, category, actor, action, target=None, result=None, round=None, turn=None):
        """Log a combat action to the combat log if available"""
        combat_log = self._get_combat_log()
        if combat_log:
            combat_log.add_log_entry(
                category, 
                actor, 
                action, 
                target, 
                result, 
                round, 
                turn
            )

    def save_state(self):
        """Save the combat tracker state"""
        state = {
            "round": self.current_round,
            "turn": self.current_turn,
            "elapsed_time": self.elapsed_time,
            "combatants": [],
            "death_saves": self.death_saves,
            "concentrating": list(self.concentrating)
        }
        
        # Save all combatants
        for row in range(self.initiative_table.rowCount()):
            combatant = {}
            for col, key in enumerate(["name", "initiative", "hp", "ac", "status", "concentration", "notes"]):
                item = self.initiative_table.item(row, col)
                if col == 5:  # Concentration
                    combatant[key] = item.checkState() == Qt.Checked if item else False
                else:
                    combatant[key] = item.text() if item else ""
                
                # Save max HP
                if col == 2 and item:
                    combatant["max_hp"] = item.data(Qt.UserRole)
            
            state["combatants"].append(combatant)
        
        return state
    
    def restore_state(self, state):
        """Restore the combat tracker state"""
        if not state:
            return
        
        # Clear existing data
        self.initiative_table.setRowCount(0)
        self.death_saves.clear()
        self.concentrating.clear()
        
        # Restore round and turn
        self.current_round = state.get("round", 1)
        self.round_spin.setValue(self.current_round)
        
        self.current_turn = state.get("turn", 0)
        self.elapsed_time = state.get("elapsed_time", 0)
        self._update_timer()
        
        # Restore death saves and concentration
        self.death_saves = state.get("death_saves", {})
        self.concentrating = set(state.get("concentrating", []))
        
        # Restore combatants
        for combatant in state.get("combatants", []):
            row = self.initiative_table.rowCount()
            self.initiative_table.insertRow(row)
            
            # Restore each field
            for col, key in enumerate(["name", "initiative", "hp", "ac", "status", "concentration", "notes"]):
                value = combatant.get(key, "")
                item = QTableWidgetItem()
                
                if col == 5:  # Concentration
                    item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                    item.setCheckState(Qt.Checked if value else Qt.Unchecked)
                else:
                    item.setText(str(value))
                
                # Restore max HP
                if col == 2:
                    item.setData(Qt.UserRole, combatant.get("max_hp", value))
                
                self.initiative_table.setItem(row, col, item)
        
        # Highlight current turn
        self._update_highlight()

    @Slot(list) # Explicitly mark as a slot receiving a list
    def add_combatant_group(self, monster_dicts: list):
        """Add a list of monsters (as dictionaries) to the combat tracker."""
        if not isinstance(monster_dicts, list):
            print(f"[CombatTracker] Error: add_combatant_group received non-list: {type(monster_dicts)}")
            return
            
        print(f"[CombatTracker] Received group of {len(monster_dicts)} monsters to add.")
        
        added_count = 0
        for monster_data in monster_dicts:
            if not isinstance(monster_data, dict):
                print(f"[CombatTracker] Warning: Skipping non-dict item in monster group: {monster_data}")
                continue
            
            try:
                # Use the existing add_monster logic (or adapt _add_combatant)
                self.add_monster(monster_data)
                added_count += 1
            except Exception as e:
                print(f"[CombatTracker] Error adding monster '{monster_data.get('name', 'Unknown')}' from group: {e}")
                # Optionally show a message box?

        if added_count > 0:
             print(f"[CombatTracker] Added {added_count} monsters from group.")
             self._sort_initiative() # Sort after adding group
        else:
             print("[CombatTracker] No monsters were added from the group.")

    def add_monster(self, monster_data):
        """Add a monster to the combat tracker from the monster panel"""
        print("Combat Tracker received monster:", monster_data)  # Debug print
        try:
            # Extract relevant data
            name = monster_data.get("name", "Unknown Monster") # Use .get for safety

            # Handle HP (assuming it might be "76 (9d10 + 27)" or just "76")
            hp_raw = monster_data.get("hp", "10") # Default to 10 if missing
            try:
                if isinstance(hp_raw, (int, float)):
                    hp = int(hp_raw)
                else: # Assume string
                    hp_text = str(hp_raw).split()[0]
                    hp = int(hp_text)
            except (ValueError, IndexError):
                hp = 10 # Fallback HP
                print(f"Warning: Could not parse HP '{hp_raw}'. Defaulting to {hp}.")

            # Handle AC (could be int like 13 or string like "15 (natural armor)")
            ac_raw = monster_data.get("ac", 10) # Default to 10 if missing
            try:
                if isinstance(ac_raw, (int, float)):
                    ac = int(ac_raw)
                else: # Assume string
                    ac_text = str(ac_raw).split()[0] # Get first part before space
                    ac = int(ac_text) # Convert to integer
            except (ValueError, IndexError):
                ac = 10 # Fallback AC
                print(f"Warning: Could not parse AC '{ac_raw}'. Defaulting to {ac}.")

            # Roll initiative using Dexterity modifier
            # Safely access nested stats dictionary
            dex_score = 10 # Default DEX
            stats_dict = monster_data.get("stats")
            if isinstance(stats_dict, dict):
                dex_score = stats_dict.get("dex", 10)
            elif 'dexterity' in monster_data: # Check if using full name from our dataclass
                 dex_score = monster_data.get("dexterity", 10)

            dex_mod = (dex_score - 10) // 2
            initiative = random.randint(1, 20) + dex_mod

            print(f"Adding combatant - Name: {name}, Initiative: {initiative}, HP: {hp}, AC: {ac}")  # Debug print
            
            # Create new row
            row = self.initiative_table.rowCount()
            self.initiative_table.insertRow(row)
            
            # Create items
            name_item = QTableWidgetItem(name)
            initiative_item = QTableWidgetItem(str(initiative))
            hp_item = QTableWidgetItem(str(hp))
            hp_item.setData(Qt.UserRole, hp)  # Store max HP
            ac_item = QTableWidgetItem(str(ac))
            status_item = QTableWidgetItem("")
            concentration_item = QTableWidgetItem()
            concentration_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            concentration_item.setCheckState(Qt.Unchecked)
            notes_item = QTableWidgetItem("")
            
            # Set items
            self.initiative_table.setItem(row, 0, name_item)
            self.initiative_table.setItem(row, 1, initiative_item)
            self.initiative_table.setItem(row, 2, hp_item)
            self.initiative_table.setItem(row, 3, ac_item)
            self.initiative_table.setItem(row, 4, status_item)
            self.initiative_table.setItem(row, 5, concentration_item)
            self.initiative_table.setItem(row, 6, notes_item)
            
            # If combat hasn't started, sort by initiative
            if not self.combat_started:
                self._sort_initiative()
                
            print("Monster successfully added to combat")  # Debug print
            
        except Exception as e:
            print(f"Error adding monster: {str(e)}")  # Debug print
            import traceback
            traceback.print_exc() # Print full traceback
            QMessageBox.warning(
                self,
                "Error",
                f"Failed to add monster to combat: {str(e)}"
            )
    
    def add_character(self, character):
        """Add a player character to the combat tracker from the character panel"""
        print("Combat Tracker received character:", character.name)  # Debug print
        try:
            # Extract relevant data
            name = character.name
            hp = character.current_hp
            ac = character.armor_class
            
            # Get initiative with bonus
            initiative_roll = random.randint(1, 20)
            initiative = initiative_roll + character.initiative_bonus
            
            print(f"Adding combatant - Name: {name}, Initiative: {initiative}, HP: {hp}, AC: {ac}")  # Debug print
            
            # Create new row
            row = self.initiative_table.rowCount()
            self.initiative_table.insertRow(row)
            
            # Create items
            name_item = QTableWidgetItem(name)
            initiative_item = QTableWidgetItem(str(initiative))
            hp_item = QTableWidgetItem(str(hp))
            hp_item.setData(Qt.UserRole, character.max_hp)  # Store max HP
            ac_item = QTableWidgetItem(str(ac))
            status_item = QTableWidgetItem("")
            concentration_item = QTableWidgetItem()
            concentration_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            concentration_item.setCheckState(Qt.Unchecked)
            notes_item = QTableWidgetItem(f"{character.race} {character.character_class} (Lvl {character.level})")
            
            # Set items
            self.initiative_table.setItem(row, 0, name_item)
            self.initiative_table.setItem(row, 1, initiative_item)
            self.initiative_table.setItem(row, 2, hp_item)
            self.initiative_table.setItem(row, 3, ac_item)
            self.initiative_table.setItem(row, 4, status_item)
            self.initiative_table.setItem(row, 5, concentration_item)
            self.initiative_table.setItem(row, 6, notes_item)
            
            # If combat hasn't started, sort by initiative
            if not self.combat_started:
                self._sort_initiative()
                
            print("Character successfully added to combat")  # Debug print
            
        except Exception as e:
            print(f"Error adding character: {str(e)}")  # Debug print
            QMessageBox.warning(
                self,
                "Error",
                f"Failed to add character to combat: {str(e)}"
            )

    def _remove_selected(self):
        """Remove selected combatants from initiative"""
        selected_rows = sorted([index.row() for index in 
                              self.initiative_table.selectionModel().selectedRows()],
                             reverse=True)
        
        for row in selected_rows:
            # Log the removal
            name_item = self.initiative_table.item(row, 0)
            if name_item:
                name = name_item.text()
                self._log_combat_action(
                    "Other", 
                    "DM", 
                    "removed combatant", 
                    name, 
                    "Removed from initiative"
                )
            
            self.initiative_table.removeRow(row)
            # Adjust current_turn if necessary
            if row < self.current_turn:
                self.current_turn -= 1
            elif row == self.current_turn:
                self._update_highlight()
            
            # Clean up tracking
            self.death_saves.pop(row, None)
            if row in self.concentrating:
                self.concentrating.remove(row)
        
        # Highlight current turn again
        self._update_highlight()
