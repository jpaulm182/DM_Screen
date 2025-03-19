"""
Spell Reference Panel

Allows looking up and filtering spells, as well as tracking spell slots for casters.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QComboBox, QPushButton, QScrollArea, QTextEdit, QSplitter,
    QTableWidget, QTableWidgetItem, QHeaderView, QTabWidget,
    QFormLayout, QSpinBox, QGroupBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from app.ui.panels.base_panel import BasePanel


class SpellReferencePanel(BasePanel):
    """
    Panel for looking up spells and tracking spell slots
    """
    
    def __init__(self, app_state, panel_id=None):
        """Initialize the spell reference panel"""
        # Initialize data before calling the parent constructor
        self.spells = []
        self.filtered_spells = []
        self.current_spell = None
        
        # Call parent constructor which will call _setup_ui
        super().__init__(app_state, "Spell Reference")
        
        # Load spells from database
        self._load_spells()
    
    def _setup_ui(self):
        """Set up the panel UI components"""
        # Main layout - override the BasePanel layout
        if self.layout():
            # Delete existing layout if present
            current_layout = self.layout()
            while current_layout.count():
                item = current_layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.deleteLater()
            self.setLayout(None)
        
        # Create a new layout
        main_layout = QVBoxLayout()
        
        # Create tabbed interface
        self.tabs = QTabWidget()
        self.reference_tab = QWidget()
        self.tracker_tab = QWidget()
        
        self.tabs.addTab(self.reference_tab, "Spell Reference")
        self.tabs.addTab(self.tracker_tab, "Spell Tracker")
        
        main_layout.addWidget(self.tabs)
        
        # Set the new layout
        self.setLayout(main_layout)
        
        # Setup reference tab
        self._setup_reference_tab()
        
        # Setup tracker tab
        self._setup_tracker_tab()
    
    def _setup_reference_tab(self):
        """Set up the spell reference tab"""
        layout = QVBoxLayout(self.reference_tab)
        
        # Filter area
        filter_layout = QHBoxLayout()
        
        # Search box
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search spells...")
        self.search_input.textChanged.connect(self._filter_spells)
        filter_layout.addWidget(self.search_input)
        
        # Level filter
        self.level_filter = QComboBox()
        self.level_filter.addItem("All Levels", -1)
        for i in range(10):
            level_name = "Cantrip" if i == 0 else f"Level {i}"
            self.level_filter.addItem(level_name, i)
        self.level_filter.currentIndexChanged.connect(self._filter_spells)
        filter_layout.addWidget(self.level_filter)
        
        # School filter
        self.school_filter = QComboBox()
        self.school_filter.addItem("All Schools", "")
        for school in ["Abjuration", "Conjuration", "Divination", "Enchantment", 
                      "Evocation", "Illusion", "Necromancy", "Transmutation"]:
            self.school_filter.addItem(school, school)
        self.school_filter.currentIndexChanged.connect(self._filter_spells)
        filter_layout.addWidget(self.school_filter)
        
        # Class filter
        self.class_filter = QComboBox()
        self.class_filter.addItem("All Classes", "")
        for cls in ["Bard", "Cleric", "Druid", "Paladin", "Ranger", 
                   "Sorcerer", "Warlock", "Wizard", "Artificer"]:
            self.class_filter.addItem(cls, cls)
        self.class_filter.currentIndexChanged.connect(self._filter_spells)
        filter_layout.addWidget(self.class_filter)
        
        layout.addLayout(filter_layout)
        
        # Splitter for table and details
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Spell table
        self.spell_table = QTableWidget(0, 4)
        self.spell_table.setHorizontalHeaderLabels(["Name", "Level", "School", "Casting Time"])
        self.spell_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.spell_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.spell_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.spell_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.spell_table.verticalHeader().setVisible(False)
        self.spell_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.spell_table.setSelectionMode(QTableWidget.SingleSelection)
        self.spell_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.spell_table.cellClicked.connect(self._show_spell_details)
        splitter.addWidget(self.spell_table)
        
        # Spell details area
        self.details_widget = QWidget()
        details_layout = QVBoxLayout(self.details_widget)
        
        self.spell_name = QLabel()
        font = QFont()
        font.setBold(True)
        font.setPointSize(14)
        self.spell_name.setFont(font)
        details_layout.addWidget(self.spell_name)
        
        # Spell properties
        props_layout = QHBoxLayout()
        
        self.spell_level_school = QLabel()
        props_layout.addWidget(self.spell_level_school)
        
        self.spell_casting_time = QLabel()
        props_layout.addWidget(self.spell_casting_time)
        
        self.spell_range = QLabel()
        props_layout.addWidget(self.spell_range)
        
        self.spell_components = QLabel()
        props_layout.addWidget(self.spell_components)
        
        self.spell_duration = QLabel()
        props_layout.addWidget(self.spell_duration)
        
        details_layout.addLayout(props_layout)
        
        # Spell description
        self.spell_description = QTextEdit()
        self.spell_description.setReadOnly(True)
        details_layout.addWidget(self.spell_description)
        
        # Add favorite button
        self.favorite_button = QPushButton("Add to Favorites")
        self.favorite_button.clicked.connect(self._toggle_favorite)
        details_layout.addWidget(self.favorite_button)
        
        splitter.addWidget(self.details_widget)
        
        # Set initial splitter sizes
        splitter.setSizes([300, 400])
        
        layout.addWidget(splitter)
    
    def _setup_tracker_tab(self):
        """Set up the spell tracker tab for spell slot management"""
        layout = QVBoxLayout(self.tracker_tab)
        
        # Spellcaster profiles
        profiles_layout = QHBoxLayout()
        
        # Spellcaster profile selection
        self.caster_profile = QComboBox()
        self.caster_profile.addItem("Create New Profile")
        profiles_layout.addWidget(QLabel("Spellcaster:"))
        profiles_layout.addWidget(self.caster_profile)
        
        # Add/Edit/Delete profile buttons
        self.add_profile_btn = QPushButton("Add")
        self.add_profile_btn.clicked.connect(self._add_caster_profile)
        profiles_layout.addWidget(self.add_profile_btn)
        
        self.edit_profile_btn = QPushButton("Edit")
        self.edit_profile_btn.clicked.connect(self._edit_caster_profile)
        profiles_layout.addWidget(self.edit_profile_btn)
        
        self.delete_profile_btn = QPushButton("Delete")
        self.delete_profile_btn.clicked.connect(self._delete_caster_profile)
        profiles_layout.addWidget(self.delete_profile_btn)
        
        layout.addLayout(profiles_layout)
        
        # Spell slot tracker
        spell_slots_group = QGroupBox("Spell Slots")
        slots_layout = QFormLayout(spell_slots_group)
        
        self.spell_slots = []
        for i in range(1, 10):
            row_layout = QHBoxLayout()
            
            # Current slots
            current_slots = QSpinBox()
            current_slots.setMinimum(0)
            current_slots.setMaximum(5)
            current_slots.valueChanged.connect(self._slot_value_changed)
            
            # Max slots
            max_slots = QSpinBox()
            max_slots.setMinimum(0)
            max_slots.setMaximum(5)
            max_slots.valueChanged.connect(self._max_slot_value_changed)
            
            # Use/restore buttons
            use_btn = QPushButton("Use")
            use_btn.clicked.connect(lambda checked, level=i: self._use_spell_slot(level))
            
            restore_btn = QPushButton("Restore")
            restore_btn.clicked.connect(lambda checked, level=i: self._restore_spell_slot(level))
            
            row_layout.addWidget(current_slots)
            row_layout.addWidget(QLabel("/"))
            row_layout.addWidget(max_slots)
            row_layout.addWidget(use_btn)
            row_layout.addWidget(restore_btn)
            
            slots_layout.addRow(f"Level {i}:", row_layout)
            self.spell_slots.append((current_slots, max_slots, use_btn, restore_btn))
        
        layout.addWidget(spell_slots_group)
        
        # Rest buttons
        rest_layout = QHBoxLayout()
        
        short_rest_btn = QPushButton("Short Rest")
        short_rest_btn.clicked.connect(self._short_rest)
        rest_layout.addWidget(short_rest_btn)
        
        long_rest_btn = QPushButton("Long Rest")
        long_rest_btn.clicked.connect(self._long_rest)
        rest_layout.addWidget(long_rest_btn)
        
        layout.addLayout(rest_layout)
        
        # Prepared spells list
        prepared_group = QGroupBox("Prepared Spells")
        prepared_layout = QVBoxLayout(prepared_group)
        
        self.prepared_spells_table = QTableWidget(0, 3)
        self.prepared_spells_table.setHorizontalHeaderLabels(["Name", "Level", "School"])
        self.prepared_spells_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.prepared_spells_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.prepared_spells_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.prepared_spells_table.verticalHeader().setVisible(False)
        prepared_layout.addWidget(self.prepared_spells_table)
        
        # Add/remove prepared spell buttons
        prepared_buttons_layout = QHBoxLayout()
        
        add_prepared_btn = QPushButton("Add Spell")
        add_prepared_btn.clicked.connect(self._add_prepared_spell)
        prepared_buttons_layout.addWidget(add_prepared_btn)
        
        remove_prepared_btn = QPushButton("Remove Spell")
        remove_prepared_btn.clicked.connect(self._remove_prepared_spell)
        prepared_buttons_layout.addWidget(remove_prepared_btn)
        
        prepared_layout.addLayout(prepared_buttons_layout)
        
        layout.addWidget(prepared_group)
    
    def _load_spells(self):
        """Load spells from the database or use mock data if DB not available"""
        # Use mock data for now since db isn't implemented
        self.spells = self._get_mock_spells()
        self.filtered_spells = self.spells.copy()
        self._update_spell_table()
        
    def _get_mock_spells(self):
        """Return mock spell data for testing"""
        return [
            {
                'id': 1,
                'name': 'Fireball',
                'level': 3,
                'school': 'Evocation',
                'casting_time': '1 action',
                'range': '150 feet',
                'components': 'V, S, M (a tiny ball of bat guano and sulfur)',
                'duration': 'Instantaneous',
                'description': 'A bright streak flashes from your pointing finger to a point you choose within range and then blossoms with a low roar into an explosion of flame. Each creature in a 20-foot-radius sphere centered on that point must make a Dexterity saving throw. A target takes 8d6 fire damage on a failed save, or half as much damage on a successful one. The fire spreads around corners. It ignites flammable objects in the area that aren\'t being worn or carried.',
                'class': 'Sorcerer, Wizard'
            },
            {
                'id': 2,
                'name': 'Cure Wounds',
                'level': 1,
                'school': 'Evocation',
                'casting_time': '1 action',
                'range': 'Touch',
                'components': 'V, S',
                'duration': 'Instantaneous',
                'description': 'A creature you touch regains a number of hit points equal to 1d8 + your spellcasting ability modifier. This spell has no effect on undead or constructs.',
                'class': 'Bard, Cleric, Druid, Paladin, Ranger'
            },
            {
                'id': 3,
                'name': 'Mage Hand',
                'level': 0,
                'school': 'Conjuration',
                'casting_time': '1 action',
                'range': '30 feet',
                'components': 'V, S',
                'duration': '1 minute',
                'description': 'A spectral, floating hand appears at a point you choose within range. The hand lasts for the duration or until you dismiss it as an action. The hand vanishes if it is ever more than 30 feet away from you or if you cast this spell again.\n\nYou can use your action to control the hand. You can use the hand to manipulate an object, open an unlocked door or container, stow or retrieve an item from an open container, or pour the contents out of a vial. You can move the hand up to 30 feet each time you use it.\n\nThe hand can\'t attack, activate magic items, or carry more than 10 pounds.',
                'class': 'Bard, Sorcerer, Warlock, Wizard'
            },
            {
                'id': 4,
                'name': 'Healing Word',
                'level': 1,
                'school': 'Evocation',
                'casting_time': '1 bonus action',
                'range': '60 feet',
                'components': 'V',
                'duration': 'Instantaneous',
                'description': 'A creature of your choice that you can see within range regains hit points equal to 1d4 + your spellcasting ability modifier. This spell has no effect on undead or constructs.',
                'class': 'Bard, Cleric, Druid'
            },
            {
                'id': 5,
                'name': 'Shield',
                'level': 1,
                'school': 'Abjuration',
                'casting_time': '1 reaction',
                'range': 'Self',
                'components': 'V, S',
                'duration': '1 round',
                'description': 'An invisible barrier of magical force appears and protects you. Until the start of your next turn, you have a +5 bonus to AC, including against the triggering attack, and you take no damage from magic missile.',
                'class': 'Sorcerer, Wizard'
            },
            {
                'id': 6,
                'name': 'Detect Magic',
                'level': 1,
                'school': 'Divination',
                'casting_time': '1 action',
                'range': 'Self',
                'components': 'V, S',
                'duration': 'Concentration, up to 10 minutes',
                'description': 'For the duration, you sense the presence of magic within 30 feet of you. If you sense magic in this way, you can use your action to see a faint aura around any visible creature or object in the area that bears magic, and you learn its school of magic, if any.\n\nThe spell can penetrate most barriers, but it is blocked by 1 foot of stone, 1 inch of common metal, a thin sheet of lead, or 3 feet of wood or dirt.',
                'class': 'Bard, Cleric, Druid, Paladin, Ranger, Sorcerer, Wizard'
            },
            {
                'id': 7,
                'name': 'Magic Missile',
                'level': 1,
                'school': 'Evocation',
                'casting_time': '1 action',
                'range': '120 feet',
                'components': 'V, S',
                'duration': 'Instantaneous',
                'description': 'You create three glowing darts of magical force. Each dart hits a creature of your choice that you can see within range. A dart deals 1d4 + 1 force damage to its target. The darts all strike simultaneously, and you can direct them to hit one creature or several.',
                'class': 'Sorcerer, Wizard'
            },
            {
                'id': 8,
                'name': 'Counterspell',
                'level': 3,
                'school': 'Abjuration',
                'casting_time': '1 reaction',
                'range': '60 feet',
                'components': 'S',
                'duration': 'Instantaneous',
                'description': 'You attempt to interrupt a creature in the process of casting a spell. If the creature is casting a spell of 3rd level or lower, its spell fails and has no effect. If it is casting a spell of 4th level or higher, make an ability check using your spellcasting ability. The DC equals 10 + the spell\'s level. On a success, the creature\'s spell fails and has no effect.',
                'class': 'Sorcerer, Warlock, Wizard'
            },
            {
                'id': 9,
                'name': 'Darkness',
                'level': 2,
                'school': 'Evocation',
                'casting_time': '1 action',
                'range': '60 feet',
                'components': 'V, M (bat fur and a drop of pitch or piece of coal)',
                'duration': 'Concentration, up to 10 minutes',
                'description': 'Magical darkness spreads from a point you choose within range to fill a 15-foot-radius sphere for the duration. The darkness spreads around corners. A creature with darkvision can\'t see through this darkness, and nonmagical light can\'t illuminate it.\n\nIf the point you choose is on an object you are holding or one that isn\'t being worn or carried, the darkness emanates from the object and moves with it. Completely covering the source of the darkness with an opaque object, such as a bowl or a helm, blocks the darkness.\n\nIf any of this spell\'s area overlaps with an area of light created by a spell of 2nd level or lower, the spell that created the light is dispelled.',
                'class': 'Sorcerer, Warlock, Wizard'
            },
            {
                'id': 10,
                'name': 'Misty Step',
                'level': 2,
                'school': 'Conjuration',
                'casting_time': '1 bonus action',
                'range': 'Self',
                'components': 'V',
                'duration': 'Instantaneous',
                'description': 'Briefly surrounded by silvery mist, you teleport up to 30 feet to an unoccupied space that you can see.',
                'class': 'Sorcerer, Warlock, Wizard'
            }
        ]
    
    def _update_spell_table(self):
        """Update the spell table with current filtered spells"""
        self.spell_table.setRowCount(0)
        
        for idx, spell in enumerate(self.filtered_spells):
            self.spell_table.insertRow(idx)
            
            name_item = QTableWidgetItem(spell['name'])
            self.spell_table.setItem(idx, 0, name_item)
            
            level_text = "Cantrip" if spell['level'] == 0 else str(spell['level'])
            level_item = QTableWidgetItem(level_text)
            self.spell_table.setItem(idx, 1, level_item)
            
            school_item = QTableWidgetItem(spell['school'])
            self.spell_table.setItem(idx, 2, school_item)
            
            casting_time_item = QTableWidgetItem(spell['casting_time'])
            self.spell_table.setItem(idx, 3, casting_time_item)
    
    def _filter_spells(self):
        """Filter spells based on search, level, school, and class"""
        search_text = self.search_input.text().lower()
        level = self.level_filter.currentData()
        school = self.school_filter.currentData()
        class_name = self.class_filter.currentData()
        
        self.filtered_spells = []
        
        for spell in self.spells:
            # Check if spell matches all criteria
            if search_text and search_text not in spell['name'].lower():
                continue
                
            if level != -1 and spell['level'] != level:
                continue
                
            if school and spell['school'] != school:
                continue
                
            if class_name and class_name.lower() not in spell['class'].lower():
                continue
                
            self.filtered_spells.append(spell)
        
        self._update_spell_table()
    
    def _show_spell_details(self, row, column):
        """Show details for the selected spell"""
        if row < 0 or row >= len(self.filtered_spells):
            return
            
        spell = self.filtered_spells[row]
        self.current_spell = spell
        
        # Update UI with spell details
        self.spell_name.setText(spell['name'])
        
        level_text = "Cantrip" if spell['level'] == 0 else f"{spell['level']}-level"
        self.spell_level_school.setText(f"{level_text} {spell['school']}")
        
        self.spell_casting_time.setText(f"Casting Time: {spell['casting_time']}")
        self.spell_range.setText(f"Range: {spell['range']}")
        self.spell_components.setText(f"Components: {spell['components']}")
        self.spell_duration.setText(f"Duration: {spell['duration']}")
        
        self.spell_description.setText(spell['description'])
        
        # Check if spell is in favorites
        is_favorite = self._is_spell_favorite(spell['id'])
        self.favorite_button.setText("Remove from Favorites" if is_favorite else "Add to Favorites")
    
    def _toggle_favorite(self):
        """Toggle the favorite status of the current spell"""
        if not self.current_spell:
            return
            
        spell_id = self.current_spell['id']
        is_favorite = self._is_spell_favorite(spell_id)
        
        if is_favorite:
            # Remove from favorites
            self._remove_spell_favorite(spell_id)
            self.favorite_button.setText("Add to Favorites")
        else:
            # Add to favorites
            self._add_spell_favorite(spell_id)
            self.favorite_button.setText("Remove from Favorites")
    
    def _is_spell_favorite(self, spell_id):
        """Check if a spell is in the favorites"""
        # TODO: Implement check from database
        return False
    
    def _add_spell_favorite(self, spell_id):
        """Add a spell to favorites"""
        # TODO: Implement add to favorites in database
        pass
    
    def _remove_spell_favorite(self, spell_id):
        """Remove a spell from favorites"""
        # TODO: Implement remove from favorites in database
        pass
    
    def _add_caster_profile(self):
        """Add a new spellcaster profile"""
        # TODO: Implement add caster profile
        pass
    
    def _edit_caster_profile(self):
        """Edit the selected spellcaster profile"""
        # TODO: Implement edit caster profile
        pass
    
    def _delete_caster_profile(self):
        """Delete the selected spellcaster profile"""
        # TODO: Implement delete caster profile
        pass
    
    def _slot_value_changed(self, value):
        """Handle spell slot value change"""
        # TODO: Implement slot value change save
        pass
    
    def _max_slot_value_changed(self, value):
        """Handle max spell slot value change"""
        # TODO: Implement max slot value change save
        pass
    
    def _use_spell_slot(self, level):
        """Use a spell slot of the specified level"""
        current, max_slots, _, _ = self.spell_slots[level-1]
        if current.value() > 0:
            current.setValue(current.value() - 1)
    
    def _restore_spell_slot(self, level):
        """Restore a spell slot of the specified level"""
        current, max_slots, _, _ = self.spell_slots[level-1]
        if current.value() < max_slots.value():
            current.setValue(current.value() + 1)
    
    def _short_rest(self):
        """Handle short rest spell slot restoration"""
        # TODO: Implement short rest recovery based on class
        pass
    
    def _long_rest(self):
        """Handle long rest spell slot restoration"""
        # Restore all spell slots to max
        for current, max_slots, _, _ in self.spell_slots:
            current.setValue(max_slots.value())
    
    def _add_prepared_spell(self):
        """Add a spell to the prepared spells list"""
        # TODO: Implement add prepared spell
        pass
    
    def _remove_prepared_spell(self):
        """Remove a spell from the prepared spells list"""
        # TODO: Implement remove prepared spell
        pass 