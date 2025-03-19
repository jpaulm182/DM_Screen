# app/ui/theme_manager.py - Theme management
"""
Theme management for the DM Screen application

Provides functions for applying and managing application themes.
"""

from PySide6.QtGui import QPalette, QColor
from PySide6.QtWidgets import QApplication

def apply_theme(widget, theme_name):
    """Apply a theme to the application"""
    if theme_name == "dark":
        _apply_dark_theme(widget)
    else:
        _apply_light_theme(widget)

def _apply_dark_theme(widget):
    """Apply the dark theme palette"""
    palette = QPalette()
    
    # Base colors
    palette.setColor(QPalette.Window, QColor(53, 53, 53))
    palette.setColor(QPalette.WindowText, QColor(255, 255, 255))
    palette.setColor(QPalette.Base, QColor(42, 42, 42))
    palette.setColor(QPalette.AlternateBase, QColor(66, 66, 66))
    palette.setColor(QPalette.Text, QColor(255, 255, 255))
    palette.setColor(QPalette.Button, QColor(53, 53, 53))
    palette.setColor(QPalette.ButtonText, QColor(255, 255, 255))
    
    # Highlight colors
    palette.setColor(QPalette.Highlight, QColor(49, 106, 197))
    palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
    
    # Link colors
    palette.setColor(QPalette.Link, QColor(42, 130, 218))
    palette.setColor(QPalette.LinkVisited, QColor(147, 112, 219))
    
    # Disabled colors
    palette.setColor(QPalette.Disabled, QPalette.WindowText, QColor(127, 127, 127))
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor(127, 127, 127))
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(127, 127, 127))
    
    # Apply the palette
    widget.setPalette(palette)
    
    # Apply to application if this is the main window
    if widget.isWindow():
        QApplication.instance().setPalette(palette)

def _apply_light_theme(widget):
    """Apply the light theme palette"""
    palette = QPalette()
    
    # Base colors
    palette.setColor(QPalette.Window, QColor(240, 240, 240))
    palette.setColor(QPalette.WindowText, QColor(0, 0, 0))
    palette.setColor(QPalette.Base, QColor(255, 255, 255))
    palette.setColor(QPalette.AlternateBase, QColor(233, 233, 233))
    palette.setColor(QPalette.Text, QColor(0, 0, 0))
    palette.setColor(QPalette.Button, QColor(240, 240, 240))
    palette.setColor(QPalette.ButtonText, QColor(0, 0, 0))
    
    # Highlight colors
    palette.setColor(QPalette.Highlight, QColor(57, 123, 209))
    palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
    
    # Link colors
    palette.setColor(QPalette.Link, QColor(41, 128, 185))
    palette.setColor(QPalette.LinkVisited, QColor(127, 80, 160))
    
    # Disabled colors
    palette.setColor(QPalette.Disabled, QPalette.WindowText, QColor(120, 120, 120))
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor(120, 120, 120))
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(120, 120, 120))
    
    # Apply the palette
    widget.setPalette(palette)
    
    # Apply to application if this is the main window
    if widget.isWindow():
        QApplication.instance().setPalette(palette)
