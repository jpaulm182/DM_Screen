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

# Configure recursion depth limit to avoid maximum recursion depth errors
sys.setrecursionlimit(3000)  # Increase from default 1000

# Add the app directory to the Python path
app_dir = Path(__file__).parent
sys.path.append(str(app_dir))

# Configure memory usage
gc.set_threshold(100, 5, 2)  # More aggressive garbage collection

from PySide6.QtWidgets import QApplication
from app.core.app_state import AppState
from app.core.patched_app_state import apply_patches
from app.ui.main_window import MainWindow

def main():
    """Main application entry point"""
    # Set up logging
    log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG) # Set root logger level
    
    # Stream Handler (console) - Temporarily disabled for testing file logging
    # stream_handler = logging.StreamHandler()
    # stream_handler.setFormatter(log_formatter)
    # # Keep console at INFO level to avoid excessive noise
    # stream_handler.setLevel(logging.INFO) 
    # root_logger.addHandler(stream_handler)
    
    # File Handler (debug.log)
    log_file_path = app_dir / 'debug.log'
    # Change mode to 'a' (append) to keep logs across runs
    file_handler = logging.FileHandler(log_file_path, 'a') 
    file_handler.setFormatter(log_formatter)
    file_handler.setLevel(logging.DEBUG) # Ensure file handler captures DEBUG messages
    root_logger.addHandler(file_handler)

    logging.info("Starting DM Screen application")
    logging.debug(f"Logging DEBUG messages to: {log_file_path}") # Add a debug message to test file logging
    
    # Apply stability patches
    logging.info("Applying stability patches")
    try:
        # Import improved patched_app_state module
        from app.core.patched_app_state import apply_patches
        apply_patches()
        
        # Apply fixes for combat resolver
        logging.info("Applying combat resolver fixes")
        from fix_fast_resolve import apply_fixes
        apply_fixes()
        
        logging.info("Stability patches applied successfully")
    except Exception as e:
        logging.error(f"Error applying patches: {e}", exc_info=True)
        # Continue running even if patches fail - the application should still work
    
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
