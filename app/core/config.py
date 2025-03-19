"""
Configuration settings for the DM Screen application

Provides centralized configuration and path management.
"""

import os
from pathlib import Path


def get_app_dir():
    """
    Get the application directory based on platform
    
    Returns:
        Path: Path to the application data directory
    """
    # Check for environment variable first (for development/testing)
    if "DM_SCREEN_DATA_DIR" in os.environ:
        return Path(os.environ["DM_SCREEN_DATA_DIR"])
        
    # Default platform-specific locations
    home = Path.home()
    
    if os.name == "nt":  # Windows
        app_dir = home / "AppData" / "Local" / "DM_Screen"
    elif os.name == "posix":  # Linux/Mac
        # Check if we're on macOS
        if os.path.exists(home / "Library"):
            app_dir = home / "Library" / "Application Support" / "DM_Screen"
        else:  # Linux
            app_dir = home / ".local" / "share" / "dm_screen"
    else:
        # Fallback
        app_dir = home / ".dm_screen"
    
    # Ensure directory exists
    os.makedirs(app_dir, exist_ok=True)
    
    return app_dir


def get_database_path():
    """
    Get the path to the SQLite database file
    
    Returns:
        Path: Path to the database file
    """
    return get_app_dir() / "dm_screen.db"


def get_assets_dir():
    """
    Get the path to the assets directory
    
    Returns:
        Path: Path to the assets directory
    """
    # First check if we're in a development environment
    # (assets located in project directory)
    current_dir = Path(__file__).resolve().parent.parent.parent
    dev_assets = current_dir / "assets"
    
    if dev_assets.exists():
        return dev_assets
    
    # Otherwise use the installed assets location
    return get_app_dir() / "assets"


def get_config_path():
    """
    Get the path to the user configuration file
    
    Returns:
        Path: Path to the config file
    """
    return get_app_dir() / "config.json" 