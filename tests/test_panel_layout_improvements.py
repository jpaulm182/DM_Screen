#!/usr/bin/env python3

"""
Test script for panel layout improvements

This script opens multiple panels and tests the improved layout system.
"""

import sys
import time
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QTimer

def main():
    """Run the test script"""
    # Create application instance
    app = QApplication(sys.argv)
    
    # Import after QApplication is created
    from app.core.app_state import AppState
    from app.ui.main_window import MainWindow
    
    # Initialize app state
    app_state = AppState()
    
    # Create main window
    window = MainWindow(app_state)
    window.setGeometry(100, 100, 1200, 900)  # Set a reasonable size
    window.show()
    
    def open_panels():
        """Open multiple panels to test layout organization"""
        panel_manager = window.panel_manager
        
        # First set of panels - should organize well
        print("Opening first set of panels...")
        panels_to_open = ["combat_tracker", "dice_roller", "conditions"]
        
        for panel_id in panels_to_open:
            panel_manager.toggle_panel(panel_id)
            
        # Give UI time to update
        QTimer.singleShot(1000, organize_panels)
    
    def organize_panels():
        """Organize panels and then open more panels"""
        print("Organizing panels...")
        window.panel_manager.smart_organize_panels()
        
        # Give UI time to update
        QTimer.singleShot(1000, open_more_panels)
    
    def open_more_panels():
        """Open additional panels to test tabbing behavior"""
        print("Opening more panels to test tabbing...")
        panels_to_open = ["monster", "spell_reference", "session_notes", "weather"]
        
        for panel_id in panels_to_open:
            window.panel_manager.toggle_panel(panel_id)
            
        # Give UI time to update
        QTimer.singleShot(1000, final_organize)
    
    def final_organize():
        """Final organization and display results"""
        print("Final organization...")
        window.panel_manager.smart_organize_panels()
        
        # Show message with test instructions
        QTimer.singleShot(500, show_instructions)
    
    def show_instructions():
        """Show test instructions"""
        msg = QMessageBox()
        msg.setWindowTitle("Panel Layout Test")
        msg.setText("Panel Layout Improvements Test")
        msg.setInformativeText(
            "The following improvements have been implemented:\n\n"
            "1. Colored borders to distinguish panel categories\n"
            "2. Automatic tabbing to prevent overcrowding\n"
            "3. Smart panel sizing based on available space\n"
            "4. Better overlap prevention\n\n"
            "Verify that panels are clearly distinguishable by their borders, and that "
            "panels are automatically tabbed to prevent overcrowding. Panels should not "
            "overlap or become too small to use effectively."
        )
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec()
    
    # Schedule tests to start after the window is shown
    QTimer.singleShot(500, open_panels)
    
    # Run the application
    return app.exec()

if __name__ == "__main__":
    main() 