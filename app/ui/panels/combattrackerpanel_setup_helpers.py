# Helpers for CombatTrackerPanel (_setup_)

    def _setup_delegates(self):
        """Set up custom delegates for the initiative table"""
        # Set custom delegates for initiative and HP columns
        self.init_delegate = InitiativeUpdateDelegate(self)
        self.init_delegate.initChanged.connect(self._initiative_changed)
        self.initiative_table.setItemDelegateForColumn(1, self.init_delegate)
        
        self.hp_delegate = HPUpdateDelegate(self)
        self.hp_delegate.hpChanged.connect(self._hp_changed)
        self.initiative_table.setItemDelegateForColumn(2, self.hp_delegate)
        
        # Set delegate for highlighting current turn
        self.current_turn_delegate = CurrentTurnDelegate()
        for col in range(8):  # Apply to all columns (including the new Max HP column)
            self.initiative_table.setItemDelegateForColumn(col, self.current_turn_delegate)
        
        # When cell content changes, update internal data
        self.initiative_table.cellChanged.connect(self._handle_cell_changed)

    def _setup_ui(self):
        """Setup the UI components"""
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Create a splitter to allow manual resizing between the table and log
        self.main_splitter = QSplitter(Qt.Vertical)
        
        # --- Initiative Table Area ---
        table_container = QWidget()
        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create initiative table
        self.initiative_table = QTableWidget(0, 8)  # Changed to 8 columns
        self.initiative_table.setHorizontalHeaderLabels(["Name", "Initiative", "HP", "Max HP", "AC", "Status", "Conc.", "Type"])
        self.initiative_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.initiative_table.setSelectionMode(QTableWidget.ExtendedSelection)
        # Allow editing via double‑click or pressing a key, but NOT on single
        # mouse right‑clicks so the context menu can appear reliably.
        self.initiative_table.setEditTriggers(
            QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed
        )
        
        # Set column widths
        self.initiative_table.setColumnWidth(0, 150)  # Name
        self.initiative_table.setColumnWidth(1, 80)   # Initiative
        self.initiative_table.setColumnWidth(2, 80)   # HP
        self.initiative_table.setColumnWidth(3, 80)   # Max HP
        self.initiative_table.setColumnWidth(4, 60)   # AC
        self.initiative_table.setColumnWidth(5, 120)  # Status
        self.initiative_table.setColumnWidth(6, 60)   # Conc
        self.initiative_table.setColumnWidth(7, 100)  # Type
        
        # Set header behavior
        header = self.initiative_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)       # Name stretches
        header.setSectionResizeMode(5, QHeaderView.Stretch)       # Status stretches
        header.setSectionResizeMode(1, QHeaderView.Fixed)         # Initiative fixed
        header.setSectionResizeMode(2, QHeaderView.Fixed)         # HP fixed
        header.setSectionResizeMode(3, QHeaderView.Fixed)         # Max HP fixed  
        header.setSectionResizeMode(4, QHeaderView.Fixed)         # AC fixed
        header.setSectionResizeMode(6, QHeaderView.Fixed)         # Conc fixed
        header.setSectionResizeMode(7, QHeaderView.Fixed)         # Type fixed
        
        # Connect context menu
        self.initiative_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.initiative_table.customContextMenuRequested.connect(self._show_context_menu)
        
        # Connect change signals
        self.initiative_table.cellChanged.connect(self._handle_cell_changed)
        
        # Set up the custom delegates
        self._setup_delegates()
        
        # --- Control Area with three rows: Round/Timer, Buttons, Add Combatant ---
        control_layout = self._setup_control_area()
        table_layout.addLayout(control_layout)
        
        # Add add combatant controls if needed
        add_combatant_layout = self._setup_add_combatant_controls()
        table_layout.addLayout(add_combatant_layout)
        
        # Add table to layout
        table_layout.addWidget(self.initiative_table)
        
        # Add table to main splitter
        self.main_splitter.addWidget(table_container)
        
        # --- Combat Log Area (NEW) ---
        self.log_container = QWidget()
        log_layout = QVBoxLayout(self.log_container)
        log_layout.setContentsMargins(0, 0, 0, 0)
        
        # Header for combat log
        log_header = QHBoxLayout()
        log_header.addWidget(QLabel("<b>Combat Log & Results</b>"))
        
        # Add clear button for log
        clear_log_btn = QPushButton("Clear Log")
        clear_log_btn.setMaximumWidth(100)
        clear_log_btn.clicked.connect(self._clear_combat_log)
        log_header.addWidget(clear_log_btn)
        
        log_layout.addLayout(log_header)
        
        # Create text area for combat log
        self.combat_log_text = QTextEdit()
        self.combat_log_text.setReadOnly(True)
        self.combat_log_text.setMinimumHeight(100)
        self.combat_log_text.setStyleSheet("""
            QTextEdit { 
                background-color: white;
                color: #000000;
                font-family: Arial, sans-serif;
                font-size: 12px;
            }
        """)
        log_layout.addWidget(self.combat_log_text)
        
        # Add log container to splitter
        self.main_splitter.addWidget(self.log_container)
        
        # Set reasonable initial sizes
        self.main_splitter.setSizes([600, 200])
        
        # Add the splitter to the main layout
        layout.addWidget(self.main_splitter)
        
        self.setLayout(layout)
        
        # Initialize UI components
        self.initiative_table.setMinimumHeight(200)
        
        # Connect signals
        self.initiative_table.itemSelectionChanged.connect(self._on_selection_changed)
        
        # Create keyboard shortcuts
        QAction("Next Turn", self, triggered=self._next_turn, shortcut=QKeySequence("N")).setShortcutContext(Qt.WidgetWithChildrenShortcut)
        self.addAction(QAction("Next Turn", self, triggered=self._next_turn, shortcut=QKeySequence("N")))
        
        # Set table stretch 
        self.main_splitter.setStretchFactor(0, 3)  # Combat tracker gets 3 parts
        self.main_splitter.setStretchFactor(1, 2)  # Details gets 2 parts
        
        # Initialize the table
        self._update_highlight()

    def _setup_control_area(self):
        """Set up the combat control area"""
        control_layout = QHBoxLayout()
        
        # Combat info group
        combat_info = QGroupBox("Combat Info")
        info_layout = QHBoxLayout()
        
        # Round counter
        round_layout = QVBoxLayout()
        round_layout.addWidget(QLabel("Round:"))
        self.round_spin = QSpinBox()
        self.round_spin.setMinimum(1)
        self.round_spin.setValue(self.current_round)
        self.round_spin.valueChanged.connect(self._round_changed)
        round_layout.addWidget(self.round_spin)
        info_layout.addLayout(round_layout)
        
        # Combat duration
        duration_layout = QVBoxLayout()
        duration_layout.addWidget(QLabel("Duration:"))
        duration_widget = QWidget()
        duration_inner = QHBoxLayout()
        
        self.timer_label = QLabel("00:00:00")
        duration_inner.addWidget(self.timer_label)
        
        self.timer_button = QPushButton("Start")
        self.timer_button.clicked.connect(self._toggle_timer)
        duration_inner.addWidget(self.timer_button)
        
        duration_widget.setLayout(duration_inner)
        duration_layout.addWidget(duration_widget)
        info_layout.addLayout(duration_layout)
        
        # In-game time
        game_time_layout = QVBoxLayout()
        game_time_layout.addWidget(QLabel("In-Game Time:"))
        self.game_time_label = QLabel("0 rounds (0 minutes)")
        game_time_layout.addWidget(self.game_time_label)
        info_layout.addLayout(game_time_layout)
        
        combat_info.setLayout(info_layout)
        control_layout.addWidget(combat_info)
        
        control_layout.addStretch(1)
        
        # Next combatant button (previously Next Turn)
        self.next_turn_button = QPushButton("Next Combatant")
        self.next_turn_button.clicked.connect(self._next_turn)
        control_layout.addWidget(self.next_turn_button)

        # Add Fast Resolve button
        self.fast_resolve_button = QPushButton("Fast Resolve")
        self.fast_resolve_button.setToolTip("Resolve the current combat using AI (Experimental)")
        self.fast_resolve_button.clicked.connect(self._fast_resolve_combat)
        control_layout.addWidget(self.fast_resolve_button)

        # Reset Combat button
        self.reset_button = QPushButton("Reset Combat")
        self.reset_button.clicked.connect(self._reset_combat)
        control_layout.addWidget(self.reset_button)
        
        # Restart Combat button
        self.restart_button = QPushButton("Restart Combat")
        self.restart_button.clicked.connect(self._restart_combat)
        control_layout.addWidget(self.restart_button)
        
        return control_layout

    def _setup_add_combatant_controls(self):
        """Set up the controls for adding new combatants"""
        add_layout = QHBoxLayout()
        
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Name")
        add_layout.addWidget(self.name_input)
        
        init_layout = QHBoxLayout()
        self.initiative_input = QSpinBox()
        self.initiative_input.setRange(-20, 30)  # Allow for negative initiative
        self.initiative_input.setPrefix("Init: ")
        init_layout.addWidget(self.initiative_input)
        
        # Add quick roll button
        roll_init_button = QPushButton("🎲")
        roll_init_button.setToolTip("Roll initiative (1d20)")
        roll_init_button.clicked.connect(self._roll_initiative)
        roll_init_button.setMaximumWidth(30)
        init_layout.addWidget(roll_init_button)
        
        init_widget = QWidget()
        init_widget.setLayout(init_layout)
        add_layout.addWidget(init_widget)
        
        self.hp_input = QSpinBox()
        self.hp_input.setRange(1, 999)
        self.hp_input.setPrefix("HP: ")
        add_layout.addWidget(self.hp_input)
        
        self.ac_input = QSpinBox()
        self.ac_input.setRange(0, 30)
        self.ac_input.setPrefix("AC: ")
        add_layout.addWidget(self.ac_input)
        
        # Add modifier input for initiative
        self.init_mod_input = QSpinBox()
        self.init_mod_input.setRange(-10, 10)
        self.init_mod_input.setPrefix("Init Mod: ")
        self.init_mod_input.setValue(0)
        add_layout.addWidget(self.init_mod_input)
        
        # Create Add button with new connection approach
        add_button = QPushButton("Add Manual Combatant")
        add_button.clicked.connect(self._handle_add_click)
        add_layout.addWidget(add_button)
        
        return add_layout

