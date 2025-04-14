"""
Session Notes Panel

Provides a system for creating, editing, and managing session notes with tagging functionality.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QTextEdit, QListWidget, QListWidgetItem, 
    QSplitter, QMenu, QDialog, QFormLayout, QDialogButtonBox,
    QMessageBox, QComboBox, QProgressDialog, QApplication,
    QTextBrowser
)
from PySide6.QtCore import Qt, Signal, QDateTime, Slot
from PySide6.QtGui import QFont, QAction, QIcon
import re
import json

from app.ui.panels.base_panel import BasePanel


class TagInputDialog(QDialog):
    """Dialog for entering tags for a note"""
    
    def __init__(self, parent=None, existing_tags=None):
        """Initialize the tag input dialog"""
        super().__init__(parent)
        self.setWindowTitle("Add Tags")
        
        self.existing_tags = existing_tags or []
        self.selected_tags = []
        
        # Layout
        layout = QVBoxLayout(self)
        
        # Existing tags
        if self.existing_tags:
            layout.addWidget(QLabel("Select existing tags:"))
            self.tag_list = QListWidget()
            self.tag_list.setSelectionMode(QListWidget.MultiSelection)
            
            for tag in sorted(self.existing_tags):
                item = QListWidgetItem(tag)
                self.tag_list.addItem(item)
            
            layout.addWidget(self.tag_list)
        
        # New tag input
        layout.addWidget(QLabel("Add new tags (comma separated):"))
        self.new_tags_input = QLineEdit()
        layout.addWidget(self.new_tags_input)
        
        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
    def get_tags(self):
        """Get the selected and new tags"""
        tags = []
        
        # Get selected existing tags
        if hasattr(self, 'tag_list'):
            for item in self.tag_list.selectedItems():
                tags.append(item.text())
        
        # Get new tags
        new_tags = self.new_tags_input.text()
        if new_tags:
            # Split by comma and strip whitespace
            for tag in new_tags.split(','):
                tag = tag.strip()
                if tag and tag not in tags:
                    tags.append(tag)
        
        return tags


class NoteEditDialog(QDialog):
    """Dialog for creating/editing notes"""
    
    def __init__(self, parent=None, app_state=None, note=None, tags=None):
        """Initialize the note edit dialog"""
        super().__init__(parent)
        self.app_state = app_state
        self.note = note
        self.all_tags = tags or []
        
        title = "Edit Note" if note else "New Note"
        self.setWindowTitle(title)
        self.resize(600, 400)
        
        # Create layout
        layout = QVBoxLayout(self)
        
        # Form layout for title and tags
        form_layout = QFormLayout()
        
        # Title field
        self.title_input = QLineEdit()
        if note:
            self.title_input.setText(note['title'])
        form_layout.addRow("Title:", self.title_input)
        
        # Tags display
        self.tags_display = QLineEdit()
        self.tags_display.setReadOnly(True)
        if note and note.get('tags'):
            self.current_tags = note.get('tags').split(',')
            self.tags_display.setText(', '.join(self.current_tags))
        else:
            self.current_tags = []
        
        # Tags edit button
        tags_layout = QHBoxLayout()
        tags_layout.addWidget(self.tags_display)
        
        self.edit_tags_btn = QPushButton("Edit Tags")
        self.edit_tags_btn.clicked.connect(self._edit_tags)
        tags_layout.addWidget(self.edit_tags_btn)
        
        form_layout.addRow("Tags:", tags_layout)
        
        layout.addLayout(form_layout)
        
        # Content area
        layout.addWidget(QLabel("Content:"))
        self.content_edit = QTextEdit()
        if note:
            self.content_edit.setText(note['content'])
        layout.addWidget(self.content_edit)
        
        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def _edit_tags(self):
        """Open the tag editing dialog"""
        dialog = TagInputDialog(self, self.all_tags)
        
        # Pre-select current tags
        if hasattr(dialog, 'tag_list'):
            for i in range(dialog.tag_list.count()):
                item = dialog.tag_list.item(i)
                if item.text() in self.current_tags:
                    item.setSelected(True)
        
        if dialog.exec():
            self.current_tags = dialog.get_tags()
            self.tags_display.setText(', '.join(self.current_tags))
    
    def get_note_data(self):
        """Get the note data from the form"""
        title = self.title_input.text().strip()
        content = self.content_edit.toPlainText()
        tags = ','.join(self.current_tags) if self.current_tags else ""
        
        if not title:
            QMessageBox.warning(self, "Warning", "Please enter a title for the note.")
            return None
        
        note_data = {
            'title': title,
            'content': content,
            'tags': tags
        }
        
        # If editing, preserve the ID
        if self.note and 'id' in self.note:
            note_data['id'] = self.note['id']
        
        return note_data


class RecapDialog(QDialog):
    """Dialog for generating session recaps"""
    
    def __init__(self, parent=None, app_state=None, notes=None):
        """Initialize the recap dialog"""
        super().__init__(parent)
        self.app_state = app_state
        self.notes = notes or []
        
        self.setWindowTitle("Generate Session Recap")
        self.resize(700, 500)
        
        # Create layout
        layout = QVBoxLayout(self)
        
        # Explanation label
        info_label = QLabel(
            "This will generate a session recap for players based on the selected notes. "
            "You can customize the style and level of detail for the recap."
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # Form layout for options
        form_layout = QFormLayout()
        
        # Style selector
        self.style_combo = QComboBox()
        self.style_combo.addItems([
            "Narrative", 
            "Bullet Points",
            "In-character",
            "Quest Log",
            "Formal Report"
        ])
        form_layout.addRow("Recap Style:", self.style_combo)
        
        # Detail level
        self.detail_combo = QComboBox()
        self.detail_combo.addItems([
            "Brief (key points only)",
            "Standard (balanced detail)",
            "Detailed (comprehensive)"
        ])
        form_layout.addRow("Detail Level:", self.detail_combo)
        
        layout.addLayout(form_layout)
        
        # Preview of notes to include
        layout.addWidget(QLabel("Notes being included:"))
        
        self.notes_list = QListWidget()
        for note in self.notes:
            self.notes_list.addItem(note['title'])
        layout.addWidget(self.notes_list)
        
        # Generated content
        layout.addWidget(QLabel("Generated Recap:"))
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        layout.addWidget(self.result_text)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.generate_btn = QPushButton("Generate Recap")
        self.generate_btn.clicked.connect(self._generate_recap)
        button_layout.addWidget(self.generate_btn)
        
        self.save_btn = QPushButton("Save as Note")
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self._save_as_note)
        button_layout.addWidget(self.save_btn)
        
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.close_btn)
        
        layout.addLayout(button_layout)
    
    def _generate_recap(self):
        """Generate the session recap using LLM"""
        style = self.style_combo.currentText()
        detail = self.detail_combo.currentText()
        
        # Create progress dialog
        progress = QProgressDialog("Generating recap...", "Cancel", 0, 0, self)
        progress.setWindowTitle("Please Wait")
        progress.setWindowModality(Qt.WindowModal)
        progress.show()
        QApplication.processEvents()
        
        try:
            # Prepare the content from the notes
            note_content = ""
            for note in self.notes:
                note_content += f"--- {note['title']} ---\n"
                note_content += f"{note['content']}\n\n"
            
            # Create a prompt for the LLM
            prompt = f"""
Generate a {detail.split('(')[0].strip().lower()} session recap for D&D players in {style.lower()} style.
This should summarize the key events, discoveries, and important NPCs from the following session notes.
Use language appropriate for players (not the DM).

SESSION NOTES:
{note_content}
"""
            
            # Call the LLM
            llm_service = self.app_state.llm_service
            result = llm_service.generate_text(prompt, max_tokens=1000)
            
            # Update the result text
            self.result_text.setText(result)
            self.save_btn.setEnabled(True)
            
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to generate recap: {str(e)}")
        finally:
            progress.close()
    
    def _save_as_note(self):
        """Save the generated recap as a new note"""
        style = self.style_combo.currentText()
        recap_text = self.result_text.toPlainText()
        
        if not recap_text:
            return
        
        # Create a title with date
        current_datetime = QDateTime.currentDateTime()
        date_str = current_datetime.toString("yyyy-MM-dd")
        title = f"Session Recap ({style}) - {date_str}"
        
        # Create a new note with the recap content
        parent = self.parent()
        if parent:
            parent._create_note_with_content(title, recap_text, tags="recap,summary")
            
            # Update the last recap date in app settings
            iso_date = current_datetime.toString(Qt.ISODate)
            parent.last_recap_date = iso_date
            parent.app_state.set_setting("last_recap_date", iso_date)
            parent.app_state.save_settings()
            
            QMessageBox.information(
                self, "Success", 
                "Session recap saved as a new note."
            )
            self.accept()


class SessionNotesPanel(BasePanel):
    """
    Panel for session note management with tag filtering
    """
    
    def __init__(self, app_state, panel_id=None):
        """Initialize the session notes panel"""
        # Initialize data before calling the parent constructor
        self.notes = []
        self.filtered_notes = []
        self.all_tags = []
        self.current_note = None
        
        # This date tracks when the last recap was generated
        # When generating a new recap, only notes created or updated after
        # this date will be included by default, unless notes are explicitly selected
        self.last_recap_date = None
        
        # Call parent constructor which will call _setup_ui
        super().__init__(app_state, "Session Notes")
        
        # Load notes
        self._load_notes()
        
        # Load last recap date from settings
        self.last_recap_date = self.app_state.get_setting("last_recap_date")
    
    def _setup_ui(self):
        """Set up the panel UI components"""
        # Create a new layout directly on this widget
        layout = QVBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        
        # Create header controls
        header_layout = QHBoxLayout()
        
        # Add new note button
        self.add_btn = QPushButton("New Note")
        self.add_btn.clicked.connect(self._create_note)
        header_layout.addWidget(self.add_btn)
        
        # Add edit button
        self.edit_btn = QPushButton("Edit")
        self.edit_btn.clicked.connect(self._edit_note)
        self.edit_btn.setEnabled(False)  # Disabled until a note is selected
        header_layout.addWidget(self.edit_btn)
        
        # Add delete button
        self.delete_btn = QPushButton("Delete")
        self.delete_btn.clicked.connect(self._delete_note)
        self.delete_btn.setEnabled(False)  # Disabled until a note is selected
        header_layout.addWidget(self.delete_btn)
        
        # Add recap button
        self.recap_btn = QPushButton("Generate Recap")
        self.recap_btn.clicked.connect(self._generate_recap)
        header_layout.addWidget(self.recap_btn)
        
        # Add spacer
        header_layout.addStretch()
        
        # Add search field
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search notes...")
        self.search_input.textChanged.connect(self._filter_notes)
        header_layout.addWidget(self.search_input)
        
        # Add header to layout
        layout.addLayout(header_layout)
        
        # Create splitter
        splitter = QSplitter(Qt.Horizontal)
        
        # Left pane - note list and controls
        left_pane = QWidget()
        left_layout = QVBoxLayout(left_pane)
        
        # Search and filter
        filter_layout = QHBoxLayout()
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search notes...")
        self.search_input.textChanged.connect(self._filter_notes)
        filter_layout.addWidget(self.search_input)
        
        self.tag_filter = QComboBox()
        self.tag_filter.addItem("All Tags", "")
        self.tag_filter.currentIndexChanged.connect(self._filter_notes)
        filter_layout.addWidget(self.tag_filter)
        
        left_layout.addLayout(filter_layout)
        
        # Notes list
        self.notes_list = QListWidget()
        self.notes_list.itemClicked.connect(self._note_selected)
        self.notes_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.notes_list.customContextMenuRequested.connect(self._show_context_menu)
        left_layout.addWidget(self.notes_list)
        
        # Note management buttons
        buttons_layout = QHBoxLayout()
        
        self.new_btn = QPushButton("New Note")
        self.new_btn.clicked.connect(self._create_note)
        buttons_layout.addWidget(self.new_btn)
        
        self.edit_btn = QPushButton("Edit")
        self.edit_btn.clicked.connect(self._edit_note)
        self.edit_btn.setEnabled(False)
        buttons_layout.addWidget(self.edit_btn)
        
        self.delete_btn = QPushButton("Delete")
        self.delete_btn.clicked.connect(self._delete_note)
        self.delete_btn.setEnabled(False)
        buttons_layout.addWidget(self.delete_btn)
        
        left_layout.addLayout(buttons_layout)
        
        # Right pane - note display
        right_pane = QWidget()
        right_layout = QVBoxLayout(right_pane)
        
        # Note title
        self.note_title = QLabel()
        font = QFont()
        font.setBold(True)
        font.setPointSize(14)
        self.note_title.setFont(font)
        right_layout.addWidget(self.note_title)
        
        # Note metadata
        self.note_metadata = QLabel()
        right_layout.addWidget(self.note_metadata)
        
        # Note tags
        self.note_tags = QLabel()
        right_layout.addWidget(self.note_tags)
        
        # Note content
        self.note_content = QTextBrowser()
        self.note_content.setReadOnly(True)
        right_layout.addWidget(self.note_content)
        self.note_content.setOpenLinks(False)
        self.note_content.setOpenExternalLinks(False)
        self.note_content.anchorClicked.connect(self._handle_note_link_clicked)
        
        # Add panes to splitter
        splitter.addWidget(left_pane)
        splitter.addWidget(right_pane)
        
        # Set initial sizes
        splitter.setSizes([200, 400])
        
        # Add the splitter to the main layout
        layout.addWidget(splitter)
    
    def _load_notes(self):
        """Load notes from database"""
        try:
            # Use database to load notes
            query = "SELECT * FROM session_notes ORDER BY updated_at DESC"
            self.notes = self.app_state.db_manager.execute_query(query)
            
            # If no notes found, create an empty list
            if not self.notes:
                self.notes = []
                
            self.filtered_notes = self.notes.copy()
            
            # Update notes list
            self._update_notes_list()
            
            # Collect all tags
            self._update_tag_list()
        except Exception as e:
            print(f"Error loading notes from database: {e}")
            # Fall back to mock data for testing/development
            self.notes = self._get_mock_notes()
            self.filtered_notes = self.notes.copy()
            self._update_notes_list()
            self._update_tag_list()
    
    def _get_mock_notes(self):
        """Return mock note data for testing"""
        return [
            {
                'id': 1,
                'title': 'Session 1: Campaign Start',
                'content': 'The party met at the Prancing Pony tavern in Fallcrest. They accepted a quest from Lord Markelhay to investigate disappearances in the nearby forest. Key NPCs: Bartender Joren, Guard Captain Serena, Lord Markelhay.',
                'tags': 'session,npc,quest',
                'created_at': '2023-01-15T18:30:00',
                'updated_at': '2023-01-15T18:30:00'
            },
            {
                'id': 2,
                'title': 'Important NPCs in Fallcrest',
                'content': '- Lord Markelhay: Ruler of Fallcrest, elderly but wise\n- Guard Captain Serena: Tough, no-nonsense leader of town guard\n- Joren: Bartender at Prancing Pony, knows many rumors\n- Theren: Elven sage at the library, knowledgeable about local history\n- Blacksmith Durnan: Dwarven smith, crafts fine weapons',
                'tags': 'npc,location,fallcrest',
                'created_at': '2023-01-16T10:15:00',
                'updated_at': '2023-01-18T14:22:00'
            },
            {
                'id': 3,
                'title': 'Session 2: The Forest Path',
                'content': 'The party traveled to the Harken Forest. They encountered a group of goblins that ambushed travelers. After defeating them, they found a map leading to a hidden cave. They camped for the night and will explore the cave next session.',
                'tags': 'session,combat,location',
                'created_at': '2023-01-22T19:00:00',
                'updated_at': '2023-01-22T23:15:00'
            },
            {
                'id': 4,
                'title': 'Magic Items Found',
                'content': '- Cloak of Elvenkind: Found in goblin camp, given to the rogue\n- +1 Shortsword: Taken from goblin leader\n- Potion of Healing (3): Found in various locations\n- Scroll of Identify: Not yet used',
                'tags': 'loot,magic items',
                'created_at': '2023-01-23T09:30:00',
                'updated_at': '2023-01-25T16:45:00'
            }
        ]
    
    def _update_notes_list(self):
        """Update the notes list widget"""
        self.notes_list.clear()
        
        for note in self.filtered_notes:
            item = QListWidgetItem(note['title'])
            item.setData(Qt.UserRole, note['id'])
            
            # Add timestamp tooltip
            created_date = QDateTime.fromString(note['created_at'], Qt.ISODate)
            updated_date = QDateTime.fromString(note['updated_at'], Qt.ISODate)
            
            created_str = created_date.toString("yyyy-MM-dd hh:mm:ss")
            updated_str = updated_date.toString("yyyy-MM-dd hh:mm:ss")
            
            # Format the tooltip with both timestamps
            tooltip = f"Created: {created_str}\nUpdated: {updated_str}"
            
            # Add tags to tooltip if available
            if note.get('tags'):
                tags = note['tags'].split(',')
                tooltip += f"\nTags: {', '.join(tags)}"
                
            item.setToolTip(tooltip)
            
            self.notes_list.addItem(item)
    
    def _update_tag_list(self):
        """Update the tag filter dropdown"""
        self.all_tags = set()
        
        # Collect all tags from notes
        for note in self.notes:
            if note.get('tags'):
                tags = note['tags'].split(',')
                for tag in tags:
                    tag = tag.strip()
                    if tag:
                        self.all_tags.add(tag)
        
        # Save current selection
        current_tag = self.tag_filter.currentData()
        
        # Clear and repopulate
        self.tag_filter.clear()
        self.tag_filter.addItem("All Tags", "")
        
        for tag in sorted(self.all_tags):
            self.tag_filter.addItem(tag, tag)
        
        # Restore selection if possible
        if current_tag:
            index = self.tag_filter.findData(current_tag)
            if index >= 0:
                self.tag_filter.setCurrentIndex(index)
    
    def _filter_notes(self):
        """Filter notes based on search text and selected tag"""
        search_text = self.search_input.text().lower()
        tag_filter = self.tag_filter.currentData()
        
        self.filtered_notes = []
        
        for note in self.notes:
            # Check if note matches search text
            if search_text and search_text not in note['title'].lower() and search_text not in note['content'].lower():
                continue
            
            # Check if note has the selected tag
            if tag_filter and (not note.get('tags') or tag_filter not in note['tags'].split(',')):
                continue
            
            self.filtered_notes.append(note)
        
        self._update_notes_list()
    
    def _note_selected(self, item):
        """Handle note selection"""
        note_id = item.data(Qt.UserRole)
        
        # Find the note
        for note in self.notes:
            if note['id'] == note_id:
                self.current_note = note
                break
        
        if self.current_note:
            # Update display
            self.note_title.setText(self.current_note['title'])
            
            # Format date
            created_date = QDateTime.fromString(self.current_note['created_at'], Qt.ISODate)
            updated_date = QDateTime.fromString(self.current_note['updated_at'], Qt.ISODate)
            
            created_str = created_date.toString("yyyy-MM-dd hh:mm:ss")
            updated_str = updated_date.toString("yyyy-MM-dd hh:mm:ss")
            
            self.note_metadata.setText(f"Created: {created_str} | Updated: {updated_str}")
            
            # Display tags
            if self.current_note.get('tags'):
                tags = self.current_note['tags'].split(',')
                self.note_tags.setText(f"Tags: {', '.join(tags)}")
            else:
                self.note_tags.setText("Tags: None")
            
            # Display content with type-specific formatting
            self._display_formatted_content(self.current_note)
            
            # Enable edit/delete buttons
            self.edit_btn.setEnabled(True)
            self.delete_btn.setEnabled(True)
    
    def _display_formatted_content(self, note):
        """Display note content with type-specific formatting based on tags and content"""
        # Get content and tags
        content = note.get('content', '')
        tags = note.get('tags', '').lower().split(',')
        title = note.get('title', '').lower()
        
        # Detect content type based on title, tags, and content structure
        content_type = self._detect_content_type(note)
        
        # Create HTML content with appropriate styling
        html_content = f"""
        <html>
        <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #e0e0e0; background-color: #1e1e1e; }}
            h1 {{ color: #81a1c1; font-size: 20px; margin-top: 12px; margin-bottom: 8px; }}
            h2 {{ color: #88c0d0; font-size: 18px; margin-top: 15px; margin-bottom: 6px; }}
            h3 {{ color: #8fbcbb; font-size: 16px; margin-top: 10px; margin-bottom: 5px; }}
            p {{ margin: 8px 0; color: #d8dee9; }}
            ul {{ margin: 5px 0; padding-left: 20px; }}
            li {{ color: #d8dee9; }}
            .metadata {{ color: #a0a0a0; font-style: italic; font-size: 0.9em; }}
            .monster {{ background-color: #2e2220; padding: 15px; border-left: 3px solid #bf616a; border-radius: 4px; margin-bottom: 10px; }}
            .location {{ background-color: #1e2b23; padding: 15px; border-left: 3px solid #a3be8c; border-radius: 4px; margin-bottom: 10px; }}
            .recap {{ background-color: #1a2533; padding: 15px; border-left: 3px solid #5e81ac; border-radius: 4px; margin-bottom: 10px; }}
            .ai {{ background-color: #2a2438; padding: 15px; border-left: 3px solid #b48ead; border-radius: 4px; margin-bottom: 10px; }}
            .loot {{ background-color: #2d2922; padding: 15px; border-left: 3px solid #ebcb8b; border-radius: 4px; margin-bottom: 10px; }}
            .rules {{ background-color: #2a2826; padding: 15px; border-left: 3px solid #d08770; border-radius: 4px; margin-bottom: 10px; }}
            .property {{ font-weight: bold; color: #eceff4; }}
            .stat-block {{ background-color: #2e3440; padding: 10px; margin: 8px 0; border-radius: 4px; border: 1px solid #3b4252; }}
            table {{ border-collapse: collapse; width: 100%; margin: 10px 0; }}
            th {{ background-color: #3b4252; color: #eceff4; padding: 8px; text-align: left; border: 1px solid #4c566a; }}
            td {{ border: 1px solid #4c566a; padding: 8px; text-align: left; color: #d8dee9; }}
            .header-icon {{ margin-right: 5px; }}
            .location-header {{ background-color: #2e3c34; padding: 10px; border-radius: 4px; margin-bottom: 15px; }}
            .location-section {{ margin-top: 15px; margin-bottom: 15px; }}
            .section-title {{ font-weight: bold; color: #a3be8c; }}
            .npc-block {{ padding: 8px; border-left: 2px solid #5e81ac; margin: 8px 0; background-color: #2e3440; border-radius: 0 4px 4px 0; }}
            .poi-block {{ padding: 8px; border-left: 2px solid #ebcb8b; margin: 8px 0; background-color: #2e3440; border-radius: 0 4px 4px 0; }}
            .secret-block {{ padding: 8px; border-left: 2px solid #b48ead; margin: 8px 0; background-color: #2e3440; border-radius: 0 4px 4px 0; }}
            strong {{ color: #ebcb8b; }}
            em {{ color: #a3be8c; font-style: italic; }}
            a {{ color: #88c0d0; text-decoration: none; }}
            a:hover {{ text-decoration: underline; }}
        </style>
        </head>
        <body>
        """
        
        # Add type-specific container
        if content_type == 'monster':
            html_content += '<div class="monster">'
        elif content_type == 'location':
            html_content += '<div class="location">'
        elif content_type == 'recap':
            html_content += '<div class="recap">'
        elif content_type == 'ai':
            html_content += '<div class="ai">'
        elif content_type == 'loot':
            html_content += '<div class="loot">'
        elif content_type == 'rules':
            html_content += '<div class="rules">'
        else:
            html_content += '<div>'
        
        # Process the content based on its type
        if content_type == 'monster':
            html_content += self._format_monster_content(content)
        elif content_type == 'location':
            html_content += self._format_location_content(content)
        elif content_type == 'recap':
            html_content += self._format_recap_content(content)
        elif content_type == 'ai':
            html_content += self._format_ai_content(content)
        elif content_type == 'loot':
            html_content += self._format_loot_content(content)
        elif content_type == 'rules':
            html_content += self._format_rules_content(content)
        else:
            # Default markdown-like formatting for regular notes
            html_content += self._format_default_content(content)
        
        # Close the container div and HTML
        html_content += "</div></body></html>"
        
        # Set the formatted content
        self.note_content.setHtml(html_content)
    
    def _detect_content_type(self, note):
        """Detect the type of content based on title, tags, and content analysis"""
        title = note.get('title', '').lower()
        tags = note.get('tags', '').lower().split(',')
        content = note.get('content', '')
        
        # Try to parse content as JSON first - this could override other types
        try:
            # Look for JSON in code blocks
            json_match = re.search(r'```json\s*([\s\S]*?)\s*```', content)
            if json_match:
                # Found a JSON code block
                json_content = json_match.group(1).strip()
                json_data = json.loads(json_content)
                
                # Determine the type of JSON
                if "narrative_output" in json_data:
                    return 'location'  # Most location data has narrative_output
                elif "name" in json_data and any(key in json_data for key in ["type", "environment", "points_of_interest", "npcs", "description", "size_scale"]):
                    return 'location'
                elif "hp" in json_data and "ac" in json_data and any(stat in json_data for stat in ["str", "dex", "con", "int", "wis", "cha"]):
                    return 'monster'
                elif "items" in json_data or "treasure" in json_data or "gold" in json_data:
                    return 'loot'
            
            # If no code block, try raw JSON
            elif content.strip().startswith('{') and content.strip().endswith('}'):
                json_data = json.loads(content.strip())
                
                # Determine the type of JSON
                if "narrative_output" in json_data:
                    return 'location'
                elif "name" in json_data and any(key in json_data for key in ["type", "environment", "points_of_interest", "npcs", "description", "size_scale"]):
                    return 'location'
                elif "hp" in json_data and "ac" in json_data and any(stat in json_data for stat in ["str", "dex", "con", "int", "wis", "cha"]):
                    return 'monster'
                elif "items" in json_data or "treasure" in json_data or "gold" in json_data:
                    return 'loot'
                
        except json.JSONDecodeError:
            # Not valid JSON, continue with normal detection
            pass
        except Exception as e:
            # Log the error but continue with normal detection
            print(f"Error parsing potential JSON content: {e}")
            
        # Try to identify content type from tags first (most reliable)
        if any(tag in ['monster', 'creature', 'npc', 'enemy'] for tag in tags):
            return 'monster'
        elif any(tag in ['location', 'place', 'setting', 'dungeon', 'town', 'city'] for tag in tags):
            return 'location'
        elif any(tag in ['recap', 'summary', 'session recap'] for tag in tags):
            return 'recap'
        elif any(tag in ['ai', 'assistant', 'llm'] for tag in tags):
            return 'ai'
        elif any(tag in ['loot', 'treasure', 'item', 'items', 'magic items'] for tag in tags):
            return 'loot'
        elif any(tag in ['rules', 'rule', 'clarification'] for tag in tags):
            return 'rules'
        
        # If tags don't provide clear identification, look at the title
        if 'location:' in title or any(term in title for term in ['monster', 'creature', 'npc']):
            return 'monster'
        elif 'location:' in title or any(term in title for term in ['location', 'place', 'town', 'city', 'dungeon', 'fortress', 'lair']):
            return 'location'
        elif 'recap' in title or 'summary' in title:
            return 'recap'
        elif 'ai' in title or 'assistant' in title:
            return 'ai'
        elif any(term in title for term in ['loot', 'treasure', 'item']):
            return 'loot'
        elif 'rule' in title or 'clarification' in title:
            return 'rules'
        
        # If still not identified, analyze content structure
        if 'type:' in content.lower() and 'environment:' in content.lower() and 'points of interest' in content.lower():
            return 'location'
        elif 'narrative_output' in content.lower():
            return 'location'  # Special string matching for location JSON-like content
        elif 'hp:' in content.lower() and 'ac:' in content.lower() and any(stat in content.lower() for stat in ['str', 'dex', 'con', 'int', 'wis', 'cha']):
            return 'monster'
        elif 'session recap' in content.lower() or 'session summary' in content.lower():
            return 'recap'
        elif 'model:' in content.lower() and 'conversation:' in content.lower():
            return 'ai'
        elif 'gp' in content.lower() and 'sp' in content.lower() and ('magic item' in content.lower() or 'potion' in content.lower() or 'scroll' in content.lower()):
            return 'loot'
        elif 'rule:' in content.lower() or 'page:' in content.lower() or 'phb' in content.lower():
            return 'rules'
        
        # Default to regular note
        return 'default'
    
    def _format_default_content(self, content):
        """Format regular note content with basic markdown-like parsing"""
        # Replace markdown headings with HTML
        content = content.replace('\n# ', '\n<h1>').replace('\n## ', '\n<h2>').replace('\n### ', '\n<h3>')
        for i in range(1, 4):
            heading_end = f"</h{i}>"
            content = re.sub(r'(<h{0}>.*?)(\n)'.format(i), r'\1{0}\2'.format(heading_end), content)
        
        # Replace markdown lists
        lines = content.split('\n')
        in_list = False
        processed_lines = []
        
        for line in lines:
            # Handle bullet points
            if line.strip().startswith('- '):
                if not in_list:
                    processed_lines.append('<ul>')
                    in_list = True
                processed_lines.append('<li>' + line.strip()[2:] + '</li>')
            elif line.strip().startswith('* '):
                if not in_list:
                    processed_lines.append('<ul>')
                    in_list = True
                processed_lines.append('<li>' + line.strip()[2:] + '</li>')
            else:
                if in_list:
                    processed_lines.append('</ul>')
                    in_list = False
                processed_lines.append(line)
        
        if in_list:
            processed_lines.append('</ul>')
        
        content = '\n'.join(processed_lines)
        
        # Replace double line breaks with paragraph tags
        content = content.replace('\n\n', '\n<p>')
        
        # Preserve line breaks
        content = content.replace('\n', '<br>')
        
        # Handle emphasis
        content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', content)  # Bold
        content = re.sub(r'\*(.+?)\*', r'<em>\1</em>', content)  # Italic
        
        return content
    
    def _format_monster_content(self, content):
        """Format monster content with stat block styling"""
        # Check if content contains JSON in code block or raw JSON
        try:
            # Look for code blocks with JSON
            json_match = re.search(r'```json\s*([\s\S]*?)\s*```', content)
            if json_match:
                # Found a JSON code block
                json_content = json_match.group(1).strip()
                monster_data = json.loads(json_content)
                return self._format_monster_json(monster_data)
            
            # If no code block, try to see if the entire content is JSON
            elif content.strip().startswith('{') and content.strip().endswith('}'):
                monster_data = json.loads(content)
                return self._format_monster_json(monster_data)
        except json.JSONDecodeError as e:
            print(f"Failed to parse monster JSON content: {e}")
        except Exception as e:
            print(f"Error processing monster JSON: {e}")
        
        # Use a modified version of the default formatter if not JSON
        formatted = self._format_default_content(content)
        
        # Further enhance monster-specific formatting
        # Look for stat blocks and add special styling
        stat_patterns = [
            (r'HP:?\s*(\d+)', r'<div class="stat-block"><span class="property">HP:</span> \1</div>'),
            (r'AC:?\s*(\d+)', r'<div class="stat-block"><span class="property">AC:</span> \1</div>'),
            (r'STR:?\s*(\d+)', r'<div class="stat-block"><span class="property">STR:</span> \1</div>'),
            (r'DEX:?\s*(\d+)', r'<div class="stat-block"><span class="property">DEX:</span> \1</div>'),
            (r'CON:?\s*(\d+)', r'<div class="stat-block"><span class="property">CON:</span> \1</div>'),
            (r'INT:?\s*(\d+)', r'<div class="stat-block"><span class="property">INT:</span> \1</div>'),
            (r'WIS:?\s*(\d+)', r'<div class="stat-block"><span class="property">WIS:</span> \1</div>'),
            (r'CHA:?\s*(\d+)', r'<div class="stat-block"><span class="property">CHA:</span> \1</div>')
        ]
        
        for pattern, replacement in stat_patterns:
            formatted = re.sub(pattern, replacement, formatted, flags=re.IGNORECASE)
        
        return formatted
        
    def _format_monster_json(self, monster_data):
        """Format a monster from JSON data"""
        html = []
        
        # Monster name as header
        name = monster_data.get("name", "Unnamed Monster")
        html.append(f'<div class="stat-block" style="background-color: #33272a; border-top: 3px solid #bf616a; border-bottom: 3px solid #bf616a; padding: 15px; margin-bottom: 15px;">')
        html.append(f'<h1 style="color: #d8a9a4; text-align: center; margin-bottom: 15px;">{name}</h1>')
        
        # Size, type, alignment
        size = monster_data.get("size", "")
        monster_type = monster_data.get("type", "")
        alignment = monster_data.get("alignment", "")
        
        type_line = []
        if size:
            type_line.append(size)
        if monster_type:
            type_line.append(monster_type)
        if alignment:
            type_line.append(alignment)
        
        if type_line:
            html.append(f'<p style="font-style: italic; text-align: center; margin-bottom: 15px;">{" ".join(type_line)}</p>')
        
        # AC, HP, Speed
        ac = monster_data.get("ac", monster_data.get("armor_class", ""))
        hp = monster_data.get("hp", monster_data.get("hit_points", ""))
        speed = monster_data.get("speed", "")
        
        if ac:
            html.append(f'<div><span class="property">Armor Class:</span> {ac}</div>')
        if hp:
            html.append(f'<div><span class="property">Hit Points:</span> {hp}</div>')
        if speed:
            html.append(f'<div><span class="property">Speed:</span> {speed}</div>')
        
        # Add a separator
        html.append('<hr style="border-color: #4c566a; margin: 10px 0;">')
        
        # Ability scores
        html.append('<div style="display: flex; justify-content: space-between; margin-bottom: 15px;">')
        
        for ability in ["str", "dex", "con", "int", "wis", "cha"]:
            score = monster_data.get(ability, monster_data.get(ability.upper(), ""))
            if score:
                # Calculate modifier
                if isinstance(score, int):
                    modifier = (score - 10) // 2
                    modifier_str = f"{modifier:+d}" if modifier != 0 else "0"
                    html.append(f'<div style="text-align: center;"><div style="font-weight: bold;">{ability.upper()}</div><div>{score} ({modifier_str})</div></div>')
                else:
                    html.append(f'<div style="text-align: center;"><div style="font-weight: bold;">{ability.upper()}</div><div>{score}</div></div>')
        
        html.append('</div>')
        
        # Add another separator
        html.append('<hr style="border-color: #4c566a; margin: 10px 0;">')
        
        # Skills, Saves, etc.
        for field in ["saving_throws", "skills", "damage_resistances", "damage_immunities", 
                      "condition_immunities", "senses", "languages", "challenge"]:
            value = monster_data.get(field, monster_data.get(field.replace("_", " "), ""))
            if value:
                field_name = field.replace("_", " ").title()
                html.append(f'<div><span class="property">{field_name}:</span> {value}</div>')
        
        # Add a separator
        html.append('<hr style="border-color: #4c566a; margin: 10px 0;">')
        
        # Abilities/Features
        abilities = monster_data.get("abilities", monster_data.get("special_abilities", monster_data.get("features", [])))
        if abilities:
            html.append('<div style="margin-top: 15px;">')
            
            if isinstance(abilities, list):
                for ability in abilities:
                    if isinstance(ability, dict):
                        ability_name = ability.get("name", "")
                        ability_desc = ability.get("description", ability.get("desc", ""))
                        
                        if ability_name and ability_desc:
                            html.append(f'<div style="margin-bottom: 10px;"><span style="font-weight: bold; font-style: italic;">{ability_name}.</span> {ability_desc}</div>')
                    elif isinstance(ability, str):
                        html.append(f'<div style="margin-bottom: 10px;">{ability}</div>')
            elif isinstance(abilities, str):
                html.append(f'<div>{abilities}</div>')
            
            html.append('</div>')
        
        # Actions
        actions = monster_data.get("actions", [])
        if actions:
            html.append('<h3 style="border-bottom: 1px solid #bf616a; padding-bottom: 5px; margin-top: 15px;">Actions</h3>')
            
            if isinstance(actions, list):
                for action in actions:
                    if isinstance(action, dict):
                        action_name = action.get("name", "")
                        action_desc = action.get("description", action.get("desc", ""))
                        
                        if action_name and action_desc:
                            html.append(f'<div style="margin-bottom: 10px;"><span style="font-weight: bold; font-style: italic;">{action_name}.</span> {action_desc}</div>')
                    elif isinstance(action, str):
                        html.append(f'<div style="margin-bottom: 10px;">{action}</div>')
            elif isinstance(actions, str):
                html.append(f'<div>{actions}</div>')
        
        # Reactions
        reactions = monster_data.get("reactions", [])
        if reactions:
            html.append('<h3 style="border-bottom: 1px solid #bf616a; padding-bottom: 5px; margin-top: 15px;">Reactions</h3>')
            
            if isinstance(reactions, list):
                for reaction in reactions:
                    if isinstance(reaction, dict):
                        reaction_name = reaction.get("name", "")
                        reaction_desc = reaction.get("description", reaction.get("desc", ""))
                        
                        if reaction_name and reaction_desc:
                            html.append(f'<div style="margin-bottom: 10px;"><span style="font-weight: bold; font-style: italic;">{reaction_name}.</span> {reaction_desc}</div>')
                    elif isinstance(reaction, str):
                        html.append(f'<div style="margin-bottom: 10px;">{reaction}</div>')
            elif isinstance(reactions, str):
                html.append(f'<div>{reactions}</div>')
        
        # Legendary Actions
        legendary = monster_data.get("legendary_actions", [])
        if legendary:
            html.append('<h3 style="border-bottom: 1px solid #bf616a; padding-bottom: 5px; margin-top: 15px;">Legendary Actions</h3>')
            
            if isinstance(legendary, list):
                for action in legendary:
                    if isinstance(action, dict):
                        action_name = action.get("name", "")
                        action_desc = action.get("description", action.get("desc", ""))
                        
                        if action_name and action_desc:
                            html.append(f'<div style="margin-bottom: 10px;"><span style="font-weight: bold; font-style: italic;">{action_name}.</span> {action_desc}</div>')
                    elif isinstance(action, str):
                        html.append(f'<div style="margin-bottom: 10px;">{action}</div>')
            elif isinstance(legendary, str):
                html.append(f'<div>{legendary}</div>')
        
        # Description or notes if available
        description = monster_data.get("description", monster_data.get("notes", ""))
        if description:
            html.append('<div style="margin-top: 15px; font-style: italic;">')
            html.append(f'<p>{description}</p>')
            html.append('</div>')
        
        html.append('</div>')  # Close stat block
        
        return ''.join(html)
    
    def _format_location_content(self, content):
        """Format location content with appropriate styling"""
        # Check if content contains JSON in code block or raw JSON
        try:
            # Look for code blocks with JSON
            json_match = re.search(r'```json\s*([\s\S]*?)\s*```', content)
            if json_match:
                # Found a JSON code block
                json_content = json_match.group(1).strip()
                location_data = json.loads(json_content)
                return self._format_location_json(location_data)
            
            # If no code block, try to see if the entire content is JSON
            elif content.strip().startswith('{') and content.strip().endswith('}'):
                location_data = json.loads(content)
                return self._format_location_json(location_data)
        except json.JSONDecodeError as e:
            print(f"Failed to parse JSON content: {e}")
        except Exception as e:
            print(f"Error processing location JSON: {e}")
        
        # If not JSON or JSON parsing failed, use the default formatter
        formatted = self._format_default_content(content)
        
        # Enhance location-specific elements
        location_patterns = [
            (r'\*Type:\*\s*(.*?)<br>', r'<div class="stat-block"><span class="property">Type:</span> \1</div>'),
            (r'\*Environment:\*\s*(.*?)<br>', r'<div class="stat-block"><span class="property">Environment:</span> \1</div>'),
            (r'\*Size:\*\s*(.*?)<br>', r'<div class="stat-block"><span class="property">Size:</span> \1</div>'),
            (r'\*Population:\*\s*(.*?)<br>', r'<div class="stat-block"><span class="property">Population:</span> \1</div>'),
            (r'\*Danger Level:\*\s*(.*?)<br>', r'<div class="stat-block"><span class="property">Danger Level:</span> \1</div>')
        ]
        
        for pattern, replacement in location_patterns:
            formatted = re.sub(pattern, replacement, formatted)
        
        return formatted
        
    def _format_location_json(self, location_data):
        """Format a location from JSON data"""
        html = []
        
        # Location name as header
        name = location_data.get("name", "Unnamed Location")
        html.append(f'<div class="location-header"><h1>{name}</h1></div>')
        
        # Basic information in a stat block
        html.append('<div class="stat-block">')
        
        # Type/Environment row
        html.append('<div style="display: flex; justify-content: space-between; flex-wrap: wrap;">')
        
        # Left column - Type, environment
        html.append('<div style="flex: 1; min-width: 150px; margin-right: 10px;">')
        
        location_type = location_data.get("type", "")
        if location_type:
            html.append(f'<div><span class="property">Type:</span> {location_type}</div>')
        
        environment = location_data.get("environment", "")
        if environment:
            html.append(f'<div><span class="property">Environment:</span> {environment}</div>')
        
        html.append('</div>')  # End left column
        
        # Right column - Size, population, danger
        html.append('<div style="flex: 1; min-width: 150px;">')
        
        # Try different possible field names for size
        size = location_data.get("size", location_data.get("size_scale", ""))
        if size:
            html.append(f'<div><span class="property">Size:</span> {size}</div>')
        
        # Try different possible field names for population
        population = location_data.get("population", location_data.get("population_activity_level", ""))
        if population:
            html.append(f'<div><span class="property">Population:</span> {population}</div>')
        
        # Try different possible field names for danger level
        danger = location_data.get("danger_level", location_data.get("threat_level", ""))
        if danger:
            html.append(f'<div><span class="property">Danger Level:</span> {danger}</div>')
        
        html.append('</div>')  # End right column
        html.append('</div>')  # End flex container
        html.append('</div>')  # End stat block
        
        # Narrative output (if present) - process this first
        narrative = location_data.get("narrative_output", "")
        if narrative and isinstance(narrative, dict):
            # Physical description
            phys_desc = narrative.get("physical_description", "")
            if phys_desc:
                html.append('<div class="location-section">')
                html.append('<h2 class="section-title">Physical Description</h2>')
                html.append(f'<p>{phys_desc}</p>')
                html.append('</div>')
            
            # Background/history
            hist_bg = narrative.get("history_background", "")
            if hist_bg:
                html.append('<div class="location-section">')
                html.append('<h2 class="section-title">History & Background</h2>')
                html.append(f'<p>{hist_bg}</p>')
                html.append('</div>')
            
            # Atmosphere/mood
            atmos = narrative.get("atmosphere_mood", "")
            if atmos:
                html.append('<div class="location-section">')
                html.append('<h2 class="section-title">Atmosphere & Mood</h2>')
                html.append(f'<p>{atmos}</p>')
                html.append('</div>')
                
            # Notable threats and challenges
            threats = narrative.get("notable_threats_challenges", "")
            if threats:
                html.append('<div class="location-section">')
                html.append('<h2 class="section-title">Threats & Challenges</h2>')
                html.append(f'<p>{threats}</p>')
                html.append('</div>')
                
            # Handle nested POIs from narrative
            self._append_narrative_points(html, narrative)
            
        # Only show description if not redundant with physical_description
        elif not phys_desc:
            # Description (only if not part of narrative)
            description = location_data.get("description", "")
            if description:
                html.append('<div class="location-section">')
                html.append('<h2 class="section-title">Description</h2>')
                html.append(f'<p>{description}</p>')
                html.append('</div>')
        
        # If narrative was a string or not present, handle other top-level fields
        if not narrative or not isinstance(narrative, dict):
            # Description
            description = location_data.get("description", "")
            if description:
                html.append('<div class="location-section">')
                html.append('<h2 class="section-title">Description</h2>')
                html.append(f'<p>{description}</p>')
                html.append('</div>')
        
            # History or background if not in narrative
            history = location_data.get("history", location_data.get("background", ""))
            if history:
                html.append('<div class="location-section">')
                html.append('<h2 class="section-title">History & Background</h2>')
                html.append(f'<p>{history}</p>')
                html.append('</div>')
            
            # Points of interest - if not already included in narrative
            points = location_data.get("points_of_interest", [])
            if points:
                html.append('<div class="location-section">')
                html.append('<h2 class="section-title">Points of Interest</h2>')
                
                if isinstance(points, list):
                    for point in points:
                        if isinstance(point, str):
                            html.append(f'<div class="poi-block"><p>• {point}</p></div>')
                        elif isinstance(point, dict):
                            point_name = point.get("name", "")
                            point_desc = point.get("description", "")
                            
                            if point_name and point_desc:
                                html.append(f'<div class="poi-block"><h3>{point_name}</h3><p>{point_desc}</p></div>')
                            elif point_name:
                                html.append(f'<div class="poi-block"><p>• <strong>{point_name}</strong></p></div>')
                            elif point_desc:
                                html.append(f'<div class="poi-block"><p>• {point_desc}</p></div>')
                elif isinstance(points, str):
                    html.append(f'<p>{points}</p>')
                
                html.append('</div>')
            
            # NPCs - if not already included in narrative
            npcs = location_data.get("npcs", location_data.get("key_npcs", []))
            if npcs:
                html.append('<div class="location-section">')
                html.append('<h2 class="section-title">Notable NPCs</h2>')
                
                if isinstance(npcs, list):
                    for npc in npcs:
                        if isinstance(npc, str):
                            html.append(f'<div class="npc-block"><p>• {npc}</p></div>')
                        elif isinstance(npc, dict):
                            npc_name = npc.get("name", "")
                            npc_desc = npc.get("description", "")
                            
                            if npc_name and npc_desc:
                                html.append(f'<div class="npc-block"><h3>{npc_name}</h3><p>{npc_desc}</p></div>')
                            elif npc_name:
                                html.append(f'<div class="npc-block"><p>• <strong>{npc_name}</strong></p></div>')
                            elif npc_desc:
                                html.append(f'<div class="npc-block"><p>• {npc_desc}</p></div>')
                elif isinstance(npcs, str):
                    html.append(f'<p>{npcs}</p>')
                
                html.append('</div>')
            
            # Secrets - if not already included in narrative
            secrets = location_data.get("secrets", location_data.get("secrets_hidden_elements", []))
            if secrets:
                html.append('<div class="location-section">')
                html.append('<h2 class="section-title">Secrets</h2>')
                
                if isinstance(secrets, list):
                    for secret in secrets:
                        if isinstance(secret, str):
                            html.append(f'<div class="secret-block"><p>• {secret}</p></div>')
                        elif isinstance(secret, dict):
                            secret_name = secret.get("name", "")
                            secret_desc = secret.get("description", secret.get("secret", ""))
                            
                            if secret_name and secret_desc:
                                html.append(f'<div class="secret-block"><h3>{secret_name}</h3><p>{secret_desc}</p></div>')
                            elif secret_name:
                                html.append(f'<div class="secret-block"><p>• <strong>{secret_name}</strong></p></div>')
                            elif secret_desc:
                                html.append(f'<div class="secret-block"><p>• {secret_desc}</p></div>')
                elif isinstance(secrets, str):
                    html.append(f'<p>{secrets}</p>')
                
                html.append('</div>')
                    
            # Add threats and challenges
            threats = location_data.get("threats", location_data.get("challenges", []))
            if threats:
                html.append('<div class="location-section">')
                html.append('<h2 class="section-title">Threats & Challenges</h2>')
                
                if isinstance(threats, list):
                    for threat in threats:
                        if isinstance(threat, str):
                            html.append(f'<p>• {threat}</p>')
                        elif isinstance(threat, dict):
                            threat_name = threat.get("name", "")
                            threat_desc = threat.get("description", "")
                            
                            if threat_name and threat_desc:
                                html.append(f'<h3>{threat_name}</h3><p>{threat_desc}</p>')
                            elif threat_name:
                                html.append(f'<p>• <strong>{threat_name}</strong></p>')
                            elif threat_desc:
                                html.append(f'<p>• {threat_desc}</p>')
                
                elif isinstance(threats, str):
                    html.append(f'<p>{threats}</p>')
                
                html.append('</div>')
        
        # Handle any additional fields
        for key, value in location_data.items():
            if key not in ["name", "type", "description", "narrative_output", 
                          "points_of_interest", "npcs", "key_npcs", "secrets", "secrets_hidden_elements", "history", 
                          "background", "environment", "size", "size_scale", "population", "population_activity_level",
                          "danger_level", "threat_level", "atmosphere", "mood", "atmosphere_mood",
                          "threats", "challenges", "notable_threats_challenges"]:
                if isinstance(value, str) and value:
                    title = key.replace('_', ' ').title()
                    html.append('<div class="location-section">')
                    html.append(f'<h2 class="section-title">{title}</h2>')
                    html.append(f'<p>{value}</p>')
                    html.append('</div>')
                elif isinstance(value, list) and value:
                    title = key.replace('_', ' ').title()
                    html.append('<div class="location-section">')
                    html.append(f'<h2 class="section-title">{title}</h2>')
                    
                    for item in value:
                        if isinstance(item, str):
                            html.append(f'<p>• {item}</p>')
                        elif isinstance(item, dict) and ("name" in item or "description" in item):
                            item_name = item.get("name", "")
                            item_desc = item.get("description", "")
                            
                            if item_name and item_desc:
                                html.append(f'<h3>{item_name}</h3><p>{item_desc}</p>')
                            elif item_name:
                                html.append(f'<p>• <strong>{item_name}</strong></p>')
                            elif item_desc:
                                html.append(f'<p>• {item_desc}</p>')
                    
                    html.append('</div>')
        
        return ''.join(html)
    
    def _append_narrative_points(self, html_list, narrative):
        """Helper method to append narrative points to the HTML list"""
        # Points of interest
        narrative_points = narrative.get("points_of_interest", [])
        if narrative_points and len(narrative_points) > 0:
            html_list.append('<div class="location-section">')
            html_list.append('<h2 class="section-title">Points of Interest</h2>')
            
            for point in narrative_points:
                if isinstance(point, dict):
                    name = point.get("name", "")
                    desc = point.get("description", "")
                    if name and desc:
                        html_list.append(f'<div class="poi-block"><h3>{name}</h3><p>{desc}</p></div>')
                    elif name:
                        html_list.append(f'<div class="poi-block"><p>• <strong>{name}</strong></p></div>')
                    elif desc:
                        html_list.append(f'<div class="poi-block"><p>• {desc}</p></div>')
                elif isinstance(point, str):
                    html_list.append(f'<div class="poi-block"><p>• {point}</p></div>')
            
            html_list.append('</div>')
        
        # NPCs
        narrative_npcs = narrative.get("key_npcs", [])
        if narrative_npcs and len(narrative_npcs) > 0:
            html_list.append('<div class="location-section">')
            html_list.append('<h2 class="section-title">Key NPCs</h2>')
            
            for npc in narrative_npcs:
                if isinstance(npc, dict):
                    name = npc.get("name", "")
                    desc = npc.get("description", "")
                    if name and desc:
                        html_list.append(f'<div class="npc-block"><h3>{name}</h3><p>{desc}</p></div>')
                    elif name:
                        html_list.append(f'<div class="npc-block"><p>• <strong>{name}</strong></p></div>')
                    elif desc:
                        html_list.append(f'<div class="npc-block"><p>• {desc}</p></div>')
                elif isinstance(npc, str):
                    html_list.append(f'<div class="npc-block"><p>• {npc}</p></div>')
            
            html_list.append('</div>')
        
        # Secrets
        narrative_secrets = narrative.get("secrets_hidden_elements", [])
        if narrative_secrets and len(narrative_secrets) > 0:
            html_list.append('<div class="location-section">')
            html_list.append('<h2 class="section-title">Secrets & Hidden Elements</h2>')
            
            for secret in narrative_secrets:
                if isinstance(secret, dict):
                    # Some LLM responses use "secret" key, others use "name"/"description"
                    secret_text = secret.get("secret", secret.get("description", ""))
                    secret_name = secret.get("name", "")
                    
                    if secret_name and secret_text:
                        html_list.append(f'<div class="secret-block"><h3>{secret_name}</h3><p>{secret_text}</p></div>')
                    elif secret_name:
                        html_list.append(f'<div class="secret-block"><p>• <strong>{secret_name}</strong></p></div>')
                    elif secret_text:
                        html_list.append(f'<div class="secret-block"><p>• {secret_text}</p></div>')
                elif isinstance(secret, str):
                    html_list.append(f'<div class="secret-block"><p>• {secret}</p></div>')
            
            html_list.append('</div>')
    
    def _format_recap_content(self, content):
        """Format session recap content with appropriate styling"""
        # Use default formatter as base
        formatted = self._format_default_content(content)
        
        # Add any recap-specific formatting here
        # For example, you might want to highlight key NPCs, locations, etc.
        npc_pattern = r'([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)'  # Capitalized words as potential NPC names
        
        # This is a simplistic approach - might lead to false positives
        # Only use if you can refine it for your specific content patterns
        # formatted = re.sub(npc_pattern, r'<strong>\1</strong>', formatted)
        
        return formatted
    
    def _format_ai_content(self, content):
        """Format AI conversation content with appropriate styling"""
        # Handle AI conversation format which often has human/assistant turns
        lines = content.split('\n')
        formatted_lines = []
        
        in_conversation = False
        
        for line in lines:
            # Detect conversation section
            if 'conversation' in line.lower() or 'you:' in line.lower():
                in_conversation = True
                formatted_lines.append(line)
            elif in_conversation:
                # Style user messages
                if line.strip().startswith('You:') or line.strip().startswith('User:'):
                    formatted_lines.append(f'<strong style="color: #2980b9;">{line}</strong>')
                # Style assistant messages
                elif line.strip().startswith('Assistant:') or line.strip().startswith('AI:'):
                    formatted_lines.append(f'<strong style="color: #16a085;">{line}</strong>')
                else:
                    formatted_lines.append(line)
            else:
                formatted_lines.append(line)
        
        # Join back and use default formatter
        return self._format_default_content('\n'.join(formatted_lines))
    
    def _format_loot_content(self, content):
        """Format loot/treasure content with appropriate styling"""
        # Use default formatter as base
        formatted = self._format_default_content(content)
        
        # Enhance gold, silver, copper values
        currency_patterns = [
            (r'(\d+)\s*gp', r'<span style="color: #f39c12; font-weight: bold;">\1 gp</span>'),
            (r'(\d+)\s*sp', r'<span style="color: #7f8c8d; font-weight: bold;">\1 sp</span>'),
            (r'(\d+)\s*cp', r'<span style="color: #d35400; font-weight: bold;">\1 cp</span>'),
            (r'(\d+)\s*pp', r'<span style="color: #2ecc71; font-weight: bold;">\1 pp</span>')
        ]
        
        for pattern, replacement in currency_patterns:
            formatted = re.sub(pattern, replacement, formatted, flags=re.IGNORECASE)
        
        # Highlight magic items
        magic_patterns = [
            (r'([+]\d+)', r'<span style="color: #8e44ad; font-weight: bold;">\1</span>'),
            (r'(potion of .*?)([\s\.,<])', r'<span style="color: #3498db;">\1</span>\2'),
            (r'(scroll of .*?)([\s\.,<])', r'<span style="color: #e74c3c;">\1</span>\2'),
            (r'(wand of .*?)([\s\.,<])', r'<span style="color: #9b59b6;">\1</span>\2'),
            (r'(staff of .*?)([\s\.,<])', r'<span style="color: #8e44ad;">\1</span>\2'),
            (r'(ring of .*?)([\s\.,<])', r'<span style="color: #f1c40f;">\1</span>\2')
        ]
        
        for pattern, replacement in magic_patterns:
            formatted = re.sub(pattern, replacement, formatted, flags=re.IGNORECASE)
        
        return formatted
    
    def _format_rules_content(self, content):
        """Format rules clarification content with appropriate styling"""
        # Use default formatter as base
        formatted = self._format_default_content(content)
        
        # Enhance page references, book citations
        rules_patterns = [
            (r'(PHB|DMG|MM|XGE|TCE|VGM)(?:\s+p\.?\s*(\d+))?', r'<span style="color: #7d3c98; font-weight: bold;">\1\2</span>'),
            (r'(page|p)\.?\s*(\d+)', r'<span style="color: #7d3c98; font-weight: bold;">\1 \2</span>'),
            (r'(Chapter|Ch)\.?\s*(\d+)', r'<span style="color: #7d3c98; font-weight: bold;">\1 \2</span>')
        ]
        
        for pattern, replacement in rules_patterns:
            formatted = re.sub(pattern, replacement, formatted, flags=re.IGNORECASE)
        
        return formatted
    
    def _create_note(self):
        """Create a new note"""
        dialog = NoteEditDialog(self, self.app_state, tags=self.all_tags)
        
        if dialog.exec():
            note_data = dialog.get_note_data()
            if note_data:
                current_time = QDateTime.currentDateTime().toString(Qt.ISODate)
                
                # Add timestamps
                note_data['created_at'] = current_time
                note_data['updated_at'] = current_time
                
                try:
                    # Insert into database
                    note_id = self.app_state.db_manager.insert('session_notes', note_data)
                    note_data['id'] = note_id
                    
                    # Add to our local data
                    self.notes.insert(0, note_data)
                    
                    # Reload notes
                    self.filtered_notes = self.notes.copy()
                    self._update_notes_list()
                    self._update_tag_list()
                    
                    # Select the new note
                    for i in range(self.notes_list.count()):
                        item = self.notes_list.item(i)
                        if item.data(Qt.UserRole) == note_id:
                            self.notes_list.setCurrentItem(item)
                            self._note_selected(item)
                            break
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to save note: {e}")
    
    def _edit_note(self):
        """Edit the selected note"""
        if not self.current_note:
            return
        
        dialog = NoteEditDialog(self, self.app_state, self.current_note, self.all_tags)
        
        if dialog.exec():
            note_data = dialog.get_note_data()
            if note_data:
                # Update timestamp
                note_data['updated_at'] = QDateTime.currentDateTime().toString(Qt.ISODate)
                
                try:
                    # Update in database
                    note_id = note_data['id']
                    self.app_state.db_manager.update(
                        'session_notes',
                        {k: v for k, v in note_data.items() if k != 'id'},
                        'id = ?',
                        [note_id]
                    )
                    
                    # Update in our local data
                    for i, note in enumerate(self.notes):
                        if note['id'] == note_id:
                            self.notes[i] = note_data
                            break
                    
                    # Reload notes
                    self.filtered_notes = self.notes.copy()
                    self._update_notes_list()
                    self._update_tag_list()
                    
                    # Re-select the note
                    for i in range(self.notes_list.count()):
                        item = self.notes_list.item(i)
                        if item.data(Qt.UserRole) == note_id:
                            self.notes_list.setCurrentItem(item)
                            self._note_selected(item)
                            break
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Failed to update note: {e}")
    
    def _delete_note(self):
        """Delete the selected note"""
        if not self.current_note:
            return
        
        # Confirm deletion
        confirm = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Are you sure you want to delete note '{self.current_note['title']}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if confirm == QMessageBox.Yes:
            try:
                # Delete from database
                note_id = self.current_note['id']
                self.app_state.db_manager.delete('session_notes', 'id = ?', [note_id])
                
                # Delete from our local data
                self.notes = [note for note in self.notes if note['id'] != note_id]
                
                # Clear current note
                self.current_note = None
                self.note_title.setText("")
                self.note_metadata.setText("")
                self.note_tags.setText("")
                self.note_content.setText("")
                
                # Disable edit/delete buttons
                self.edit_btn.setEnabled(False)
                self.delete_btn.setEnabled(False)
                
                # Reload notes
                self.filtered_notes = self.notes.copy()
                self._update_notes_list()
                self._update_tag_list()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete note: {e}")
    
    def _show_context_menu(self, position):
        """Show context menu for notes list"""
        # Only show if an item is selected
        item = self.notes_list.itemAt(position)
        if not item:
            return
        
        # Create menu
        menu = QMenu(self)
        
        edit_action = QAction("Edit", self)
        edit_action.triggered.connect(self._edit_note)
        menu.addAction(edit_action)
        
        delete_action = QAction("Delete", self)
        delete_action.triggered.connect(self._delete_note)
        menu.addAction(delete_action)
        
        menu.exec(self.notes_list.mapToGlobal(position))

    def _create_note_with_content(self, title, content, tags=None):
        """Creates a new note programmatically and saves it."""
        print(f"Creating note programmatically: Title='{title}'") # Debug
        tags_str = ",".join(tags) if tags else ""
        now = QDateTime.currentDateTime().toString(Qt.ISODate)

        new_note_data = {
            'title': title,
            'content': content,
            'tags': tags_str,
            'created_at': now,
            'updated_at': now
        }

        # Save to database (using app_state.db_manager)
        try:
            inserted_id = self.app_state.db_manager.insert('session_notes', new_note_data)
            if inserted_id is not None:
                new_note_data['id'] = inserted_id
                print(f"Note '{title}' saved with ID: {inserted_id}") # Debug

                # Add to beginning of internal list to maintain chronological order (newest first)
                self.notes.insert(0, new_note_data)
                self._update_tag_list()
                self._filter_notes() # This will update the list widget

                # Optionally, select the new note
                # Find the item in the list widget based on ID and select it
                for i in range(self.notes_list.count()):
                    item = self.notes_list.item(i)
                    if item.data(Qt.UserRole) == inserted_id:
                        self.notes_list.setCurrentItem(item)
                        self._note_selected(item) # Update display
                        break
                return True
            else:
                print(f"Error: Failed to insert note '{title}' into database.") # Debug
                QMessageBox.critical(self, "Error", f"Could not save the note '{title}' to the database.")
                return False
        except Exception as e:
            print(f"Exception saving note '{title}': {e}") # Debug
            QMessageBox.critical(self, "Error", f"An error occurred while saving the note '{title}': {e}")
            return False

    # --- Public Slots --- 

    @Slot(str)
    def add_monster_creation_note(self, monster_name: str):
        """Slot to add a note when a new custom monster is created."""
        print(f"Slot add_monster_creation_note called with: {monster_name}") # Debug
        title = f"New Monster Created: {monster_name}"
        content = (f"A new custom monster named '{monster_name}' was added to the database on {QDateTime.currentDateTime().toString()}. "
                   f"You can view or edit it in the Monster Reference panel.")
        tags = ["Monster", "Custom Content", "Creation Log"] # Example tags

        # Use the internal method to create and save the note
        self._create_note_with_content(title, content, tags)

    def __repr__(self):
        """String representation of the panel for debugging"""
        return f"SessionNotesPanel(id={id(self)})"
    
    def debug_info(self):
        """Print debug information about this panel"""
        print(f"SessionNotesPanel: id={id(self)}")
        print(f"  _create_note_with_content method exists: {hasattr(self, '_create_note_with_content')}")
        print(f"  Current note count: {len(self.notes)}")
        print(f"  Is visible: {self.isVisible()}")
        print(f"  Parent: {self.parent()}")
        if self.parent():
            print(f"  Parent is visible: {self.parent().isVisible()}")
        return True

    def _generate_recap(self):
        """Open the dialog to generate a session recap"""
        # Check if any notes are selected in list, otherwise include all notes since last recap
        selected_items = self.notes_list.selectedItems()
        
        if not selected_items:
            # No notes selected, use all notes since last recap
            if not self.filtered_notes:
                QMessageBox.warning(
                    self, "No Notes Available", 
                    "There are no notes available to generate a recap. "
                    "Please create some session notes first."
                )
                return
            
            if self.last_recap_date:
                # Filter notes since last recap
                notes_since_last_recap = []
                for note in self.filtered_notes:
                    # Check if note was created or updated after last recap
                    note_date = max(
                        QDateTime.fromString(note['created_at'], Qt.ISODate),
                        QDateTime.fromString(note['updated_at'], Qt.ISODate)
                    )
                    last_recap_dt = QDateTime.fromString(self.last_recap_date, Qt.ISODate)
                    if note_date >= last_recap_dt:
                        notes_since_last_recap.append(note)
                
                if notes_since_last_recap:
                    notes_to_include = notes_since_last_recap
                else:
                    # If no notes since last recap, use all filtered notes
                    notes_to_include = self.filtered_notes
                    QMessageBox.information(
                        self, "No New Notes", 
                        "No new notes found since the last recap. "
                        "All current notes will be included in the recap."
                    )
            else:
                # No last recap date, use all filtered notes
                notes_to_include = self.filtered_notes
        else:
            # Use selected notes
            selected_notes = []
            for item in selected_items:
                note_id = item.data(Qt.UserRole)
                for note in self.filtered_notes:
                    if note['id'] == note_id:
                        selected_notes.append(note)
                        break
            notes_to_include = selected_notes
            
        # Open the recap dialog
        recap_dialog = RecapDialog(self, self.app_state, notes_to_include)
        recap_dialog.exec()

    def _handle_note_link_clicked(self, url):
        """Handle anchor clicks in the note content (for dnd:// links)"""
        scheme = url.scheme()
        path = url.path()
        if scheme == "dnd":
            element_data = path.lstrip("/")
            # Call the same logic as the location generator (stub for now)
            self._handle_interactive_element(element_data)

    def _handle_interactive_element(self, element_data):
        """Stub: Show or generate details for the clicked element. Replace with shared logic."""
        QMessageBox.information(self, "Element Clicked", f"Clicked: {element_data}\n(Implement shared detail dialog here)")