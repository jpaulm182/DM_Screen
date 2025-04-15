"""
Core component for resolving combat encounters using LLM.

This class takes the current combat state and uses an LLM to generate
narrative results, update combatant statuses, and potentially make
tactical decisions.
"""

from app.core.llm_service import LLMService
import json # Import json for parsing
import re

class CombatResolver:
    """
    Handles the logic for resolving combat using an LLM.
    """

    def __init__(self, llm_service: LLMService):
        """Initialize the CombatResolver with the LLM service."""
        self.llm_service = llm_service

    def resolve_combat_async(self, combat_state: dict, callback):
        """
        Asynchronously resolve the combat using the LLM.

        Args:
            combat_state: A dictionary representing the current state of the combat 
                          (combatants, round, environment, etc.).
            callback: A function to call with the results (narrative, updates) 
                      or an error message.
        """
        print("CombatResolver.resolve_combat_async called with state:", combat_state)
        
        # 1. Construct a detailed prompt based on combat_state.
        prompt = self._create_combat_prompt(combat_state)
        
        # 2. Call self.llm_service.generate_completion_async.
        # Ensure LLM service and method exist
        if not hasattr(self.llm_service, 'generate_completion_async'):
            callback(None, "LLM service is not available or does not support async generation.")
            return
            
        try:
            # Get the first available model ID
            available_models = self.llm_service.get_available_models()
            if not available_models:
                callback(None, "No LLM models are available or configured. Please check API keys.")
                return
            model_id = available_models[0]["id"] # Use the ID of the first available model
                 
            print(f"--- Combat Resolver Prompt (Model: {model_id}) ---")
            print(prompt)
            print("---------------------------------------------")

            # 3. Call the LLM service, passing _handle_llm_response as the callback
            self.llm_service.generate_completion_async(
                model=model_id,
                messages=[{"role": "user", "content": prompt}],
                callback=lambda response, error: self._handle_llm_response(response, error, callback),
                temperature=0.6, # Slightly lower temp for more predictable combat results
                max_tokens=1000 # Adjust as needed
            )
        except Exception as e:
            callback(None, f"Error calling LLM service: {str(e)}")

    def resolve_combat_turn_by_turn_async(self, combat_state: dict, dice_roller, callback):
        """
        Asynchronously resolve combat turn-by-turn using the LLM and dice roller.
        Args:
            combat_state: The current combat state dict (combatants, round, etc.)
            dice_roller: A callable that takes a dice expression (e.g., '1d20+5') and returns the result.
            callback: Function to call with the final results or error.
        """
        import copy
        import threading
        
        # Make a deep copy of the combat state to avoid mutating the original
        state = copy.deepcopy(combat_state)
        log = []  # Log of actions for transparency
        
        def run_resolution():
            try:
                round_num = state.get("round", 1)
                combatants = state.get("combatants", [])
                initiative_order = sorted(range(len(combatants)), key=lambda i: -combatants[i]["initiative"])  # Descending
                active_combatants = [i for i in initiative_order if combatants[i]["hp"] > 0]
                turn_idx = state.get("current_turn_index", 0)
                
                # Main combat loop
                while len([c for c in combatants if c["hp"] > 0]) > 1:
                    for idx in active_combatants:
                        c = combatants[idx]
                        if c["hp"] <= 0:
                            continue  # Skip dead/unconscious
                        # Build prompt for LLM to decide action
                        prompt = self._create_turn_prompt(state, idx)
                        print(f"[CombatResolver] About to call LLM for action suggestion for {c['name']} (turn {idx})")
                        # Get LLM action suggestion (sync for simplicity)
                        action = self.llm_service.generate_completion(
                            model=self.llm_service.get_available_models()[0]["id"],
                            messages=[{"role": "user", "content": prompt}],
                            temperature=0.5,
                            max_tokens=400
                        )
                        print(f"[CombatResolver] Received LLM action suggestion for {c['name']} (turn {idx})")
                        print(f"[CombatResolver] Raw LLM action response for {c['name']} (turn {idx}): {action!r}")
                        # Parse action and dice requests
                        # For simplicity, expect LLM to output a JSON with {"action": ..., "dice": ["1d20+5", ...]}
                        try:
                            # Extract the first {...} JSON block from the response
                            json_match = re.search(r'\{[\s\S]*\}', action)
                            if json_match:
                                json_str = json_match.group(0)
                                action_data = json.loads(json_str)
                            else:
                                callback(None, f"Could not find JSON in LLM action response: {action}")
                                return
                        except Exception:
                            callback(None, f"LLM action parse error: {action}")
                            return
                        # Roll dice as requested
                        dice_results = []
                        for expr in action_data.get("dice", []):
                            result = dice_roller(expr)
                            dice_results.append({"expr": expr, "result": result})
                        # Build result prompt for LLM to narrate and apply outcome
                        result_prompt = self._create_result_prompt(state, idx, action_data, dice_results)
                        print(f"[CombatResolver] About to call LLM for result narration for {c['name']} (turn {idx})")
                        result = self.llm_service.generate_completion(
                            model=self.llm_service.get_available_models()[0]["id"],
                            messages=[{"role": "user", "content": result_prompt}],
                            temperature=0.5,
                            max_tokens=400
                        )
                        print(f"[CombatResolver] Received LLM result narration for {c['name']} (turn {idx})")
                        print(f"[CombatResolver] Raw LLM result narration for {c['name']} (turn {idx}): {result!r}")
                        try:
                            # Extract the first {...} JSON block from the response
                            json_match = re.search(r'\{[\s\S]*\}', result)
                            if json_match:
                                json_str = json_match.group(0)
                                result_data = json.loads(json_str)
                            else:
                                callback(None, f"Could not find JSON in LLM result: {result}")
                                return
                        except Exception:
                            callback(None, f"LLM result parse error: {result}")
                            return
                        # Apply updates to combatants
                        for update in result_data.get("updates", []):
                            for c2 in combatants:
                                if c2["name"] == update["name"]:
                                    if "hp" in update:
                                        c2["hp"] = update["hp"]
                                    if "status" in update:
                                        c2["status"] = update["status"]
                        # Log the action
                        log.append({
                            "turn": idx,
                            "actor": c["name"],
                            "action": action_data.get("action", ""),
                            "dice": dice_results,
                            "result": result_data.get("narrative", "")
                        })
                        # Remove dead combatants from active list
                        active_combatants = [i for i in initiative_order if combatants[i]["hp"] > 0]
                        if len(active_combatants) <= 1:
                            break
                    round_num += 1
                    state["round"] = round_num
                # Prepare final summary
                survivors = [c for c in combatants if c["hp"] > 0]
                summary = {
                    "narrative": f"Combat ended after {round_num} rounds. Survivors: {[c['name'] for c in survivors]}",
                    "updates": combatants,
                    "log": log
                }
                callback(summary, None)
            except Exception as e:
                callback(None, f"Error in turn-by-turn resolution: {e}")
        # Run in a background thread
        threading.Thread(target=run_resolution).start()

    def _create_combat_prompt(self, combat_state: dict) -> str:
        """Construct the prompt for the LLM based on combat state."""
        round_num = combat_state.get("round", 1)
        turn_idx = combat_state.get("current_turn_index", 0)
        combatants = combat_state.get("combatants", [])
        
        current_combatant_name = "N/A"
        if 0 <= turn_idx < len(combatants):
            current_combatant_name = combatants[turn_idx].get("name", "Unknown")

        combatant_lines = []
        for combatant in combatants:
            name = combatant.get("name", "Unknown")
            hp = combatant.get("hp", 0)
            max_hp = combatant.get("max_hp") or hp # Use current HP if max_hp is missing
            ac = combatant.get("ac", 10)
            status = combatant.get("status", "OK")
            conc = combatant.get("concentration", False)
            notes = combatant.get("notes", "")
            
            line = f"- Name: {name}\n  HP: {hp}/{max_hp}\n  AC: {ac}\n  Status: {status}\n  Concentrating: {conc}\n  Notes: {notes}"
            combatant_lines.append(line)
            
        combatants_str = "\n".join(combatant_lines)

        prompt = f"""
You are a Dungeons & Dragons 5e Dungeon Master AI. Resolve the current combat encounter based on the state provided below. Provide a brief, engaging narrative summary of the likely outcome of the combat, focusing on the key actions and results. Then, provide a JSON object containing updates to the combatants' status.

**IMPORTANT: Your entire response MUST be ONLY the JSON object specified below, with no introductory text, code block formatting, or any characters outside the JSON structure.**

Combat State:
Round: {round_num}
Current Turn: Combatant '{current_combatant_name}' (Index {turn_idx})

Combatants:
{combatants_str}

Instructions:
1. Analyze the combat state, considering HP, AC, status, and typical creature/character behavior. Assume standard tactics unless notes suggest otherwise. Prioritize actions for the current combatant if relevant, but resolve the overall likely outcome.
2. Generate a concise narrative summary (2-4 sentences) describing the resolution.
3. Generate a JSON object under the key \"updates\" containing a list of combatants whose state changed. Each entry should be a dictionary with at least a \"name\" key matching a combatant. Include \"hp\" and/or \"status\" keys ONLY if they changed. **If status becomes \"Dead\", HP should be 0.** Possible statuses include \"Unconscious\", \"Dead\", \"Fled\", or specific D&D conditions if applicable.

**Your response must start with `{{` and end with `}}`.**

Example Output Format:
{{
  \"narrative\": \"The adventurers press their advantage. The fighter cleaves through the lead goblin, while the remaining goblins, seeing their leader fall, turn and flee into the darkness.\",
  \"updates\": [
    {{\"name\": \"Goblin Boss\", \"hp\": 0, \"status\": \"Dead\"}},
    {{\"name\": \"Goblin 1\", \"status\": \"Fled\"}},
    {{\"name\": \"Goblin 2\", \"status\": \"Fled\"}}
  ]
}}

Combat Details for Resolution:

Round: {round_num}
Current Turn Index: {turn_idx}

Combatants List:
{combatants_str}
"""
        return prompt

    def _create_turn_prompt(self, state, idx):
        """
        Create a prompt for the LLM to decide the action for a single combatant's turn.
        """
        combatants = state.get("combatants", [])
        c = combatants[idx]
        # Include stats, skills, abilities, inventory, and visible state
        prompt = f"""
You are a D&D 5e DM AI. It is {c['name']}'s turn. Here are their stats and the combat state:

Combatant:
Name: {c['name']}
HP: {c['hp']}/{c.get('max_hp', c['hp'])}
AC: {c.get('ac', 10)}
Status: {c.get('status', 'OK')}
Inventory: {c.get('inventory', 'Unknown')}
Abilities: {c.get('abilities', 'Unknown')}
Skills: {c.get('skills', 'Unknown')}

Other Combatants:
"""
        for i, other in enumerate(combatants):
            if i == idx:
                continue
            prompt += f"- {other['name']} (HP: {other['hp']}, AC: {other.get('ac', 10)}, Status: {other.get('status', 'OK')})\n"
        prompt += "\nWhat is the most likely action for this turn? Output a JSON with 'action' (string) and 'dice' (list of dice expressions needed for this action, e.g., ['1d20+5', '1d8+3'])."
        return prompt

    def _create_result_prompt(self, state, idx, action_data, dice_results):
        """
        Create a prompt for the LLM to narrate and apply the outcome of the action, given the dice results.
        """
        combatants = state.get("combatants", [])
        c = combatants[idx]
        prompt = f"""
You are a D&D 5e DM AI. {c['name']} attempted the following action: {action_data.get('action', '')}.
Here are the dice results: {dice_results}.
Here is the current combat state:
"""
        for other in combatants:
            prompt += f"- {other['name']} (HP: {other['hp']}, AC: {other.get('ac', 10)}, Status: {other.get('status', 'OK')})\n"
        prompt += "\nNarrate the outcome in 1-2 sentences, and output a JSON with 'narrative' and 'updates' (list of dicts with 'name', 'hp', and/or 'status' for changed combatants)."
        return prompt

    def _handle_llm_response(self, response: str | None, error: str | None, original_callback):
        """Parse the LLM response and call the original callback."""
        if error:
            original_callback(None, f"LLM Error: {error}")
            return
            
        if not response:
             original_callback(None, "LLM returned an empty response.")
             return
             
        try:
            # The response should be a JSON string directly
            # Clean up potential markdown code blocks if present
            if response.strip().startswith("```json"):
                response = response.strip()[7:]
            if response.strip().endswith("```"):
                response = response.strip()[:-3]
                
            parsed_result = json.loads(response.strip())
            
            # Basic validation of the parsed structure
            if "narrative" not in parsed_result or "updates" not in parsed_result:
                 raise ValueError("LLM response missing 'narrative' or 'updates' key.")
            if not isinstance(parsed_result["updates"], list):
                 raise ValueError("'updates' key must contain a list.")
                 
            original_callback(parsed_result, None)
            
        except json.JSONDecodeError as json_err:
            error_msg = f"Failed to parse LLM JSON response: {json_err}\nResponse received:\n{response}"
            print(error_msg) # Log the problematic response
            original_callback(None, error_msg)
        except ValueError as val_err:
             error_msg = f"Invalid LLM response structure: {val_err}\nResponse received:\n{response}"
             print(error_msg) # Log the problematic response
             original_callback(None, error_msg)
        except Exception as e:
            error_msg = f"Unexpected error handling LLM response: {str(e)}\nResponse received:\n{response}"
            print(error_msg) # Log the problematic response
            original_callback(None, error_msg) 