"""
Minimal Spell Reference Panel for testing

A minimal implementation to identify and fix issues with the main spell panel.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from app.ui.panels.base_panel import BasePanel


class MinimalSpellPanel(BasePanel):
    """
    Minimal panel for testing spell reference
    """
    
    def __init__(self, app_state, panel_id=None):
        """Initialize the minimal spell panel"""
        super().__init__(app_state, "Minimal Spell Panel")
    
    def _setup_ui(self):
        """Set up a simple UI for the panel"""
        # Create a layout directly on this widget
        layout = QVBoxLayout(self)
        
        label = QLabel("This is a minimal spell panel for testing")
        label.setAlignment(Qt.AlignCenter)
        font = QFont()
        font.setPointSize(14)
        font.setBold(True)
        label.setFont(font)
        
        layout.addWidget(label)
    
    def save_state(self):
        """Save panel state"""
        return {}
    
    def restore_state(self, state):
        """Restore panel state"""
        pass 