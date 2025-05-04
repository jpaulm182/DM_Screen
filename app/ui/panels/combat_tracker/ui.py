"""
UI setup functions for the CombatTrackerPanel facade.
Extracted from original combat_tracker_panel implementation.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QLabel, QSpinBox,
    QLineEdit, QPushButton, QHeaderView, QGroupBox, QTextEdit,
    QSplitter, QAbstractItemView
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QAction

from app.ui.panels.combat_tracker.combatant_manager import CombatantManager
from app.ui.panels.combat_tracker.combat_tracker_dialogs import DeathSavesDialog
from app.ui.panels.combat_tracker_delegates import (
    InitiativeUpdateDelegate, HPUpdateDelegate, CurrentTurnDelegate
)


def _setup_delegates(panel):
    panel.init_delegate = InitiativeUpdateDelegate(panel)
    panel.init_delegate.initChanged.connect(panel._initiative_changed)
    panel.initiative_table.setItemDelegateForColumn(1, panel.init_delegate)

    panel.hp_delegate = HPUpdateDelegate(panel)
    panel.hp_delegate.hpChanged.connect(panel._hp_changed)
    panel.initiative_table.setItemDelegateForColumn(2, panel.hp_delegate)

    panel.current_turn_delegate = CurrentTurnDelegate()
    for col in range(8):
        panel.initiative_table.setItemDelegateForColumn(col, panel.current_turn_delegate)

    panel.initiative_table.cellChanged.connect(panel._handle_cell_changed)


def _setup_control_area(panel):
    control_layout = QHBoxLayout()
    combat_info = QGroupBox("Combat Info")
    info_layout = QHBoxLayout()
    # Round counter
    round_layout = QVBoxLayout()
    round_layout.addWidget(QLabel("Round:"))
    panel.round_spin = QSpinBox()
    panel.round_spin.setMinimum(1)
    panel.round_spin.setValue(panel.current_round)
    panel.round_spin.valueChanged.connect(panel._round_changed)
    round_layout.addWidget(panel.round_spin)
    info_layout.addLayout(round_layout)
    # Combat duration
    duration_layout = QVBoxLayout()
    duration_layout.addWidget(QLabel("Duration:"))
    duration_widget = QWidget()
    duration_inner = QHBoxLayout()
    panel.timer_label = QLabel("00:00:00")
    duration_inner.addWidget(panel.timer_label)
    panel.timer_button = QPushButton("Start")
    panel.timer_button.clicked.connect(panel._toggle_timer)
    duration_inner.addWidget(panel.timer_button)
    duration_widget.setLayout(duration_inner)
    duration_layout.addWidget(duration_widget)
    info_layout.addLayout(duration_layout)
    # In-game time
    game_time_layout = QVBoxLayout()
    game_time_layout.addWidget(QLabel("In-Game Time:"))
    panel.game_time_label = QLabel("0 rounds (0 minutes)")
    game_time_layout.addWidget(panel.game_time_label)
    info_layout.addLayout(game_time_layout)
    combat_info.setLayout(info_layout)
    control_layout.addWidget(combat_info)
    control_layout.addStretch(1)
    # Next combatant
    panel.next_turn_button = QPushButton("Next Combatant")
    panel.next_turn_button.clicked.connect(panel._next_turn)
    control_layout.addWidget(panel.next_turn_button)
    # Fast resolve
    panel.fast_resolve_button = QPushButton("Fast Resolve")
    panel.fast_resolve_button.setToolTip("Resolve the current combat using AI (Experimental)")
    # Connection is now handled in _connect_signals to prevent duplicate connections
    # DO NOT connect here: panel.fast_resolve_button.clicked.connect(panel._fast_resolve_combat)
    control_layout.addWidget(panel.fast_resolve_button)
    # Reset and restart
    panel.reset_button = QPushButton("Reset Combat")
    panel.reset_button.clicked.connect(panel._reset_combat)
    control_layout.addWidget(panel.reset_button)
    panel.restart_button = QPushButton("Restart Combat")
    panel.restart_button.clicked.connect(panel._restart_combat)
    control_layout.addWidget(panel.restart_button)
    return control_layout


def _setup_add_combatant_controls(panel):
    add_layout = QHBoxLayout()
    panel.name_input = QLineEdit()
    panel.name_input.setPlaceholderText("Name")
    add_layout.addWidget(panel.name_input)
    init_layout = QHBoxLayout()
    panel.initiative_input = QSpinBox()
    panel.initiative_input.setRange(-20, 30)
    panel.initiative_input.setPrefix("Init: ")
    init_layout.addWidget(panel.initiative_input)
    roll_init_button = QPushButton("🎲")
    roll_init_button.setToolTip("Roll initiative (1d20)")
    roll_init_button.clicked.connect(panel._roll_initiative)
    roll_init_button.setMaximumWidth(30)
    init_layout.addWidget(roll_init_button)
    init_widget = QWidget()
    init_widget.setLayout(init_layout)
    add_layout.addWidget(init_widget)
    panel.hp_input = QSpinBox()
    panel.hp_input.setRange(1, 999)
    panel.hp_input.setPrefix("HP: ")
    add_layout.addWidget(panel.hp_input)
    panel.ac_input = QSpinBox()
    panel.ac_input.setRange(0, 30)
    panel.ac_input.setPrefix("AC: ")
    add_layout.addWidget(panel.ac_input)
    panel.init_mod_input = QSpinBox()
    panel.init_mod_input.setRange(-10, 10)
    panel.init_mod_input.setPrefix("Init Mod: ")
    panel.init_mod_input.setValue(0)
    add_layout.addWidget(panel.init_mod_input)
    add_button = QPushButton("Add Manual Combatant")
    add_button.clicked.connect(panel._handle_add_click)
    add_layout.addWidget(add_button)
    return add_layout


def _setup_ui(panel):
    layout = QVBoxLayout()
    layout.setContentsMargins(5, 5, 5, 5)
    layout.setSpacing(5)
    panel.main_splitter = QSplitter(Qt.Vertical)
    # Initiative table
    table_container = QWidget()
    table_layout = QVBoxLayout(table_container)
    table_layout.setContentsMargins(0, 0, 0, 0)
    panel.initiative_table = QTableWidget(0, 8)
    panel.initiative_table.setHorizontalHeaderLabels([
        "Name", "Initiative", "HP", "Max HP",
        "AC", "Status", "Conc.", "Type"
    ])
    panel.initiative_table.setSelectionBehavior(QTableWidget.SelectRows)
    panel.initiative_table.setSelectionMode(QTableWidget.ExtendedSelection)
    panel.initiative_table.setEditTriggers(
        QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed
    )
    # Column sizes
    panel.initiative_table.setColumnWidth(0, 150)
    panel.initiative_table.setColumnWidth(1, 80)
    panel.initiative_table.setColumnWidth(2, 80)
    panel.initiative_table.setColumnWidth(3, 80)
    panel.initiative_table.setColumnWidth(4, 60)
    panel.initiative_table.setColumnWidth(5, 120)
    panel.initiative_table.setColumnWidth(6, 60)
    panel.initiative_table.setColumnWidth(7, 100)
    header = panel.initiative_table.horizontalHeader()
    header.setSectionResizeMode(0, QHeaderView.Stretch)
    header.setSectionResizeMode(5, QHeaderView.Stretch)
    header.setSectionResizeMode(1, QHeaderView.Fixed)
    header.setSectionResizeMode(2, QHeaderView.Fixed)
    header.setSectionResizeMode(3, QHeaderView.Fixed)
    header.setSectionResizeMode(4, QHeaderView.Fixed)
    header.setSectionResizeMode(6, QHeaderView.Fixed)
    header.setSectionResizeMode(7, QHeaderView.Fixed)
    panel.initiative_table.setContextMenuPolicy(Qt.CustomContextMenu)
    panel.initiative_table.customContextMenuRequested.connect(panel._show_context_menu)
    panel.initiative_table.cellChanged.connect(panel._handle_cell_changed)
    # Build UI
    _setup_delegates(panel)
    table_layout.addLayout(_setup_control_area(panel))
    table_layout.addLayout(_setup_add_combatant_controls(panel))
    table_layout.addWidget(panel.initiative_table)
    panel.main_splitter.addWidget(table_container)
    # Combat log
    panel.log_container = QWidget()
    log_layout = QVBoxLayout(panel.log_container)
    log_layout.setContentsMargins(0, 0, 0, 0)
    log_header = QHBoxLayout()
    log_header.addWidget(QLabel("<b>Combat Log & Results</b>"))
    clear_log_btn = QPushButton("Clear Log")
    clear_log_btn.setMaximumWidth(100)
    clear_log_btn.clicked.connect(panel._clear_combat_log)
    log_header.addWidget(clear_log_btn)
    log_layout.addLayout(log_header)
    panel.combat_log_text = QTextEdit()
    panel.combat_log_text.setReadOnly(True)
    panel.combat_log_text.setMinimumHeight(100)
    panel.combat_log_text.setStyleSheet("""
        QTextEdit { 
            background-color: white;
            color: #000000;
            font-family: Arial, sans-serif;
            font-size: 12px;
        }
    """)
    log_layout.addWidget(panel.combat_log_text)
    panel.main_splitter.addWidget(panel.log_container)
    panel.main_splitter.setSizes([600, 200])
    layout.addWidget(panel.main_splitter)
    panel.setLayout(layout)
    panel.initiative_table.setMinimumHeight(200)
    panel.initiative_table.itemSelectionChanged.connect(panel._on_selection_changed)
    # Keyboard shortcut
    next_act = QAction("Next Turn", panel, triggered=panel._next_turn, shortcut=QKeySequence("N"))
    next_act.setShortcutContext(Qt.WidgetWithChildrenShortcut)
    panel.addAction(next_act)
    # Stretch and highlight
    panel.main_splitter.setStretchFactor(0, 3)
    panel.main_splitter.setStretchFactor(1, 2)
    panel._update_highlight()
