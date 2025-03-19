# app/ui/layout_name_dialog.py - Layout name input dialog
"""
Dialog for naming and saving panel layouts

This dialog allows users to input a name when saving a layout configuration.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QCheckBox, QComboBox, QMessageBox
)
from PySide6.QtCore import Qt

class LayoutNameDialog(QDialog):
    """Dialog for naming a layout when saving"""
    
    def __init__(self, parent=None, existing_layouts=None, current_layout=None):
        """Initialize the layout name dialog
        
        Args:
            parent: Parent widget
            existing_layouts: List of existing layout names
            current_layout: Name of the currently loaded layout (if any)
        """
        super().__init__(parent)
        
        self.existing_layouts = existing_layouts or []
        self.current_layout = current_layout
        
        self.setWindowTitle("Save Layout")
        self.setMinimumWidth(350)
        self.layout_name = ""
        self.is_preset = False
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the dialog UI"""
        layout = QVBoxLayout(self)
        
        # Name input section
        name_label = QLabel("Layout Name:")
        self.name_edit = QLineEdit()
        if self.current_layout:
            self.name_edit.setText(self.current_layout)
        
        layout.addWidget(name_label)
        layout.addWidget(self.name_edit)
        
        # Preset checkbox
        self.preset_checkbox = QCheckBox("Save as preset (recommended for specialized layouts)")
        layout.addWidget(self.preset_checkbox)
        
        # Preset category section (only enabled when preset is checked)
        category_layout = QHBoxLayout()
        category_label = QLabel("Category:")
        self.category_combo = QComboBox()
        self.category_combo.addItems(["Combat", "Exploration", "Social", "Reference", "Custom"])
        self.category_combo.setEnabled(False)
        
        category_layout.addWidget(category_label)
        category_layout.addWidget(self.category_combo)
        layout.addLayout(category_layout)
        
        # Connect checkbox to enable/disable category
        self.preset_checkbox.toggled.connect(self.category_combo.setEnabled)
        
        # Warning for existing names
        self.warning_label = QLabel("")
        self.warning_label.setStyleSheet("color: red;")
        self.warning_label.hide()
        layout.addWidget(self.warning_label)
        
        # Connect text changed to check for duplicates
        self.name_edit.textChanged.connect(self._check_name)
        
        # Buttons
        button_layout = QHBoxLayout()
        save_button = QPushButton("Save")
        save_button.clicked.connect(self.accept)
        
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        
        button_layout.addWidget(save_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)
    
    def _check_name(self):
        """Check if the entered name already exists"""
        name = self.name_edit.text().strip()
        
        if not name:
            self.warning_label.setText("Layout name cannot be empty")
            self.warning_label.show()
            return
        
        if name in self.existing_layouts and name != self.current_layout:
            self.warning_label.setText("A layout with this name already exists and will be overwritten")
            self.warning_label.show()
        else:
            self.warning_label.hide()
    
    def accept(self):
        """Handle the accept action"""
        name = self.name_edit.text().strip()
        
        if not name:
            QMessageBox.warning(self, "Invalid Name", "Please enter a layout name.")
            return
        
        self.layout_name = name
        self.is_preset = self.preset_checkbox.isChecked()
        self.preset_category = self.category_combo.currentText() if self.is_preset else ""
        
        super().accept() 