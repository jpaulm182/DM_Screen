    def event(self, event):
        """Handle custom events posted to our panel"""
        from PySide6.QtWidgets import QApplication, QMessageBox
        
        if event.type() == QEvent.Type(QEvent.User + 1):
            # This is our UpdateUIEvent for JSON
            try:
                self._update_ui(event.json_data)
                return True
            except Exception as e:
                print(f"[CombatTracker] Error in event handler UI update: {e}")
                return False
        elif event.type() == QEvent.Type(QEvent.User + 100):
            # Progress event
            self.fast_resolve_button.setText(event.message)
            QApplication.processEvents()
            return True
        elif event.type() == QEvent.Type(QEvent.User + 101):
            # Error event
            self._reset_resolve_button("Fast Resolve", True)
            QMessageBox.critical(self, event.title, event.message)
            return True
        elif event.type() == QEvent.Type(QEvent.User + 102):
            # Clear log event
            self.combat_log_text.clear()
            return True
        elif event.type() == QEvent.Type(QEvent.User + 103):
            # Add initial state event
            self._add_initial_combat_state_to_log(event.combat_state)
            return True
        elif event.type() == QEvent.Type(QEvent.User + 104):
            # Log dice event
            self._log_combat_action(
                "Dice", 
                "AI", 
                f"rolled {event.expr}", 
                result=f"Result: {event.result}"
            )
            return True
        elif event.type() == QEvent.Type(QEvent.User + 105):
            # Process result event
            self._process_resolution_ui(event.result, event.error)
            return True
        elif event.type() == QEvent.Type(QEvent.User + 106):
            # Update UI event
            self._update_ui_wrapper(event.turn_state)
            return True
        elif event.type() == QEvent.Type(QEvent.User + 107):
            # Set resolving event
            self._is_resolving_combat = event.is_resolving
            print(f"[CombatTracker] Setting _is_resolving_combat = {event.is_resolving}")
            return True
        elif event.type() == QEvent.Type(QEvent.User + 108):
            # Connect signal event
            try:
                # Disconnect any existing connection first to be safe
                try:
                    self.app_state.combat_resolver.resolution_complete.disconnect(self._process_resolution_ui)
                    print("[CombatTracker] Disconnected existing signal connection")
                except Exception:
                    # Connection might not exist yet, which is fine
                    pass
                
                # Connect the signal
                self.app_state.combat_resolver.resolution_complete.connect(self._process_resolution_ui)
                print("[CombatTracker] Successfully connected resolution_complete signal")
            except Exception as conn_error:
                print(f"[CombatTracker] Failed to connect signal: {conn_error}")
            return True
        elif event.type() == QEvent.Type(QEvent.User + 109):
            # Update button event
            self._reset_resolve_button(event.text, event.enabled)
            return True
            
        return super().event(event)
