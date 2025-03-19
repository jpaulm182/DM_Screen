"""
Monster/NPC stat block viewer panel for D&D 5e

Features:
- Quick access to monster/NPC statistics
- Search and filter functionality
- Stat block display with proper formatting
- Quick-add to combat tracker
- Custom monster creation and storage
"""

from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QTextEdit, QLineEdit, QWidget,
    QSpinBox, QComboBox, QDialog, QDialogButtonBox,
    QFormLayout, QTabWidget, QScrollArea, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QIcon

from app.ui.panels.base_panel import BasePanel

# Sample monster data structure
SAMPLE_MONSTER = {
    "name": "Goblin",
    "size": "Small",
    "type": "humanoid (goblinoid)",
    "alignment": "neutral evil",
    "ac": "15 (leather armor, shield)",
    "hp": "7 (2d6)",
    "speed": "30 ft.",
    "stats": {
        "str": 8,
        "dex": 14,
        "con": 10,
        "int": 10,
        "wis": 8,
        "cha": 8
    },
    "saves": [],
    "skills": ["Stealth +6"],
    "senses": ["darkvision 60 ft.", "passive Perception 9"],
    "languages": ["Common", "Goblin"],
    "challenge": "1/4 (50 XP)",
    "features": [
        {
            "name": "Nimble Escape",
            "desc": "The goblin can take the Disengage or Hide action as a bonus action on each of its turns."
        }
    ],
    "actions": [
        {
            "name": "Scimitar",
            "desc": "Melee Weapon Attack: +4 to hit, reach 5 ft., one target. Hit: 5 (1d6 + 2) slashing damage."
        },
        {
            "name": "Shortbow",
            "desc": "Ranged Weapon Attack: +4 to hit, range 80/320 ft., one target. Hit: 5 (1d6 + 2) piercing damage."
        }
    ]
}

class MonsterPanel(BasePanel):
    """Panel for viewing and managing monster/NPC stat blocks"""
    
    # Signal emitted when adding monster to combat
    add_to_combat = Signal(dict)  # Emits monster data
    
    def __init__(self, app_state):
        self.monsters = {"Goblin": SAMPLE_MONSTER}  # Will be replaced with proper storage
        self.current_monster = None
        super().__init__(app_state, "Monster Reference")
    
    def _setup_ui(self):
        """Set up the monster panel UI"""
        main_layout = QVBoxLayout()
        
        # Search and filter area
        search_layout = QHBoxLayout()
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search monsters...")
        self.search_input.textChanged.connect(self._filter_monsters)
        search_layout.addWidget(self.search_input)
        
        self.cr_filter = QComboBox()
        self.cr_filter.addItem("All CRs")
        self.cr_filter.addItems(["0", "1/8", "1/4", "1/2"] + [str(i) for i in range(1, 31)])
        self.cr_filter.currentTextChanged.connect(self._filter_monsters)
        search_layout.addWidget(self.cr_filter)
        
        self.type_filter = QComboBox()
        self.type_filter.addItem("All Types")
        self.type_filter.addItems([
            "Aberration", "Beast", "Celestial", "Construct",
            "Dragon", "Elemental", "Fey", "Fiend", "Giant",
            "Humanoid", "Monstrosity", "Ooze", "Plant", "Undead"
        ])
        self.type_filter.currentTextChanged.connect(self._filter_monsters)
        search_layout.addWidget(self.type_filter)
        
        main_layout.addLayout(search_layout)
        
        # Split view
        content_layout = QHBoxLayout()
        
        # Monster list
        list_layout = QVBoxLayout()
        self.monster_list = QListWidget()
        self.monster_list.currentItemChanged.connect(self._show_monster)
        list_layout.addWidget(self.monster_list)
        
        # Add monster buttons
        button_layout = QHBoxLayout()
        
        add_to_combat_btn = QPushButton("Add to Combat")
        add_to_combat_btn.clicked.connect(self._add_to_combat)
        button_layout.addWidget(add_to_combat_btn)
        
        create_monster_btn = QPushButton("Create Monster")
        create_monster_btn.clicked.connect(self._create_monster)
        button_layout.addWidget(create_monster_btn)
        
        list_layout.addLayout(button_layout)
        content_layout.addLayout(list_layout, stretch=1)
        
        # Stat block display
        self.stat_block = QTextEdit()
        self.stat_block.setReadOnly(True)
        content_layout.addWidget(self.stat_block, stretch=2)
        
        main_layout.addLayout(content_layout)
        
        # Set up the panel
        self.setLayout(main_layout)
        self.setMinimumSize(800, 600)
        
        # Populate initial list
        self._populate_monster_list()
    
    def _populate_monster_list(self):
        """Populate the monster list based on current filters"""
        self.monster_list.clear()
        
        search_text = self.search_input.text().lower()
        cr_filter = self.cr_filter.currentText()
        type_filter = self.type_filter.currentText()
        
        for name, data in sorted(self.monsters.items()):
            # Apply filters
            if search_text and search_text not in name.lower():
                continue
            
            if cr_filter != "All CRs" and data["challenge"].split()[0] != cr_filter:
                continue
            
            if type_filter != "All Types" and type_filter.lower() not in data["type"].lower():
                continue
            
            self.monster_list.addItem(name)
    
    def _show_monster(self, current, previous):
        """Display the selected monster's stat block"""
        if not current:
            self.current_monster = None
            self.stat_block.clear()
            return
        
        name = current.text()
        monster = self.monsters[name]
        self.current_monster = monster
        
        # Format stat block
        html = f"""
        <div style='font-family: Arial, sans-serif;'>
            <h2>{monster['name']}</h2>
            <p><i>{monster['size']} {monster['type']}, {monster['alignment']}</i></p>
            <hr>
            <p><b>Armor Class</b> {monster['ac']}</p>
            <p><b>Hit Points</b> {monster['hp']}</p>
            <p><b>Speed</b> {monster['speed']}</p>
            <hr>
            <table width='100%'>
                <tr>
                    <th>STR</th>
                    <th>DEX</th>
                    <th>CON</th>
                    <th>INT</th>
                    <th>WIS</th>
                    <th>CHA</th>
                </tr>
                <tr>
                    <td>{monster['stats']['str']} ({self._get_modifier(monster['stats']['str'])})</td>
                    <td>{monster['stats']['dex']} ({self._get_modifier(monster['stats']['dex'])})</td>
                    <td>{monster['stats']['con']} ({self._get_modifier(monster['stats']['con'])})</td>
                    <td>{monster['stats']['int']} ({self._get_modifier(monster['stats']['int'])})</td>
                    <td>{monster['stats']['wis']} ({self._get_modifier(monster['stats']['wis'])})</td>
                    <td>{monster['stats']['cha']} ({self._get_modifier(monster['stats']['cha'])})</td>
                </tr>
            </table>
            <hr>
        """
        
        if monster['saves']:
            html += f"<p><b>Saving Throws</b> {', '.join(monster['saves'])}</p>"
        
        if monster['skills']:
            html += f"<p><b>Skills</b> {', '.join(monster['skills'])}</p>"
        
        html += f"""
            <p><b>Senses</b> {', '.join(monster['senses'])}</p>
            <p><b>Languages</b> {', '.join(monster['languages'])}</p>
            <p><b>Challenge</b> {monster['challenge']}</p>
            <hr>
        """
        
        # Features
        for feature in monster['features']:
            html += f"<p><b>{feature['name']}.</b> {feature['desc']}</p>"
        
        if monster['actions']:
            html += "<h3>Actions</h3>"
            for action in monster['actions']:
                html += f"<p><b>{action['name']}.</b> {action['desc']}</p>"
        
        html += "</div>"
        self.stat_block.setHtml(html)
    
    def _get_modifier(self, score):
        """Get the ability score modifier"""
        modifier = (score - 10) // 2
        return f"+{modifier}" if modifier >= 0 else str(modifier)
    
    def _filter_monsters(self):
        """Filter the monster list based on search text and filters"""
        self._populate_monster_list()
    
    def _add_to_combat(self):
        """Add the current monster to the combat tracker"""
        if self.current_monster:
            print("Adding monster to combat:", self.current_monster["name"])  # Debug print
            self.add_to_combat.emit(self.current_monster)
            print("Signal emitted")  # Debug print
    
    def _create_monster(self):
        """Open the monster creation dialog"""
        # TODO: Implement monster creation dialog
        pass
    
    def save_state(self):
        """Save panel state"""
        return {
            "search_text": self.search_input.text(),
            "cr_filter": self.cr_filter.currentText(),
            "type_filter": self.type_filter.currentText()
        }
    
    def restore_state(self, state):
        """Restore panel state"""
        if not state:
            return
        
        self.search_input.setText(state.get("search_text", ""))
        self.cr_filter.setCurrentText(state.get("cr_filter", "All CRs"))
        self.type_filter.setCurrentText(state.get("type_filter", "All Types"))
        self._populate_monster_list() 