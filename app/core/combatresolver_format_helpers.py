# Helpers for CombatResolver (_format_)

    def _format_active_auras(self, auras):
        """
        Format a list of active auras into a readable string
        
        Args:
            auras: List of aura objects affecting a combatant
            
        Returns:
            Formatted string describing the auras
        """
        if not auras:
            return "None"
            
        aura_strings = []
        for aura in auras:
            effect = aura.get("effect", {})
            effect_type = effect.get("type", "unknown")
            source = aura.get("source", "Unknown")
            name = aura.get("name", "unnamed aura")
            distance = aura.get("distance", 0)
            
            effect_desc = ""
            if effect_type == "damage":
                damage_expr = effect.get("expression", "")
                damage_type = effect.get("damage_type", "unspecified")
                effect_desc = f"{damage_expr} {damage_type} damage"
            elif effect_type == "condition":
                condition = effect.get("condition", "")
                effect_desc = f"applies {condition} condition"
            elif effect_type == "healing":
                healing_expr = effect.get("expression", "")
                effect_desc = f"heals {healing_expr} per turn"
            elif effect_type == "resistance":
                damage_types = effect.get("damage_types", [])
                types_str = ", ".join(damage_types)
                effect_desc = f"grants resistance to {types_str}"
                
            aura_strings.append(f"{source}'s {name} ({distance}ft away) - {effect_desc}")
            
        return "\n".join(aura_strings)

    def _format_nearby_combatants(self, nearby):
        """
        Format a list of nearby combatants into a readable string
        
        Args:
            nearby: List of nearby combatants
            
        Returns:
            Formatted string describing the nearby combatants
        """
        if not nearby:
            return "None"
        
        nearby_str = "\n".join([f"- {c.get('name', 'Unknown')} (HP: {c.get('hp', 0)}/{c.get('max_hp', c.get('hp', 0))}, AC: {c.get('ac', 10)}, Status: {c.get('status', 'OK')})" for c in nearby])
        return nearby_str

    def _format_conditions(self, combatant):
        """
        Format a list of conditions affecting the combatant
        
        Args:
            combatant: The combatant to check for conditions
            
        Returns:
            Formatted string describing the conditions
        """
        conditions = []
        
        # Check for blinded condition
        if combatant.get("blinded", False):
            conditions.append("Blinded: Cannot see, has disadvantage on attacks, grants advantage to attackers")
        
        # Check for frightened condition
        if combatant.get("frightened", False):
            conditions.append("Frightened: Has disadvantage on attacks while source of fear is in sight")
        
        # Check for invisible condition
        if combatant.get("invisible", False):
            conditions.append("Invisible: Has advantage on attacks, attacks against it have disadvantage")
        
        # Check for paralyzed condition
        if combatant.get("paralyzed", False):
            conditions.append("Paralyzed: Grants advantage on attacks, auto-crits if attacker within 5 feet")
        
        # Check for poisoned condition
        if combatant.get("poisoned", False):
            conditions.append("Poisoned: Has disadvantage on attacks and ability checks")
        
        # Check for prone condition
        if combatant.get("prone", False):
            conditions.append("Prone: Has disadvantage on attacks, grants advantage on attacks against it within 5 feet, grants disadvantage on ranged attacks against it")
        
        # Check for restrained condition
        if combatant.get("restrained", False):
            conditions.append("Restrained: Has disadvantage on attacks, grants advantage to attackers")
        
        # Check for stunned condition
        if combatant.get("stunned", False):
            conditions.append("Stunned: Grants advantage on attacks")
        
        # Check for unconscious condition
        if combatant.get("unconscious", False):
            conditions.append("Unconscious: Grants advantage on attacks, auto-crits if attacker within 5 feet")
        
        return "\n".join(conditions) if conditions else "No conditions affecting the combatant."

    def _format_active_auras(self, auras):
        """
        Format a list of active auras into a readable string
        
        Args:
            auras: List of aura objects affecting a combatant
            
        Returns:
            Formatted string describing the auras
        """
        if not auras:
            return "None"
            
        aura_strings = []
        for aura in auras:
            effect = aura.get("effect", {})
            effect_type = effect.get("type", "unknown")
            source = aura.get("source", "Unknown")
            name = aura.get("name", "unnamed aura")
            distance = aura.get("distance", 0)
            
            effect_desc = ""
            if effect_type == "damage":
                damage_expr = effect.get("expression", "")
                damage_type = effect.get("damage_type", "unspecified")
                effect_desc = f"{damage_expr} {damage_type} damage"
            elif effect_type == "condition":
                condition = effect.get("condition", "")
                effect_desc = f"applies {condition} condition"
            elif effect_type == "healing":
                healing_expr = effect.get("expression", "")
                effect_desc = f"heals {healing_expr} per turn"
            elif effect_type == "resistance":
                damage_types = effect.get("damage_types", [])
                types_str = ", ".join(damage_types)
                effect_desc = f"grants resistance to {types_str}"
                
            aura_strings.append(f"{source}'s {name} ({distance}ft away) - {effect_desc}")
            
        return "\n".join(aura_strings)

    def _format_dice_results(self, dice_results):
        """Return dice results in a concise, readable string for the LLM prompt.

        Args:
            dice_results: List of dicts with keys `expression`, `result`, and optional `purpose`.

        Returns:
            A newline-separated string summarizing each dice roll. If no dice were rolled,
            returns a friendly placeholder message.
        """
        # If nothing was rolled, keep the prompt clean and explicit
        if not dice_results:
            return "No dice were rolled this turn."

        # Build a line for each result: "1d20 => 17 (Attack roll)"
        formatted_lines = []
        for roll in dice_results:
            # Safely fetch each field with sensible fallbacks
            expr = str(roll.get("expression", "?"))
            res = str(roll.get("result", "?"))
            purpose = roll.get("purpose", "")

            # Add purpose in parentheses only when provided
            if purpose:
                formatted_lines.append(f"{expr} ⇒ {res} ({purpose})")
            else:
                formatted_lines.append(f"{expr} ⇒ {res}")

        return "\n".join(formatted_lines)

