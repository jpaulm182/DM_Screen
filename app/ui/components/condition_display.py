"""
Condition Display Component

This module provides UI components for displaying conditions on combatants
in the combat tracker interface.
"""

from PySide6.QtWidgets import (
    QWidget, QLabel, QHBoxLayout, QVBoxLayout, 
    QGridLayout, QToolTip, QFrame
)
from PySide6.QtCore import Qt, QSize, Signal, QPoint
from PySide6.QtGui import QPixmap, QIcon, QMouseEvent, QPainter, QColor

from app.combat.conditions import ConditionType
import os
from pathlib import Path


class ConditionIcon(QLabel):
    """A clickable icon representing a condition with tooltip information."""
    
    clicked = Signal(ConditionType)
    
    def __init__(self, condition_type: ConditionType, parent=None):
        super().__init__(parent)
        self.condition_type = condition_type
        self.setFixedSize(24, 24)
        self.setToolTip(self._get_tooltip_text())
        self.setCursor(Qt.PointingHandCursor)
        self.setAlignment(Qt.AlignCenter)
        
        # Load condition icon
        self._load_icon()
        
    def _load_icon(self):
        """Load the appropriate icon for this condition."""
        # Map condition types to icon filenames
        icon_map = {
            ConditionType.BLINDED: "blinded.png",
            ConditionType.CHARMED: "charmed.png",
            ConditionType.DEAFENED: "deafened.png",
            ConditionType.EXHAUSTION: "exhaustion.png",
            ConditionType.FRIGHTENED: "frightened.png",
            ConditionType.GRAPPLED: "grappled.png",
            ConditionType.INCAPACITATED: "incapacitated.png",
            ConditionType.INVISIBLE: "invisible.png",
            ConditionType.PARALYZED: "paralyzed.png",
            ConditionType.PETRIFIED: "petrified.png",
            ConditionType.POISONED: "poisoned.png",
            ConditionType.PRONE: "prone.png",
            ConditionType.RESTRAINED: "restrained.png",
            ConditionType.STUNNED: "stunned.png",
            ConditionType.UNCONSCIOUS: "unconscious.png",
            ConditionType.CONCENTRATION: "concentration.png",
        }
        
        # Determine the path to the icons directory
        icons_dir = Path(__file__).parent.parent.parent / "resources" / "icons" / "conditions"
        
        # Default icon if not found
        icon_path = icons_dir / "generic_condition.png"
        
        # Try to find the specific icon
        if self.condition_type in icon_map:
            specific_path = icons_dir / icon_map[self.condition_type]
            if specific_path.exists():
                icon_path = specific_path
        
        # Load the icon if the file exists
        if icon_path.exists():
            pixmap = QPixmap(str(icon_path))
            self.setPixmap(pixmap.scaled(
                24, 24, 
                Qt.KeepAspectRatio, 
                Qt.SmoothTransformation
            ))
        else:
            # Fallback to text representation if icon not found
            self.setText(self._get_short_name())
    
    def _get_short_name(self) -> str:
        """Get a short text representation of the condition."""
        # Use first 2-3 letters for each condition
        condition_short_names = {
            ConditionType.BLINDED: "BL",
            ConditionType.CHARMED: "CH",
            ConditionType.DEAFENED: "DF",
            ConditionType.EXHAUSTION: "EX",
            ConditionType.FRIGHTENED: "FR",
            ConditionType.GRAPPLED: "GR",
            ConditionType.INCAPACITATED: "INC",
            ConditionType.INVISIBLE: "INV",
            ConditionType.PARALYZED: "PAR",
            ConditionType.PETRIFIED: "PET",
            ConditionType.POISONED: "POI",
            ConditionType.PRONE: "PRO",
            ConditionType.RESTRAINED: "RES",
            ConditionType.STUNNED: "STN",
            ConditionType.UNCONSCIOUS: "UNC",
            ConditionType.CONCENTRATION: "CON",
        }
        
        return condition_short_names.get(self.condition_type, "??")
    
    def _get_tooltip_text(self) -> str:
        """Generate tooltip text describing the condition."""
        condition_descriptions = {
            ConditionType.BLINDED: (
                "• A blinded creature can't see and automatically fails any ability check that requires sight.\n"
                "• Attack rolls against the creature have advantage, and the creature's attack rolls have disadvantage."
            ),
            ConditionType.CHARMED: (
                "• A charmed creature can't attack the charmer or target the charmer with harmful abilities or magical effects.\n"
                "• The charmer has advantage on any ability check to interact socially with the creature."
            ),
            ConditionType.DEAFENED: (
                "• A deafened creature can't hear and automatically fails any ability check that requires hearing."
            ),
            ConditionType.EXHAUSTION: (
                "• Level 1: Disadvantage on ability checks\n"
                "• Level 2: Speed halved\n"
                "• Level 3: Disadvantage on attack rolls and saving throws\n"
                "• Level 4: Hit point maximum halved\n"
                "• Level 5: Speed reduced to 0\n"
                "• Level 6: Death"
            ),
            ConditionType.FRIGHTENED: (
                "• A frightened creature has disadvantage on ability checks and attack rolls while the source of its fear is within line of sight.\n"
                "• The creature can't willingly move closer to the source of its fear."
            ),
            ConditionType.GRAPPLED: (
                "• A grappled creature's speed becomes 0, and it can't benefit from any bonus to its speed.\n"
                "• The condition ends if the grappler is incapacitated.\n"
                "• The condition also ends if an effect removes the grappled creature from the reach of the grappler."
            ),
            ConditionType.INCAPACITATED: (
                "• An incapacitated creature can't take actions or reactions."
            ),
            ConditionType.INVISIBLE: (
                "• An invisible creature is impossible to see without special senses.\n"
                "• The creature's location can be detected by any noise it makes or tracks it leaves.\n"
                "• Attack rolls against the creature have disadvantage, and the creature's attack rolls have advantage."
            ),
            ConditionType.PARALYZED: (
                "• A paralyzed creature is incapacitated and can't move or speak.\n"
                "• The creature automatically fails Strength and Dexterity saving throws.\n"
                "• Attack rolls against the creature have advantage.\n"
                "• Any attack that hits the creature is a critical hit if the attacker is within 5 feet."
            ),
            ConditionType.PETRIFIED: (
                "• A petrified creature is transformed into a solid inanimate substance and is incapacitated.\n"
                "• The creature's weight increases by a factor of ten, and it ceases aging.\n"
                "• The creature is incapacitated, can't move or speak, and is unaware of its surroundings.\n"
                "• Attack rolls against the creature have advantage.\n"
                "• The creature automatically fails Strength and Dexterity saving throws.\n"
                "• The creature has resistance to all damage.\n"
                "• The creature is immune to poison and disease, although poisons and diseases already in its system are suspended, not neutralized."
            ),
            ConditionType.POISONED: (
                "• A poisoned creature has disadvantage on attack rolls and ability checks."
            ),
            ConditionType.PRONE: (
                "• A prone creature's only movement option is to crawl, unless it stands up.\n"
                "• The creature has disadvantage on attack rolls.\n"
                "• An attack roll against the creature has advantage if the attacker is within 5 feet. Otherwise, the attack roll has disadvantage."
            ),
            ConditionType.RESTRAINED: (
                "• A restrained creature's speed becomes 0, and it can't benefit from any bonus to its speed.\n"
                "• Attack rolls against the creature have advantage, and the creature's attack rolls have disadvantage.\n"
                "• The creature has disadvantage on Dexterity saving throws."
            ),
            ConditionType.STUNNED: (
                "• A stunned creature is incapacitated, can't move, and can speak only falteringly.\n"
                "• The creature automatically fails Strength and Dexterity saving throws.\n"
                "• Attack rolls against the creature have advantage."
            ),
            ConditionType.UNCONSCIOUS: (
                "• An unconscious creature is incapacitated, can't move or speak, and is unaware of its surroundings.\n"
                "• The creature drops whatever it's holding and falls prone.\n"
                "• The creature automatically fails Strength and Dexterity saving throws.\n"
                "• Attack rolls against the creature have advantage.\n"
                "• Any attack that hits the creature is a critical hit if the attacker is within 5 feet."
            ),
            ConditionType.CONCENTRATION: (
                "• The creature is concentrating on a spell.\n"
                "• Concentration can be broken if the creature takes damage, fails a Constitution saving throw, casts another concentration spell, or becomes incapacitated or killed.\n"
                "• When taking damage, the DC equals 10 or half the damage taken, whichever is higher."
            ),
        }
        
        condition_name = self.condition_type.name.replace("_", " ").title()
        description = condition_descriptions.get(self.condition_type, "No description available.")
        
        return f"{condition_name}\n\n{description}"
    
    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle mouse press events to emit clicked signal."""
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.condition_type)
        super().mousePressEvent(event)


class ExhaustionIcon(ConditionIcon):
    """Special condition icon for exhaustion that shows the level."""
    
    def __init__(self, level: int = 1, parent=None):
        super().__init__(ConditionType.EXHAUSTION, parent)
        self.level = level
        self._update_appearance()
    
    def _update_appearance(self):
        """Update the appearance to reflect the exhaustion level."""
        # Set text to show level
        self.setText(f"E{self.level}")
        
        # Set background color based on level severity
        colors = [
            QColor(255, 255, 200),  # Level 1: Light yellow
            QColor(255, 200, 150),  # Level 2: Light orange
            QColor(255, 150, 150),  # Level 3: Light red
            QColor(255, 100, 100),  # Level 4: Medium red
            QColor(255, 50, 50),    # Level 5: Bright red
            QColor(200, 0, 0)       # Level 6: Dark red
        ]
        
        level_idx = min(self.level - 1, 5)  # Clamp to 0-5 index
        color = colors[level_idx]
        
        # Create and set stylesheet for background color
        self.setStyleSheet(f"""
            QLabel {{
                background-color: rgba({color.red()}, {color.green()}, {color.blue()}, 180);
                border-radius: 3px;
                font-weight: bold;
                padding: 1px;
            }}
        """)
    
    def set_level(self, level: int):
        """Update the exhaustion level."""
        self.level = max(1, min(level, 6))  # Clamp between 1-6
        self._update_appearance()


class ConditionDisplay(QWidget):
    """Widget for displaying all conditions affecting a combatant."""
    
    condition_clicked = Signal(ConditionType)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.conditions = {}  # Map of ConditionType to ConditionIcon
        self.exhaustion_level = 0
        
        # Set up the layout
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(2)
        self.setLayout(self.layout)
    
    def update_conditions(self, conditions_dict: dict):
        """
        Update the displayed conditions based on a conditions dictionary.
        
        Args:
            conditions_dict: Dictionary of conditions from a combatant
        """
        # Clear current conditions
        self.clear_conditions()
        
        # Skip if no conditions or invalid format
        if not conditions_dict or not isinstance(conditions_dict, dict):
            return
        
        # Special handling for exhaustion
        exhaustion_data = conditions_dict.get(ConditionType.EXHAUSTION.name.lower(), None)
        if exhaustion_data and isinstance(exhaustion_data, dict):
            level = exhaustion_data.get("level", 1)
            self.add_exhaustion(level)
        
        # Add all other conditions
        for condition_name, condition_data in conditions_dict.items():
            # Skip exhaustion as it's already handled
            if condition_name.lower() == ConditionType.EXHAUSTION.name.lower():
                continue
                
            # Parse condition type from name
            try:
                condition_type = ConditionType[condition_name.upper()]
                self.add_condition(condition_type)
            except (KeyError, ValueError):
                # Unknown condition, skip it
                continue
    
    def add_condition(self, condition_type: ConditionType):
        """
        Add a condition icon to the display.
        
        Args:
            condition_type: The type of condition to add
        """
        # Skip if already present (except for special cases)
        if condition_type in self.conditions:
            return
            
        # Handle exhaustion specially
        if condition_type == ConditionType.EXHAUSTION:
            self.add_exhaustion(1)
            return
            
        # Create and add the condition icon
        icon = ConditionIcon(condition_type, self)
        icon.clicked.connect(self.condition_clicked)
        self.layout.addWidget(icon)
        self.conditions[condition_type] = icon
    
    def add_exhaustion(self, level: int):
        """
        Add or update exhaustion with the specified level.
        
        Args:
            level: The level of exhaustion (1-6)
        """
        if ConditionType.EXHAUSTION in self.conditions:
            # Update existing exhaustion icon
            icon = self.conditions[ConditionType.EXHAUSTION]
            if isinstance(icon, ExhaustionIcon):
                icon.set_level(level)
        else:
            # Create new exhaustion icon
            icon = ExhaustionIcon(level, self)
            icon.clicked.connect(self.condition_clicked)
            self.layout.addWidget(icon)
            self.conditions[ConditionType.EXHAUSTION] = icon
            
        self.exhaustion_level = level
    
    def remove_condition(self, condition_type: ConditionType):
        """
        Remove a condition from the display.
        
        Args:
            condition_type: The type of condition to remove
        """
        if condition_type in self.conditions:
            icon = self.conditions[condition_type]
            self.layout.removeWidget(icon)
            icon.deleteLater()
            del self.conditions[condition_type]
            
            if condition_type == ConditionType.EXHAUSTION:
                self.exhaustion_level = 0
    
    def clear_conditions(self):
        """Remove all condition icons from the display."""
        for icon in self.conditions.values():
            self.layout.removeWidget(icon)
            icon.deleteLater()
        
        self.conditions = {}
        self.exhaustion_level = 0


class CombatantConditionBar(QFrame):
    """
    A bar showing condition icons for a combatant in the combat tracker.
    Includes hover effects and click handling.
    """
    
    condition_clicked = Signal(str, ConditionType)  # (combatant_id, condition_type)
    
    def __init__(self, combatant_id: str, parent=None):
        super().__init__(parent)
        self.combatant_id = combatant_id
        self.setFrameShape(QFrame.StyledPanel)
        self.setFrameShadow(QFrame.Sunken)
        
        # Set up the layout
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(3, 0, 3, 0)
        self.layout.setSpacing(2)
        
        # Create the condition display
        self.condition_display = ConditionDisplay(self)
        self.condition_display.condition_clicked.connect(self._on_condition_clicked)
        
        self.layout.addWidget(self.condition_display)
        self.setLayout(self.layout)
        
        # Style the widget
        self.setStyleSheet("""
            CombatantConditionBar {
                background-color: rgba(50, 50, 50, 30);
                border-radius: 3px;
                min-height: 28px;
                max-height: 28px;
            }
            
            CombatantConditionBar:hover {
                background-color: rgba(50, 50, 50, 60);
            }
        """)
    
    def _on_condition_clicked(self, condition_type: ConditionType):
        """Handle condition icon click by emitting signal with combatant ID."""
        self.condition_clicked.emit(self.combatant_id, condition_type)
    
    def update_conditions(self, conditions_dict: dict):
        """Update the condition display with combatant's conditions."""
        self.condition_display.update_conditions(conditions_dict)
        
        # Show/hide the bar based on whether conditions exist
        self.setVisible(len(self.condition_display.conditions) > 0)
    
    def has_conditions(self) -> bool:
        """Check if the combatant has any conditions."""
        return len(self.condition_display.conditions) > 0 