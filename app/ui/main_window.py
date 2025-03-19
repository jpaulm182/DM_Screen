# app/ui/main_window.py - Main application window
"""
Main window for the DM Screen application

Implements the main UI window with dynamic layout system and panel management.
"""

from PySide6.QtWidgets import (
    QMainWindow, QDockWidget, QToolBar, QMenu, QMenuBar,
    QStatusBar, QFileDialog, QMessageBox, QLabel
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QAction

from app.ui.panel_manager import PanelManager
from app.ui.panels.welcome_panel import WelcomePanel
from app.ui.theme_manager import apply_theme
from app.ui.panels.panel_category import PanelCategory


class MainWindow(QMainWindow):
    """
    Main application window with dockable panels and menu system
    """
    
    def __init__(self, app_state):
        """Initialize the main window and UI components"""
        super().__init__()
        self.app_state = app_state
        self.panel_manager = PanelManager(self, app_state)
        
        self._setup_ui()
        self._create_menus()
        self._create_toolbar()
        self._create_status_bar()
        
        # Apply the current theme
        self.current_theme = app_state.get_setting("theme", "dark")
        apply_theme(self, self.current_theme)
        
        # Load the default layout or show welcome screen
        if not self.app_state.load_layout():
            self._show_welcome_panel()
    
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
        
        load_layout_action = layout_menu.addAction("&Load Layout")
        load_layout_action.setShortcut("Ctrl+Alt+L")
        load_layout_action.triggered.connect(self._load_layout)
        
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
        
        # Panels menu
        panels_menu = self.menuBar().addMenu("&Panels")
        
        # Combat panels
        combat_menu = panels_menu.addMenu("&Combat Tools")
        combat_menu.addAction("Combat Tracker").triggered.connect(
            lambda: self.panel_manager.toggle_panel("combat_tracker"))
        combat_menu.addAction("Dice Roller").triggered.connect(
            lambda: self.panel_manager.toggle_panel("dice_roller"))
        
        # Reference panels
        reference_menu = panels_menu.addMenu("&Reference")
        reference_menu.addAction("Rules Reference").triggered.connect(
            lambda: self.panel_manager.toggle_panel("rules_reference"))
        reference_menu.addAction("Conditions").triggered.connect(
            lambda: self.panel_manager.toggle_panel("conditions"))
        reference_menu.addAction("Monsters").triggered.connect(
            lambda: self.panel_manager.toggle_panel("monster"))
        reference_menu.addAction("Spells").triggered.connect(
            lambda: self.panel_manager.toggle_panel("spell_reference"))
            
        # Campaign Management panels
        campaign_menu = panels_menu.addMenu("&Campaign")
        campaign_menu.addAction("Session Notes").triggered.connect(
            lambda: self.panel_manager.toggle_panel("session_notes"))
        
        # Utility panels
        utility_menu = panels_menu.addMenu("&Utilities")
        utility_menu.addAction("Weather Generator").triggered.connect(
            lambda: self.panel_manager.toggle_panel("weather"))
        utility_menu.addAction("Time Tracker").triggered.connect(
            lambda: self.panel_manager.toggle_panel("time_tracker"))
        
        # Help menu
        help_menu = self.menuBar().addMenu("&Help")
        help_menu.addAction("&About").triggered.connect(self._show_about)
    
    def _create_toolbar(self):
        """Create the main toolbar"""
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(toolbar)
        
        # Add quick access actions
        new_action = toolbar.addAction("New")
        new_action.setToolTip("New Session (Ctrl+Shift+N)")
        new_action.triggered.connect(self._new_session)
        
        save_action = toolbar.addAction("Save")
        save_action.setToolTip("Save Session (Ctrl+Shift+S)")
        save_action.triggered.connect(self._save_session)
        
        # Add Smart Organize button
        organize_action = toolbar.addAction("Smart Organize")
        organize_action.setToolTip("Smart Organize Panels (Ctrl+Alt+O)")
        organize_action.triggered.connect(self._smart_organize_panels)
        
        toolbar.addSeparator()
        
        # Combat tools section
        combat_label = QLabel("Combat:")
        toolbar.addWidget(combat_label)
        
        dice_action = toolbar.addAction("Dice")
        dice_action.setToolTip("Dice Roller (Ctrl+D)")
        dice_action.triggered.connect(lambda: self.panel_manager.toggle_panel("dice_roller"))
        
        combat_action = toolbar.addAction("Combat")
        combat_action.setToolTip("Combat Tracker (Ctrl+T)")
        combat_action.triggered.connect(lambda: self.panel_manager.toggle_panel("combat_tracker"))
        
        toolbar.addSeparator()
        
        # Reference section
        ref_label = QLabel("Reference:")
        toolbar.addWidget(ref_label)
        
        spell_action = toolbar.addAction("Spells")
        spell_action.setToolTip("Spell Reference (Ctrl+S)")
        spell_action.triggered.connect(lambda: self.panel_manager.toggle_panel("spell_reference"))
        
        conditions_action = toolbar.addAction("Conditions")
        conditions_action.setToolTip("Conditions Reference")
        conditions_action.triggered.connect(lambda: self.panel_manager.toggle_panel("conditions"))
        
        rules_action = toolbar.addAction("Rules")
        rules_action.setToolTip("Rules Reference")
        rules_action.triggered.connect(lambda: self.panel_manager.toggle_panel("rules_reference"))
        
        monster_action = toolbar.addAction("Monsters")
        monster_action.setToolTip("Monster Reference")
        monster_action.triggered.connect(lambda: self.panel_manager.toggle_panel("monster"))
        
        toolbar.addSeparator()
        
        # Campaign section
        campaign_label = QLabel("Campaign:")
        toolbar.addWidget(campaign_label)
        
        notes_action = toolbar.addAction("Notes")
        notes_action.setToolTip("Session Notes (Ctrl+N)")
        notes_action.triggered.connect(lambda: self.panel_manager.toggle_panel("session_notes"))
        
        toolbar.addSeparator()
        
        # Utility section
        utility_label = QLabel("Utilities:")
        toolbar.addWidget(utility_label)
        
        weather_action = toolbar.addAction("Weather")
        weather_action.setToolTip("Weather Panel (Ctrl+W)")
        weather_action.triggered.connect(lambda: self.panel_manager.toggle_panel("weather"))
        
        time_action = toolbar.addAction("Time")
        time_action.setToolTip("Time Tracker (Ctrl+I)")
        time_action.triggered.connect(lambda: self.panel_manager.toggle_panel("time_tracker"))
    
    def _create_status_bar(self):
        """Create the status bar"""
        status_bar = QStatusBar()
        self.setStatusBar(status_bar)
        status_bar.showMessage("Ready")
    
    def _show_welcome_panel(self):
        """Show the welcome panel when no layout is loaded"""
        welcome = WelcomePanel(self.panel_manager)
        self.setCentralWidget(welcome)
    
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
        """Save the current layout configuration"""
        # TODO: Implement dialog to name the layout
        self.app_state.save_layout()
        self.statusBar().showMessage("Layout saved")
    
    def _load_layout(self):
        """Load a saved layout configuration"""
        # TODO: Implement layout selection dialog
        self.app_state.load_layout()
        self.statusBar().showMessage("Layout loaded")
    
    def _smart_organize_panels(self):
        """Smart organize all visible panels"""
        message = self.panel_manager.smart_organize_panels()
        self.statusBar().showMessage(message)
    
    def _change_theme(self, theme_name):
        """Change the application theme"""
        # Apply theme to UI
        apply_theme(self, theme_name)
        
        # Update panel_manager theme
        self.panel_manager.update_theme(theme_name)
        
        # Store theme in settings
        self.app_state.set_setting("theme", theme_name)
        self.current_theme = theme_name
        
        self.statusBar().showMessage(f"Theme changed to {theme_name}")
    
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
        
        # Always save the current layout
        self.app_state.save_layout()
        
        event.accept()
