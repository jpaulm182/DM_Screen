# app/ui/panels/welcome_panel.py - Welcome panel
"""
Welcome panel with quick access to all panel types
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QGroupBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPixmap

from app.ui.panels.panel_category import PanelCategory


class WelcomePanel(QWidget):
    """Welcome panel with quick access buttons"""
    
    def __init__(self, panel_manager):
        """Initialize the welcome panel"""
        super().__init__()
        self.panel_manager = panel_manager
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the welcome panel UI"""
        # Main layout
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)
        
        # Header with title
        header_layout = QHBoxLayout()
        title = QLabel("DM Screen")
        title_font = QFont()
        title_font.setPointSize(24)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignCenter)
        
        header_layout.addStretch()
        header_layout.addWidget(title)
        header_layout.addStretch()
        
        layout.addLayout(header_layout)
        
        # Welcome message
        welcome_text = QLabel("Welcome to your digital Dungeon Master's screen!")
        welcome_text.setAlignment(Qt.AlignCenter)
        welcome_font = QFont()
        welcome_font.setPointSize(14)
        welcome_text.setFont(welcome_font)
        layout.addWidget(welcome_text)
        
        # Button grid layout for panels
        panels_layout = QGridLayout()
        panels_layout.setSpacing(15)
        
        # Group panels by category
        self._add_category_panels(panels_layout)
        
        layout.addLayout(panels_layout)
        
        # Add stretching space at the bottom
        layout.addStretch()
        
        self.setLayout(layout)
    
    def _add_category_panels(self, layout):
        """Add grouped panels by category"""
        row = 0
        
        # Combat Tools
        combat_group = self._create_category_group(
            "Combat Tools", 
            PanelCategory.COMBAT, 
            [
                ("Combat Tracker", "combat_tracker", "Initiative and combat management"),
                ("Dice Roller", "dice_roller", "Roll dice and save commonly used roll patterns")
            ]
        )
        layout.addWidget(combat_group, row, 0)
        
        # Reference Tools
        reference_group = self._create_category_group(
            "Reference Materials", 
            PanelCategory.REFERENCE, 
            [
                ("Rules Reference", "rules_reference", "Quick access to D&D 5e rules"),
                ("Conditions", "conditions", "Reference for character conditions"),
                ("Monsters", "monster", "Monster reference and lookup"),
                ("Spells", "spell_reference", "Spell reference and lookup")
            ]
        )
        layout.addWidget(reference_group, row, 1)
        
        row += 1
        
        # Campaign Tools
        campaign_group = self._create_category_group(
            "Campaign Management", 
            PanelCategory.CAMPAIGN, 
            [
                ("Session Notes", "session_notes", "Take and organize session notes")
            ]
        )
        layout.addWidget(campaign_group, row, 0)
        
        # Utility Tools
        utility_group = self._create_category_group(
            "Utility Tools", 
            PanelCategory.UTILITY, 
            [
                ("Weather Generator", "weather", "Generate random weather conditions"),
                ("Time Tracker", "time_tracker", "Track time and calendar events")
            ]
        )
        layout.addWidget(utility_group, row, 1)
    
    def _create_category_group(self, title, category, panels):
        """Create a group box with buttons for a category of panels"""
        group = QGroupBox(title)
        
        # Get colors for this category
        colors = PanelCategory.get_colors(panels[0][1]) if panels else None
        if colors:
            # Style the group box with category colors
            group.setStyleSheet(f"""
                QGroupBox {{
                    border: 2px solid {colors['border'].name()};
                    border-radius: 6px;
                    margin-top: 1.5ex;
                    font-weight: bold;
                    padding: 10px;
                }}
                QGroupBox::title {{
                    subcontrol-origin: margin;
                    subcontrol-position: top center;
                    padding: 0 5px;
                    color: {colors['title_text'].name()};
                    background-color: {colors['title_bg'].name()};
                }}
            """)
        
        # Grid layout for buttons inside the group
        grid = QGridLayout(group)
        grid.setSpacing(8)
        
        # Add buttons for each panel in this category
        for i, (title, panel_type, tooltip) in enumerate(panels):
            row, col = divmod(i, 2)  # Arrange in 2 columns
            button = QPushButton(title)
            button.setMinimumSize(140, 80)
            button.setToolTip(tooltip)
            
            # Style the button
            if colors:
                button.setStyleSheet(f"""
                    QPushButton {{
                        font-size: 12px;
                        padding: 8px;
                        background-color: {colors['title_bg'].name()};
                        color: {colors['title_text'].name()};
                        border: 1px solid {colors['border'].name()};
                        border-radius: 4px;
                    }}
                    QPushButton:hover {{
                        background-color: {colors['border'].name()};
                    }}
                """)
                
            button.clicked.connect(lambda checked, pt=panel_type: self._open_panel(pt))
            grid.addWidget(button, row, col)
        
        return group
    
    def _open_panel(self, panel_type):
        """Open a panel of the specified type"""
        self.panel_manager.create_panel(panel_type)
