# app/ui/main_window.py - Main application window
"""
Main window for the DM Screen application

Implements the main UI window with dynamic layout system and panel management.
"""

from PySide6.QtWidgets import (
    QMainWindow, QDockWidget, QToolBar, QMenu, QMenuBar,
    QStatusBar, QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QAction

from app.ui.panel_manager import PanelManager
from app.ui.panels.welcome_panel import WelcomePanel
from app.ui.theme_manager import apply_theme


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
        apply_theme(self, app_state.get_setting("theme", "dark"))
        
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
        
        # Combat Tracker
        combat_action = QAction("Combat &Tracker", self)
        combat_action.setShortcut("Ctrl+T")
        combat_action.triggered.connect(lambda: self.panel_manager.create_panel("combat_tracker"))
        panels_menu.addAction(combat_action)
        
        # Dice Roller
        dice_action = QAction("&Dice Roller", self)
        dice_action.setShortcut("Ctrl+D")
        dice_action.triggered.connect(lambda: self.panel_manager.create_panel("dice_roller"))
        panels_menu.addAction(dice_action)
        
        # Conditions Reference
        conditions_action = QAction("&Conditions", self)
        conditions_action.setShortcut("Ctrl+C")
        conditions_action.triggered.connect(lambda: self.panel_manager.create_panel("conditions"))
        panels_menu.addAction(conditions_action)
        
        # Rules Reference
        rules_action = QAction("&Rules Reference", self)
        rules_action.setShortcut("Ctrl+R")
        rules_action.triggered.connect(lambda: self.panel_manager.create_panel("rules_reference"))
        panels_menu.addAction(rules_action)
        
        # Monster Reference
        monster_action = QAction("&Monster Reference", self)
        monster_action.setShortcut("Ctrl+M")
        monster_action.triggered.connect(lambda: self.panel_manager.create_panel("monster"))
        panels_menu.addAction(monster_action)
        
        # Spell Reference
        spell_action = QAction("&Spell Reference", self)
        spell_action.setShortcut("Ctrl+S")
        spell_action.triggered.connect(lambda: self.panel_manager.create_panel("spell_reference"))
        panels_menu.addAction(spell_action)
        
        # Weather Panel
        weather_action = QAction("&Weather", self)
        weather_action.setShortcut("Ctrl+W")
        weather_action.triggered.connect(lambda: self.panel_manager.create_panel("weather"))
        panels_menu.addAction(weather_action)
        
        # Time Tracker Panel
        time_action = QAction("T&ime Tracker", self)
        time_action.setShortcut("Ctrl+I")
        time_action.triggered.connect(lambda: self.panel_manager.create_panel("time_tracker"))
        panels_menu.addAction(time_action)
        
        # Session Notes Panel
        notes_action = QAction("Session &Notes", self)
        notes_action.setShortcut("Ctrl+N")
        notes_action.triggered.connect(lambda: self.panel_manager.create_panel("session_notes"))
        panels_menu.addAction(notes_action)
        
        panels_menu.addSeparator()
        
        # Generators menu
        generators_menu = panels_menu.addMenu("&Generators")
        
        encounter_action = generators_menu.addAction("&Encounter Generator")
        encounter_action.setShortcut("Ctrl+Shift+E")
        encounter_action.triggered.connect(lambda: self.panel_manager.create_panel("encounter_generator"))
        
        treasure_action = generators_menu.addAction("&Treasure Generator")
        treasure_action.setShortcut("Ctrl+Shift+T")
        treasure_action.triggered.connect(lambda: self.panel_manager.create_panel("treasure_generator"))
        
        npc_action = generators_menu.addAction("&NPC Generator")
        npc_action.setShortcut("Ctrl+Shift+N")
        npc_action.triggered.connect(lambda: self.panel_manager.create_panel("npc_generator"))
        
        # Help menu
        help_menu = self.menuBar().addMenu("&Help")
        
        about_action = help_menu.addAction("&About")
        about_action.triggered.connect(self._show_about)
    
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
        
        toolbar.addSeparator()
        
        dice_action = toolbar.addAction("Dice")
        dice_action.setToolTip("Dice Roller (Ctrl+D)")
        dice_action.triggered.connect(lambda: self.panel_manager.create_panel("dice_roller"))
        
        combat_action = toolbar.addAction("Combat")
        combat_action.setToolTip("Combat Tracker (Ctrl+T)")
        combat_action.triggered.connect(lambda: self.panel_manager.create_panel("combat_tracker"))
        
        spell_action = toolbar.addAction("Spells")
        spell_action.setToolTip("Spell Reference (Ctrl+S)")
        spell_action.triggered.connect(lambda: self.panel_manager.create_panel("spell_reference"))
        
        notes_action = toolbar.addAction("Notes")
        notes_action.setToolTip("Session Notes (Ctrl+N)")
        notes_action.triggered.connect(lambda: self.panel_manager.create_panel("session_notes"))
        
        weather_action = toolbar.addAction("Weather")
        weather_action.setToolTip("Weather Panel (Ctrl+W)")
        weather_action.triggered.connect(lambda: self.panel_manager.create_panel("weather"))
        
        time_action = toolbar.addAction("Time")
        time_action.setToolTip("Time Tracker (Ctrl+I)")
        time_action.triggered.connect(lambda: self.panel_manager.create_panel("time_tracker"))
    
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
        if self.app_state.load_layout():
            # Apply the loaded layout
            self.panel_manager.apply_layout(self.app_state.layout_config)
            self.statusBar().showMessage("Layout loaded")
    
    def _change_theme(self, theme):
        """Change the application theme"""
        self.app_state.set_setting("theme", theme)
        apply_theme(self, theme)
        self.statusBar().showMessage(f"Theme changed to {theme}")
    
    def _show_about(self):
        """Show the about dialog"""
        QMessageBox.about(
            self, "About DM Screen V0",
            "DM Screen V0\n\n"
            "A dynamic Dungeon Master's screen for D&D 5e.\n\n"
            "Created by jpaulm182"
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
