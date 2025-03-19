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
    QWidget, QSplitter, QMenu, QToolBar, QComboBox, QMessageBox
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
        
        # Helper function to check if item should be shown
        def matches_filter(text):
            return search_text in text.lower()
        
        # Add categories and rules
        for category in sorted(RULES.keys()):
            # Skip if category doesn't match filter
            if category_filter != "All Categories" and category != category_filter:
                continue
            
            # Create category item
            category_item = QTreeWidgetItem([category])
            category_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            
            # Add rules under category
            has_visible_children = False
            for rule in sorted(RULES[category].keys()):
                # Skip if rule doesn't match search
                if search_text and not (matches_filter(rule) or matches_filter(RULES[category][rule])):
                    continue
                
                # Create rule item
                if self.bookmark_icon.isNull():
                    rule_text = rule
                    if f"{category}:{rule}" in self.bookmarks:
                        rule_text = "★ " + rule
                    rule_item = QTreeWidgetItem([rule_text])
                else:
                    rule_item = QTreeWidgetItem([rule])
                    if f"{category}:{rule}" in self.bookmarks:
                        rule_item.setIcon(0, self.bookmark_icon)
                
                rule_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                category_item.addChild(rule_item)
                has_visible_children = True
            
            # Only add category if it has visible children or matches search
            if has_visible_children or (search_text and matches_filter(category)):
                self.rules_tree.addTopLevelItem(category_item)
                category_item.setExpanded(bool(search_text))
    
    def _show_rule(self, current, previous):
        """Display the selected rule's content"""
        if not current:
            return
            
        # Get category and rule
        if current.parent():  # Rule item
            category = current.parent().text(0)
            rule = current.text(0)
            self.current_category = category
            self.current_rule = rule
            
            # Update title and content
            self.rule_title.setText(f"{category} - {rule}")
            self.rule_text.setText(RULES[category][rule].strip())
            
            # Update bookmark status
            self.bookmark_action.setChecked(f"{category}:{rule}" in self.bookmarks)
        else:  # Category item
            self.current_category = current.text(0)
            self.current_rule = None
            
            # Show category overview
            self.rule_title.setText(self.current_category)
            rules_list = "\n\n".join(f"• {rule}" for rule in sorted(RULES[self.current_category].keys()))
            self.rule_text.setText(f"Available rules in this category:\n\n{rules_list}")
    
    def _filter_rules(self):
        """Filter the rules tree based on search text and category"""
        self._populate_rules_tree()
    
    def _toggle_bookmark(self, checked):
        """Toggle bookmark for current rule"""
        if self.current_category and self.current_rule:
            bookmark_id = f"{self.current_category}:{self.current_rule}"
            if checked:
                self.bookmarks.add(bookmark_id)
            else:
                self.bookmarks.discard(bookmark_id)
            self._populate_rules_tree()
    
    def _show_context_menu(self, position):
        """Show context menu for rules tree"""
        item = self.rules_tree.itemAt(position)
        if not item:
            return
            
        menu = QMenu()
        
        if item.parent():  # Rule item
            bookmark_action = menu.addAction("Bookmark")
            bookmark_action.setCheckable(True)
            bookmark_id = f"{item.parent().text(0)}:{item.text(0)}"
            bookmark_action.setChecked(bookmark_id in self.bookmarks)
            bookmark_action.triggered.connect(
                lambda checked: self._toggle_bookmark(checked)
            )
        
        menu.exec_(self.rules_tree.mapToGlobal(position))
    
    def save_state(self):
        """Save panel state"""
        return {
            "bookmarks": list(self.bookmarks),
            "category_filter": self.category_filter.currentText(),
            "search_text": self.search_input.text()
        }
    
    def restore_state(self, state):
        """Restore panel state"""
        if not state:
            return
            
        self.bookmarks = set(state.get("bookmarks", []))
        self.category_filter.setCurrentText(state.get("category_filter", "All Categories"))
        self.search_input.setText(state.get("search_text", ""))
        self._populate_rules_tree()

        # Check if any rule is bookmarked and update bookmark button
        if self.rules_tree.topLevelItemCount() > 0:
            for category_item in range(self.rules_tree.topLevelItemCount()):
                rule_item = self.rules_tree.topLevelItem(category_item).child(0)
                if rule_item.text(0) in self.bookmarks:
                    self.bookmark_action.setChecked(True)
                    break
                else:
                    self.bookmark_action.setChecked(False)
    
    def _toggle_bookmark(self, checked):
        """Toggle bookmark for current rule"""
        if self.current_category and self.current_rule:
            bookmark_id = f"{self.current_category}:{self.current_rule}"
            if checked:
                self.bookmarks.add(bookmark_id)
            else:
                self.bookmarks.discard(bookmark_id)
            self._populate_rules_tree()

            # Check if any rule is bookmarked and update bookmark button
            if self.rules_tree.topLevelItemCount() > 0:
                for category_item in range(self.rules_tree.topLevelItemCount()):
                    rule_item = self.rules_tree.topLevelItem(category_item).child(0)
                    if rule_item.text(0) in self.bookmarks:
                        self.bookmark_action.setChecked(True)
                        break
                    else:
                        self.bookmark_action.setChecked(False) 