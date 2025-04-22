#!/bin/bash
# Script to run the combat test with various debugging tools

echo "DM Screen Combat Test Runner"
echo "---------------------------"
echo ""

# Set up environment variables for testing
export PYTHONPATH="$(pwd):$PYTHONPATH"
export PYTHONMALLOC=debug
export PYTHONFAULTHANDLER=1

# Make test files executable
chmod +x tests/test_combat.py tests/test_with_leak_detection.py

# Current timestamp
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# Function to print separator
separator() {
  echo ""
  echo "========================================================"
  echo "$1"
  echo "========================================================"
  echo ""
}

# Function to ask for user choice
ask_for_choice() {
  echo "Select a test to run:"
  echo "1) Basic combat test"
  echo "2) Test with memory leak detection"
  echo "3) Run with valgrind"
  echo "4) Run with gdb"
  echo "5) Run all tests"
  echo "q) Quit"
  echo ""
  read -p "Enter your choice (1-5 or q): " choice
  echo ""
  
  case $choice in
    1) run_basic_test ;;
    2) run_leak_detection ;;
    3) run_valgrind ;;
    4) run_gdb ;;
    5) run_all_tests ;;
    q) exit 0 ;;
    *) echo "Invalid choice. Please try again."; ask_for_choice ;;
  esac
}

# Run basic test
run_basic_test() {
  separator "Running basic test"
  echo "Running test_combat.py normally..."
  python tests/test_combat.py
  echo "Test completed. See test_combat.log for details."
  
  # Go back to menu
  echo ""
  read -p "Press Enter to continue..."
  ask_for_choice
}

# Run with memory leak detection
run_leak_detection() {
  separator "Running with memory leak detection"
  echo "Running test_with_leak_detection.py..."
  python tests/test_with_leak_detection.py
  echo "Test completed. See test_with_leak_detection.log and memory_leak_report.txt for details."
  
  # Go back to menu
  echo ""
  read -p "Press Enter to continue..."
  ask_for_choice
}

# Run with valgrind
run_valgrind() {
  separator "Running with Valgrind"
  
  # Check if valgrind is installed
  if ! command -v valgrind &> /dev/null; then
    echo "Valgrind not found. Please install it first."
    echo "For example: sudo pacman -S valgrind  # Arch Linux"
    echo "             sudo apt install valgrind  # Debian/Ubuntu"
    
    # Go back to menu
    echo ""
    read -p "Press Enter to continue..."
    ask_for_choice
    return
  fi
  
  echo "This may take a while..."
  
  VALGRIND_LOG="logs/valgrind_${TIMESTAMP}.log"
  echo "Log file: $VALGRIND_LOG"
  
  valgrind --tool=memcheck \
           --leak-check=full \
           --track-origins=yes \
           --log-file="$VALGRIND_LOG" \
           python tests/test_combat.py
  
  echo "Valgrind analysis complete. Check log file for details."
  
  # Go back to menu
  echo ""
  read -p "Press Enter to continue..."
  ask_for_choice
}

# Run with gdb
run_gdb() {
  separator "Running with GDB"
  
  # Check if gdb is installed
  if ! command -v gdb &> /dev/null; then
    echo "GDB not found. Please install it first."
    echo "For example: sudo pacman -S gdb  # Arch Linux"
    echo "             sudo apt install gdb  # Debian/Ubuntu"
    
    # Go back to menu
    echo ""
    read -p "Press Enter to continue..."
    ask_for_choice
    return
  fi
  
  GDB_LOG="logs/gdb_${TIMESTAMP}.log"
  echo "Log file: $GDB_LOG"
  
  gdb -ex "set confirm off" \
      -ex "set pagination off" \
      -ex "run" \
      -ex "bt full" \
      -ex "thread apply all bt full" \
      -ex "quit" \
      --args python tests/test_combat.py > "$GDB_LOG" 2>&1
  
  echo "GDB run complete. Check log file for details."
  
  # Go back to menu
  echo ""
  read -p "Press Enter to continue..."
  ask_for_choice
}

# Run all tests
run_all_tests() {
  separator "Running all tests"
  
  # Basic test
  echo "1. Running basic test..."
  python tests/test_combat.py
  echo "Basic test completed."
  
  # Memory leak detection
  echo "2. Running memory leak detection test..."
  python tests/test_with_leak_detection.py
  echo "Memory leak detection test completed."
  
  # Valgrind
  if command -v valgrind &> /dev/null; then
    echo "3. Running valgrind test..."
    VALGRIND_LOG="logs/valgrind_${TIMESTAMP}.log"
    valgrind --tool=memcheck \
             --leak-check=full \
             --track-origins=yes \
             --log-file="$VALGRIND_LOG" \
             python tests/test_combat.py
    echo "Valgrind test completed."
  else
    echo "Valgrind not found. Skipping valgrind test."
  fi
  
  # GDB
  if command -v gdb &> /dev/null; then
    echo "4. Running GDB test..."
    GDB_LOG="logs/gdb_${TIMESTAMP}.log"
    gdb -ex "set confirm off" \
        -ex "set pagination off" \
        -ex "run" \
        -ex "bt full" \
        -ex "thread apply all bt full" \
        -ex "quit" \
        --args python tests/test_combat.py > "$GDB_LOG" 2>&1
    echo "GDB test completed."
  else
    echo "GDB not found. Skipping GDB test."
  fi
  
  separator "All tests completed"
  echo "Review the log files for debugging information."
  
  # Go back to menu
  echo ""
  read -p "Press Enter to continue..."
  ask_for_choice
}

# Show menu
ask_for_choice 