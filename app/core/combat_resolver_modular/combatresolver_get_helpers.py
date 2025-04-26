# Helpers for CombatResolver (_get_)

    def _get_distance_between(self, combatant1, combatant2):
        """Get distance between two combatants in feet"""
        # Check if distances are explicitly defined in position data
        if "position" in combatant1 and "distance_to" in combatant1["position"]:
            target_name = combatant2.get("name", "")
            if target_name in combatant1["position"]["distance_to"]:
                return combatant1["position"]["distance_to"][target_name]
                
        # Default distance if not explicitly defined
        # 5ft for melee range, otherwise large distance (effectively out of range)
        if combatant1.get("type") != combatant2.get("type"):
            return 5  # Assume enemies are in melee range by default
        return 1  # Assume allies are very close by default

    def _get_active_auras(self, active_combatant, all_combatants):
        """
        Get a list of auras currently affecting a combatant
        
        Args:
            active_combatant: The combatant to check for affecting auras
            all_combatants: List of all combatants in the encounter
            
        Returns:
            List of aura objects affecting the combatant
        """
        active_auras = []
        
        # Ensure auras have been detected on all combatants
        for combatant in all_combatants:
            if "auras" not in combatant:
                self._add_auras_from_traits(combatant)
        
        # Check each combatant's auras
        for c in all_combatants:
            if "auras" not in c or not c.get("auras"):
                continue
                
            for aura_name, aura in c.get("auras", {}).items():
                # Skip self-auras that don't affect self
                if c.get("name") == active_combatant.get("name") and not aura.get("affects_self", False):
                    continue
                    
                # Skip auras that don't affect allies/enemies appropriately
                if aura.get("affects", "enemies") == "enemies" and c.get("type") == active_combatant.get("type"):
                    continue
                if aura.get("affects", "enemies") == "allies" and c.get("type") != active_combatant.get("type"):
                    continue
                
                # Check if this combatant is within the aura's range
                range_feet = aura.get("range", 10)  # Default 10 ft range
                distance = self._get_distance_between(c, active_combatant)
                
                if distance <= range_feet:
                    active_auras.append({
                        "name": aura_name,
                        "source": c.get("name", "Unknown"),
                        "range": range_feet,
                        "effect": aura.get("effect", {}),
                        "distance": distance
                    })
        
        return active_auras

    def _get_nearby_combatants(self, active_combatant, all_combatants):
        """
        Get a list of nearby combatants for the active combatant
        
        Args:
            active_combatant: The combatant to check for nearby combatants
            all_combatants: List of all combatants in the encounter
            
        Returns:
            List of nearby combatants
        """
        nearby = []
        
        # Check for nearby enemies
        for c in all_combatants:
            if c.get("type", "").lower() == "monster" and c.get("hp", 0) > 0:
                nearby.append(c)
        
        # Check for nearby allies
        for c in all_combatants:
            if c.get("type", "").lower() != "monster" and c.get("name", "") != "Add your party here!":
                nearby.append(c)
        
        return nearby

    def _get_active_auras(self, active_combatant, all_combatants):
        """
        Get a list of auras currently affecting a combatant
        
        Args:
            active_combatant: The combatant to check for affecting auras
            all_combatants: List of all combatants in the encounter
            
        Returns:
            List of aura objects affecting the combatant
        """
        active_auras = []
        
        # Ensure auras have been detected on all combatants
        for combatant in all_combatants:
            if "auras" not in combatant:
                self._add_auras_from_traits(combatant)
        
        # Check each combatant's auras
        for c in all_combatants:
            if "auras" not in c or not c.get("auras"):
                continue
                
            for aura_name, aura in c.get("auras", {}).items():
                # Skip self-auras that don't affect self
                if c.get("name") == active_combatant.get("name") and not aura.get("affects_self", False):
                    continue
                    
                # Skip auras that don't affect allies/enemies appropriately
                if aura.get("affects", "enemies") == "enemies" and c.get("type") == active_combatant.get("type"):
                    continue
                if aura.get("affects", "enemies") == "allies" and c.get("type") != active_combatant.get("type"):
                    continue
                
                # Check if this combatant is within the aura's range
                range_feet = aura.get("range", 10)  # Default 10 ft range
                distance = self._get_distance_between(c, active_combatant)
                
                if distance <= range_feet:
                    active_auras.append({
                        "name": aura_name,
                        "source": c.get("name", "Unknown"),
                        "range": range_feet,
                        "effect": aura.get("effect", {}),
                        "distance": distance
                    })
        
        return active_auras

