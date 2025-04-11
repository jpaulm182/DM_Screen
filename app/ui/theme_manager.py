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

def apply_theme(widget, theme_name="dark", font_size=None):
    """Apply a theme to the application
    
    Args:
        widget: The main application widget
        theme_name: The theme name ('dark' or 'light')
        font_size: Optional font size to apply
    """
    # Get theme stylesheet
    style = get_theme_stylesheet(theme_name)
    
    # Apply the stylesheet
    widget.setStyleSheet(style)
    
    # Apply font size if specified
    if font_size is not None:
        set_font_size(widget, font_size)

def set_font_size(widget, size):
    """Set the application font size
    
    Args:
        widget: The main application widget
        size: Font size in points or name ('small', 'medium', 'large')
    """
    # Convert named sizes to points if needed
    if isinstance(size, str):
        size_map = {
            "small": 10,
            "medium": 12,
            "large": 14,
            "x-large": 16
        }
        size = size_map.get(size.lower(), 12)
    
    # Get current font
    font = widget.font()
    font.setPointSize(size)
    
    # Apply font to application
    widget.setFont(font)
    
    # Apply to all child widgets
    for child in widget.findChildren(object):
        try:
            if hasattr(child, 'setFont'):
                child.setFont(font)
        except:
            pass

def get_theme_stylesheet(theme_name):
    """Get the CSS stylesheet for a theme
    
    Args:
        theme_name: The theme name ('dark' or 'light')
        
    Returns:
        str: The CSS stylesheet
    """
    if theme_name == "light":
        return """
            QMainWindow {
                background-color: #F0F0F0;
                color: #303030;
            }
            QWidget {
                background-color: #F5F5F5;
                color: #303030;
            }
            QMenu {
                background-color: #FAFAFA;
                color: #303030;
                border: 1px solid #CCCCCC;
            }
            QMenuBar {
                background-color: #E5E5E5;
                color: #303030;
            }
            QToolBar {
                background-color: #E5E5E5;
                color: #303030;
                spacing: 3px;
                border: 0px;
            }
            QStatusBar {
                background-color: #E5E5E5;
                color: #303030;
            }
            QTabWidget::pane {
                border: 1px solid #CCCCCC;
            }
            QTabBar::tab {
                background-color: #E0E0E0;
                color: #505050;
                border: 1px solid #CCCCCC;
                padding: 5px 10px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: #F5F5F5;
                color: #303030;
                border-bottom-color: #F5F5F5;
            }
            QToolButton {
                background-color: #E5E5E5;
                color: #303030;
                border: 1px solid #CCCCCC;
                border-radius: 4px;
                padding: 3px;
            }
            QToolButton:hover {
                background-color: #D0D0D0;
            }
            QToolButton:pressed {
                background-color: #C0C0C0;
            }
            QPushButton {
                background-color: #E5E5E5;
                color: #303030;
                border: 1px solid #CCCCCC;
                border-radius: 4px;
                padding: 5px 10px;
            }
            QPushButton:hover {
                background-color: #D0D0D0;
            }
            QPushButton:pressed {
                background-color: #C0C0C0;
            }
            QLineEdit, QTextEdit, QPlainTextEdit {
                background-color: #FFFFFF;
                color: #303030;
                border: 1px solid #CCCCCC;
                border-radius: 3px;
                padding: 3px;
            }
            QComboBox {
                background-color: #FFFFFF;
                color: #303030;
                border: 1px solid #CCCCCC;
                border-radius: 3px;
                padding: 2px 10px 2px 5px;
            }
            QSpinBox, QDoubleSpinBox {
                background-color: #FFFFFF;
                color: #303030;
                border: 1px solid #CCCCCC;
                border-radius: 3px;
                padding: 2px 3px;
            }
            QScrollBar {
                background-color: #F5F5F5;
                border: 1px solid #CCCCCC;
            }
            QScrollBar::handle {
                background-color: #CCCCCC;
                border-radius: 3px;
            }
            QScrollBar::handle:hover {
                background-color: #BBBBBB;
            }
        """
    else:  # Dark theme (default)
        return """
            QMainWindow {
                background-color: #2D2D2D;
                color: #EEEEEE;
            }
            QWidget {
                background-color: #303030;
                color: #EEEEEE;
            }
            QMenu {
                background-color: #3A3A3A;
                color: #EEEEEE;
                border: 1px solid #555555;
            }
            QMenuBar {
                background-color: #2A2A2A;
                color: #EEEEEE;
            }
            QToolBar {
                background-color: #2A2A2A;
                color: #EEEEEE;
                spacing: 3px;
                border: 0px;
            }
            QStatusBar {
                background-color: #2A2A2A;
                color: #EEEEEE;
            }
            QTabWidget::pane {
                border: 1px solid #555555;
            }
            QTabBar::tab {
                background-color: #404040;
                color: #BBBBBB;
                border: 1px solid #555555;
                padding: 5px 10px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: #303030;
                color: #EEEEEE;
                border-bottom-color: #303030;
            }
            QToolButton {
                background-color: #404040;
                color: #EEEEEE;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 3px;
            }
            QToolButton:hover {
                background-color: #4A4A4A;
            }
            QToolButton:pressed {
                background-color: #555555;
            }
            QPushButton {
                background-color: #404040;
                color: #EEEEEE;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 5px 10px;
            }
            QPushButton:hover {
                background-color: #4A4A4A;
            }
            QPushButton:pressed {
                background-color: #555555;
            }
            QLineEdit, QTextEdit, QPlainTextEdit {
                background-color: #404040;
                color: #EEEEEE;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 3px;
            }
            QComboBox {
                background-color: #404040;
                color: #EEEEEE;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 2px 10px 2px 5px;
            }
            QSpinBox, QDoubleSpinBox {
                background-color: #404040;
                color: #EEEEEE;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 2px 3px;
            }
            QScrollBar {
                background-color: #303030;
                border: 1px solid #555555;
            }
            QScrollBar::handle {
                background-color: #555555;
                border-radius: 3px;
            }
            QScrollBar::handle:hover {
                background-color: #666666;
            }
        """
