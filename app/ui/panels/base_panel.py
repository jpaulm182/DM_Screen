# app/ui/panels/base_panel.py - Base panel class
"""
Base panel class for all DM Screen panels

Defines the common functionality and interface for all panel types.
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt


class BasePanel(QWidget):
    """
    Base class for all panel widgets
    
    Provides common functionality and interface that all panels should implement.
    """
    
    def __init__(self, app_state, title="Panel"):
        """Initialize the base panel"""
        super().__init__()
        self.app_state = app_state
        self._title = title
        
        # Set up the panel
        self._setup_ui()
    
    @property
    def title(self):
        """Get the panel title"""
        return self._title
    
    def _setup_ui(self):
        """
        Set up the panel UI - to be implemented by subclasses
        
        Base implementation creates a placeholder label if no layout is set
        """
        if not self.layout():
            layout = QVBoxLayout()
            layout.setContentsMargins(4, 4, 4, 4)
            layout.setSpacing(4)
            
            label = QLabel(f"Panel: {self._title}")
            label.setAlignment(Qt.AlignCenter)
            layout.addWidget(label)
            
            self.setLayout(layout)
    
    def save_state(self):
        """
        Save the panel state - to be implemented by subclasses
        
        Returns:
            A dictionary of panel state data
        """
        return {}
    
    def restore_state(self, state):
        """
        Restore the panel state - to be implemented by subclasses
        
        Args:
            state: Dictionary of panel state data
        """
        pass
