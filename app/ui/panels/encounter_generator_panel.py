"""
Encounter Generator Panel for DM Screen

Provides a UI for generating balanced D&D 5e encounters using LLM.
Includes automatic generation and saving of new monster stat blocks.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QSpinBox, QComboBox, QTextEdit, QGroupBox, QLineEdit,
    QMessageBox, QFormLayout, QCheckBox
)
from PySide6.QtCore import Qt, Signal
import json
import logging
import random

from app.ui.panels.base_panel import BasePanel
# Need access to db_manager for checking/saving monsters
from app.data.db_manager import DatabaseManager
from app.core.models.monster import Monster # Import Monster dataclass
from app.core.llm_integration import generate_monster_stat_block # Assuming this function exists

logger = logging.getLogger(__name__)

class EncounterGeneratorPanel(BasePanel):
    """
    Panel for generating D&D 5e encounters using LLM.
    """
    
    PANEL_TYPE = "encounter_generator"
    PANEL_TITLE = "Encounter Generator"
    PANEL_CATEGORY = "Campaign" # Or Utility?
    PANEL_DESCRIPTION = "Generate balanced encounters with narrative and tactical suggestions."
    
    # Signal for results
    generation_result = Signal(str, str) # response_str, error_str
    # Signal to add multiple monsters to combat tracker
    add_group_to_combat = Signal(list) # List of monster dicts

    def __init__(self, app_state, panel_id=None):
        panel_id = panel_id or self.PANEL_TYPE
        super().__init__(app_state, panel_id)
        
        self.llm_service = app_state.llm_service
        self.db_manager = app_state.db_manager # Get DB manager
        self.is_generating = False
        self.current_encounter_data = None # To store parsed encounter details
        
        self._init_ui()
        self._connect_signals()
        self._load_settings()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        
        # === Config ===
        config_group = QGroupBox("Encounter Parameters")
        config_layout = QFormLayout(config_group)
        
        self.level_spinbox = QSpinBox()
        self.level_spinbox.setRange(1, 20)
        self.level_spinbox.setValue(5)
        config_layout.addRow("Average Party Level:", self.level_spinbox)
        
        self.players_spinbox = QSpinBox()
        self.players_spinbox.setRange(1, 10)
        self.players_spinbox.setValue(4)
        config_layout.addRow("Number of Players:", self.players_spinbox)
        
        self.difficulty_combo = QComboBox()
        self.difficulty_combo.addItems(["Easy", "Medium", "Hard", "Deadly", "Random"])
        self.difficulty_combo.setCurrentText("Medium")
        config_layout.addRow("Desired Difficulty:", self.difficulty_combo)
        
        self.environment_input = QLineEdit()
        self.environment_input.setPlaceholderText("e.g., Forest, Cave, Dungeon room, Urban alley")
        config_layout.addRow("Environment/Terrain:", self.environment_input)
        
        self.context_input = QTextEdit()
        self.context_input.setPlaceholderText("Optional: Any specific context, recent events, or required monster types...")
        self.context_input.setMaximumHeight(60)
        config_layout.addRow("Context (Optional):", self.context_input)
        
        # Checkboxes for monster generation options
        checkbox_layout = QVBoxLayout()
        
        # Add checkbox for diverse monsters
        self.diverse_monsters_checkbox = QCheckBox("Generate diverse and interesting monsters")
        self.diverse_monsters_checkbox.setChecked(True)  # Enable by default
        checkbox_layout.addWidget(self.diverse_monsters_checkbox)
        
        # Add checkbox for rare/unique monsters
        self.rare_monsters_checkbox = QCheckBox("Prioritize rare/unique monsters")
        self.rare_monsters_checkbox.setChecked(True)  # Enable by default
        checkbox_layout.addWidget(self.rare_monsters_checkbox)
        
        config_layout.addRow("Options:", checkbox_layout)
        
        self.generate_button = QPushButton("Generate Encounter")
        config_layout.addRow(self.generate_button)
        
        main_layout.addWidget(config_group)
        
        # === Results ===
        results_group = QGroupBox("Generated Encounter")
        results_layout = QVBoxLayout(results_group)
        
        self.results_display = QTextEdit()
        self.results_display.setReadOnly(True)
        self.results_display.setPlaceholderText("Generated encounter details will appear here...")
        results_layout.addWidget(self.results_display)
        
        self.add_to_combat_button = QPushButton("Add Monsters to Combat Tracker")
        self.add_to_combat_button.setEnabled(False) # Disabled initially
        results_layout.addWidget(self.add_to_combat_button)
        
        main_layout.addWidget(results_group)
        main_layout.addStretch()

    def _connect_signals(self):
        self.generate_button.clicked.connect(self._generate_encounter)
        self.generation_result.connect(self._process_generation_ui)
        self.add_to_combat_button.clicked.connect(self._add_encounter_to_combat)
        # Connect the add_group_to_combat signal later in PanelManager

    def _load_settings(self):
        pass # Load models if needed

    def _generate_encounter(self):
        if self.is_generating:
            return
        
        params = self._get_generation_params()
        prompt = self._create_encounter_prompt(params)
        
        if not hasattr(self.llm_service, 'generate_completion_async'):
            QMessageBox.warning(self, "Error", "LLM Service not available.")
            return

        try:
            available_models = self.llm_service.get_available_models()
            if not available_models:
                QMessageBox.warning(self, "Error", "No LLM models configured.")
                return
            model_id = available_models[0]["id"]

            self.is_generating = True
            self.generate_button.setEnabled(False)
            self.generate_button.setText("Generating...")
            self.results_display.setPlainText("Generating encounter...")
            self.add_to_combat_button.setEnabled(False)
            self.current_encounter_data = None

            print(f"--- Encounter Gen Prompt (Model: {model_id}) ---")
            print(prompt)
            print("---------------------------------------------")

            self.llm_service.generate_completion_async(
                model=model_id,
                messages=[{"role": "user", "content": prompt}],
                callback=self._handle_generation_result,
                temperature=0.7,
                max_tokens=4000  # Increased to 4000 for longer responses
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to start generation: {e}")
            self._reset_ui_state()

    def _get_generation_params(self):
        return {
            "level": self.level_spinbox.value(),
            "players": self.players_spinbox.value(),
            "difficulty": self.difficulty_combo.currentText(),
            "environment": self.environment_input.text().strip(),
            "context": self.context_input.toPlainText().strip(),
            "diverse": self.diverse_monsters_checkbox.isChecked(),
            "rare": self.rare_monsters_checkbox.isChecked()
        }

    def _create_encounter_prompt(self, params: dict) -> str:
        # Get a list of available monsters from the database to hint to the LLM
        monster_names = []
        try:
            # Get just a small sample of monster names for reference
            monster_results = self.db_manager.get_all_monster_names(include_custom=True, include_standard=True)
            if monster_results:
                # Take a small random sample to avoid biasing toward common monsters
                if len(monster_results) > 15:
                    monster_names = [m['name'] for m in random.sample(monster_results, 15)]
                else:
                    monster_names = [m['name'] for m in monster_results]
                logger.debug(f"Retrieved {len(monster_names)} monster names for prompt")
        except Exception as e:
            logger.error(f"Error retrieving monster names for prompt: {e}")
        
        # Basic prompt structure
        prompt = f"""Generate a D&D 5e encounter based on these parameters. Respond ONLY with a JSON object.

Parameters:
- Average Party Level: {params['level']}
- Number of Players: {params['players']}
- Desired Difficulty: {params['difficulty']}
- Environment: {params['environment']}
- Context: {params['context'] if params['context'] else 'None'}
- Diverse Monsters: {params['diverse']}
- Prioritize Rare/Unique Monsters: {params['rare']}

Instructions:
1. Create a balanced, diverse encounter matching the difficulty, player count, and level.
2. List the specific monster types and quantities (e.g., ["Goblin Scout", "Goblin Shaman", "Goblin Boss"]).
3. Provide a brief narrative description setting the scene (2-3 sentences).
4. Suggest 1-2 simple tactical considerations for the monsters.
5. Format the entire response as a single JSON object with keys: 'monsters' (list of strings), 'narrative' (string), 'tactics' (string).

IMPORTANT: 
- CREATE UNCOMMON AND UNIQUE MONSTERS! Prefer generating new and interesting monsters over using common ones.
- Create interesting and varied encounters with diverse monster combinations.
- Avoid using multiple copies of the exact same monster type.
- Include rare, unusual, and specialized variants of monsters - these will be automatically generated.
- Match monsters logically to the environment and include interesting terrain features.
- Consider adding environmental hazards, traps, or unique combat conditions to make encounters more dynamic.
- Feel free to invent creative monster variants with specialized roles (e.g., "Frost Goblin Shaman", "Dire Wolf Alpha").
"""

        # Add monster suggestions if available, but present them differently
        if monster_names:
            prompt += f"""
Some example monsters (for reference only):
{', '.join(monster_names)}

DO NOT FEEL LIMITED by these examples. The system can generate ANY monster you specify, including rare, unique or specialized variants. {'STRONGLY prioritize creating new, rare monsters' if params['rare'] else 'Prioritize creating interesting and unusual monster combinations'}.
"""

        prompt += """
Example JSON:
{
  "monsters": ["Goblin Pyromancer", "Shadow Wolf", "Thorn Sprite"],
  "narrative": "Flickering flames illuminate the darkened chamber as a goblin wielding burning magic commands a shadowy wolf. From the surrounding plants, tiny thorn-covered fey creatures emerge, their eyes gleaming with malice.",
  "tactics": "The Goblin Pyromancer stays behind cover, launching fire spells while the Shadow Wolf flanks enemies. The Thorn Sprites attack in bursts, retreating into the vegetation between strikes."
}

**IMPORTANT: Output ONLY the JSON object. No extra text before or after.**
"""
        return prompt

    def _handle_generation_result(self, response, error):
        """Handle the result of the LLM generation"""
        # Log the response or error
        if error:
            logger.error(f"LLM generation error: {error}")
        elif response is None:
            logger.error("LLM generation returned None response")
            # Convert None to empty string to avoid further errors
            response = ""
        elif not response:
            logger.warning("LLM generation returned empty string response")
        else:
            # Log the first 100 characters of the response to avoid flooding logs
            logger.info(f"LLM generation complete. Response preview: {str(response)[:100]}...")
            
        # Pass to main thread for processing
        self.generation_result.emit(response, error)

    def _process_generation_ui(self, response, error):
        """Process the LLM generation result in the UI thread"""
        self._reset_ui_state()
        
        if error:
            error_msg = f"Encounter generation failed: {error}"
            logger.error(error_msg)
            QMessageBox.critical(self, "Error", error_msg)
            self.results_display.setPlainText(f"Error: {error}")
            return
        
        # Debug log the response type and value
        logger.debug(f"Response type: {type(response)}, Is None: {response is None}, Is empty: {not bool(response)}")
            
        if response is None or not response:
            error_msg = f"Received empty response from LLM. Response value: '{response}'"
            logger.error(error_msg)
            QMessageBox.warning(self, "Empty Response", 
                "The LLM returned an empty response. This may be due to:\n"
                "- API rate limits\n"
                "- Connection issues\n"
                "- Server-side filtering\n\n"
                "Please try again or check your API key settings.")
            self.results_display.setPlainText("Error: Empty response received.")
            return
        
        try:
            # Log the raw response to help with debugging
            logger.debug(f"Raw LLM response: {response}")
            
            # Clean potential markdown
            clean_response = response.strip()
            if clean_response.startswith("```json"):
                clean_response = clean_response[7:]
            if clean_response.endswith("```"):
                clean_response = clean_response[:-3]
            
            clean_response = clean_response.strip()
            
            if not clean_response:
                logger.error("Response was only markdown fences with no content")
                QMessageBox.warning(self, "Invalid Response", 
                    "The LLM returned markdown without content. Please try again.")
                self.results_display.setPlainText("Error: Invalid response format.")
                return
                
            logger.debug(f"Cleaned response for parsing: {clean_response}")
            
            parsed_data = json.loads(clean_response)
            
            if not isinstance(parsed_data, dict):
                logger.error(f"Parsed data is not a dictionary: {type(parsed_data)}")
                QMessageBox.warning(self, "Invalid Format", "Response is not a valid JSON object.")
                self.results_display.setPlainText(f"Error: Invalid JSON format. Got {type(parsed_data)}.")
                return
                
            # Validate required keys
            required_keys = ['monsters', 'narrative', 'tactics']
            missing_keys = [key for key in required_keys if key not in parsed_data]
            
            if missing_keys:
                logger.warning(f"Response missing required keys: {missing_keys}")
                # Still continue, but with a warning
                QMessageBox.warning(self, "Incomplete Response", 
                    f"The response is missing these required fields: {', '.join(missing_keys)}.\n"
                    "The encounter may be incomplete.")
            
            # Pre-check monster existence as soon as we have the encounter data
            monsters_list = parsed_data.get("monsters", [])
            if monsters_list:
                # Create a status list showing what monsters already exist
                monster_status = []
                for name in monsters_list:
                    monster_exists = self.db_manager.get_monster_by_name(name) is not None
                    monster_status.append(f"{'✓' if monster_exists else '⊕'} {name}")
                
                # Add the status to parsed_data for display
                parsed_data["monster_status"] = monster_status
            
            self.current_encounter_data = parsed_data  # Store for adding to combat
            
            # Display formatted results
            display_text = f"## Encounter Details\n\n"
            display_text += f"**Narrative:**\n{parsed_data.get('narrative', 'N/A')}\n\n"
            display_text += "**Monsters:**\n"
            
            # If we have status info, use it for nicer display
            if "monster_status" in parsed_data:
                for status in parsed_data["monster_status"]:
                    display_text += f"- {status} {'(in database)' if status.startswith('✓') else '(will be generated)'}\n"
            else:
                display_text += f"- {'\n- '.join(parsed_data.get('monsters', []))}\n"
            
            display_text += f"\n**Tactics:**\n{parsed_data.get('tactics', 'N/A')}"
            
            self.results_display.setPlainText(display_text)
            self.add_to_combat_button.setEnabled(True)
            
        except json.JSONDecodeError as e:
            error_msg = f"Failed to parse LLM response as JSON: {e}\nRaw response:\n{response}"
            logger.error(error_msg)
            QMessageBox.critical(self, "Parsing Error", error_msg)
            self.results_display.setPlainText(error_msg)
            self.current_encounter_data = None
        except Exception as e:
            error_msg = f"Error processing LLM response: {e}"
            logger.error(error_msg, exc_info=True)
            QMessageBox.critical(self, "Error", error_msg)
            self.results_display.setPlainText(error_msg)
            self.current_encounter_data = None

    def _add_encounter_to_combat(self):
        """Add monsters from the current encounter to the combat tracker."""
        if not self.current_encounter_data:
            logger.warning("No encounter data to add to combat")
            QMessageBox.warning(self, "No Encounter Data", 
                               "No encounter has been generated yet.")
            return
        
        monsters_to_add = []
        errors = []
        
        monsters_list = self.current_encounter_data.get("monsters", [])
        if not monsters_list:
            logger.warning("No monsters in encounter data")
            QMessageBox.warning(self, "No Monsters", 
                               "The current encounter doesn't contain any monsters.")
            return
        
        logger.info(f"Processing {len(monsters_list)} monsters for combat")
        
        for name in monsters_list:
            try:
                # Check if monster exists in DB
                monster_data = self.db_manager.get_monster_by_name(name)
                
                if monster_data:
                    logger.info(f"Found monster '{name}' in DB")
                    monsters_to_add.append(monster_data.to_dict())
                else:
                    logger.info(f"Monster '{name}' not found in DB. Attempting generation...")
                    # Monster doesn't exist - Generate using LLM
                    try:
                        # Call LLM to generate stat block
                        logger.debug(f"Before calling generate_monster_stat_block for '{name}'")
                        monster_obj = generate_monster_stat_block(self.llm_service, name)
                        
                        if not monster_obj:
                            # LLM failed or returned invalid data
                            error_msg = f"LLM failed to generate a valid stat block for '{name}'."
                            logger.error(error_msg)
                            errors.append(error_msg)
                            
                            QMessageBox.warning(self, "Generation Failed", 
                                f"Could not generate stats for '{name}'. This monster will be skipped.")
                            continue  # Skip this monster but continue with others
                        
                        # Debug: Check returned monster before saving
                        logger.debug(f"Generated monster: name={monster_obj.name}, type={monster_obj.type}, CR={monster_obj.challenge_rating}")
                        logger.debug(f"Monster has {len(monster_obj.actions) if monster_obj.actions else 0} actions")
                        
                        # Mark as custom and generated
                        monster_obj.is_custom = True
                        monster_obj.source = "AI Generated" 
                        
                        logger.info(f"Successfully generated stat block for '{name}'. Saving to database...")
                        
                        # Save to custom DB
                        saved_monster = self.db_manager.save_custom_monster(monster_obj)
                        
                        # Debug: Check what was returned after save
                        logger.debug(f"After save: saved_monster type: {type(saved_monster)}")
                        logger.debug(f"After save: saved_monster is None? {saved_monster is None}")
                        if saved_monster:
                            logger.debug(f"After save: saved_monster.id = {saved_monster.id if hasattr(saved_monster, 'id') else 'no id attribute'}")
                        
                        if not saved_monster or not hasattr(saved_monster, 'id'):
                            # Database save failed or returned wrong type
                            error_msg = f"Failed to save generated monster '{name}' to the database. Type returned: {type(saved_monster)}"
                            logger.error(error_msg)
                            errors.append(error_msg)
                            
                            QMessageBox.warning(self, "Save Failed", 
                                f"Could not save '{name}' to database. This monster will be skipped.")
                            continue  # Skip this monster but continue with others
                        
                        logger.info(f"Saved new monster '{name}' to DB with ID: {saved_monster.id}")
                        
                        # Add the newly saved monster to the list for the combat tracker
                        monster_dict = saved_monster.to_dict()
                        logger.debug(f"Adding to combat tracker: monster_dict has {len(monster_dict)} keys")
                        monsters_to_add.append(monster_dict)
                        
                    except Exception as gen_err:
                        logger.error(f"Error during monster generation for '{name}': {gen_err}")
                        errors.append(f"Error generating '{name}': {str(gen_err)}")
                        
                        QMessageBox.warning(self, "Generation Error", 
                            f"Error processing '{name}': {str(gen_err)}\nThis monster will be skipped.")
                        continue  # Skip this monster but continue with others

            except Exception as db_err:
                logger.error(f"Error processing monster '{name}': {db_err}")
                errors.append(f"Error with '{name}': {str(db_err)}")
                
                QMessageBox.warning(self, "Database Error", 
                    f"Error processing '{name}': {str(db_err)}\nThis monster will be skipped.")
                continue  # Skip this monster but continue with others
        
        # If we have any monsters to add, emit the signal
        if monsters_to_add:
            logger.info(f"Adding {len(monsters_to_add)} monsters to combat tracker")
            self.add_group_to_combat.emit(monsters_to_add)
            
            # Show summary message with any errors
            message = f"Added {len(monsters_to_add)} monsters to combat tracker."
            if errors:
                message += f"\n\nSkipped {len(errors)} monsters due to errors:"
                for error in errors[:5]:  # Show first 5 errors only
                    message += f"\n- {error}"
                if len(errors) > 5:
                    message += f"\n- ... and {len(errors) - 5} more errors."
            
            QMessageBox.information(self, "Monsters Added", message)
        else:
            # No monsters were successfully added
            error_msg = "Failed to add any monsters to combat tracker."
            if errors:
                error_msg += " Errors encountered:"
                for error in errors[:5]:  # Show first 5 errors only
                    error_msg += f"\n- {error}"
                if len(errors) > 5:
                    error_msg += f"\n- ... and {len(errors) - 5} more errors."
            
            logger.error(error_msg)
            QMessageBox.critical(self, "Addition Failed", error_msg)

    def _reset_ui_state(self):
        self.is_generating = False
        self.generate_button.setEnabled(True)
        self.generate_button.setText("Generate Encounter")
        # Keep add button enabled if data exists
        self.add_to_combat_button.setEnabled(self.current_encounter_data is not None)

# REMOVE THE INVALID MARKER BELOW 