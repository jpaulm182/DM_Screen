"""
Rules Clarification Panel for DM Screen

Uses LLM to clarify D&D 5e rules questions and provide interpretations for edge cases.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton, 
    QComboBox, QLabel, QTabWidget, QLineEdit, QSplitter,
    QToolButton, QMenu, QDialog, QDialogButtonBox, QFormLayout,
    QListWidget, QListWidgetItem, QFileDialog, QInputDialog,
    QScrollArea, QMessageBox, QGroupBox, QCheckBox, QSpinBox
)
from PySide6.QtCore import Qt, Signal, Slot, QSize
from PySide6.QtGui import QIcon, QAction, QTextCursor, QFont

from app.ui.panels.base_panel import BasePanel


class RulesClarificationPanel(BasePanel):
    """
    Panel for clarifying D&D 5e rules using LLM
    """
    
    PANEL_TYPE = "rules_clarification"
    PANEL_TITLE = "Rules Clarification"
    PANEL_CATEGORY = "Reference"
    PANEL_DESCRIPTION = "AI-powered rules clarification and edge case interpretation"
    
    # Signal emitted when a rule interpretation is generated
    rule_generated = Signal(dict)
    
    # Signal for thread-safe communication between worker and UI
    generation_result = Signal(str, str)  # response, error
    
    def __init__(self, app_state, panel_id=None):
        """Initialize the Rules Clarification panel"""
        panel_id = panel_id or "rules_clarification"
        super().__init__(app_state, panel_id)
        
        # Get services
        self.llm_service = app_state.llm_service
        self.llm_data_manager = app_state.llm_data_manager
        
        # Generation state
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
        
        # === Query Section ===
        query_widget = QWidget()
        query_layout = QVBoxLayout(query_widget)
        query_layout.setContentsMargins(0, 0, 0, 0)
        
        # Model selection group
        model_group = QGroupBox("LLM Model")
        model_layout = QHBoxLayout(model_group)
        
        model_label = QLabel("Model:")
        self.model_combo = QComboBox()
        model_layout.addWidget(model_label)
        model_layout.addWidget(self.model_combo)
        model_layout.addStretch()
        
        # Quick query suggestions
        suggestions_group = QGroupBox("Rule Topics")
        suggestions_layout = QHBoxLayout(suggestions_group)
        
        # Add common rule topics as buttons
        self.combat_btn = QPushButton("Combat")
        self.spellcasting_btn = QPushButton("Spellcasting")
        self.conditions_btn = QPushButton("Conditions")
        self.classes_btn = QPushButton("Classes")
        self.movement_btn = QPushButton("Movement")
        
        suggestions_layout.addWidget(self.combat_btn)
        suggestions_layout.addWidget(self.spellcasting_btn)
        suggestions_layout.addWidget(self.conditions_btn)
        suggestions_layout.addWidget(self.classes_btn)
        suggestions_layout.addWidget(self.movement_btn)
        
        # Rule query input
        query_input_group = QGroupBox("Rule Question")
        query_input_layout = QVBoxLayout(query_input_group)
        
        self.query_input = QTextEdit()
        self.query_input.setPlaceholderText("Enter your rule question or describe the situation you need clarification on...")
        self.query_input.setMinimumHeight(80)
        
        # Character counter
        self.char_count_label = QLabel("0 characters")
        self.char_count_label.setAlignment(Qt.AlignRight)
        
        # Query buttons
        query_buttons_layout = QHBoxLayout()
        
        self.query_button = QPushButton("Get Rule Clarification")
        self.query_button.setMinimumHeight(40)
        self.query_button.setStyleSheet("font-weight: bold;")
        
        self.save_button = QPushButton("Save Result")
        self.save_button.setEnabled(False)
        
        self.save_to_notes_button = QPushButton("Save to Session Notes")
        self.save_to_notes_button.setEnabled(False)
        
        self.clear_button = QPushButton("Clear")
        
        query_buttons_layout.addWidget(self.query_button)
        query_buttons_layout.addWidget(self.save_button)
        query_buttons_layout.addWidget(self.save_to_notes_button)
        query_buttons_layout.addWidget(self.clear_button)
        
        # Add elements to query input layout
        query_input_layout.addWidget(self.query_input)
        query_input_layout.addWidget(self.char_count_label)
        query_input_layout.addLayout(query_buttons_layout)
        
        # Add groups to query widget
        query_layout.addWidget(model_group)
        query_layout.addWidget(suggestions_group)
        query_layout.addWidget(query_input_group)
        
        # === Results Section ===
        results_widget = QWidget()
        results_layout = QVBoxLayout(results_widget)
        results_layout.setContentsMargins(0, 0, 0, 0)
        
        # Results display
        results_group = QGroupBox("Rule Clarification")
        results_inner_layout = QVBoxLayout(results_group)
        
        self.rule_display = QTextEdit()
        self.rule_display.setReadOnly(True)
        self.rule_display.setMinimumHeight(200)
        self.rule_display.setPlaceholderText("Rule interpretations will appear here...")
        
        results_inner_layout.addWidget(self.rule_display)
        results_layout.addWidget(results_group)
        
        # History list
        history_group = QGroupBox("Recent Queries")
        history_layout = QVBoxLayout(history_group)
        
        self.history_list = QListWidget()
        history_layout.addWidget(self.history_list)
        
        results_layout.addWidget(history_group)
        
        # Generation status
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: gray;")
        results_layout.addWidget(self.status_label)
        
        # Add widgets to splitter
        self.splitter.addWidget(query_widget)
        self.splitter.addWidget(results_widget)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 2)
        
        # Add splitter to main layout
        main_layout.addWidget(self.splitter)
    
    def _connect_signals(self):
        """Connect UI signals to handlers"""
        # Button connections
        self.query_button.clicked.connect(self._generate_rule_clarification)
        self.save_button.clicked.connect(self._save_rule)
        self.save_to_notes_button.clicked.connect(self._save_to_session_notes)
        self.clear_button.clicked.connect(self._clear_form)
        
        # Topic button connections
        self.combat_btn.clicked.connect(lambda: self._set_topic("combat"))
        self.spellcasting_btn.clicked.connect(lambda: self._set_topic("spellcasting"))
        self.conditions_btn.clicked.connect(lambda: self._set_topic("conditions"))
        self.classes_btn.clicked.connect(lambda: self._set_topic("classes"))
        self.movement_btn.clicked.connect(lambda: self._set_topic("movement"))
        
        # Text input connections
        self.query_input.textChanged.connect(self._update_char_count)
        
        # History list connection
        self.history_list.itemClicked.connect(self._load_history_item)
        
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
    
    def _update_char_count(self):
        """Update character count for query input"""
        count = len(self.query_input.toPlainText())
        self.char_count_label.setText(f"{count} characters")
        
        # Enable query button only if there's text
        self.query_button.setEnabled(count > 0)
    
    def _set_topic(self, topic):
        """Set a predefined topic in the query input"""
        topic_templates = {
            "combat": "How does [combat mechanic] work in D&D 5e?",
            "spellcasting": "Can you explain how [spell feature] works in D&D 5e?",
            "conditions": "What are the exact effects of the [condition] condition in D&D 5e?",
            "classes": "What are the key features of the [class] class in D&D 5e?",
            "movement": "How does [movement type] movement work in D&D 5e?"
        }
        
        template = topic_templates.get(topic, "How does [rule] work in D&D 5e?")
        current_text = self.query_input.toPlainText()
        
        if current_text:
            # Append to existing text
            self.query_input.setPlainText(f"{current_text}\n\nRelated to {topic}: {template}")
        else:
            # Set new text
            self.query_input.setPlainText(template)
        
        # Focus and move cursor to edit the template placeholder
        self.query_input.setFocus()
        cursor = self.query_input.textCursor()
        text = self.query_input.toPlainText()
        start_pos = text.find('[')
        end_pos = text.find(']')
        
        if start_pos != -1 and end_pos != -1:
            cursor.setPosition(start_pos)
            cursor.setPosition(end_pos + 1, QTextCursor.KeepAnchor)
            self.query_input.setTextCursor(cursor)
    
    def _model_changed(self, index):
        """Handle model selection change"""
        # Update UI based on selected model
        pass
    
    def _generate_rule_clarification(self):
        """Generate a rule clarification using the LLM service"""
        if self.is_generating:
            return
        
        # Get selected model
        model_id = self.model_combo.currentData()
        if not model_id:
            QMessageBox.warning(self, "Model Required", "Please select a valid LLM model.")
            return
        
        # Get the query text
        query_text = self.query_input.toPlainText().strip()
        if not query_text:
            QMessageBox.warning(self, "Query Required", "Please enter a rule question.")
            return
        
        # Create prompt for LLM
        prompt = self._create_rules_prompt(query_text)
        
        # Update UI
        self.is_generating = True
        self.status_label.setText("Generating rule clarification...")
        self.status_label.setStyleSheet("color: blue;")
        self.query_button.setEnabled(False)
        
        # Add to history list
        short_query = query_text[:50] + ("..." if len(query_text) > 50 else "")
        history_item = QListWidgetItem(short_query)
        history_item.setData(Qt.UserRole, query_text)  # Store full query
        self.history_list.insertItem(0, history_item)  # Add at top
        
        # Limit history items
        while self.history_list.count() > 10:
            self.history_list.takeItem(self.history_list.count() - 1)
        
        # Call LLM service
        self.llm_service.generate_completion_async(
            model=model_id,
            messages=[{"role": "user", "content": prompt}],
            callback=self._handle_generation_result,
            temperature=0.3,  # Lower temperature for more deterministic factual responses
            max_tokens=1500
        )
    
    def _create_rules_prompt(self, query_text):
        """Create an optimized prompt for rules clarification"""
        prompt = f"""As a D&D 5e rules expert, please provide a detailed and accurate clarification for the following rules question:

{query_text}

Please include:
1. A direct answer to the question
2. The official rule as written from the Player's Handbook, Dungeon Master's Guide, or other official source
3. Any relevant examples of how the rule works in play
4. Notes on common misunderstandings or edge cases relevant to this question
5. If there are multiple possible interpretations, provide each with its reasoning

Format your answer in clear sections with markdown formatting for readability. Make sure your explanation is accurate according to the official 5th Edition D&D rules published by Wizards of the Coast.
"""
        return prompt
    
    def _handle_generation_result(self, response, error):
        """Handle the result from LLM generation"""
        # Emit signal to update UI from any thread
        self.generation_result.emit(
            response if response else "", 
            error if error else ""
        )
    
    def _update_ui_with_generation_result(self, response, error):
        """Update UI with generation result (runs in UI thread)"""
        self.is_generating = False
        self.query_button.setEnabled(True)
        
        if error:
            self.rule_display.setPlainText(f"Error: {error}")
            self.rule_display.setStyleSheet("color: red;")
            self.status_label.setText(f"Error: {error}")
            self.status_label.setStyleSheet("color: red;")
            self.save_button.setEnabled(False)
            self.save_to_notes_button.setEnabled(False)
            return
        
        # Update UI with generated rule clarification
        self.rule_display.setMarkdown(response)
        self.status_label.setText("Rule clarification generated!")
        self.status_label.setStyleSheet("color: green;")
        
        # Add to history
        query_text = self.query_input.toPlainText()
        item = QListWidgetItem(query_text[:50] + ("..." if len(query_text) > 50 else ""))
        item.setData(Qt.UserRole, query_text)
        self.history_list.insertItem(0, item)
        
        # Enable save buttons
        self.save_button.setEnabled(True)
        self.save_to_notes_button.setEnabled(True)
        
        # Store the response for saving
        self.current_generation = {
            "content": response,
            "type": "rule_clarification",
            "query": self.query_input.toPlainText().strip(),
            "timestamp": self.llm_service.get_timestamp()
        }
    
    def _save_rule(self):
        """Save the generated rule clarification to the data manager"""
        if not hasattr(self, 'current_generation') or not self.current_generation:
            return
        
        # Extract a title from the query
        query_text = self.current_generation.get("query", "")
        title = query_text[:50] + ("..." if len(query_text) > 50 else "")
        
        # Save to data manager
        try:
            # Generate unique ID for this content
            content_id = self.llm_data_manager.add_generated_content(
                title=title,
                content_type="rule_clarification",
                content=self.current_generation["content"],
                model_id=self.model_combo.currentData(),
                prompt=self._create_rules_prompt(query_text),
                tags=["rules", "clarification"]
            )
            
            # Show success message
            self.status_label.setText(f"Rule saved: {title}")
            self.status_label.setStyleSheet("color: green;")
            
            # Emit signal
            self.rule_generated.emit({
                "id": content_id,
                "title": title,
                "content": self.current_generation["content"],
                "type": "rule_clarification",
                "query": query_text
            })
            
        except Exception as e:
            QMessageBox.warning(self, "Save Error", f"Could not save rule clarification: {str(e)}")
    
    def _load_history_item(self, item):
        """Load a rule query from history"""
        query_text = item.data(Qt.UserRole)
        if query_text:
            self.query_input.setPlainText(query_text)
    
    def _save_to_session_notes(self):
        """Save the current rule clarification to session notes"""
        if not hasattr(self, 'current_generation') or not self.current_generation:
            return
        
        # Extract a title from the query
        query_text = self.current_generation.get("query", "")
        title = query_text[:50] + ("..." if len(query_text) > 50 else "")
        
        # Format content for session notes
        formatted_content = f"## Rule Clarification: {title}\n\n"
        formatted_content += f"**Question:**\n{query_text}\n\n"
        formatted_content += f"**Clarification:**\n{self.current_generation['content']}\n\n"
        formatted_content += f"**Model:** {self.model_combo.currentText()}\n"
        formatted_content += f"**Date:** {self.current_generation.get('timestamp', self.llm_service.get_timestamp())}\n"
        
        # Get session notes panel from panel_manager
        panel_manager = self.parent().parent()  # Get to the PanelManager
        session_notes_panel = panel_manager.get_panel("session_notes")
        
        if session_notes_panel:
            # Make sure session notes panel is visible
            session_notes_panel.show()
            
            # Get the widget inside the dock widget
            notes_widget = session_notes_panel.widget()
            
            # Create a new note with the rule clarification
            success = notes_widget._create_note_with_content(
                f"Rule Clarification: {title}", 
                formatted_content,
                tags="rules,clarification,ai"
            )
            
            if success:
                QMessageBox.information(
                    self, 
                    "Rule Added", 
                    f"The rule clarification has been added to your session notes."
                )
            else:
                QMessageBox.warning(
                    self,
                    "Note Creation Failed",
                    "Failed to create note in session notes panel."
                )
        else:
            # Panel not available, show error message
            QMessageBox.warning(
                self, 
                "Session Notes Not Available", 
                "The Session Notes panel is not available. Please open it first."
            )
    
    def _clear_form(self):
        """Clear the form and reset to default state"""
        # Reset input fields
        self.query_input.clear()
        
        # Reset display
        self.rule_display.clear()
        self.rule_display.setPlaceholderText("Rule interpretations will appear here...")
        
        # Disable save buttons
        self.save_button.setEnabled(False)
        self.save_to_notes_button.setEnabled(False)
        
        # Reset status
        self.status_label.setText("Ready")
        self.status_label.setStyleSheet("color: gray;")
        
        # Clear current generation
        self.current_generation = None
        
        # Update character count
        self._update_char_count() 