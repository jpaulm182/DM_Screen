# app/ui/panels/panel_category.py - Panel categories and styling
"""
Panel categories and styling for the DM Screen application

Defines the categories, colors, and styles for panel organization.
"""

from PySide6.QtGui import QColor

# Panel category definitions
class PanelCategory:
    """Panel category definitions and styling"""
    
    # Category types
    COMBAT = "combat"
    REFERENCE = "reference"
    UTILITY = "utility"
    CAMPAIGN = "campaign"
    
    # Panel to category mapping
    PANEL_CATEGORIES = {
        "combat_tracker": COMBAT,
        "dice_roller": COMBAT,
        "combat_log": COMBAT,
        "conditions": REFERENCE,
        "rules_reference": REFERENCE,
        "monster": REFERENCE,
        "spell_reference": REFERENCE,
        "llm": REFERENCE,
        "rules_clarification": REFERENCE,
        "session_notes": CAMPAIGN,
        "player_character": CAMPAIGN,
        "npc_generator": CAMPAIGN,
        "location_generator": CAMPAIGN,
        "treasure_generator": CAMPAIGN,
        "encounter_generator": CAMPAIGN,
        "weather": UTILITY,
        "time_tracker": UTILITY
    }
    
    # Category colors (in dark and light themes)
    CATEGORY_COLORS = {
        COMBAT: {
            "dark": {
                "title_bg": QColor(170, 0, 0, 180),
                "title_text": QColor(255, 255, 255),
                "border": QColor(120, 0, 0)
            },
            "light": {
                "title_bg": QColor(230, 115, 115),
                "title_text": QColor(50, 0, 0),
                "border": QColor(200, 80, 80)
            }
        },
        REFERENCE: {
            "dark": {
                "title_bg": QColor(0, 0, 170, 180),
                "title_text": QColor(255, 255, 255),
                "border": QColor(0, 0, 120)
            },
            "light": {
                "title_bg": QColor(115, 115, 230),
                "title_text": QColor(0, 0, 50),
                "border": QColor(80, 80, 200)
            }
        },
        UTILITY: {
            "dark": {
                "title_bg": QColor(0, 100, 0, 180),
                "title_text": QColor(255, 255, 255),
                "border": QColor(0, 80, 0)
            },
            "light": {
                "title_bg": QColor(115, 230, 115),
                "title_text": QColor(0, 50, 0),
                "border": QColor(80, 200, 80)
            }
        },
        CAMPAIGN: {
            "dark": {
                "title_bg": QColor(120, 60, 0, 180),
                "title_text": QColor(255, 255, 255),
                "border": QColor(100, 50, 0)
            },
            "light": {
                "title_bg": QColor(230, 190, 115),
                "title_text": QColor(50, 25, 0),
                "border": QColor(200, 150, 80)
            }
        }
    }
    
    @classmethod
    def get_category(cls, panel_id):
        """Get the category for a panel"""
        return cls.PANEL_CATEGORIES.get(panel_id, cls.UTILITY)
    
    @classmethod
    def get_colors(cls, panel_id, theme="dark"):
        """Get the colors for a panel based on its category and theme"""
        category = cls.get_category(panel_id)
        return cls.CATEGORY_COLORS.get(category, {}).get(theme, {})
    
    @classmethod
    def get_category_display_name(cls, category):
        """Get a display name for a category"""
        return {
            cls.COMBAT: "Combat Tools",
            cls.REFERENCE: "Reference Materials",
            cls.UTILITY: "Utility Tools",
            cls.CAMPAIGN: "Campaign Management"
        }.get(category, "General") 