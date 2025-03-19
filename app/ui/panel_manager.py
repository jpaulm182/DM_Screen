# app/ui/panel_manager.py - Panel management system
"""
Panel management system for the DM Screen application

Handles creating, organizing, and managing dockable panels.
"""

from PySide6.QtWidgets import QDockWidget, QMessageBox, QLabel, QWidget
from PySide6.QtCore import Qt, QObject
from PySide6.QtGui import QPalette, QColor

# Import all panel types
from app.ui.panels.combat_tracker_panel import CombatTrackerPanel
from app.ui.panels.dice_roller_panel import DiceRollerPanel
from app.ui.panels.welcome_panel import WelcomePanel
from app.ui.panels.conditions_panel import ConditionsPanel
from app.ui.panels.rules_reference_panel import RulesReferencePanel
from app.ui.panels.monster_panel import MonsterPanel
from app.ui.panels.spell_reference_panel import SpellReferencePanel
# from app.ui.panels.minimal_spell_panel import MinimalSpellPanel
from app.ui.panels.session_notes_panel import SessionNotesPanel
from app.ui.panels.weather_panel import WeatherPanel
from app.ui.panels.time_tracker_panel import TimeTrackerPanel
from app.ui.panels.panel_category import PanelCategory
from app.ui.panels.player_character_panel import PlayerCharacterPanel
from app.ui.panels.llm_panel import LLMPanel  # Import the new LLM panel
from app.ui.panels.npc_generator_panel import NPCGeneratorPanel  # Import the NPC Generator panel
from app.ui.panels.rules_clarification_panel import RulesClarificationPanel  # Import the Rules Clarification panel


class PanelManager(QObject):
    """
    Manages the creation and organization of dockable panels
    """
    
    def __init__(self, main_window, app_state):
        """Initialize the panel manager"""
        super().__init__()
        self.main_window = main_window
        self.app_state = app_state
        self.panels = {}  # Dictionary of active panels
        self.panel_categories = {}  # Group panels by category
        self.current_theme = app_state.get_setting("theme", "dark")
        
        # Initialize panels
        self._init_panels()
        
        # Connect panel signals
        self._connect_panel_signals()
    
    def _init_panels(self):
        """Initialize all available panels"""
        # Create panels but don't show them all by default
        self.panels["combat_tracker"] = self._create_panel(CombatTrackerPanel, "combat_tracker")
        self.panels["dice_roller"] = self._create_panel(DiceRollerPanel, "dice_roller")
        self.panels["conditions"] = self._create_panel(ConditionsPanel, "conditions")
        self.panels["rules_reference"] = self._create_panel(RulesReferencePanel, "rules_reference")
        self.panels["monster"] = self._create_panel(MonsterPanel, "monster")
        self.panels["spell_reference"] = self._create_panel(SpellReferencePanel, "spell_reference")
        self.panels["session_notes"] = self._create_panel(SessionNotesPanel, "session_notes")
        self.panels["player_character"] = self._create_panel(PlayerCharacterPanel, "player_character")
        self.panels["weather"] = self._create_panel(WeatherPanel, "weather")
        self.panels["time_tracker"] = self._create_panel(TimeTrackerPanel, "time_tracker")
        self.panels["llm"] = self._create_panel(LLMPanel, "llm")  # Add the LLM panel
        self.panels["npc_generator"] = self._create_panel(NPCGeneratorPanel, "npc_generator")  # Add the NPC Generator panel
        self.panels["rules_clarification"] = self._create_panel(RulesClarificationPanel, "rules_clarification")  # Add the Rules Clarification panel
        
        # Organize panels by category
        self._organize_panels_by_category()
        
        # Show specific panels by default
        if "combat_tracker" in self.panels and self.panels["combat_tracker"]:
            self.panels["combat_tracker"].show()
        
        if "dice_roller" in self.panels and self.panels["dice_roller"]:
            self.panels["dice_roller"].show()
        
        # If both combat tracker and dice roller are shown, split them horizontally
        if "combat_tracker" in self.panels and self.panels["combat_tracker"]:
            self.main_window.splitDockWidget(
                self.panels["combat_tracker"],
                self.panels["dice_roller"],
                Qt.Horizontal
            )
        
        # Show session notes (in a different dock area)
        if "session_notes" in self.panels and self.panels["session_notes"]:
            self.panels["session_notes"].show()
        
        # Split session notes vertically with combat panels
        if "combat_tracker" in self.panels and self.panels["combat_tracker"]:
            self.main_window.splitDockWidget(
                self.panels["combat_tracker"],
                self.panels["session_notes"],
                Qt.Vertical
            )
        
        # Raise the combat tracker initially
        if "combat_tracker" in self.panels and self.panels["combat_tracker"]:
            self.panels["combat_tracker"].raise_()
    
    def _organize_panels_by_category(self):
        """Organize panels into logical groups by category"""
        # Group panels by category
        for panel_id, dock in self.panels.items():
            if not dock:
                continue
                
            category = PanelCategory.get_category(panel_id)
            
            if category not in self.panel_categories:
                self.panel_categories[category] = []
                
            self.panel_categories[category].append(panel_id)
        
        # Place panels in appropriate dock areas based on category
        for panel_id, dock in self.panels.items():
            if not dock:
                continue
                
            category = PanelCategory.get_category(panel_id)
            
            # Set dock area based on category
            if category == PanelCategory.COMBAT:
                self.main_window.addDockWidget(Qt.LeftDockWidgetArea, dock)
            elif category == PanelCategory.REFERENCE:
                self.main_window.addDockWidget(Qt.RightDockWidgetArea, dock)
            elif category == PanelCategory.CAMPAIGN:
                self.main_window.addDockWidget(Qt.TopDockWidgetArea, dock)
            else:  # UTILITY
                self.main_window.addDockWidget(Qt.BottomDockWidgetArea, dock)
        
        # Stack related panels in the same category, but don't tabify all of them
        self._stack_similar_panels()
    
    def _stack_similar_panels(self):
        """Stack some related panels while allowing others to be side by side"""
        # For each category, we'll organize based on panel function
        
        # Reference category: tabify conditions, monster, and spell reference panels
        reference_tabs = ["conditions", "monster", "spell_reference"]
        self._tabify_specific_panels(reference_tabs)
        
        # Utility category: tabify weather and time tracker panels
        utility_tabs = ["weather", "time_tracker"]
        self._tabify_specific_panels(utility_tabs)
        
        # Combat category: allow combat_tracker and dice_roller to be separate
        # We don't tabify these as they're frequently used together
    
    def _tabify_specific_panels(self, panel_ids):
        """Tabify a specific set of panels if they exist"""
        first_panel = None
        
        # Find the first available panel to use as reference
        for panel_id in panel_ids:
            if panel_id in self.panels and self.panels[panel_id]:
                first_panel = self.panels[panel_id]
                break
        
        if not first_panel:
            return
        
        # Tabify the remaining panels with the first one
        for panel_id in panel_ids:
            if (panel_id in self.panels and self.panels[panel_id] and 
                self.panels[panel_id] != first_panel):
                self.main_window.tabifyDockWidget(first_panel, self.panels[panel_id])
    
    def _create_panel(self, panel_class, panel_id):
        """Create a new panel instance wrapped in a QDockWidget"""
        try:
            # Create panel instance
            panel = panel_class(self.app_state)
            
            # Create dock widget
            dock = QDockWidget(panel.title, self.main_window)
            dock.setWidget(panel)
            dock.setObjectName(panel_class.__name__)
            dock.setFeatures(
                QDockWidget.DockWidgetClosable |
                QDockWidget.DockWidgetMovable |
                QDockWidget.DockWidgetFloatable
            )
            
            # Apply category styling
            self._apply_panel_styling(dock, panel_id)
            
            # Hide by default to avoid overlap
            dock.hide()
            
            return dock
            
        except Exception as e:
            QMessageBox.critical(
                self.main_window,
                "Panel Creation Error",
                f"Failed to create {panel_class.__name__}: {str(e)}"
            )
            return None
    
    def _apply_panel_styling(self, dock, panel_id):
        """Apply color coding and styling to the panel based on its category"""
        # Get colors for this panel's category
        colors = PanelCategory.get_colors(panel_id, self.current_theme)
        category = PanelCategory.get_category(panel_id)
        
        if colors:
            # Apply title bar styling
            title_style = f"""
                QDockWidget::title {{
                    background-color: {colors['title_bg'].name()};
                    color: {colors['title_text'].name()};
                    font-weight: bold;
                    padding-left: 5px;
                }}
                QDockWidget {{
                    border: 1px solid {colors['border'].name()};
                }}
            """
            dock.setStyleSheet(title_style)
            
            # Add category prefix to title
            category_name = PanelCategory.get_category_display_name(category)
            dock.setWindowTitle(f"[{category_name}] {dock.windowTitle()}")
    
    def _connect_panel_signals(self):
        """Connect signals between panels"""
        try:
            # Connect monster panel to combat tracker
            monster_panel = self.panels["monster"].widget()
            combat_tracker = self.panels["combat_tracker"].widget()
            
            if monster_panel and combat_tracker:
                if hasattr(monster_panel, "add_to_combat"):
                    monster_panel.add_to_combat.connect(combat_tracker.add_monster)
            
            # Connect conditions panel to combat tracker
            conditions_panel = self.panels["conditions"].widget()
            if conditions_panel and hasattr(conditions_panel, "apply_condition"):
                conditions_panel.apply_condition.connect(combat_tracker.apply_condition)
            
            # Connect player character panel to combat tracker
            player_character_panel = self.panels["player_character"].widget()
            if player_character_panel and hasattr(player_character_panel, "add_to_combat"):
                player_character_panel.add_to_combat.connect(combat_tracker.add_character)
            
            # Connect NPC Generator to LLM panel for context sharing (if implemented)
            npc_generator = self.panels["npc_generator"].widget()
            llm_panel = self.panels["llm"].widget()
            
            # Connect NPC Generator to Player Character Panel
            if npc_generator and player_character_panel and hasattr(npc_generator, "npc_generated"):
                npc_generator.npc_generated.connect(player_character_panel.add_npc_character)
            
            # Weather panel and time tracker panel (future integration)
            weather_panel = self.panels["weather"].widget()
            time_tracker = self.panels["time_tracker"].widget()
            
            # This connection would be implemented when the signal/slot is ready
            # if weather_panel and time_tracker:
            #     if hasattr(time_tracker, "update_weather") and hasattr(weather_panel, "generate_weather"):
            #         time_tracker.update_weather.connect(weather_panel.generate_weather)
            
        except Exception as e:
            QMessageBox.warning(
                self.main_window,
                "Signal Connection Error",
                f"Failed to connect panel signals: {str(e)}"
            )
    
    def create_panel(self, panel_type):
        """Create a panel of the specified type
        
        Args:
            panel_type (str): Type of panel to create
            
        Returns:
            QDockWidget: Created panel, or None if type is invalid
        """
        # Map panel_type to panel class
        panel_class_map = {
            "combat_tracker": CombatTrackerPanel,
            "dice_roller": DiceRollerPanel,
            "monster": MonsterPanel,
            "conditions": ConditionsPanel,
            "rules_reference": RulesReferencePanel,
            "spell_reference": SpellReferencePanel,
            "session_notes": SessionNotesPanel,
            "player_character": PlayerCharacterPanel,
            "weather": WeatherPanel,
            "time_tracker": TimeTrackerPanel,
            "llm": LLMPanel,  # Add LLM panel to the map
            "npc_generator": NPCGeneratorPanel,  # Add NPC Generator panel to the map
        }
        
        if panel_type in self.panels and self.panels[panel_type]:
            # Panel already exists, toggle visibility
            if self.panels[panel_type].isVisible():
                self.panels[panel_type].hide()
            else:
                self.panels[panel_type].show()
                self.panels[panel_type].raise_()
            return self.panels[panel_type]
        
        # Create new panel based on type
        if panel_type in panel_class_map:
            self.panels[panel_type] = self._create_panel(panel_class_map[panel_type], panel_type)
        else:
            QMessageBox.warning(
                self.main_window,
                "Invalid Panel Type",
                f"Panel type '{panel_type}' is not supported."
            )
            return None
        
        # Show the new panel
        if self.panels[panel_type]:
            self.panels[panel_type].show()
            self.panels[panel_type].raise_()
            
            # Try to place the panel in a sensible location based on category
            self._tabify_panel_with_category(panel_type, self.panels[panel_type].content.PANEL_CATEGORY)
        
        return self.panels[panel_type]
    
    def _tabify_panel_with_category(self, panel_type, category):
        """Tabify a panel with others in its category if appropriate"""
        # For combat panels, we don't automatically tabify
        if category == PanelCategory.COMBAT:
            return
        
        # For reference panels, tabify with existing reference panels if visible
        reference_tabs = ["conditions", "monster", "spell_reference"]
        if category == PanelCategory.REFERENCE and panel_type in reference_tabs:
            for other_id in reference_tabs:
                if (other_id != panel_type and other_id in self.panels and 
                    self.panels[other_id].isVisible()):
                    self.main_window.tabifyDockWidget(
                        self.panels[other_id],
                        self.panels[panel_type]
                    )
                    return
                
        # For utility panels, tabify with existing utility panels if visible
        utility_tabs = ["weather", "time_tracker"]
        if category == PanelCategory.UTILITY and panel_type in utility_tabs:
            for other_id in utility_tabs:
                if (other_id != panel_type and other_id in self.panels and 
                    self.panels[other_id].isVisible()):
                    self.main_window.tabifyDockWidget(
                        self.panels[other_id],
                        self.panels[panel_type]
                    )
                    return
    
    def update_theme(self, theme):
        """Update the theme for all panels"""
        self.current_theme = theme
        for panel_id, dock in self.panels.items():
            if dock:
                self._apply_panel_styling(dock, panel_id)
    
    def close_all_panels(self):
        """Close all panels"""
        for dock in self.panels.values():
            if dock:
                dock.hide()
    
    def save_state(self):
        """Save the state of all panels"""
        state = {}
        for name, dock in self.panels.items():
            if dock and dock.widget():
                panel = dock.widget()
                if hasattr(panel, "save_state"):
                    state[name] = panel.save_state()
        return state
    
    def restore_state(self, state):
        """Restore the state of all panels"""
        if not state:
            return
            
        for name, panel_state in state.items():
            if name in self.panels and self.panels[name]:
                panel = self.panels[name].widget()
                if panel and hasattr(panel, "restore_state"):
                    panel.restore_state(panel_state)
    
    def get_panel(self, name):
        """
        Get a panel by name
        
        Args:
            name: Panel ID or name
            
        Returns:
            The panel dock widget or None if not found
        """
        print(f"PanelManager.get_panel called for: {name}")
        print(f"Available panels: {list(self.panels.keys())}")
        
        # Standardize panel name
        name = name.lower().strip()
        
        # Look for exact match first
        panel = self.panels.get(name)
        
        # If not found, try case-insensitive match
        if not panel:
            for panel_id, dock in self.panels.items():
                if panel_id.lower() == name:
                    panel = dock
                    break
        
        print(f"Panel {name} found: {panel is not None}")
        return panel

    def toggle_panel(self, panel_type):
        """Toggle a panel on or off"""
        if panel_type in self.panels and self.panels[panel_type]:
            if self.panels[panel_type].isVisible():
                self.panels[panel_type].hide()
                return False  # Panel is now hidden
            else:
                self.panels[panel_type].show()
                self.panels[panel_type].raise_()
                return True  # Panel is now visible
        else:
            # Panel doesn't exist yet, create it
            self.create_panel(panel_type)
            return True  # Panel was created and should be visible
    
    def show_panel(self, panel_type):
        """Show a panel, creating it if it doesn't exist"""
        if panel_type in self.panels and self.panels[panel_type]:
            self.panels[panel_type].show()
            self.panels[panel_type].raise_()
            return True
        else:
            # Panel doesn't exist yet, create it
            return self.create_panel(panel_type)

    def smart_organize_panels(self):
        """Smart organization of panels to maximize usable space"""
        # Step 1: Temporary hide all panels to reorganize them
        visible_panels = {}
        for panel_id, dock in self.panels.items():
            if dock and dock.isVisible():
                visible_panels[panel_id] = True
                dock.hide()
        
        # Step 2: Determine screen quadrants - account for toolbar and status bar
        main_window_geometry = self.main_window.geometry()
        effective_height = main_window_geometry.height() - 50  # Account for toolbar/statusbar
        effective_width = main_window_geometry.width() 
        center_x = effective_width // 2
        center_y = effective_height // 2
        
        # Force reset dock widget locations to avoid stacking issues
        for panel_id in self.panels:
            if self.panels[panel_id]:
                self.panels[panel_id].setFloating(False)
        
        # Step 3: Organize by category in specific quadrants
        # - Combat: Top Left
        # - Reference: Top Right 
        # - Campaign: Bottom Left
        # - Utility: Bottom Right
        
        # Organize combat panels - allow combat_tracker and dice_roller to be side by side
        combat_panels = [p for p in self.panel_categories.get(PanelCategory.COMBAT, []) 
                         if p in visible_panels]
        if combat_panels:
            # Add all combat panels to the top-left area
            for i, panel_id in enumerate(combat_panels):
                self.main_window.addDockWidget(Qt.TopDockWidgetArea, self.panels[panel_id])
                self.panels[panel_id].show()
                
            # If we have more than one combat panel, split them horizontally
            if len(combat_panels) > 1:
                for i in range(1, len(combat_panels)):
                    self.main_window.splitDockWidget(
                        self.panels[combat_panels[0]],
                        self.panels[combat_panels[i]],
                        Qt.Horizontal
                    )
        
        # Organize reference panels
        reference_panels = [p for p in self.panel_categories.get(PanelCategory.REFERENCE, []) 
                           if p in visible_panels]
        if reference_panels:
            # Add first panel
            first_panel = reference_panels[0]
            self.main_window.addDockWidget(Qt.TopDockWidgetArea, self.panels[first_panel])
            self.panels[first_panel].show()
            
            # Group reference panels that should be tabified
            reference_tabs = ["conditions", "monster", "spell_reference"]
            tab_group = [p for p in reference_panels if p in reference_tabs]
            non_tab_group = [p for p in reference_panels if p not in reference_tabs]
            
            # Tabify panels in the tab group
            if len(tab_group) > 1:
                for i in range(1, len(tab_group)):
                    self.main_window.tabifyDockWidget(
                        self.panels[tab_group[0]],
                        self.panels[tab_group[i]]
                    )
                    self.panels[tab_group[i]].show()
                
            # Add other reference panels side by side
            if non_tab_group:
                for panel_id in non_tab_group:
                    if panel_id != first_panel:  # Skip the first panel we already added
                        self.main_window.splitDockWidget(
                            self.panels[first_panel],
                            self.panels[panel_id],
                            Qt.Vertical
                        )
                        self.panels[panel_id].show()
            
            # Split combat and reference horizontally if both exist
            if combat_panels:
                self.main_window.splitDockWidget(
                    self.panels[combat_panels[0]],
                    self.panels[reference_panels[0]],
                    Qt.Horizontal
                )
        
        # Organize campaign panels
        campaign_panels = [p for p in self.panel_categories.get(PanelCategory.CAMPAIGN, []) 
                          if p in visible_panels]
        if campaign_panels:
            # Add first panel
            first_panel = campaign_panels[0]
            self.main_window.addDockWidget(Qt.BottomDockWidgetArea, self.panels[first_panel])
            self.panels[first_panel].show()
            
            # Tabify remaining campaign panels
            for i in range(1, len(campaign_panels)):
                panel_id = campaign_panels[i]
                self.main_window.tabifyDockWidget(
                    self.panels[first_panel],
                    self.panels[panel_id]
                )
                self.panels[panel_id].show()
            
            # Split vertically with top panels if they exist
            if combat_panels:
                self.main_window.splitDockWidget(
                    self.panels[combat_panels[0]],
                    self.panels[campaign_panels[0]],
                    Qt.Vertical
                )
        
        # Organize utility panels
        utility_panels = [p for p in self.panel_categories.get(PanelCategory.UTILITY, []) 
                         if p in visible_panels]
        if utility_panels:
            # Add first panel
            first_panel = utility_panels[0]
            self.main_window.addDockWidget(Qt.BottomDockWidgetArea, self.panels[first_panel])
            self.panels[first_panel].show()
            
            # Group utility panels that should be tabified
            utility_tabs = ["weather", "time_tracker"]
            tab_group = [p for p in utility_panels if p in utility_tabs]
            non_tab_group = [p for p in utility_panels if p not in utility_tabs]
            
            # Tabify panels in the tab group
            if len(tab_group) > 1:
                for i in range(1, len(tab_group)):
                    self.main_window.tabifyDockWidget(
                        self.panels[tab_group[0]],
                        self.panels[tab_group[i]]
                    )
                    self.panels[tab_group[i]].show()
            
            # Add other utility panels side by side
            if non_tab_group:
                for panel_id in non_tab_group:
                    if panel_id != first_panel:  # Skip the first panel we already added
                        self.main_window.splitDockWidget(
                            self.panels[first_panel],
                            self.panels[panel_id],
                            Qt.Vertical
                        )
                        self.panels[panel_id].show()
            
            # Split horizontally with campaign panels if they exist,
            # otherwise split vertically with reference panels
            if campaign_panels:
                self.main_window.splitDockWidget(
                    self.panels[campaign_panels[0]],
                    self.panels[utility_panels[0]],
                    Qt.Horizontal
                )
            elif reference_panels:
                self.main_window.splitDockWidget(
                    self.panels[reference_panels[0]],
                    self.panels[utility_panels[0]],
                    Qt.Vertical
                )
        
        # Step 4: Raise the appropriate panels in each area to make them visible
        for category, panel_ids in self.panel_categories.items():
            for panel_id in panel_ids:
                if panel_id in visible_panels:
                    self.panels[panel_id].raise_()
                    break
                
        # Return success message
        return "Panels have been intelligently organized for optimal use of screen space."

    def is_panel_visible(self, panel_type):
        """Check if a panel is currently visible"""
        if panel_type in self.panels and self.panels[panel_type]:
            return self.panels[panel_type].isVisible()
        return False