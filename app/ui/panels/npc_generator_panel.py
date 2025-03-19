"""
NPC Generator Panel for DM Screen

Provides a user interface for generating NPCs using LLM with customizable parameters.
Supports saving and managing generated NPCs for campaign use.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton, 
    QComboBox, QLabel, QTabWidget, QLineEdit, QSplitter,
    QToolButton, QMenu, QDialog, QDialogButtonBox, QFormLayout,
    QListWidget, QListWidgetItem, QFileDialog, QInputDialog,
    QScrollArea, QMessageBox, QGroupBox, QCheckBox, QSpinBox,
    QRadioButton, QButtonGroup
)
from PySide6.QtCore import Qt, Signal, Slot, QSize, QMetaObject, Q_ARG
from PySide6.QtGui import QIcon, QAction, QTextCursor, QFont

from app.ui.panels.base_panel import BasePanel


class NPCGeneratorPanel(BasePanel):
    """
    Panel for generating NPCs using LLM and managing them for campaigns
    """
    
    PANEL_TYPE = "npc_generator"
    PANEL_TITLE = "NPC Generator"
    PANEL_CATEGORY = "Campaign"
    PANEL_DESCRIPTION = "Generate NPCs with personalities, backgrounds, and stats using AI"
    
    # Signal emitted when an NPC is generated and should be saved
    npc_generated = Signal(dict)
    
    # Signal for thread-safe communication between worker and UI
    generation_result = Signal(str, str)  # response, error
    
    def __init__(self, app_state, panel_id=None):
        """Initialize the NPC Generator panel"""
        panel_id = panel_id or "npc_generator"
        super().__init__(app_state, panel_id)
        
        # Get services
        self.llm_service = app_state.llm_service
        self.llm_data_manager = app_state.llm_data_manager
        
        # Generation state
        self.current_generation_id = None
        self.is_generating = False
        self.current_generation = None
        
        # Initialize UI
        self._init_ui()
        
        # Connect signals
        self._connect_signals()
        
        # Load models and settings
        self._load_settings()
    
    def _init_ui(self):
        """Initialize the panel UI"""
        # Main layout
        main_layout = QVBoxLayout(self)
        
        # Create splitter for configuration and results
        self.splitter = QSplitter(Qt.Vertical)
        
        # === Configuration Section ===
        config_widget = QWidget()
        config_layout = QVBoxLayout(config_widget)
        config_layout.setContentsMargins(0, 0, 0, 0)
        
        # Model selection group
        model_group = QGroupBox("LLM Model")
        model_layout = QHBoxLayout(model_group)
        
        model_label = QLabel("Model:")
        self.model_combo = QComboBox()
        model_layout.addWidget(model_label)
        model_layout.addWidget(self.model_combo)
        model_layout.addStretch()
        
        # Settings for NPC generator
        settings_group = QGroupBox("NPC Settings")
        settings_layout = QFormLayout(settings_group)
        
        # NPC Name
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Leave blank for random name")
        settings_layout.addRow("Name (optional):", self.name_input)
        
        # NPC Race
        self.race_combo = QComboBox()
        self.race_combo.addItems([
            "Random", "Human", "Elf", "Dwarf", "Halfling", "Gnome", 
            "Half-Elf", "Half-Orc", "Tiefling", "Dragonborn", "Other"
        ])
        settings_layout.addRow("Race:", self.race_combo)
        
        # NPC Gender
        gender_widget = QWidget()
        gender_layout = QHBoxLayout(gender_widget)
        gender_layout.setContentsMargins(0, 0, 0, 0)
        
        self.gender_group = QButtonGroup(gender_widget)
        self.random_gender = QRadioButton("Random")
        self.male_gender = QRadioButton("Male")
        self.female_gender = QRadioButton("Female")
        self.other_gender = QRadioButton("Other")
        
        self.gender_group.addButton(self.random_gender, 0)
        self.gender_group.addButton(self.male_gender, 1)
        self.gender_group.addButton(self.female_gender, 2)
        self.gender_group.addButton(self.other_gender, 3)
        
        self.random_gender.setChecked(True)
        
        gender_layout.addWidget(self.random_gender)
        gender_layout.addWidget(self.male_gender)
        gender_layout.addWidget(self.female_gender)
        gender_layout.addWidget(self.other_gender)
        
        settings_layout.addRow("Gender:", gender_widget)
        
        # NPC Type/Role
        self.role_combo = QComboBox()
        self.role_combo.addItems([
            "Random", "Shopkeeper", "Guard", "Noble", "Peasant", "Innkeeper",
            "Blacksmith", "Wizard", "Priest", "Criminal", "Merchant", "Adventurer"
        ])
        self.role_combo.setEditable(True)
        settings_layout.addRow("Role:", self.role_combo)
        
        # NPC Level/Power
        level_widget = QWidget()
        level_layout = QHBoxLayout(level_widget)
        level_layout.setContentsMargins(0, 0, 0, 0)
        
        self.level_spinner = QSpinBox()
        self.level_spinner.setRange(0, 20)
        self.level_spinner.setValue(1)
        self.level_spinner.setMinimumWidth(70)
        
        self.has_stats_check = QCheckBox("Generate Stats")
        self.has_stats_check.setChecked(True)
        
        level_layout.addWidget(self.level_spinner)
        level_layout.addWidget(self.has_stats_check)
        level_layout.addStretch()
        
        settings_layout.addRow("Level/CR:", level_widget)
        
        # Personality Traits
        personality_widget = QWidget()
        personality_layout = QHBoxLayout(personality_widget)
        personality_layout.setContentsMargins(0, 0, 0, 0)
        
        self.alignment_combo = QComboBox()
        self.alignment_combo.addItems([
            "Random", "Lawful Good", "Neutral Good", "Chaotic Good",
            "Lawful Neutral", "True Neutral", "Chaotic Neutral",
            "Lawful Evil", "Neutral Evil", "Chaotic Evil"
        ])
        
        self.quirk_check = QCheckBox("Add Quirk")
        self.quirk_check.setChecked(True)
        
        personality_layout.addWidget(self.alignment_combo)
        personality_layout.addWidget(self.quirk_check)
        personality_layout.addStretch()
        
        settings_layout.addRow("Alignment:", personality_widget)
        
        # Campaign setting & context
        self.campaign_context = QTextEdit()
        self.campaign_context.setPlaceholderText("Enter details about your campaign setting, current situation, or other context to make the NPC fit better...")
        self.campaign_context.setMaximumHeight(80)
        settings_layout.addRow("Context:", self.campaign_context)
        
        # Add groups to layout
        config_layout.addWidget(model_group)
        config_layout.addWidget(settings_group)
        
        # Generation buttons
        buttons_layout = QHBoxLayout()
        
        self.generate_button = QPushButton("Generate NPC")
        self.generate_button.setMinimumHeight(40)
        self.generate_button.setStyleSheet("font-weight: bold;")
        
        self.save_button = QPushButton("Save NPC")
        self.save_button.setEnabled(False)
        
        self.clear_button = QPushButton("Clear")
        
        buttons_layout.addWidget(self.generate_button)
        buttons_layout.addWidget(self.save_button)
        buttons_layout.addWidget(self.clear_button)
        
        config_layout.addLayout(buttons_layout)
        
        # === Results Section ===
        results_widget = QWidget()
        results_layout = QVBoxLayout(results_widget)
        results_layout.setContentsMargins(0, 0, 0, 0)
        
        # Results display
        results_group = QGroupBox("Generated NPC")
        results_inner_layout = QVBoxLayout(results_group)
        
        self.npc_display = QTextEdit()
        self.npc_display.setReadOnly(True)
        self.npc_display.setMinimumHeight(200)
        self.npc_display.setPlaceholderText("Generated NPC will appear here...")
        
        results_inner_layout.addWidget(self.npc_display)
        results_layout.addWidget(results_group)
        
        # Generation status
        self.status_label = QLabel("Ready to generate")
        self.status_label.setStyleSheet("color: gray;")
        results_layout.addWidget(self.status_label)
        
        # Add widgets to splitter
        self.splitter.addWidget(config_widget)
        self.splitter.addWidget(results_widget)
        self.splitter.setStretchFactor(0, 2)
        self.splitter.setStretchFactor(1, 3)
        
        # Add splitter to main layout
        main_layout.addWidget(self.splitter)
    
    def _connect_signals(self):
        """Connect UI signals to handlers"""
        # Button connections
        self.generate_button.clicked.connect(self._generate_npc)
        self.save_button.clicked.connect(self._save_npc)
        self.clear_button.clicked.connect(self._clear_form)
        
        # Model connections
        self.model_combo.currentIndexChanged.connect(self._model_changed)
        
        # Connect thread-safe signal for LLM generation results
        self.generation_result.connect(self._update_ui_with_generation_result)
    
    def _load_settings(self):
        """Load models and settings"""
        # Clear model combo
        self.model_combo.clear()
        
        # Add all available models
        models = self.llm_service.get_available_models() if hasattr(self.llm_service, 'get_available_models') else []
        
        if not models:
            # Fallback to ModelInfo if method not available
            from app.core.llm_service import ModelInfo
            all_models = ModelInfo.get_all_models()
            for provider_models in all_models.values():
                for model in provider_models:
                    self.model_combo.addItem(model["name"], model["id"])
        else:
            for model in models:
                self.model_combo.addItem(model["name"], model["id"])
        
        # Default text
        self._clear_form()
    
    def _model_changed(self, index):
        """Handle model selection change"""
        # Update UI based on selected model
        pass
    
    def _generate_npc(self):
        """Generate an NPC using the LLM service"""
        if self.is_generating:
            return
        
        # Get selected model
        model_id = self.model_combo.currentData()
        if not model_id:
            QMessageBox.warning(self, "Model Required", "Please select a valid LLM model.")
            return
        
        # Collect NPC parameters
        params = self._get_generation_params()
        
        # Create prompt for LLM
        prompt = self._create_npc_prompt(params)
        
        # Update UI
        self.is_generating = True
        self.status_label.setText("Generating NPC...")
        self.status_label.setStyleSheet("color: blue;")
        self.generate_button.setEnabled(False)
        
        # Call LLM service
        self.llm_service.generate_completion_async(
            model=model_id,
            messages=[{"role": "user", "content": prompt}],
            callback=self._handle_generation_result,
            temperature=0.7,
            max_tokens=1500
        )
    
    def _get_generation_params(self):
        """Get parameters for NPC generation from form fields"""
        params = {
            "name": self.name_input.text().strip(),
            "race": self.race_combo.currentText(),
            "role": self.role_combo.currentText(),
            "level": self.level_spinner.value(),
            "generate_stats": self.has_stats_check.isChecked(),
            "alignment": self.alignment_combo.currentText(),
            "add_quirk": self.quirk_check.isChecked(),
            "context": self.campaign_context.toPlainText().strip()
        }
        
        # Handle gender selection
        gender_id = self.gender_group.checkedId()
        if gender_id == 1:
            params["gender"] = "Male"
        elif gender_id == 2:
            params["gender"] = "Female"
        elif gender_id == 3:
            params["gender"] = "Other"
        else:
            params["gender"] = "Random"
        
        return params
    
    def _create_npc_prompt(self, params):
        """Create an optimized prompt for NPC generation"""
        prompt = "Generate a detailed D&D 5e NPC with the following specifications:\n\n"
        
        # Add specific parameters
        if params["name"]:
            prompt += f"Name: {params['name']}\n"
        else:
            prompt += "Name: [Generate an appropriate fantasy name]\n"
        
        if params["race"] != "Random":
            prompt += f"Race: {params['race']}\n"
        else:
            prompt += "Race: [Choose an appropriate D&D 5e race]\n"
        
        if params["gender"] != "Random":
            prompt += f"Gender: {params['gender']}\n"
        
        if params["role"] != "Random":
            prompt += f"Role/Occupation: {params['role']}\n"
        
        if params["level"] > 0:
            prompt += f"Level/CR: {params['level']}\n"
        
        if params["alignment"] != "Random":
            prompt += f"Alignment: {params['alignment']}\n"
        
        # Add context if provided
        if params["context"]:
            prompt += f"\nCampaign Context:\n{params['context']}\n"
        
        # Additional requirements
        prompt += "\nPlease include:\n"
        prompt += "1. Physical description and appearance\n"
        prompt += "2. Personality traits and behavior\n"
        prompt += "3. Background and history\n"
        prompt += "4. Goals and motivations\n"
        
        if params["add_quirk"]:
            prompt += "5. A unique quirk or distinctive trait\n"
        
        if params["generate_stats"]:
            prompt += "6. Basic D&D 5e statistics (ability scores, AC, HP, etc.)\n"
            prompt += "7. Notable skills, abilities, or equipment\n"
        
        # Output format guidelines
        prompt += "\nFormat the response in markdown with clear sections. Make the NPC interesting, three-dimensional, and ready to use in a D&D 5e game."
        
        return prompt
    
    def _handle_generation_result(self, response, error):
        """Handle the result from LLM generation"""
        # Emit the signal to safely update the UI from any thread
        self.generation_result.emit(
            response if response else "", 
            error if error else ""
        )
    
    def _update_ui_with_generation_result(self, response, error):
        """Update UI with generation result (runs in UI thread)"""
        self.is_generating = False
        self.generate_button.setEnabled(True)
        
        if error:
            self.status_label.setText(f"Error: {error}")
            self.status_label.setStyleSheet("color: red;")
            return
        
        # Update UI with generated NPC
        self.npc_display.setMarkdown(response)
        self.status_label.setText("NPC generated successfully!")
        self.status_label.setStyleSheet("color: green;")
        
        # Enable save button
        self.save_button.setEnabled(True)
        
        # Store the response for saving
        self.current_generation = {
            "content": response,
            "type": "npc",
            "parameters": self._get_generation_params()
        }
    
    def _save_npc(self):
        """Save the generated NPC to the data manager"""
        if not hasattr(self, 'current_generation') or not self.current_generation:
            return
        
        # Extract a title from the NPC content (usually first line)
        content_lines = self.current_generation["content"].split('\n')
        title = "Unnamed NPC"
        
        for line in content_lines:
            line = line.strip()
            if line and not line.startswith('#'):
                title = line
                break
        
        # Get parameters
        params = self.current_generation["parameters"]
        
        # Save to data manager
        try:
            # Generate unique ID for this content
            content_id = self.llm_data_manager.save_generated_content(
                title=title,
                content_type="npc",
                content=self.current_generation["content"],
                model_id=self.model_combo.currentData(),
                prompt=self._create_npc_prompt(params),
                tags=["npc", params.get("race", ""), params.get("role", "")]
            )
            
            # Show success message
            self.status_label.setText(f"NPC saved: {title}")
            self.status_label.setStyleSheet("color: green;")
            
            # Emit signal
            self.npc_generated.emit({
                "id": content_id,
                "title": title,
                "content": self.current_generation["content"],
                "type": "npc"
            })
            
        except Exception as e:
            QMessageBox.warning(self, "Save Error", f"Could not save NPC: {str(e)}")
    
    def _clear_form(self):
        """Clear the form and reset to default state"""
        # Reset input fields
        self.name_input.clear()
        self.race_combo.setCurrentIndex(0)
        self.random_gender.setChecked(True)
        self.role_combo.setCurrentIndex(0)
        self.level_spinner.setValue(1)
        self.has_stats_check.setChecked(True)
        self.alignment_combo.setCurrentIndex(0)
        self.quirk_check.setChecked(True)
        self.campaign_context.clear()
        
        # Reset display
        self.npc_display.clear()
        self.npc_display.setPlaceholderText("Generated NPC will appear here...")
        
        # Disable save button
        self.save_button.setEnabled(False)
        
        # Reset status
        self.status_label.setText("Ready to generate")
        self.status_label.setStyleSheet("color: gray;")
        
        # Clear current generation
        self.current_generation = None 