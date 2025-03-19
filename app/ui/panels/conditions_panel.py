"""
Conditions reference panel for D&D 5e

Features:
- Quick reference for all D&D 5e conditions
- Detailed descriptions and effects
- Quick-apply functionality for Combat Tracker
- Search and filter capabilities
"""

from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QTextEdit, QLineEdit, QWidget,
    QMenu
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from app.ui.panels.base_panel import BasePanel

# D&D 5e Conditions with their descriptions
CONDITIONS = {
    "Blinded": """
• A blinded creature can't see and automatically fails any ability check that requires sight.
• Attack rolls against the creature have advantage, and the creature's attack rolls have disadvantage.""",

    "Charmed": """
• A charmed creature can't attack the charmer or target them with harmful abilities or magical effects.
• The charmer has advantage on any ability check to interact socially with the creature.""",

    "Deafened": """
• A deafened creature can't hear and automatically fails any ability check that requires hearing.""",

    "Frightened": """
• A frightened creature has disadvantage on ability checks and attack rolls while the source of its fear is within line of sight.
• The creature can't willingly move closer to the source of its fear.""",

    "Grappled": """
• A grappled creature's speed becomes 0, and it can't benefit from any bonus to its speed.
• The condition ends if the grappler is incapacitated.
• The condition also ends if an effect removes the grappled creature from the reach of the grappler.""",

    "Incapacitated": """
• An incapacitated creature can't take actions or reactions.""",

    "Invisible": """
• An invisible creature is impossible to see without special means.
• The creature's location can be detected by any noise it makes or tracks it leaves.
• Attack rolls against the creature have disadvantage.
• The creature's attack rolls have advantage.""",

    "Paralyzed": """
• A paralyzed creature is incapacitated and can't move or speak.
• The creature automatically fails Strength and Dexterity saving throws.
• Attack rolls against the creature have advantage.
• Any attack that hits the creature is a critical hit if the attacker is within 5 feet.""",

    "Petrified": """
• A petrified creature is transformed into solid inanimate matter and is incapacitated.
• Its weight increases by a factor of ten, and it ceases aging.
• The creature is immune to poison and disease.
• Attack rolls against the creature have advantage.""",

    "Poisoned": """
• A poisoned creature has disadvantage on attack rolls and ability checks.""",

    "Prone": """
• A prone creature's only movement option is to crawl.
• The creature has disadvantage on attack rolls.
• Attack rolls against the creature have advantage if the attacker is within 5 feet.
• Otherwise, attack rolls against the creature have disadvantage.""",

    "Restrained": """
• A restrained creature's speed becomes 0, and it can't benefit from any bonus to its speed.
• Attack rolls against the creature have advantage.
• The creature's attack rolls have disadvantage.
• The creature has disadvantage on Dexterity saving throws.""",

    "Stunned": """
• A stunned creature is incapacitated, can't move, and can speak only falteringly.
• The creature automatically fails Strength and Dexterity saving throws.
• Attack rolls against the creature have advantage.""",

    "Unconscious": """
• An unconscious creature is incapacitated, can't move or speak, and is unaware of its surroundings.
• The creature drops whatever it's holding and falls prone.
• The creature automatically fails Strength and Dexterity saving throws.
• Attack rolls against the creature have advantage.
• Any attack that hits the creature is a critical hit if the attacker is within 5 feet."""
}

class ConditionsPanel(BasePanel):
    """Panel for referencing and applying D&D 5e conditions"""
    
    condition_applied = Signal(str)  # Signal emitted when condition is applied
    
    def __init__(self, app_state):
        super().__init__(app_state, "Conditions Reference")
        self.current_condition = None
    
    def _setup_ui(self):
        """Set up the conditions panel UI"""
        main_layout = QVBoxLayout()
        
        # Search bar
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search conditions...")
        self.search_input.textChanged.connect(self._filter_conditions)
        search_layout.addWidget(self.search_input)
        main_layout.addLayout(search_layout)
        
        # Split view layout
        content_layout = QHBoxLayout()
        
        # Conditions list
        self.conditions_list = QListWidget()
        self.conditions_list.addItems(sorted(CONDITIONS.keys()))
        self.conditions_list.currentItemChanged.connect(self._show_condition)
        self.conditions_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.conditions_list.customContextMenuRequested.connect(self._show_context_menu)
        content_layout.addWidget(self.conditions_list)
        
        # Description area
        description_layout = QVBoxLayout()
        
        # Condition title
        self.condition_title = QLabel()
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(12)
        self.condition_title.setFont(title_font)
        description_layout.addWidget(self.condition_title)
        
        # Condition description
        self.description_text = QTextEdit()
        self.description_text.setReadOnly(True)
        description_layout.addWidget(self.description_text)
        
        # Quick apply button
        self.apply_button = QPushButton("Apply to Selected")
        self.apply_button.clicked.connect(self._apply_condition)
        description_layout.addWidget(self.apply_button)
        
        content_layout.addLayout(description_layout)
        content_layout.setStretchFactor(self.conditions_list, 1)
        content_layout.setStretchFactor(description_layout, 2)
        
        main_layout.addLayout(content_layout)
        
        # Set minimum sizes
        self.setMinimumSize(600, 400)
        self.conditions_list.setMinimumWidth(150)
        
        self.setLayout(main_layout)
        
        # Show first condition by default
        if self.conditions_list.count() > 0:
            self.conditions_list.setCurrentRow(0)
    
    def _show_condition(self, current, previous):
        """Display the selected condition's details"""
        if current:
            condition_name = current.text()
            self.current_condition = condition_name
            self.condition_title.setText(condition_name)
            self.description_text.setText(CONDITIONS[condition_name].strip())
    
    def _filter_conditions(self, text):
        """Filter the conditions list based on search text"""
        search_text = text.lower()
        for i in range(self.conditions_list.count()):
            item = self.conditions_list.item(i)
            item.setHidden(search_text not in item.text().lower())
    
    def _apply_condition(self):
        """Apply the current condition to selected combatants"""
        if self.current_condition:
            self.condition_applied.emit(self.current_condition)
    
    def _show_context_menu(self, position):
        """Show context menu for conditions list"""
        menu = QMenu()
        if self.conditions_list.currentItem():
            apply_action = menu.addAction("Apply Condition")
            apply_action.triggered.connect(self._apply_condition)
            menu.exec_(self.conditions_list.mapToGlobal(position)) 