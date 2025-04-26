# Helpers for CombatTrackerPanel (_round_)

    def _round_changed(self, value):
        """Handle round number change"""
        self.current_round = value
        self._update_game_time()

