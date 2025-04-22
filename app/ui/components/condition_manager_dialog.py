"""
Condition Manager Dialog

This module provides a dialog for managing conditions on combatants,
allowing DMs to add, edit, and remove conditions during combat.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QComboBox, QSpinBox,
    QDialogButtonBox, QFormLayout, QWidget, QStackedWidget,
    QCheckBox, QLineEdit
)
from PySide6.QtCore import Qt, Signal, Slot, QSize
from PySide6.QtGui import QIcon

from app.combat.conditions import ConditionType, ConditionManager
from app.ui.components.condition_display import ConditionIcon
import logging

logger = logging.getLogger(__name__)


class ConditionListItem(QWidget):
    """Custom list item widget for displaying a condition."""
    
    remove_clicked = Signal(ConditionType)
    
    def __init__(self, condition_type: ConditionType, parent=None):
        super().__init__(parent)
        self.condition_type = condition_type
        
        # Set up the layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        
        # Add condition icon
        self.icon = ConditionIcon(condition_type, self)
        layout.addWidget(self.icon)
        
        # Add condition name
        name = condition_type.name.replace("_", " ").title()
        self.name_label = QLabel(name)
        layout.addWidget(self.name_label)
        
        # Add spacer
        layout.addStretch()
        
        # Add remove button
        self.remove_btn = QPushButton("Remove")
        self.remove_btn.setMaximumWidth(80)
        self.remove_btn.clicked.connect(lambda: self.remove_clicked.emit(condition_type))
        layout.addWidget(self.remove_btn)
        
        self.setLayout(layout)


class ExhaustionConfigWidget(QWidget):
    """Widget for configuring exhaustion level."""
    
    def __init__(self, initial_level=1, parent=None):
        super().__init__(parent)
        layout = QFormLayout(self)
        
        # Exhaustion level spinner
        self.level_spinner = QSpinBox(self)
        self.level_spinner.setMinimum(1)
        self.level_spinner.setMaximum(6)
        self.level_spinner.setValue(initial_level)
        
        layout.addRow("Exhaustion Level:", self.level_spinner)
        
        # Information about levels
        info_label = QLabel(
            "Level 1: Disadvantage on ability checks\n"
            "Level 2: Speed halved\n"
            "Level 3: Disadvantage on attack rolls and saving throws\n"
            "Level 4: Hit point maximum halved\n"
            "Level 5: Speed reduced to 0\n"
            "Level 6: Death"
        )
        info_label.setWordWrap(True)
        layout.addRow(info_label)
        
        self.setLayout(layout)
    
    def get_level(self) -> int:
        """Get the configured exhaustion level."""
        return self.level_spinner.value()


class ConcentrationConfigWidget(QWidget):
    """Widget for configuring concentration details."""
    
    def __init__(self, spell_name="", parent=None):
        super().__init__(parent)
        layout = QFormLayout(self)
        
        # Spell being concentrated on
        self.spell_name = QLineEdit(self)
        self.spell_name.setText(spell_name)
        layout.addRow("Concentrating On:", self.spell_name)
        
        self.setLayout(layout)
    
    def get_spell_name(self) -> str:
        """Get the spell being concentrated on."""
        return self.spell_name.text().strip()


class ConditionManagerDialog(QDialog):
    """Dialog for managing conditions on a combatant."""
    
    def __init__(self, combatant_id: str, combatant_name: str, 
                condition_manager: ConditionManager = None, parent=None):
        super().__init__(parent)
        self.combatant_id = combatant_id
        self.combatant_name = combatant_name
        self.condition_manager = condition_manager or ConditionManager()
        
        self.setWindowTitle(f"Manage Conditions: {combatant_name}")
        self.resize(400, 500)
        
        self._setup_ui()
        self._load_conditions()
    
    def _setup_ui(self):
        """Set up the dialog UI elements."""
        layout = QVBoxLayout(self)
        
        # Header with combatant name
        header_label = QLabel(f"<h2>Conditions for {self.combatant_name}</h2>")
        header_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(header_label)
        
        # Horizontal layout for condition list and add panel
        main_layout = QHBoxLayout()
        
        # Left side: Condition list
        list_layout = QVBoxLayout()
        list_label = QLabel("<b>Active Conditions:</b>")
        list_layout.addWidget(list_label)
        
        self.condition_list = QListWidget()
        self.condition_list.setMinimumWidth(200)
        list_layout.addWidget(self.condition_list)
        
        main_layout.addLayout(list_layout)
        
        # Right side: Add condition panel
        add_layout = QVBoxLayout()
        add_label = QLabel("<b>Add Condition:</b>")
        add_layout.addWidget(add_label)
        
        # Condition selection
        self.condition_combo = QComboBox()
        for condition_type in ConditionType:
            # Skip conditions that are handled specially
            self.condition_combo.addItem(
                condition_type.name.replace("_", " ").title(), 
                condition_type
            )
        
        add_layout.addWidget(self.condition_combo)
        
        # Configuration stack
        self.config_stack = QStackedWidget()
        self.config_stack.setMinimumHeight(150)
        
        # Default empty config
        self.default_config = QWidget()
        self.config_stack.addWidget(self.default_config)
        
        # Exhaustion config
        self.exhaustion_config = ExhaustionConfigWidget()
        self.config_stack.addWidget(self.exhaustion_config)
        
        # Concentration config
        self.concentration_config = ConcentrationConfigWidget()
        self.config_stack.addWidget(self.concentration_config)
        
        add_layout.addWidget(self.config_stack)
        
        # Add condition button
        self.add_button = QPushButton("Add Condition")
        self.add_button.clicked.connect(self._add_condition)
        add_layout.addWidget(self.add_button)
        
        add_layout.addStretch()
        main_layout.addLayout(add_layout)
        
        layout.addLayout(main_layout)
        
        # Dialog buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        # Connect signals
        self.condition_combo.currentIndexChanged.connect(self._update_config_panel)
        
        self.setLayout(layout)
        
        # Initialize with the current selection
        self._update_config_panel()
    
    def _update_config_panel(self):
        """Update the configuration panel based on selected condition."""
        current_condition = self.condition_combo.currentData()
        
        if current_condition == ConditionType.EXHAUSTION:
            self.config_stack.setCurrentWidget(self.exhaustion_config)
        elif current_condition == ConditionType.CONCENTRATION:
            self.config_stack.setCurrentWidget(self.concentration_config)
        else:
            self.config_stack.setCurrentWidget(self.default_config)
    
    def _load_conditions(self):
        """Load the combatant's conditions into the list."""
        # Clear existing items
        self.condition_list.clear()
        
        # Get combatant conditions
        conditions = self.condition_manager.get_conditions(self.combatant_id)
        if not conditions:
            return
            
        # Add each condition as a list item
        for condition_name, condition_data in conditions.items():
            try:
                condition_type = ConditionType[condition_name.upper()]
                self._add_condition_to_list(condition_type)
            except (KeyError, ValueError) as e:
                logger.warning(f"Unknown condition: {condition_name} - {e}")
    
    def _add_condition_to_list(self, condition_type: ConditionType):
        """Add a condition to the list widget."""
        # Create list item
        item = QListWidgetItem()
        item.setSizeHint(QSize(0, 40))  # Minimum height
        
        # Create widget for the item
        widget = ConditionListItem(condition_type)
        widget.remove_clicked.connect(self._remove_condition)
        
        # Add to list
        self.condition_list.addItem(item)
        self.condition_list.setItemWidget(item, widget)
    
    def _add_condition(self):
        """Add the selected condition to the combatant."""
        condition_type = self.condition_combo.currentData()
        if not condition_type:
            return
            
        # Check if already has this condition
        if self.condition_manager.has_condition(self.combatant_id, condition_type.name.lower()):
            # If it's exhaustion, update the level
            if condition_type == ConditionType.EXHAUSTION:
                level = self.exhaustion_config.get_level()
                self.condition_manager.add_exhaustion(self.combatant_id, level)
            return
            
        # Add the condition
        if condition_type == ConditionType.EXHAUSTION:
            # Add exhaustion with level
            level = self.exhaustion_config.get_level()
            self.condition_manager.add_exhaustion(self.combatant_id, level)
        elif condition_type == ConditionType.CONCENTRATION:
            # Add concentration with spell name
            spell_name = self.concentration_config.get_spell_name()
            self.condition_manager.add_condition(self.combatant_id, 
                                                condition_type.name.lower(),
                                                {"spell": spell_name})
        else:
            # Add regular condition
            self.condition_manager.add_condition(self.combatant_id, condition_type.name.lower())
        
        # Update the list
        self._add_condition_to_list(condition_type)
    
    def _remove_condition(self, condition_type: ConditionType):
        """Remove a condition from the combatant."""
        self.condition_manager.remove_condition(self.combatant_id, condition_type.name.lower())
        
        # Remove from UI list
        for i in range(self.condition_list.count()):
            item = self.condition_list.item(i)
            widget = self.condition_list.itemWidget(item)
            if widget.condition_type == condition_type:
                self.condition_list.takeItem(i)
                break
    
    def get_condition_manager(self) -> ConditionManager:
        """Get the updated condition manager instance."""
        return self.condition_manager 