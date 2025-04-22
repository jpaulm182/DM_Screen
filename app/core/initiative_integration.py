"""
Integration module for connecting the improved initiative system with the combat resolver.

This module demonstrates how to use the ImprovedInitiative class to enhance
the existing CombatResolver with proper D&D 5e initiative mechanics.
"""

from app.core.improved_initiative import ImprovedInitiative
import copy

def initialize_combat_with_improved_initiative(combat_state):
    """
    Initialize a combat state with improved initiative handling.
    
    Args:
        combat_state: Original combat state dictionary
        
    Returns:
        Enhanced combat state with improved initiative handling
    """
    # Make a deep copy to avoid modifying the original
    enhanced_state = copy.deepcopy(combat_state)
    
    # Get combatants from the state
    combatants = enhanced_state.get("combatants", [])
    
    # Apply initiative modifiers from character features
    combatants = ImprovedInitiative.apply_initiative_modifiers(combatants)
    
    # Determine surprise status for first round
    surprise_status = ImprovedInitiative.get_surprise_status(combatants)
    enhanced_state["surprise_status"] = surprise_status
    
    # Sort combatants by initiative using improved ordering
    initiative_order = ImprovedInitiative.sort_combatants_by_initiative(combatants)
    enhanced_state["initiative_order"] = initiative_order
    
    # Determine active combatants for the first round
    round_num = enhanced_state.get("round", 1)
    active_combatants = ImprovedInitiative.determine_active_combatants(
        combatants, round_num, surprise_status
    )
    enhanced_state["active_combatants"] = active_combatants
    
    # Initialize combat events list for tracking initiative changes
    enhanced_state["combat_events"] = []
    
    # Update combatants in the state
    enhanced_state["combatants"] = combatants
    
    return enhanced_state

def update_combat_state_for_next_round(combat_state):
    """
    Update the combat state for the next round, handling initiative changes.
    
    Args:
        combat_state: Current combat state dictionary
        
    Returns:
        Updated combat state for the next round
    """
    # Make a deep copy to avoid modifying the original
    updated_state = copy.deepcopy(combat_state)
    
    # Increment round counter
    updated_state["round"] = updated_state.get("round", 1) + 1
    round_num = updated_state["round"]
    
    # Get combatants and combat events
    combatants = updated_state.get("combatants", [])
    combat_events = updated_state.get("combat_events", [])
    
    # Get current initiative order or recalculate if not present
    current_order = updated_state.get("initiative_order")
    if not current_order:
        current_order = ImprovedInitiative.sort_combatants_by_initiative(combatants)
    
    # Apply any initiative order changes from events
    updated_order = ImprovedInitiative.update_initiative_order(
        combatants, current_order, combat_events
    )
    updated_state["initiative_order"] = updated_order
    
    # Determine active combatants for the new round
    surprise_status = updated_state.get("surprise_status", {})
    active_combatants = ImprovedInitiative.determine_active_combatants(
        combatants, round_num, surprise_status
    )
    updated_state["active_combatants"] = active_combatants
    
    # Clear combat events for the new round
    updated_state["combat_events"] = []
    
    # Reset any per-round abilities or statuses
    for combatant in combatants:
        # Reset reaction availability
        if "action_economy" in combatant:
            combatant["action_economy"]["reaction"] = True
        
        # Reset legendary actions used
        if combatant.get("legendary_actions", 0) > 0:
            combatant["legendary_actions_used"] = 0
            
        # Handle condition duration
        if "conditions" in combatant:
            conditions_to_remove = []
            for condition_name, condition_data in combatant["conditions"].items():
                # Decrement duration for conditions tracked by rounds
                if "duration" in condition_data:
                    condition_data["duration"] -= 1
                    # Remove expired conditions
                    if condition_data["duration"] <= 0:
                        conditions_to_remove.append(condition_name)
            
            # Remove expired conditions
            for condition_name in conditions_to_remove:
                del combatant["conditions"][condition_name]
    
    # Update combatants in the state
    updated_state["combatants"] = combatants
    
    return updated_state

def record_ready_action(combat_state, combatant_idx, trigger_condition, trigger_initiative):
    """
    Record a ready action event in the combat state.
    
    Args:
        combat_state: Current combat state dictionary
        combatant_idx: Index of combatant taking the Ready action
        trigger_condition: Description of the trigger condition
        trigger_initiative: Initiative count when the action should trigger
        
    Returns:
        Updated combat state with the ready action recorded
    """
    # Make a deep copy to avoid modifying the original
    updated_state = copy.deepcopy(combat_state)
    
    # Get combat events list
    combat_events = updated_state.get("combat_events", [])
    
    # Add ready action event
    ready_event = {
        "type": "ready",
        "combatant_idx": combatant_idx,
        "trigger_condition": trigger_condition,
        "trigger_initiative": trigger_initiative
    }
    combat_events.append(ready_event)
    
    # Update events in the state
    updated_state["combat_events"] = combat_events
    
    return updated_state

def trigger_held_action(combat_state, combatant_idx, current_turn_position):
    """
    Trigger a held/readied action for a combatant.
    
    Args:
        combat_state: Current combat state dictionary
        combatant_idx: Index of combatant triggering their readied action
        current_turn_position: Current position in the initiative order
        
    Returns:
        Updated combat state with the triggered action recorded
    """
    # Make a deep copy to avoid modifying the original
    updated_state = copy.deepcopy(combat_state)
    
    # Get combat events list
    combat_events = updated_state.get("combat_events", [])
    
    # Add held action triggered event
    trigger_event = {
        "type": "held_action_triggered",
        "combatant_idx": combatant_idx,
        "current_position": current_turn_position
    }
    combat_events.append(trigger_event)
    
    # Update events in the state
    updated_state["combat_events"] = combat_events
    
    return updated_state

def get_next_combatant(combat_state, current_idx=None):
    """
    Get the next combatant in the initiative order.
    
    Args:
        combat_state: Current combat state dictionary
        current_idx: Current combatant index, or None to get the first combatant
        
    Returns:
        Tuple of (next_combatant_idx, is_end_of_round)
    """
    # Get active combatants list
    active_combatants = combat_state.get("active_combatants", [])
    
    # If there are no active combatants, end of round
    if not active_combatants:
        return None, True
    
    # If current_idx is None, return the first combatant
    if current_idx is None:
        return active_combatants[0], False
    
    # Find the current combatant's position in the active combatants list
    try:
        current_position = active_combatants.index(current_idx)
    except ValueError:
        # Current combatant not in the active list, start from beginning
        return active_combatants[0], False
    
    # Determine if this is the last combatant in the initiative order
    if current_position >= len(active_combatants) - 1:
        # End of round
        return None, True
    else:
        # Return the next combatant
        return active_combatants[current_position + 1], False 