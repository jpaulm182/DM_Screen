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
"""

from PySide6.QtWidgets import (
    QTableWidget, QTableWidgetItem, QHeaderView, QPushButton,
    QLineEdit, QSpinBox, QHBoxLayout, QVBoxLayout, QComboBox,
    QLabel, QCheckBox, QMenu, QMessageBox, QDialog, QDialogButtonBox,
    QGroupBox, QWidget, QStyledItemDelegate, QStyle
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QIcon, QKeySequence, QBrush, QPalette
import random

from app.ui.panels.base_panel import BasePanel

# D&D 5e Conditions
CONDITIONS = [
    "Blinded", "Charmed", "Deafened", "Frightened", "Grappled",
    "Incapacitated", "Invisible", "Paralyzed", "Petrified",
    "Poisoned", "Prone", "Restrained", "Stunned", "Unconscious"
]

# --- Custom Delegate for Highlighting --- 

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

        # Create main layout
        main_layout = QVBoxLayout()
        
        # Add shortcuts info
        shortcuts_label = QLabel(
            "Shortcuts: Next Combatant (Ctrl+Space) | Sort (Ctrl+S) | Timer (Ctrl+T)"
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
        self.initiative_table.setSelectionMode(QTableWidget.SingleSelection)
        
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
        """Add a new combatant to the tracker"""
        print(f"_add_combatant called with: {name}, {initiative}, {hp}, {ac}")  # Debug print
        
        # Get current row count
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
        
        # Set items
        self.initiative_table.setItem(row, 0, name_item)
        self.initiative_table.setItem(row, 1, initiative_item)
        self.initiative_table.setItem(row, 2, hp_item)
        self.initiative_table.setItem(row, 3, ac_item)
        self.initiative_table.setItem(row, 4, status_item)
        self.initiative_table.setItem(row, 5, concentration_item)
        
        print(f"Added combatant at row {row}")  # Debug print
    
    def _sort_initiative(self):
        """Sort combatants by initiative"""
        if self.initiative_table.rowCount() <= 1:
            return
            
        # Get all rows data
        rows = []
        for row in range(self.initiative_table.rowCount()):
            row_data = []
            for col in range(self.initiative_table.columnCount()):
                item = self.initiative_table.item(row, col)
                if col == 5:  # Concentration column
                    new_item = QTableWidgetItem()
                    new_item.setFlags(new_item.flags() | Qt.ItemIsUserCheckable)
                    new_item.setCheckState(item.checkState() if item else Qt.Unchecked)
                    row_data.append(new_item)
                else:
                    new_item = QTableWidgetItem(item.text() if item else "")
                    if col == 2 and item:  # HP column
                        new_item.setData(Qt.UserRole, item.data(Qt.UserRole))
                    row_data.append(new_item)
            rows.append(row_data)
        
        # Sort by initiative (column 1)
        rows.sort(key=lambda x: int(x[1].text() or "0"), reverse=True)
        
        # Update table
        for row, items in enumerate(rows):
            for col, item in enumerate(items):
                self.initiative_table.setItem(row, col, item)
        
        # Reset current turn if combat hasn't started
        if self.current_round == 1 and self.current_turn == 0:
            self.current_turn = 0
            self._update_highlight()
    
    def _next_turn(self):
        """Advance to the next turn"""
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
        """Show context menu for initiative table"""
        menu = QMenu()
        
        # Only show if a row is selected
        selected_rows = self.initiative_table.selectionModel().selectedRows()
        if selected_rows:
            row = selected_rows[0].row()
            
            # Add menu actions
            remove_action = QAction("Remove", self)
            remove_action.triggered.connect(self._remove_selected)
            menu.addAction(remove_action)
            
            damage_action = QAction("Apply Damage...", self)
            damage_action.triggered.connect(lambda: self._apply_damage(False))
            menu.addAction(damage_action)
            
            heal_action = QAction("Heal...", self)
            heal_action.triggered.connect(lambda: self._apply_damage(True))
            menu.addAction(heal_action)
            
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
        dialog = DamageDialog(self, is_healing)
        if dialog.exec_():
            amount = dialog.get_amount()
            if amount > 0:
                for row in (index.row() for index in 
                          self.initiative_table.selectionModel().selectedRows()):
                    hp_item = self.initiative_table.item(row, 2)
                    if hp_item:
                        current_hp = int(hp_item.text())
                        max_hp = hp_item.data(Qt.UserRole)
                        
                        if is_healing:
                            new_hp = min(current_hp + amount, max_hp)
                        else:
                            new_hp = max(current_hp - amount, 0)
                        
                        hp_item.setText(str(new_hp))
                        
                        # Check for concentration
                        if not is_healing and amount > 0:
                            self._check_concentration(row, amount)
    
    def _check_concentration(self, row, damage):
        """Check if concentration needs to be made"""
        conc_item = self.initiative_table.item(row, 5)
        if conc_item and conc_item.checkState() == Qt.Checked:
            dc = max(10, damage // 2)
            name = self.initiative_table.item(row, 0).text()
            QMessageBox.information(
                self,
                "Concentration Check",
                f"{name} needs to make a Constitution saving throw\n"
                f"DC {dc} to maintain concentration"
            )
    
    def _manage_death_saves(self, row):
        """Manage death saving throws for a character"""
        current_saves = self.death_saves.get(row, {"successes": 0, "failures": 0})
        dialog = DeathSavesDialog(self, current_saves)
        
        if dialog.exec_():
            self.death_saves[row] = dialog.get_saves()
            saves = self.death_saves[row]
            
            # Check for stabilization or death
            if saves["successes"] >= 3:
                QMessageBox.information(self, "Stabilized", 
                    f"{self.initiative_table.item(row, 0).text()} has stabilized!")
                self.death_saves.pop(row)
            elif saves["failures"] >= 3:
                QMessageBox.warning(self, "Death", 
                    f"{self.initiative_table.item(row, 0).text()} has died!")
                self.death_saves.pop(row)
    
    def _remove_selected(self):
        """Remove selected combatants from initiative"""
        selected_rows = sorted([index.row() for index in 
                              self.initiative_table.selectionModel().selectedRows()],
                             reverse=True)
        
        for row in selected_rows:
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
    
    def _set_status(self, status):
        """Set status for selected combatants"""
        for row in (index.row() for index in 
                   self.initiative_table.selectionModel().selectedRows()):
            self.initiative_table.setItem(row, 4, QTableWidgetItem(status))
    
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
        """Roll initiative for a new combatant"""
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
            # No need to explicitly call _update_highlight as the table is empty
            
            print("Combat Reset") # Optional: Confirmation in console
    
    def _restart_combat(self):
        """Restart the current combat, keeping combatants but resetting state."""
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
            # Note: _sort_initiative calls _update_highlight if needed
            
            print("Combat Restarted") # Optional: Confirmation
            
    def _fast_resolve_combat(self):
        """(Placeholder) Use LLM to resolve the current combat encounter."""
        # TODO: Implement logic to gather combat state, call LLM service,
        # and update the combat tracker based on the result.
        QMessageBox.information(
            self, 
            "Fast Resolve (Experimental)", 
            "This feature is not yet implemented. It will use AI to resolve the combat."
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
