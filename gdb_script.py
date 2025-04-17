"""
GDB Python script for analyzing segmentation faults in the DM Screen application.

To use this script, run:
gdb -ex "py execfile('gdb_script.py')" --args python main.py
"""

try:
    import gdb
except ImportError:
    # Mock GDB for development/testing outside of GDB
    class MockGDB:
        class Command:
            def __init__(self, *args, **kwargs): pass
    gdb = MockGDB()
    print("Running in mock GDB mode")

class SegfaultHandler(gdb.Command):
    """Command to set up segfault analysis"""
    
    def __init__(self):
        super(SegfaultHandler, self).__init__("analyze-segfault", gdb.COMMAND_USER)
    
    def invoke(self, arg, from_tty):
        print("Setting up segfault analysis...")
        
        # Set up handlers for various signals
        gdb.execute("handle SIGSEGV stop print")
        gdb.execute("handle SIGABRT stop print")
        
        # Set breakpoint on malloc_consolidate
        gdb.execute("break malloc_consolidate")
        
        # Set a catchpoint for exceptions
        gdb.execute("catch throw")
        
        # Command to run when a segfault occurs
        gdb.execute("""
        define hook-stop
          if $_isvoid($_exitsignal) == 0 && $_exitsignal != 0
            printf "Program received signal %d\\n", $_exitsignal
            bt full
            info threads
            thread apply all bt full
            print sizeof(PyThreadState)
            print sizeof(PyObject)
            py-bt
          end
        end
        """)
        
        print("Segfault analysis setup complete. Run the program with 'run'.")

SegfaultHandler()

class PythonMemoryInfo(gdb.Command):
    """Command to display Python memory info"""
    
    def __init__(self):
        super(PythonMemoryInfo, self).__init__("py-mem-info", gdb.COMMAND_USER)
    
    def invoke(self, arg, from_tty):
        print("Python Memory Information:")
        gdb.execute("print PyRuntime")
        gdb.execute("info threads")
        print("\nActive Python threads:")
        gdb.execute("thread apply all py-bt")

PythonMemoryInfo()

print("GDB Python script loaded. Available commands:")
print("  analyze-segfault - Set up segfault analysis")
print("  py-mem-info - Display Python memory information")
print("Run the program with 'run'")
print("To generate a crash report when segfault occurs, use:")
print("  run > crash_report.txt 2>&1")
print("  bt full >> crash_report.txt")
print("  thread apply all bt full >> crash_report.txt")
print("  py-bt >> crash_report.txt") 