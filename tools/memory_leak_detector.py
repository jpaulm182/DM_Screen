#!/usr/bin/env python3
"""
Memory leak detection tool for DM Screen

This tool helps identify memory leaks by tracking object counts
and memory usage over time.
"""

import gc
import os
import sys
import logging
import threading
import time
from pathlib import Path

# Add parent directory to path
parent_dir = Path(__file__).parent.parent
sys.path.append(str(parent_dir))

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('memory_leak.log', 'w')
    ]
)
logger = logging.getLogger("memory_leak_detector")

class MemoryLeakDetector:
    """
    Tracks object counts and memory usage to detect memory leaks
    """
    
    def __init__(self, interval=5):
        """
        Initialize the memory leak detector
        
        Args:
            interval: Interval in seconds between memory checks
        """
        self.interval = interval
        self.running = False
        self.thread = None
        self.baseline = None
        self.snapshots = []
        
    def start(self):
        """Start the memory leak detector"""
        if self.running:
            logger.warning("Memory leak detector already running")
            return
            
        self.running = True
        self.thread = threading.Thread(target=self._monitor, daemon=True)
        self.thread.start()
        logger.info(f"Memory leak detector started (interval: {self.interval}s)")
        
        # Take initial baseline after a short delay
        time.sleep(1)
        self.baseline = self._take_snapshot("baseline")
        
    def stop(self):
        """Stop the memory leak detector"""
        if not self.running:
            logger.warning("Memory leak detector not running")
            return
            
        self.running = False
        if self.thread:
            self.thread.join(timeout=1)
        
        logger.info("Memory leak detector stopped")
        
        # Generate final report
        self.report()
        
    def _monitor(self):
        """Monitor memory usage at regular intervals"""
        iteration = 0
        
        while self.running:
            try:
                # Take snapshot with iteration number
                iteration += 1
                self._take_snapshot(f"iteration_{iteration}")
                
                # Sleep until next interval
                time.sleep(self.interval)
            except Exception as e:
                logger.error(f"Error in memory monitor: {e}")
                
    def _take_snapshot(self, label):
        """
        Take a snapshot of current memory state
        
        Args:
            label: Label for this snapshot
            
        Returns:
            Snapshot data
        """
        # Force garbage collection
        gc.collect()
        
        try:
            # Get memory usage
            import psutil
            process = psutil.Process()
            memory_info = process.memory_info()
            
            # Count objects by type
            type_counts = {}
            for obj in gc.get_objects():
                obj_type = type(obj).__name__
                type_counts[obj_type] = type_counts.get(obj_type, 0) + 1
                
            # Create snapshot
            snapshot = {
                "label": label,
                "timestamp": time.time(),
                "memory": {
                    "rss": memory_info.rss,
                    "vms": memory_info.vms,
                },
                "type_counts": type_counts,
                "gc_counts": gc.get_count()
            }
            
            # Add thread count
            snapshot["threads"] = threading.active_count()
            
            # Store snapshot
            self.snapshots.append(snapshot)
            
            # Log basic info
            logger.info(f"Snapshot {label}: RSS={memory_info.rss/1024/1024:.2f}MB, Threads={snapshot['threads']}")
            
            return snapshot
        except ImportError:
            logger.error("psutil not available - limited memory tracking")
            
            # Create basic snapshot without psutil
            snapshot = {
                "label": label,
                "timestamp": time.time(),
                "memory": {
                    "rss": 0,
                    "vms": 0,
                },
                "type_counts": {},
                "gc_counts": gc.get_count()
            }
            
            # Add thread count
            snapshot["threads"] = threading.active_count()
            
            # Store snapshot
            self.snapshots.append(snapshot)
            
            return snapshot
            
    def report(self):
        """Generate a memory leak report"""
        if not self.snapshots:
            logger.warning("No snapshots available for report")
            return
            
        # Get last snapshot
        last = self.snapshots[-1]
        
        if not self.baseline:
            logger.warning("No baseline snapshot for comparison")
            return
            
        # Compare with baseline
        baseline = self.baseline
        
        # Calculate time elapsed
        elapsed = last["timestamp"] - baseline["timestamp"]
        
        logger.info(f"Memory Leak Report (elapsed: {elapsed:.2f}s)")
        logger.info("=======================================")
        
        # Memory change
        if "rss" in baseline["memory"] and baseline["memory"]["rss"] > 0:
            rss_change = last["memory"]["rss"] - baseline["memory"]["rss"]
            rss_change_mb = rss_change / 1024 / 1024
            rss_change_pct = (rss_change / baseline["memory"]["rss"]) * 100
            
            logger.info(f"RSS Memory: {baseline['memory']['rss']/1024/1024:.2f}MB -> {last['memory']['rss']/1024/1024:.2f}MB")
            logger.info(f"Change: {rss_change_mb:+.2f}MB ({rss_change_pct:+.2f}%)")
            
            if rss_change_pct > 10:
                logger.warning(f"Potential memory leak: RSS increased by {rss_change_pct:.2f}%")
        
        # Thread count change
        thread_change = last["threads"] - baseline["threads"]
        logger.info(f"Threads: {baseline['threads']} -> {last['threads']} ({thread_change:+d})")
        
        if thread_change > 0:
            logger.warning(f"Potential thread leak: {thread_change} new threads")
        
        # Type count changes
        logger.info("Object count changes:")
        
        for obj_type, last_count in sorted(last["type_counts"].items()):
            baseline_count = baseline["type_counts"].get(obj_type, 0)
            change = last_count - baseline_count
            
            # Only show significant changes
            if change > 10 or (change > 0 and baseline_count == 0):
                logger.info(f"  {obj_type}: {baseline_count} -> {last_count} ({change:+d})")
                
                if obj_type in ("dict", "list", "tuple", "set") and change > 1000:
                    logger.warning(f"Potential leak of {obj_type} objects: {change:+d}")
        
        # Generate detailed report file
        try:
            with open("memory_leak_report.txt", "w") as f:
                f.write("MEMORY LEAK DETECTOR REPORT\n")
                f.write("==========================\n\n")
                
                f.write(f"Duration: {elapsed:.2f} seconds\n")
                f.write(f"Snapshots: {len(self.snapshots)}\n\n")
                
                f.write("MEMORY USAGE\n")
                f.write("-----------\n")
                for i, snapshot in enumerate(self.snapshots):
                    if i == 0:
                        f.write(f"Baseline ({snapshot['label']}): RSS={snapshot['memory']['rss']/1024/1024:.2f}MB, Threads={snapshot['threads']}\n")
                    else:
                        prev = self.snapshots[i-1]
                        rss_change = snapshot['memory']['rss'] - prev['memory']['rss']
                        thread_change = snapshot['threads'] - prev['threads']
                        f.write(f"Snapshot {i} ({snapshot['label']}): RSS={snapshot['memory']['rss']/1024/1024:.2f}MB ({rss_change/1024/1024:+.2f}MB), " + 
                                f"Threads={snapshot['threads']} ({thread_change:+d})\n")
                
                f.write("\nOBJECT COUNTS\n")
                f.write("-------------\n")
                
                # Get all types
                all_types = set()
                for snapshot in self.snapshots:
                    all_types.update(snapshot["type_counts"].keys())
                
                # Track each type
                for obj_type in sorted(all_types):
                    f.write(f"{obj_type}:\n")
                    for i, snapshot in enumerate(self.snapshots):
                        count = snapshot["type_counts"].get(obj_type, 0)
                        if i == 0:
                            f.write(f"  Baseline ({snapshot['label']}): {count}\n")
                        else:
                            prev = self.snapshots[i-1]
                            prev_count = prev["type_counts"].get(obj_type, 0)
                            change = count - prev_count
                            f.write(f"  Snapshot {i} ({snapshot['label']}): {count} ({change:+d})\n")
                    f.write("\n")
                
            logger.info(f"Detailed report written to memory_leak_report.txt")
        except Exception as e:
            logger.error(f"Error writing detailed report: {e}")

def main():
    """Main function for standalone usage"""
    print("Memory Leak Detector")
    print("===================")
    print("This tool will monitor memory usage and object counts")
    print("to help identify memory leaks in the DM Screen application.")
    print("")
    
    # Check if psutil is available
    try:
        import psutil
        print("psutil is available - full memory tracking enabled")
    except ImportError:
        print("WARNING: psutil not available - limited memory tracking")
        print("Install psutil for better memory tracking:")
        print("  pip install psutil")
    
    # Create detector
    detector = MemoryLeakDetector(interval=2)
    
    try:
        # Start monitoring
        print("Starting memory monitoring (press Ctrl+C to stop)...")
        detector.start()
        
        # Wait for Ctrl+C
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping memory monitoring...")
    finally:
        # Stop and generate report
        detector.stop()
        print("Memory monitoring stopped. See memory_leak.log and memory_leak_report.txt for details.")

if __name__ == "__main__":
    main() 