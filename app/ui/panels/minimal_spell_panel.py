"""
Minimal spell panel for testing

This is a minimal implementation of the spell panel for testing purposes.
"""

from PySide6.QtWidgets import QVBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from app.ui.panels.base_panel import BasePanel


class MinimalSpellPanel(BasePanel):
    """
    Minimal implementation of spell panel for testing
    """
    
    def __init__(self, app_state, panel_id=None):
        """Initialize the minimal spell panel"""
        super().__init__(app_state, "Spell Reference")
        
        # Create own layout without calling super()._setup_ui()
        layout = QVBoxLayout(self)
        
        # Add a label
        title_label = QLabel("Minimal Spell Panel")
        title_label.setAlignment(Qt.AlignCenter)
        font = QFont()
        font.setPointSize(16)
        font.setBold(True)
        title_label.setFont(font)
        layout.addWidget(title_label)
        
        # Add a description
        description = QLabel(
            "This is a minimal implementation of the spell panel for testing purposes.\n"
            "The full spell reference panel will be implemented in the future."
        )
        description.setAlignment(Qt.AlignCenter)
        description.setWordWrap(True)
        layout.addWidget(description)
        
        # Add a dummy button
        button = QPushButton("Click Me (Does Nothing)")
        layout.addWidget(button)
        
        # Add spacer
        layout.addStretch(1)
    
    def save_state(self):
        """Save panel state"""
        return {}
    
    def restore_state(self, state):
        """Restore panel state"""
        pass 