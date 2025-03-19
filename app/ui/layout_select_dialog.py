# app/ui/layout_select_dialog.py - Layout selection dialog
"""
Dialog for selecting and loading panel layouts

This dialog displays available layout configurations for loading.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QSplitter, QFrame, QTextEdit,
    QGroupBox
)
from PySide6.QtCore import Qt


class LayoutSelectDialog(QDialog):
    """Dialog for selecting a layout to load"""
    
    def __init__(self, parent=None, layouts=None, current_layout=None):
        """Initialize the layout selection dialog
        
        Args:
            parent: Parent widget
            layouts: Dictionary of available layouts with metadata
            current_layout: Name of the currently loaded layout (if any)
        """
        super().__init__(parent)
        
        self.layouts = layouts or {}  # Format: {name: {metadata}}
        self.current_layout = current_layout
        
        self.setWindowTitle("Select Layout")
        self.setMinimumSize(500, 400)
        self.selected_layout = None
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the dialog UI"""
        main_layout = QVBoxLayout(self)
        
        # Create splitter for layout list and preview
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)
        
        # Create layout categories
        layout_frame = QFrame()
        layout_frame.setFrameShape(QFrame.StyledPanel)
        layout_frame_layout = QVBoxLayout(layout_frame)
        
        # Preset layouts
        preset_group = QGroupBox("Preset Layouts")
        preset_layout = QVBoxLayout(preset_group)
        self.preset_list = QListWidget()
        preset_layout.addWidget(self.preset_list)
        
        # User layouts
        user_group = QGroupBox("User Layouts")
        user_layout = QVBoxLayout(user_group)
        self.user_list = QListWidget()
        user_layout.addWidget(self.user_list)
        
        # Add both layout types to the frame
        layout_frame_layout.addWidget(preset_group)
        layout_frame_layout.addWidget(user_group)
        
        # Preview area
        preview_frame = QFrame()
        preview_frame.setFrameShape(QFrame.StyledPanel)
        preview_layout = QVBoxLayout(preview_frame)
        
        preview_label = QLabel("Layout Preview:")
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        
        preview_layout.addWidget(preview_label)
        preview_layout.addWidget(self.preview_text)
        
        # Add frames to splitter
        splitter.addWidget(layout_frame)
        splitter.addWidget(preview_frame)
        splitter.setSizes([200, 300])
        
        # Populate layout lists
        self._populate_layout_lists()
        
        # Connect signals
        self.preset_list.itemClicked.connect(self._on_preset_selected)
        self.user_list.itemClicked.connect(self._on_user_selected)
        
        # Buttons
        button_layout = QHBoxLayout()
        load_button = QPushButton("Load")
        load_button.clicked.connect(self.accept)
        
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        
        button_layout.addWidget(load_button)
        button_layout.addWidget(cancel_button)
        main_layout.addLayout(button_layout)
    
    def _populate_layout_lists(self):
        """Populate the layout lists with available layouts"""
        for name, data in self.layouts.items():
            is_preset = data.get("is_preset", False)
            
            item = QListWidgetItem(name)
            item.setData(Qt.UserRole, name)
            
            # Set selected if this is the current layout
            if name == self.current_layout:
                item.setSelected(True)
                if is_preset:
                    self.preset_list.setCurrentItem(item)
                else:
                    self.user_list.setCurrentItem(item)
            
            # Add to appropriate list
            if is_preset:
                category = data.get("category", "Custom")
                item.setText(f"{name} ({category})")
                self.preset_list.addItem(item)
            else:
                self.user_list.addItem(item)
    
    def _on_preset_selected(self, item):
        """Handle preset layout selection"""
        # Deselect any item in the user list
        self.user_list.clearSelection()
        
        name = item.data(Qt.UserRole)
        self._show_layout_preview(name)
        self.selected_layout = name
    
    def _on_user_selected(self, item):
        """Handle user layout selection"""
        # Deselect any item in the preset list
        self.preset_list.clearSelection()
        
        name = item.data(Qt.UserRole)
        self._show_layout_preview(name)
        self.selected_layout = name
    
    def _show_layout_preview(self, name):
        """Show a preview of the selected layout"""
        if name not in self.layouts:
            self.preview_text.setText("Layout information not available.")
            return
        
        layout_data = self.layouts[name]
        is_preset = layout_data.get("is_preset", False)
        
        preview = f"Layout: {name}\n\n"
        
        if is_preset:
            category = layout_data.get("category", "Custom")
            preview += f"Type: Preset ({category})\n\n"
        else:
            preview += "Type: User Layout\n\n"
        
        # Add visible panels
        visible_panels = layout_data.get("visible_panels", [])
        if visible_panels:
            preview += "Visible Panels:\n"
            for panel in visible_panels:
                preview += f"- {panel}\n"
        else:
            preview += "No panels are visible in this layout.\n"
        
        # Add created/modified date if available
        if "created" in layout_data:
            preview += f"\nCreated: {layout_data['created']}\n"
        
        if "modified" in layout_data:
            preview += f"Last Modified: {layout_data['modified']}\n"
        
        self.preview_text.setText(preview)
    
    def accept(self):
        """Handle the accept action"""
        # Get selected layout from either list
        selected_preset = self.preset_list.currentItem()
        selected_user = self.user_list.currentItem()
        
        if selected_preset:
            self.selected_layout = selected_preset.data(Qt.UserRole)
        elif selected_user:
            self.selected_layout = selected_user.data(Qt.UserRole)
        
        if not self.selected_layout:
            # If nothing is selected, default to first preset or user layout
            if self.preset_list.count() > 0:
                self.selected_layout = self.preset_list.item(0).data(Qt.UserRole)
            elif self.user_list.count() > 0:
                self.selected_layout = self.user_list.item(0).data(Qt.UserRole)
        
        super().accept() 