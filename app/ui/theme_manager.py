# app/ui/theme_manager.py - Theme management
"""
Theme management for the DM Screen application

Provides functions for applying and managing application themes.
"""

from PySide6.QtGui import QPalette, QColor, QFont
from PySide6.QtWidgets import QApplication

# Default font sizes
FONT_SIZES = {
    "small": 8,
    "medium": 10,
    "large": 12,
    "x-large": 14
}

def apply_theme(widget, theme_name, font_size="medium"):
    """Apply a theme to the application"""
    if theme_name == "dark":
        _apply_dark_theme(widget, font_size)
    else:
        _apply_light_theme(widget, font_size)

def set_font_size(font_size):
    """Set font size for the application"""
    if font_size in FONT_SIZES:
        size = FONT_SIZES[font_size]
    else:
        size = FONT_SIZES["medium"]
    
    app = QApplication.instance()
    font = app.font()
    font.setPointSize(size)
    app.setFont(font)
    
    return size

def _apply_dark_theme(widget, font_size="medium"):
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
    
    # Group/Tab colors
    palette.setColor(QPalette.Light, QColor(76, 76, 76))
    palette.setColor(QPalette.Midlight, QColor(66, 66, 66))
    palette.setColor(QPalette.Mid, QColor(56, 56, 56))
    palette.setColor(QPalette.Dark, QColor(46, 46, 46))
    palette.setColor(QPalette.Shadow, QColor(26, 26, 26))
    
    # Apply the palette
    widget.setPalette(palette)
    
    # Apply to application if this is the main window
    if widget.isWindow():
        QApplication.instance().setPalette(palette)
        
        # Apply font size
        set_font_size(font_size)
        
        # Apply additional styling
        _apply_additional_styling(widget, "dark")

def _apply_light_theme(widget, font_size="medium"):
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
    
    # Group/Tab colors
    palette.setColor(QPalette.Light, QColor(255, 255, 255))
    palette.setColor(QPalette.Midlight, QColor(226, 226, 226))
    palette.setColor(QPalette.Mid, QColor(200, 200, 200))
    palette.setColor(QPalette.Dark, QColor(170, 170, 170))
    palette.setColor(QPalette.Shadow, QColor(130, 130, 130))
    
    # Apply the palette
    widget.setPalette(palette)
    
    # Apply to application if this is the main window
    if widget.isWindow():
        QApplication.instance().setPalette(palette)
        
        # Apply font size
        set_font_size(font_size)
        
        # Apply additional styling
        _apply_additional_styling(widget, "light")

def _apply_additional_styling(widget, theme):
    """Apply additional styling to specific components"""
    # Style sheet for common widgets in each theme
    if theme == "dark":
        style = """
            QTabWidget::pane {
                border: 1px solid #666;
                background-color: #333;
            }
            QTabBar::tab {
                background-color: #444;
                color: #ccc;
                padding: 6px 10px;
                border: 1px solid #666;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected, QTabBar::tab:hover {
                background-color: #555;
                color: #fff;
            }
            QTabBar::tab:selected {
                border-bottom-color: #444;
            }
            QStatusBar {
                background-color: #333;
                color: #ccc;
            }
            QMenu {
                background-color: #333;
                color: #fff;
                border: 1px solid #555;
            }
            QMenu::item:selected {
                background-color: #4466aa;
            }
            QToolBar {
                background-color: #444;
                border: none;
                padding: 2px;
                spacing: 3px;
            }
            QToolBar QLabel {
                color: #aaa;
                font-weight: bold;
                margin-left: 5px;
            }
            QToolButton {
                background-color: #555;
                color: #fff;
                border: 1px solid #666;
                border-radius: 3px;
                padding: 2px;
            }
            QToolButton:hover {
                background-color: #666;
            }
            QToolButton:pressed {
                background-color: #444;
            }
        """
    else:  # Light theme
        style = """
            QTabWidget::pane {
                border: 1px solid #bbb;
                background-color: #f5f5f5;
            }
            QTabBar::tab {
                background-color: #e0e0e0;
                color: #333;
                padding: 6px 10px;
                border: 1px solid #bbb;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected, QTabBar::tab:hover {
                background-color: #f5f5f5;
                color: #000;
            }
            QTabBar::tab:selected {
                border-bottom-color: #f5f5f5;
            }
            QStatusBar {
                background-color: #e0e0e0;
                color: #333;
            }
            QMenu {
                background-color: #f5f5f5;
                color: #333;
                border: 1px solid #ccc;
            }
            QMenu::item:selected {
                background-color: #cce6ff;
            }
            QToolBar {
                background-color: #e5e5e5;
                border: none;
                padding: 2px;
                spacing: 3px;
            }
            QToolBar QLabel {
                color: #666;
                font-weight: bold;
                margin-left: 5px;
            }
            QToolButton {
                background-color: #eee;
                color: #333;
                border: 1px solid #ccc;
                border-radius: 3px;
                padding: 2px;
            }
            QToolButton:hover {
                background-color: #f5f5f5;
            }
            QToolButton:pressed {
                background-color: #ddd;
            }
        """
    
    # Apply the stylesheet to the application
    QApplication.instance().setStyleSheet(style)
