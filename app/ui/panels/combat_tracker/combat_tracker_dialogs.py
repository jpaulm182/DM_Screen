# app/ui/panels/combat_tracker/combat_tracker_dialogs.py
# Contains dialogs used by the Combat Tracker Panel

from PySide6.QtWidgets import (
    QDialog, 
    QVBoxLayout, 
    QGroupBox, 
    QHBoxLayout, 
    QCheckBox, 
    QDialogButtonBox
)

class DeathSavesDialog(QDialog):
    """Dialog for tracking death saving throws"""
    def __init__(self, parent=None, current_saves=None):
        super().__init__(parent)
        self.setWindowTitle("Death Saving Throws")
        # Store current saves (e.g., {"successes": 1, "failures": 2})
        self.current_saves = current_saves or {"successes": 0, "failures": 0}
        self._setup_ui()

    def _setup_ui(self):
        """Set up the user interface elements for the dialog."""
        layout = QVBoxLayout()

        # --- Successes Group ---
        success_group = QGroupBox("Successes")
        success_layout = QHBoxLayout()
        self.success_checks = []
        # Create 3 checkboxes for successes
        for i in range(3):
            check = QCheckBox()
            # Check the box if the current count is greater than the index
            check.setChecked(i < self.current_saves["successes"])
            self.success_checks.append(check)
            success_layout.addWidget(check)
        success_group.setLayout(success_layout)
        layout.addWidget(success_group)

        # --- Failures Group ---
        failure_group = QGroupBox("Failures")
        failure_layout = QHBoxLayout()
        self.failure_checks = []
        # Create 3 checkboxes for failures
        for i in range(3):
            check = QCheckBox()
            # Check the box if the current count is greater than the index
            check.setChecked(i < self.current_saves["failures"])
            self.failure_checks.append(check)
            failure_layout.addWidget(check)
        failure_group.setLayout(failure_layout)
        layout.addWidget(failure_group)

        # --- Dialog Buttons (OK/Cancel) ---
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        # Connect signals for button clicks
        buttons.accepted.connect(self.accept) # Closes dialog with QDialog.Accepted status
        buttons.rejected.connect(self.reject) # Closes dialog with QDialog.Rejected status
        layout.addWidget(buttons)

        self.setLayout(layout)

    def get_saves(self):
        """Get the current death saves state based on checked boxes."""
        # Count checked boxes for successes and failures
        return {
            "successes": sum(1 for c in self.success_checks if c.isChecked()),
            "failures": sum(1 for c in self.failure_checks if c.isChecked())
        } 