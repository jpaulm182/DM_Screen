# Helpers for CombatResolver (_create_)

    def _create_decision_prompt(self, combat_state, turn_combatant):
        """Create a prompt for the LLM to decide a combatant's action."""
        prompt = "You are playing the role of a combatant in a D&D 5e battle. Make a tactical decision for your next action.\n\n"
        
        # Basic combat situation
        active_combatant = next((c for c in combat_state.get("combatants", []) if c.get("id") == turn_combatant.get("id")), None)
        if not active_combatant:
            return "Error: Could not find active combatant in combat state."
            
        instance_id = active_combatant.get("instance_id", "")
        
        # Get lists of available and unavailable recharge abilities
        available_recharge_abilities = []
        unavailable_recharge_abilities = []
        # Use try-except for potential errors during processing
        try: 
            for name, info in active_combatant.get("recharge_abilities", {}).items():
                if info.get("available", False):
                    available_recharge_abilities.append(f"{name} ({info.get('recharge_text', 'Recharge ability')})")
                else:
                    unavailable_recharge_abilities.append(f"{name} ({info.get('recharge_text', 'Recharge ability')})")
        except Exception as e:
            print(f"[CombatResolver] Error processing recharge abilities: {e}")
            # Handle error case gracefully, e.g., log or default behavior
            pass  # Example: continue without adding abilities
        
        # Format initiative order
        initiative_order = []
        for c in sorted([c for c in combat_state.get("combatants", [])], key=lambda x: x.get("initiative", 0), reverse=True):
            initiative_text = f"{c.get('name')} (Initiative: {c.get('initiative')})"
            if c.get("id") == active_combatant.get("id"):
                initiative_text += " - ACTIVE TURN"
            initiative_order.append(initiative_text)
        
        # Describe the combat situation
        prompt += "# Combat Situation\n"
        prompt += f"You are playing as: {active_combatant.get('name')} (Type: {active_combatant.get('type')})\n"
        # Use 'hp' as the canonical current HP field (fixes bug where HP was always 0)
        # Fallback to 'current_hp' only if 'hp' is missing, for robustness
        current_hp = active_combatant.get('hp', active_combatant.get('current_hp', 0))
        max_hp = active_combatant.get('max_hp', 0)
        prompt += f"Current HP: {current_hp}/{max_hp}\n"
        prompt += f"AC: {active_combatant.get('ac', 0)}\n"
        
        # Add status effects if any
        status_effects = active_combatant.get("status_effects", [])
        if status_effects:
            prompt += f"Status Effects: {', '.join(status_effects)}\n"
        
        # Initiative order
        prompt += "\n## Initiative Order\n"
        for init in initiative_order:
            prompt += f"- {init}\n"
        
        # Current turn number
        prompt += f"\nCurrent Turn: {combat_state.get('turn_number', 1)}\n"
        
        # Add information about all combatants
        prompt += "\n# Combatants\n"
        for c in combat_state.get("combatants", []):
            name = c.get("name", "Unknown")
            ctype = c.get("type", "unknown")
            c_current_hp = c.get('hp', c.get('current_hp', 0))
            c_max_hp = c.get('max_hp', c_current_hp)
            status = c.get("status", "Healthy")
            prompt += f"- {name} (Type: {ctype}, HP: {c_current_hp}/{c_max_hp}, Status: {status})\n"
        
        # Recharge abilities status
        if available_recharge_abilities or unavailable_recharge_abilities:
            prompt += "\n# Recharge Abilities Status\n"
            
            if available_recharge_abilities:
                prompt += "## Available Recharge Abilities\n"
                for ability in available_recharge_abilities:
                    prompt += f"- {ability} (AVAILABLE NOW)\n"
                    
            if unavailable_recharge_abilities:
                prompt += "## Unavailable Recharge Abilities\n"
                for ability in unavailable_recharge_abilities:
                    prompt += f"- {ability} (NOT YET RECHARGED - unavailable this turn)\n"
                    
            prompt += "\n"
        
        # Add actions, abilities, and traits
        prompt += "\n# Your Available Options\n"
        
        # Actions
        actions = active_combatant.get("actions", [])
        if actions:
            prompt += "## Actions\n"
            for action in actions:
                if isinstance(action, dict):
                    name = action.get("name", "Unknown")
                    desc = action.get("description", "No description")
                    
                    # Check if this is a recharge ability
                    recharge_info = ""
                    is_recharge = False
                    is_available = True
                    
                    if "recharge_abilities" in active_combatant:
                        if name in active_combatant["recharge_abilities"]:
                            is_recharge = True
                            recharge_data = active_combatant["recharge_abilities"][name]
                            is_available = recharge_data.get("available", False)
                            recharge_text = recharge_data.get("recharge_text", "Recharge ability")
                            
                            if is_available:
                                recharge_info = f" - {recharge_text} (AVAILABLE)"
                            else:
                                recharge_info = f" - {recharge_text} (NOT AVAILABLE THIS TURN)"
                    
                    # Skip unavailable recharge abilities in the prompt (to avoid confusion)
                    if is_recharge and not is_available:
                        continue
                        
                    # Check for instance ID to ensure this is for the right monster
                    # Use 'monster_instance_id' which is added during combat state gathering
                    action_instance_id = action.get("monster_instance_id", "") 
                    if action_instance_id and action_instance_id != instance_id:
                        print(f"[Prompt] Skipping action '{name}' (ID: {action_instance_id}) for combatant {active_combatant.get('name')}({instance_id})")
                        continue  # Skip actions belonging to different instances
                    
                    attack_bonus = action.get("attack_bonus", "")
                    if attack_bonus:
                        attack_text = f"Attack Bonus: {attack_bonus}"
                    else:
                        attack_text = ""
                        
                    damage = action.get("damage", "")
                    if damage:
                        damage_text = f"Damage: {damage}"
                    else:
                        damage_text = ""
                        
                    prompt += f"- {name}{recharge_info}\n"
                    prompt += f"  {desc}\n"
                    if attack_text:
                        prompt += f"  {attack_text}\n"
                    if damage_text:
                        prompt += f"  {damage_text}\n"
                    prompt += "\n"
        
        # Abilities
        abilities = active_combatant.get("abilities", [])
        if abilities:
            prompt += "## Abilities\n"
            for ability in abilities:
                if isinstance(ability, dict):
                    name = ability.get("name", "Unknown")
                    desc = ability.get("description", "No description")
                    
                    # Check if this is a recharge ability
                    recharge_info = ""
                    is_recharge = False
                    is_available = True
                    
                    if "recharge_abilities" in active_combatant:
                        if name in active_combatant["recharge_abilities"]:
                            is_recharge = True
                            recharge_data = active_combatant["recharge_abilities"][name]
                            is_available = recharge_data.get("available", False)
                            recharge_text = recharge_data.get("recharge_text", "Recharge ability")
                            
                            if is_available:
                                recharge_info = f" - {recharge_text} (AVAILABLE)"
                            else:
                                recharge_info = f" - {recharge_text} (NOT AVAILABLE THIS TURN)"
                    
                    # Skip unavailable recharge abilities in the prompt
                    if is_recharge and not is_available:
                        continue
                        
                    # Check for instance ID to ensure this is for the right monster
                    # Use 'monster_instance_id' which is added during combat state gathering
                    ability_instance_id = ability.get("monster_instance_id", "") 
                    if ability_instance_id and ability_instance_id != instance_id:
                        print(f"[Prompt] Skipping ability '{name}' (ID: {ability_instance_id}) for combatant {active_combatant.get('name')}({instance_id})")
                        continue  # Skip abilities belonging to different instances
                    
                    prompt += f"- {name}{recharge_info}\n"
                    prompt += f"  {desc}\n\n"
        
        # Traits/Features
        traits = active_combatant.get("traits", [])
        if traits:
            prompt += "## Traits/Features\n"
            for trait in traits:
                if isinstance(trait, dict):
                    name = trait.get("name", "Unknown")
                    desc = trait.get("description", "No description")
                    
                    # Check for instance ID to ensure this is for the right monster
                    # Use 'monster_instance_id' which is added during combat state gathering
                    trait_instance_id = trait.get("monster_instance_id", "") 
                    if trait_instance_id and trait_instance_id != instance_id:
                        print(f"[Prompt] Skipping trait '{name}' (ID: {trait_instance_id}) for combatant {active_combatant.get('name')}({instance_id})")
                        continue  # Skip traits belonging to different instances
                    
                    prompt += f"- {name}\n"
                    prompt += f"  {desc}\n\n"
        
        # Decision request
        prompt += "\n# Your Decision\n"
        prompt += "Given the current combat situation, decide what action to take. Consider the following:\n"
        prompt += "1. Which available action would be most effective tactically?\n"
        prompt += "2. Consider using any available recharged abilities (like breath weapons) when they're available\n"
        prompt += "3. Consider the positioning of allies and enemies\n"
        prompt += "4. If you have low HP, consider defensive actions or targeting dangerous opponents first\n\n"
        
        # Add explicit targeting guidance
        prompt += "IMPORTANT TARGETING RULES:\n"
        prompt += "- NEVER target yourself with attacks or harmful abilities\n"
        prompt += "- Target enemies, not allies (unless using a beneficial ability like healing)\n"
        prompt += "- Vary your actions when possible for dynamic combat\n"
        prompt += "- For area effects like breath weapons, target clusters of enemies\n\n"
        
        if available_recharge_abilities:
            prompt += f"IMPORTANT: You have {len(available_recharge_abilities)} recharged special abilities available now! Consider using them!\n\n"
        
        prompt += "Reply with a single JSON object in this format:\n"
        prompt += '{\n  "action": "[action name]",\n  "target": "[target name or none]",\n  "reasoning": "[brief tactical reasoning for this choice]",\n'
        
        # Add details about requesting dice rolls
        prompt += '  "dice_requests": [\n    {"expression": "1d20+5", "purpose": "Attack roll"},\n    {"expression": "2d6+3", "purpose": "Damage roll"}\n  ]\n}\n\n'
        
        # Ensure prompt is a string, even if errors occurred
        if not isinstance(prompt, str):
            prompt = "Error: Prompt generation failed."
        
        return prompt

    def _create_resolution_prompt(self, combatants, active_idx, combatant_decision, dice_results, round_num):
        """
        Create a prompt for the LLM to resolve a combatant's action.
        
        This method generates a detailed prompt to help the LLM narrate and resolve
        the outcome of a combatant's action, including handling damage, conditions,
        and special ability effects, including recharge ability tracking.
        
        Args:
            combatants: List of all combatants
            active_idx: Index of active combatant
            combatant_decision: The decision made by the LLM for the active combatant
            dice_results: Results of any dice rolls requested by the decision LLM
            round_num: Current round number
            
        Returns:
            Prompt string for the resolution LLM
        """
        active = combatants[active_idx]
        active_name = active.get('name', 'Unknown')
        
        # Get the instance ID for this combatant
        instance_id = active.get('instance_id', f"combatant_{active_idx}")
        
        # Extract the decision components
        action = combatant_decision.get('action', 'No action taken')
        target = combatant_decision.get('target', None)
        action_type = combatant_decision.get('action_type', 'none')
        
        # Format dice results
        dice_str = self._format_dice_results(dice_results)
        
        # Format nearby combatants
        nearby = self._get_nearby_combatants(active, combatants)
        nearby_str = self._format_nearby_combatants(nearby)
        
        # Format the target information
        target_str = "No specific target."
        target_data = None
        
        if target:
            # Find the target in the list of combatants
            for combatant in combatants:
                if combatant.get('name') == target:
                    target_data = combatant
                    break
            
            if target_data:
                target_str = f"""
Target: {target_data.get('name', 'Unknown')}
HP: {target_data.get('hp', 0)}/{target_data.get('max_hp', target_data.get('hp', 0))}
AC: {target_data.get('ac', 10)}
Type: {target_data.get('type', 'Unknown')}
Status: {target_data.get('status', 'OK')}
"""
            else:
                target_str = f"Target: {target} (details unknown)"
        
        # Get and format conditions affecting the active combatant
        condition_str = self._format_conditions(active)
        
        # Check for recharge ability usage
        recharge_warning = ""
        recharge_status = ""
        used_ability_name = None
        
        # First, compile a list of available and unavailable recharge abilities
        available_recharge = []
        unavailable_recharge = []
        
        if "recharge_abilities" in active and active["recharge_abilities"]:
            for ability_name, info in active["recharge_abilities"].items():
                if info.get("available", False):
                    available_recharge.append(ability_name)
                else:
                    unavailable_recharge.append(ability_name)
        
            # Add recharge status information
            recharge_status = f"""
# RECHARGE ABILITIES STATUS
Available now: {', '.join(available_recharge) if available_recharge else 'None'}
NOT available (needs recharge): {', '.join(unavailable_recharge) if unavailable_recharge else 'None'}
"""
            
        # Try to identify which ability is being used from the action description
        if "recharge_abilities" in active and active["recharge_abilities"]:
            for ability_name in active["recharge_abilities"].keys():
                # Check if the ability name appears in the action text
                if ability_name.lower() in action.lower():
                    used_ability_name = ability_name
                    break
            
            # If we identified a recharge ability being used
            if used_ability_name:
                is_available = active["recharge_abilities"][used_ability_name].get("available", False)
                
                # If the ability is not available, add a warning
                if not is_available:
                    recharge_warning = f"""
⚠️ WARNING - RECHARGE ABILITY NOT AVAILABLE ⚠️
The combatant is attempting to use {used_ability_name}, but this ability has not recharged yet!
This ability cannot be used until it recharges (typically on a roll of 5-6 on a d6 at the start of the creature's turn).
Please adjust the resolution to indicate the creature attempted to use this ability but couldn't, and had to choose a different action instead.
"""
                else:
                    # If the ability is available, mark it as used (unavailable for next turn)
                    active["recharge_abilities"][used_ability_name]["available"] = False
                    recharge_warning = f"""
RECHARGE ABILITY USED: {used_ability_name} has been used and is now unavailable until recharged.
Make sure to reflect this in your resolution by setting "recharge_ability_used" to "{used_ability_name}".
"""
        
        # Start constructing the prompt
        prompt = f"""
You are the combat resolution AI for a D&D 5e game. Your task is to resolve {active_name}'s action this turn and narrate the outcome.

# COMBAT SITUATION
Round: {round_num}
Active Combatant: {active_name}

# {active_name.upper()} DETAILS
HP: {active.get('hp', 0)}/{active.get('max_hp', active.get('hp', 0))}
AC: {active.get('ac', 10)}
Type: {active.get('type', 'Unknown')}
Status: {active.get('status', 'OK')}

# CHOSEN ACTION
{action}
Action Type: {action_type}

{recharge_status}
{recharge_warning}

# DICE RESULTS
{dice_str}

# TARGET INFORMATION
{target_str}

# NEARBY COMBATANTS
{nearby_str}

# CURRENT CONDITIONS
{condition_str}

# RESOLUTION INSTRUCTIONS
1. Narrate what happens when {active_name} takes their action.
2. Determine outcomes based on dice results.
3. Calculate damage dealt or healing provided.
4. Apply any conditions that result from the action.
5. Note any resource usage (spell slots, limited use abilities, etc.).

Your response MUST be a JSON object containing:
{{
  "description": "A vivid narration of what happens when the action is taken and its immediate effects",
  "damage_dealt": {{"target_name": damage_amount, ...}},
  "damage_taken": {{"source_name": damage_amount, ...}},
  "healing": {{"target_name": healing_amount, ...}},
  "conditions_applied": {{"target_name": ["condition1", "condition2", ...], ...}},
  "conditions_removed": {{"target_name": ["condition1", "condition2", ...], ...}},
  "recharge_ability_used": ""
}}

IMPORTANT GUIDELINES:
- Provide a detailed, vivid description of the action's outcome
- In "damage_dealt", use specific target names and numerical damage values
- Use dice results to determine hits/misses and damage amounts
- If attack rolls beat the target's AC, apply appropriate damage
- Apply appropriate conditions based on the attack type and narrative
- For healing effects, specify the target and amount in the "healing" field
- ALWAYS format your response as a proper JSON object

DESCRIPTION: A detailed narrative of what happens
DAMAGE_DEALT: A mapping of target names to damage amounts
DAMAGE_TAKEN: A mapping of damage sources to damage amounts
HEALING: A mapping of target names to healing amounts
CONDITIONS_APPLIED: A mapping of target names to lists of conditions applied
CONDITIONS_REMOVED: A mapping of target names to lists of conditions removed
RECHARGE_ABILITY_USED: If a recharge ability was used, set this to the name of the ability (e.g. "Fire Breath")

IMPORTANT: If the action involves using a recharge ability that is not available, adjust your narration to describe how the creature attempted to use that ability but couldn't, and then chose an alternative action instead.
"""
        return prompt

    def _create_combat_prompt(self, combat_state):
        # Simplified legacy prompt creation
        round_num = combat_state.get("round", 1)
        combatants = combat_state.get("combatants", [])
        
        combatant_str = "\n".join([
            f"- {c.get('name', 'Unknown')}: HP {c.get('hp', 0)}/{c.get('max_hp', c.get('hp', 0))}, AC {c.get('ac', 10)}, Status: {c.get('status', 'OK')}"
            for c in combatants
        ])
        
        prompt = f"""
You are a Dungeons & Dragons 5e Dungeon Master. Resolve this combat encounter with a brief narrative and status updates.

Combat State:
Round: {round_num}
Combatants:
{combatant_str}

Response format:
{{
  \"narrative\": \"Brief description of combat outcome\",
  \"updates\": [
    {{\"name\": \"Combatant1\", \"hp\": 25, \"status\": \"OK\"}},
    ...
  ]
}}

Return ONLY the JSON object with no other text.
"""
        return prompt

