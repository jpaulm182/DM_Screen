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
from app.ui.panels.location_generator_panel import LocationGeneratorPanel  # Import the Location Generator panel
from app.ui.panels.treasure_generator_panel import TreasureGeneratorPanel # Import Treasure Generator
from app.ui.panels.encounter_generator_panel import EncounterGeneratorPanel # Import Encounter Generator
from app.ui.panels.combat_log_panel import CombatLogPanel


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
        self.panels["location_generator"] = self._create_panel(LocationGeneratorPanel, "location_generator")  # Add the Location Generator panel
        self.panels["treasure_generator"] = self._create_panel(TreasureGeneratorPanel, "treasure_generator") # Initialize Treasure Generator
        self.panels["encounter_generator"] = self._create_panel(EncounterGeneratorPanel, "encounter_generator") # Initialize Encounter Generator
        self.panels["combat_log"] = self._create_panel(CombatLogPanel, "combat_log")
        
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
        
        # Get border intensity from settings (1-5)
        border_intensity = self.app_state.get_panel_layout_setting("panel_border_intensity", 3)
        
        # Set border width based on intensity
        border_width = border_intensity
        
        if colors:
            # Apply title bar styling with more prominent borders
            title_style = f"""
                QDockWidget::title {{
                    background-color: {colors['title_bg'].name()};
                    color: {colors['title_text'].name()};
                    font-weight: bold;
                    padding-left: 5px;
                    font-size: 13px;
                }}
                QDockWidget {{
                    border: {border_width}px solid {colors['border'].name()};
                    border-radius: 2px;
                }}
                QDockWidget > QWidget {{
                    border: 1px solid {colors['border'].name()};
                    background-color: {self._get_content_bg_color(colors, category).name()};
                }}
            """
            dock.setStyleSheet(title_style)
            
            # Add category prefix to title
            category_name = PanelCategory.get_category_display_name(category)
            dock.setWindowTitle(f"[{category_name}] {dock.windowTitle()}")
    
    def _get_content_bg_color(self, colors, category):
        """Get a subtle background color for panel content based on category"""
        # Create a very light tint of the category color for the panel background
        bg_color = colors['title_bg']
        if self.current_theme == "dark":
            # For dark theme, create a darker, more subtle version
            return QColor(
                min(bg_color.red() + 10, 255), 
                min(bg_color.green() + 10, 255),
                min(bg_color.blue() + 10, 255),
                40  # Very transparent
            )
        else:
            # For light theme, create a very light tint
            return QColor(
                min(bg_color.red() + 230, 255),
                min(bg_color.green() + 230, 255),
                min(bg_color.blue() + 230, 255),
                70  # Slightly transparent
            )
    
    def _connect_panel_signals(self):
        """Connect signals between panels for inter-panel communication"""
        print("[PanelManager] Attempting to connect panel signals...")
        
        try:
            # Connect monster panel to combat tracker
            monster_panel = self.panels["monster"].widget()
            combat_tracker = self.panels["combat_tracker"].widget()
            
            if monster_panel and combat_tracker:
                print(f"[PanelManager] Found both monster_panel ({type(monster_panel).__name__}) and combat_tracker ({type(combat_tracker).__name__})")
                
                if hasattr(monster_panel, "add_to_combat"):
                    print("[PanelManager] monster_panel has add_to_combat signal")
                    
                    if hasattr(combat_tracker, "add_monster"):
                        print("[PanelManager] combat_tracker has add_monster method")
                        monster_panel.add_to_combat.connect(combat_tracker.add_monster)
                        print("[PanelManager] CONNECTED: monster_panel.add_to_combat -> combat_tracker.add_monster")
                    else:
                        print("[PanelManager] ERROR: combat_tracker does not have add_monster method!")
                else:
                    print("[PanelManager] ERROR: monster_panel does not have add_to_combat signal!")
            else:
                missing = []
                if not monster_panel:
                    missing.append("monster_panel")
                if not combat_tracker:
                    missing.append("combat_tracker")
                print(f"[PanelManager] ERROR: Missing panels: {', '.join(missing)}")
            
            # Connect conditions panel to combat tracker
            conditions_panel = self.panels["conditions"].widget()
            if conditions_panel and hasattr(conditions_panel, "apply_condition"):
                conditions_panel.apply_condition.connect(combat_tracker.apply_condition)
                print("[PanelManager] Connected conditions_panel.apply_condition to combat_tracker.apply_condition")
            
            # Connect player character panel to combat tracker
            player_character_panel = self.panels["player_character"].widget()
            if player_character_panel and hasattr(player_character_panel, "add_to_combat"):
                player_character_panel.add_to_combat.connect(combat_tracker.add_character)
                print("[PanelManager] Connected player_character_panel.add_to_combat to combat_tracker.add_character")
            
            # Connect Encounter Generator to Combat Tracker
            encounter_panel_dock = self.panels.get("encounter_generator")
            if encounter_panel_dock and combat_tracker:
                encounter_panel = encounter_panel_dock.widget()
                if hasattr(encounter_panel, 'add_group_to_combat') and hasattr(combat_tracker, 'add_combatant_group'):
                    encounter_panel.add_group_to_combat.connect(combat_tracker.add_combatant_group)
                    print("Connected EncounterGeneratorPanel.add_group_to_combat to CombatTrackerPanel.add_combatant_group") # Debug log
            
            # Connect custom monster creation from Encounter Generator to Monster Panel
            if encounter_panel_dock and monster_panel:
                encounter_panel = encounter_panel_dock.widget()
                if hasattr(encounter_panel, 'add_group_to_combat') and hasattr(monster_panel, '_load_initial_monsters'):
                    # When monsters are added to combat from encounter generator, refresh the monster panel list
                    encounter_panel.add_group_to_combat.connect(lambda _: monster_panel._load_initial_monsters())
                    print("Connected EncounterGeneratorPanel.add_group_to_combat to MonsterPanel._load_initial_monsters")
            
            # Connect Monster Panel's custom monster created signal to Session Notes Panel
            session_notes_dock = self.panels.get("session_notes")
            if monster_panel and session_notes_dock:
                session_notes = session_notes_dock.widget()
                if hasattr(monster_panel, "custom_monster_created") and hasattr(session_notes, "add_monster_creation_note"):
                    monster_panel.custom_monster_created.connect(session_notes.add_monster_creation_note)
                    print("Connected MonsterPanel.custom_monster_created to SessionNotesPanel.add_monster_creation_note")
            
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
            
            # TODO: Connect Encounter Generator panel signals
            # encounter_panel = self.get_panel_widget("encounter_generator")
            # combat_tracker = self.get_panel_widget("combat_tracker")
            # if encounter_panel and combat_tracker and hasattr(encounter_panel, 'add_group_to_combat'):
            #     encounter_panel.add_group_to_combat.connect(combat_tracker.add_combatant_group) # Assuming combat_tracker has this method
            
            print("[PanelManager] Successfully connected panel signals")
            
        except Exception as e:
            print(f"[PanelManager] ERROR connecting panel signals: {e}")
            import traceback
            traceback.print_exc()
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
            "rules_clarification": RulesClarificationPanel,  # Add Rules Clarification panel to the map
            "location_generator": LocationGeneratorPanel,  # Add Location Generator panel to the map
            "treasure_generator": TreasureGeneratorPanel, # Add Treasure Generator panel to the map
            "encounter_generator": EncounterGeneratorPanel, # Add Encounter Generator panel to the map
            "combat_log": CombatLogPanel
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
        # Step 1: Temporarily hide all panels to reorganize them
        visible_panels = {}
        for panel_id, dock in self.panels.items():
            if dock and dock.isVisible():
                visible_panels[panel_id] = True
                dock.hide()
        
        # If no panels are visible, nothing to do
        if not visible_panels:
            return "No panels to organize."
        
        # Step 2: Determine screen quadrants - account for toolbar and status bar
        main_window_geometry = self.main_window.geometry()
        effective_height = main_window_geometry.height() - 50  # Account for toolbar/statusbar
        effective_width = main_window_geometry.width() 
        
        # Get panel layout settings
        tab_threshold = self.app_state.get_panel_layout_setting("tab_threshold", 4)  # Lower threshold to tab earlier
        always_tab_reference = self.app_state.get_panel_layout_setting("always_tab_reference", True)
        always_tab_campaign = self.app_state.get_panel_layout_setting("always_tab_campaign", True)
        always_tab_utility = self.app_state.get_panel_layout_setting("always_tab_utility", True)
        min_panel_width = self.app_state.get_panel_layout_setting("min_panel_width", 350)  # Increased minimum size
        min_panel_height = self.app_state.get_panel_layout_setting("min_panel_height", 250)  # Increased minimum size
        
        # Force reset dock widget locations to avoid stacking issues
        for panel_id in self.panels:
            if self.panels[panel_id]:
                self.panels[panel_id].setFloating(False)
                
                # Set minimum sizes for panels to prevent excessive squishing
                panel_widget = self.panels[panel_id].widget()
                if panel_widget:
                    # Set reasonable minimum sizes based on panel type
                    category = PanelCategory.get_category(panel_id)
                    if category == PanelCategory.COMBAT:
                        panel_widget.setMinimumSize(min_panel_width, min_panel_height)
                    elif category == PanelCategory.REFERENCE:
                        panel_widget.setMinimumSize(min_panel_width, min_panel_height)
                    elif category == PanelCategory.CAMPAIGN:
                        panel_widget.setMinimumSize(min_panel_width, min_panel_height)
                    else:  # UTILITY
                        panel_widget.setMinimumSize(min_panel_width, min_panel_height)
        
        # Step 3: Organize panels by category, applying a tab-based arrangement when more than 
        # a certain number of panels is visible
        category_panels = {
            PanelCategory.COMBAT: [],
            PanelCategory.REFERENCE: [],
            PanelCategory.CAMPAIGN: [],
            PanelCategory.UTILITY: []
        }
        
        # Sort visible panels by category
        for panel_id in visible_panels:
            category = PanelCategory.get_category(panel_id)
            category_panels[category].append(panel_id)
        
        # Count number of categories that have visible panels
        active_categories = sum(1 for cat, panels in category_panels.items() if panels)
        
        # Determine layout strategy based on number of panels and categories
        total_panels = len(visible_panels)
        
        # For 4+ panels, we'll use a more aggressive tabbing strategy
        force_tabbing = total_panels >= tab_threshold
        
        # COMBAT PANELS (Top Left)
        combat_panels = category_panels[PanelCategory.COMBAT]
        if combat_panels:
            # Add first combat panel
            first_panel = combat_panels[0]
            self.main_window.addDockWidget(Qt.TopDockWidgetArea, self.panels[first_panel])
            self.panels[first_panel].show()
            
            # If we have more than one combat panel
            if len(combat_panels) > 1:
                # If we have many visible panels overall, tabify all combat panels
                if force_tabbing or (active_categories > 2 and len(combat_panels) > 2):
                    for i in range(1, len(combat_panels)):
                        self.main_window.tabifyDockWidget(
                            self.panels[combat_panels[0]],
                            self.panels[combat_panels[i]]
                        )
                        self.panels[combat_panels[i]].show()
                else:
                    # Otherwise try to split them horizontally (side by side)
                    # But limit to 2 side-by-side panels to prevent squishing
                    for i in range(1, min(2, len(combat_panels))):
                        self.main_window.splitDockWidget(
                            self.panels[combat_panels[0]],
                            self.panels[combat_panels[i]],
                            Qt.Horizontal
                        )
                        self.panels[combat_panels[i]].show()
                    
                    # Tabify any remaining panels with the last visible one
                    for i in range(2, len(combat_panels)):
                        self.main_window.tabifyDockWidget(
                            self.panels[combat_panels[1]],
                            self.panels[combat_panels[i]]
                        )
                        self.panels[combat_panels[i]].show()
        
        # REFERENCE PANELS (Top Right)
        reference_panels = category_panels[PanelCategory.REFERENCE]
        if reference_panels:
            # Add first reference panel
            first_panel = reference_panels[0]
            self.main_window.addDockWidget(Qt.TopDockWidgetArea, self.panels[first_panel])
            self.panels[first_panel].show()
            
            # Check if we should tabify reference panels
            if always_tab_reference or len(reference_panels) > 1 or force_tabbing:
                # Always tabify reference panels since they tend to be content-heavy
                for i in range(1, len(reference_panels)):
                    self.main_window.tabifyDockWidget(
                        self.panels[reference_panels[0]],
                        self.panels[reference_panels[i]]
                    )
                    self.panels[reference_panels[i]].show()
            
            # If we have combat panels, split horizontally with them
            if combat_panels:
                self.main_window.splitDockWidget(
                    self.panels[combat_panels[0]],
                    self.panels[reference_panels[0]],
                    Qt.Horizontal
                )
        
        # CAMPAIGN PANELS (Bottom Left)
        campaign_panels = category_panels[PanelCategory.CAMPAIGN]
        if campaign_panels:
            # Add first campaign panel
            first_panel = campaign_panels[0]
            self.main_window.addDockWidget(Qt.BottomDockWidgetArea, self.panels[first_panel])
            self.panels[first_panel].show()
            
            # Check if we should tabify campaign panels
            if always_tab_campaign or len(campaign_panels) > 1 or force_tabbing:
                # Always tabify campaign panels to save space
                for i in range(1, len(campaign_panels)):
                    self.main_window.tabifyDockWidget(
                        self.panels[campaign_panels[0]],
                        self.panels[campaign_panels[i]]
                    )
                    self.panels[campaign_panels[i]].show()
            
            # Split vertically with top panels if they exist
            if combat_panels:
                self.main_window.splitDockWidget(
                    self.panels[combat_panels[0]],
                    self.panels[campaign_panels[0]],
                    Qt.Vertical
                )
        
        # UTILITY PANELS (Bottom Right)
        utility_panels = category_panels[PanelCategory.UTILITY]
        if utility_panels:
            # Add first utility panel
            first_panel = utility_panels[0]
            self.main_window.addDockWidget(Qt.BottomDockWidgetArea, self.panels[first_panel])
            self.panels[first_panel].show()
            
            # Check if we should tabify utility panels
            if always_tab_utility or len(utility_panels) > 1 or force_tabbing:
                # Always tabify utility panels
                for i in range(1, len(utility_panels)):
                    self.main_window.tabifyDockWidget(
                        self.panels[utility_panels[0]],
                        self.panels[utility_panels[i]]
                    )
                    self.panels[utility_panels[i]].show()
            
            # Split layout based on what other panels exist
            if campaign_panels:
                # Split horizontally with campaign panels
                self.main_window.splitDockWidget(
                    self.panels[campaign_panels[0]],
                    self.panels[utility_panels[0]],
                    Qt.Horizontal
                )
            elif reference_panels:
                # Split vertically with reference panels
                self.main_window.splitDockWidget(
                    self.panels[reference_panels[0]],
                    self.panels[utility_panels[0]],
                    Qt.Vertical
                )
            elif combat_panels:
                # If only combat panels exist, split diagonally
                self.main_window.splitDockWidget(
                    self.panels[combat_panels[0]],
                    self.panels[utility_panels[0]],
                    Qt.Vertical
                )
        
        # Step 4: Set appropriate panel sizes based on available space
        self._set_panel_sizes(category_panels, active_categories)
        
        # Step 5: Make sure tabbed panels have the active tab visible
        for category, panel_ids in category_panels.items():
            if len(panel_ids) > 1:
                # For each set of panels in this category, find the first one and raise it
                if panel_ids[0] in self.panels and self.panels[panel_ids[0]]:
                    self.panels[panel_ids[0]].raise_()
        
        # Apply a final sizing adjustment to ensure equal space distribution
        if active_categories >= 2:
            self._normalize_dock_sizes()
        
        # Return success message
        return "Panels have been intelligently organized to prevent overlap."
    
    def _normalize_dock_sizes(self):
        """Normalize dock sizes to ensure equal space distribution"""
        # Get all visible dock widgets
        visible_docks = []
        for dock in self.panels.values():
            if dock and dock.isVisible() and not dock.isFloating():
                visible_docks.append(dock)
        
        # Skip if no visible docks
        if not visible_docks:
            return
        
        # Get main window size
        main_window_geometry = self.main_window.geometry()
        window_width = main_window_geometry.width()
        window_height = main_window_geometry.height()
        
        # Calculate ideal sizes based on number of visible docks
        horizontal_count = len(set(dock.x() for dock in visible_docks))
        vertical_count = len(set(dock.y() for dock in visible_docks))
        
        if horizontal_count > 0 and vertical_count > 0:
            ideal_width = window_width / horizontal_count
            ideal_height = window_height / vertical_count
            
            # Apply size constraints
            for dock in visible_docks:
                dock_size = dock.size()
                # Only adjust if panels are too large or too small
                if dock_size.width() > ideal_width * 1.5 or dock_size.width() < ideal_width * 0.5:
                    dock.resize(int(ideal_width * 0.95), dock_size.height())
                if dock_size.height() > ideal_height * 1.5 or dock_size.height() < ideal_height * 0.5:
                    dock.resize(dock_size.width(), int(ideal_height * 0.95))

    def is_panel_visible(self, panel_type):
        """Check if a panel is currently visible"""
        if panel_type in self.panels and self.panels[panel_type]:
            return self.panels[panel_type].isVisible()
        return False

    def _setup_initial_layout(self):
        """Set up the initial panel layout"""
        # Show welcome panel first if this is a first launch
        if self.app_state.get_setting("first_launch", True):
            self.toggle_panel("welcome")
            self.app_state.update_setting("first_launch", False)
            return

        # Get list of panels to show on startup
        visible_panels = self.app_state.get_setting("visible_panels", ["combat_tracker", "dice_roller", "combat_log", "conditions"])
        
        # Show the panels
        for panel_id in visible_panels:
            if panel_id in self.panels:
                self.panels[panel_id].show()
        
        # Set up specific layouts
        
        # Combat category: organize combat_tracker, dice_roller, and combat_log
        if "combat_tracker" in self.panels and self.panels["combat_tracker"] and "dice_roller" in self.panels and self.panels["dice_roller"]:
            # Tabify combat tracker and combat log
            if "combat_log" in self.panels and self.panels["combat_log"]:
                self.tabifyDockWidget(
                    self.panels["combat_tracker"],
                    self.panels["combat_log"]
                )
                # Split them horizontally with dice roller
                self.splitDockWidget(
                    self.panels["combat_tracker"],
                    self.panels["dice_roller"],
                    Qt.Horizontal
                )
            else:
                # If no combat log, just split combat tracker and dice roller
                self.splitDockWidget(
                    self.panels["combat_tracker"],
                    self.panels["dice_roller"],
                    Qt.Horizontal
                )
            
            # Raise the combat tracker initially
            if "combat_tracker" in self.panels and self.panels["combat_tracker"]:
                self.panels["combat_tracker"].raise_()
                
        # Reference category: tabify conditions, rules reference, and spell reference
        condition_docks = [self.panels.get(id) for id in ["conditions", "rules_reference", "spell_reference"] if id in self.panels and self.panels[id]]
        self._tabify_multiple(condition_docks)

    def organize_panel_layout(self):
        """Organize the layout of visible panels by category"""
        # Use the new _setup_initial_layout method
        if hasattr(self, '_setup_initial_layout'):
            self._setup_initial_layout()
            return
            
        # Legacy layout organization (kept for backward compatibility)
        # Show welcome panel first if this is a first launch
        if self.app_state.get_setting("first_launch", True):
            self.toggle_panel("welcome")
            self.app_state.update_setting("first_launch", False)
            return

        # Get list of panels to show on startup
        visible_panels = self.app_state.get_setting("visible_panels", ["combat_tracker", "dice_roller", "conditions"])
        
        # Show the panels
        for panel_id in visible_panels:
            if panel_id in self.panels:
                self.panels[panel_id].show()
        
        # If both combat tracker and dice roller are shown, split them horizontally
        if "combat_tracker" in self.panels and self.panels["combat_tracker"] and \
           "dice_roller" in self.panels and self.panels["dice_roller"]:
            self.splitDockWidget(
                self.panels["combat_tracker"],
                self.panels["dice_roller"],
                Qt.Horizontal
            )
        
        # Tabify similar panels - group by category
        condition_docks = []
        if "conditions" in self.panels and self.panels["conditions"]:
            condition_docks.append(self.panels["conditions"])
        if "rules_reference" in self.panels and self.panels["rules_reference"]:
            condition_docks.append(self.panels["rules_reference"])
        if "spell_reference" in self.panels and self.panels["spell_reference"]:
            condition_docks.append(self.panels["spell_reference"])
        
        self._tabify_multiple(condition_docks)
        
        # Raise the combat tracker initially
        if "combat_tracker" in self.panels and self.panels["combat_tracker"]:
            self.panels["combat_tracker"].raise_()

    def _set_panel_sizes(self, category_panels, active_categories):
        """Set appropriate sizes for panels based on layout"""
        main_window_geometry = self.main_window.geometry()
        window_width = main_window_geometry.width()
        window_height = main_window_geometry.height()
        
        # Get panel layout settings
        use_percentage_sizing = self.app_state.get_panel_layout_setting("use_percentage_sizing", True)
        
        # If not using percentage-based sizing, just use default sizes
        if not use_percentage_sizing:
            return
        
        # Set size multipliers based on the number of active categories
        width_multiplier = 0.45
        height_multiplier = 0.45
        
        if active_categories == 1:
            # If only one category is visible, give it more space
            width_multiplier = 0.9
            height_multiplier = 0.9
        elif active_categories == 2:
            # If two categories are visible, give them half the space each
            width_multiplier = 0.5
            height_multiplier = 0.5
        
        # Ensure all panels have reasonable sizes
        for category, panel_ids in category_panels.items():
            # Only process the first panel in each category since others may be tabbed
            if not panel_ids:
                continue
                
            panel_id = panel_ids[0]
            if not self.panels[panel_id]:
                continue
                
            dock = self.panels[panel_id]
            
            # Skip floating panels - they're handled separately
            if dock.isFloating():
                continue
                
            # Set size based on category and available space
            if category == PanelCategory.COMBAT:
                # Combat panels take up more space for maps and tokens
                width = min(int(window_width * width_multiplier), 800)
                height = min(int(window_height * height_multiplier), 600)
                dock.resize(width, height)
            elif category == PanelCategory.REFERENCE:
                # Reference panels need space for text content
                width = min(int(window_width * width_multiplier), 800)
                height = min(int(window_height * height_multiplier), 600)
                dock.resize(width, height)
            elif category == PanelCategory.CAMPAIGN:
                # Campaign panels for notes and management
                width = min(int(window_width * width_multiplier), 800)
                height = min(int(window_height * (height_multiplier * 0.9)), 500)
                dock.resize(width, height)
            else:  # UTILITY
                # Utility panels usually need less space
                width = min(int(window_width * (width_multiplier * 0.9)), 700)
                height = min(int(window_height * (height_multiplier * 0.9)), 500)
                dock.resize(width, height)
                
        # Handle floating panels separately
        for panel_id, dock in self.panels.items():
            if dock and dock.isVisible() and dock.isFloating():
                category = PanelCategory.get_category(panel_id)
                # Set size based on category
                if category == PanelCategory.COMBAT:
                    dock.resize(700, 500)
                elif category == PanelCategory.REFERENCE:
                    dock.resize(650, 550)
                elif category == PanelCategory.CAMPAIGN:
                    dock.resize(600, 450)
                else:  # UTILITY
                    dock.resize(500, 400)