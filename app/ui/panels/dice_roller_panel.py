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
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLineEdit, QLabel, QListWidget, QGroupBox,
    QSpinBox, QComboBox, QCheckBox, QMessageBox
)
from PySide6.QtCore import Qt
from app.ui.panels.base_panel import BasePanel

class DiceRollerPanel(BasePanel):
    """Panel for rolling dice and managing roll history"""
    
    def __init__(self, app_state):
        """Initialize the dice roller panel"""
        super().__init__(app_state, "Dice Roller")
        self.roll_history = []
        self.saved_rolls = {}
    
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
        
        # Custom roll input
        custom_roll_group = QGroupBox("Custom Roll")
        custom_roll_layout = QHBoxLayout()
        
        self.roll_input = QLineEdit()
        self.roll_input.setPlaceholderText("Enter roll (e.g. 2d6+3)")
        self.roll_input.returnPressed.connect(self._custom_roll)
        custom_roll_layout.addWidget(self.roll_input)
        
        roll_button = QPushButton("Roll")
        roll_button.clicked.connect(self._custom_roll)
        custom_roll_layout.addWidget(roll_button)
        
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
        history_layout.addWidget(self.history_list)
        
        clear_history = QPushButton("Clear History")
        clear_history.clicked.connect(self._clear_history)
        history_layout.addWidget(clear_history)
        
        history_group.setLayout(history_layout)
        layout.addWidget(history_group)
        
        # Set the layout for this panel
        self.setLayout(layout)
    
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
        
        self.roll_history.append(text)
        self.history_list.insertItem(0, text)
        
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
