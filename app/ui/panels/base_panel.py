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
        
        # Call _setup_ui which will be implemented by subclasses
        # Do not create any layouts here to avoid conflicts
        self._setup_ui()
    
    @property
    def title(self):
        """Get the panel title"""
        return self._title
    
    def _setup_ui(self):
        """
        Set up the panel UI - to be implemented by subclasses
        
        Base implementation does nothing to avoid layout conflicts
        """
        pass
    
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
    
    def get_panel(self, panel_id):
        """
        Helper method to get another panel from the panel manager
        
        Args:
            panel_id: ID of the panel to retrieve
            
        Returns:
            The panel widget if found, None otherwise
        """
        # Find the panel manager (parent of parent)
        panel_manager = self.parent() and self.parent().parent()
        
        if not panel_manager:
            print(f"Could not find panel manager from {self.__class__.__name__}")
            return None
            
        # Get the requested panel
        panel_dock = getattr(panel_manager, 'get_panel', lambda x: None)(panel_id)
        
        if not panel_dock:
            print(f"Could not find panel {panel_id}")
            return None
            
        # Get the widget inside the dock
        panel_widget = panel_dock.widget()
        
        if not panel_widget:
            print(f"Panel {panel_id} has no widget")
            return None
            
        return panel_widget
