"""
Treasure Generator Panel for DM Screen

Provides a UI for generating treasure hoards and magic items using LLM.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QSpinBox, QComboBox, QTextEdit, QGroupBox, QMessageBox
)
from PySide6.QtCore import Qt, Signal
import json # For parsing LLM response

from app.ui.panels.base_panel import BasePanel


class TreasureGeneratorPanel(BasePanel):
    """
    Panel for generating treasure hoards and magic items using LLM.
    """
    
    PANEL_TYPE = "treasure_generator"
    PANEL_TITLE = "Treasure Generator"
    PANEL_CATEGORY = "Campaign" # Or perhaps Utility? Let's start with Campaign
    PANEL_DESCRIPTION = "Generate treasure hoards and magic items based on CR, party level, and context."
    
    # Signal for thread-safe communication (similar to other generator panels)
    generation_result = Signal(str, str) # response, error

    def __init__(self, app_state, panel_id=None):
        """Initialize the Treasure Generator panel."""
        panel_id = panel_id or self.PANEL_TYPE
        super().__init__(app_state, panel_id)
        
        self.llm_service = app_state.llm_service
        self.llm_data_manager = app_state.llm_data_manager
        self.is_generating = False
        self.current_treasure_data = None # Store the last generated data
        
        self._init_ui()
        self._connect_signals()
        self._load_settings()

    def _init_ui(self):
        """Initialize the panel UI."""
        main_layout = QVBoxLayout(self)
        
        # === Configuration Section ===
        config_group = QGroupBox("Generation Parameters")
        config_layout = QVBoxLayout(config_group)
        
        # Input Row 1: CR / Party Level
        input_row1 = QHBoxLayout()
        input_row1.addWidget(QLabel("Challenge Rating (CR): Goblins...Level 20))"))
        self.cr_spinbox = QSpinBox()
        self.cr_spinbox.setRange(0, 30) # CR 0 to 30
        self.cr_spinbox.setValue(5)
        input_row1.addWidget(self.cr_spinbox)
        
        input_row1.addWidget(QLabel("Avg Party Level:"))
        self.level_spinbox = QSpinBox()
        self.level_spinbox.setRange(1, 20)
        self.level_spinbox.setValue(5)
        input_row1.addWidget(self.level_spinbox)
        input_row1.addStretch()
        config_layout.addLayout(input_row1)

        # Input Row 2: Treasure Type / Context
        input_row2 = QHBoxLayout()
        input_row2.addWidget(QLabel("Type:"))
        self.type_combo = QComboBox()
        self.type_combo.addItems(["Hoard", "Individual Monster", "Magic Item Only", "Mundane Items"])
        input_row2.addWidget(self.type_combo)
        
        input_row2.addWidget(QLabel("Context (Optional):"))
        self.context_input = QTextEdit()
        self.context_input.setPlaceholderText("e.g., Dragon's lair, Bandit camp, Ancient tomb")
        input_row2.addWidget(self.context_input)
        config_layout.addLayout(input_row2)

        # Generate Button
        self.generate_button = QPushButton("Generate Treasure")
        config_layout.addWidget(self.generate_button)
        
        main_layout.addWidget(config_group)

        # === Results Section ===
        results_group = QGroupBox("Generated Treasure")
        results_layout = QVBoxLayout(results_group)
        
        self.results_display = QTextEdit()
        self.results_display.setReadOnly(True)
        self.results_display.setPlaceholderText("Generated treasure will appear here...")
        results_layout.addWidget(self.results_display)
        
        # Add Save to Notes button
        self.save_to_notes_button = QPushButton("Save to Session Notes")
        self.save_to_notes_button.setEnabled(False) # Disabled initially
        results_layout.addWidget(self.save_to_notes_button)
        
        main_layout.addWidget(results_group)
        main_layout.addStretch()

    def _connect_signals(self):
        """Connect UI signals to handlers."""
        self.generate_button.clicked.connect(self._generate_treasure)
        # Connect generation_result signal to a UI update slot
        self.generation_result.connect(self._process_generation_ui)
        # Connect save button
        self.save_to_notes_button.clicked.connect(self._save_to_notes)

    def _load_settings(self):
        """Load any necessary settings (e.g., models)."""
        # TODO: Load available LLM models if needed for selection
        pass

    def _generate_treasure(self):
        """Placeholder for starting the treasure generation process."""
        if self.is_generating:
            return
            
        # 1. Gather parameters
        params = self._get_generation_params()
        
        # 2. Create prompt for LLM
        prompt = self._create_treasure_prompt(params)

        # 3. Call LLM service asynchronously
        if not hasattr(self.llm_service, 'generate_completion_async'):
            QMessageBox.warning(self, "Error", "LLM Service not available.")
            return
            
        try:
            available_models = self.llm_service.get_available_models()
            if not available_models:
                QMessageBox.warning(self, "Error", "No LLM models configured.")
                return
            model_id = available_models[0]["id"]

            # 4. Update UI state
            self.is_generating = True
            self.generate_button.setEnabled(False)
            self.generate_button.setText("Generating...")
            self.results_display.setPlainText("Generating treasure with AI...")

            print(f"--- Treasure Generator Prompt (Model: {model_id}) ---")
            print(prompt)
            print("----------------------------------------------")

            self.llm_service.generate_completion_async(
                model=model_id,
                messages=[{"role": "user", "content": prompt}],
                callback=self._handle_generation_result, # Use background handler
                temperature=0.7, 
                max_tokens=1500 # Allow more tokens for detailed treasure/items
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to start generation: {e}")
            self._reset_ui_state()

    def _get_generation_params(self):
        """Gather parameters from the UI fields."""
        return {
            "cr": self.cr_spinbox.value(),
            "level": self.level_spinbox.value(),
            "type": self.type_combo.currentText(),
            "context": self.context_input.toPlainText().strip()
        }

    def _create_treasure_prompt(self, params: dict) -> str:
        """Create the prompt for the LLM based on parameters."""
        # Start with base instructions and parameters
        prompt_lines = [
            "Generate Dungeons & Dragons 5e treasure based on the following parameters. Respond ONLY with a JSON object containing the treasure details.",
            "",
            "Parameters:",
            f"- Type: {params['type']}",
            f"- Challenge Rating (CR) / Difficulty: {params['cr']}",
            f"- Average Party Level: {params['level']}"
        ]
        
        if params["context"]:
            prompt_lines.append(f"- Context: {params['context']}")
            
        prompt_lines.extend([
            "",
            "Instructions:"
        ])
        
        # Add type-specific instructions
        treasure_type = params['type']
        if treasure_type == "Hoard":
            prompt_lines.extend([
                "- Generate a varied and randomized treasure hoard appropriate for the CR/level, following DMG guidelines roughly.",
                "- Ensure variety in the types of gems, art objects, and magic items; avoid excessive repetition of specific items.",
                f"- **CRITICAL:** The total value of currency, gems, art objects, and the rarity/number of magic items **MUST** be scaled appropriately for the provided CR ({params['cr']}) and Average Party Level ({params['level']}). Do not generate overly valuable or powerful items for low levels, nor trivial amounts for high levels.",
                "- Include currency (CP, SP, EP, GP, PP), gems, art objects, and potentially 1 or more magic items suitable for the party level.",
                "- Structure the output in JSON format with keys like 'currency', 'gems', 'art_objects', 'magic_items'. Magic items should include 'name', 'rarity', 'type', and 'description'."
            ])
        elif treasure_type == "Individual Monster":
            prompt_lines.extend([
                "- Generate treasure suitable for a single monster of the specified CR.",
                "- This might include some coins, a trinket, or a low-value consumable item. Be less generous than a hoard.",
                "- Structure the output in JSON with keys like 'currency', 'items'."
            ])
        elif treasure_type == "Magic Item Only":
            prompt_lines.extend([
                "- Generate 1-3 magic items appropriate for the specified party level.",
                "- Include the item name, rarity, type (e.g., Weapon, Armor, Potion, Wondrous Item), and a brief description of its appearance and function.",
                "- Structure the output as a JSON object with a single key 'magic_items' containing a list of item objects, each including 'name', 'rarity', 'type', and 'description' keys."
            ])
        elif treasure_type == "Mundane Items":
            prompt_lines.extend([
                "- Generate a list of 5-10 mundane, non-magical items that might be found.",
                "- Consider the context (e.g., camp supplies, tools, personal effects).",
                "- Structure the output as a JSON object with a single key 'mundane_items' containing a list of strings."
            ])

        # Add final JSON requirement
        prompt_lines.extend([
            "",
            "**IMPORTANT: Your entire response MUST be ONLY the JSON object. Do not include any text before or after the JSON structure. Start with `{` and end with `}`.**"
        ])
        
        return "\n".join(prompt_lines)

    def _handle_generation_result(self, response, error):
        """Handle LLM result in background thread and emit signal."""
        self.generation_result.emit(response, error)

    def _process_generation_ui(self, response, error):
        """Process LLM result in main GUI thread."""
        self._reset_ui_state()

        if error:
            QMessageBox.critical(self, "Generation Error", f"Error generating treasure: {error}")
            self.results_display.setPlainText(f"Error: {error}")
            return

        if not response:
            QMessageBox.warning(self, "Empty Response", "The AI returned an empty response.")
            self.results_display.setPlainText("Received empty response from AI.")
            return

        try:
            # Clean potential markdown
            if response.strip().startswith("```json"):
                response = response.strip()[7:]
            if response.strip().endswith("```"):
                response = response.strip()[:-3]
                
            parsed_result = json.loads(response.strip())
            # Pretty-print the JSON for display
            formatted_json = json.dumps(parsed_result, indent=4)
            self.results_display.setPlainText(formatted_json)
            
            # Store the parsed data for potential saving
            self.current_treasure_data = parsed_result
            
            # Enable the save button
            self.save_to_notes_button.setEnabled(True)
            
        except json.JSONDecodeError as e:
            self.current_treasure_data = None # Clear data on error
            self.save_to_notes_button.setEnabled(False) # Disable save on error
            error_msg = f"Failed to parse AI response as JSON: {e}\n\nRaw response:\n{response}"
            QMessageBox.critical(self, "Parsing Error", error_msg)
            self.results_display.setPlainText(error_msg)
        except Exception as e:
            error_msg = f"An unexpected error occurred processing the response: {e}"
            QMessageBox.critical(self, "Error", error_msg)
            self.results_display.setPlainText(error_msg)

    def _reset_ui_state(self):
        """Reset UI elements after generation attempt."""
        self.is_generating = False
        self.generate_button.setEnabled(True)
        self.generate_button.setText("Generate Treasure")
        # Don't disable save button on reset, allow saving after generation
        # self.save_to_notes_button.setEnabled(False) 
        # Don't clear current_treasure_data here, allow saving after error reset

    def _save_to_notes(self):
        """Format the current treasure data and save it to session notes."""
        if not self.current_treasure_data:
            QMessageBox.warning(self, "No Data", "No treasure data available to save.")
            return

        # Try to get the session notes panel
        session_notes_panel = self.get_panel("session_notes")
        if not session_notes_panel or not hasattr(session_notes_panel, '_create_note_with_content'):
            QMessageBox.warning(self, "Session Notes Error", 
                                "Could not find Session Notes panel or it lacks '_create_note_with_content' method.")
            return

        # Format the data
        formatted_content = self._format_treasure_for_notes(self.current_treasure_data)
        
        # Determine title
        treasure_type = self.type_combo.currentText()
        title = f"Generated Treasure ({treasure_type})"
        if treasure_type == "Hoard":
             title += f" (CR {self.cr_spinbox.value()})"
        elif treasure_type == "Individual Monster":
             title += f" (CR {self.cr_spinbox.value()})"
        elif treasure_type == "Magic Item Only":
            title += f" (Lvl {self.level_spinbox.value()})"
        
        tags = ["treasure", "generated", treasure_type.lower().replace(" ", "-")]

        # Add the note
        try:
            # Call the correct method on SessionNotesPanel
            session_notes_panel._create_note_with_content(title=title, content=formatted_content, tags=tags)
            QMessageBox.information(self, "Saved", f"Treasure saved to Session Notes: '{title}'")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save to Session Notes: {e}")

    def _format_treasure_for_notes(self, data: dict) -> str:
        """Convert the treasure JSON data to markdown/text for notes."""
        content = []
        
        treasure_type = data.get("_type", self.type_combo.currentText()) # Store type if possible?

        content.append(f"## Generated Treasure ({treasure_type})")
        content.append("")

        if "currency" in data:
            content.append("### Currency")
            curr = data["currency"]
            curr_str = ", ".join([f"{v} {k.upper() }" for k, v in curr.items() if v > 0])
            content.append(curr_str if curr_str else "None")
            content.append("")

        if "gems" in data and data["gems"]:
            content.append("### Gems")
            for gem in data["gems"]:
                 print(f"[_format_treasure_for_notes] Processing gem: {gem}")
                 # Try 'name', then 'type', then fallback
                 gem_name = gem.get("name") or gem.get("type", "Unknown gem")
                 val = gem.get("value", "?")
                 content.append(f"- {gem_name} ({val} GP)")
            content.append("")

        if "art_objects" in data and data["art_objects"]:
            content.append("### Art Objects")
            for art in data["art_objects"]:
                 print(f"[_format_treasure_for_notes] Processing art object: {art}")
                 # Try 'name', then 'description', then 'type', then fallback
                 art_name = art.get("name") or art.get("description") or art.get("type", "Unknown object")
                 val = art.get("value", "?")
                 content.append(f"- {art_name} ({val} GP)")
            content.append("")

        if "magic_items" in data and data["magic_items"]:
            content.append("### Magic Items")
            for item in data["magic_items"]:
                # Log the item data being processed
                print(f"[_format_treasure_for_notes] Processing magic item: {item}") 
                
                # Assuming items are dicts with name, rarity, type, description
                name = item.get("name", "Unnamed Item")
                rarity = item.get("rarity", "Unknown")
                item_type = item.get("type", "Item") # Get type if provided
                desc = item.get("description", "No description provided.") # Get description
                content.append(f"**{name}** ({rarity}, {item_type})")
                content.append(f"> {desc}") # Display description
                content.append("") # Add space between items
            content.append("")

        if "items" in data and data["items"]:
             content.append("### Other Items")
             for item in data["items"]:
                  # Assuming simple list of strings or dicts
                  if isinstance(item, dict):
                      name = item.get("name", "Unknown item")
                      desc = item.get("description", "")
                      content.append(f"- {name}{': ' + desc if desc else ''}")
                  else:
                      content.append(f"- {str(item)}")
             content.append("")
             
        if "mundane_items" in data and data["mundane_items"]:
             content.append("### Mundane Items")
             for item in data["mundane_items"]:
                 content.append(f"- {str(item)}")
             content.append("")

        return "\n".join(content)
        
    # TODO: Implement save_state and restore_state if needed

# REMOVE THE INVALID MARKER BELOW 