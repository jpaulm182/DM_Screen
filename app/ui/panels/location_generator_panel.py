"""
Location Generator Panel for DM Screen

Provides a user interface for generating detailed locations using LLM with customizable parameters.
Supports saving and managing generated locations for campaign use.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton, 
    QComboBox, QLabel, QTabWidget, QLineEdit, QSplitter,
    QToolButton, QMenu, QDialog, QDialogButtonBox, QFormLayout,
    QListWidget, QListWidgetItem, QFileDialog, QInputDialog,
    QScrollArea, QMessageBox, QGroupBox, QCheckBox, QSpinBox,
    QRadioButton, QButtonGroup, QSlider
)
from PySide6.QtCore import Qt, Signal, Slot, QSize, QMetaObject, Q_ARG
from PySide6.QtGui import QIcon, QAction, QTextCursor, QFont
import json

from app.ui.panels.base_panel import BasePanel


class LocationGeneratorPanel(BasePanel):
    """
    Panel for generating detailed locations using LLM and managing them for campaigns
    """
    
    PANEL_TYPE = "location_generator"
    PANEL_TITLE = "Location Generator"
    PANEL_CATEGORY = "Campaign"
    PANEL_DESCRIPTION = "Generate detailed locations with descriptions, NPCs, and points of interest using AI"
    
    # Signal emitted when a location is generated and should be saved
    location_generated = Signal(dict)
    
    # Signal for thread-safe communication between worker and UI
    generation_result = Signal(str, str)  # response, error
    
    def __init__(self, app_state, panel_id=None):
        """Initialize the Location Generator panel"""
        panel_id = panel_id or "location_generator"
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
        
        # Settings for location generator
        settings_group = QGroupBox("Location Settings")
        settings_layout = QFormLayout(settings_group)
        
        # Location Name
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Leave blank for random name")
        settings_layout.addRow("Name (optional):", self.name_input)
        
        # Location Type
        self.type_combo = QComboBox()
        self.type_combo.addItems([
            "Random", "Town", "City", "Village", "Fortress", "Dungeon", 
            "Temple", "Forest", "Mountain", "Cave", "Ruins", "Tavern", 
            "Shop", "Manor", "Castle", "Port", "Island", "Wilderness"
        ])
        self.type_combo.setEditable(True)
        settings_layout.addRow("Type:", self.type_combo)
        
        # Environment/Setting
        self.environment_combo = QComboBox()
        self.environment_combo.addItems([
            "Random", "Forest", "Mountains", "Desert", "Coastal", "Urban",
            "Underground", "Arctic", "Jungle", "Swamp", "Plains", "Volcanic"
        ])
        self.environment_combo.setEditable(True)
        settings_layout.addRow("Environment:", self.environment_combo)
        
        # Size/Scale
        size_widget = QWidget()
        size_layout = QHBoxLayout(size_widget)
        size_layout.setContentsMargins(0, 0, 0, 0)
        
        self.size_combo = QComboBox()
        self.size_combo.addItems([
            "Tiny", "Small", "Medium", "Large", "Huge", "Massive"
        ])
        self.size_combo.setCurrentIndex(2)  # Medium by default
        
        size_layout.addWidget(self.size_combo)
        size_layout.addStretch()
        
        settings_layout.addRow("Size/Scale:", size_widget)
        
        # Population/Activity Level
        population_widget = QWidget()
        population_layout = QHBoxLayout(population_widget)
        population_layout.setContentsMargins(0, 0, 0, 0)
        
        self.population_slider = QSlider(Qt.Horizontal)
        self.population_slider.setMinimum(0)
        self.population_slider.setMaximum(10)
        self.population_slider.setValue(5)
        self.population_slider.setTickPosition(QSlider.TicksBelow)
        self.population_slider.setTickInterval(1)
        
        self.population_label = QLabel("Medium")
        self.population_slider.valueChanged.connect(self._update_population_label)
        
        population_layout.addWidget(self.population_slider)
        population_layout.addWidget(self.population_label)
        
        settings_layout.addRow("Population/Activity:", population_widget)
        
        # Optional Features
        features_widget = QWidget()
        features_layout = QHBoxLayout(features_widget)
        features_layout.setContentsMargins(0, 0, 0, 0)
        
        self.npcs_check = QCheckBox("Key NPCs")
        self.npcs_check.setChecked(True)
        
        self.secrets_check = QCheckBox("Secrets")
        self.secrets_check.setChecked(True)
        
        self.points_check = QCheckBox("Points of Interest")
        self.points_check.setChecked(True)
        
        features_layout.addWidget(self.npcs_check)
        features_layout.addWidget(self.secrets_check)
        features_layout.addWidget(self.points_check)
        features_layout.addStretch()
        
        settings_layout.addRow("Include:", features_widget)
        
        # Danger/Threat Level
        threat_widget = QWidget()
        threat_layout = QHBoxLayout(threat_widget)
        threat_layout.setContentsMargins(0, 0, 0, 0)
        
        self.threat_combo = QComboBox()
        self.threat_combo.addItems([
            "Safe", "Mild Danger", "Moderate Danger", "Dangerous", "Very Dangerous", "Extremely Dangerous"
        ])
        self.threat_combo.setCurrentIndex(2)  # Moderate by default
        
        threat_layout.addWidget(self.threat_combo)
        threat_layout.addStretch()
        
        settings_layout.addRow("Danger Level:", threat_widget)
        
        # Campaign setting & context
        self.campaign_context = QTextEdit()
        self.campaign_context.setPlaceholderText("Enter details about your campaign setting, current situation, or other context to make the location fit better...")
        self.campaign_context.setMaximumHeight(80)
        settings_layout.addRow("Context:", self.campaign_context)
        
        # Add groups to layout
        config_layout.addWidget(model_group)
        config_layout.addWidget(settings_group)
        
        # Generation buttons
        buttons_layout = QHBoxLayout()
        
        self.generate_button = QPushButton("Generate Location")
        self.generate_button.setMinimumHeight(40)
        self.generate_button.setStyleSheet("font-weight: bold;")
        
        self.save_button = QPushButton("Save Location")
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
        results_group = QGroupBox("Generated Location")
        results_inner_layout = QVBoxLayout(results_group)
        
        self.location_display = QTextEdit()
        self.location_display.setReadOnly(True)
        self.location_display.setMinimumHeight(200)
        self.location_display.setPlaceholderText("Generated location will appear here...")
        
        results_inner_layout.addWidget(self.location_display)
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
    
    def _update_population_label(self, value):
        """Update the population label based on slider value"""
        labels = [
            "Abandoned", "Deserted", "Sparse", "Low", "Below Average", 
            "Average", "Above Average", "Busy", "Crowded", "Dense", "Overcrowded"
        ]
        self.population_label.setText(labels[value])
    
    def _connect_signals(self):
        """Connect UI signals to handlers"""
        # Button connections
        self.generate_button.clicked.connect(self._generate_location)
        self.save_button.clicked.connect(self._save_location)
        self.clear_button.clicked.connect(self._clear_form)
        
        # Model connections
        self.model_combo.currentIndexChanged.connect(self._model_changed)
        
        # Connect thread-safe signal for LLM generation results
        self.generation_result.connect(self._update_ui_with_generation_result)
    
    def _load_settings(self):
        """Load saved settings and available models"""
        # Load available models
        models = self.llm_service.get_available_models()
        self.model_combo.clear()
        
        for model in models:
            self.model_combo.addItem(model["name"], model["id"])
        
        # Set default model if available
        default_model = self.app_state.get_setting("default_llm_model")
        if default_model:
            index = self.model_combo.findData(default_model)
            if index >= 0:
                self.model_combo.setCurrentIndex(index)
    
    def _model_changed(self, index):
        """Handle model selection change"""
        model_id = self.model_combo.currentData()
        if model_id:
            self.app_state.set_setting("default_llm_model", model_id)
    
    def _generate_location(self):
        """Generate a location using the LLM service"""
        if self.is_generating:
            return
        
        # Get selected model
        model_id = self.model_combo.currentData()
        if not model_id:
            QMessageBox.warning(self, "Model Required", "Please select a valid LLM model.")
            return
        
        # Collect location parameters
        params = self._get_generation_params()
        
        # Create prompt for LLM
        prompt = self._create_location_prompt(params)
        
        # Update UI
        self.is_generating = True
        self.status_label.setText("Generating location...")
        self.status_label.setStyleSheet("color: blue;")
        self.generate_button.setEnabled(False)
        
        # Call LLM service
        self.llm_service.generate_completion_async(
            model=model_id,
            messages=[{"role": "user", "content": prompt}],
            callback=self._handle_generation_result,
            temperature=0.7,
            max_tokens=2000
        )
    
    def _get_generation_params(self):
        """Get parameters for location generation from form fields"""
        params = {
            "name": self.name_input.text().strip(),
            "type": self.type_combo.currentText(),
            "environment": self.environment_combo.currentText(),
            "size": self.size_combo.currentText(),
            "population": self.population_slider.value(),
            "include_npcs": self.npcs_check.isChecked(),
            "include_secrets": self.secrets_check.isChecked(),
            "include_points": self.points_check.isChecked(),
            "threat_level": self.threat_combo.currentText(),
            "context": self.campaign_context.toPlainText().strip()
        }
        
        return params
    
    def _create_location_prompt(self, params):
        """Create an optimized prompt for location generation"""
        prompt = "Generate a detailed D&D 5e location with the following specifications in JSON format only. Include all narrative in a 'narrative_output' field within the JSON structure. Do not generate anything outside of the JSON structure.\n\n"
        
        # Add specific parameters
        if params["name"]:
            prompt += f"Name: {params['name']}\n"
        else:
            prompt += "Name: [Generate an appropriate fantasy name]\n"
        
        if params["type"] != "Random":
            prompt += f"Type: {params['type']}\n"
        else:
            prompt += "Type: [Choose an appropriate location type]\n"
        
        if params["environment"] != "Random":
            prompt += f"Environment: {params['environment']}\n"
        
        # Size/Scale
        prompt += f"Size/Scale: {params['size']}\n"
        
        # Population/Activity Level
        population_labels = [
            "Abandoned", "Deserted", "Sparse", "Low", "Below Average", 
            "Average", "Above Average", "Busy", "Crowded", "Dense", "Overcrowded"
        ]
        population = population_labels[params["population"]]
        prompt += f"Population/Activity Level: {population}\n"
        
        # Threat Level
        prompt += f"Danger Level: {params['threat_level']}\n"
        
        # Add context if provided
        if params["context"]:
            prompt += f"\nCampaign Context:\n{params['context']}\n"
        
        # Additional requirements
        prompt += "\nPlease include:\n"
        prompt += "1. Detailed physical description with sensory elements\n"
        prompt += "2. History and background of the location\n"
        
        if params["include_points"]:
            prompt += "3. At least 3-5 points of interest with brief descriptions\n"
        
        if params["include_npcs"]:
            prompt += "4. Key NPCs who can be found here (at least 2-3) with brief descriptions\n"
        
        if params["include_secrets"]:
            prompt += "5. At least 2 secrets or hidden elements that characters might discover\n"
        
        prompt += "6. Atmosphere and overall mood of the location\n"
        prompt += "7. Any notable threats or challenges present\n"
        
        return prompt
    
    def _handle_generation_result(self, response, error):
        """Handle the LLM generation result (will be called in a thread)"""
        if error:
            # Signal the error to the main thread
            self.generation_result.emit(None, error)
        else:
            # Signal the response to the main thread
            self.generation_result.emit(response, None)
    
    def _update_ui_with_generation_result(self, response, error):
        """Update the UI with generation results (called in the main thread)"""
        # Reset generating state
        self.is_generating = False
        self.generate_button.setEnabled(True)
        
        # Check for error
        if error:
            self.status_label.setText(f"Error: {error}")
            self.status_label.setStyleSheet("color: red;")
            return
        
        # Clear the system message about generating
        self.location_display.clear()
        
        # Parse and display the result
        try:
            # Try to extract JSON from the response
            # Find JSON block in case there's text before or after
            json_start = response.find('{')
            json_end = response.rfind('}')
            
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end+1]
                location_data = json.loads(json_str)
                
                # Store the full generation for later saving
                self.current_generation = {
                    "raw_response": response,
                    "parsed_data": location_data,
                    "params": self._get_generation_params()
                }
                
                # Enable save button
                self.save_button.setEnabled(True)
                
                # Display formatted location
                html_content = self._format_location_as_html(location_data)
                self.location_display.setHtml(html_content)
                
                # Update status
                self.status_label.setText("Location generated successfully")
                self.status_label.setStyleSheet("color: green;")
            else:
                # Handle non-JSON response
                self.location_display.setPlainText(response)
                self.current_generation = {
                    "raw_response": response,
                    "parsed_data": {"description": response},
                    "params": self._get_generation_params()
                }
                self.save_button.setEnabled(True)
                self.status_label.setText("Location generated (non-standard format)")
                self.status_label.setStyleSheet("color: orange;")
                
        except Exception as e:
            # Handle parsing errors
            self.location_display.setPlainText(response)
            self.status_label.setText(f"Error parsing result: {str(e)}")
            self.status_label.setStyleSheet("color: red;")
            
            # Still allow saving the raw text
            self.current_generation = {
                "raw_response": response,
                "parsed_data": {"description": response},
                "params": self._get_generation_params()
            }
            self.save_button.setEnabled(True)
    
    def _format_location_as_html(self, location_data):
        """Format location data as HTML for display"""
        html = "<html><body style='font-family: Arial, sans-serif;'>"
        
        # Location name and type
        name = location_data.get("name", "Unnamed Location")
        location_type = location_data.get("type", "")
        
        html += f"<h2>{name}</h2>"
        if location_type:
            html += f"<h3>{location_type}</h3>"
        
        # Main description
        description = location_data.get("description", "")
        if description:
            html += f"<p>{description}</p>"
        
        # Narrative output (if present)
        narrative = location_data.get("narrative_output", "")
        if narrative:
            html += f"<div>{narrative}</div>"
        
        # Points of interest
        points = location_data.get("points_of_interest", [])
        if points:
            html += "<h3>Points of Interest</h3><ul>"
            for point in points:
                if isinstance(point, str):
                    html += f"<li>{point}</li>"
                elif isinstance(point, dict):
                    point_name = point.get("name", "")
                    point_desc = point.get("description", "")
                    html += f"<li><b>{point_name}</b>: {point_desc}</li>"
            html += "</ul>"
        
        # NPCs
        npcs = location_data.get("npcs", [])
        if npcs:
            html += "<h3>Notable NPCs</h3><ul>"
            for npc in npcs:
                if isinstance(npc, str):
                    html += f"<li>{npc}</li>"
                elif isinstance(npc, dict):
                    npc_name = npc.get("name", "")
                    npc_desc = npc.get("description", "")
                    html += f"<li><b>{npc_name}</b>: {npc_desc}</li>"
            html += "</ul>"
        
        # Secrets
        secrets = location_data.get("secrets", [])
        if secrets:
            html += "<h3>Secrets</h3><ul>"
            for secret in secrets:
                if isinstance(secret, str):
                    html += f"<li>{secret}</li>"
                elif isinstance(secret, dict):
                    secret_name = secret.get("name", "")
                    secret_desc = secret.get("description", "")
                    html += f"<li><b>{secret_name}</b>: {secret_desc}</li>"
            html += "</ul>"
        
        # Handle other potential location data
        for key, value in location_data.items():
            if key not in ["name", "type", "description", "narrative_output", 
                          "points_of_interest", "npcs", "secrets"]:
                if isinstance(value, str):
                    html += f"<h3>{key.replace('_', ' ').title()}</h3>"
                    html += f"<p>{value}</p>"
        
        html += "</body></html>"
        return html
    
    def _save_location(self):
        """Save the generated location to the data manager"""
        if not self.current_generation:
            return
        
        # Extract data
        location_data = self.current_generation["parsed_data"]
        params = self.current_generation["params"]
        
        # Determine title
        if "name" in location_data:
            title = location_data["name"]
        else:
            title = params["name"] if params["name"] else "Generated Location"
        
        # Ask for confirmation and title
        title, ok = QInputDialog.getText(
            self, "Save Location", "Location name:", 
            QLineEdit.Normal, title
        )
        
        if not ok or not title:
            return
        
        # Prepare content for saving
        if isinstance(location_data, dict):
            # Convert to JSON string for storage
            content = json.dumps(location_data, indent=2)
        else:
            # Use raw response if data isn't a dict
            content = self.current_generation["raw_response"]
        
        # Save to data manager
        try:
            # Generate unique ID for this content
            content_id = self.llm_data_manager.add_generated_content(
                title=title,
                content_type="location",
                content=content,
                model_id=self.model_combo.currentData(),
                prompt=self._create_location_prompt(params),
                tags=["location", params["type"], params["environment"], params["size"]]
            )
            
            # Show success message
            self.status_label.setText(f"Location saved: {title}")
            self.status_label.setStyleSheet("color: green;")
            
            # Emit signal
            self.location_generated.emit({
                "id": content_id,
                "title": title,
                "content": content,
                "type": "location"
            })
            
        except Exception as e:
            QMessageBox.warning(self, "Save Error", f"Could not save location: {str(e)}")
    
    def _clear_form(self):
        """Clear the form and reset to default state"""
        # Reset input fields
        self.name_input.clear()
        self.type_combo.setCurrentIndex(0)
        self.environment_combo.setCurrentIndex(0)
        self.size_combo.setCurrentIndex(2)  # Medium
        self.population_slider.setValue(5)  # Average
        self.npcs_check.setChecked(True)
        self.secrets_check.setChecked(True)
        self.points_check.setChecked(True)
        self.threat_combo.setCurrentIndex(2)  # Moderate
        self.campaign_context.clear()
        
        # Reset display
        self.location_display.clear()
        self.location_display.setPlaceholderText("Generated location will appear here...")
        
        # Disable save button
        self.save_button.setEnabled(False)
        
        # Reset status
        self.status_label.setText("Ready to generate")
        self.status_label.setStyleSheet("color: gray;")
        
        # Clear current generation
        self.current_generation = None 