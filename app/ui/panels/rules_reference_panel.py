"""
Basic rules quick-reference panel for D&D 5e

Features:
- Quick access to common rules
- Searchable content
- Categorized rules sections
- Bookmarking system
"""

from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTreeWidget, QTreeWidgetItem, QTextEdit, QLineEdit,
    QWidget, QSplitter, QMenu, QToolBar, QComboBox, QMessageBox, QApplication
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QIcon, QAction

from app.ui.panels.base_panel import BasePanel

# D&D 5e Basic Rules Categories and Content
RULES = {
    "Ability Checks": {
        "Basic Rules": """
• Roll d20 + ability modifier
• DC set by DM (typically 10-20)
• Advantage: Roll 2d20, take higher
• Disadvantage: Roll 2d20, take lower""",
        
        "Common DCs": """
Very Easy: 5
Easy: 10
Medium: 15
Hard: 20
Very Hard: 25
Nearly Impossible: 30""",

        "Group Checks": """
• When everyone in a group needs to make a check
• At least half the group must succeed"""
    },
    
    "Combat Actions": {
        "Standard Actions": """
• Attack
• Cast a Spell
• Dash
• Disengage
• Dodge
• Help
• Hide
• Ready
• Search
• Use an Object""",

        "Bonus Actions": """
• Only one per turn
• Must be specifically granted by ability/spell
• Common sources: Two-Weapon Fighting, Cunning Action, Healing Word""",

        "Reactions": """
• Only one per round
• Triggered by specific circumstance
• Common types: Opportunity Attacks, Shield spell, Counterspell"""
    },
    
    "Combat Rules": {
        "Turn Structure": """
1. Move (up to speed)
2. Action
3. Bonus Action (if available)
4. Free Action (interact with one object)""",

        "Attack Rolls": """
• Roll d20 + ability modifier + proficiency (if proficient)
• Compare to target's AC
• Natural 20: Critical hit
• Natural 1: Automatic miss""",

        "Damage": """
• Roll specified weapon/spell damage
• Add ability modifier (usually)
• Critical hits: Roll damage dice twice
• Resistance: Half damage
• Vulnerability: Double damage"""
    },
    
    "Spellcasting": {
        "Casting Time": """
• Action: Most common
• Bonus Action: Quick spells
• Reaction: Response spells
• 1+ Minutes: Ritual spells""",

        "Components": """
• Verbal (V): Must be able to speak
• Somatic (S): Must have free hand
• Material (M): Must have components/focus""",

        "Concentration": """
• Only one concentration spell at a time
• Ends if: Cast another concentration spell, Incapacitated, Failed Con save
• Con save when taking damage: DC 10 or half damage (whichever higher)"""
    },
    
    "Environment & Exploration": {
        "Light": """
• Bright light: Normal vision
• Dim light: Lightly obscured
• Darkness: Heavily obscured""",

        "Cover": """
• Half cover: +2 AC and Dex saves
• Three-quarters cover: +5 AC and Dex saves
• Full cover: Can't be targeted directly""",

        "Travel Pace": """
Fast: -5 passive perception
Normal: Standard
Slow: Able to stealth"""
    },
    
    "Resting": {
        "Short Rest": """
• 1 hour minimum
• Can spend Hit Dice
• Some abilities recharge""",

        "Long Rest": """
• 8 hours
• Must be peaceful
• Regain all HP
• Regain half total Hit Dice
• Reset daily abilities
• Can't benefit from more than one per 24 hours"""
    }
}

class RulesReferencePanel(BasePanel):
    """Panel for quick access to D&D 5e basic rules"""
    
    def __init__(self, app_state):
        # Initialize variables before calling parent's __init__
        self.current_category = None
        self.current_rule = None
        self.bookmarks = set()
        
        # Create bookmark icon with fallbacks
        self.bookmark_icon = QIcon.fromTheme("bookmark")
        if self.bookmark_icon.isNull():
            self.bookmark_icon = QIcon.fromTheme("favorite")
        if self.bookmark_icon.isNull():
            # Create a simple star icon as fallback
            self.bookmark_action_text = "★ Bookmark"  # Unicode star
        else:
            self.bookmark_action_text = "Bookmark"
        
        # Now call parent's __init__ which will call _setup_ui
        super().__init__(app_state, "Rules Reference")
    
    def _setup_ui(self):
        """Set up the rules reference UI"""
        main_layout = QVBoxLayout()
        
        # Search and filter
        search_layout = QHBoxLayout()
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search rules...")
        self.search_input.textChanged.connect(self._filter_rules)
        search_layout.addWidget(self.search_input)
        
        self.category_filter = QComboBox()
        self.category_filter.addItem("All Categories")
        self.category_filter.addItems(sorted(RULES.keys()))
        self.category_filter.currentTextChanged.connect(self._filter_rules)
        search_layout.addWidget(self.category_filter)
        
        main_layout.addLayout(search_layout)
        
        # Create splitter for resizable sections
        splitter = QSplitter(Qt.Horizontal)
        
        # Rules tree
        self.rules_tree = QTreeWidget()
        self.rules_tree.setHeaderHidden(True)
        self.rules_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.rules_tree.customContextMenuRequested.connect(self._show_context_menu)
        self.rules_tree.currentItemChanged.connect(self._show_rule)
        splitter.addWidget(self.rules_tree)
        
        # Rule content
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        
        # Toolbar for content area
        toolbar = QToolBar()
        
        # Bookmark action
        if self.bookmark_icon.isNull():
            self.bookmark_action = QAction(self.bookmark_action_text, self)
        else:
            self.bookmark_action = QAction(self.bookmark_icon, "Bookmark", self)
        self.bookmark_action.setCheckable(True)
        self.bookmark_action.triggered.connect(self._toggle_bookmark)
        toolbar.addAction(self.bookmark_action)
        
        # Add to Session Notes action
        self.add_to_notes_action = QAction("Add to Session Notes", self)
        self.add_to_notes_action.triggered.connect(self._add_to_session_notes)
        toolbar.addAction(self.add_to_notes_action)
        
        content_layout.addWidget(toolbar)
        
        # Rule title
        self.rule_title = QLabel()
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(12)
        self.rule_title.setFont(title_font)
        content_layout.addWidget(self.rule_title)
        
        # Rule description
        self.rule_text = QTextEdit()
        self.rule_text.setReadOnly(True)
        content_layout.addWidget(self.rule_text)
        
        splitter.addWidget(content_widget)
        
        # Set stretch factors
        splitter.setStretchFactor(0, 1)  # Tree
        splitter.setStretchFactor(1, 2)  # Content
        
        main_layout.addWidget(splitter)
        
        self.setLayout(main_layout)
        self.setMinimumSize(800, 500)
        
        # Populate rules tree
        self._populate_rules_tree()
        
        # Show first rule by default
        if self.rules_tree.topLevelItemCount() > 0:
            first_item = self.rules_tree.topLevelItem(0)
            if first_item.childCount() > 0:
                self.rules_tree.setCurrentItem(first_item.child(0))
    
    def _populate_rules_tree(self):
        """Populate the rules tree with categories and rules"""
        self.rules_tree.clear()
        
        # Get current filter
        category_filter = self.category_filter.currentText()
        search_text = self.search_input.text().lower()
        
        def matches_filter(text):
            """Check if text matches the search filter"""
            if not search_text:
                return True
            return search_text in text.lower()
        
        # Process each category
        for category in sorted(RULES.keys()):
            # Skip if category filter is active
            if category_filter != "All Categories" and category_filter != category:
                continue
                
            # Check if any rule in this category matches the search
            category_matches = matches_filter(category)
            rules_match = False
            
            for rule in RULES[category]:
                rule_text = RULES[category][rule]
                if category_matches or matches_filter(rule) or matches_filter(rule_text):
                    rules_match = True
                    break
                    
            if not rules_match and not category_matches:
                continue
                
            # Add category
            category_item = QTreeWidgetItem([category])
            category_item.setExpanded(True)
            self.rules_tree.addTopLevelItem(category_item)
            
            # Add rules
            for rule in sorted(RULES[category].keys()):
                rule_text = RULES[category][rule]
                if not search_text or matches_filter(rule) or matches_filter(rule_text) or category_matches:
                    rule_item = QTreeWidgetItem([rule])
                    
                    # Mark bookmarked rules with bold font and a special icon
                    if (category, rule) in self.bookmarks:
                        font = rule_item.font(0)
                        font.setBold(True)
                        rule_item.setFont(0, font)
                        
                        # Add star icon or text indicator for bookmarks
                        rule_item.setText(0, f"★ {rule}")
                    
                    category_item.addChild(rule_item)
    
    def _show_rule(self, current, previous):
        """Display the selected rule content"""
        if not current or not current.parent():
            return
            
        category = current.parent().text(0)
        rule_text = current.text(0)
        
        # Remove star prefix if present
        if rule_text.startswith("★ "):
            rule = rule_text[2:]  # Remove the star and space
        else:
            rule = rule_text
        
        if category in RULES and rule in RULES[category]:
            self.current_category = category
            self.current_rule = rule
            
            # Set the title
            self.rule_title.setText(f"{category}: {rule}")
            
            # Set the content
            self.rule_text.setText(RULES[category][rule])
            
            # Update bookmark status
            is_bookmarked = (category, rule) in self.bookmarks
            self.bookmark_action.setChecked(is_bookmarked)
    
    def _filter_rules(self):
        """Filter the rules tree based on search text and category"""
        self._populate_rules_tree()
    
    def _toggle_bookmark(self, checked):
        """Toggle bookmark for the current rule"""
        if not self.current_category or not self.current_rule:
            return
            
        if checked:
            self.bookmarks.add((self.current_category, self.current_rule))
        else:
            self.bookmarks.discard((self.current_category, self.current_rule))
            
        self._populate_rules_tree()
    
    def _show_context_menu(self, position):
        """Show the context menu for a tree item"""
        item = self.rules_tree.itemAt(position)
        if not item:
            return
            
        # Only show for rule items (not categories)
        if item.parent() is None:
            return
            
        menu = QMenu(self)
        
        # Get the rule info
        category = item.parent().text(0)
        rule_text = item.text(0)
        
        # Remove star prefix if present
        if rule_text.startswith("★ "):
            rule = rule_text[2:]  # Remove the star and space
        else:
            rule = rule_text
        
        # Check if this rule is bookmarked
        is_bookmarked = (category, rule) in self.bookmarks
        
        # Add bookmark action
        bookmark_action = menu.addAction(self.bookmark_action_text)
        bookmark_action.setCheckable(True)
        bookmark_action.setChecked(is_bookmarked)
        
        # Add to session notes action
        add_to_notes_action = menu.addAction("Add to Session Notes")
        
        # Show menu and handle selected action
        action = menu.exec(self.rules_tree.mapToGlobal(position))
        
        if action == bookmark_action:
            # Toggle bookmark status
            if is_bookmarked:
                self.bookmarks.remove((category, rule))
            else:
                self.bookmarks.add((category, rule))
            self._populate_rules_tree()
        elif action == add_to_notes_action:
            # Set the current item to ensure rule is loaded
            self.rules_tree.setCurrentItem(item)
            # Add to session notes
            self._add_to_session_notes()
    
    def save_state(self):
        """Save panel state"""
        state = {
            "category_filter": self.category_filter.currentText(),
            "search_text": self.search_input.text(),
            "bookmarks": list(self.bookmarks)
        }
        
        # Save current selection
        if self.current_category and self.current_rule:
            state["current_category"] = self.current_category
            state["current_rule"] = self.current_rule
            
        return state
    
    def restore_state(self, state):
        """Restore panel state"""
        if not state:
            return
            
        # Restore bookmarks
        bookmarks = state.get("bookmarks", [])
        self.bookmarks = set()
        for bookmark in bookmarks:
            if isinstance(bookmark, tuple) and len(bookmark) == 2:
                self.bookmarks.add(bookmark)
        
        # Restore filters
        self.category_filter.setCurrentText(state.get("category_filter", "All Categories"))
        self.search_input.setText(state.get("search_text", ""))
        
        # Repopulate rules with restored filters and bookmarks
        self._populate_rules_tree()
        
        # Restore selection
        if "current_category" in state and "current_rule" in state:
            self._select_rule(state["current_category"], state["current_rule"])
    
    def _select_rule(self, category, rule):
        """Select a specific rule in the tree"""
        for i in range(self.rules_tree.topLevelItemCount()):
            category_item = self.rules_tree.topLevelItem(i)
            if category_item.text(0) == category:
                for j in range(category_item.childCount()):
                    rule_item = category_item.child(j)
                    if rule_item.text(0) == rule:
                        self.rules_tree.setCurrentItem(rule_item)
                        return
    
    def _add_to_session_notes(self):
        """Add the selected rule to the session notes"""
        notes_widget = None
        
        # Get the current selection
        current_item = self.rules_tree.currentItem()
        if not current_item:
            QMessageBox.warning(self, "No Selection", "Please select a rule first")
            return

        # Extract the rule data
        category = current_item.parent().text(0)
        rule = current_item.text(0)
        
        # Format the content for notes
        title = f"Rule: {category} - {rule}"
        content = RULES[category][rule]

        # Method 1: Try to get the session notes panel directly from app_state
        try:
            print("Method 1: Using app_state.get_panel_widget")
            notes_widget = self.app_state.get_panel_widget("Session Notes")
            if notes_widget:
                print(f"Method 1 success: {notes_widget}")
        except Exception as e:
            print(f"Method 1 failed: {str(e)}")
        
        # Method 2: Try using helper method
        if not notes_widget:
            try:
                print("Method 2: Using get_panel helper")
                notes_widget = self.get_panel("Session Notes")
                if notes_widget:
                    print(f"Method 2 success: {notes_widget}")
            except Exception as e:
                print(f"Method 2 failed: {str(e)}")
        
        # Method 3: Try using panel_manager directly
        if not notes_widget:
            try:
                print("Method 3: Using app_state.panel_manager directly")
                if hasattr(self.app_state, 'panel_manager'):
                    panel_dock = self.app_state.panel_manager.get_panel("Session Notes")
                    if panel_dock:
                        notes_widget = panel_dock.widget()
                        print(f"Method 3 success: {notes_widget}")
            except Exception as e:
                print(f"Method 3 failed: {str(e)}")
        
        # Method 4: Try using main window
        if not notes_widget:
            try:
                print("Method 4: Using main window")
                main_window = self.window()
                if hasattr(main_window, 'panel_manager'):
                    panel_dock = main_window.panel_manager.get_panel("Session Notes")
                    if panel_dock:
                        notes_widget = panel_dock.widget()
                        print(f"Method 4 success: {notes_widget}")
            except Exception as e:
                print(f"Method 4 failed: {str(e)}")
        
        # Check if we have the widget and create the note
        if notes_widget:
            print(f"Session notes widget found: {notes_widget}")
            
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
            
            # Try to create the note
            try:
                success = notes_widget._create_note_with_content(
                    title=title,
                    content=content,
                    tags="rules reference"
                )
                
                if success:
                    QMessageBox.information(
                        self, "Note Created", 
                        "The rule has been added to your session notes"
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
        else:
            # No session notes panel found - inform the user
            error_msg = "Session Notes panel is not available. Please open it first."
            print(error_msg)
            QMessageBox.warning(self, "Session Notes Not Available", error_msg)
            
            # Try to show the Session Notes panel if possible
            try:
                if hasattr(self.app_state, 'panel_manager'):
                    self.app_state.panel_manager.show_panel("Session Notes")
                    QMessageBox.information(
                        self, "Panel Opened", 
                        "The Session Notes panel has been opened. Please try again."
                    )
            except Exception as e:
                print(f"Failed to open Session Notes panel: {str(e)}") 