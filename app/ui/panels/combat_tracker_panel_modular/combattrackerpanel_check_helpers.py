# Helpers for CombatTrackerPanel (_check_)

    def _check_and_reset_button(self):
        """Check if the button should be reset and reset it if necessary"""
        # Check if the button text is still in "Initializing..." state after our timer
        if self.fast_resolve_button.text() == "Initializing..." or self.fast_resolve_button.text().startswith("Resolving"):
            print("[CombatTracker] Backup timer detected hanging button, forcing reset")
            self._reset_resolve_button("Fast Resolve", True)
            
            # Also log this to the combat log for user awareness
            self.combat_log_text.append("<p style='color:orange;'><b>Notice:</b> Combat resolution timed out or is taking too long. The Fast Resolve button has been reset.</p>")
            
            # Maybe the combat resolver is still running - force all needed flag resets too
            self._is_resolving_combat = False

    # ---------------------------------------------------------------
    # Helper: remove currently selected combatants (invoked by the
    # context‑menu 'Remove' action).
    # ---------------------------------------------------------------
        """Remove all currently selected rows from the combat tracker.

        We reuse the existing _cleanup_dead_combatants logic to ensure all
        bookkeeping (death_saves, concentrating sets, current_turn index,
        etc.) is handled in one place.
        """

        # Determine which rows are selected.
        rows = sorted({idx.row() for idx in self.initiative_table.selectedIndexes()})
        if not rows:
            return

        # Ask for confirmation to prevent accidental deletion.
        reply = QMessageBox.question(
            self,
            "Remove Combatant(s)",
            f"Remove {len(rows)} selected combatant(s) from the tracker?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        # Tag each selected combatant as Dead so that the existing cleanup
        # routine will remove them and handle all related state.
        for row in rows:
            if row >= self.initiative_table.rowCount():
                continue
            status_item = self.initiative_table.item(row, 5)
            if status_item is None:
                status_item = QTableWidgetItem()
                self.initiative_table.setItem(row, 5, status_item)
            status_item.setText("Dead")

        # Now invoke the shared cleanup function to physically remove rows.
        self._cleanup_dead_combatants()

