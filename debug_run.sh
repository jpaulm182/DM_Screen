#!/bin/bash
# Debug script to run DM Screen with GDB for crash analysis

echo "DM Screen Debug Run Script"
echo "-------------------------"
echo "This script will run the application with GDB for crash analysis."
echo ""

# Make sure gdb is installed
if ! command -v gdb &> /dev/null; then
    echo "Error: gdb is not installed."
    echo "Please install gdb with your package manager, e.g.:"
    echo "  sudo pacman -S gdb  # Arch Linux"
    echo "  sudo apt install gdb  # Debian/Ubuntu"
    exit 1
fi

# Make sure Python debug symbols are available
if ! python -c "import sys; print('Python debug symbols are available' if hasattr(sys, 'gettotalrefcount') else 'Python debug symbols are NOT available')" | grep -q "are available"; then
    echo "Warning: Python debug symbols may not be available."
    echo "This may limit the debugging information."
    echo "Consider installing Python debug symbols package if available."
    echo ""
fi

# Create logs directory
mkdir -p logs

# Current timestamp for log files
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="logs/debug_${TIMESTAMP}.log"
CRASH_FILE="logs/crash_${TIMESTAMP}.txt"

# Set environment variables for debugging
export PYTHONMALLOC=debug
export PYTHONFAULTHANDLER=1
export PYTHONVERBOSE=1

echo "Starting debug session..."
echo "Log file: $LOG_FILE"
echo "Crash report: $CRASH_FILE"
echo ""
echo "Running with GDB..."

# Run with GDB
gdb -ex "set confirm off" \
    -ex "set pagination off" \
    -ex "py execfile('gdb_script.py')" \
    -ex "analyze-segfault" \
    -ex "run" \
    -ex "bt full" \
    -ex "thread apply all bt full" \
    -ex "py-bt" \
    -ex "py-mem-info" \
    -ex "quit" \
    --args python main.py > "$LOG_FILE" 2>&1

# Check if the application crashed
if grep -q "Program received signal" "$LOG_FILE"; then
    echo "The application crashed. Creating crash report..."
    
    # Extract crash information
    grep -A 100 "Program received signal" "$LOG_FILE" > "$CRASH_FILE"
    echo "" >> "$CRASH_FILE"
    echo "=================================" >> "$CRASH_FILE"
    echo "Python Backtrace:" >> "$CRASH_FILE"
    grep -A 50 "Python stack trace:" "$LOG_FILE" >> "$CRASH_FILE"
    
    echo "Crash report created: $CRASH_FILE"
    echo "Please share this file with the developers."
else
    echo "The application exited normally."
fi

echo ""
echo "Debug session complete."
echo "Full log file: $LOG_FILE" 