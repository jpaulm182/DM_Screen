#!/usr/bin/env python3

"""
Test script to verify panel accessibility fixes

This script runs the application and automatically opens different panels
to verify that panel selection works through both menu and toolbar.
"""

import sys
import time
from pathlib import Path
from PySide6.QtWidgets import QApplication, QToolBar
from PySide6.QtCore import QTimer
from PySide6.QtCore import Qt

# Add the app directory to the Python path
app_dir = Path(__file__).parent.parent
sys.path.append(str(app_dir))

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
    window.show()
    
    # Function to test panel access through menu
    def test_menu_panel_access():
        print("Testing panel access through menus...")
        
        # Access panels menu
        panels_menu = None
        for action in window.menuBar().actions():
            if action.text() == "&Panels":
                panels_menu = action.menu()
                break
        
        if not panels_menu:
            print("Error: Panels menu not found!")
            return False
        
        # Access combat menu
        combat_menu = None
        for action in panels_menu.actions():
            if action.text() == "&Combat Tools":
                combat_menu = action.menu()
                break
        
        if not combat_menu:
            print("Error: Combat Tools menu not found!")
            return False
        
        # Try to open combat tracker
        for action in combat_menu.actions():
            if action.text() == "Combat Tracker":
                action.trigger()
                print("Opened Combat Tracker from menu")
                return True
        
        print("Error: Combat Tracker action not found!")
        return False
    
    # Function to test panel access through toolbar
    def test_toolbar_panel_access():
        print("Testing panel access through toolbar...")
        
        # Find toolbar
        toolbar = window.findChild(QToolBar, "MainToolbar")
        if not toolbar:
            print("Error: Main toolbar not found!")
            return False
        
        # Find and click the dice roller button
        for action in toolbar.actions():
            if action.text() == "Dice Roller":
                action.trigger()
                print("Opened Dice Roller from toolbar")
                return True
        
        print("Error: Dice Roller button not found in toolbar!")
        return False
    
    # Schedule tests
    def run_tests():
        print("Running panel accessibility tests...")
        
        # Run menu test
        menu_result = test_menu_panel_access()
        
        # Wait a moment
        QTimer.singleShot(500, lambda: None)
        
        # Run toolbar test
        toolbar_result = test_toolbar_panel_access()
        
        # Print results
        print("\nTest Results:")
        print(f"Menu Panel Access: {'PASSED' if menu_result else 'FAILED'}")
        print(f"Toolbar Panel Access: {'PASSED' if toolbar_result else 'FAILED'}")
        
        # Keep window open for viewing
        print("\nTests complete. Close the window to exit.")
    
    # Schedule test execution
    QTimer.singleShot(1000, run_tests)
    
    # Run the application
    sys.exit(app.exec())

if __name__ == "__main__":
    main() 