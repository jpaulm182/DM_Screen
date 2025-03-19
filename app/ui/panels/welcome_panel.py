# app/ui/panels/welcome_panel.py - Welcome panel
"""
Welcome panel for the DM Screen application

Provides quick access to create common panels and get started.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QSpacerItem, QSizePolicy
)
from PySide6.QtCore import Qt

class WelcomePanel(QWidget):
    """Welcome panel with quick access buttons"""
    
    def __init__(self, panel_manager):
        """Initialize the welcome panel"""
        super().__init__()
        self.panel_manager = panel_manager
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the welcome panel UI"""
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(20)
        
        # Welcome message
        title = QLabel("Welcome to DM Screen")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        layout.addWidget(title)
        
        description = QLabel(
            "Get started by opening one of these common panels\n"
            "or use the menus above to access all features."
        )
        description.setAlignment(Qt.AlignCenter)
        description.setStyleSheet("font-size: 14px;")
        layout.addWidget(description)
        
        # Add some spacing
        layout.addSpacing(30)
        
        # Quick access buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(20)
        button_layout.setAlignment(Qt.AlignCenter)
        
        # Define the quick access panels
        quick_panels = [
            ("Combat Tracker", "combat_tracker", "Track initiative and combat encounters"),
            ("Dice Roller", "dice_roller", "Roll dice and save common rolls"),
        ]
        
        # Create buttons for each panel
        for title, panel_type, tooltip in quick_panels:
            button = QPushButton(title)
            button.setMinimumSize(150, 100)
            button.setToolTip(tooltip)
            button.setStyleSheet("""
                QPushButton {
                    font-size: 14px;
                    padding: 10px;
                }
            """)
            button.clicked.connect(lambda checked, pt=panel_type: self._open_panel(pt))
            button_layout.addWidget(button)
        
        layout.addLayout(button_layout)
        
        # Add stretching space at the bottom
        layout.addStretch()
        
        self.setLayout(layout)
    
    def _open_panel(self, panel_type):
        """Open a panel of the specified type"""
        self.panel_manager.create_panel(panel_type)
