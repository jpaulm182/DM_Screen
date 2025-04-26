# Helpers for CombatResolver (_add_)

    def _add_auras_from_traits(self, combatant):
        """
        Analyze combatant traits and detect auras using pattern matching or LLM
        
        Args:
            combatant: The combatant to analyze for auras
            
        Returns:
            Updated combatant with auras field
        """
        # Initialize auras dict if not present
        if "auras" not in combatant:
            combatant["auras"] = {}
            
        # Skip if already processed
        if combatant.get("auras_processed", False):
            return combatant
            
        # Get combatant name for better logging
        name = combatant.get("name", "Unknown")
        print(f"[CombatResolver] Checking for auras in {name}'s traits")
            
        # Check for aura-related traits by name and description
        if "traits" in combatant and isinstance(combatant["traits"], list):
            for trait in combatant["traits"]:
                if not isinstance(trait, dict):
                    continue

                trait_name = trait.get("name", "")
                trait_desc = trait.get("description", "")
                
                # Check if it's an aura by name
                if "aura" in trait_name.lower():
                    print(f"[CombatResolver] Found aura trait by name: {trait_name}")
                    aura_name = trait_name.lower().replace(" ", "_")
                    aura_range = 10  # Default range
                    
                    # Try to extract range from description
                    import re
                    range_match = re.search(r'(\d+)[- ]feet?', trait_desc, re.IGNORECASE)
                    if range_match:
                        aura_range = int(range_match.group(1))
                        
                    # Determine effect type and details from description
                    effect_type = "damage" if any(x in trait_desc.lower() for x in ["damage", "takes", "hurt"]) else "condition"
                    
                    # Create damage effect
                    if effect_type == "damage":
                        # Extract damage amount from description
                        damage_match = re.search(r'(\d+)d(\d+)(?:\s*\+\s*(\d+))?', trait_desc)
                        damage_expr = "1d6"  # Default damage
                        damage_type = "fire"  # Default type
                        
                        if damage_match:
                            dice_count = damage_match.group(1)
                            dice_size = damage_match.group(2)
                            bonus = damage_match.group(3) or "0"
                            damage_expr = f"{dice_count}d{dice_size}+{bonus}"
                            
                        # Extract damage type if present
                        type_match = re.search(r'(\w+) damage', trait_desc.lower())
                        if type_match:
                            damage_type = type_match.group(1)
                            
                        # Create the aura effect
                        combatant["auras"][aura_name] = {
                            "range": aura_range,
                            "effect": {
                                "type": "damage",
                                "expression": damage_expr,
                                "damage_type": damage_type
                            },
                            "affects": "enemies",
                            "affects_self": False,
                            "source": "trait"
                        }
                        
                        print(f"[CombatResolver] Created {damage_type} damage aura '{aura_name}' with range {aura_range}ft, damage {damage_expr}")
                    
                    # Create condition effect
                    else:
                        # Extract condition from description
                        condition_match = re.search(r'(?:becomes?|is) (frightened|poisoned|stunned|blinded|deafened)', trait_desc.lower())
                        condition = "frightened" if not condition_match else condition_match.group(1)
                        
                        # Create the aura effect
                        combatant["auras"][aura_name] = {
                            "range": aura_range,
                            "effect": {
                                "type": "condition",
                                "condition": condition,
                                "duration": 1
                            },
                            "affects": "enemies",
                            "affects_self": False,
                            "source": "trait"
                        }
                        
                        print(f"[CombatResolver] Created condition aura '{aura_name}' with range {aura_range}ft, condition {condition}")
        
        # Special handling for known monsters with auras regardless of traits
        name_lower = name.lower()
        if "fire" in name_lower or "infernal" in name_lower or "tyrant" in name_lower:
            print(f"[CombatResolver] Adding fire aura to {name} based on name")
            
            # Only add if not already present
            if "fire_aura" not in combatant["auras"]:
                combatant["auras"]["fire_aura"] = {
                    "range": 10,
                    "effect": {
                        "type": "damage", 
                        "expression": "3d6", 
                        "damage_type": "fire"
                    },
                    "affects": "enemies",
                    "affects_self": False,
                    "source": "infernal_nature"
                }
                
                print(f"[CombatResolver] Added fire_aura to {name}")
        
        # Mark as processed to avoid redundant checks
        combatant["auras_processed"] = True
        return combatant

