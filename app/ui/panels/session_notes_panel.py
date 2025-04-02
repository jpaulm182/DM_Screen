"""
Session Notes Panel

Provides a system for creating, editing, and managing session notes with tagging functionality.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QTextEdit, QListWidget, QListWidgetItem, 
    QSplitter, QMenu, QDialog, QFormLayout, QDialogButtonBox,
    QMessageBox, QComboBox
)
from PySide6.QtCore import Qt, Signal, QDateTime, Slot
from PySide6.QtGui import QFont, QAction, QIcon

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
        
        # Call parent constructor which will call _setup_ui
        super().__init__(app_state, "Session Notes")
        
        # Load notes
        self._load_notes()
    
    def _setup_ui(self):
        """Set up the panel UI components"""
        # Create a new layout directly on this widget
        main_layout = QVBoxLayout(self)
        
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
        self.note_content = QTextEdit()
        self.note_content.setReadOnly(True)
        right_layout.addWidget(self.note_content)
        
        # Add panes to splitter
        splitter.addWidget(left_pane)
        splitter.addWidget(right_pane)
        
        # Set initial sizes
        splitter.setSizes([200, 400])
        
        # Add the splitter to the main layout
        main_layout.addWidget(splitter)
    
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
            
            # Display content
            self.note_content.setText(self.current_note['content'])
            
            # Enable edit/delete buttons
            self.edit_btn.setEnabled(True)
            self.delete_btn.setEnabled(True)
    
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