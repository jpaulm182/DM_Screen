"""
Improved initiative handling for the D&D 5e combat resolver.

This module enhances the initiative system to properly handle:
1. Initiative tie-breaking using DEX scores
2. Features that modify initiative order
3. Support for "Improved Initiative" and similar abilities
4. Reactions that can change initiative order
"""

class ImprovedInitiative:
    """
    A class to handle improved initiative mechanics for D&D 5e combat.
    """
    
    @staticmethod
    def sort_combatants_by_initiative(combatants):
        """
        Sort combatants by initiative with proper tie-breaking rules.
        
        Args:
            combatants: List of combatant dictionaries
            
        Returns:
            List of indices in sorted initiative order
        """
        # Create a list of indices
        indices = list(range(len(combatants)))
        
        # Sort by multiple criteria:
        # 1. Initiative (higher goes first)
        # 2. Dexterity score (higher goes first)
        # 3. Initiative advantage (higher goes first)
        sorted_indices = sorted(
            indices,
            key=lambda i: (
                # Primary sort by initiative (descending)
                -int(combatants[i].get("initiative", 0)),
                # Tie-breaker 1: Dexterity (descending)
                -int(combatants[i].get("dexterity", 0)),
                # Tie-breaker 2: Initiative advantage from features (descending)
                -int(combatants[i].get("initiative_advantage", 0))
            )
        )
        
        return sorted_indices
        
    @staticmethod
    def get_surprise_status(combatants):
        """
        Determine which combatants are surprised for the first round.
        
        Args:
            combatants: List of combatant dictionaries
            
        Returns:
            Dictionary mapping combatant indices to their surprise status (True/False)
        """
        surprise_status = {}
        
        for i, combatant in enumerate(combatants):
            # A combatant is surprised if they have the surprised flag
            is_surprised = combatant.get("surprised", False)
            
            # Alert feat prevents surprise
            if combatant.get("has_alert_feat", False):
                is_surprised = False
                
            surprise_status[i] = is_surprised
            
        return surprise_status
        
    @staticmethod
    def apply_initiative_modifiers(combatants):
        """
        Apply initiative modifiers from features and abilities.
        
        Args:
            combatants: List of combatant dictionaries
            
        Returns:
            List of combatants with modified initiative values
        """
        for combatant in combatants:
            base_initiative = int(combatant.get("initiative", 0))
            
            # Apply modifiers
            
            # Alert feat: +5 to initiative
            if combatant.get("has_alert_feat", False):
                base_initiative += 5
                
            # Jack of All Trades (Bard): Add half proficiency to initiative
            if combatant.get("has_jack_of_all_trades", False):
                proficiency = int(combatant.get("proficiency_bonus", 2))
                base_initiative += proficiency // 2
                
            # Remarkable Athlete (Champion Fighter): Add half proficiency to initiative
            if combatant.get("has_remarkable_athlete", False):
                proficiency = int(combatant.get("proficiency_bonus", 2))
                base_initiative += proficiency // 2
                
            # Advantage on initiative rolls (various features like Gift of Alacrity)
            if combatant.get("has_initiative_advantage", False):
                # This is just a flag for the dice roller, but we can mark it for tie-breaking
                combatant["initiative_advantage"] = 1
                
            # Update the initiative value
            combatant["initiative"] = base_initiative
            
        return combatants
    
    @staticmethod
    def determine_active_combatants(combatants, round_num, surprise_status=None):
        """
        Determine which combatants can act in the current round, accounting for surprise.
        
        Args:
            combatants: List of combatant dictionaries
            round_num: Current round number
            surprise_status: Dictionary mapping combatant indices to surprise status
            
        Returns:
            List of indices of combatants who can act this round
        """
        # Get all combatants sorted by initiative
        all_combatants = ImprovedInitiative.sort_combatants_by_initiative(combatants)
        
        # If no surprise or not first round, everyone who's alive can act
        if round_num > 1 or surprise_status is None:
            # Filter out dead or invalid combatants
            active_combatants = [
                idx for idx in all_combatants 
                if (
                    # Monster is alive
                    (combatants[idx].get("type", "").lower() == "monster" and 
                     combatants[idx].get("hp", 0) > 0 and 
                     combatants[idx].get("status", "").lower() != "dead") 
                    or 
                    # Character is alive or unconscious/stable (for death saves)
                    (combatants[idx].get("type", "").lower() != "monster" and 
                     (combatants[idx].get("hp", 0) > 0 or 
                      combatants[idx].get("status", "").lower() in ["unconscious", "stable"]))
                )
            ]
            return active_combatants
        
        # First round with surprise - filter out surprised combatants
        active_combatants = [
            idx for idx in all_combatants 
            if not surprise_status.get(idx, False) and  # Not surprised
            (
                # Monster is alive
                (combatants[idx].get("type", "").lower() == "monster" and 
                 combatants[idx].get("hp", 0) > 0 and 
                 combatants[idx].get("status", "").lower() != "dead") 
                or 
                # Character is alive or unconscious/stable (for death saves)
                (combatants[idx].get("type", "").lower() != "monster" and 
                 (combatants[idx].get("hp", 0) > 0 or 
                  combatants[idx].get("status", "").lower() in ["unconscious", "stable"]))
            )
        ]
        
        return active_combatants
    
    @staticmethod
    def update_initiative_order(combatants, current_order, events):
        """
        Update initiative order based on in-combat events.
        
        Args:
            combatants: List of combatant dictionaries
            current_order: Current initiative order (list of indices)
            events: List of events that might affect initiative
            
        Returns:
            Updated initiative order
        """
        # Create a copy to avoid modifying the original
        updated_order = current_order.copy()
        
        for event in events:
            event_type = event.get("type")
            
            # Ready action
            if event_type == "ready":
                # Get the combatant who readied an action
                combatant_idx = event.get("combatant_idx")
                
                # Ready action moves a combatant to later in the initiative
                if combatant_idx in updated_order:
                    # Remove from current position
                    updated_order.remove(combatant_idx)
                    # Re-insert at a later position based on trigger
                    trigger_initiative = event.get("trigger_initiative", 0)
                    
                    # Find the right position to insert
                    insert_pos = 0
                    for i, idx in enumerate(updated_order):
                        if combatants[idx].get("initiative", 0) <= trigger_initiative:
                            insert_pos = i
                            break
                    
                    # Insert at the calculated position
                    updated_order.insert(insert_pos, combatant_idx)
            
            # Held action triggered
            elif event_type == "held_action_triggered":
                # Get the combatant who triggered their ready action
                combatant_idx = event.get("combatant_idx")
                
                # Move them to the current position in initiative for this round
                current_position = event.get("current_position", 0)
                
                if combatant_idx in updated_order:
                    # Remove from current position
                    updated_order.remove(combatant_idx)
                    # Insert at the current position
                    updated_order.insert(current_position, combatant_idx)
        
        return updated_order 