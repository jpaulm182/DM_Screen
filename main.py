#!/usr/bin/env python3

"""
Main entry point for the DM Screen application

This desktop application serves as a dynamic DM screen for D&D 5e with
reference materials, generators, and campaign management tools.
"""

import sys
from pathlib import Path

# Add the app directory to the Python path
app_dir = Path(__file__).parent
sys.path.append(str(app_dir))

from PySide6.QtWidgets import QApplication
from app.core.app_state import AppState
from app.ui.main_window import MainWindow

def main():
    """Main application entry point"""
    # Create the Qt Application
    app = QApplication(sys.argv)
    app.setApplicationName("DM Screen")
    app.setApplicationVersion("0.5.0")
    
    # Initialize application state~
    app_state = AppState()
    
    # Create and show the main window
    window = MainWindow(app_state)
    window.show()
    
    # Set up cleanup on exit
    app.aboutToQuit.connect(app_state.close)
    
    # Start the event loop
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
