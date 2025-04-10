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
    QRadioButton, QButtonGroup, QSlider, QFrame, QSizePolicy,
    QApplication
)
from PySide6.QtCore import Qt, Signal, Slot, QSize, QMetaObject, Q_ARG, QRect
from PySide6.QtGui import QIcon, QAction, QTextCursor, QFont, QPalette, QScreen
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
        
        self.save_to_notes_button = QPushButton("Save to Notes")
        self.save_to_notes_button.setEnabled(False)
        
        self.clear_button = QPushButton("Clear")
        
        buttons_layout.addWidget(self.generate_button)
        buttons_layout.addWidget(self.save_button)
        buttons_layout.addWidget(self.save_to_notes_button)
        buttons_layout.addWidget(self.clear_button)
        
        config_layout.addLayout(buttons_layout)
        
        # === Results Section ===
        results_widget = QWidget()
        results_layout = QVBoxLayout(results_widget)
        results_layout.setContentsMargins(0, 0, 0, 0)
        
        # Results display with tabs
        results_group = QGroupBox("Generated Location")
        results_inner_layout = QVBoxLayout(results_group)
        
        # Create tabbed interface
        self.results_tabs = QTabWidget()
        
        # HTML display tab
        self.html_tab = QWidget()
        html_layout = QVBoxLayout(self.html_tab)
        html_layout.setContentsMargins(5, 5, 5, 5)
        
        self.location_display = QTextEdit()
        self.location_display.setReadOnly(True)
        self.location_display.setMinimumHeight(200)
        self.location_display.setPlaceholderText("Generated location will appear here...")
        
        html_layout.addWidget(self.location_display)
        
        # Formatted view tab
        self.formatted_tab = QWidget()
        formatted_layout = QVBoxLayout(self.formatted_tab)
        formatted_layout.setContentsMargins(5, 5, 5, 5)
        
        # Create a scroll area for the formatted view
        formatted_scroll = QScrollArea()
        formatted_scroll.setWidgetResizable(True)
        formatted_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        formatted_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # Create the content widget for the scroll area
        self.formatted_content = QWidget()
        self.formatted_layout = QVBoxLayout(self.formatted_content)
        
        # Set size policy to ensure content expands properly
        self.formatted_content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.formatted_content.setMinimumWidth(300)  # Ensure minimum width for content
        
        formatted_scroll.setWidget(self.formatted_content)
        
        formatted_layout.addWidget(formatted_scroll)
        
        # Raw JSON tab
        self.json_tab = QWidget()
        json_layout = QVBoxLayout(self.json_tab)
        json_layout.setContentsMargins(5, 5, 5, 5)
        
        self.json_display = QTextEdit()
        self.json_display.setReadOnly(True)
        self.json_display.setMinimumHeight(200)
        self.json_display.setPlaceholderText("Raw JSON data will appear here...")
        
        # Set a monospace font for the JSON view
        json_font = QFont("Courier New", 10)
        self.json_display.setFont(json_font)
        
        json_layout.addWidget(self.json_display)
        
        # Add tabs to tab widget
        self.results_tabs.addTab(self.formatted_tab, "Formatted View")
        self.results_tabs.addTab(self.html_tab, "HTML View")
        self.results_tabs.addTab(self.json_tab, "JSON Data")
        
        # Add a "View Full Screen" button
        self.fullscreen_button = QPushButton("View Full Screen")
        self.fullscreen_button.setEnabled(False)
        self.fullscreen_button.clicked.connect(self._show_fullscreen_view)
        results_inner_layout.addWidget(self.fullscreen_button)
        
        results_inner_layout.addWidget(self.results_tabs)
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
        self.save_to_notes_button.clicked.connect(self._save_to_notes)
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
        
        # Clear the displays
        self.location_display.clear()
        self.json_display.clear()
        self._clear_formatted_view()
        
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
                
                # Enable save buttons
                self.save_button.setEnabled(True)
                self.save_to_notes_button.setEnabled(True)
                self.fullscreen_button.setEnabled(True)  # Enable fullscreen button
                
                # Display in HTML view
                html_content = self._format_location_as_html(location_data)
                self.location_display.setHtml(html_content)
                
                # Display in JSON view - use pretty print
                formatted_json = json.dumps(location_data, indent=4)
                self.json_display.setPlainText(formatted_json)
                
                # Update formatted view
                self._update_formatted_view(location_data)
                
                # Update status
                self.status_label.setText("Location generated successfully")
                self.status_label.setStyleSheet("color: green;")
            else:
                # Handle non-JSON response
                self.location_display.setPlainText(response)
                self.json_display.setPlainText(response)
                self.current_generation = {
                    "raw_response": response,
                    "parsed_data": {"description": response},
                    "params": self._get_generation_params()
                }
                self.save_button.setEnabled(True)
                self.save_to_notes_button.setEnabled(True)
                self.fullscreen_button.setEnabled(False)
                self.status_label.setText("Location generated (non-standard format)")
                self.status_label.setStyleSheet("color: orange;")
                
        except Exception as e:
            # Handle parsing errors
            self.location_display.setPlainText(response)
            self.json_display.setPlainText(response)
            self.status_label.setText(f"Error parsing result: {str(e)}")
            self.status_label.setStyleSheet("color: red;")
            
            # Still allow saving the raw text
            self.current_generation = {
                "raw_response": response,
                "parsed_data": {"description": response},
                "params": self._get_generation_params()
            }
            self.save_button.setEnabled(True)
            self.save_to_notes_button.setEnabled(True)
            self.fullscreen_button.setEnabled(False)
    
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
    
    def _save_to_notes(self):
        """Save the generated location to session notes"""
        if not self.current_generation:
            return
            
        # Try to get session notes panel
        session_notes_panel = self.get_panel("session_notes")
        if not session_notes_panel:
            QMessageBox.warning(self, "Session Notes Not Available", 
                "Could not find the Session Notes panel. Make sure it's loaded.")
            return
        
        # Extract location data
        location_data = self.current_generation["parsed_data"]
        params = self.current_generation["params"]
        
        # Determine title
        if "name" in location_data:
            title = location_data["name"]
        else:
            title = params["name"] if params["name"] else "Generated Location"
            
        # Get formatted content directly (no JSON)
        formatted_content = self._format_location_for_notes(location_data)
        
        # Generate tags
        tags = ["location"]
        if params["type"] != "Random":
            tags.append(params["type"])
        if params["environment"] != "Random":
            tags.append(params["environment"])
        tags.append(params["size"])
        
        # Save to notes using session notes panel's method
        try:
            # Check if _create_note_with_content exists
            if hasattr(session_notes_panel, '_create_note_with_content'):
                success = session_notes_panel._create_note_with_content(
                    title=f"Location: {title}",
                    content=formatted_content,
                    tags=tags  # Pass the tags as a list instead of joining them
                )
                
                if success:
                    self.status_label.setText(f"Location saved to session notes: {title}")
                    self.status_label.setStyleSheet("color: green;")
                else:
                    self.status_label.setText("Failed to save location to session notes")
                    self.status_label.setStyleSheet("color: red;")
            # Alternative method if _create_note_with_content doesn't exist
            elif hasattr(session_notes_panel, 'debug_info'):
                # Debug to see what methods are available
                session_notes_panel.debug_info()
                QMessageBox.warning(self, "Alternative Method Used", 
                    "Using debug method to diagnose session notes panel issue.")
            else:
                QMessageBox.warning(self, "Method Not Available", 
                    "The session notes panel does not have the expected methods.")
        except Exception as e:
            QMessageBox.warning(self, "Save to Notes Error", f"Error saving to notes: {str(e)}")
    
    def _format_location_for_notes(self, location_data):
        """Format location data as formatted text for session notes"""
        content = []
        
        # Location name and type
        name = location_data.get("name", "Unnamed Location")
        location_type = location_data.get("type", "")
        
        # Add basic location information
        if location_type:
            content.append(f"*Type:* {location_type}")
        
        # Environment and size/scale
        environment = location_data.get("environment", "")
        if environment:
            content.append(f"*Environment:* {environment}")
            
        size = location_data.get("size", "")
        if size:
            content.append(f"*Size:* {size}")
            
        # Population/activity level
        population = location_data.get("population", "")
        if population:
            content.append(f"*Population:* {population}")
            
        # Add threat/danger level
        danger = location_data.get("danger_level", location_data.get("threat_level", ""))
        if danger:
            content.append(f"*Danger Level:* {danger}")
            
        content.append("")  # Empty line
        
        # Main description
        description = location_data.get("description", "")
        if description:
            content.append("## Description")
            content.append(description)
            content.append("")
            
        # Narrative output (if present)
        narrative = location_data.get("narrative_output", "")
        if narrative:
            # If narrative is a complex object, format each part
            if isinstance(narrative, dict):
                # Physical description
                phys_desc = narrative.get("physical_description", "")
                if phys_desc:
                    content.append("## Physical Description")
                    content.append(phys_desc)
                    content.append("")
                
                # Background/history
                hist_bg = narrative.get("history_background", "")
                if hist_bg:
                    content.append("## History & Background") 
                    content.append(hist_bg)
                    content.append("")
                
                # Atmosphere/mood
                atmos = narrative.get("atmosphere_mood", "")
                if atmos:
                    content.append("## Atmosphere & Mood")
                    content.append(atmos)
                    content.append("")
                
                # Threats/challenges
                threats = narrative.get("notable_threats_challenges", "")
                if threats:
                    content.append("## Threats & Challenges")
                    content.append(threats)
                    content.append("")
                
                # Handle nested lists in narrative
                narrative_points = narrative.get("points_of_interest", [])
                if narrative_points and len(narrative_points) > 0:
                    content.append("## Points of Interest")
                    for point in narrative_points:
                        if isinstance(point, dict):
                            name = point.get("name", "")
                            desc = point.get("description", "")
                            if name:
                                content.append(f"### {name}")
                            if desc:
                                content.append(desc)
                            content.append("")
                        elif isinstance(point, str):
                            content.append(f"- {point}")
                    content.append("")
                
                narrative_npcs = narrative.get("key_npcs", [])
                if narrative_npcs and len(narrative_npcs) > 0:
                    content.append("## Key NPCs")
                    for npc in narrative_npcs:
                        if isinstance(npc, dict):
                            name = npc.get("name", "")
                            desc = npc.get("description", "")
                            if name:
                                content.append(f"### {name}")
                            if desc:
                                content.append(desc)
                            content.append("")
                        elif isinstance(npc, str):
                            content.append(f"- {npc}")
                    content.append("")
                
                narrative_secrets = narrative.get("secrets_hidden_elements", [])
                if narrative_secrets and len(narrative_secrets) > 0:
                    content.append("## Secrets & Hidden Elements")
                    for secret in narrative_secrets:
                        if isinstance(secret, dict):
                            # Some LLM responses use "secret" key, others use "name"/"description"
                            secret_text = secret.get("secret", secret.get("description", ""))
                            secret_name = secret.get("name", "")
                            
                            if secret_name:
                                content.append(f"### {secret_name}")
                            if secret_text:
                                content.append(secret_text)
                            content.append("")
                        elif isinstance(secret, str):
                            content.append(f"- {secret}")
                    content.append("")
            else:
                # Simple string narrative
                content.append(narrative)
                content.append("")
        
        # If narrative didn't have these sections, look for them in the top level
        
        # History or background
        if "history_background" not in str(narrative):
            history = location_data.get("history", location_data.get("background", ""))
            if history:
                content.append("## History & Background")
                content.append(history)
                content.append("")
            
        # Points of interest - if not already included in narrative
        if "points_of_interest" not in str(narrative):
            points = location_data.get("points_of_interest", [])
            if points:
                content.append("## Points of Interest")
                if isinstance(points, list):
                    for point in points:
                        if isinstance(point, str):
                            content.append(f"- {point}")
                        elif isinstance(point, dict):
                            point_name = point.get("name", "")
                            point_desc = point.get("description", "")
                            if point_name and point_desc:
                                content.append(f"### {point_name}")
                                content.append(point_desc)
                            elif point_name:
                                content.append(f"- {point_name}")
                            elif point_desc:
                                content.append(f"- {point_desc}")
                            content.append("")
                elif isinstance(points, str):
                    content.append(points)
                content.append("")
        
        # NPCs - if not already included in narrative
        if "key_npcs" not in str(narrative):
            npcs = location_data.get("npcs", [])
            if npcs:
                content.append("## Notable NPCs")
                if isinstance(npcs, list):
                    for npc in npcs:
                        if isinstance(npc, str):
                            content.append(f"- {npc}")
                        elif isinstance(npc, dict):
                            npc_name = npc.get("name", "")
                            npc_desc = npc.get("description", "")
                            if npc_name and npc_desc:
                                content.append(f"### {npc_name}")
                                content.append(npc_desc)
                            elif npc_name:
                                content.append(f"- {npc_name}")
                            elif npc_desc:
                                content.append(f"- {npc_desc}")
                            content.append("")
                elif isinstance(npcs, str):
                    content.append(npcs)
                content.append("")
        
        # Secrets - if not already included in narrative
        if "secrets_hidden_elements" not in str(narrative):
            secrets = location_data.get("secrets", [])
            if secrets:
                content.append("## Secrets")
                if isinstance(secrets, list):
                    for secret in secrets:
                        if isinstance(secret, str):
                            content.append(f"- {secret}")
                        elif isinstance(secret, dict):
                            secret_name = secret.get("name", "")
                            secret_desc = secret.get("description", "")
                            if secret_name and secret_desc:
                                content.append(f"### {secret_name}")
                                content.append(secret_desc)
                            elif secret_name:
                                content.append(f"- {secret_name}")
                            elif secret_desc:
                                content.append(f"- {secret_desc}")
                            content.append("")
                elif isinstance(secrets, str):
                    content.append(secrets)
                content.append("")
        
        # Atmosphere/mood - if not already in narrative
        if "atmosphere_mood" not in str(narrative):
            atmosphere = location_data.get("atmosphere", location_data.get("mood", ""))
            if atmosphere:
                content.append("## Atmosphere & Mood")
                content.append(atmosphere)
                content.append("")
        
        # Threats/challenges - if not already in narrative
        if "notable_threats_challenges" not in str(narrative):
            threats = location_data.get("threats", location_data.get("challenges", ""))
            if threats:
                content.append("## Threats & Challenges")
                content.append(threats)
                content.append("")
        
        # Handle other potential location data
        for key, value in location_data.items():
            if key not in ["name", "type", "description", "narrative_output", 
                          "points_of_interest", "npcs", "secrets", "history", 
                          "background", "environment", "size", "population", 
                          "danger_level", "threat_level", "atmosphere", "mood",
                          "threats", "challenges"]:
                if isinstance(value, str) and value:
                    content.append(f"## {key.replace('_', ' ').title()}")
                    content.append(value)
                    content.append("")
                    
        return "\n".join(content)
    
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
        
        # Reset displays
        self.location_display.clear()
        self.location_display.setPlaceholderText("Generated location will appear here...")
        self.json_display.clear()
        self.json_display.setPlaceholderText("Raw JSON data will appear here...")
        self._clear_formatted_view()
        
        # Disable buttons
        self.save_button.setEnabled(False)
        self.save_to_notes_button.setEnabled(False)
        self.fullscreen_button.setEnabled(False)
        
        # Reset status
        self.status_label.setText("Ready to generate")
        self.status_label.setStyleSheet("color: gray;")
        
        # Clear current generation
        self.current_generation = None

    def _clear_formatted_view(self):
        """Clear the formatted view"""
        # Remove all widgets from the layout
        while self.formatted_layout.count():
            item = self.formatted_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def _update_formatted_view(self, location_data):
        """Update the formatted view with location data"""
        self._clear_formatted_view()
        
        # Create a styled view of the location
        # Location name as title
        name = location_data.get("name", "Unnamed Location")
        name_label = QLabel(name)
        name_font = QFont()
        name_font.setPointSize(16)
        name_font.setBold(True)
        name_label.setFont(name_font)
        name_label.setAlignment(Qt.AlignCenter)
        name_label.setWordWrap(True)
        name_label.setTextFormat(Qt.PlainText)
        name_label.setStyleSheet("color: #1a237e; margin: 10px 0; padding: 5px;")
        self.formatted_layout.addWidget(name_label)
        
        # Location type and basic info
        info_widget = QWidget()
        info_layout = QHBoxLayout(info_widget)
        
        # Left column - Type, environment
        left_info = QWidget()
        left_layout = QVBoxLayout(left_info)
        
        # Type
        location_type = location_data.get("type", "")
        if location_type:
            type_label = QLabel(f"<b>Type:</b> {location_type}")
            type_label.setWordWrap(True)
            type_label.setTextFormat(Qt.RichText)
            left_layout.addWidget(type_label)
        
        # Environment
        environment = location_data.get("environment", "")
        if environment:
            env_label = QLabel(f"<b>Environment:</b> {environment}")
            env_label.setWordWrap(True)
            env_label.setTextFormat(Qt.RichText)
            left_layout.addWidget(env_label)
            
        info_layout.addWidget(left_info)
        
        # Right column - Size, population, danger
        right_info = QWidget()
        right_layout = QVBoxLayout(right_info)
        
        # Size
        size = location_data.get("size", "")
        if size:
            size_label = QLabel(f"<b>Size:</b> {size}")
            size_label.setWordWrap(True)
            size_label.setTextFormat(Qt.RichText)
            right_layout.addWidget(size_label)
            
        # Population
        population = location_data.get("population", "")
        if population:
            pop_label = QLabel(f"<b>Population:</b> {population}")
            pop_label.setWordWrap(True)
            pop_label.setTextFormat(Qt.RichText)
            right_layout.addWidget(pop_label)
            
        # Danger level
        danger = location_data.get("danger_level", location_data.get("threat_level", ""))
        if danger:
            danger_label = QLabel(f"<b>Danger:</b> {danger}")
            danger_label.setWordWrap(True)
            danger_label.setTextFormat(Qt.RichText)
            right_layout.addWidget(danger_label)
            
        info_layout.addWidget(right_info)
        self.formatted_layout.addWidget(info_widget)
        
        # Add a separator line
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        self.formatted_layout.addWidget(line)
        
        # Description
        description = location_data.get("description", "")
        if description:
            desc_title = QLabel("Description")
            desc_title.setStyleSheet("font-weight: bold; font-size: 14px; color: #4a148c; margin-top: 10px;")
            self.formatted_layout.addWidget(desc_title)
            
            desc_text = QLabel(description)
            desc_text.setWordWrap(True)
            desc_text.setTextFormat(Qt.RichText)
            self.formatted_layout.addWidget(desc_text)
            
            # Add a small spacer
            spacer = QWidget()
            spacer.setFixedHeight(10)
            self.formatted_layout.addWidget(spacer)
        
        # Narrative output (if present)
        narrative = location_data.get("narrative_output", "")
        if narrative:
            narrative_label = QLabel(narrative)
            narrative_label.setWordWrap(True)
            narrative_label.setTextFormat(Qt.RichText)
            self.formatted_layout.addWidget(narrative_label)
            
            # Add a small spacer
            spacer = QWidget()
            spacer.setFixedHeight(10)
            self.formatted_layout.addWidget(spacer)
        
        # History
        history = location_data.get("history", location_data.get("background", ""))
        if history:
            history_title = QLabel("History & Background")
            history_title.setStyleSheet("font-weight: bold; font-size: 14px; color: #4a148c; margin-top: 10px;")
            self.formatted_layout.addWidget(history_title)
            
            history_text = QLabel(history)
            history_text.setWordWrap(True)
            history_text.setTextFormat(Qt.RichText)
            self.formatted_layout.addWidget(history_text)
            
            # Add a small spacer
            spacer = QWidget()
            spacer.setFixedHeight(10)
            self.formatted_layout.addWidget(spacer)
        
        # Points of interest
        points = location_data.get("points_of_interest", [])
        if points:
            points_title = QLabel("Points of Interest")
            points_title.setStyleSheet("font-weight: bold; font-size: 14px; color: #4a148c; margin-top: 10px;")
            self.formatted_layout.addWidget(points_title)
            
            if isinstance(points, list):
                for point in points:
                    point_widget = QWidget()
                    point_layout = QVBoxLayout(point_widget)
                    point_layout.setContentsMargins(10, 0, 0, 0)
                    
                    if isinstance(point, str):
                        point_label = QLabel(f"• {point}")
                        point_label.setWordWrap(True)
                        point_layout.addWidget(point_label)
                    elif isinstance(point, dict):
                        point_name = point.get("name", "")
                        point_desc = point.get("description", "")
                        
                        if point_name:
                            name_label = QLabel(f"• <b>{point_name}</b>")
                            name_label.setTextFormat(Qt.RichText)
                            point_layout.addWidget(name_label)
                        
                        if point_desc:
                            desc_label = QLabel(point_desc)
                            desc_label.setWordWrap(True)
                            desc_label.setIndent(15)
                            point_layout.addWidget(desc_label)
                            
                    self.formatted_layout.addWidget(point_widget)
            elif isinstance(points, str):
                points_label = QLabel(points)
                points_label.setWordWrap(True)
                self.formatted_layout.addWidget(points_label)
            
            # Add a small spacer
            spacer = QWidget()
            spacer.setFixedHeight(10)
            self.formatted_layout.addWidget(spacer)
        
        # NPCs
        npcs = location_data.get("npcs", [])
        if npcs:
            npcs_title = QLabel("Notable NPCs")
            npcs_title.setStyleSheet("font-weight: bold; font-size: 14px; color: #4a148c; margin-top: 10px;")
            self.formatted_layout.addWidget(npcs_title)
            
            if isinstance(npcs, list):
                for npc in npcs:
                    npc_widget = QWidget()
                    npc_layout = QVBoxLayout(npc_widget)
                    npc_layout.setContentsMargins(10, 0, 0, 0)
                    
                    if isinstance(npc, str):
                        npc_label = QLabel(f"• {npc}")
                        npc_label.setWordWrap(True)
                        npc_layout.addWidget(npc_label)
                    elif isinstance(npc, dict):
                        npc_name = npc.get("name", "")
                        npc_desc = npc.get("description", "")
                        
                        if npc_name:
                            name_label = QLabel(f"• <b>{npc_name}</b>")
                            name_label.setTextFormat(Qt.RichText)
                            npc_layout.addWidget(name_label)
                        
                        if npc_desc:
                            desc_label = QLabel(npc_desc)
                            desc_label.setWordWrap(True)
                            desc_label.setIndent(15)
                            npc_layout.addWidget(desc_label)
                            
                    self.formatted_layout.addWidget(npc_widget)
            elif isinstance(npcs, str):
                npcs_label = QLabel(npcs)
                npcs_label.setWordWrap(True)
                self.formatted_layout.addWidget(npcs_label)
            
            # Add a small spacer
            spacer = QWidget()
            spacer.setFixedHeight(10)
            self.formatted_layout.addWidget(spacer)
        
        # Secrets
        secrets = location_data.get("secrets", [])
        if secrets:
            secrets_title = QLabel("Secrets")
            secrets_title.setStyleSheet("font-weight: bold; font-size: 14px; color: #4a148c; margin-top: 10px;")
            self.formatted_layout.addWidget(secrets_title)
            
            if isinstance(secrets, list):
                for secret in secrets:
                    secret_widget = QWidget()
                    secret_layout = QVBoxLayout(secret_widget)
                    secret_layout.setContentsMargins(10, 0, 0, 0)
                    
                    if isinstance(secret, str):
                        secret_label = QLabel(f"• {secret}")
                        secret_label.setWordWrap(True)
                        secret_layout.addWidget(secret_label)
                    elif isinstance(secret, dict):
                        secret_name = secret.get("name", "")
                        secret_desc = secret.get("description", "")
                        
                        if secret_name:
                            name_label = QLabel(f"• <b>{secret_name}</b>")
                            name_label.setTextFormat(Qt.RichText)
                            name_label.setStyleSheet("font-size: 16px;")
                            secret_layout.addWidget(name_label)
                        
                        if secret_desc:
                            desc_label = QLabel(secret_desc)
                            desc_label.setWordWrap(True)
                            desc_label.setIndent(15)
                            desc_label.setStyleSheet("font-size: 14px;")
                            secret_layout.addWidget(desc_label)
                            
                    self.formatted_layout.addWidget(secret_widget)
            elif isinstance(secrets, str):
                secrets_label = QLabel(secrets)
                secrets_label.setWordWrap(True)
                self.formatted_layout.addWidget(secrets_label)
        
        # Add a spacer at the end to push everything up
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.formatted_layout.addWidget(spacer)
    
    def _show_fullscreen_view(self):
        """Show full-screen formatted view of the location"""
        if not self.current_generation:
            return
            
        location_data = self.current_generation["parsed_data"]
        dialog = FullScreenLocationDialog(self, location_data)
        dialog.exec()


# Add a new FullScreenLocationDialog class for displaying locations in full screen
class FullScreenLocationDialog(QDialog):
    """Dialog for displaying a location in full screen format"""
    
    def __init__(self, parent=None, location_data=None):
        super().__init__(parent)
        self.location_data = location_data
        
        # Set up the dialog
        self.setWindowTitle("Location Viewer")
        self.resize(1024, 768)  # Start with a reasonable size
        
        # Create the layout
        layout = QVBoxLayout(self)
        
        # Create scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # Create content widget
        content_widget = QWidget()
        self.content_layout = QVBoxLayout(content_widget)
        self.content_layout.setContentsMargins(20, 20, 20, 20)  # Add more padding for readability
        
        # Fill with formatted content
        self._populate_content()
        
        # Set content widget to scroll area
        scroll_area.setWidget(content_widget)
        
        # Add scroll area to main layout
        layout.addWidget(scroll_area)
        
        # Add close button at bottom
        button_box = QDialogButtonBox(QDialogButtonBox.Close)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        # Maximize the dialog on larger screens
        screen = QApplication.primaryScreen().geometry()
        if screen.width() >= 1280 and screen.height() >= 800:
            self.showMaximized()
    
    def _populate_content(self):
        """Populate the dialog with formatted location content"""
        if not self.location_data:
            self.content_layout.addWidget(QLabel("No location data available"))
            return
        
        # Using an attractive styling with larger fonts for readability
        # Location name as title
        name = self.location_data.get("name", "Unnamed Location")
        name_label = QLabel(name)
        name_font = QFont()
        name_font.setPointSize(24)  # Much larger font
        name_font.setBold(True)
        name_label.setFont(name_font)
        name_label.setAlignment(Qt.AlignCenter)
        name_label.setStyleSheet("color: #1a237e; margin: 20px 0;")
        self.content_layout.addWidget(name_label)
        
        # Location type and basic info - presented in a nicer way
        info_widget = QWidget()
        info_layout = QHBoxLayout(info_widget)
        
        # Style the info box
        info_widget.setStyleSheet("background-color: #f5f5f5; border-radius: 5px; padding: 10px;")
        
        # Left column - Type, environment
        left_info = QWidget()
        left_layout = QVBoxLayout(left_info)
        
        # Type with larger fonts
        location_type = self.location_data.get("type", "")
        if location_type:
            type_label = QLabel(f"<b>Type:</b> {location_type}")
            type_label.setStyleSheet("font-size: 14px;")
            left_layout.addWidget(type_label)
        
        # Environment
        environment = self.location_data.get("environment", "")
        if environment:
            env_label = QLabel(f"<b>Environment:</b> {environment}")
            env_label.setStyleSheet("font-size: 14px;")
            left_layout.addWidget(env_label)
            
        info_layout.addWidget(left_info)
        
        # Right column - Size, population, danger
        right_info = QWidget()
        right_layout = QVBoxLayout(right_info)
        
        # Size
        size = self.location_data.get("size", "")
        if size:
            size_label = QLabel(f"<b>Size:</b> {size}")
            size_label.setStyleSheet("font-size: 14px;")
            right_layout.addWidget(size_label)
            
        # Population
        population = self.location_data.get("population", "")
        if population:
            pop_label = QLabel(f"<b>Population:</b> {population}")
            pop_label.setStyleSheet("font-size: 14px;")
            right_layout.addWidget(pop_label)
            
        # Danger level
        danger = self.location_data.get("danger_level", self.location_data.get("threat_level", ""))
        if danger:
            danger_label = QLabel(f"<b>Danger:</b> {danger}")
            danger_label.setStyleSheet("font-size: 14px;")
            right_layout.addWidget(danger_label)
            
        info_layout.addWidget(right_info)
        self.content_layout.addWidget(info_widget)
        
        # Add a separator line
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        line.setLineWidth(2)  # Thicker line
        self.content_layout.addWidget(line)
        
        # Description
        description = self.location_data.get("description", "")
        if description:
            desc_title = QLabel("Description")
            desc_title.setStyleSheet("font-weight: bold; font-size: 18px; color: #4a148c; margin-top: 20px;")
            self.content_layout.addWidget(desc_title)
            
            desc_text = QLabel(description)
            desc_text.setWordWrap(True)
            desc_text.setTextFormat(Qt.RichText)
            desc_text.setStyleSheet("font-size: 14px; line-height: 1.5;")
            self.content_layout.addWidget(desc_text)
            
            # Add a small spacer
            spacer = QWidget()
            spacer.setFixedHeight(20)
            self.content_layout.addWidget(spacer)
        
        # Narrative output (if present)
        narrative = self.location_data.get("narrative_output", "")
        if narrative:
            narrative_label = QLabel(narrative)
            narrative_label.setWordWrap(True)
            narrative_label.setTextFormat(Qt.RichText)
            narrative_label.setStyleSheet("font-size: 14px; line-height: 1.5;")
            self.content_layout.addWidget(narrative_label)
            
            # Add a small spacer
            spacer = QWidget()
            spacer.setFixedHeight(20)
            self.content_layout.addWidget(spacer)
        
        # History
        history = self.location_data.get("history", self.location_data.get("background", ""))
        if history:
            history_title = QLabel("History & Background")
            history_title.setStyleSheet("font-weight: bold; font-size: 18px; color: #4a148c; margin-top: 20px;")
            self.content_layout.addWidget(history_title)
            
            history_text = QLabel(history)
            history_text.setWordWrap(True)
            history_text.setTextFormat(Qt.RichText)
            history_text.setStyleSheet("font-size: 14px; line-height: 1.5;")
            self.content_layout.addWidget(history_text)
            
            # Add a small spacer
            spacer = QWidget()
            spacer.setFixedHeight(20)
            self.content_layout.addWidget(spacer)
        
        # Points of interest
        points = self.location_data.get("points_of_interest", [])
        if points:
            points_title = QLabel("Points of Interest")
            points_title.setStyleSheet("font-weight: bold; font-size: 18px; color: #4a148c; margin-top: 20px;")
            self.content_layout.addWidget(points_title)
            
            # Create a container with alternating background colors for points
            points_container = QWidget()
            points_container.setStyleSheet("background-color: #f9f9f9; border-radius: 5px; padding: 10px;")
            points_layout = QVBoxLayout(points_container)
            
            if isinstance(points, list):
                for i, point in enumerate(points):
                    point_widget = QWidget()
                    # Alternate background colors for better readability
                    if i % 2 == 0:
                        point_widget.setStyleSheet("background-color: #f5f5f5; padding: 5px; border-radius: 3px;")
                    else:
                        point_widget.setStyleSheet("background-color: #ffffff; padding: 5px; border-radius: 3px;")
                        
                    point_layout = QVBoxLayout(point_widget)
                    point_layout.setContentsMargins(10, 5, 10, 5)
                    
                    if isinstance(point, str):
                        point_label = QLabel(f"• {point}")
                        point_label.setWordWrap(True)
                        point_label.setStyleSheet("font-size: 14px;")
                        point_layout.addWidget(point_label)
                    elif isinstance(point, dict):
                        point_name = point.get("name", "")
                        point_desc = point.get("description", "")
                        
                        if point_name:
                            name_label = QLabel(f"• <b>{point_name}</b>")
                            name_label.setTextFormat(Qt.RichText)
                            name_label.setStyleSheet("font-size: 16px;")
                            point_layout.addWidget(name_label)
                        
                        if point_desc:
                            desc_label = QLabel(point_desc)
                            desc_label.setWordWrap(True)
                            desc_label.setIndent(15)
                            desc_label.setStyleSheet("font-size: 14px;")
                            point_layout.addWidget(desc_label)
                            
                    points_layout.addWidget(point_widget)
            elif isinstance(points, str):
                points_label = QLabel(points)
                points_label.setWordWrap(True)
                points_label.setStyleSheet("font-size: 14px;")
                points_layout.addWidget(points_label)
            
            self.content_layout.addWidget(points_container)
            
            # Add a small spacer
            spacer = QWidget()
            spacer.setFixedHeight(20)
            self.content_layout.addWidget(spacer)
        
        # NPCs
        npcs = self.location_data.get("npcs", [])
        if npcs:
            npcs_title = QLabel("Notable NPCs")
            npcs_title.setStyleSheet("font-weight: bold; font-size: 18px; color: #4a148c; margin-top: 20px;")
            self.content_layout.addWidget(npcs_title)
            
            # Create a container with alternating background colors for NPCs
            npcs_container = QWidget()
            npcs_container.setStyleSheet("background-color: #f9f9f9; border-radius: 5px; padding: 10px;")
            npcs_layout = QVBoxLayout(npcs_container)
            
            if isinstance(npcs, list):
                for i, npc in enumerate(npcs):
                    npc_widget = QWidget()
                    # Alternate background colors for better readability
                    if i % 2 == 0:
                        npc_widget.setStyleSheet("background-color: #f5f5f5; padding: 5px; border-radius: 3px;")
                    else:
                        npc_widget.setStyleSheet("background-color: #ffffff; padding: 5px; border-radius: 3px;")
                        
                    npc_layout = QVBoxLayout(npc_widget)
                    npc_layout.setContentsMargins(10, 5, 10, 5)
                    
                    if isinstance(npc, str):
                        npc_label = QLabel(f"• {npc}")
                        npc_label.setWordWrap(True)
                        npc_label.setStyleSheet("font-size: 14px;")
                        npc_layout.addWidget(npc_label)
                    elif isinstance(npc, dict):
                        npc_name = npc.get("name", "")
                        npc_desc = npc.get("description", "")
                        
                        if npc_name:
                            name_label = QLabel(f"• <b>{npc_name}</b>")
                            name_label.setTextFormat(Qt.RichText)
                            name_label.setStyleSheet("font-size: 16px;")
                            npc_layout.addWidget(name_label)
                        
                        if npc_desc:
                            desc_label = QLabel(npc_desc)
                            desc_label.setWordWrap(True)
                            desc_label.setIndent(15)
                            desc_label.setStyleSheet("font-size: 14px;")
                            npc_layout.addWidget(desc_label)
                            
                    npcs_layout.addWidget(npc_widget)
            elif isinstance(npcs, str):
                npcs_label = QLabel(npcs)
                npcs_label.setWordWrap(True)
                npcs_label.setStyleSheet("font-size: 14px;")
                npcs_layout.addWidget(npcs_label)
            
            self.content_layout.addWidget(npcs_container)
            
            # Add a small spacer
            spacer = QWidget()
            spacer.setFixedHeight(20)
            self.content_layout.addWidget(spacer)
        
        # Secrets
        secrets = self.location_data.get("secrets", [])
        if secrets:
            secrets_title = QLabel("Secrets")
            secrets_title.setStyleSheet("font-weight: bold; font-size: 18px; color: #4a148c; margin-top: 20px;")
            self.content_layout.addWidget(secrets_title)
            
            # Create a container with styling for secrets
            secrets_container = QWidget()
            secrets_container.setStyleSheet("background-color: #f0f4f8; border-radius: 5px; padding: 10px; border: 1px dashed #7986cb;")
            secrets_layout = QVBoxLayout(secrets_container)
            
            if isinstance(secrets, list):
                for secret in secrets:
                    secret_widget = QWidget()
                    secret_layout = QVBoxLayout(secret_widget)
                    secret_layout.setContentsMargins(10, 5, 10, 5)
                    
                    if isinstance(secret, str):
                        secret_label = QLabel(f"• {secret}")
                        secret_label.setWordWrap(True)
                        secret_label.setStyleSheet("font-size: 14px;")
                        secret_layout.addWidget(secret_label)
                    elif isinstance(secret, dict):
                        secret_name = secret.get("name", "")
                        secret_desc = secret.get("description", "")
                        
                        if secret_name:
                            name_label = QLabel(f"• <b>{secret_name}</b>")
                            name_label.setTextFormat(Qt.RichText)
                            name_label.setStyleSheet("font-size: 16px;")
                            secret_layout.addWidget(name_label)
                        
                        if secret_desc:
                            desc_label = QLabel(secret_desc)
                            desc_label.setWordWrap(True)
                            desc_label.setIndent(15)
                            desc_label.setStyleSheet("font-size: 14px;")
                            secret_layout.addWidget(desc_label)
                            
                    secrets_layout.addWidget(secret_widget)
            elif isinstance(secrets, str):
                secrets_label = QLabel(secrets)
                secrets_label.setWordWrap(True)
                secrets_label.setStyleSheet("font-size: 14px;")
                secrets_layout.addWidget(secrets_label)
            
            self.content_layout.addWidget(secrets_container)
        
        # Add additional sections for any other data
        for key, value in self.location_data.items():
            if key not in ["name", "type", "description", "narrative_output", 
                          "points_of_interest", "npcs", "secrets", "history", 
                          "background", "environment", "size", "population", 
                          "danger_level", "threat_level", "atmosphere", "mood",
                          "threats", "challenges"]:
                if isinstance(value, str) and value:
                    # Add a section title
                    section_title = QLabel(key.replace('_', ' ').title())
                    section_title.setStyleSheet("font-weight: bold; font-size: 18px; color: #4a148c; margin-top: 20px;")
                    self.content_layout.addWidget(section_title)
                    
                    # Add section content
                    section_text = QLabel(value)
                    section_text.setWordWrap(True)
                    section_text.setTextFormat(Qt.RichText)
                    section_text.setStyleSheet("font-size: 14px; line-height: 1.5;")
                    self.content_layout.addWidget(section_text)
                    
                    # Add a small spacer
                    spacer = QWidget()
                    spacer.setFixedHeight(20)
                    self.content_layout.addWidget(spacer)
        
        # Add a spacer at the end to push everything up
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.content_layout.addWidget(spacer) 