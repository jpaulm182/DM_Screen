"""
LLM Panel for DM Screen

Provides a user interface for interacting with LLM services and managing generated content.
Supports direct chat with LLMs, content generation, and organization of generated materials.
"""

from pathlib import Path
import logging
import json

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton, 
    QComboBox, QLabel, QTabWidget, QLineEdit, QSplitter,
    QToolButton, QMenu, QDialog, QDialogButtonBox, QFormLayout,
    QListWidget, QListWidgetItem, QFileDialog, QInputDialog,
    QScrollArea, QMessageBox, QApplication, QSpinBox
)
from PySide6.QtCore import Qt, Signal, Slot, QSize, QDateTime
from PySide6.QtGui import QIcon, QAction, QTextCursor, QFont

from app.ui.panels.base_panel import BasePanel
from app.core.llm_service import ModelInfo, ModelProvider


class APIKeyDialog(QDialog):
    """Dialog for setting API keys for LLM providers"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("API Key Settings")
        self.setMinimumWidth(400)
        
        # Create layout
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()
        
        # Create widgets
        self.openai_key_input = QLineEdit()
        self.openai_key_input.setEchoMode(QLineEdit.Password)
        self.openai_key_input.setPlaceholderText("sk-...")
        
        self.anthropic_key_input = QLineEdit()
        self.anthropic_key_input.setEchoMode(QLineEdit.Password)
        self.anthropic_key_input.setPlaceholderText("sk-ant-...")
        
        # Add widgets to form layout
        form_layout.addRow("OpenAI API Key:", self.openai_key_input)
        form_layout.addRow("Anthropic API Key:", self.anthropic_key_input)
        
        # Add form layout to main layout
        layout.addLayout(form_layout)
        
        # Add buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def get_api_keys(self):
        """Get the API keys entered by the user"""
        return {
            "openai": self.openai_key_input.text(),
            "anthropic": self.anthropic_key_input.text()
        }
    
    def set_api_keys(self, openai_key="", anthropic_key=""):
        """Set the API keys in the dialog"""
        if openai_key:
            self.openai_key_input.setText(openai_key)
        
        if anthropic_key:
            self.anthropic_key_input.setText(anthropic_key)


class ChatArea(QWidget):
    """
    Widget for chat interactions with LLM models
    """
    
    message_sent = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Create layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Chat display area
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setPlaceholderText("Chat messages will appear here...")
        
        # Message input area
        self.message_input = QTextEdit()
        self.message_input.setPlaceholderText("Type your message here...")
        self.message_input.setMaximumHeight(100)
        
        # Send button
        self.send_button = QPushButton("Send")
        self.send_button.clicked.connect(self.send_message)
        
        # Input container
        input_layout = QHBoxLayout()
        input_layout.addWidget(self.message_input)
        input_layout.addWidget(self.send_button)
        
        # Add widgets to layout
        layout.addWidget(self.chat_display, 1)
        layout.addLayout(input_layout)
        
        # Connect signals
        self.message_input.textChanged.connect(self.update_send_button)
    
    def update_send_button(self):
        """Enable send button only when there's text to send"""
        self.send_button.setEnabled(bool(self.message_input.toPlainText().strip()))
    
    def send_message(self):
        """Send the current message"""
        message = self.message_input.toPlainText().strip()
        if not message:
            return
        
        # Add user message to display
        self.add_message("user", message)
        
        # Clear input
        self.message_input.clear()
        
        # Emit signal with message
        self.message_sent.emit(message)
    
    def add_message(self, role, content):
        """Add a message to the chat display"""
        cursor = self.chat_display.textCursor()
        cursor.movePosition(QTextCursor.End)
        
        # Format based on role
        if role == "user":
            self.chat_display.append("<b>You:</b>")
        elif role == "assistant":
            self.chat_display.append("<b>Assistant:</b>")
        elif role == "system":
            self.chat_display.append("<b>System:</b>")
        else:
            self.chat_display.append(f"<b>{role}:</b>")
        
        # Add content with proper formatting
        self.chat_display.append(content)
        self.chat_display.append("")  # Add empty line for spacing
        
        # Scroll to bottom
        self.chat_display.verticalScrollBar().setValue(
            self.chat_display.verticalScrollBar().maximum()
        )


class GenerationSettingsWidget(QWidget):
    """Widget for adjusting generation settings like temperature and max tokens"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Create layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Temperature setting
        self.temperature_label = QLabel("Temperature:")
        self.temperature_spinner = QSpinBox()
        self.temperature_spinner.setRange(1, 20)  # 0.1 to 2.0
        self.temperature_spinner.setValue(7)  # Default 0.7
        self.temperature_spinner.setToolTip("Controls randomness: 1=deterministic, 20=maximum creativity")
        
        # Max tokens setting
        self.max_tokens_label = QLabel("Max Tokens:")
        self.max_tokens_spinner = QSpinBox()
        self.max_tokens_spinner.setRange(50, 4000)
        self.max_tokens_spinner.setValue(1000)
        self.max_tokens_spinner.setSingleStep(50)
        self.max_tokens_spinner.setToolTip("Maximum tokens to generate")
        
        # Add widgets to layout
        layout.addWidget(self.temperature_label)
        layout.addWidget(self.temperature_spinner)
        layout.addWidget(self.max_tokens_label)
        layout.addWidget(self.max_tokens_spinner)
        layout.addStretch()
    
    def get_temperature(self):
        """Get the temperature value (divided by 10 for actual value)"""
        return self.temperature_spinner.value() / 10.0
    
    def get_max_tokens(self):
        """Get the max tokens value"""
        return self.max_tokens_spinner.value()


class LLMPanel(BasePanel):
    """
    Panel for interacting with LLM services and managing generated content
    """
    
    PANEL_TYPE = "llm"
    PANEL_TITLE = "AI Assistant"
    PANEL_CATEGORY = "Reference"
    PANEL_DESCRIPTION = "Chat with AI models and generate content for your campaign"
    
    def __init__(self, app_state, panel_id=None):
        """Initialize the LLM panel"""
        panel_id = panel_id or "llm"
        super().__init__(app_state, panel_id)
        
        # Get services
        self.llm_service = app_state.llm_service
        self.llm_data_manager = app_state.llm_data_manager
        
        # Initialize UI
        self._init_ui()
        
        # Connect signals
        self._connect_signals()
        
        # Load available models
        self._load_available_models()
        
        # Current conversation tracking
        self.current_conversation_id = None
    
    def _init_ui(self):
        """Initialize the panel UI"""
        # Main layout
        layout = QVBoxLayout(self)
        
        # Control bar
        control_layout = QHBoxLayout()
        
        # Model selection
        model_layout = QHBoxLayout()
        model_label = QLabel("Model:")
        self.model_combo = QComboBox()
        model_layout.addWidget(model_label)
        model_layout.addWidget(self.model_combo)
        
        # Conversation status
        self.conversation_status = QLabel("No active conversation")
        self.conversation_status.setStyleSheet("color: gray;")
        
        # API key button
        self.api_key_button = QToolButton()
        self.api_key_button.setText("API Keys")
        self.api_key_button.setToolTip("Configure API keys for LLM providers")
        self.api_key_button.clicked.connect(self.show_api_key_dialog)
        
        # Reset conversation button
        self.reset_button = QPushButton("Reset Conversation")
        self.reset_button.setToolTip("Start a new conversation")
        self.reset_button.clicked.connect(self.reset_conversation)
        self.reset_button.setEnabled(False)  # Disabled until conversation starts
        
        # Save to notes button
        self.save_to_notes_button = QPushButton("Save to Notes")
        self.save_to_notes_button.setToolTip("Save the current conversation to session notes")
        self.save_to_notes_button.clicked.connect(self._save_to_session_notes)
        self.save_to_notes_button.setEnabled(False)  # Disabled until there's content to save
        
        # Add to control layout
        control_layout.addLayout(model_layout)
        control_layout.addWidget(self.conversation_status)
        control_layout.addStretch()
        control_layout.addWidget(self.reset_button)
        control_layout.addWidget(self.save_to_notes_button)
        control_layout.addWidget(self.api_key_button)
        
        # Generation settings
        self.settings_widget = GenerationSettingsWidget()
        
        # Chat area
        self.chat_area = ChatArea()
        
        # System prompt
        system_layout = QHBoxLayout()
        system_label = QLabel("System Prompt:")
        self.system_prompt_input = QLineEdit()
        self.system_prompt_input.setPlaceholderText("Instructions for the AI assistant...")
        
        # Set default D&D helper system prompt
        default_system_prompt = ("You are a D&D 5e assistant helping a Dungeon Master. "
                                 "Provide concise, accurate information about rules, creatures, spells, "
                                 "and help with creative ideas for the campaign when asked.")
        self.system_prompt_input.setText(default_system_prompt)
        
        system_layout.addWidget(system_label)
        system_layout.addWidget(self.system_prompt_input)
        
        # Add widgets to layout
        layout.addLayout(control_layout)
        layout.addWidget(self.settings_widget)
        layout.addLayout(system_layout)
        layout.addWidget(self.chat_area)
    
    def _connect_signals(self):
        """Connect signals to slots"""
        # Connect chat area message signal
        self.chat_area.message_sent.connect(self.handle_user_message)
        
        # Connect LLM service signals
        self.llm_service.completion_ready.connect(self.handle_llm_response)
        self.llm_service.completion_error.connect(self.handle_llm_error)
    
    def _load_available_models(self):
        """Load available models into the combo box"""
        # Clear existing items
        self.model_combo.clear()
        
        # Check which providers are available
        openai_available = self.llm_service.is_provider_available(ModelProvider.OPENAI)
        anthropic_available = self.llm_service.is_provider_available(ModelProvider.ANTHROPIC)
        
        # Get all models
        models = ModelInfo.get_all_models()
        
        # Add OpenAI models if available
        if openai_available and ModelProvider.OPENAI in models:
            for model in models[ModelProvider.OPENAI]:
                self.model_combo.addItem(model["name"], model["id"])
        
        # Add Anthropic models if available
        if anthropic_available and ModelProvider.ANTHROPIC in models:
            for model in models[ModelProvider.ANTHROPIC]:
                self.model_combo.addItem(model["name"], model["id"])
        
        # If no providers are available, show a placeholder
        if not openai_available and not anthropic_available:
            self.model_combo.addItem("No API keys configured", None)
            self.model_combo.setEnabled(False)
        else:
            self.model_combo.setEnabled(True)
    
    def show_api_key_dialog(self):
        """Show dialog for configuring API keys"""
        dialog = APIKeyDialog(self)
        
        # Prefill with existing keys (if any)
        openai_key = self.app_state.get_setting("openai_api_key", "")
        anthropic_key = self.app_state.get_setting("anthropic_api_key", "")
        dialog.set_api_keys(openai_key, anthropic_key)
        
        # Show dialog
        if dialog.exec():
            # Get and save keys
            keys = dialog.get_api_keys()
            
            # Update OpenAI key if changed
            if keys["openai"] != openai_key:
                self.llm_service.set_api_key(ModelProvider.OPENAI, keys["openai"])
            
            # Update Anthropic key if changed
            if keys["anthropic"] != anthropic_key:
                self.llm_service.set_api_key(ModelProvider.ANTHROPIC, keys["anthropic"])
            
            # Reload models
            self._load_available_models()
    
    def handle_user_message(self, message):
        """Handle a message sent by the user"""
        # Get model and settings
        model_id = self.model_combo.currentData()
        if not model_id:
            self.chat_area.add_message("system", "Please configure an API key for an LLM provider first.")
            return
        
        # Add user message to chat
        self.chat_area.add_message("user", message)
        
        # Show loading indicator
        self.chat_area.add_message("system", "Generating response...")
        
        # Get the system prompt
        system_prompt = self.system_prompt_input.text()
        
        # Create a new conversation if needed
        if not self.current_conversation_id:
            try:
                self.current_conversation_id = self.llm_data_manager.create_conversation(
                    "New Conversation", 
                    model_id,
                    system_prompt=system_prompt
                )
                # Update conversation status
                self._update_conversation_status(True)
            except Exception as e:
                self.chat_area.add_message("system", f"Error creating conversation: {str(e)}")
                return
        
        # Save message to database
        try:
            self.llm_data_manager.add_message(self.current_conversation_id, "user", message)
        except Exception as e:
            self.chat_area.add_message("system", f"Error saving message: {str(e)}")
            # Continue anyway - we can still try to get a response
        
        # Get the complete conversation history
        try:
            messages = []
            conversation_messages = self.llm_data_manager.get_conversation_messages(self.current_conversation_id)
            
            # Format messages for API
            for msg in conversation_messages:
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
        except Exception as e:
            # Fall back to just the current message if there's an error
            self.chat_area.add_message("system", f"Warning: Couldn't retrieve conversation history. Starting fresh.")
            messages = [{"role": "user", "content": message}]
        
        # Get model settings
        temperature = self.settings_widget.get_temperature()
        max_tokens = self.settings_widget.get_max_tokens()
        
        # Send to LLM service
        self.llm_service.generate_completion_async(
            model_id,
            messages,
            self.handle_llm_completion,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens
        )
    
    def handle_llm_completion(self, response, error):
        """Handle completion from the LLM service"""
        # Remove loading message (last message)
        cursor = self.chat_area.chat_display.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.movePosition(QTextCursor.StartOfBlock, QTextCursor.KeepAnchor)
        cursor.movePosition(QTextCursor.PreviousBlock, QTextCursor.KeepAnchor)
        cursor.movePosition(QTextCursor.PreviousBlock, QTextCursor.KeepAnchor)
        cursor.removeSelectedText()
        
        if error:
            # Show error
            self.chat_area.add_message("system", f"Error: {error}")
            return
        
        # Add response to chat
        self.chat_area.add_message("assistant", response)
        
        # Enable save to notes button
        self.save_to_notes_button.setEnabled(True)
        
        # Save to database, but handle errors
        if self.current_conversation_id:
            try:
                self.llm_data_manager.add_message(self.current_conversation_id, "assistant", response)
            except Exception as e:
                self.chat_area.add_message("system", f"Error saving response: {str(e)}")
                # This is non-fatal as the user already has the response in the UI
    
    def handle_llm_response(self, response, request_id):
        """Handle response from LLM service"""
        # If this is handled by the async method, we can ignore this signal
        pass
    
    def handle_llm_error(self, error, request_id):
        """Handle error from LLM service"""
        # If this is handled by the async method, we can ignore this signal
        pass

    def reset_conversation(self):
        """Reset the current conversation"""
        # Ask for confirmation
        reply = QMessageBox.question(
            self,
            "Reset Conversation",
            "This will clear the current conversation history. Continue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Reset conversation ID
            self.current_conversation_id = None
            
            # Clear the chat display
            self.clear_chat_display()
            
            # Update conversation status
            self._update_conversation_status(False)
            
            # Disable save to notes button
            self.save_to_notes_button.setEnabled(False)
            
            # Add system message
            self.chat_area.add_message("system", "Started a new conversation. The AI will not remember previous messages.")
    
    def clear_chat_display(self):
        """Clear the chat display area"""
        self.chat_area.chat_display.clear()
    
    def _update_conversation_status(self, active):
        """Update the conversation status indicator
        
        Args:
            active (bool): Whether a conversation is active
        """
        if active:
            self.conversation_status.setText("Conversation active")
            self.conversation_status.setStyleSheet("color: green; font-weight: bold;")
            self.reset_button.setEnabled(True)
        else:
            self.conversation_status.setText("No active conversation")
            self.conversation_status.setStyleSheet("color: gray;")
            self.reset_button.setEnabled(False)

    def _save_to_session_notes(self):
        """Save the current conversation to session notes"""
        # Get the session notes panel
        notes_widget = None
        
        try:
            # Try to get the session notes panel from app_state
            notes_widget = self.app_state.get_panel_widget("session_notes")
        except Exception as e:
            print(f"Error getting session notes panel: {str(e)}")
        
        # If we couldn't find the notes widget, try other methods
        if not notes_widget:
            # Try to find it using panel_manager
            try:
                if hasattr(self.app_state, 'panel_manager') and hasattr(self.app_state.panel_manager, 'get_panel_widget'):
                    notes_widget = self.app_state.panel_manager.get_panel_widget("session_notes")
            except Exception as e:
                print(f"Error getting session notes panel through panel_manager: {str(e)}")
        
        # Check if we have the widget
        if not notes_widget:
            QMessageBox.warning(self, "Session Notes Not Available", 
                "Session Notes panel is not available. Please open it first.")
            
            # Try to show the Session Notes panel if possible
            try:
                if hasattr(self.app_state, 'panel_manager') and hasattr(self.app_state.panel_manager, 'show_panel'):
                    self.app_state.panel_manager.show_panel("session_notes")
                    QMessageBox.information(
                        self, "Panel Opened", 
                        "The Session Notes panel has been opened. Please try again."
                    )
            except Exception as e:
                print(f"Failed to open Session Notes panel: {str(e)}")
            return
        
        # Extract text from the chat display
        conversation_text = self.chat_area.chat_display.toPlainText()
        if not conversation_text.strip():
            QMessageBox.warning(self, "Empty Conversation", 
                "There is no conversation to save. Please have a conversation first.")
            return
        
        # Set default title and model name
        title = "AI Assistant Conversation"
        model_name = self.model_combo.currentText() or "Unknown Model"
        model_id = self.model_combo.currentData()
        if not model_id:
            # If no model is selected, use basic fallbacks and skip LLM-based enhancements
            tag_string = "ai,assistant"
            
            # Format the content with basic information
            content = (
                f"# {title}\n\n"
                f"## Model\n{model_name}\n\n"
                f"## System Prompt\n{self.system_prompt_input.text()}\n\n"
                f"## Conversation\n{conversation_text}\n\n"
                f"*Generated on {QDateTime.currentDateTime().toString(Qt.ISODate)}*"
            )
            
            # Ensure panel is visible
            parent_dock = notes_widget.parent()
            if parent_dock and hasattr(parent_dock, 'setVisible'):
                parent_dock.setVisible(True)
                parent_dock.raise_()
            
            # Verify the widget has the required method
            if not hasattr(notes_widget, '_create_note_with_content'):
                error_msg = "Session notes panel doesn't have the required method"
                print(error_msg)
                QMessageBox.warning(self, "Error", error_msg)
                return
            
            # Try to create the note with basic information
            try:
                success = notes_widget._create_note_with_content(
                    title=title,
                    content=content,
                    tags=tag_string
                )
                
                if success:
                    QMessageBox.information(
                        self, "Note Created", 
                        "The conversation has been added to your session notes"
                    )
                else:
                    QMessageBox.warning(
                        self, "Note Not Created", 
                        "The note creation was cancelled or failed"
                    )
            except Exception as e:
                error_msg = f"An error occurred while trying to create the note: {str(e)}"
                print(f"Error creating note: {str(e)}")
                QMessageBox.critical(self, "Error", error_msg)
            
            return
        
        # Parse conversation to find the first user message (as a fallback)
        first_user_msg = ""
        try:
            lines = conversation_text.split('\n')
            for i in range(len(lines)):
                if lines[i].strip() == "You:":
                    if i + 1 < len(lines):
                        first_user_msg = lines[i + 1].strip()
                        # Use first user message as title with length limit
                        if first_user_msg:
                            if len(first_user_msg) > 50:
                                title = first_user_msg[:47] + "..."
                            else:
                                title = first_user_msg
                        break
        except Exception as e:
            print(f"Error parsing conversation for first message: {str(e)}")
        
        # Default tags - we'll use these if LLM tag generation fails
        tags = ["ai", "assistant"]
        
        # Try to enhance with keyword-based tags
        try:
            # Check for common D&D related content to add appropriate tags
            lower_text = conversation_text.lower()
            if any(term in lower_text for term in ["spell", "casting", "magic"]):
                tags.append("spells")
            if any(term in lower_text for term in ["monster", "creature", "enemy", "npc"]):
                tags.append("monsters")
            if any(term in lower_text for term in ["combat", "initiative", "attack", "damage"]):
                tags.append("combat")
            if any(term in lower_text for term in ["rule", "rules", "mechanics"]):
                tags.append("rules")
            if any(term in lower_text for term in ["item", "magic item", "weapon", "armor"]):
                tags.append("items")
            if any(term in lower_text for term in ["adventure", "quest", "mission", "plot"]):
                tags.append("adventure")
        except Exception as e:
            print(f"Error generating keyword tags: {str(e)}")
        
        # Default tag string
        tags_string = ",".join(tags)
        
        # Setup content without LLM enhancements
        content = (
            f"# {title}\n\n"
            f"## Model\n{model_name}\n\n"
            f"## System Prompt\n{self.system_prompt_input.text()}\n\n"
            f"## Conversation\n{conversation_text}\n\n"
            f"*Generated on {QDateTime.currentDateTime().toString(Qt.ISODate)}*"
        )
        
        # Ensure panel is visible
        parent_dock = notes_widget.parent()
        if parent_dock and hasattr(parent_dock, 'setVisible'):
            parent_dock.setVisible(True)
            parent_dock.raise_()
        
        # Verify the widget has the required method
        if not hasattr(notes_widget, '_create_note_with_content'):
            error_msg = "Session notes panel doesn't have the required method"
            print(error_msg)
            QMessageBox.warning(self, "Error", error_msg)
            return
        
        # Flag to track if any LLM enhancements were successfully applied
        used_llm_for_title = False
        used_llm_for_tags = False
        
        # Try to get LLM-generated title only if we have an API configured
        try:
            # Create a prompt for title generation
            title_prompt = (
                "Based on the following conversation, generate a concise but descriptive title (maximum 50 characters). "
                "The title should accurately reflect the main topic or purpose of the conversation. "
                "Return ONLY the title with no additional text, quotes, or explanations.\n\n"
                f"System prompt: {self.system_prompt_input.text()}\n\n"
                f"Conversation:\n{conversation_text}"
            )
            
            # Create simple message list for the LLM
            title_messages = [{"role": "user", "content": title_prompt}]
            
            # Generate title synchronously
            title_response = self.llm_service.generate_completion(
                model_id,
                title_messages,
                system_prompt="You are a helpful assistant that generates concise, descriptive titles. Respond with ONLY the title text.",
                temperature=0.3,  # Lower temperature for more consistent results
                max_tokens=20     # Short response needed for title
            )
            
            if title_response and not title_response.startswith("Error:"):
                # Clean up the response
                generated_title = title_response.strip()
                
                # Remove any quotes that might be present
                if generated_title.startswith('"') and generated_title.endswith('"'):
                    generated_title = generated_title[1:-1]
                
                # Limit length
                if len(generated_title) > 50:
                    generated_title = generated_title[:47] + "..."
                
                # Use generated title if it's not empty and differs from default
                if generated_title and generated_title != "AI Assistant Conversation":
                    title = generated_title
                    used_llm_for_title = True
            
        except Exception as e:
            print(f"Error generating title with LLM: {str(e)}")
            # Continue with current title
        
        # Try to generate tags with LLM
        try:
            # Create a prompt for tag generation
            tag_prompt = (
                "Based on the following conversation, generate appropriate tags for organizing this note. "
                "Focus on D&D 5e related concepts, topics and themes. "
                "Return only a comma-separated list of 3-8 tags, with no explanations or other text. "
                "Always include 'ai' and 'assistant' as tags.\n\n"
                f"System prompt: {self.system_prompt_input.text()}\n\n"
                f"Conversation:\n{conversation_text}"
            )
            
            # Create simple message list for the LLM
            tag_messages = [{"role": "user", "content": tag_prompt}]
            
            # Generate tags synchronously (ok for a short response)
            tags_response = self.llm_service.generate_completion(
                model_id,
                tag_messages,
                system_prompt="You are a helpful assistant that generates concise, relevant tags for D&D 5e content.",
                temperature=0.3,  # Lower temperature for more consistent results
                max_tokens=50     # Short response needed
            )
            
            if tags_response and not tags_response.startswith("Error:"):
                # Clean up the response to ensure it's just tags
                candidate_tags_string = tags_response.strip()
                
                # Remove any non-tag text (explanations, etc.)
                if "," in candidate_tags_string:
                    # Split by commas, trim whitespace, and rejoin
                    candidate_tags = [tag.strip() for tag in candidate_tags_string.split(",")]
                    
                    # Ensure we have the default tags
                    if "ai" not in candidate_tags:
                        candidate_tags.insert(0, "ai")
                    if "assistant" not in candidate_tags:
                        candidate_tags.insert(1, "assistant")
                    
                    # Only use if we got more than just the default tags
                    if len(candidate_tags) > 2:
                        # Rejoin into a comma-separated string
                        tags_string = ",".join(candidate_tags)
                        used_llm_for_tags = True
        except Exception as e:
            print(f"Error generating tags with LLM: {str(e)}")
            # Continue with current tags
        
        # Try to create the note
        try:
            # Add notes about AI-generated content
            ai_notes = []
            
            # Add note about AI-generated title if we successfully used the LLM for title
            if used_llm_for_title:
                ai_notes.append("*Title was automatically generated using AI*")
            
            # Add note about AI-generated tags if we successfully used the LLM for tags
            if used_llm_for_tags:
                ai_notes.append("*Tags were automatically generated using AI analysis of the conversation content*")
            
            # Combine notes if any
            ai_notes_text = ""
            if ai_notes:
                ai_notes_text = "\n\n" + "\n".join(ai_notes)
            
            content_with_notes = content + ai_notes_text
            
            # Save the note
            success = notes_widget._create_note_with_content(
                title=title,
                content=content_with_notes,
                tags=tags_string
            )
            
            if success:
                QMessageBox.information(
                    self, "Note Created", 
                    "The conversation has been added to your session notes"
                )
            else:
                QMessageBox.warning(
                    self, "Note Not Created", 
                    "The note creation was cancelled or failed"
                )
        except Exception as e:
            error_msg = f"An error occurred while trying to create the note: {str(e)}"
            print(f"Error creating note: {str(e)}")
            QMessageBox.critical(self, "Error", error_msg) 