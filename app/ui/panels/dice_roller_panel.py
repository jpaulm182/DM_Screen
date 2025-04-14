# app/ui/panels/dice_roller_panel.py - Dice roller panel
"""
Dice roller panel for the DM Screen application

Provides a flexible dice rolling system with support for:
- Standard D&D dice (d4, d6, d8, d10, d12, d20, d100)
- Custom dice expressions (e.g. 2d6+3)
- Advantage/disadvantage rolls
- Roll history
- Saved custom rolls
- Mini mode for non-obtrusive operation
"""

import re
import random
import json
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLineEdit, QLabel, QListWidget, QGroupBox, QListWidgetItem,
    QSpinBox, QComboBox, QCheckBox, QMessageBox,
    QScrollArea, QSizePolicy, QMenu, QInputDialog
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QColor, QPalette, QTextDocument, QIcon
from app.ui.panels.base_panel import BasePanel

class DiceRollerPanel(BasePanel):
    """Panel for rolling dice and managing roll history"""
    
    def __init__(self, app_state):
        """Initialize the dice roller panel"""
        # Initialize with default values before parent init
        self.roll_history = []
        self.saved_rolls = self._get_default_rolls()
        self.mini_mode = False  # Start in full mode
        
        # Call parent init
        super().__init__(app_state, "Dice Roller")
        
        # Defer loading saved rolls until after setup is complete
        self.loaded = False
    
    def _setup_ui(self):
        """Set up the dice roller UI"""
        # Create a new layout for this panel
        self.main_layout = QVBoxLayout()
        
        # Add toggle button for mini mode at the top right
        toggle_layout = QHBoxLayout()
        toggle_layout.addStretch()
        
        self.mini_mode_toggle = QPushButton("Mini Mode")
        self.mini_mode_toggle.setCheckable(True)
        self.mini_mode_toggle.setToolTip("Toggle between full and compact dice roller")
        self.mini_mode_toggle.clicked.connect(self._toggle_mini_mode)
        toggle_layout.addWidget(self.mini_mode_toggle)
        
        self.main_layout.addLayout(toggle_layout)
        
        # Create both UI modes
        self._setup_full_ui()
        self._setup_mini_ui()
        
        # Show the appropriate UI
        self._toggle_mini_mode(self.mini_mode)
        
        # Set the layout for this panel
        self.setLayout(self.main_layout)
        
        # Now that UI is set up, try to load saved rolls and update UI
        try:
            self._try_load_saved_rolls()
            self._update_saved_roll_combo()
            self.saved_roll_combo.currentTextChanged.connect(self._on_saved_roll_selected)
        except Exception as e:
            print(f"Error initializing saved rolls: {e}")
    
    def _setup_full_ui(self):
        """Set up the full version of the dice roller UI"""
        self.full_widget = QWidget()
        layout = QVBoxLayout(self.full_widget)
        self.full_widget.setLayout(layout)
        
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
        self.result_display = QLabel()
        self.result_display.setAlignment(Qt.AlignCenter)
        self.result_display.setTextFormat(Qt.RichText)  # Enable rich text support
        
        # Set initial text with the same styling used in our dice roll
        default_text = f"<span style='font-size: 24px; font-weight: bold;'>Roll some dice</span><br><span style='font-size: 14px; color: #555;'>Use buttons or formula above</span>"
        self.result_display.setText(default_text)
        
        self.result_display.setStyleSheet("background-color: rgba(0, 0, 0, 0.1); border-radius: 5px; padding: 10px;")
        self.result_display.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.result_display.setMinimumHeight(100)  # Increased height to accommodate larger text
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
        self.roll_input.setPlaceholderText("Enter roll (e.g. 2d6+3 or 1d8+2d4+5)")
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
        # Enable rich text (HTML) in list items
        self.history_list.setTextElideMode(Qt.ElideNone)  # Prevent text from being truncated
        self.history_list.setWordWrap(True)  # Enable word wrapping
        
        history_layout.addWidget(self.history_list)
        
        clear_history = QPushButton("Clear History")
        clear_history.clicked.connect(self._clear_history)
        history_layout.addWidget(clear_history)
        
        history_group.setLayout(history_layout)
        layout.addWidget(history_group)
        
        # Add the full widget to the main layout but initially hide it
        self.main_layout.addWidget(self.full_widget)
    
    def _setup_mini_ui(self):
        """Set up the mini version of the dice roller UI"""
        self.mini_widget = QWidget()
        layout = QVBoxLayout(self.mini_widget)
        
        # Mini result display - smaller but still visible
        self.mini_result_display = QLabel()
        self.mini_result_display.setAlignment(Qt.AlignCenter)
        self.mini_result_display.setTextFormat(Qt.RichText)
        default_text = f"<span style='font-size: 20px; font-weight: bold;'>Roll some dice</span>"
        self.mini_result_display.setText(default_text)
        self.mini_result_display.setStyleSheet("background-color: rgba(0, 0, 0, 0.1); border-radius: 5px; padding: 5px;")
        self.mini_result_display.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.mini_result_display.setMinimumHeight(50)
        layout.addWidget(self.mini_result_display)
        
        # Compact dice buttons in a single row
        dice_layout = QHBoxLayout()
        standard_dice = [4, 6, 8, 10, 12, 20, 100]
        
        for sides in standard_dice:
            button = QPushButton(f"d{sides}")
            button.setMaximumWidth(40)  # Make buttons narrower
            button.clicked.connect(lambda checked, s=sides: self._quick_roll_mini(s))
            dice_layout.addWidget(button)
        
        # Add advantage/disadvantage buttons
        adv_button = QPushButton("ADV")
        adv_button.setToolTip("Roll with advantage (2d20, take highest)")
        adv_button.clicked.connect(lambda: self._roll_with_advantage_mini(True))
        dice_layout.addWidget(adv_button)
        
        disadv_button = QPushButton("DIS")
        disadv_button.setToolTip("Roll with disadvantage (2d20, take lowest)")
        disadv_button.clicked.connect(lambda: self._roll_with_advantage_mini(False))
        dice_layout.addWidget(disadv_button)
        
        layout.addLayout(dice_layout)
        
        # Mini custom roll input
        mini_input_layout = QHBoxLayout()
        self.mini_roll_input = QLineEdit()
        self.mini_roll_input.setPlaceholderText("2d6+3")
        self.mini_roll_input.returnPressed.connect(self._custom_roll_mini)
        mini_input_layout.addWidget(self.mini_roll_input)
        
        mini_roll_button = QPushButton("Roll")
        mini_roll_button.clicked.connect(self._custom_roll_mini)
        mini_input_layout.addWidget(mini_roll_button)
        
        # Add saved roll dropdown (compact version)
        self.mini_saved_roll_combo = QComboBox()
        self.mini_saved_roll_combo.setMaximumWidth(150)
        self.mini_saved_roll_combo.currentTextChanged.connect(self._on_mini_saved_roll_selected)
        mini_input_layout.addWidget(self.mini_saved_roll_combo)
        
        layout.addLayout(mini_input_layout)
        
        # Add the mini widget to the main layout but initially hide it
        self.main_layout.addWidget(self.mini_widget)
        self.mini_widget.hide()
    
    def _toggle_mini_mode(self, checked=None):
        """Toggle between full and mini dice roller modes"""
        if checked is None:
            checked = not self.mini_mode
        
        self.mini_mode = checked
        self.mini_mode_toggle.setChecked(checked)
        
        if checked:
            self.mini_mode_toggle.setText("Full Mode")
            self.full_widget.hide()
            self.mini_widget.show()
            
            # Update the mini saved roll combo
            self.mini_saved_roll_combo.clear()
            self.mini_saved_roll_combo.addItem("-- Saved --")
            for name in sorted(self.saved_rolls.keys()):
                self.mini_saved_roll_combo.addItem(f"{name}")
        else:
            self.mini_mode_toggle.setText("Mini Mode")
            self.mini_widget.hide()
            self.full_widget.show()
        
        # Save the mode preference
        if hasattr(self, 'app_state') and self.app_state:
            self.app_state.save_panel_setting("dice_roller", "mini_mode", checked)
    
    def _quick_roll_mini(self, sides):
        """Perform a quick roll in mini mode"""
        result = random.randint(1, sides)
        self._update_mini_result(f"d{sides}", result)
        self._add_to_history(f"d{sides}", result)
    
    def _custom_roll_mini(self):
        """Handle custom dice roll in mini mode"""
        expression = self.mini_roll_input.text().strip().lower()
        if not expression:
            return
        
        try:
            results = self._parse_and_roll(expression)
            if results:
                total, details = results
                self._update_mini_result(expression, total, details)
                self._add_to_history(expression, total, details)
        except ValueError as e:
            QMessageBox.warning(self, "Invalid Roll", str(e))
    
    def _roll_with_advantage_mini(self, is_advantage):
        """Roll with advantage/disadvantage in mini mode"""
        roll1 = random.randint(1, 20)
        roll2 = random.randint(1, 20)
        
        if is_advantage:
            result = max(roll1, roll2)
            roll_type = "Advantage"
        else:
            result = min(roll1, roll2)
            roll_type = "Disadvantage"
        
        details = f"[{roll1}, {roll2}]"
        self._update_mini_result(f"d20 {roll_type}", result, details)
        self._add_to_history(f"d20 with {roll_type}", result, details)
    
    def _update_mini_result(self, expression, result, details=None):
        """Update the mini mode result display"""
        # Similar styling as full mode but more compact
        if "d20" in expression.lower() and result == 20:
            result_text = f"<span style='font-size: 28px; font-weight: bold; color: white;'>{result}</span>"
            self.mini_result_display.setStyleSheet("background-color: rgba(0, 200, 0, 0.5); color: white; font-weight: bold; border-radius: 5px; padding: 5px; border: 2px solid green;")
        elif "d20" in expression.lower() and result == 1:
            result_text = f"<span style='font-size: 28px; font-weight: bold; color: white;'>{result}</span>"
            self.mini_result_display.setStyleSheet("background-color: rgba(200, 0, 0, 0.5); color: white; font-weight: bold; border-radius: 5px; padding: 5px; border: 2px solid red;")
        else:
            result_text = f"<span style='font-size: 24px; font-weight: bold;'>{result}</span>"
            self.mini_result_display.setStyleSheet("background-color: rgba(0, 0, 0, 0.1); border-radius: 5px; padding: 5px;")
        
        expr_text = f"<span style='font-size: 12px; color: #555;'>{expression}</span>"
        self.mini_result_display.setText(f"{result_text}<br>{expr_text}")
    
    def _on_mini_saved_roll_selected(self, text):
        """Handle selection from mini mode saved roll dropdown"""
        if text and text != "-- Saved --":
            formula = self.saved_rolls.get(text, "")
            if formula:
                self.mini_roll_input.setText(formula)
                self._custom_roll_mini()
    
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
        # Remove all spaces for easier parsing
        expression = expression.replace(" ", "").lower()
        
        # For complex expressions with multiple dice types and modifiers
        dice_pattern = r'(\d+)?d(\d+)'  # Pattern for dice components like 2d6
        modifier_pattern = r'([+-]\d+)'  # Pattern for modifiers like +3
        
        # Find all dice components (like 2d6, 1d8)
        dice_components = re.finditer(dice_pattern, expression)
        
        # Track the result
        all_rolls = []  # Store all individual dice rolls
        total = 0
        rolls_text = []  # For display purposes
        
        # Process each dice component
        for match in dice_components:
            count = int(match.group(1)) if match.group(1) else 1
            sides = int(match.group(2))
            
            if count > 100:
                raise ValueError("Too many dice (maximum 100 per type)")
            if sides > 1000:
                raise ValueError("Die has too many sides (maximum 1000)")
            
            # Roll the dice
            rolls = [random.randint(1, sides) for _ in range(count)]
            all_rolls.extend(rolls)
            total += sum(rolls)
            
            # Format for the details display
            rolls_text.append(f"{count}d{sides}[{', '.join(map(str, rolls))}]")
        
        # If no dice were found, the expression is invalid
        if not rolls_text:
            raise ValueError("Invalid dice expression format")
            
        # Find all modifiers (like +3, -2)
        modifiers = re.finditer(modifier_pattern, expression)
        for match in modifiers:
            mod = int(match.group(1))
            total += mod
            # Only add non-zero modifiers to the display
            if mod != 0:
                rolls_text.append(f"{'+' if mod > 0 else ''}{mod}")
        
        # Format details
        details = " ".join(rolls_text)
        return total, details
    
    def _add_to_history(self, expression, result, details=None):
        """Add a roll to the history"""
        text = f"{expression}: {result}"
        if details:
            text += f" {details}"
        
        # Update the result display in both modes
        self._update_result_display(expression, result, details)
        
        # Store plain text in history
        self.roll_history.append(text)
        
        # Add to history list with color coding but plain text (no HTML)
        item = QListWidgetItem(text)
        item.setToolTip(text)  # Add tooltip for longer entries
        
        # Apply color formatting based on roll type
        is_crit_hit = "d20" in expression.lower() and result == 20
        is_crit_fail = "d20" in expression.lower() and result == 1
        
        if is_crit_hit:
            item.setForeground(QColor("white"))
            item.setBackground(QColor(0, 150, 0))  # Darker green background for better contrast
        elif is_crit_fail:
            item.setForeground(QColor("white"))
            item.setBackground(QColor(180, 0, 0))  # Darker red background for better contrast
        elif "d20" in expression.lower():
            # Regular d20 roll - use blue for visibility
            if result >= 15:
                # Good roll
                item.setForeground(QColor("darkblue"))
                item.setBackground(QColor(220, 220, 255))  # Light blue background
            elif result <= 5:
                # Poor roll
                item.setForeground(QColor("purple"))
                item.setBackground(QColor(240, 220, 240))  # Light purple background
        
        self.history_list.insertItem(0, item)
        
        # Keep history at a reasonable size
        while len(self.roll_history) > 50:
            self.roll_history.pop()
            self.history_list.takeItem(self.history_list.count() - 1)
            
        # Log to combat log if available
        self._log_roll_to_combat_log(expression, result, details)
    
    def _update_result_display(self, expression, result, details=None):
        """Update both result displays with the roll result"""
        # Format result for full mode display
        is_crit_hit = "d20" in expression.lower() and result == 20
        is_crit_fail = "d20" in expression.lower() and result == 1
        
        # Update full mode display
        if "d20" in expression.lower() and result == 20:
            result_text = f"<span style='font-size: 48px; font-weight: bold; color: white;'>{result}</span>"
            self.result_display.setStyleSheet("background-color: rgba(0, 200, 0, 0.5); color: white; font-weight: bold; border-radius: 5px; padding: 10px; border: 2px solid green;")
        elif "d20" in expression.lower() and result == 1:
            result_text = f"<span style='font-size: 48px; font-weight: bold; color: white;'>{result}</span>"
            self.result_display.setStyleSheet("background-color: rgba(200, 0, 0, 0.5); color: white; font-weight: bold; border-radius: 5px; padding: 10px; border: 2px solid red;")
        else:
            result_text = f"<span style='font-size: 36px; font-weight: bold;'>{result}</span>"
            self.result_display.setStyleSheet("background-color: rgba(0, 0, 0, 0.1); border-radius: 5px; padding: 10px;")
        
        expr_text = f"<span style='font-size: 14px; color: #555;'>{expression}</span>"
        self.result_display.setText(f"{result_text}<br>{expr_text}")
        
        # Also update mini mode display
        self._update_mini_result(expression, result, details)
    
    def _update_saved_roll_combo(self):
        """Update the saved rolls combo boxes in both modes"""
        # Update full mode combo
        self.saved_roll_combo.clear()
        self.saved_roll_combo.addItem("-- Select Saved Formula --")
        
        for name in sorted(self.saved_rolls.keys()):
            self.saved_roll_combo.addItem(f"{name} ({self.saved_rolls[name]})")
            
        # Also update mini mode combo if it exists
        if hasattr(self, 'mini_saved_roll_combo'):
            self.mini_saved_roll_combo.clear()
            self.mini_saved_roll_combo.addItem("-- Saved --")
            for name in sorted(self.saved_rolls.keys()):
                self.mini_saved_roll_combo.addItem(f"{name}")
    
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
                
                # Load mini mode preference
                self.mini_mode = self.app_state.get_panel_setting("dice_roller", "mini_mode", False)
                if self.mini_mode:
                    # Delay setting mini mode until after UI setup
                    QTimer.singleShot(100, lambda: self._toggle_mini_mode(True))
        except Exception as e:
            print(f"Unexpected error accessing config: {e}")
    
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
        
        # Reset the result display with the same styling as our enhanced display
        default_text = f"<span style='font-size: 24px; font-weight: bold;'>Roll some dice</span><br><span style='font-size: 14px; color: #555;'>Use buttons or formula above</span>"
        self.result_display.setText(default_text)
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
    
    def _is_valid_formula(self, formula):
        """Check if a dice formula is valid"""
        # Remove spaces for easier validation
        formula = formula.replace(" ", "").lower()
        
        # For complex dice expressions
        dice_pattern = r'(\d+)?d(\d+)'  # Pattern for dice components like 2d6
        modifier_pattern = r'([+-]\d+)'  # Pattern for modifiers like +3
        
        # Check if there's at least one dice component
        dice_matches = list(re.finditer(dice_pattern, formula))
        if not dice_matches:
            return False
            
        # Build a pattern that combines dice and modifiers
        # This checks that the formula consists entirely of valid dice/modifier components
        full_pattern = dice_pattern + '|' + modifier_pattern
        all_components = re.findall(full_pattern, formula)
        
        # If the joined components don't equal the original formula, there's invalid content
        joined = ''.join(''.join(match) for match in all_components)
        return joined == formula
    
    def _save_current_formula(self):
        """Save the current formula"""
        formula = self.roll_input.text().strip()
        if not formula:
            return
            
        # Verify it's a valid formula
        if not self._is_valid_formula(formula):
            QMessageBox.warning(self, "Invalid Formula", 
                               "Please enter a valid dice formula (e.g. 2d6+3 or 1d8+2d4+5)")
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
                "Enter the dice formula (e.g. 2d6+3 or 1d8+2d4+5):"
            )
            
            if ok and formula:
                # Verify it's a valid formula
                if not self._is_valid_formula(formula):
                    QMessageBox.warning(self, "Invalid Formula", 
                                       "Please enter a valid dice formula (e.g. 2d6+3 or 1d8+2d4+5)")
                    return
                
                self.saved_rolls[name] = formula
                self._save_rolls()
                self._update_saved_roll_combo()
                
                # Select the newly added formula
                index = self.saved_roll_combo.findText(f"{name} ({formula})")
                if index >= 0:
                    self.saved_roll_combo.setCurrentIndex(index)
    
    def save_state(self):
        """Save the panel state"""
        return {
            "mini_mode": self.mini_mode,
            "saved_rolls": self.saved_rolls,
            "roll_history": self.roll_history
        }
    
    def restore_state(self, state):
        """Restore the panel state from saved data"""
        if not state:
            return
            
        # Restore saved rolls
        if "saved_rolls" in state and isinstance(state["saved_rolls"], dict):
            self.saved_rolls = state["saved_rolls"]
            self._update_saved_roll_combo()
            
        # Restore roll history
        if "roll_history" in state and isinstance(state["roll_history"], list):
            self.roll_history = state["roll_history"]
            self.history_list.clear()
            
            # Add history items in reverse order (newest at top)
            for text in reversed(self.roll_history):
                item = QListWidgetItem(text)
                item.setToolTip(text)
                self.history_list.addItem(item)
            
        # Restore mini mode state
        if "mini_mode" in state:
            mini_mode = state["mini_mode"]
            # Use a timer to ensure UI is fully set up before switching modes
            QTimer.singleShot(100, lambda: self._toggle_mini_mode(mini_mode))
    
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
    
    def _save_rolls(self):
        """Save the roll formulas to config"""
        config_dir = self.app_state.config_dir
        saved_rolls_file = config_dir / "saved_dice_rolls.json"
        
        try:
            with open(saved_rolls_file, 'w') as f:
                json.dump(self.saved_rolls, f, indent=2)
        except Exception as e:
            print(f"Error saving dice rolls: {e}")
