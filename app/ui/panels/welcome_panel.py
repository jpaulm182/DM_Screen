# app/ui/panels/welcome_panel.py - Welcome panel
"""
Welcome panel with quick access to all panel types
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QGroupBox
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QPixmap

from app.ui.panels.panel_category import PanelCategory


class WelcomePanel(QWidget):
    """Welcome panel with quick access buttons"""
    
    def __init__(self, panel_manager):
        """Initialize the welcome panel"""
        super().__init__()
        self.panel_manager = panel_manager
        self.panel_buttons = {}  # Store buttons by panel_type for state updates
        self._setup_ui()
        
        # Set up timer to refresh button states
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self._update_button_states)
        self.update_timer.start(500)  # Update every 500ms
    
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
        
        # Smart Organize button at top
        organize_button = QPushButton("Smart Panel Organization")
        organize_button.setMinimumSize(200, 50)
        organize_button.setStyleSheet("""
            QPushButton {
                font-size: 14px;
                font-weight: bold;
                padding: 10px;
                background-color: #444499;
                color: white;
                border-radius: 5px;
                border: 2px solid #333388;
            }
            QPushButton:hover {
                background-color: #5555AA;
            }
            QPushButton:pressed {
                background-color: #333388;
            }
        """)
        organize_button.setToolTip("Automatically organize your open panels for optimal layout")
        organize_button.clicked.connect(self._smart_organize)
        
        # Add the organize button with some space around it
        organize_layout = QHBoxLayout()
        organize_layout.addStretch()
        organize_layout.addWidget(organize_button)
        organize_layout.addStretch()
        layout.addLayout(organize_layout)
        
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
        
        # Initial update of button states
        self._update_button_states()
    
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
            button.setToolTip(tooltip + " (click to toggle panel on/off)")
            button.setProperty("panel_type", panel_type)
            
            # Store button reference for later state updates
            self.panel_buttons[panel_type] = button
            
            # Apply initial style based on panel visibility
            self._apply_button_style(button, panel_type, colors)
                
            button.clicked.connect(lambda checked, pt=panel_type: self._toggle_panel(pt))
            grid.addWidget(button, row, col)
        
        return group
    
    def _apply_button_style(self, button, panel_type, colors):
        """Apply appropriate style to button based on panel state"""
        is_active = self.panel_manager.is_panel_visible(panel_type)
        
        if is_active:
            # Active style - brighter with highlighted border
            button.setStyleSheet(f"""
                QPushButton {{
                    font-size: 12px;
                    padding: 8px;
                    background-color: {colors['border'].name()};
                    color: {colors['title_text'].name()};
                    border: 2px solid white;
                    border-radius: 4px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background-color: {colors['title_bg'].name()};
                    border: 2px solid white;
                }}
            """)
        else:
            # Inactive style - normal appearance
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
    
    def _update_button_states(self):
        """Update all button states based on panel visibility"""
        for panel_type, button in self.panel_buttons.items():
            colors = PanelCategory.get_colors(panel_type)
            if colors:
                self._apply_button_style(button, panel_type, colors)
    
    def _toggle_panel(self, panel_type):
        """Toggle a panel of the specified type"""
        self.panel_manager.toggle_panel(panel_type)
        
        # Immediately update the button style for immediate feedback
        button = self.panel_buttons.get(panel_type)
        if button:
            colors = PanelCategory.get_colors(panel_type)
            if colors:
                self._apply_button_style(button, panel_type, colors)
        
    def _smart_organize(self):
        """Trigger smart organization of panels"""
        # Call the smart organize function on the panel manager
        result = self.panel_manager.smart_organize_panels()
        
        # Update all button states
        self._update_button_states()
        
        # If there's a parent main window with a status bar, show a message
        main_window = self.window()
        if main_window and hasattr(main_window, "statusBar"):
            main_window.statusBar().showMessage(result)
            
    def hideEvent(self, event):
        """Stop the timer when the panel is hidden"""
        self.update_timer.stop()
        super().hideEvent(event)
        
    def showEvent(self, event):
        """Restart the timer when the panel is shown"""
        self.update_timer.start(500)
        super().showEvent(event)
