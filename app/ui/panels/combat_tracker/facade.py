from app.ui.panels.base_panel import BasePanel
from app.ui.panels.combat_tracker.ui import _setup_ui

class CombatTrackerPanel(BasePanel):
    """Combat Tracker panel built with modular UI functions."""

    def __init__(self, app_state):
        super().__init__(app_state, "Combat Tracker")

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
        self._fast_resolve_combat = lambda: None
        self._reset_combat = lambda: None
        self._restart_combat = lambda: None
        self._handle_add_click = lambda: None
        self._clear_combat_log = lambda: None
        self._update_highlight = lambda: None
        # Build UI layout and widgets
        _setup_ui(self)
