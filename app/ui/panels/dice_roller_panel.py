# app/ui/panels/dice_roller_panel.py - Dice roller panel
"""
Dice roller panel for the DM Screen application

Provides a flexible dice rolling system with support for:
- Standard D&D dice (d4, d6, d8, d10, d12, d20, d100)
- Custom dice expressions (e.g. 2d6+3)
- Advantage/disadvantage rolls
- Roll history
- Saved custom rolls
"""

import re
import random
import json
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLineEdit, QLabel, QListWidget, QGroupBox,
    QSpinBox, QComboBox, QCheckBox, QMessageBox,
    QScrollArea, QSizePolicy, QMenu, QInputDialog
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QColor, QPalette
from app.ui.panels.base_panel import BasePanel

class DiceRollerPanel(BasePanel):
    """Panel for rolling dice and managing roll history"""
    
    def __init__(self, app_state):
        """Initialize the dice roller panel"""
        # Initialize with default values before parent init
        self.roll_history = []
        self.saved_rolls = self._get_default_rolls()
        
        # Call parent init
        super().__init__(app_state, "Dice Roller")
        
        # Defer loading saved rolls until after setup is complete
        self.loaded = False
    
    def _setup_ui(self):
        """Set up the dice roller UI"""
        # Create a new layout for this panel
        layout = QVBoxLayout()
        
        # Quick roll buttons
        quick_roll_group = QGroupBox("Quick Rolls")
        quick_roll_layout = QHBoxLayout()
        
        standard_dice = [4, 6, 8, 10, 12, 20, 100]
        for sides in standard_dice:
            button = QPushButton(f"d{sides}")
            button.clicked.connect(lambda checked, s=sides: self._quick_roll(s))
            quick_roll_layout.addWidget(button)
        
        quick_roll_group.setLayout(quick_roll_layout)
        layout.addWidget(quick_roll_group)
        
        # Latest roll result display
        self.result_display = QLabel("Roll some dice...")
        self.result_display.setAlignment(Qt.AlignCenter)
        result_font = self.result_display.font()
        result_font.setPointSize(result_font.pointSize() * 2)
        result_font.setBold(True)
        self.result_display.setFont(result_font)
        self.result_display.setStyleSheet("background-color: rgba(0, 0, 0, 0.1); border-radius: 5px; padding: 10px;")
        self.result_display.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.result_display.setMinimumHeight(60)
        layout.addWidget(self.result_display)
        
        # Custom roll input with saved rolls
        custom_roll_group = QGroupBox("Custom Roll")
        custom_roll_layout = QVBoxLayout()
        
        # Saved rolls selector
        saved_roll_layout = QHBoxLayout()
        saved_roll_layout.addWidget(QLabel("Saved Formulas:"))
        
        self.saved_roll_combo = QComboBox()
        saved_roll_layout.addWidget(self.saved_roll_combo, 1)
        
        manage_saved_button = QPushButton("⚙️")
        manage_saved_button.setToolTip("Manage saved formulas")
        manage_saved_button.clicked.connect(self._manage_saved_rolls)
        saved_roll_layout.addWidget(manage_saved_button)
        
        custom_roll_layout.addLayout(saved_roll_layout)
        
        # Roll input field
        input_layout = QHBoxLayout()
        self.roll_input = QLineEdit()
        self.roll_input.setPlaceholderText("Enter roll (e.g. 2d6+3)")
        self.roll_input.returnPressed.connect(self._custom_roll)
        input_layout.addWidget(self.roll_input)
        
        roll_button = QPushButton("Roll")
        roll_button.clicked.connect(self._custom_roll)
        input_layout.addWidget(roll_button)
        
        save_button = QPushButton("Save")
        save_button.setToolTip("Save this formula for future use")
        save_button.clicked.connect(self._save_current_formula)
        input_layout.addWidget(save_button)
        
        custom_roll_layout.addLayout(input_layout)
        custom_roll_group.setLayout(custom_roll_layout)
        layout.addWidget(custom_roll_group)
        
        # Advantage/Disadvantage section
        adv_group = QGroupBox("D20 with Advantage/Disadvantage")
        adv_layout = QHBoxLayout()
        
        adv_button = QPushButton("Advantage")
        adv_button.clicked.connect(lambda: self._roll_with_advantage(True))
        adv_layout.addWidget(adv_button)
        
        disadv_button = QPushButton("Disadvantage")
        disadv_button.clicked.connect(lambda: self._roll_with_advantage(False))
        adv_layout.addWidget(disadv_button)
        
        adv_group.setLayout(adv_layout)
        layout.addWidget(adv_group)
        
        # Roll history
        history_group = QGroupBox("Roll History")
        history_layout = QVBoxLayout()
        
        self.history_list = QListWidget()
        # Make history items more readable
        self.history_list.setAlternatingRowColors(True)
        history_list_font = self.history_list.font()
        history_list_font.setPointSize(history_list_font.pointSize() + 1)
        self.history_list.setFont(history_list_font)
        self.history_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.history_list.customContextMenuRequested.connect(self._show_history_context_menu)
        
        history_layout.addWidget(self.history_list)
        
        clear_history = QPushButton("Clear History")
        clear_history.clicked.connect(self._clear_history)
        history_layout.addWidget(clear_history)
        
        history_group.setLayout(history_layout)
        layout.addWidget(history_group)
        
        # Set the layout for this panel
        self.setLayout(layout)
        
        # Now that UI is set up, try to load saved rolls and update UI
        try:
            self._try_load_saved_rolls()
            self._update_saved_roll_combo()
            self.saved_roll_combo.currentTextChanged.connect(self._on_saved_roll_selected)
        except Exception as e:
            print(f"Error initializing saved rolls: {e}")
    
    def _quick_roll(self, sides):
        """Perform a quick roll of a single die"""
        result = random.randint(1, sides)
        self._add_to_history(f"d{sides}", result)
    
    def _custom_roll(self):
        """Handle custom dice roll expressions"""
        expression = self.roll_input.text().strip().lower()
        if not expression:
            return
        
        try:
            results = self._parse_and_roll(expression)
            if results:
                total, details = results
                self._add_to_history(expression, total, details)
        except ValueError as e:
            QMessageBox.warning(self, "Invalid Roll", str(e))
    
    def _roll_with_advantage(self, is_advantage):
        """Roll with advantage or disadvantage"""
        roll1 = random.randint(1, 20)
        roll2 = random.randint(1, 20)
        
        if is_advantage:
            result = max(roll1, roll2)
            roll_type = "Advantage"
        else:
            result = min(roll1, roll2)
            roll_type = "Disadvantage"
        
        details = f"[{roll1}, {roll2}]"
        self._add_to_history(f"d20 with {roll_type}", result, details)
    
    def _parse_and_roll(self, expression):
        """Parse and evaluate a dice roll expression"""
        # Basic dice roll pattern: XdY+Z
        pattern = r'^(\d+)?d(\d+)([+-]\d+)?$'
        match = re.match(pattern, expression)
        
        if not match:
            raise ValueError("Invalid dice expression format")
        
        count = int(match.group(1)) if match.group(1) else 1
        sides = int(match.group(2))
        modifier = int(match.group(3)) if match.group(3) else 0
        
        if count > 100:
            raise ValueError("Too many dice (maximum 100)")
        if sides > 1000:
            raise ValueError("Die has too many sides (maximum 1000)")
        
        # Roll the dice
        rolls = [random.randint(1, sides) for _ in range(count)]
        total = sum(rolls) + modifier
        
        # Format details
        details = f"[{', '.join(map(str, rolls))}]"
        if modifier:
            details += f" {'+' if modifier > 0 else ''}{modifier}"
        
        return total, details
    
    def _add_to_history(self, expression, result, details=None):
        """Add a roll to the history"""
        text = f"{expression}: {result}"
        if details:
            text += f" {details}"
        
        # Update the prominent result display
        self.result_display.setText(f"{result} - {expression}")
        
        # Update style based on roll type
        if "d20" in expression.lower():
            if result == 20:
                # Critical hit!
                self.result_display.setStyleSheet("background-color: rgba(0, 200, 0, 0.3); border-radius: 5px; padding: 10px;")
            elif result == 1:
                # Critical fail!
                self.result_display.setStyleSheet("background-color: rgba(200, 0, 0, 0.3); border-radius: 5px; padding: 10px;")
            else:
                self.result_display.setStyleSheet("background-color: rgba(0, 0, 0, 0.1); border-radius: 5px; padding: 10px;")
        else:
            self.result_display.setStyleSheet("background-color: rgba(0, 0, 0, 0.1); border-radius: 5px; padding: 10px;")
        
        self.roll_history.append(text)
        self.history_list.insertItem(0, text)
        self.history_list.item(0).setToolTip(text)  # Add tooltip for longer entries
        
        # Keep history at a reasonable size
        while len(self.roll_history) > 50:
            self.roll_history.pop()
            self.history_list.takeItem(self.history_list.count() - 1)
            
        # Log to combat log if available
        self._log_roll_to_combat_log(expression, result, details)
    
    def _log_roll_to_combat_log(self, expression, result, details=None):
        """Log the roll to the combat log if available"""
        combat_log = self._get_combat_log()
        if combat_log:
            # Determine the roll category
            category = "Other"
            if "d20" in expression.lower():
                if "advantage" in expression.lower() or "disadvantage" in expression.lower():
                    category = "Attack"  # Assumes advantage/disadvantage is used for attacks
                else:
                    category = "Attack"  # Default d20 rolls are often attacks or ability checks
            
            # Format result string
            result_str = f"{result}"
            if details:
                result_str += f" {details}"
                
            # Log to combat log
            combat_log.add_log_entry(
                category,
                "Dice Roller",
                f"rolled {expression}",
                None,
                result_str
            )
    
    def _get_combat_log(self):
        """Get the combat log panel if available"""
        if hasattr(self.app_state, 'panel_manager') and hasattr(self.app_state.panel_manager, 'get_panel_widget'):
            return self.app_state.panel_manager.get_panel_widget("combat_log")
        return None
    
    def _clear_history(self):
        """Clear the roll history"""
        self.roll_history.clear()
        self.history_list.clear()
        self.result_display.setText("Roll some dice...")
        self.result_display.setStyleSheet("background-color: rgba(0, 0, 0, 0.1); border-radius: 5px; padding: 10px;")
    
    def _get_default_rolls(self):
        """Get default set of dice rolls"""
        return {
            "Attack Roll": "1d20",
            "Damage (Shortsword)": "1d6",
            "Damage (Longsword)": "1d8",
            "Damage (Greatsword)": "2d6", 
            "Sneak Attack (L1)": "1d6"
        }
        
    def _try_load_saved_rolls(self):
        """Safely try to load saved rolls after UI is ready"""
        if not hasattr(self, 'app_state') or not self.app_state:
            print("Warning: app_state not available")
            return
            
        try:
            if hasattr(self.app_state, 'config_dir'):
                config_dir = self.app_state.config_dir
                saved_rolls_file = config_dir / "saved_dice_rolls.json"
                
                if saved_rolls_file.exists():
                    try:
                        with open(saved_rolls_file, 'r') as f:
                            loaded_rolls = json.load(f)
                            if isinstance(loaded_rolls, dict):
                                self.saved_rolls = loaded_rolls
                                self.loaded = True
                    except Exception as e:
                        print(f"Error loading saved dice rolls: {e}")
        except Exception as e:
            print(f"Unexpected error accessing config: {e}")
            
    def _load_saved_rolls(self):
        """Legacy method kept for compatibility"""
        return self.saved_rolls
    
    def _save_rolls(self):
        """Save the roll formulas to config"""
        config_dir = self.app_state.config_dir
        saved_rolls_file = config_dir / "saved_dice_rolls.json"
        
        try:
            with open(saved_rolls_file, 'w') as f:
                json.dump(self.saved_rolls, f, indent=2)
        except Exception as e:
            print(f"Error saving dice rolls: {e}")
    
    def _update_saved_roll_combo(self):
        """Update the saved rolls combo box"""
        self.saved_roll_combo.clear()
        self.saved_roll_combo.addItem("-- Select Saved Formula --")
        
        for name in sorted(self.saved_rolls.keys()):
            self.saved_roll_combo.addItem(f"{name} ({self.saved_rolls[name]})")
    
    def _on_saved_roll_selected(self, text):
        """Handle selection of a saved roll from the dropdown"""
        if text and text != "-- Select Saved Formula --":
            # Extract just the formula in parentheses
            formula_start = text.rfind("(")
            formula_end = text.rfind(")")
            if formula_start > 0 and formula_end > formula_start:
                formula = text[formula_start + 1:formula_end]
                self.roll_input.setText(formula)
                self._custom_roll()  # Auto-roll the selected formula
    
    def _save_current_formula(self):
        """Save the current formula"""
        formula = self.roll_input.text().strip()
        if not formula:
            return
            
        # Verify it's a valid formula
        try:
            pattern = r'^(\d+)?d(\d+)([+-]\d+)?$'
            if not re.match(pattern, formula.lower()):
                raise ValueError("Invalid dice formula format")
        except ValueError:
            QMessageBox.warning(self, "Invalid Formula", 
                               "Please enter a valid dice formula (e.g. 2d6+3)")
            return
            
        # Get a name for the formula
        name, ok = QInputDialog.getText(
            self, "Save Formula", 
            "Enter a name for this dice formula:",
            text=f"Roll {formula}"
        )
        
        if ok and name:
            self.saved_rolls[name] = formula
            self._save_rolls()
            self._update_saved_roll_combo()
            
            # Select the newly added formula
            index = self.saved_roll_combo.findText(f"{name} ({formula})")
            if index >= 0:
                self.saved_roll_combo.setCurrentIndex(index)
    
    def _manage_saved_rolls(self):
        """Show context menu to manage saved rolls"""
        menu = QMenu(self)
        
        # Add actions for each saved roll
        for name, formula in sorted(self.saved_rolls.items()):
            roll_action = menu.addAction(f"{name} ({formula})")
            roll_action.setData((name, formula))
        
        # Show the menu only if we have saved rolls
        if not self.saved_rolls:
            menu.addAction("No saved formulas").setEnabled(False)
        else:
            menu.addSeparator()
            menu.addAction("Delete Selected").triggered.connect(self._delete_saved_roll)
            menu.addAction("Rename Selected").triggered.connect(self._rename_saved_roll)
        
        menu.addSeparator()
        menu.addAction("Add New Formula").triggered.connect(self._add_new_saved_roll)
        
        # Show the context menu
        menu.exec_(self.mapToGlobal(self.saved_roll_combo.pos()))
    
    def _delete_saved_roll(self):
        """Delete the selected saved roll"""
        current_text = self.saved_roll_combo.currentText()
        if current_text and current_text != "-- Select Saved Formula --":
            name_part = current_text.split(" (")[0]
            if name_part in self.saved_rolls:
                confirm = QMessageBox.question(
                    self, "Confirm Deletion",
                    f"Are you sure you want to delete '{name_part}'?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                
                if confirm == QMessageBox.Yes:
                    del self.saved_rolls[name_part]
                    self._save_rolls()
                    self._update_saved_roll_combo()
    
    def _rename_saved_roll(self):
        """Rename the selected saved roll"""
        current_text = self.saved_roll_combo.currentText()
        if current_text and current_text != "-- Select Saved Formula --":
            name_part = current_text.split(" (")[0]
            if name_part in self.saved_rolls:
                new_name, ok = QInputDialog.getText(
                    self, "Rename Formula", 
                    "Enter a new name:",
                    text=name_part
                )
                
                if ok and new_name and new_name != name_part:
                    formula = self.saved_rolls[name_part]
                    del self.saved_rolls[name_part]
                    self.saved_rolls[new_name] = formula
                    self._save_rolls()
                    self._update_saved_roll_combo()
                    
                    # Select the renamed formula
                    index = self.saved_roll_combo.findText(f"{new_name} ({formula})")
                    if index >= 0:
                        self.saved_roll_combo.setCurrentIndex(index)
    
    def _add_new_saved_roll(self):
        """Add a new saved roll formula"""
        name, ok = QInputDialog.getText(
            self, "Add Formula", 
            "Enter a name for the formula:"
        )
        
        if ok and name:
            formula, ok = QInputDialog.getText(
                self, "Add Formula", 
                "Enter the dice formula (e.g. 2d6+3):"
            )
            
            if ok and formula:
                # Verify it's a valid formula
                try:
                    pattern = r'^(\d+)?d(\d+)([+-]\d+)?$'
                    if not re.match(pattern, formula.lower()):
                        raise ValueError("Invalid dice formula format")
                except ValueError:
                    QMessageBox.warning(self, "Invalid Formula", 
                                       "Please enter a valid dice formula (e.g. 2d6+3)")
                    return
                
                self.saved_rolls[name] = formula
                self._save_rolls()
                self._update_saved_roll_combo()
                
                # Select the newly added formula
                index = self.saved_roll_combo.findText(f"{name} ({formula})")
                if index >= 0:
                    self.saved_roll_combo.setCurrentIndex(index)
    
    def _show_history_context_menu(self, pos):
        """Show context menu for roll history items"""
        item = self.history_list.itemAt(pos)
        if item:
            menu = QMenu(self)
            reroll_action = menu.addAction("Reroll")
            save_action = menu.addAction("Save as Formula")
            
            action = menu.exec_(self.history_list.mapToGlobal(pos))
            
            if action == reroll_action:
                # Extract the formula from the history item
                text = item.text()
                formula_end = text.find(":")
                if formula_end > 0:
                    formula = text[:formula_end].strip()
                    self.roll_input.setText(formula)
                    self._custom_roll()
            elif action == save_action:
                # Extract the formula and save it
                text = item.text()
                formula_end = text.find(":")
                if formula_end > 0:
                    formula = text[:formula_end].strip()
                    name, ok = QInputDialog.getText(
                        self, "Save Formula", 
                        "Enter a name for this dice formula:",
                        text=f"Roll {formula}"
                    )
                    
                    if ok and name:
                        self.saved_rolls[name] = formula
                        self._save_rolls()
                        self._update_saved_roll_combo()
