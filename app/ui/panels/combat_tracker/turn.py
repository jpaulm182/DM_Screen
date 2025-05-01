    def current_turn(self):
        """Get the current turn index"""
        return getattr(self, '_current_turn', -1)

    def current_turn(self, value):
        """Set the current turn index"""
        self._current_turn = value
