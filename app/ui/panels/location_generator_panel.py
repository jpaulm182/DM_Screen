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
    QApplication,
    QTextBrowser, QProgressDialog
)
from PySide6.QtCore import Qt, Signal, Slot, QSize, QMetaObject, Q_ARG, QRect
from PySide6.QtGui import QIcon, QAction, QTextCursor, QFont, QPalette, QScreen
import json

from app.ui.panels.base_panel import BasePanel
from app.utils.markdown_utils import markdown_to_html  # Import the Markdown utility
from app.utils.link_handler import handle_dnd_link, generate_entity_from_selection  # Import the shared dnd:// link handler and entity generator
from app.ui.dialogs.detail_dialog import DetailDialog


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
        
        self.location_display = QTextBrowser()
        self.location_display.setReadOnly(True)
        self.location_display.setMinimumHeight(200)
        self.location_display.setPlaceholderText("Generated location will appear here...")
        html_layout.addWidget(self.location_display)
        # Add custom context menu for text selection
        self.location_display.setContextMenuPolicy(Qt.CustomContextMenu)
        self.location_display.customContextMenuRequested.connect(self._show_location_display_context_menu)
        
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
    
    def _show_location_display_context_menu(self, pos):
        """Show context menu for location display to generate entity from selection"""
        menu = self.location_display.createStandardContextMenu()
        selected_text = self.location_display.textCursor().selectedText()
        if selected_text:
            action = QAction("Generate Entity from Selection", self)
            action.triggered.connect(lambda: self._generate_entity_from_selection(selected_text))
            menu.addAction(action)
        menu.exec(self.location_display.mapToGlobal(pos))
    
    def _generate_entity_from_selection(self, selected_text):
        """Generate an entity from the selected text using LLM"""
        if not selected_text:
            QMessageBox.information(self, "No Selection", "Please select some text to generate an entity.")
            return
        
        # Prompt for entity type
        entity_types = ["NPC", "Location", "Item", "Object", "Other"]
        entity_type, ok = QInputDialog.getItem(self, "Entity Type", "Select the type of entity to generate:", entity_types, 0, False)
        if not ok or not entity_type:
            return
            
        # Get context from current location data
        context = self.current_generation["parsed_data"] if self.current_generation else {}
        
        # Show a loading dialog
        progress = QProgressDialog("Generating entity...", None, 0, 0, self)
        progress.setWindowTitle("Please Wait")
        progress.setWindowModality(Qt.WindowModal)
        progress.show()
        QApplication.processEvents()
        
        def handle_result(response, error):
            progress.close()
            if error:
                QMessageBox.warning(self, "LLM Error", str(error))
                return
            
            # Debug: Print the raw LLM output
            print("RAW LLM OUTPUT:", response)
            
            # Try to extract JSON from the response
            player_desc = ""
            dm_desc = ""
            try:
                json_start = response.find('{')
                json_end = response.rfind('}')
                if json_start >= 0 and json_end > json_start:
                    json_str = response[json_start:json_end+1]
                    data = json.loads(json_str)
                    player_desc = data.get("player_description", "")
                    dm_desc = data.get("dm_description", "")
            except Exception:
                # Ignore JSON errors, fallback below
                pass
                
            if not player_desc and not dm_desc:
                # Fallback: show the whole response in both tabs
                player_desc = dm_desc = response
                
            dialog = DetailDialog(self, selected_text, player_desc, dm_desc)
            dialog.exec()
        
        # Use the shared utility to generate the entity
        generate_entity_from_selection(self, self.llm_service, selected_text, entity_type, context, handle_result)
    
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
        
        # Set up HTML link click handling
        self.location_display.setOpenLinks(False)
        self.location_display.setOpenExternalLinks(False)
        self.location_display.anchorClicked.connect(self._handle_link_clicked)
    
    def _handle_link_clicked(self, url):
        """Handle clicked links in the HTML display by passing to the shared link handler"""
        handle_dnd_link(self, url, self.app_state)
    
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
            max_tokens=4000
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
        
        # Add new section for generating the HTML structure with clickable elements
        prompt += "\nImportant: Format all output in HTML with clickable elements for NPCs, locations, objects, and other important features.\n"
        prompt += "For each element (NPC, place, object, etc.), create a data-element attribute with the element type and a unique identifier.\n"
        prompt += "Include both a player-facing description and a DM-only description for each section.\n"
        prompt += "Example structure in the narrative_output field:\n"
        prompt += "<div class='location-content'>\n"
        prompt += "  <div class='player-description'>\n"
        prompt += "    <h3>What Players See</h3>\n"
        prompt += "    <p>Description with <span class='interactive' data-element='npc-guard'>guard</span> and <span class='interactive' data-element='object-statue'>statue</span>...</p>\n"
        prompt += "  </div>\n"
        prompt += "  <div class='dm-description'>\n"
        prompt += "    <h3>For DM's Eyes Only</h3>\n"
        prompt += "    <p>Additional context, secrets, and motivations...</p>\n"
        prompt += "  </div>\n"
        prompt += "</div>\n"
        
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
                # Handle non-JSON response (likely Markdown)
                # Use markdown_to_html to render clickable links and formatting
                html_content = markdown_to_html(response)
                self.location_display.setHtml(html_content)
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
        """Format location data as HTML for display with interactive elements as <a href> links"""
        html = """
        <html>
        <head>
        <style>
            body { font-family: Arial, sans-serif; line-height: 1.6; }
            h2 { color: #4a148c; border-bottom: 1px solid #ccc; padding-bottom: 5px; }
            h3 { color: #6a1b9a; margin-top: 15px; }
            a.interactive { 
                color: #0277bd; 
                text-decoration: underline; 
                cursor: pointer;
                font-weight: bold;
            }
            a.interactive:hover { 
                color: #01579b; 
                background-color: #e1f5fe;
            }
            .player-description {
                background-color: #f5f5f5;
                border-left: 4px solid #4a148c;
                padding: 10px;
                margin: 10px 0;
            }
            .dm-description {
                background-color: #fff3e0;
                border-left: 4px solid #e65100;
                padding: 10px;
                margin: 10px 0;
            }
            .dm-description h3 {
                color: #e65100;
            }
        </style>
        </head>
        <body>
        """
        
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
            # Check if narrative is already in HTML format
            if narrative.strip().startswith("<") and narrative.strip().endswith(">"):
                html += f"{narrative}"
            else:
                html += f"<div>{narrative}</div>"
        
        # Points of interest as links
        points = location_data.get("points_of_interest", [])
        if points:
            html += "<h3>Points of Interest</h3><ul>"
            for i, point in enumerate(points):
                if isinstance(point, str):
                    html += f"<li><a class='interactive' href='dnd://poi-{i}'>{point}</a></li>"
                elif isinstance(point, dict):
                    point_name = point.get("name", "")
                    point_desc = point.get("description", "")
                    html += f"<li><a class='interactive' href='dnd://poi-{point_name.lower().replace(' ', '-')}'><b>{point_name}</b></a>: {point_desc}</li>"
            html += "</ul>"
        
        # NPCs as links
        npcs = location_data.get("npcs", [])
        if npcs:
            html += "<h3>Notable NPCs</h3><ul>"
            for i, npc in enumerate(npcs):
                if isinstance(npc, str):
                    html += f"<li><a class='interactive' href='dnd://npc-{i}'>{npc}</a></li>"
                elif isinstance(npc, dict):
                    npc_name = npc.get("name", "")
                    npc_desc = npc.get("description", "")
                    html += f"<li><a class='interactive' href='dnd://npc-{npc_name.lower().replace(' ', '-')}'><b>{npc_name}</b></a>: {npc_desc}</li>"
            html += "</ul>"
        
        # Secrets as links
        secrets = location_data.get("secrets", [])
        if secrets:
            html += "<h3>Secrets</h3><ul>"
            for i, secret in enumerate(secrets):
                if isinstance(secret, str):
                    html += f"<li><a class='interactive' href='dnd://secret-{i}'>{secret}</a></li>"
                elif isinstance(secret, dict):
                    secret_name = secret.get("name", "")
                    secret_desc = secret.get("description", "")
                    if secret_name:
                        html += f"<li><a class='interactive' href='dnd://secret-{secret_name.lower().replace(' ', '-')}'><b>{secret_name}</b></a>: {secret_desc}</li>"
                    else:
                        html += f"<li><a class='interactive' href='dnd://secret-{i}'>{secret_desc}</a></li>"
            html += "</ul>"
        
        # Handle other potential location data
        for key, value in location_data.items():
            if key not in ["name", "type", "description", "narrative_output", 
                          "points_of_interest", "npcs", "secrets"]:
                if isinstance(value, str):
                    html += f"<h3>{key.replace('_', ' ').title()}</h3>"
                    html += f"<p>{value}</p>"
        
        html += """
        </body>
        </html>
        """
        return html
    
    def _show_fullscreen_view(self):
        """Show a fullscreen view of the generated location content"""
        if not self.current_generation:
            return
            
        # Create a new dialog for fullscreen view
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Location: {self.current_generation['parsed_data'].get('name', 'Unnamed Location')}")
        dialog.setWindowFlags(Qt.Dialog | Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint)
        
        # Set size to 80% of screen
        screen_size = QApplication.primaryScreen().size()
        dialog.resize(int(screen_size.width() * 0.8), int(screen_size.height() * 0.8))
        
        # Create layout
        layout = QVBoxLayout(dialog)
        
        # Create content browser
        content = QTextBrowser(dialog)
        content.setOpenLinks(False)
        content.setOpenExternalLinks(False)
        content.anchorClicked.connect(self._handle_link_clicked)
        
        # Get HTML content based on current tab
        current_tab = self.results_tabs.currentIndex()
        if current_tab == 0:  # Formatted View
            # Create a scrollable view with the same content as the formatted tab
            content_widget = QWidget()
            content_layout = QVBoxLayout(content_widget)
            
            # Clone the formatted content widgets
            for i in range(self.formatted_layout.count()):
                item = self.formatted_layout.itemAt(i)
                if item and item.widget():
                    # Clone the widget - this is simplified, might need enhancement
                    if isinstance(item.widget(), QLabel):
                        label = QLabel(item.widget().text())
                        label.setTextFormat(item.widget().textFormat())
                        content_layout.addWidget(label)
                    else:
                        # For other widget types, you might need custom cloning logic
                        pass
                        
            # Use a scroll area to make the content scrollable
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(content_widget)
            layout.addWidget(scroll)
            
        else:
            # Use HTML or JSON view directly
            html_content = self.location_display.toHtml() if current_tab == 1 else self.json_display.toPlainText()
            content.setHtml(html_content)
            layout.addWidget(content)
        
        # Add close button
        close_button = QPushButton("Close")
        close_button.clicked.connect(dialog.close)
        layout.addWidget(close_button)
        
        # Show dialog
        dialog.exec()
    
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
                    # Add a section title and content in Markdown format
                    section_title = key.replace('_', ' ').title()
                    content.append(f"## {section_title}")
                    content.append(value)
                    content.append("")
        
        return "\n".join(content)
    
    def _clear_formatted_view(self):
        """Clear the formatted view by removing all widgets from the layout"""
        # Remove all existing widgets from the layout
        while self.formatted_layout.count():
            item = self.formatted_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def _clear_form(self):
        """Clear the form and reset to default state"""
        # Reset input fields
        self.name_input.clear()
        self.type_combo.setCurrentIndex(0)
        self.environment_combo.setCurrentIndex(0)
        self.size_combo.setCurrentIndex(2)  # Medium by default
        self.population_slider.setValue(5)  # Average by default
        self.npcs_check.setChecked(True)
        self.secrets_check.setChecked(True)
        self.points_check.setChecked(True)
        self.threat_combo.setCurrentIndex(2)  # Moderate by default
        self.campaign_context.clear()
        
        # Reset displays
        self.location_display.clear()
        self.location_display.setPlaceholderText("Generated location will appear here...")
        self.json_display.clear()
        self.json_display.setPlaceholderText("Raw JSON data will appear here...")
        self._clear_formatted_view()
        
        # Disable save buttons
        self.save_button.setEnabled(False)
        self.save_to_notes_button.setEnabled(False)
        self.fullscreen_button.setEnabled(False)
        
        # Reset status
        self.status_label.setText("Ready to generate")
        self.status_label.setStyleSheet("color: gray;")
        
        # Clear current generation
        self.current_generation = None 