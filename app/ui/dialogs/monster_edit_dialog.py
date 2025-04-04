# app/ui/dialogs/monster_edit_dialog.py

import asyncio
import json
import logging
from typing import Optional, List
from dataclasses import asdict

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, QTextEdit,
    QSpinBox, QComboBox, QPushButton, QDialogButtonBox, QMessageBox, QLabel,
    QScrollArea, QWidget, QFrame, QGroupBox, QInputDialog, QApplication
)
from PySide6.QtCore import Qt, Slot, QObject, Signal, QRunnable, QThreadPool

from app.core.models.monster import (
    Monster, MonsterSkill, MonsterSense, MonsterTrait, MonsterAction, MonsterLegendaryAction
)
# Assuming LLM service and generator are available. Adjust imports as necessary.
from app.core.llm_service import LLMService
from app.core.llm_integration import monster_generator  # Importing the correct module

# Setup logger
logger = logging.getLogger(__name__)

# --- Async Worker ---
# Helper to run async LLM calls in a separate thread for Qt compatibility

class WorkerSignals(QObject):
    """Defines signals available from a running worker thread."""
    finished = Signal()
    error = Signal(str)
    result = Signal(object) # Emits the result (e.g., Monster object)

class AsyncWorker(QRunnable):
    """Worker thread for running async functions."""
    def __init__(self, async_func, *args, **kwargs):
        super().__init__()
        self.async_func = async_func
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        """Execute the async function."""
        try:
            # Get the current running event loop or create a new one
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            # Run the async function until it completes
            result = loop.run_until_complete(self.async_func(*self.args, **self.kwargs))
            self.signals.result.emit(result)
        except Exception as e:
            logger.error(f"Error in async worker: {e}", exc_info=True)
            self.signals.error.emit(str(e))
        finally:
            self.signals.finished.emit()


# --- Main Dialog ---

class MonsterEditDialog(QDialog):
    """Dialog for creating/editing custom monsters."""

    def __init__(self, monster: Monster, llm_service: LLMService, db_manager, parent=None):
        super().__init__(parent)
        # Ensure the monster passed in is marked as custom
        monster.is_custom = True
        self.monster = monster # Store the monster being edited/created
        self.llm_service = llm_service
        self.db_manager = db_manager # Need this to save
        self.threadpool = QThreadPool() # For running async LLM tasks

        self.setWindowTitle("Create/Edit Custom Monster")
        self.setMinimumSize(700, 800) # Make it reasonably large

        self._setup_ui()
        self._populate_fields() # Fill UI with existing monster data (if editing)

        logger.info(f"MonsterEditDialog initialized for monster: {self.monster.name} (ID: {self.monster.id})")

    def _setup_ui(self):
        """Create the UI elements for the dialog."""
        main_layout = QVBoxLayout(self)

        # Use a scroll area for potentially long content
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        main_layout.addWidget(scroll_area)

        scroll_widget = QWidget()
        scroll_area.setWidget(scroll_widget)
        content_layout = QVBoxLayout(scroll_widget)

        # --- LLM Actions ---
        llm_group = QGroupBox("AI Assistant (LLM)")
        llm_layout = QHBoxLayout()
        self.generate_btn = QPushButton("Generate from Prompt...")
        self.generate_btn.clicked.connect(self._generate_with_llm)
        self.extract_btn = QPushButton("Extract from Text...")
        self.extract_btn.clicked.connect(self._extract_with_llm)
        llm_layout.addWidget(self.generate_btn)
        llm_layout.addWidget(self.extract_btn)
        llm_group.setLayout(llm_layout)
        content_layout.addWidget(llm_group)

        # --- Main Form ---
        form_layout = QFormLayout()
        form_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows) # Wrap long text

        # Core Identification
        self.name_input = QLineEdit()
        form_layout.addRow("Name:", self.name_input)
        self.size_combo = QComboBox()
        self.size_combo.addItems(["Tiny", "Small", "Medium", "Large", "Huge", "Gargantuan"])
        form_layout.addRow("Size:", self.size_combo)
        self.type_input = QLineEdit() # Allow free text for type (e.g., humanoid (elf))
        self.type_input.setPlaceholderText("e.g., beast, humanoid (elf), fiend")
        form_layout.addRow("Type:", self.type_input)
        self.alignment_input = QLineEdit()
        self.alignment_input.setPlaceholderText("e.g., lawful good, neutral, unaligned")
        form_layout.addRow("Alignment:", self.alignment_input)

        # Basic Stats
        self.ac_spin = QSpinBox()
        self.ac_spin.setRange(0, 40); self.ac_spin.setSuffix(" AC")
        form_layout.addRow("Armor Class:", self.ac_spin)
        self.hp_input = QLineEdit() # Keep as string for dice notation
        self.hp_input.setPlaceholderText("e.g., 110 (15d10 + 30)")
        form_layout.addRow("Hit Points:", self.hp_input)
        self.speed_input = QLineEdit()
        self.speed_input.setPlaceholderText("e.g., 30 ft., fly 60 ft.")
        form_layout.addRow("Speed:", self.speed_input)

        # Ability Scores
        abilities_layout = QHBoxLayout()
        self.str_spin = QSpinBox(); self.str_spin.setRange(1, 30)
        self.dex_spin = QSpinBox(); self.dex_spin.setRange(1, 30)
        self.con_spin = QSpinBox(); self.con_spin.setRange(1, 30)
        self.int_spin = QSpinBox(); self.int_spin.setRange(1, 30)
        self.wis_spin = QSpinBox(); self.wis_spin.setRange(1, 30)
        self.cha_spin = QSpinBox(); self.cha_spin.setRange(1, 30)
        abilities_layout.addWidget(QLabel("STR:"))
        abilities_layout.addWidget(self.str_spin)
        abilities_layout.addWidget(QLabel("DEX:"))
        abilities_layout.addWidget(self.dex_spin)
        abilities_layout.addWidget(QLabel("CON:"))
        abilities_layout.addWidget(self.con_spin)
        abilities_layout.addWidget(QLabel("INT:"))
        abilities_layout.addWidget(self.int_spin)
        abilities_layout.addWidget(QLabel("WIS:"))
        abilities_layout.addWidget(self.wis_spin)
        abilities_layout.addWidget(QLabel("CHA:"))
        abilities_layout.addWidget(self.cha_spin)
        form_layout.addRow("Abilities:", abilities_layout)

        # Derived Stats
        self.cr_input = QLineEdit()
        self.cr_input.setPlaceholderText("e.g., 1/2, 5")
        form_layout.addRow("Challenge Rating:", self.cr_input)
        self.languages_input = QLineEdit()
        self.languages_input.setPlaceholderText("Comma-separated, e.g., Common, Draconic")
        form_layout.addRow("Languages:", self.languages_input)

        content_layout.addLayout(form_layout) # Add main form to content layout

        # --- Complex Fields (Text Areas) ---
        # Skills (JSON format for now)
        skills_group = QGroupBox("Skills (JSON: [{\"name\": \"SkillName\", \"modifier\": +/-X}, ...])")
        skills_layout = QVBoxLayout()
        self.skills_edit = QTextEdit()
        self.skills_edit.setAcceptRichText(False)
        self.skills_edit.setPlaceholderText('[{"name": "Perception", "modifier": 5}, {"name": "Stealth", "modifier": 6}]')
        skills_layout.addWidget(self.skills_edit)
        skills_group.setLayout(skills_layout)
        content_layout.addWidget(skills_group)

        # Senses (JSON format for now)
        senses_group = QGroupBox("Senses (JSON: [{\"name\": \"SenseName\", \"range\": \"X ft.\"}, ...])")
        senses_layout = QVBoxLayout()
        self.senses_edit = QTextEdit()
        self.senses_edit.setAcceptRichText(False)
        self.senses_edit.setPlaceholderText('[{"name": "Darkvision", "range": "120 ft."}, {"name": "Passive Perception", "range": "15"}]')
        senses_layout.addWidget(self.senses_edit)
        senses_group.setLayout(senses_layout)
        content_layout.addWidget(senses_group)

        # Traits (JSON format for now)
        traits_group = QGroupBox("Special Traits (JSON: [{\"name\": \"TraitName\", \"description\": \"...\"}, ...])")
        traits_layout = QVBoxLayout()
        self.traits_edit = QTextEdit()
        self.traits_edit.setAcceptRichText(False)
        self.traits_edit.setPlaceholderText('[{"name": "Amphibious", "description": "Can breathe air and water."}, ...]')
        traits_layout.addWidget(self.traits_edit)
        traits_group.setLayout(traits_layout)
        content_layout.addWidget(traits_group)

        # Actions (JSON format for now)
        actions_group = QGroupBox("Actions (JSON: [{\"name\": \"ActionName\", \"description\": \"...\"}, ...])")
        actions_layout = QVBoxLayout()
        self.actions_edit = QTextEdit()
        self.actions_edit.setAcceptRichText(False)
        self.actions_edit.setPlaceholderText('[{"name": "Multiattack", "description": "..."}, {"name": "Bite", "description": "Melee Weapon Attack: +X..."}]')
        actions_layout.addWidget(self.actions_edit)
        actions_group.setLayout(actions_layout)
        content_layout.addWidget(actions_group)

        # Legendary Actions (JSON format for now, or empty/null)
        legendary_group = QGroupBox("Legendary Actions (Optional JSON: [{\"name\": \"ActionName\", \"description\": \"...\", \"cost\": X}, ...])")
        legendary_layout = QVBoxLayout()
        self.legendary_actions_edit = QTextEdit()
        self.legendary_actions_edit.setAcceptRichText(False)
        self.legendary_actions_edit.setPlaceholderText('[{"name": "Detect", "description": "...", "cost": 1}, ...]')
        legendary_layout.addWidget(self.legendary_actions_edit)
        legendary_group.setLayout(legendary_layout)
        content_layout.addWidget(legendary_group)

        # Description
        desc_group = QGroupBox("Description / Lore")
        desc_layout = QVBoxLayout()
        self.description_edit = QTextEdit()
        desc_layout.addWidget(self.description_edit)
        desc_group.setLayout(desc_layout)
        content_layout.addWidget(desc_group)

        # --- Source ---
        source_layout = QHBoxLayout()
        source_layout.addWidget(QLabel("Source:"))
        self.source_input = QLineEdit()
        source_layout.addWidget(self.source_input)
        content_layout.addLayout(source_layout)

        # --- Dialog Buttons (Save/Cancel) ---
        # Placed at the bottom, outside the scroll area
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.accept) # `accept` will trigger validation and saving
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

        # Add status label for LLM operations
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.status_label)

    def _populate_fields(self):
        """Fill the UI fields with data from the self.monster object."""
        if not self.monster:
            return

        # Basic fields
        self.name_input.setText(self.monster.name)
        self.size_combo.setCurrentText(self.monster.size)
        self.type_input.setText(self.monster.type)
        self.alignment_input.setText(self.monster.alignment)
        self.ac_spin.setValue(self.monster.armor_class)
        self.hp_input.setText(self.monster.hit_points)
        self.speed_input.setText(self.monster.speed)
        self.cr_input.setText(self.monster.challenge_rating)
        self.languages_input.setText(self.monster.languages)
        self.description_edit.setText(self.monster.description or "")
        self.source_input.setText(self.monster.source or "Custom") # Default to Custom

        # Abilities
        self.str_spin.setValue(self.monster.strength)
        self.dex_spin.setValue(self.monster.dexterity)
        self.con_spin.setValue(self.monster.constitution)
        self.int_spin.setValue(self.monster.intelligence)
        self.wis_spin.setValue(self.monster.wisdom)
        self.cha_spin.setValue(self.monster.charisma)

        # Complex fields (serialize to JSON for text edits)
        # Wrap in try-except blocks as JSON operations can fail
        try:
            self.skills_edit.setText(json.dumps([asdict(s) for s in self.monster.skills], indent=2) if self.monster.skills else "[]")
        except Exception as e:
            logger.warning(f"Could not serialize skills: {e}")
            self.skills_edit.setText("[]")
        try:
            self.senses_edit.setText(json.dumps([asdict(s) for s in self.monster.senses], indent=2) if self.monster.senses else "[]")
        except Exception as e:
             logger.warning(f"Could not serialize senses: {e}")
             self.senses_edit.setText("[]")
        try:
            self.traits_edit.setText(json.dumps([asdict(t) for t in self.monster.traits], indent=2) if self.monster.traits else "[]")
        except Exception as e:
             logger.warning(f"Could not serialize traits: {e}")
             self.traits_edit.setText("[]")
        try:
            self.actions_edit.setText(json.dumps([asdict(a) for a in self.monster.actions], indent=2) if self.monster.actions else "[]")
        except Exception as e:
             logger.warning(f"Could not serialize actions: {e}")
             self.actions_edit.setText("[]")
        try:
            self.legendary_actions_edit.setText(json.dumps([asdict(la) for la in self.monster.legendary_actions], indent=2) if self.monster.legendary_actions else "null")
        except Exception as e:
             logger.warning(f"Could not serialize legendary actions: {e}")
             self.legendary_actions_edit.setText("null")

    def _update_monster_from_fields(self) -> bool:
        """Update the self.monster object from UI fields. Returns True on success, False on validation/parse error."""
        logger.debug("Updating monster object from UI fields...")
        if not self.monster:
            logger.error("Monster object is None, cannot update.")
            return False

        # Basic fields
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation Error", "Monster name cannot be empty.")
            self.name_input.setFocus()
            return False
        self.monster.name = name
        self.monster.size = self.size_combo.currentText()
        self.monster.type = self.type_input.text().strip()
        self.monster.alignment = self.alignment_input.text().strip()
        self.monster.armor_class = self.ac_spin.value()
        self.monster.hit_points = self.hp_input.text().strip()
        self.monster.speed = self.speed_input.text().strip()
        self.monster.challenge_rating = self.cr_input.text().strip()
        self.monster.languages = self.languages_input.text().strip()
        self.monster.description = self.description_edit.toPlainText().strip() or None # Use None if empty
        self.monster.source = self.source_input.text().strip() or "Custom" # Default source

        # Abilities
        self.monster.strength = self.str_spin.value()
        self.monster.dexterity = self.dex_spin.value()
        self.monster.constitution = self.con_spin.value()
        self.monster.intelligence = self.int_spin.value()
        self.monster.wisdom = self.wis_spin.value()
        self.monster.charisma = self.cha_spin.value()

        # Complex fields (parse from JSON)
        try:
            skills_data = json.loads(self.skills_edit.toPlainText() or "[]")
            self.monster.skills = [MonsterSkill(**s) for s in skills_data if isinstance(s, dict)]
        except json.JSONDecodeError as e:
            QMessageBox.warning(self, "JSON Error", f"Invalid JSON format in Skills field: {e}")
            self.skills_edit.setFocus()
            return False
        except TypeError as e: # Handles cases like wrong dict keys
             QMessageBox.warning(self, "Data Error", f"Error creating Skill objects from JSON: {e}")
             self.skills_edit.setFocus()
             return False

        try:
            senses_data = json.loads(self.senses_edit.toPlainText() or "[]")
            self.monster.senses = [MonsterSense(**s) for s in senses_data if isinstance(s, dict)]
        except json.JSONDecodeError as e:
            QMessageBox.warning(self, "JSON Error", f"Invalid JSON format in Senses field: {e}")
            self.senses_edit.setFocus()
            return False
        except TypeError as e:
             QMessageBox.warning(self, "Data Error", f"Error creating Sense objects from JSON: {e}")
             self.senses_edit.setFocus()
             return False

        try:
            traits_data = json.loads(self.traits_edit.toPlainText() or "[]")
            self.monster.traits = [MonsterTrait(**t) for t in traits_data if isinstance(t, dict)]
        except json.JSONDecodeError as e:
            QMessageBox.warning(self, "JSON Error", f"Invalid JSON format in Traits field: {e}")
            self.traits_edit.setFocus()
            return False
        except TypeError as e:
            QMessageBox.warning(self, "Data Error", f"Error creating Trait objects from JSON: {e}")
            self.traits_edit.setFocus()
            return False

        try:
            actions_data = json.loads(self.actions_edit.toPlainText() or "[]")
            self.monster.actions = [MonsterAction(**a) for a in actions_data if isinstance(a, dict)]
        except json.JSONDecodeError as e:
            QMessageBox.warning(self, "JSON Error", f"Invalid JSON format in Actions field: {e}")
            self.actions_edit.setFocus()
            return False
        except TypeError as e:
             QMessageBox.warning(self, "Data Error", f"Error creating Action objects from JSON: {e}")
             self.actions_edit.setFocus()
             return False

        try:
            legendary_text = self.legendary_actions_edit.toPlainText().strip()
            if not legendary_text or legendary_text.lower() == 'null':
                 self.monster.legendary_actions = None
            else:
                legendary_data = json.loads(legendary_text)
                if legendary_data is None: # Explicit null
                     self.monster.legendary_actions = None
                elif isinstance(legendary_data, list):
                    self.monster.legendary_actions = [MonsterLegendaryAction(**la) for la in legendary_data if isinstance(la, dict)]
                else:
                     raise json.JSONDecodeError("Expected a list or null for Legendary Actions", legendary_text, 0)
        except json.JSONDecodeError as e:
            QMessageBox.warning(self, "JSON Error", f"Invalid JSON format in Legendary Actions field (expected list or null): {e}")
            self.legendary_actions_edit.setFocus()
            return False
        except TypeError as e:
             QMessageBox.warning(self, "Data Error", f"Error creating Legendary Action objects from JSON: {e}")
             self.legendary_actions_edit.setFocus()
             return False

        logger.debug("Successfully updated monster object from UI fields.")
        return True # Success

    # --- LLM Methods ---

    def _run_llm_task(self, task_function, *args):
        """Run an async LLM task in a separate thread."""
        # Disable buttons while LLM task is running
        self.generate_btn.setEnabled(False)
        self.extract_btn.setEnabled(False)
        self.status_label.setText("🔄 AI Assistant is working...")
        
        # Create a worker to run the task asynchronously
        worker = AsyncWorker(task_function, *args)
        worker.signals.result.connect(self._llm_task_finished)
        worker.signals.error.connect(self._llm_task_error)
        worker.signals.finished.connect(self._llm_task_cleanup)
        
        # Start the worker
        self.threadpool.start(worker)

    @Slot()
    def _generate_with_llm(self):
        """Show a dialog to get a prompt for monster generation and start the LLM task."""
        prompt, ok = QInputDialog.getText(self, "Generate Monster", 
            "Enter a prompt describing the monster to generate:\n(e.g., 'A large insectoid creature with poisonous spines')")
        if ok and prompt:
            logger.info(f"Starting LLM generation for prompt: {prompt}")
            # Pass llm_service as the first argument since generate_monster_from_prompt expects it
            self._run_llm_task(monster_generator.generate_monster_from_prompt, self.llm_service, prompt)
        elif ok:
             QMessageBox.warning(self, "Input Needed", "Please enter a prompt for the monster.")

    @Slot()
    def _extract_with_llm(self):
        """Show a dialog to get text containing a monster stat block and start the LLM task."""
        text, ok = QInputDialog.getMultiLineText(self, "Extract Monster", 
             "Paste text containing the monster stat block to extract:")
        if ok and text:
            logger.info("Starting LLM extraction from text.")
            # Pass llm_service as the first argument since extract_monster_from_text expects it
            self._run_llm_task(monster_generator.extract_monster_from_text, self.llm_service, text)
        elif ok:
            QMessageBox.warning(self, "Input Needed", "Please paste the text to extract from.")

    @Slot(object)
    def _llm_task_finished(self, result_monster: Optional[Monster]):
        """Handle successful LLM task result."""
        if result_monster:
            logger.info(f"LLM task successful, received monster: {result_monster.name}")
            # Preserve the existing DB ID if we were editing
            existing_id = self.monster.id
            # Update the dialog's internal monster object with the new data
            self.monster = result_monster
            self.monster.id = existing_id # Restore ID
            self.monster.is_custom = True # Ensure it's marked custom
            # Update UI fields
            self._populate_fields()
            self.status_label.setText("✅ AI Assistant finished. Review and Save.")
        else:
            logger.error("LLM task finished but returned no valid monster data.")
            self.status_label.setText("❌ AI Assistant failed to produce valid data.")
            QMessageBox.warning(self, "LLM Error", "The AI assistant did not return valid monster data. Please check the format or try again.")

    @Slot(str)
    def _llm_task_error(self, error_message: str):
        """Handle error during LLM task."""
        logger.error(f"LLM task failed: {error_message}")
        self.status_label.setText(f"❌ AI Assistant Error: {error_message[:100]}...") # Show truncated error
        QMessageBox.critical(self, "LLM Error", f"An error occurred while communicating with the AI assistant:\n{error_message}")

    @Slot()
    def _llm_task_cleanup(self):
        """Re-enable buttons after LLM task completes or fails."""
        self.generate_btn.setEnabled(True)
        self.extract_btn.setEnabled(True)
        # Optionally clear status label after a delay

    # --- Dialog Actions ---

    def accept(self):
        """Called when Save/OK is clicked. Validates, saves, and closes."""
        logger.info("Save button clicked.")
        if self._update_monster_from_fields():
            logger.info(f"Attempting to save monster: {self.monster.name} (ID: {self.monster.id})")
            try:
                # Save to database using the db_manager
                saved_id = self.db_manager.save_custom_monster(self.monster)
                if saved_id is not None:
                    self.monster.id = saved_id # Ensure ID is updated on the object
                    logger.info(f"Monster saved successfully with ID: {saved_id}")
                    super().accept() # Close dialog if save successful
                else:
                    logger.error("Failed to save monster to database (db_manager returned None).")
                    QMessageBox.critical(self, "Save Error", "Failed to save monster to the database.")
                    # Keep dialog open
            except Exception as e:
                logger.error(f"An error occurred during database save: {e}", exc_info=True)
                QMessageBox.critical(self, "Save Error", f"An unexpected error occurred during save:\n{e}")
                # Keep dialog open
        else:
             logger.warning("Validation failed. Monster not saved.")
             # Keep dialog open, focus should be set by _update_monster_from_fields

    def get_saved_monster(self) -> Optional[Monster]:
        """Returns the monster object if the dialog was accepted AND save was successful."""
        # This should only be called after dialog.exec() == QDialog.Accepted
        # Check if the monster object has an ID, indicating successful save
        if self.monster and self.monster.id is not None:
            return self.monster
        return None

# End of class MonsterEditDialog 