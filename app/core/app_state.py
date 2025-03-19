# app/core/app_state.py - Application state management
"""
Application state management for DM Screen

Handles global application state, settings, and configuration.
"""

import json
import os
from pathlib import Path

class AppState:
    """
    Manages global application state, user preferences, and session data
    """
    
    def __init__(self):
        """Initialize application state and load user preferences"""
        self.panels = {}  # Active panels by ID
        self.layout_config = {}  # Current layout configuration
        self.settings = {
            "theme": "dark",  # Default theme
            "font_size": "medium",
            "auto_save": True,
            "backup_frequency": 15,  # minutes
        }
        
        # Ensure application directories exist
        self.app_dir = Path.home() / ".dm_screen"
        self.data_dir = self.app_dir / "data"
        self.config_dir = self.app_dir / "config"
        self.backup_dir = self.app_dir / "backups"
        
        self._ensure_directories()
        self._load_settings()
    
    def _ensure_directories(self):
        """Create application directories if they don't exist"""
        for directory in [self.app_dir, self.data_dir, self.config_dir, self.backup_dir]:
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
    
    def save_settings(self):
        """Save current settings to configuration file"""
        settings_file = self.config_dir / "settings.json"
        try:
            with open(settings_file, 'w') as f:
                json.dump(self.settings, f, indent=2)
        except Exception as e:
            print(f"Error saving settings: {e}")
    
    def save_layout(self, name="default"):
        """Save current layout configuration"""
        layout_file = self.config_dir / f"layout_{name}.json"
        try:
            with open(layout_file, 'w') as f:
                json.dump(self.layout_config, f, indent=2)
        except Exception as e:
            print(f"Error saving layout: {e}")
    
    def load_layout(self, name="default"):
        """Load layout configuration"""
        layout_file = self.config_dir / f"layout_{name}.json"
        if layout_file.exists():
            try:
                with open(layout_file, 'r') as f:
                    self.layout_config = json.load(f)
                return True
            except Exception as e:
                print(f"Error loading layout: {e}")
        return False
    
    def get_setting(self, key, default=None):
        """Get a setting value with an optional default"""
        return self.settings.get(key, default)
    
    def set_setting(self, key, value):
        """Update a setting value"""
        self.settings[key] = value
        # Save settings immediately for persistence
        self.save_settings()
