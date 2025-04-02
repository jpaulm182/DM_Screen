# app/ui/main_window.py - Main application window
"""
Main window for the DM Screen application

Implements the main UI window with dynamic layout system and panel management.
"""

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QDockWidget, QToolBar, QMenu, QMenuBar,
    QStatusBar, QFileDialog, QMessageBox, QLabel, QInputDialog, QComboBox, QSizePolicy
)
from PySide6.QtCore import Qt, QSize, QTimer, QByteArray
from PySide6.QtGui import QIcon, QAction, QKeySequence
from datetime import datetime

from app.ui.panel_manager import PanelManager
from app.ui.panels.welcome_panel import WelcomePanel
from app.ui.theme_manager import apply_theme, set_font_size
from app.ui.panels.panel_category import PanelCategory
from app.ui.layout_name_dialog import LayoutNameDialog
from app.ui.layout_select_dialog import LayoutSelectDialog

# Import the panels we need to connect
from app.ui.panels.monster_panel import MonsterPanel
from app.ui.panels.session_notes_panel import SessionNotesPanel


class MainWindow(QMainWindow):
    """
    Main application window with dockable panels and menu system
    """
    
    def __init__(self, app_state):
        """Initialize the main window and UI components"""
        super().__init__()
        self.app_state = app_state
        
        # Initialize panel-related UI elements mapping before creating panels
        self.panel_actions = {}  # Actions for each panel
        self.welcome_panel = None  # Keep track of welcome panel
        self.stored_visible_panels = []  # Store visible panels when welcome panel is shown
        
        # Create the panel manager
        self.panel_manager = PanelManager(self, app_state)
        
        # Make panel manager available to app_state for easier access
        app_state.panel_manager = self.panel_manager
        
        # Apply the current theme
        self.current_theme = app_state.get_setting("theme", "dark")
        apply_theme(self, self.current_theme)
        
        # Setup UI components
        self._setup_ui()
        self._create_menus()
        self._create_toolbar()
        self._create_status_bar()
        
        # Connect signals AFTER panels are likely instantiated by PanelManager
        self._connect_panel_signals()
        
        # Load the default layout or show welcome screen
        self._load_initial_layout()
        
        # Start UI update timer for panel states
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self._update_panel_action_states)
        self.update_timer.start(500)  # Update every 500ms
    
    def _setup_ui(self):
        """Configure the main window UI properties"""
        self.setWindowTitle("DM Screen V0")
        self.setMinimumSize(1024, 768)
        
        # Allow nested docks
        self.setDockNestingEnabled(True)
        
        # Set central widget to None to allow docks to take full space
        self.setCentralWidget(None)
    
    def _create_menus(self):
        """Create application menu structure"""
        # File menu
        file_menu = self.menuBar().addMenu("&File")
        
        new_action = file_menu.addAction("&New Session")
        new_action.setShortcut("Ctrl+Shift+N")
        new_action.triggered.connect(self._new_session)
        
        open_action = file_menu.addAction("&Open Session")
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self._open_session)
        
        save_action = file_menu.addAction("&Save Session")
        save_action.setShortcut("Ctrl+Shift+S")
        save_action.triggered.connect(self._save_session)
        
        file_menu.addSeparator()
        
        exit_action = file_menu.addAction("E&xit")
        exit_action.setShortcut("Alt+F4")
        exit_action.triggered.connect(self.close)
        
        # View menu
        view_menu = self.menuBar().addMenu("&View")
        
        layout_menu = view_menu.addMenu("&Layouts")
        save_layout_action = layout_menu.addAction("&Save Current Layout")
        save_layout_action.setShortcut("Ctrl+Alt+S")
        save_layout_action.triggered.connect(self._save_layout)
        
        save_layout_as_action = layout_menu.addAction("Save Layout &As...")
        save_layout_as_action.triggered.connect(self._save_layout_as)
        
        layout_menu.addSeparator()
        
        load_layout_action = layout_menu.addAction("&Load Layout")
        load_layout_action.setShortcut("Ctrl+Alt+L")
        load_layout_action.triggered.connect(self._load_layout)
        
        manage_layouts_action = layout_menu.addAction("&Manage Layouts")
        manage_layouts_action.triggered.connect(self._manage_layouts)
        
        layout_menu.addSeparator()
        
        # Add layout presets submenu
        self.preset_layouts_menu = layout_menu.addMenu("Preset Layouts")
        self._populate_preset_layouts_menu()
        
        # Add Smart Organize action
        smart_organize_action = view_menu.addAction("Smart &Organize Panels")
        smart_organize_action.setShortcut("Ctrl+Alt+O")
        smart_organize_action.triggered.connect(self._smart_organize_panels)
        
        view_menu.addSeparator()
        
        theme_menu = view_menu.addMenu("&Theme")
        dark_theme_action = theme_menu.addAction("&Dark")
        dark_theme_action.setShortcut("Ctrl+Alt+D")
        dark_theme_action.triggered.connect(lambda: self._change_theme("dark"))
        
        light_theme_action = theme_menu.addAction("&Light")
        light_theme_action.setShortcut("Ctrl+Alt+T")
        light_theme_action.triggered.connect(lambda: self._change_theme("light"))
        
        # Add Font Size menu
        font_size_menu = view_menu.addMenu("Font &Size")
        
        small_font_action = font_size_menu.addAction("&Small")
        small_font_action.triggered.connect(lambda: self._change_font_size("small"))
        
        medium_font_action = font_size_menu.addAction("&Medium")
        medium_font_action.triggered.connect(lambda: self._change_font_size("medium"))
        
        large_font_action = font_size_menu.addAction("&Large")
        large_font_action.triggered.connect(lambda: self._change_font_size("large"))
        
        xlarge_font_action = font_size_menu.addAction("&X-Large")
        xlarge_font_action.triggered.connect(lambda: self._change_font_size("x-large"))
        
        # Panels menu
        panels_menu = self.menuBar().addMenu("&Panels")
        
        # Combat panels
        combat_menu = panels_menu.addMenu("&Combat Tools")
        combat_tracker_action = combat_menu.addAction("Combat Tracker")
        combat_tracker_action.triggered.connect(
            lambda: self.panel_manager.toggle_panel("combat_tracker"))
        self.panel_actions["combat_tracker"] = combat_tracker_action
        
        dice_roller_action = combat_menu.addAction("Dice Roller")
        dice_roller_action.triggered.connect(
            lambda: self.panel_manager.toggle_panel("dice_roller"))
        self.panel_actions["dice_roller"] = dice_roller_action
        
        combat_log_action = combat_menu.addAction("Combat Log")
        combat_log_action.triggered.connect(
            lambda: self.panel_manager.toggle_panel("combat_log"))
        self.panel_actions["combat_log"] = combat_log_action
        
        # Reference panels
        reference_menu = panels_menu.addMenu("&Reference")
        rules_action = reference_menu.addAction("Rules Reference")
        rules_action.triggered.connect(
            lambda: self.panel_manager.toggle_panel("rules_reference"))
        self.panel_actions["rules_reference"] = rules_action
        
        conditions_action = reference_menu.addAction("Conditions")
        conditions_action.triggered.connect(
            lambda: self.panel_manager.toggle_panel("conditions"))
        self.panel_actions["conditions"] = conditions_action
        
        monster_action = reference_menu.addAction("Monsters")
        monster_action.triggered.connect(
            lambda: self.panel_manager.toggle_panel("monster"))
        self.panel_actions["monster"] = monster_action
        
        spell_action = reference_menu.addAction("Spells")
        spell_action.triggered.connect(
            lambda: self.panel_manager.toggle_panel("spell_reference"))
        self.panel_actions["spell_reference"] = spell_action
        
        rules_clarification_action = reference_menu.addAction("Rules Clarification")
        rules_clarification_action.triggered.connect(
            lambda: self.panel_manager.toggle_panel("rules_clarification"))
        self.panel_actions["rules_clarification"] = rules_clarification_action
        
        llm_action = reference_menu.addAction("AI Assistant")
        llm_action.triggered.connect(
            lambda: self.panel_manager.toggle_panel("llm"))
        self.panel_actions["llm"] = llm_action
            
        # Campaign Management panels
        campaign_menu = panels_menu.addMenu("&Campaign")
        notes_action = campaign_menu.addAction("Session Notes")
        notes_action.triggered.connect(
            lambda: self.panel_manager.toggle_panel("session_notes"))
        self.panel_actions["session_notes"] = notes_action
        
        player_chars_action = campaign_menu.addAction("Player Characters")
        player_chars_action.triggered.connect(
            lambda: self.panel_manager.toggle_panel("player_character"))
        self.panel_actions["player_character"] = player_chars_action
        
        npc_generator_action = campaign_menu.addAction("NPC Generator")
        npc_generator_action.triggered.connect(
            lambda: self.panel_manager.toggle_panel("npc_generator"))
        self.panel_actions["npc_generator"] = npc_generator_action
        
        location_generator_action = campaign_menu.addAction("Location Generator")
        location_generator_action.triggered.connect(
            lambda: self.panel_manager.toggle_panel("location_generator"))
        self.panel_actions["location_generator"] = location_generator_action
        
        treasure_generator_action = campaign_menu.addAction("Treasure Generator")
        treasure_generator_action.triggered.connect(
            lambda: self.panel_manager.toggle_panel("treasure_generator"))
        self.panel_actions["treasure_generator"] = treasure_generator_action
        
        encounter_generator_action = campaign_menu.addAction("Encounter Generator")
        encounter_generator_action.triggered.connect(
            lambda: self.panel_manager.toggle_panel("encounter_generator"))
        self.panel_actions["encounter_generator"] = encounter_generator_action
        
        # Utility panels
        utility_menu = panels_menu.addMenu("&Utilities")
        weather_action = utility_menu.addAction("Weather Generator")
        weather_action.triggered.connect(
            lambda: self.panel_manager.toggle_panel("weather"))
        self.panel_actions["weather"] = weather_action
        
        time_action = utility_menu.addAction("Time Tracker")
        time_action.triggered.connect(
            lambda: self.panel_manager.toggle_panel("time_tracker"))
        self.panel_actions["time_tracker"] = time_action
        
        # Help menu
        help_menu = self.menuBar().addMenu("&Help")
        
        # Add welcome panel action
        welcome_action = help_menu.addAction("Show &Welcome Panel")
        welcome_action.setShortcut("F1")
        welcome_action.triggered.connect(self._toggle_welcome_panel)
        
        help_menu.addSeparator()
        help_menu.addAction("&About").triggered.connect(self._show_about)
    
    def _populate_preset_layouts_menu(self):
        """Populate the preset layouts menu with available layouts"""
        self.preset_layouts_menu.clear()
        
        # Get all available layouts
        layouts = self.app_state.get_available_layouts()
        
        # Add preset layouts to menu
        preset_layouts = {name: data for name, data in layouts.items() 
                         if data.get("is_preset", False)}
        
        # Sort by category
        by_category = {}
        for name, data in preset_layouts.items():
            category = data.get("category", "Custom")
            if category not in by_category:
                by_category[category] = []
            by_category[category].append((name, data))
        
        if not preset_layouts:
            empty_action = self.preset_layouts_menu.addAction("No presets available")
            empty_action.setEnabled(False)
            return
        
        # Add actions by category
        for category in sorted(by_category.keys()):
            # Add category as submenu if there are multiple items
            if len(by_category[category]) > 1:
                category_menu = self.preset_layouts_menu.addMenu(category)
                for name, _ in sorted(by_category[category]):
                    action = category_menu.addAction(name)
                    action.triggered.connect(lambda checked=False, n=name: self._load_preset_layout(n))
            # Otherwise add directly
            elif by_category[category]:
                name, _ = by_category[category][0]
                action = self.preset_layouts_menu.addAction(f"{name} ({category})")
                action.triggered.connect(lambda checked=False, n=name: self._load_preset_layout(n))
    
    def _create_toolbar(self):
        """Create the main toolbar with categorized quick select buttons"""
        toolbar = QToolBar("Main Toolbar")
        toolbar.setObjectName("MainToolbar")  # Set object name to fix state saving
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(toolbar)
        
        # Define panel descriptions and keyboard shortcuts for tooltips
        panel_info = {
            # Combat Category
            "combat_tracker": {
                "description": "Track initiative, hit points, and conditions for combat encounters",
                "shortcut": "Ctrl+1"
            },
            "dice_roller": {
                "description": "Roll various dice combinations with modifiers",
                "shortcut": "Ctrl+2"
            },
            # Reference Category
            "monster": {
                "description": "Browse, search, and manage monster stat blocks",
                "shortcut": "Ctrl+3"
            },
            "spell_reference": {
                "description": "Look up spell details, levels, and components",
                "shortcut": "Ctrl+4"
            },
            "conditions": {
                "description": "Reference condition effects and apply them to combatants",
                "shortcut": "Ctrl+5"
            },
            "rules_reference": {
                "description": "Quick access to game rules and mechanics",
                "shortcut": "Ctrl+6"
            },
            # Campaign Category
            "session_notes": {
                "description": "Create, edit and organize campaign notes",
                "shortcut": "Ctrl+7"
            },
            "player_character": {
                "description": "Manage player character information and stats",
                "shortcut": "Ctrl+8"
            },
            "encounter_generator": {
                "description": "Generate balanced encounters based on party level",
                "shortcut": "Ctrl+9"
            },
            "npc_generator": {
                "description": "Create NPCs with personalities, goals, and backstories",
                "shortcut": ""
            },
            "location_generator": {
                "description": "Generate detailed locations, buildings, and environments",
                "shortcut": ""
            },
            "treasure_generator": {
                "description": "Create appropriate treasure for encounters and hoards",
                "shortcut": ""
            },
            # Utility Category
            "llm": {
                "description": "AI assistant for creative ideas and game rulings",
                "shortcut": "Ctrl+0"
            },
            "weather": {
                "description": "Track and generate weather conditions",
                "shortcut": ""
            },
            "time_tracker": {
                "description": "Keep track of in-game time, rest periods, and events",
                "shortcut": ""
            },
            "rules_clarification": {
                "description": "Get AI assistance for rules explanations and interpretations",
                "shortcut": ""
            }
        }
        
        # Define panel categories and their order
        panel_categories = [
            {
                "title": "Combat",
                "panels": ["combat_tracker", "dice_roller"]
            },
            {
                "title": "Reference",
                "panels": ["monster", "spell_reference", "conditions", "rules_reference"]
            },
            {
                "title": "Campaign",
                "panels": ["session_notes", "player_character", "encounter_generator", "npc_generator", "location_generator", "treasure_generator"]
            },
            {
                "title": "Utility",
                "panels": ["llm", "weather", "time_tracker", "rules_clarification"]
            }
        ]
        
        # Create buttons for each category
        for category in panel_categories:
            # Add category label
            category_label = QLabel(f"<b>{category['title']}</b>:")
            category_label.setStyleSheet("margin-left: 10px; margin-right: 5px;")
            toolbar.addWidget(category_label)
            
            # Add buttons for panels in this category
            for panel_id in category['panels']:
                if panel_id in self.panel_actions:
                    action = self.panel_actions[panel_id]
                    panel_name = panel_id.replace('_', ' ').title()
                    
                    # Create the button with a more descriptive name
                    panel_button = toolbar.addAction(panel_name)
                    
                    # Create detailed tooltip with shortcut info if available
                    tooltip = panel_info.get(panel_id, {})
                    desc = tooltip.get("description", f"Toggle {panel_name} Panel")
                    shortcut = tooltip.get("shortcut", "")
                    tooltip_text = f"{desc}"
                    if shortcut:
                        tooltip_text += f" ({shortcut})"
                        
                        # Set the actual keyboard shortcut
                        panel_button.setShortcut(shortcut)
                    
                    panel_button.setToolTip(tooltip_text)
                    panel_button.triggered.connect(lambda checked=False, p=panel_id: self.panel_manager.toggle_panel(p))
                    
                    # Store the action for state updates
                    self.panel_actions[f"{panel_id}_toolbar"] = panel_button
            
            # Add separator between categories (except after the last one)
            if category != panel_categories[-1]:
                toolbar.addSeparator()
        
        # Add spacer between panel buttons and layout selector
        spacer_label = QLabel()
        spacer_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        toolbar.addWidget(spacer_label)
        
        # Initialize layout selector as a QMenu
        self.layout_selector = QMenu("Layouts")
        layout_button = toolbar.addAction("Select Layout")
        layout_button.setToolTip("Choose, save, or manage panel layouts")
        layout_button.setMenu(self.layout_selector)

        # Populate layout selector
        self._update_layout_selector()
        
        # Update panel action states to reflect current visibility
        self._update_panel_action_states()
    
    def _update_layout_selector(self):
        """Update the layout selector menu with available layouts"""
        self.layout_selector.clear()
        
        # Add quick actions
        save_action = self.layout_selector.addAction("Save Current Layout")
        save_action.triggered.connect(self._save_layout)
        
        load_action = self.layout_selector.addAction("Load Layout...")
        load_action.triggered.connect(self._load_layout)
        
        self.layout_selector.addSeparator()
        
        # Add current layout indicator
        current_layout_action = self.layout_selector.addAction(
            f"Current: {self.app_state.current_layout_name}")
        current_layout_action.setEnabled(False)
        
        self.layout_selector.addSeparator()
        
        # Get all available layouts
        layouts = self.app_state.get_available_layouts()
        
        # Add preset layouts
        preset_menu = self.layout_selector.addMenu("Preset Layouts")
        
        preset_layouts = {name: data for name, data in layouts.items() 
                         if data.get("is_preset", False)}
        
        if not preset_layouts:
            empty_action = preset_menu.addAction("No presets available")
            empty_action.setEnabled(False)
        else:
            for name in sorted(preset_layouts.keys()):
                action = preset_menu.addAction(name)
                action.triggered.connect(lambda checked=False, n=name: self._load_preset_layout(n))
        
        # Add user layouts
        user_menu = self.layout_selector.addMenu("User Layouts")
        
        user_layouts = {name: data for name, data in layouts.items() 
                       if not data.get("is_preset", False)}
        
        if not user_layouts:
            empty_action = user_menu.addAction("No user layouts available")
            empty_action.setEnabled(False)
        else:
            for name in sorted(user_layouts.keys()):
                action = user_menu.addAction(name)
                action.triggered.connect(lambda checked=False, n=name: self._load_preset_layout(n))
    
    def _update_panel_action_states(self):
        """Update the state of all panel-related UI elements"""
        # First, update menu items
        for panel_id, action in self.panel_actions.items():
            # Extract the base panel id from toolbar items
            base_panel_id = panel_id.split('_toolbar')[0]
            
            # Set checkable for checkbox-like behavior
            action.setCheckable(True)
            
            # Set checked state based on panel visibility
            if action.isCheckable():
                action.setChecked(self.panel_manager.is_panel_visible(base_panel_id))
        
        # Apply visual styling to toolbar buttons
        self._style_toolbar_buttons()
    
    def _style_toolbar_buttons(self):
        """Apply styling to toolbar buttons based on panel states and categories"""
        toolbar = self.findChild(QToolBar)
        if not toolbar:
            return
            
        # Set appropriate styling for each action in the toolbar
        for action in toolbar.actions():
            if not action.text() or action.text() == "Select Layout":  # Skip separators and layout selector
                continue
                
            # Find the corresponding panel if any
            panel_id = None
            for key, act in self.panel_actions.items():
                if act == action:
                    panel_id = key.split('_toolbar')[0] if '_toolbar' in key else key
                    break
            
            if panel_id:
                # Get the panel's category
                category = PanelCategory.get_category(panel_id)
                colors = PanelCategory.get_colors(panel_id, self.current_theme)
                
                toolbar_btn = toolbar.widgetForAction(action)
                if not toolbar_btn:
                    continue
                
                is_visible = self.panel_manager.is_panel_visible(panel_id)
                    
                if is_visible and colors:
                    # Style the active button
                    toolbar_btn.setStyleSheet(f"""
                        background-color: {colors['title_bg'].name()};
                        color: {colors['title_text'].name()};
                        font-weight: bold;
                        border: 1px solid {colors['border'].name()};
                        border-radius: 4px;
                        padding: 4px 8px;
                        margin: 2px 3px;
                    """)
                else:
                    # Inactive button style - lighter and less prominent
                    light_text = "#E0E0E0" if self.current_theme == "dark" else "#505050"
                    light_bg = "#424242" if self.current_theme == "dark" else "#F0F0F0"
                    border_color = "#555555" if self.current_theme == "dark" else "#CCCCCC"
                    
                    # Apply category hint color to inactive buttons
                    if colors:
                        hint_color = colors['title_bg'].name()
                        # Make the color more subtle for inactive state
                        toolbar_btn.setStyleSheet(f"""
                            background-color: {light_bg};
                            color: {light_text};
                            border: 1px solid {border_color};
                            border-left: 3px solid {hint_color};
                            border-radius: 4px;
                            padding: 4px 8px;
                            margin: 2px 3px;
                        """)
                    else:
                        toolbar_btn.setStyleSheet(f"""
                            background-color: {light_bg};
                            color: {light_text};
                            border: 1px solid {border_color};
                            border-radius: 4px;
                            padding: 4px 8px;
                            margin: 2px 3px;
                        """)
    
    def _create_status_bar(self):
        """Create the status bar"""
        status_bar = QStatusBar()
        self.setStatusBar(status_bar)
        status_bar.showMessage("Ready")
    
    def _show_welcome_panel(self):
        """Show the welcome panel when no layout is loaded or when requested"""
        # Store the currently visible panels to restore later
        self.stored_visible_panels = []
        for panel_id, dock in self.panel_manager.panels.items():
            if dock and dock.isVisible():
                self.stored_visible_panels.append(panel_id)
                dock.hide()
        
        # Create and show the welcome panel
        welcome = WelcomePanel(self.panel_manager)
        welcome.panel_selected.connect(self._hide_welcome_panel)
        self.setCentralWidget(welcome)
        self.welcome_panel = welcome  # Store reference to access later
    
    def _hide_welcome_panel(self):
        """Hide the welcome panel and restore previous panels"""
        self.setCentralWidget(None)
        self.welcome_panel = None
        
        # Restore previously visible panels
        if hasattr(self, 'stored_visible_panels') and self.stored_visible_panels:
            for panel_id in self.stored_visible_panels:
                panel = self.panel_manager.get_panel(panel_id)
                if panel:
                    panel.show()
            
            # Restore panel organization
            self.panel_manager.smart_organize_panels()
            self.stored_visible_panels = []
    
    def _load_initial_layout(self):
        """Load the initial layout or show welcome screen if no layout is available"""
        success, data, ui_state = self.app_state.load_layout()
        
        if success:
            # Apply the layout
            self._apply_layout(data, ui_state)
        else:
            # Show welcome screen if no layout available
            self._show_welcome_panel()
    
    def _apply_layout(self, layout_data, ui_state):
        """Apply a loaded layout to the application
        
        Args:
            layout_data (dict): The layout configuration data
            ui_state (bytes): The UI state to restore with restoreState()
        """
        # Check if we have panel data
        if not layout_data or "visible_panels" not in layout_data:
            return
        
        # First, hide all existing panels
        self.panel_manager.close_all_panels()
            
        # Show the visible panels from the layout
        for panel_id in layout_data.get("visible_panels", []):
            panel = self.panel_manager.get_panel(panel_id)
            if panel:
                panel.show()
        
        # Restore panel states if available
        if "panel_states" in layout_data:
            self.panel_manager.restore_state(layout_data["panel_states"])
            
        # Restore UI state
        if ui_state:
            self.restoreState(ui_state)
            
        # Ensure no panels overlap window edges
        self._adjust_panel_positions()
        
        # Update UI
        self._update_panel_action_states()
        self._update_layout_selector()
        
        # Update status
        self.statusBar().showMessage(
            f"Loaded layout: {self.app_state.current_layout_name}")
    
    def _new_session(self):
        """Create a new session, clearing current panels"""
        reply = QMessageBox.question(
            self, "New Session",
            "Create a new session? This will close all current panels.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.panel_manager.close_all_panels()
            self._show_welcome_panel()
            self._update_panel_action_states()
    
    def _open_session(self):
        """Open a saved session file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Session", str(self.app_state.app_dir),
            "DM Screen Session (*.dms);;All Files (*)"
        )
        
        if file_path:
            # TODO: Implement session loading logic
            self.statusBar().showMessage(f"Opened session: {file_path}")
    
    def _save_session(self):
        """Save the current session to file"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Session", str(self.app_state.app_dir),
            "DM Screen Session (*.dms);;All Files (*)"
        )
        
        if file_path:
            # TODO: Implement session saving logic
            self.statusBar().showMessage(f"Saved session: {file_path}")
    
    def _save_layout(self):
        """Save the current layout configuration to the current layout name"""
        # Get the current visible panels
        visible_panels = []
        for panel_id, dock in self.panel_manager.panels.items():
            if dock and dock.isVisible():
                visible_panels.append(panel_id)
                
        # Save panel states
        panel_states = self.panel_manager.save_state()
        
        # Create layout data dictionary
        layout_data = {
            "visible_panels": visible_panels,
            "panel_states": panel_states
        }
        
        # Get UI state
        ui_state = self.saveState()
        
        # Save to current layout
        current_name = self.app_state.current_layout_name
        success = self.app_state.save_layout(
            name=current_name,
            layout_data=layout_data,
            ui_state=ui_state
        )
        
        if success:
            self.statusBar().showMessage(f"Layout saved as '{current_name}'")
            # Update UI
            self._update_layout_selector()
        else:
            self.statusBar().showMessage("Failed to save layout")
    
    def _save_layout_as(self):
        """Save the current layout with a new name"""
        # Get a list of existing layout names
        existing_layouts = list(self.app_state.get_available_layouts().keys())
        
        # Show the layout name dialog
        dialog = LayoutNameDialog(
            self, 
            existing_layouts=existing_layouts,
            current_layout=self.app_state.current_layout_name
        )
        
        if dialog.exec_():
            # Get the layout name and preset status
            layout_name = dialog.layout_name
            is_preset = dialog.is_preset
            category = dialog.preset_category if is_preset else None
            
            # Get the current visible panels
            visible_panels = []
            for panel_id, dock in self.panel_manager.panels.items():
                if dock and dock.isVisible():
                    visible_panels.append(panel_id)
                    
            # Save panel states
            panel_states = self.panel_manager.save_state()
            
            # Create layout data dictionary
            layout_data = {
                "visible_panels": visible_panels,
                "panel_states": panel_states,
                "description": f"Custom layout created on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            }
            
            # Get UI state
            ui_state = self.saveState()
            
            # Save the layout
            success = self.app_state.save_layout(
                name=layout_name,
                layout_data=layout_data,
                ui_state=ui_state,
                is_preset=is_preset,
                category=category
            )
            
            if success:
                self.statusBar().showMessage(f"Layout saved as '{layout_name}'")
                # Update UI
                self._update_layout_selector()
                self._populate_preset_layouts_menu()
            else:
                self.statusBar().showMessage("Failed to save layout")
    
    def _load_layout(self):
        """Load a saved layout configuration through a selection dialog"""
        # Get available layouts
        layouts = self.app_state.get_available_layouts()
        
        # Show layout selection dialog
        dialog = LayoutSelectDialog(
            self,
            layouts=layouts,
            current_layout=self.app_state.current_layout_name
        )
        
        if dialog.exec_():
            selected_layout = dialog.selected_layout
            if selected_layout:
                self._load_preset_layout(selected_layout)
    
    def _load_preset_layout(self, layout_name):
        """Load a specific layout by name
        
        Args:
            layout_name (str): Name of the layout to load
        """
        # Load the layout from app state
        success, data, ui_state = self.app_state.load_layout(layout_name)
        
        if success:
            # Apply the layout
            self._apply_layout(data, ui_state)
        else:
            self.statusBar().showMessage(f"Failed to load layout '{layout_name}'")
    
    def _manage_layouts(self):
        """Open the layout management dialog to delete or export layouts"""
        # Get available layouts
        layouts = self.app_state.get_available_layouts()
        
        # Show layout selection dialog
        dialog = QInputDialog(self)
        dialog.setWindowTitle("Delete Layout")
        dialog.setLabelText("Select layout to delete:")
        dialog.setComboBoxItems(sorted(layouts.keys()))
        dialog.setComboBoxEditable(False)
        
        if dialog.exec_():
            layout_name = dialog.textValue()
            
            # Confirm deletion
            reply = QMessageBox.question(
                self, "Delete Layout",
                f"Are you sure you want to delete the layout '{layout_name}'?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                # Delete the layout
                success = self.app_state.delete_layout(layout_name)
                
                if success:
                    self.statusBar().showMessage(f"Deleted layout '{layout_name}'")
                    # Update UI
                    self._update_layout_selector()
                    self._populate_preset_layouts_menu()
                else:
                    self.statusBar().showMessage(f"Failed to delete layout '{layout_name}'")
    
    def _smart_organize_panels(self):
        """Smart organize all visible panels"""
        message = self.panel_manager.smart_organize_panels()
        self.statusBar().showMessage(message)
        self._update_panel_action_states()
    
    def _change_theme(self, theme_name):
        """Change the application theme"""
        # Get current font size
        current_font_size = self.app_state.get_setting("font_size", "medium")
        
        # Apply the theme with current font size
        apply_theme(self, theme_name, current_font_size)
        
        # Store the theme selection
        self.current_theme = theme_name
        self.app_state.set_setting("theme", theme_name)
        
        # Update UI elements
        self.statusBar().showMessage(f"Theme changed to {theme_name}", 3000)
        
        # Trigger update of toolbar icon styles
        self._style_toolbar_buttons()
    
    def _change_font_size(self, size_name):
        """Change the application font size"""
        # Apply the font size
        set_font_size(size_name)
        
        # Store the font size selection
        self.app_state.set_setting("font_size", size_name)
        
        # Update UI elements
        self.statusBar().showMessage(f"Font size changed to {size_name}", 3000)
        
        # Re-apply theme to ensure consistent appearance
        apply_theme(self, self.current_theme, size_name)
    
    def _show_about(self):
        """Show about dialog"""
        QMessageBox.about(
            self,
            "About DM Screen",
            "DM Screen V0.1.0\n\n"
            "A dynamic Dungeon Master's Screen for D&D 5e\n"
            "Provides quick access to rules, references, and tools."
        )
    
    def closeEvent(self, event):
        """Handle application close event"""
        # Stop the update timer
        if hasattr(self, 'update_timer'):
            self.update_timer.stop()
        
        try:
            # Prompt to save session if auto-save is disabled
            if not self.app_state.get_setting("auto_save", True):
                reply = QMessageBox.question(
                    self, "Exit",
                    "Save current session before exiting?",
                    QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                    QMessageBox.Yes
                )
                
                if reply == QMessageBox.Cancel:
                    event.ignore()
                    return
                
                if reply == QMessageBox.Yes:
                    self._save_session()
            
            # Always save the current layout before exiting
            self._save_layout()
            
            # Clean up resources
            self.app_state.close()
            
            event.accept()
        except Exception as e:
            print(f"Error during application close: {e}")
            # Still accept the close event even if saving failed
            event.accept()

    def _adjust_panel_positions(self):
        """Adjust panel positions to ensure they don't overlap toolbar or window edges"""
        # Give panels a moment to position themselves
        QTimer.singleShot(100, self._do_adjust_panel_positions)
    
    def _do_adjust_panel_positions(self):
        """Actually perform the panel position adjustment"""
        main_window_geometry = self.geometry()
        
        # Get toolbar height more reliably
        toolbar = self.findChild(QToolBar, "MainToolbar")
        toolbar_height = toolbar.height() if toolbar else 30
        
        statusbar_height = self.statusBar().height()
        
        # Get effective area
        min_y = toolbar_height + 5
        max_y = main_window_geometry.height() - statusbar_height - 5
        min_x = 5
        max_x = main_window_geometry.width() - 5
        
        # Adjust panel positions if needed
        for dock in self.findChildren(QDockWidget):
            if dock.isFloating():
                dock_geometry = dock.geometry()
                
                # Ensure panel is visible
                if dock_geometry.top() < min_y:
                    dock_geometry.moveTop(min_y)
                if dock_geometry.bottom() > max_y:
                    dock_geometry.moveBottom(max_y)
                if dock_geometry.left() < min_x:
                    dock_geometry.moveLeft(min_x)
                if dock_geometry.right() > max_x:
                    dock_geometry.moveRight(max_x)
                
                dock.setGeometry(dock_geometry)

    def _toggle_welcome_panel(self):
        """Toggle the welcome panel visibility"""
        # If welcome panel is visible, hide it
        if self.centralWidget() and isinstance(self.centralWidget(), WelcomePanel):
            self._hide_welcome_panel()
        else:
            # Otherwise show it
            self._show_welcome_panel()
            
            # Force layout update to ensure welcome panel fills the available space
            if self.welcome_panel:
                self.welcome_panel.adjustSize()
                QTimer.singleShot(100, lambda: self._resize_welcome_panel())
    
    def _resize_welcome_panel(self):
        """Resize the welcome panel to fill the central widget area"""
        if self.welcome_panel:
            self.welcome_panel.setGeometry(self.centralWidget().rect())
            self.centralWidget().update()
    
    def resizeEvent(self, event):
        """Handle window resize events"""
        if event:
            super().resizeEvent(event)
        
        # If welcome panel is visible, resize it to fill the space
        if self.centralWidget() and isinstance(self.centralWidget(), WelcomePanel):
            self._resize_welcome_panel()

    def keyPressEvent(self, event):
        """Handle key press events"""
        # F1 toggles welcome panel
        if event.key() == Qt.Key_F1:
            self._toggle_welcome_panel()
            event.accept()
        else:
            super().keyPressEvent(event)

    def _connect_panel_signals(self):
        """Connect signals between different panels."""
        print("Attempting to connect panel signals...") # Debug
        try:
            # The connections below are now handled by PanelManager._connect_panel_signals
            # and we're avoiding duplicate connections that would cause duplicate notes
            
            # --- Connect other signals that aren't handled by PanelManager here --- 
            pass  # Currently no additional connections needed here

        except Exception as e:
            print(f"Error connecting panel signals: {e}")
            import traceback
            traceback.print_exc() # Print full traceback for debugging
            # Consider logging this error more formally
