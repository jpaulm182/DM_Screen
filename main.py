#!/usr/bin/env python3

"""
Main entry point for the DM Screen application

This desktop application serves as a dynamic DM screen for D&D 5e with
reference materials, generators, and campaign management tools.
"""

import sys
import gc
import os
import logging
from pathlib import Path
import threading

# Force single-thread OpenAI API
os.environ["OPENAI_API_REQUEST_TIMEOUT"] = "60"
os.environ["PYTHONMALLOC"] = "debug"  # Enable debug malloc

# Configure thread limits
threading.stack_size(16 * 1024 * 1024)  # 16MB stack size

# Add the app directory to the Python path
app_dir = Path(__file__).parent
sys.path.append(str(app_dir))

from PySide6.QtWidgets import QApplication
from app.core.app_state import AppState
from app.core.patched_app_state import apply_patches
from app.ui.main_window import MainWindow

def main():
    """Main application entry point"""
    # Set up logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(app_dir / 'debug.log', 'w')
        ]
    )
    logging.info("Starting DM Screen application")
    
    # Apply stability patches
    logging.info("Applying stability patches")
    try:
        apply_patches()
        logging.info("Stability patches applied successfully")
    except Exception as e:
        logging.error(f"Error applying patches: {e}", exc_info=True)
    
    # Force garbage collection before starting
    gc.collect()
    
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
