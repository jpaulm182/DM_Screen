#!/usr/bin/env python3
"""
Test script for combat resolution with memory leak detection

This script runs the combat resolver while monitoring for memory leaks.
"""

import sys
import logging
import gc
import os
import time
import traceback
from pathlib import Path

# Add debug environment variables
os.environ["PYTHONMALLOC"] = "debug"
os.environ["PYTHONFAULTHANDLER"] = "1"

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('test_with_leak_detection.log', 'w')
    ]
)
logger = logging.getLogger("test_with_leak_detection")

# Add the app directory to the Python path
app_dir = Path(__file__).parent.parent
sys.path.append(str(app_dir))

# Import memory leak detector
try:
    from tools.memory_leak_detector import MemoryLeakDetector
    logger.info("Memory leak detector imported successfully")
except ImportError as e:
    logger.error(f"Error importing memory leak detector: {e}")
    sys.exit(1)

# Force garbage collection
gc.collect()

# Import test combat module
try:
    from . import test_combat
    logger.info("Test combat module imported successfully")
except ImportError as e:
    logger.error(f"Error importing test combat module: {e}")
    sys.exit(1)

def main():
    """Main test function with leak detection"""
    logger.info("Starting combat resolution test with leak detection")
    
    try:
        # Start memory leak detector
        detector = MemoryLeakDetector(interval=1)
        detector.start()
        logger.info("Memory leak detector started")
        
        # Run the combat test
        logger.info("Running combat test")
        test_combat.main()
        
        # Stop memory leak detector and generate report
        logger.info("Combat test completed, stopping memory leak detector")
        detector.stop()
        
        logger.info("Test completed successfully")
        
    except Exception as e:
        logger.error(f"Error in test: {e}")
        logger.error(traceback.format_exc())
        
        # Make sure to stop the detector
        try:
            detector.stop()
        except:
            pass
            
if __name__ == "__main__":
    main() 