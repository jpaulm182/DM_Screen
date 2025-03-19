# app/ui/panel_manager.py - Panel management system
"""
Panel management system for the DM Screen application

Handles creating, organizing, and managing dockable panels.
"""

from PySide6.QtWidgets import QDockWidget, QMessageBox
from PySide6.QtCore import Qt, QObject

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
        
        # Initialize panels
        self._init_panels()
        
        # Connect panel signals
        self._connect_panel_signals()
    
    def _init_panels(self):
        """Initialize all available panels"""
        # Create panels
        self.panels["combat_tracker"] = self._create_panel(CombatTrackerPanel)
        self.panels["dice_roller"] = self._create_panel(DiceRollerPanel)
        self.panels["conditions"] = self._create_panel(ConditionsPanel)
        self.panels["rules_reference"] = self._create_panel(RulesReferencePanel)
        self.panels["monster"] = self._create_panel(MonsterPanel)
        self.panels["spell_reference"] = self._create_panel(SpellReferencePanel)
        self.panels["session_notes"] = self._create_panel(SessionNotesPanel)
        self.panels["weather"] = self._create_panel(WeatherPanel)
        self.panels["time_tracker"] = self._create_panel(TimeTrackerPanel)
        
        # Set initial dock locations
        self.main_window.addDockWidget(Qt.LeftDockWidgetArea, self.panels["dice_roller"])
        self.main_window.addDockWidget(Qt.LeftDockWidgetArea, self.panels["combat_tracker"])
        self.main_window.addDockWidget(Qt.RightDockWidgetArea, self.panels["conditions"])
        self.main_window.addDockWidget(Qt.RightDockWidgetArea, self.panels["rules_reference"])
        self.main_window.addDockWidget(Qt.RightDockWidgetArea, self.panels["monster"])
        self.main_window.addDockWidget(Qt.RightDockWidgetArea, self.panels["spell_reference"])
        self.main_window.addDockWidget(Qt.BottomDockWidgetArea, self.panels["session_notes"])
        self.main_window.addDockWidget(Qt.BottomDockWidgetArea, self.panels["weather"])
        self.main_window.addDockWidget(Qt.BottomDockWidgetArea, self.panels["time_tracker"])
        
        # Tabify related panels
        self.main_window.tabifyDockWidget(
            self.panels["conditions"],
            self.panels["rules_reference"]
        )
        self.main_window.tabifyDockWidget(
            self.panels["rules_reference"],
            self.panels["monster"]
        )
        self.main_window.tabifyDockWidget(
            self.panels["monster"],
            self.panels["spell_reference"]
        )
        
        # Tabify weather and time tracker
        self.main_window.tabifyDockWidget(
            self.panels["weather"],
            self.panels["time_tracker"]
        )
        
        # Raise the combat tracker initially
        self.panels["combat_tracker"].raise_()
    
    def _create_panel(self, panel_class):
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
            
            return dock
            
        except Exception as e:
            QMessageBox.critical(
                self.main_window,
                "Panel Creation Error",
                f"Failed to create {panel_class.__name__}: {str(e)}"
            )
            return None
    
    def _connect_panel_signals(self):
        """Connect signals between panels"""
        try:
            # Connect monster panel to combat tracker
            monster_panel = self.panels["monster"].widget()
            combat_tracker = self.panels["combat_tracker"].widget()
            
            # Debug print to check panel instances
            print("Monster Panel:", monster_panel)
            print("Combat Tracker:", combat_tracker)
            
            if monster_panel and combat_tracker:
                if hasattr(monster_panel, "add_to_combat"):
                    print("Connecting add_to_combat signal")
                    monster_panel.add_to_combat.connect(combat_tracker.add_monster)
                else:
                    print("Monster panel missing add_to_combat signal")
            
            # Connect conditions panel to combat tracker
            conditions_panel = self.panels["conditions"].widget()
            if conditions_panel and hasattr(conditions_panel, "apply_condition"):
                conditions_panel.apply_condition.connect(combat_tracker.apply_condition)
            
            # Connect weather panel and time tracker panel (future integration)
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
        """Create a specific panel and show it"""
        if panel_type in self.panels and self.panels[panel_type]:
            # Panel already exists, just show it
            self.panels[panel_type].show()
            self.panels[panel_type].raise_()
            return
        
        # Create new panel based on type
        if panel_type == "combat_tracker":
            self.panels[panel_type] = self._create_panel(CombatTrackerPanel)
        elif panel_type == "dice_roller":
            self.panels[panel_type] = self._create_panel(DiceRollerPanel)
        elif panel_type == "conditions":
            self.panels[panel_type] = self._create_panel(ConditionsPanel)
        elif panel_type == "rules_reference":
            self.panels[panel_type] = self._create_panel(RulesReferencePanel)
        elif panel_type == "monster":
            self.panels[panel_type] = self._create_panel(MonsterPanel)
        elif panel_type == "spell_reference":
            self.panels[panel_type] = self._create_panel(SpellReferencePanel)
        elif panel_type == "session_notes":
            self.panels[panel_type] = self._create_panel(SessionNotesPanel)
        elif panel_type == "weather":
            self.panels[panel_type] = self._create_panel(WeatherPanel)
        elif panel_type == "time_tracker":
            self.panels[panel_type] = self._create_panel(TimeTrackerPanel)
        else:
            QMessageBox.warning(
                self.main_window,
                "Panel Creation Error",
                f"Unknown panel type: {panel_type}"
            )
            return
        
        # Add the new panel to the main window
        self.main_window.addDockWidget(Qt.RightDockWidgetArea, self.panels[panel_type])
        self.panels[panel_type].show()
        self.panels[panel_type].raise_()
    
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
        """Get a panel by name"""
        return self.panels.get(name)