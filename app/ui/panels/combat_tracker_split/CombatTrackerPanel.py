# Split from combat_tracker_panel.py
# See helpers: combattrackerpanel_CombatTrackerPanel_helpers.py
from app.ui.panels.base_panel import BasePanel
from PySide6.QtCore import Signal
from PySide6.QtCore import QEvent
from PySide6.QtCore import Slot
from app.ui.panels.combat_tracker.combatant_manager import CombatantManager
from PySide6.QtCore import QTimer
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QLabel,
    QSpinBox, QLineEdit, QPushButton, QHeaderView, QComboBox, QCheckBox,
    QGroupBox, QWidget, QStyledItemDelegate, QStyle, QToolButton,
    QTabWidget, QScrollArea, QFormLayout, QFrame, QSplitter, QApplication,
    QSizePolicy, QTextEdit, QMenu, QMessageBox, QDialog, QDialogButtonBox,
    QAbstractItemView, QInputDialog
)
from app.ui.panels.combat_tracker_delegates import InitiativeUpdateDelegate, HPUpdateDelegate, CurrentTurnDelegate
from PySide6.QtGui import QAction, QKeySequence
from app.ui.panels.combattrackerpanel_CombatTrackerPanel_helpers import CombatTrackerPanel
