from app.ui.panels.base_panel import BasePanel
from app.ui.panels.combat_tracker.ui import _setup_ui
from app.ui.panels.combat_tracker.combatant_manager import CombatantManager
from app.ui.panels.combat_utils import roll_dice
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox

class CombatTrackerPanel(BasePanel):
    """Combat Tracker panel built with modular UI functions."""

    def __init__(self, app_state):
        # Initialize UI state required by ui.setup (round counter)
        self.current_round = 1
        super().__init__(app_state, "Combat Tracker")
        # Provide dice-rolling utility to combat manager
        self.roll_dice = roll_dice
        # Initialize combatant manager for MonsterPanel signals
        self.combatant_manager = CombatantManager(self)

    def _setup_ui(self):
        # Stub callback methods to satisfy UI signal connections
        self._initiative_changed = lambda row, col: None
        self._hp_changed = lambda row, col: None
        self._handle_cell_changed = lambda row, col: None
        self._show_context_menu = lambda pos: None
        self._on_selection_changed = lambda: None
        self._round_changed = lambda value: None
        self._toggle_timer = lambda: None
        self._next_turn = lambda: None
        self._reset_combat = lambda: None
        self._restart_combat = lambda: None
        self._handle_add_click = lambda: None
        self._update_highlight = lambda: None
        # Stub roll initiative handler for UI button
        self._roll_initiative = lambda: None
        # Stub fast resolve (AI) handler for UI button
        self._fast_resolve_combat = lambda: QMessageBox.information(self, "Fast Resolve", "Fast Resolve is not implemented yet.")
        # Append combat log entries to the text widget
        self._log_combat_action = lambda category, actor, action, target=None, result=None, round=None, turn=None: self.combat_log_text.append(f"[{category}] {actor} {action}{(' ' + str(target)) if target else ''}{(' ' + str(result)) if result else ''}")
        # Clear combat log
        self._clear_combat_log = lambda: self.combat_log_text.clear()
        # Stub sort handler so manager can sort initiative table
        self._sort_initiative = lambda: self.initiative_table.sortItems(1, Qt.DescendingOrder)
        # Build UI layout and widgets
        _setup_ui(self)
