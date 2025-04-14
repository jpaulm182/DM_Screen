# app/core/app_state.py - Application state management
"""
Application state management for DM Screen

Handles global application state, settings, and configuration.
"""

import json
import os
import time
from pathlib import Path
from datetime import datetime

from app.core.llm_service import LLMService
from app.data.llm_data_manager import LLMDataManager
from app.core.config import get_app_dir
from app.core.combat_resolver import CombatResolver

# Default application settings
DEFAULT_SETTINGS = {
    "theme": "dark",
    "font_size": 12,
    "first_launch": True,
    "visible_panels": ["combat_tracker", "dice_roller"],
    "auto_save_interval": 5,  # minutes
    "layout_version": 1,
    # Panel layout settings
    "panel_layout": {
        "tab_threshold": 4,  # Number of panels before forcing tabbing
        "always_tab_reference": True,  # Always tab reference panels
        "always_tab_campaign": True,  # Always tab campaign panels
        "always_tab_utility": True,  # Always tab utility panels
        "min_panel_width": 350,  # Minimum width for panels
        "min_panel_height": 250,  # Minimum height for panels
        "use_percentage_sizing": True,  # Use percentage-based sizing instead of fixed
        "panel_border_intensity": 3  # Border thickness (1-5)
    }
}

class AppState:
    """
    Manages global application state, user preferences, and session data
    """
    
    def __init__(self):
        """Initialize application state and load user preferences"""
        self.panels = {}  # Active panels by ID
        self.layout_config = {}  # Current layout configuration
        self.current_layout_name = "default"  # Name of currently loaded layout
        self.settings = {
            "theme": "dark",  # Default theme
            "font_size": "medium",
            "auto_save": True,
            "backup_frequency": 15,  # minutes
        }
        
        # Ensure application directories exist
        self.app_dir = get_app_dir()
        self.data_dir = self.app_dir / "data"
        self.config_dir = self.app_dir / "config"
        self.backup_dir = self.app_dir / "backups"
        self.layouts_dir = self.app_dir / "layouts"
        
        self._ensure_directories()
        self._load_settings()
        
        # Create default layouts if they don't exist
        self._create_default_layouts()
        
        # Initialize database manager
        from app.data.db_manager import DatabaseManager
        self.db_manager = DatabaseManager(self)
        
        # Initialize LLM services
        self.llm_data_manager = LLMDataManager(self)
        self.llm_service = LLMService(self)
        self.combat_resolver = CombatResolver(self.llm_service)
    
    def _ensure_directories(self):
        """Create application directories if they don't exist"""
        for directory in [self.app_dir, self.data_dir, self.config_dir, 
                          self.backup_dir, self.layouts_dir]:
            directory.mkdir(exist_ok=True, parents=True)
    
    def _load_settings(self):
        """Load user settings from configuration file"""
        settings_file = self.config_dir / "settings.json"
        if settings_file.exists():
            try:
                with open(settings_file, 'r') as f:
                    loaded_settings = json.load(f)
                    self.settings.update(loaded_settings)
            except Exception as e:
                print(f"Error loading settings: {e}")
    
    def _create_default_layouts(self):
        """Create default layout presets if they don't exist"""
        default_layouts = {
            "Combat Focus": {
                "is_preset": True,
                "category": "Combat",
                "description": "Optimized for combat encounters with all combat tools available.",
                "visible_panels": ["combat_tracker", "dice_roller", "combat_log", "conditions"],
                "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            },
            "Exploration": {
                "is_preset": True,
                "category": "Exploration",
                "description": "Focused on exploration with maps, time tracking, and weather.",
                "visible_panels": ["weather", "time_tracker", "rules_reference"],
                "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            },
            "Reference": {
                "is_preset": True,
                "category": "Reference",
                "description": "All reference tools visible for quick information lookup.",
                "visible_panels": ["monster", "spell_reference", "rules_reference", "conditions"],
                "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            },
            "Full Suite": {
                "is_preset": True,
                "category": "Custom",
                "description": "All available panels organized for maximum visibility.",
                "visible_panels": ["combat_tracker", "dice_roller", "monster", "spell_reference", 
                                  "conditions", "rules_reference", "session_notes", 
                                  "weather", "time_tracker"],
                "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        }
        
        # Create each default layout if it doesn't exist
        for name, data in default_layouts.items():
            layout_file = self.layouts_dir / f"{name}.json"
            if not layout_file.exists():
                try:
                    with open(layout_file, 'w') as f:
                        json.dump(data, f, indent=2)
                except Exception as e:
                    print(f"Error creating default layout '{name}': {e}")
    
    def save_settings(self):
        """Save current settings to configuration file"""
        settings_file = self.config_dir / "settings.json"
        try:
            with open(settings_file, 'w') as f:
                json.dump(self.settings, f, indent=2)
        except Exception as e:
            print(f"Error saving settings: {e}")
    
    def get_available_layouts(self):
        """Get a dictionary of all available layouts with metadata
        
        Returns:
            dict: Dictionary with layout names as keys and metadata as values
        """
        layouts = {}
        
        for file_path in self.layouts_dir.glob("*.json"):
            try:
                name = file_path.stem
                with open(file_path, 'r') as f:
                    data = json.load(f)
                layouts[name] = data
            except Exception as e:
                print(f"Error loading layout '{file_path.name}': {e}")
                
        return layouts
    
    def save_layout(self, name=None, layout_data=None, ui_state=None, is_preset=False, category=None):
        """Save current layout configuration
        
        Args:
            name (str): Name of the layout
            layout_data (dict): Additional layout data including visible panels
            ui_state (bytes): The serialized UI state from QMainWindow.saveState()
            is_preset (bool): Whether this is a preset layout
            category (str): Category for preset layouts
            
        Returns:
            bool: True if layout was saved successfully
        """
        if not name:
            name = self.current_layout_name or "default"
        
        # Prepare layout data
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        data = layout_data or {}
        data["modified"] = timestamp
        
        if "created" not in data:
            data["created"] = timestamp
            
        if is_preset is not None:
            data["is_preset"] = is_preset
            
        if category and is_preset:
            data["category"] = category
            
        if ui_state:
            # Convert QByteArray to a storable format
            data["ui_state"] = ui_state.toHex().data().decode()
        
        # Save to file
        layout_file = self.layouts_dir / f"{name}.json"
        try:
            with open(layout_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            # Update current layout name
            self.current_layout_name = name
            return True
        except Exception as e:
            print(f"Error saving layout '{name}': {e}")
            return False
    
    def load_layout(self, name=None):
        """Load layout configuration
        
        Args:
            name (str): Name of the layout to load
            
        Returns:
            tuple: (success, data, ui_state) where:
                - success is a boolean indicating if load was successful
                - data is the layout configuration data
                - ui_state is the serialized UI state for QMainWindow.restoreState()
        """
        if not name:
            name = self.current_layout_name or "default"
            
        layout_file = self.layouts_dir / f"{name}.json"
        
        if not layout_file.exists():
            # If requested layout doesn't exist, try default
            if name != "default":
                return self.load_layout("default")
            return False, None, None
            
        try:
            with open(layout_file, 'r') as f:
                data = json.load(f)
                
            # Extract serialized UI state if it exists
            ui_state = None
            if "ui_state" in data:
                try:
                    # Convert from hex string back to bytes
                    ui_state = bytes.fromhex(data["ui_state"])
                except ValueError:
                    # For backward compatibility with old format
                    print(f"Warning: Could not parse UI state from '{name}' layout")
                    ui_state = None
            
            # Update current layout name
            self.current_layout_name = name
            
            return True, data, ui_state
        except Exception as e:
            print(f"Error loading layout '{name}': {e}")
            return False, None, None
    
    def delete_layout(self, name):
        """Delete a layout configuration
        
        Args:
            name (str): Name of the layout to delete
            
        Returns:
            bool: True if layout was deleted successfully
        """
        if not name or name == "default":
            return False  # Don't allow deleting default layout
            
        layout_file = self.layouts_dir / f"{name}.json"
        
        if layout_file.exists():
            try:
                layout_file.unlink()
                return True
            except Exception as e:
                print(f"Error deleting layout '{name}': {e}")
                
        return False
    
    def get_setting(self, key, default=None):
        """Get a setting value with an optional default"""
        return self.settings.get(key, default)
    
    def set_setting(self, key, value):
        """Update a setting value"""
        self.settings[key] = value
        # Save settings immediately for persistence
        self.save_settings()

    def close(self):
        """Close all resources and perform cleanup"""
        # Save current settings
        self.save_settings()
        
        # Close database connection
        if hasattr(self, 'db_manager'):
            self.db_manager.close()
            
        # Close LLM data manager
        if hasattr(self, 'llm_data_manager'):
            self.llm_data_manager.close()

    def get_panel_widget(self, panel_id):
        """
        Get a panel widget by its ID
        
        Args:
            panel_id: The ID of the panel to retrieve
            
        Returns:
            The panel widget if found, None otherwise
        """
        # Make sure we have a panel manager
        if not hasattr(self, 'panel_manager'):
            print(f"AppState has no panel_manager")
            return None
            
        # Get the panel dock widget
        panel_dock = self.panel_manager.get_panel(panel_id)
        if not panel_dock:
            print(f"Panel dock {panel_id} not found")
            return None
            
        # Get the widget inside the dock
        panel_widget = panel_dock.widget()
        if not panel_widget:
            print(f"Panel {panel_id} has no widget")
            return None
            
        return panel_widget

    def get_panel_layout_setting(self, setting_name, default=None):
        """Get a specific panel layout setting
        
        Args:
            setting_name: Name of the panel layout setting
            default: Default value if not found
            
        Returns:
            The value of the setting or default if not found
        """
        panel_layout = self.get_setting("panel_layout", {})
        if default is None and setting_name in DEFAULT_SETTINGS["panel_layout"]:
            default = DEFAULT_SETTINGS["panel_layout"][setting_name]
        return panel_layout.get(setting_name, default)
        
    def update_panel_layout_setting(self, setting_name, value):
        """Update a specific panel layout setting
        
        Args:
            setting_name: Name of the panel layout setting
            value: New value for the setting
        """
        panel_layout = self.get_setting("panel_layout", {})
        panel_layout[setting_name] = value
        self.set_setting("panel_layout", panel_layout)
        
    def get_panel_setting(self, panel_id, setting_name, default=None):
        """Get a panel-specific setting
        
        Args:
            panel_id: The ID of the panel (e.g., 'dice_roller')
            setting_name: Name of the setting to retrieve
            default: Default value if setting is not found
            
        Returns:
            The value of the setting or default if not found
        """
        panel_settings = self.get_setting("panel_settings", {})
        panel_config = panel_settings.get(panel_id, {})
        return panel_config.get(setting_name, default)
        
    def save_panel_setting(self, panel_id, setting_name, value):
        """Save a panel-specific setting
        
        Args:
            panel_id: The ID of the panel (e.g., 'dice_roller')
            setting_name: Name of the setting to save
            value: Value to save
        """
        panel_settings = self.get_setting("panel_settings", {})
        
        if panel_id not in panel_settings:
            panel_settings[panel_id] = {}
            
        panel_settings[panel_id][setting_name] = value
        self.set_setting("panel_settings", panel_settings)
