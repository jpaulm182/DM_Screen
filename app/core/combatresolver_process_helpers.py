# Helpers for CombatResolver (_process_)

    def _process_recharge_abilities(self, combatant, dice_roller):
        """Process recharge abilities: roll d6 to recharge limited-use abilities based on recharge_text."""
        import re
        # Iterate through each limited-use ability and attempt recharge if not already available
        for name, info in combatant.get("recharge_abilities", {}).items():
            if not info.get("available", False):
                recharge_text = info.get("recharge_text", "")
                # Determine recharge range e.g. '5-6'
                match = re.search(r'(\d+)\s*-\s*(\d+)', recharge_text)
                if match:
                    low, high = int(match.group(1)), int(match.group(2))
                else:
                    low, high = 6, 6
                # Roll a d6 to check for recharge
                try:
                    roll = dice_roller("1d6")
                except Exception as e:
                    print(f"[CombatResolver] Error rolling recharge d6 for {combatant.get('name')}'s {name}: {e}")
                    continue
                # Check roll outcome
                if isinstance(roll, int) and low <= roll <= high:
                    info["available"] = True
                    print(f"[CombatResolver] {combatant.get('name')} recharge roll for '{name}': {roll} (in {low}-{high}), now AVAILABLE")
                else:
                    print(f"[CombatResolver] {combatant.get('name')} recharge roll for '{name}': {roll} (not in {low}-{high}), still unavailable")
        # Return combatant with updated availability flags
        return combatant

    def _process_turn(self, combatants, active_idx, round_num, dice_roller):
        """
        Process a single combatant's turn with LLM.
        
        Args:
            combatants: List of all combatants
            active_idx: Index of active combatant
            round_num: Current round number
            dice_roller: Function to roll dice
            
        Returns:
            Dictionary with turn results or None if error
        """
        logging.debug(f"--- ENTERING _process_turn for index {active_idx}, round {round_num} ---") # TEST LOG
        import json  # Import json at the function level to ensure it's available
        import re
        
        # Ensure dice_results is always defined to prevent NameError in error/fallback cases
        dice_results = []
        try:
            active_combatant = combatants[active_idx]
            print(f"[CombatResolver] Processing turn for {active_combatant.get('name', 'Unknown')} (round {round_num})")
            
            # --- ADD DEBUG LOGGING --- 
            try:
                import json
                print(f"[CombatResolver] DEBUG: START OF TURN DATA for {active_combatant.get('name')}:")
                # Print relevant fields, especially actions/traits
                debug_data = {
                    k: v for k, v in active_combatant.items() 
                    if k in ['name', 'type', 'hp', 'ac', 'actions', 'traits', 'instance_id']
                }
                print(json.dumps(debug_data, indent=2))
            except Exception as log_e:
                print(f"[CombatResolver] Error logging start-of-turn data: {log_e}")
            # --- END DEBUG LOGGING ---
            
            # Import ActionEconomyManager if needed
            from app.combat.action_economy import ActionEconomyManager
            
            # Initialize or reset action economy at the start of the turn
            active_combatant = ActionEconomyManager.initialize_action_economy(active_combatant)
            
            # Process recharge abilities for monsters
            if active_combatant.get("type", "").lower() == "monster":
                self._process_recharge_abilities(active_combatant, dice_roller)
            
            # Debug: Log all combatant HP values at start of turn
            print(f"\n[CombatResolver] DEBUG: CURRENT HP VALUES AT START OF TURN:")
            for i, c in enumerate(combatants):
                print(f"[CombatResolver] DEBUG: Combatant {i}: {c.get('name')} - HP: {c.get('hp', 0)}/{c.get('max_hp', c.get('hp', 0))}")
            
            # Process aura effects at the start of turn
            aura_updates = self._process_auras(active_combatant, combatants)
            if aura_updates:
                print(f"[CombatResolver] Processed {len(aura_updates)} aura effects affecting {active_combatant.get('name', 'Unknown')}")
                for update in aura_updates:
                    print(f"[CombatResolver] Aura effect: {update.get('source')} -> {update.get('target')}: {update.get('effect')}")
                    
                    # Update the combatant in the list after processing aura effects
                    combatants[active_idx] = active_combatant
            else:
                print(f"[CombatResolver] No aura effects processed for {active_combatant.get('name', 'Unknown')}")
                
                # Debug the auras
                active_auras = self._get_active_auras(active_combatant, combatants)
                if active_auras:
                    print(f"[CombatResolver] Found {len(active_auras)} auras that should affect {active_combatant.get('name', 'Unknown')}:")
                    for aura in active_auras:
                        print(f"[CombatResolver] - {aura.get('source')}'s {aura.get('name')} (range: {aura.get('range')}ft, distance: {aura.get('distance')}ft)")
                else:
                    print(f"[CombatResolver] No active auras found for {active_combatant.get('name', 'Unknown')}")
                    
                # Debug aura data on all combatants
                for idx, c in enumerate(combatants):
                    if "auras" in c and c.get("auras"):
                        print(f"[CombatResolver] Combatant {idx} ({c.get('name')}) has {len(c.get('auras'))} defined auras:")
                        for aura_name, aura in c.get("auras", {}).items():
                            aura_range = aura.get("range", 0)
                            affects = aura.get("affects", "unknown")
                            print(f"[CombatResolver] -- {aura_name} (range: {aura_range}ft, affects: {affects})")
            
            # Skip if combatant is dead or has status "Dead"
            if active_combatant.get("hp", 0) <= 0 and active_combatant.get("status", "").lower() == "dead":
                print(f"[CombatResolver] Skipping turn for {active_combatant.get('name', 'Unknown')}: dead or 0 HP")
                # Return a minimal result to avoid None return which would error
                return {
                    "action": f"{active_combatant.get('name', 'Unknown')} is unconscious/dead and skips their turn.",
                    "narrative": f"{active_combatant.get('name', 'Unknown')} is unconscious/dead and skips their turn.",
                    "dice": [],
                    "updates": []
                }
                
            # If aura effects reduced HP to 0, handle that before processing the turn
            if active_combatant.get("hp", 0) <= 0 and active_combatant.get("status", "").lower() != "dead":
                active_combatant["status"] = "Unconscious"
                print(f"[CombatResolver] {active_combatant.get('name', 'Unknown')} was knocked unconscious by aura effects")
                return {
                    "action": f"{active_combatant.get('name', 'Unknown')} falls unconscious due to aura damage.",
                    "narrative": f"{active_combatant.get('name', 'Unknown')} falls unconscious due to aura damage.",
                    "dice": [],
                    "updates": [{
                        "name": active_combatant.get('name', 'Unknown'),
                        "hp": 0,
                        "status": "Unconscious"
                    }],
                    "aura_updates": aura_updates
                }
            
            # 1. Create a prompt for the LLM to decide the action
            # Prepare combat_state and turn_combatant for prompt creation
            combat_state = {"combatants": combatants, "turn_number": round_num}
            turn_combatant = combatants[active_idx]
            prompt = self._create_decision_prompt(combat_state, turn_combatant)
            
            # 2. Get action decision from LLM
            print(f"[CombatResolver] Requesting action decision from LLM for {active_combatant.get('name', 'Unknown')}")
            try:
                # Prefer GPT-4.1 Mini for fast combat resolution if available
                available_models = self.llm_service.get_available_models()
                model_id = None
                for m in available_models:
                    if m["id"] == ModelInfo.OPENAI_GPT4O_MINI:
                        model_id = m["id"]
                        break
                if not model_id:
                    # Fallback: use first available model
                    model_id = available_models[0]["id"]
                # Now use model_id for LLM calls
                print(f"[CombatResolver] Sending prompt to LLM:\n{prompt}\n---END PROMPT---")
                decision_response = self.llm_service.generate_completion(
                    model=model_id,
                    messages=self.build_llm_messages(self.previous_turn_summaries, prompt),
                    temperature=0.7,
                    max_tokens=800
                )
                print(f"[CombatResolver] Received LLM decision for {active_combatant.get('name', 'Unknown')}")
                print(f"[CombatResolver] Raw decision response TYPE: {type(decision_response).__name__}")
                print(f"[CombatResolver] Raw decision response VALUE: {decision_response!r}")
                
                # Extended debugging to understand resolution response
                print(f"[CombatResolver] *** RESOLUTION DEBUG ***")
                print(f"[CombatResolver] Resolution type: {type(decision_response).__name__}")
                if isinstance(decision_response, str):
                    print(f"[CombatResolver] First 100 chars: {decision_response[:100]}...")
                    if "```json" in decision_response or "```" in decision_response:
                        print(f"[CombatResolver] Contains code block markers")
                
                # --- FIX: Parse JSON if needed (strip code block markers first) ---
                if isinstance(decision_response, str):
                    cleaned = decision_response.strip()
                    # Multiple cleanup attempts in sequence, from most specific to general
                    
                    # 1. Try to extract JSON specifically marked with ```json
                    if "```json" in cleaned:
                        json_parts = cleaned.split("```json")
                        if len(json_parts) > 1:
                            json_content = json_parts[1].split("```")[0].strip()
                            print(f"[CombatResolver] Extracted JSON from ```json block: {json_content[:100]}...")
                            try:
                                parsed_decision = json.loads(json_content)
                                print(f"[CombatResolver] Successfully parsed JSON from ```json block")
                                decision_response = parsed_decision
                            except Exception as e:
                                print(f"[CombatResolver] Error parsing JSON from ```json block: {e}")
                                # Continue to next cleanup approach
                        
                    # 2. Try to extract content from any ``` code block
                    if isinstance(decision_response, str) and "```" in cleaned:
                        # Get content between first ``` and last ```
                        parts = cleaned.split("```")
                        if len(parts) >= 3:  # At least one complete code block
                            # Take the first complete code block (parts[1])
                            code_content = parts[1].strip()
                            print(f"[CombatResolver] Extracted from generic code block: {code_content[:100]}...")
                            try:
                                parsed_decision = json.loads(code_content)
                                print(f"[CombatResolver] Successfully parsed JSON from generic code block")
                                decision_response = parsed_decision
                            except Exception as e:
                                print(f"[CombatResolver] Error parsing content from generic code block: {e}")
                                # Continue to next cleanup approach
                        
                    # 3. Try standard cleanup (removing all code markers)
                    if isinstance(decision_response, str):
                        cleaned = re.sub(r'```(?:json)?\s*', '', cleaned)
                        cleaned = re.sub(r'```\s*$', '', cleaned)
                        cleaned = cleaned.strip()
                        print(f"[CombatResolver] Standard cleanup result: {cleaned[:100]}...")
                        try:
                            parsed_decision = json.loads(cleaned)
                            print(f"[CombatResolver] Successfully parsed JSON after standard cleanup")
                            decision_response = parsed_decision
                        except json.JSONDecodeError as e:  # Use json instead of _json
                            print(f"[CombatResolver] JSON decode error in resolution: {e}")
                            # Try to clean up the JSON string further
                            cleaned_json = re.sub(r',\s*}', '}', cleaned)
                            cleaned_json = re.sub(r',\s*]', ']', cleaned_json)  # Remove trailing commas in arrays
                            print(f"[CombatResolver] Cleaned JSON: {cleaned_json[:100]}...")
                            try:
                                parsed_decision = json.loads(cleaned_json)  # Use json instead of _json
                                print(f"[CombatResolver] Parsed cleaned LLM resolution as JSON: {parsed_decision}")
                                decision_response = parsed_decision
                            except json.JSONDecodeError as e2:  # Use json instead of _json
                                print(f"[CombatResolver] Failed to parse JSON resolution even after cleanup: {e2}")
                                # Use a simpler approach - construct a minimal resolution with description field
                                decision_response = {
                                    "description": "The action resolves with technical difficulties.",
                                    "narrative": "The action resolves with technical difficulties.",
                                    "updates": []
                                }
                                
                                # Try to extract potential targets and damage from dice results
                                potential_target = target if 'target' in locals() and target and target.lower() != "none" else None
                                if not potential_target:
                                    # Find first enemy
                                    for c in combatants:
                                        if c.get("name") != active_combatant.get("name"):
                                            potential_target = c.get("name")
                                            break
                                
                                if potential_target and 'dice_results' in locals() and dice_results:
                                    # Look for damage dice
                                    damage_dice = [d for d in dice_results if "damage" in d.get("purpose", "").lower()]
                                    if damage_dice:
                                        try:
                                            damage_amount = int(damage_dice[0].get("result", 0))
                                            # Create or update damage value for target
                                            decision_response["damage_dealt"] = {potential_target: damage_amount}
                                            print(f"[CombatResolver] Created damage_dealt with {damage_amount} to {potential_target}")
                                        except (ValueError, TypeError):
                                            print(f"[CombatResolver] Could not extract damage value from dice")
                # --- ENSURE resolution is a dict ---
                if not isinstance(decision_response, dict):
                    print(f"[CombatResolver] LLM resolution is not a dict, using fallback.")
                    decision_response = {
                        "description": str(decision_response),
                        "narrative": str(decision_response),
                        "updates": []
                    }

                # DEBUG: Print raw LLM output for troubleshooting
                if 'decision_response' in locals(): # Check for decision_response instead
                    print(f"[CombatResolver] RAW LLM OUTPUT (first 500 chars): {str(decision_response)[:500]}") # Use decision_response

                # --- DICE ROLLING PHASE ---
                dice_results = []
                # Check for dice_requests in the LLM response
                dice_requests = decision_response.get('dice_requests', [])
                for req in dice_requests:
                    expr = req.get('expression')
                    purpose = req.get('purpose', '')
                    if expr:
                        try:
                            result = dice_roller(expr)
                        except Exception as e:
                            print(f"[CombatResolver] Dice roll error for '{expr}': {e}")
                            result = 'error'
                        dice_results.append({
                            'expression': expr,
                            'result': result,
                            'purpose': purpose
                        })
                # Attach dice_results to locals for downstream logic
                # (the rest of the function already tries to use dice_results)

                # ------------------------------------------------------------------
                # NEW: Build and RETURN the turn_result so the caller can log it
                # ------------------------------------------------------------------
                
                # Build updates list based on damage/healing information if provided
                updates = []

                try:
                    # Extract a narrative/description in a tolerant manner
                    narrative_text = None
                    # Prefer 'reasoning', then 'description', then 'narrative', then 'action', then 'result' for the combat log
                    for field in ["reasoning", "description", "narrative", "action", "result"]:
                        if field in decision_response and decision_response[field]:
                            narrative_text = decision_response[field]
                            print(f"[CombatResolver] Found narrative in field '{field}': {narrative_text[:50]}...")
                            break
                    # If no appropriate field was found, use a default
                    if not narrative_text:
                        narrative_text = "The action resolves with technical difficulties."
                        print(f"[CombatResolver] Using fallback narrative: {narrative_text}")

                    # Auto-detect targets if no damage_dealt is specified but there's a narrative
                    if (not decision_response.get("damage_dealt") or len(decision_response.get("damage_dealt", {})) == 0) and narrative_text:
                        print(f"[CombatResolver] No damage specified in resolution, attempting to extract from narrative")
                        # Find potential targets mentioned in the narrative
                        potential_targets = []
                        for c in combatants:
                            if c.get("name") != active_combatant.get("name") and c.get("name") in narrative_text:
                                potential_targets.append(c.get("name"))
                        
                        if potential_targets:
                            print(f"[CombatResolver] Found potential targets in narrative: {potential_targets}")
                            # Add the first found target to damage_dealt
                            if "damage_dealt" not in decision_response:
                                decision_response["damage_dealt"] = {}
                            
                            # Check if attack/damage dice were rolled
                            damage_dice = [d for d in dice_results if "damage" in d.get("purpose", "").lower()]
                            if damage_dice:
                                try:
                                    damage_value = int(damage_dice[0].get("result", 0))
                                    # Create or update damage value for target
                                    decision_response["damage_dealt"][potential_targets[0]] = damage_value
                                    print(f"[CombatResolver] Auto-assigned {damage_value} damage to {potential_targets[0]}")
                                except (ValueError, TypeError):
                                    print(f"[CombatResolver] Could not extract damage value from dice")
                    
                    # If there are damage dice but no damage_dealt section at all, create one
                    if not decision_response.get("damage_dealt") and 'dice_results' in locals() and dice_results:
                        damage_dice = [d for d in dice_results if "damage" in d.get("purpose", "").lower()]
                        if damage_dice:
                            # Try to find the most likely target
                            if 'target' in locals() and target and target != "none" and target != "None":
                                # Target was specified in the decision
                                try:
                                    damage_value = int(damage_dice[0].get("result", 0))
                                    decision_response["damage_dealt"] = {target: damage_value}
                                    print(f"[CombatResolver] Created damage_dealt with {damage_value} to {target}")
                                except (ValueError, TypeError):
                                    print(f"[CombatResolver] Could not extract damage value from dice")
                            else:
                                # Try to find enemy targets
                                enemies = [c.get("name") for c in combatants 
                                          if c.get("name") != active_combatant.get("name")]
                                if enemies:
                                    try:
                                        damage_value = int(damage_dice[0].get("result", 0))
                                        decision_response["damage_dealt"] = {enemies[0]: damage_value}
                                        print(f"[CombatResolver] Created damage_dealt with {damage_value} to {enemies[0]}")
                                    except (ValueError, TypeError):
                                        print(f"[CombatResolver] Could not extract damage value from dice")

                    # Handle damage dealt (reduce HP for targets)
                    for target_name, dmg in decision_response.get("damage_dealt", {}).items():
                        target = next((c for c in combatants if c.get("name") == target_name), None)
                        if not target:
                            print(f"[CombatResolver] Target '{target_name}' not found for damage.")
                            continue

                        # --- REVISED Saving Throw & Damage Logic ---
                        save_succeeded = False
                        save_required = False
                        final_dmg = 0
                        action_name = decision_response.get("action", "Unknown Action")
                        
                        # Find the action definition for the active combatant
                        action_details = None
                        if "actions" in active_combatant:
                             action_details = next((a for a in active_combatant["actions"] if isinstance(a, dict) and a.get("name") == action_name), None)
                        
                        # 1. Check if the action requires a saving throw based on its description
                        if action_details and "saving throw" in action_details.get("description", "").lower():
                            save_required = True
                            print(f"[CombatResolver] Action '{action_name}' requires a saving throw.")
                            
                            # Extract DC and Ability from action description (more reliable)
                            save_dc = 15 # Default fallback DC
                            save_ability_name = "Dexterity" # Default fallback ability
                            damage_on_save = "half" # Default assumption
                            
                            # Regex to find "DC X Ability saving throw"
                            save_match = re.search(r"DC\s*(\d+)\s*(\w+)\s*saving throw", action_details["description"], re.IGNORECASE)
                            if save_match:
                                save_dc = int(save_match.group(1))
                                save_ability_name = save_match.group(2).capitalize()
                                print(f"[CombatResolver] Extracted Save DC {save_dc} and Ability {save_ability_name} from action description.")
                            else:
                                print(f"[CombatResolver] WARNING: Could not extract DC/Ability from action description: {action_details['description']}. Using defaults DC {save_dc} {save_ability_name}.")

                            # Determine damage on save from description
                            if "half as much damage on a successful one" in action_details["description"].lower():
                                damage_on_save = "half"
                            elif "no damage on a successful save" in action_details["description"].lower(): # Check for 'no damage' case
                                damage_on_save = "none"
                            else:
                                damage_on_save = "full" # Assume full damage on fail, maybe half on success if not specified
                                print(f"[CombatResolver] Assuming '{damage_on_save}' damage on successful save for {action_name}")

                            # Get target's save modifier
                            # Map ability name to stat abbreviation (e.g., Dexterity -> dex)
                            ability_abbr_map = {"Strength": "str", "Dexterity": "dex", "Constitution": "con", "Intelligence": "int", "Wisdom": "wis", "Charisma": "cha"}
                            ability_abbr = ability_abbr_map.get(save_ability_name, "dex") # Default to dex if name is weird
                            
                            target_stat_value = target.get(ability_abbr, 10) # Default to 10 if stat missing
                            save_modifier = (target_stat_value - 10) // 2
                            print(f"[CombatResolver] Target {target_name}'s {save_ability_name} modifier: {save_modifier}")
                            
                            # Roll the save INTERNALLY
                            save_roll_expr = f"1d20+{save_modifier}"
                            try:
                                save_roll_result = dice_roller(save_roll_expr)
                                if isinstance(save_roll_result, (int, float)): # Check if roll succeeded
                                     save_roll_result = int(save_roll_result)
                                     # Append this internally rolled save to dice_results for logging
                                     dice_results.append({
                                         'expression': save_roll_expr,
                                         'result': save_roll_result,
                                         'purpose': f"{target_name}'s {save_ability_name} save vs DC {save_dc}"
                                     })
                                     print(f"[CombatResolver] Internally rolled save for {target_name}: {save_roll_result} vs DC {save_dc}")
                                     if save_roll_result >= save_dc:
                                         save_succeeded = True
                                         print(f"[CombatResolver] {target_name} succeeded on the internal save!")
                                     else:
                                         save_succeeded = False
                                         print(f"[CombatResolver] {target_name} failed the internal save.")
                                else:
                                     print(f"[CombatResolver] ERROR: Internal save roll failed or returned invalid type: {save_roll_result}. Assuming failure.")
                                     save_succeeded = False
                                     # Log the failed roll attempt
                                     dice_results.append({
                                         'expression': save_roll_expr,
                                         'result': 'Error',
                                         'purpose': f"{target_name}'s {save_ability_name} save vs DC {save_dc} (Roll Failed)"
                                     })
                            except Exception as e:
                                print(f"[CombatResolver] CRITICAL ERROR rolling internal save '{save_roll_expr}': {e}. Assuming failure.")
                                save_succeeded = False
                                # Log the failed roll attempt
                                dice_results.append({
                                    'expression': save_roll_expr,
                                    'result': 'Error',
                                    'purpose': f"{target_name}'s {save_ability_name} save vs DC {save_dc} (Roll Exception)"
                                })
                        
                        # 2. Validate and get initial damage amount (from LLM or dice)
                        initial_dmg = 0
                        if isinstance(dmg, (int, float)):
                            initial_dmg = int(dmg)
                        else:
                            try:
                                initial_dmg = int(dmg)
                            except (ValueError, TypeError):
                                print(f"[CombatResolver] Invalid initial damage value: {dmg} for target {target_name}. Trying dice fallback.")
                                # Fallback: Try extracting from dice results directly
                                damage_dice = [d for d in dice_results if "damage" in d.get("purpose", "").lower()]
                                if damage_dice:
                                    try:
                                        initial_dmg = int(damage_dice[0].get("result", 0))
                                        print(f"[CombatResolver] Using damage from dice result: {initial_dmg}")
                                    except (ValueError, TypeError):
                                        print(f"[CombatResolver] Could not parse damage dice result.")
                                        initial_dmg = 0
                                else:
                                    initial_dmg = 0
                        
                        # 3. Adjust damage based on saving throw outcome
                        if save_required:
                            if save_succeeded:
                                if damage_on_save == "half":
                                    final_dmg = initial_dmg // 2
                                    print(f"[CombatResolver] Applying half damage ({final_dmg}) due to successful save.")
                                elif damage_on_save == "none":
                                    final_dmg = 0
                                    print(f"[CombatResolver] Applying no damage due to successful save.")
                                else: # Includes 'full' which implies full damage on fail, half on success? Revisit this assumption if needed.
                                     final_dmg = initial_dmg // 2 # Default to half damage on save if not specified otherwise
                                     print(f"[CombatResolver] Applying default half damage ({final_dmg}) due to successful save.")
                            else: # Save failed
                                final_dmg = initial_dmg
                                print(f"[CombatResolver] Applying full damage ({final_dmg}) due to failed save.")
                        else: 
                            # 4. If no save required, check attack roll vs AC
                            final_dmg = 0 # Default to 0 unless attack hits
                            attack_rolls = [d for d in dice_results if "attack" in d.get("purpose", "").lower()]
                            if attack_rolls:
                                try:
                                    attack_value = int(attack_rolls[0].get("result", 0))
                                    target_ac = target.get("ac", 15) # Use target's AC
                                    print(f"[CombatResolver] Checking attack roll {attack_value} vs AC {target_ac} for {target_name}")
                                    if attack_value >= target_ac:
                                        final_dmg = initial_dmg # Apply full damage if attack hits
                                        print(f"[CombatResolver] Attack hit! Applying damage {final_dmg}.")
                                    else:
                                        final_dmg = 0 # Ensure damage is zero if attack missed
                                        print(f"[CombatResolver] Attack missed. No damage applied.")
                                except (ValueError, TypeError, IndexError) as e:
                                    print(f"[CombatResolver] Could not parse attack roll for damage check: {e}. Assuming miss.")
                                    final_dmg = 0
                            else:
                                # If no attack roll found for non-save action, assume it hits? Or apply 0 damage?
                                # Let's assume 0 damage if no attack roll present for a non-save action.
                                print(f"[CombatResolver] No attack roll found for action '{action_name}'. Applying 0 damage.")
                                final_dmg = 0
                        
                        # 5. Apply the final calculated damage
                        if final_dmg > 0:
                            new_hp = max(0, target.get("hp", 0) - final_dmg)
                            # Check if update already exists for this target
                            existing_update = next((u for u in updates if u.get("name") == target_name), None)
                            if existing_update:
                                existing_update["hp"] = new_hp # Update existing entry
                            else:
                                updates.append({"name": target_name, "hp": new_hp}) # Add new entry
                            print(f"[CombatResolver] Applying {final_dmg} damage to {target_name}: HP {target.get('hp', 0)} → {new_hp}")
                        else:
                            print(f"[CombatResolver] No damage applied to {target_name}.")

                        # --- End REVISED Logic ---

                    # Handle healing (increase HP up to max)
                    for target_name, heal in decision_response.get("healing", {}).items():
                        if not isinstance(heal, (int, float)):
                            try:
                                # Attempt to convert to int
                                heal = int(heal)
                            except (ValueError, TypeError):
                                print(f"[CombatResolver] Invalid healing value: {heal} for target {target_name}")
                                # Try to extract healing from dice results
                                healing_dice = [d for d in dice_results if "heal" in d.get("purpose", "").lower()]
                                if healing_dice:
                                    try:
                                        heal = int(healing_dice[0].get("result", 0))
                                        print(f"[CombatResolver] Using healing from dice result: {heal}")
                                    except (ValueError, TypeError):
                                        heal = 0
                                        print(f"[CombatResolver] Could not use dice healing value")
                                else:
                                    # Default healing amount
                                    heal = 10
                                    print(f"[CombatResolver] Using default healing amount of {heal}")
                                    
                        target = next((c for c in combatants if c.get("name") == target_name), None)
                        if target:
                            max_hp = target.get("max_hp", target.get("hp", 0))
                            new_hp = min(max_hp, target.get("hp", 0) + int(heal))
                            updates.append({"name": target_name, "hp": new_hp})
                            print(f"[CombatResolver] Applying {heal} healing to {target_name}: HP {target.get('hp', 0)} → {new_hp}")
                    
                    # Apply conditions if specified
                    for target_name, conditions in decision_response.get("conditions_applied", {}).items():
                        target = next((c for c in combatants if c.get("name") == target_name), None)
                        if target and isinstance(conditions, list):
                            if "conditions" not in target:
                                target["conditions"] = {}
                            
                            # Add each condition
                            for condition in conditions:
                                if isinstance(condition, str):
                                    target["conditions"][condition.lower()] = {"source": active_combatant.get("name", "Unknown")}
                                    print(f"[CombatResolver] Applied condition '{condition}' to {target_name}")
                                    
                            # Add condition update to updates list
                            condition_update = {"name": target_name, "conditions": target["conditions"]}
                            updates.append(condition_update)
                            
                    # Remove conditions if specified
                    for target_name, conditions in decision_response.get("conditions_removed", {}).items():
                        target = next((c for c in combatants if c.get("name") == target_name), None)
                        if target and "conditions" in target and isinstance(conditions, list):
                            # Remove each condition
                            for condition in conditions:
                                if isinstance(condition, str) and condition.lower() in target["conditions"]:
                                    del target["conditions"][condition.lower()]
                                    print(f"[CombatResolver] Removed condition '{condition}' from {target_name}")
                            
                            # Add condition update to updates list
                            condition_update = {"name": target_name, "conditions": target["conditions"]}
                            updates.append(condition_update)
                except Exception as e:
                    # Defensive: Never let update generation crash the turn
                    print(f"[CombatResolver] WARNING: Error translating resolution to updates: {e}")
                    import traceback
                    traceback.print_exc()

                # Fall back to any explicit updates provided by the LLM
                if not updates and isinstance(decision_response.get("updates"), list):
                    updates = decision_response["updates"]
                    print(f"[CombatResolver] Using explicit updates from resolution: {updates}")

                turn_result = {
                    "action": decision_response.get("action", "Unknown action"),
                    "narrative": narrative_text,
                    "dice": dice_results,
                    "updates": updates,
                }

                print(f"[CombatResolver] Final turn result: {turn_result}")
                return turn_result
            except Exception as e:
                print(f"[CombatResolver] Error processing turn resolution: {str(e)}")
                import traceback
                traceback.print_exc()
                
                # Even in case of error, return a valid turn result
                fallback_result = {
                    "action": decision_response.get("action", "Unknown action"),
                    "narrative": f"The {active_combatant.get('name', 'combatant')} acted, but a technical issue prevented recording the outcome.",
                    "dice": dice_results,
                    "updates": []
                }
                print(f"[CombatResolver] Using fallback turn result due to error: {fallback_result}")
                return fallback_result
        except Exception as e:
            # Final fallback - this should never be reached, but just in case
            print(f"[CombatResolver] Critical error in _process_turn: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                "action": "Unknown action",
                "narrative": f"The {active_combatant.get('name', 'Unknown')} attempted to act, but a critical error occurred.",
                "dice": [],
                "updates": []
            }

    def _process_death_save(self, combatant):
        """Process a death saving throw for a combatant."""
        import random
        
        # Set up death saves tracking if not present
        if "death_saves" not in combatant:
            combatant["death_saves"] = {
                "successes": 0,
                "failures": 0
            }
        
        # Roll a d20 for the death save
        roll = random.randint(1, 20)
        
        # Natural 20: regain 1 hit point
        if roll == 20:
            combatant["hp"] = 1
            combatant["status"] = "Conscious"
            print(f"[CombatResolver] {combatant['name']} rolled a natural 20 on death save and regains consciousness with 1 HP!")
            return
        
        # Natural 1: two failures
        if roll == 1:
            combatant["death_saves"]["failures"] += 2
            print(f"[CombatResolver] {combatant['name']} rolled a natural 1 on death save - two failures! Now at {combatant['death_saves']['failures']} failures.")
        # 10 or higher: success
        elif roll >= 10:
            combatant["death_saves"]["successes"] += 1
            print(f"[CombatResolver] {combatant['name']} succeeded on death save with {roll}! Now at {combatant['death_saves']['successes']} successes.")
        # Below 10: failure
        else:
            combatant["death_saves"]["failures"] += 1
            print(f"[CombatResolver] {combatant['name']} failed death save with {roll}! Now at {combatant['death_saves']['failures']} failures.")
        
        # Check results
        if combatant["death_saves"]["successes"] >= 3:
            combatant["status"] = "Stable"
            print(f"[CombatResolver] {combatant['name']} is now stable after 3 successful death saves!")
        elif combatant["death_saves"]["failures"] >= 3:
            combatant["status"] = "Dead"
            print(f"[CombatResolver] {combatant['name']} has died after 3 failed death saves!")

    def _process_hp_update(self, target_name, hp_update, current_hp):
        """
        Processes an HP update instruction, handling relative changes.
        
        Args:
            target_name: Name of the target combatant.
            hp_update: The HP update value (can be int, '+X', '-X').
            current_hp: The current HP of the target.
            
        Returns:
            The new HP value (int).
        """
        try:
            if isinstance(hp_update, str):
                if hp_update.startswith('+'):
                    change = int(hp_update[1:])
                    return current_hp + change
                elif hp_update.startswith('-'):
                    change = int(hp_update[1:])
                    return max(0, current_hp - change)
                else:
                    # Assume absolute value if no sign
                    return int(hp_update)
            elif isinstance(hp_update, (int, float)):
                # If it's already a number, assume absolute value
                return int(hp_update)
            else:
                print(f"[CombatResolver] Invalid hp_update type for {target_name}: {type(hp_update)}. Defaulting to current HP.")
                return current_hp
        except (ValueError, TypeError) as e:
            print(f"[CombatResolver] Error processing HP update '{hp_update}' for {target_name}: {e}. Defaulting to current HP.")
            return current_hp
        except Exception as e:
            # Catch any other unexpected errors during HP processing
            print(f"[CombatResolver] Unexpected error processing HP update for {target_name}: {e}. Defaulting to current HP.")
            return current_hp

    def _process_auras(self, active_combatant, all_combatants):
        """
        Process aura effects at the start of a combatant's turn
        
        Args:
            active_combatant: The combatant whose turn is starting
            all_combatants: List of all combatants in the encounter
            
        Returns:
            List of aura effect updates
        """
        updates = []
        
        # Ensure each combatant has auras detected and processed
        for combatant in all_combatants:
            # Add auras if not already present
            if "auras" not in combatant:
                self._add_auras_from_traits(combatant)
        
        # Check for aura effects from all combatants
        for c in all_combatants:
            if "auras" not in c:
                continue
                
            for aura_name, aura in c.get("auras", {}).items():
                # Skip self-auras that don't affect others (unless they're beneficial)
                if c.get("name") == active_combatant.get("name") and not aura.get("affects_self", False):
                    continue
                    
                # Skip auras that don't affect allies/enemies appropriately
                if aura.get("affects", "enemies") == "enemies" and c.get("type") == active_combatant.get("type"):
                    continue
                if aura.get("affects", "enemies") == "allies" and c.get("type") != active_combatant.get("type"):
                    continue
                
                # Check if this combatant is affected by the aura based on distance
                range_feet = aura.get("range", 10)  # Default 10 ft range
                distance = self._get_distance_between(c, active_combatant)
                
                if distance <= range_feet:
                    print(f"[CombatResolver] {c.get('name')} aura '{aura_name}' is in range ({distance}/{range_feet}ft) to affect {active_combatant.get('name')}")
                    effect = aura.get("effect", {})
                    effect_type = effect.get("type", "damage")
                    
                    # Process based on effect type
                    if effect_type == "damage":
                        # Get dice expression or default damage amount
                        damage_expr = effect.get("expression", "1d6")
                        
                        # Roll damage using random if dice_roller not available
                        try:
                            import re, random
                            # Simple dice parser for expressions like "2d6+3"
                            dice_match = re.match(r'(\d+)d(\d+)(?:\+(\d+))?', damage_expr)
                            if dice_match:
                                num_dice = int(dice_match.group(1))
                                dice_size = int(dice_match.group(2))
                                modifier = int(dice_match.group(3) or 0)
                                damage = sum(random.randint(1, dice_size) for _ in range(num_dice)) + modifier
                                print(f"[CombatResolver] Rolled aura damage: {damage_expr} = {damage}")
                            else:
                                # Default to fixed damage if expression parsing fails
                                damage = int(damage_expr) if damage_expr.isdigit() else 1
                                print(f"[CombatResolver] Using fixed aura damage: {damage}")
                        except Exception as e:
                            print(f"[CombatResolver] Error rolling aura damage: {str(e)}")
                            # Continue to next aura
                            continue
                        
                        # Apply damage to active combatant
                        damage_type = effect.get("damage_type", "fire")
                        old_hp = active_combatant.get("hp", 0)
                        active_combatant["hp"] = max(0, old_hp - damage)
                        
                        print(f"[CombatResolver] {c.get('name')}'s {aura_name} deals {damage} {damage_type} damage to {active_combatant.get('name')}")
                        print(f"[CombatResolver] {active_combatant.get('name')} HP: {old_hp} → {active_combatant['hp']}")
                        
                        # Record the update
                        updates.append({
                            "source": c.get("name", "Unknown"),
                            "source_type": c.get("type", "unknown"),
                            "aura": aura_name,
                            "target": active_combatant.get("name", "Unknown"),
                            "effect": f"{damage} {damage_type} damage",
                            "hp_before": old_hp,
                            "hp_after": active_combatant.get("hp", 0)
                        })
                        
                    elif effect_type == "condition":
                        # Add condition to active combatant
                        condition = effect.get("condition", "")
                        if condition:
                            if "conditions" not in active_combatant:
                                active_combatant["conditions"] = {}
                            
                            # Add condition
                            active_combatant["conditions"][condition] = {
                                "source": f"{c.get('name', 'Unknown')}'s {aura_name}",
                                "duration": effect.get("duration", 1)
                            }
                            
                            # Record the update
                            updates.append({
                                "source": c.get("name", "Unknown"),
                                "source_type": c.get("type", "unknown"), 
                                "aura": aura_name,
                                "target": active_combatant.get("name", "Unknown"),
                                "effect": f"Condition: {condition}"
                            })
        
        if not updates:
            print(f"[CombatResolver] No aura effects applied to {active_combatant.get('name', 'Unknown')}")
        
        return updates

