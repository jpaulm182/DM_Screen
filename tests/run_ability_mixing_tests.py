#!/usr/bin/env python
"""
Run all ability mixing tests to verify the solution.

This script runs both unit tests for the validator and integration tests 
for the combat resolver to ensure ability mixing is properly prevented.
"""

import os
import sys
import unittest
import logging

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Set up logging to file for debugging
log_file = os.path.join(os.path.dirname(__file__), "ability_mixing_tests.log")
logging.basicConfig(
    filename=log_file,
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def run_tests():
    """Run all tests related to ability mixing."""
    print("Running ability mixing tests...")
    
    # Create test suite
    test_suite = unittest.TestSuite()
    
    # Add unit tests for the validator
    from core.test_monster_ability_validator import TestMonsterAbilityValidator
    validator_tests = unittest.TestLoader().loadTestsFromTestCase(TestMonsterAbilityValidator)
    test_suite.addTest(validator_tests)
    
    # Add integration tests for combat
    from core.test_combat_ability_mixing import TestCombatAbilityMixing
    combat_tests = unittest.TestLoader().loadTestsFromTestCase(TestCombatAbilityMixing)
    test_suite.addTest(combat_tests)
    
    # Run the tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # Print summary
    print("\nTest Summary:")
    print(f"Ran {result.testsRun} tests")
    
    if result.wasSuccessful():
        print("\033[92mAll tests passed! Ability mixing prevention is working correctly.\033[0m")
        return 0
    else:
        print(f"\033[91mFailures: {len(result.failures)}, Errors: {len(result.errors)}\033[0m")
        return 1

def verify_production_files():
    """Verify that all required files are in place for the solution."""
    print("\nVerifying required files...")
    
    required_files = [
        "app/core/utils/monster_ability_validator.py",
        "app/core/combat_resolver_patch.py"
    ]
    
    all_present = True
    for filepath in required_files:
        full_path = os.path.join(os.path.dirname(__file__), "..", filepath)
        if os.path.exists(full_path):
            print(f"✅ {filepath} - Present")
        else:
            print(f"❌ {filepath} - Missing")
            all_present = False
    
    if all_present:
        print("\033[92mAll required files are present!\033[0m")
    else:
        print("\033[91mSome required files are missing! Solution may not work correctly.\033[0m")
    
    return all_present

if __name__ == "__main__":
    # Verify files
    files_ok = verify_production_files()
    
    # Run tests
    test_result = run_tests()
    
    # Exit with status code
    sys.exit(0 if files_ok and test_result == 0 else 1) 