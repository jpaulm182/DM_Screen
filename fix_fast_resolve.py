#!/usr/bin/env python3

"""
Fix script for the combat resolver's fast resolve functionality.

This script applies the fixes needed to make the fast resolve functionality work properly:
1. Adds the missing _process_recharge_abilities method
2. Fixes error handling in the _process_turn method
3. Updates the _run_resolution_thread method to properly handle goto_post_turn_logic
"""

import logging
import os
import sys

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("FixFastResolve")

def apply_fixes():
    """Apply fixes to the combat resolver code"""
    
    # Main file path
    combat_resolver_path = os.path.join("app", "core", "combat_resolver.py")
    
    # Verify the file exists
    if not os.path.exists(combat_resolver_path):
        logger.error(f"Combat resolver file not found at {combat_resolver_path}")
        return False
    
    logger.info(f"Found combat resolver at {combat_resolver_path}")
    
    # Read the file
    with open(combat_resolver_path, 'r') as f:
        content = f.read()
    
    # 1. Check if _process_recharge_abilities is already defined
    if "_process_recharge_abilities" not in content:
        logger.info("Adding missing _process_recharge_abilities method")
        
        # Find the end of the class definition
        class_end_marker = "# Ensure the final class definition is accessible"
        
        if class_end_marker not in content:
            logger.error("Could not find class end marker - aborting")
            return False
            
        # Define the method to add
        recharge_method = """    def _process_recharge_abilities(self, combatant, dice_roller):
        \"\"\"Process recharge abilities for a monster at the start of its turn.
        
        Args:
            combatant: The combatant dictionary to process
            dice_roller: Function to roll dice
            
        This method updates the combatant dictionary directly, modifying the 
        "recharge_abilities" field based on dice rolls.
        \"\"\"
        if not combatant or combatant.get("type", "").lower() != "monster":
            return  # Only monsters have recharge abilities
            
        if "recharge_abilities" not in combatant:
            combatant["recharge_abilities"] = {}  # Initialize if not present
            return
            
        # Process each recharge ability
        for ability_name, ability_data in combatant.get("recharge_abilities", {}).items():
            # Skip already available abilities
            if ability_data.get("available", True):
                continue
                
            # Get recharge condition (default: 5-6 on d6)
            recharge_on = ability_data.get("recharge_on", [5, 6])
            dice_expr = ability_data.get("recharge_dice", "1d6")
            
            # Roll for recharge
            roll_value = dice_roller(dice_expr)
            logging.info(f"[CombatResolver] Recharge roll for {ability_name}: {roll_value} (recharges on {recharge_on})")
            
            # Check if ability recharges
            if isinstance(recharge_on, list) and roll_value in recharge_on:
                combatant["recharge_abilities"][ability_name]["available"] = True
                logging.info(f"[CombatResolver] {ability_name} recharged!")
            elif isinstance(recharge_on, int) and roll_value >= recharge_on:
                combatant["recharge_abilities"][ability_name]["available"] = True
                logging.info(f"[CombatResolver] {ability_name} recharged!")
            else:
                logging.info(f"[CombatResolver] {ability_name} failed to recharge.")
                
        logging.debug(f"[CombatResolver] Recharge abilities after processing: {combatant.get('recharge_abilities')}")
        return

"""
        
        # Insert the method before the class end marker
        updated_content = content.replace(class_end_marker, recharge_method + "\n" + class_end_marker)
    else:
        logger.info("Method _process_recharge_abilities already exists, no need to add it")
        updated_content = content
    
    # 2. Add error handling and debugging to the _run_resolution_thread method
    # This ensures goto_post_turn_logic is always initialized
    if "goto_post_turn_logic = False  # Initialize this variable to prevent NameError" not in updated_content:
        logger.info("Adding initialization for goto_post_turn_logic")
        
        # Find the section where goto_post_turn_logic is used
        target_code = "                    # Skip turn if combatant is incapacitated (Dead monster, or Unconscious/Stable/Dead PC)\n                    status = combatant.get(\"status\", \"\").lower()\n                    ctype = combatant.get(\"type\", \"\").lower()\n                    hp = combatant.get(\"hp\", 0)"
        
        replacement_code = "                    # Skip turn if combatant is incapacitated (Dead monster, or Unconscious/Stable/Dead PC)\n                    status = combatant.get(\"status\", \"\").lower()\n                    ctype = combatant.get(\"type\", \"\").lower()\n                    hp = combatant.get(\"hp\", 0)\n\n                    skip_turn = False\n                    skip_reason = \"\"\n                    goto_post_turn_logic = False  # Initialize this variable to prevent NameError"
        
        updated_content = updated_content.replace(target_code, replacement_code)
    
    # 3. Improve turn_result null check
    if "turn_summary = f\"Round {round_num}, {combatant_name}'s turn: {turn_result.get('narrative', 'No action.') if turn_result else 'No result available.'}\"\n" not in updated_content:
        logger.info("Adding null check for turn_result")
        
        # Find the line to update
        target_code = "                            turn_summary = f\"Round {round_num}, {combatant_name}'s turn: {turn_result.get('narrative', 'No action.')}\""
        
        # Replacement with null check
        replacement_code = "                            turn_summary = f\"Round {round_num}, {combatant_name}'s turn: {turn_result.get('narrative', 'No action.') if turn_result else 'No result available.'}\""
        
        updated_content = updated_content.replace(target_code, replacement_code)
    
    # Write the updated content back to the file
    with open(combat_resolver_path, 'w') as f:
        f.write(updated_content)
    
    logger.info("Combat resolver fixes applied successfully")
    return True

def main():
    """Main function"""
    try:
        logger.info("Applying fixes to combat resolver...")
        success = apply_fixes()
        
        if success:
            logger.info("All fixes applied successfully")
            return 0
        else:
            logger.error("Failed to apply some fixes")
            return 1
            
    except Exception as e:
        logger.error(f"Error applying fixes: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 