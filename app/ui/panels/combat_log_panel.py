"""
Combat log panel for tracking and displaying combat actions

Features:
- Chronological log of all combat actions
- Timestamped entries
- Action categories (damage, healing, conditions, etc.)
- Filtering by action type
- Export functionality
- Clear log option
- Turn and round tracking
- Initiative order changes
- Status effect application
"""

import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, 
    QPushButton, QComboBox, QLabel, QLineEdit, 
    QTableWidget, QTableWidgetItem, QHeaderView,
    QCheckBox, QGroupBox, QMessageBox, QFileDialog
)
from PySide6.QtCore import Qt, Signal, Slot, QSize
from PySide6.QtGui import QColor, QTextCharFormat, QFont, QIcon

from app.ui.panels.base_panel import BasePanel

# Action Categories for filtering
ACTION_CATEGORIES = [
    "All",
    "Attack",
    "Damage",
    "Healing",
    "Status Effect",
    "Initiative",
    "Movement",
    "Death Save",
    "Spell Cast",
    "Item Use",
    "Other"
]

class LogEntry:
    """Class to represent a combat log entry"""
    def __init__(self, timestamp, category, actor, target, action, result, round_num=None, turn_num=None):
        self.timestamp = timestamp  # When the action occurred
        self.category = category    # Type of action (from ACTION_CATEGORIES)
        self.actor = actor          # Who performed the action
        self.target = target        # Who received the action (if applicable)
        self.action = action        # Description of the action
        self.result = result        # Result of the action
        self.round_num = round_num  # Combat round when action occurred
        self.turn_num = turn_num    # Combat turn when action occurred
    
    def __str__(self):
        time_str = self.timestamp.strftime("%H:%M:%S")
        round_turn = ""
        if self.round_num is not None and self.turn_num is not None:
            round_turn = f"[Round {self.round_num}, Turn {self.turn_num}] "
        
        target_str = ""
        if self.target:
            target_str = f" → {self.target}"
            
        result_str = ""
        if self.result:
            result_str = f": {self.result}"
            
        return f"[{time_str}] {round_turn}{self.actor}{target_str} {self.action}{result_str}"
    
    def to_html(self):
        """Convert log entry to HTML for rich display"""
        time_str = self.timestamp.strftime("%H:%M:%S")
        
        # Color coding based on category
        category_colors = {
            "Attack": "#3498db",    # Blue
            "Damage": "#e74c3c",    # Red
            "Healing": "#2ecc71",   # Green
            "Status Effect": "#9b59b6", # Purple
            "Initiative": "#f39c12", # Orange
            "Movement": "#95a5a6",  # Gray
            "Death Save": "#c0392b", # Dark Red
            "Spell Cast": "#8e44ad", # Dark Purple
            "Item Use": "#d35400",  # Dark Orange
            "Other": "#7f8c8d"      # Dark Gray
        }
        
        color = category_colors.get(self.category, "#000000")
        
        # Build HTML components
        time_html = f"<span style='color: #7f8c8d; font-size: 0.9em;'>[{time_str}]</span>"
        
        round_turn_html = ""
        if self.round_num is not None and self.turn_num is not None:
            round_turn_html = f"<span style='color: #f39c12; font-weight: bold;'>[Round {self.round_num}, Turn {self.turn_num}]</span> "
        
        actor_html = f"<span style='font-weight: bold;'>{self.actor}</span>"
        
        target_html = ""
        if self.target:
            target_html = f" <span style='color: #7f8c8d;'>→</span> <span style='font-weight: bold;'>{self.target}</span>"
            
        action_html = f"<span style='color: {color};'>{self.action}</span>"
        
        result_html = ""
        if self.result:
            result_html = f": <span>{self.result}</span>"
            
        return f"{time_html} {round_turn_html}{actor_html}{target_html} {action_html}{result_html}"

class CombatLogPanel(BasePanel):
    """Panel for logging and displaying combat actions"""
    
    def __init__(self, app_state):
        """Initialize the combat log panel"""
        super().__init__(app_state, "Combat Log")
        self.log_entries = []  # List to store all log entries
        self.current_filter = "All"  # Default filter
        
    def _setup_ui(self):
        """Set up the combat log UI"""
        # Main layout
        layout = QVBoxLayout()
        
        # Filter controls
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Filter:"))
        
        self.filter_combo = QComboBox()
        for category in ACTION_CATEGORIES:
            self.filter_combo.addItem(category)
        self.filter_combo.currentTextChanged.connect(self._apply_filter)
        filter_layout.addWidget(self.filter_combo)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search...")
        self.search_input.textChanged.connect(self._apply_filter)
        filter_layout.addWidget(self.search_input)
        
        layout.addLayout(filter_layout)
        
        # Log display area
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setStyleSheet("font-family: monospace;")
        layout.addWidget(self.log_display)
        
        # Control buttons
        button_layout = QHBoxLayout()
        
        self.clear_button = QPushButton("Clear Log")
        self.clear_button.clicked.connect(self._clear_log)
        button_layout.addWidget(self.clear_button)
        
        self.export_button = QPushButton("Export Log")
        self.export_button.clicked.connect(self._export_log)
        button_layout.addWidget(self.export_button)
        
        # Manual log entry button
        self.add_entry_button = QPushButton("Add Entry")
        self.add_entry_button.clicked.connect(self._add_manual_entry)
        button_layout.addWidget(self.add_entry_button)
        
        layout.addLayout(button_layout)
        
        # Set the layout
        self.setLayout(layout)
    
    def add_log_entry(self, category, actor, action, target=None, result=None, round_num=None, turn_num=None):
        """Add a new entry to the combat log"""
        timestamp = datetime.datetime.now()
        
        # Get current round and turn from combat tracker if not provided
        if round_num is None or turn_num is None:
            combat_tracker = self._get_combat_tracker()
            if combat_tracker:
                if round_num is None:
                    round_num = combat_tracker.current_round
                if turn_num is None:
                    turn_num = combat_tracker.current_turn
        
        entry = LogEntry(timestamp, category, actor, target, action, result, round_num, turn_num)
        self.log_entries.append(entry)
        
        # Update the display
        self._update_display()
        
        return entry
    
    def _get_combat_tracker(self):
        """Get the combat tracker panel if available"""
        if hasattr(self.app_state, 'panel_manager') and hasattr(self.app_state.panel_manager, 'get_panel_widget'):
            return self.app_state.panel_manager.get_panel_widget("combat_tracker")
        return None
    
    def _apply_filter(self):
        """Apply filters to the log display"""
        self.current_filter = self.filter_combo.currentText()
        self._update_display()
    
    def _update_display(self):
        """Update the log display with filtered entries"""
        self.log_display.clear()
        
        # Get search text
        search_text = self.search_input.text().lower()
        
        # Build HTML content
        html_content = "<html><body>"
        
        for entry in reversed(self.log_entries):  # Newest entries at the top
            # Apply category filter
            if self.current_filter != "All" and entry.category != self.current_filter:
                continue
                
            # Apply search filter
            if search_text:
                entry_text = str(entry).lower()
                if search_text not in entry_text:
                    continue
            
            # Add entry to display
            html_content += f"<div>{entry.to_html()}</div>"
        
        html_content += "</body></html>"
        self.log_display.setHtml(html_content)
    
    def _clear_log(self):
        """Clear the combat log"""
        confirm = QMessageBox.question(
            self,
            "Clear Combat Log",
            "Are you sure you want to clear the combat log? This cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if confirm == QMessageBox.Yes:
            self.log_entries.clear()
            self._update_display()
    
    def _export_log(self):
        """Export the combat log to a file"""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Combat Log",
            "",
            "Text Files (*.txt);;HTML Files (*.html);;All Files (*)"
        )
        
        if not file_path:
            return
            
        try:
            with open(file_path, 'w') as f:
                if file_path.endswith('.html'):
                    # Export as HTML
                    f.write("<html><head><style>")
                    f.write("body { font-family: Arial, sans-serif; }")
                    f.write("</style></head><body>")
                    
                    for entry in self.log_entries:
                        f.write(f"<div>{entry.to_html()}</div>")
                        
                    f.write("</body></html>")
                else:
                    # Export as plain text
                    for entry in self.log_entries:
                        f.write(f"{str(entry)}\n")
                        
            QMessageBox.information(
                self,
                "Export Successful",
                f"Combat log exported to {file_path}"
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Export Failed",
                f"Failed to export combat log: {str(e)}"
            )
    
    def _add_manual_entry(self):
        """Add a manual entry to the log"""
        # This would open a dialog to add custom entries
        # For now, we'll just add a placeholder
        self.add_log_entry("Other", "DM", "manually added a note", result="Manual entry")
    
    def log_attack(self, attacker, target, attack_roll, hit=None, damage=None, crit=False):
        """Log an attack action"""
        # Build the result string
        result = f"Roll: {attack_roll}"
        if hit is not None:
            result += f", {'Hit' if hit else 'Miss'}"
        if damage is not None:
            result += f", Damage: {damage}"
        if crit:
            result += " (Critical Hit!)"
            
        return self.add_log_entry("Attack", attacker, "attacked", target, result)
    
    def log_damage(self, source, target, amount, damage_type=None):
        """Log damage dealt"""
        action = "dealt damage to"
        result = f"{amount} damage"
        if damage_type:
            result += f" ({damage_type})"
            
        return self.add_log_entry("Damage", source, action, target, result)
    
    def log_healing(self, source, target, amount):
        """Log healing received"""
        action = "healed"
        result = f"{amount} HP"
            
        return self.add_log_entry("Healing", source, action, target, result)
    
    def log_status_effect(self, source, target, effect, applied=True):
        """Log a status effect application or removal"""
        action = f"{'applied' if applied else 'removed'} status"
        result = effect
            
        return self.add_log_entry("Status Effect", source, action, target, result)
    
    def log_initiative(self, character, roll, total=None):
        """Log an initiative roll"""
        action = "rolled initiative"
        result = f"{roll}"
        if total is not None and total != roll:
            result += f" (Total: {total})"
            
        return self.add_log_entry("Initiative", character, action, None, result)
    
    def log_death_save(self, character, roll, success=None):
        """Log a death saving throw"""
        action = "made a death save"
        result = f"Roll: {roll}, {'Success' if success else 'Failure'}" if success is not None else f"Roll: {roll}"
            
        return self.add_log_entry("Death Save", character, action, None, result)
    
    def log_spell_cast(self, caster, spell_name, level=None, target=None, result=None):
        """Log a spell being cast"""
        action = f"cast {spell_name}"
        if level is not None:
            action += f" (Level {level})"
            
        return self.add_log_entry("Spell Cast", caster, action, target, result)
    
    def log_item_use(self, user, item_name, target=None, result=None):
        """Log an item being used"""
        action = f"used {item_name}"
            
        return self.add_log_entry("Item Use", user, action, target, result)
    
    def log_turn_start(self, character, round_num, turn_num):
        """Log the start of a character's turn"""
        action = "started their turn"
            
        return self.add_log_entry("Initiative", character, action, None, None, round_num, turn_num)
    
    def log_round_start(self, round_num):
        """Log the start of a new round"""
        action = f"started"
            
        return self.add_log_entry("Initiative", f"Round {round_num}", action)
    
    def save_state(self):
        """Save the combat log state"""
        # Convert log entries to serializable format
        serialized_entries = []
        for entry in self.log_entries:
            serialized_entries.append({
                "timestamp": entry.timestamp.isoformat(),
                "category": entry.category,
                "actor": entry.actor,
                "target": entry.target,
                "action": entry.action,
                "result": entry.result,
                "round_num": entry.round_num,
                "turn_num": entry.turn_num
            })
        
        return {
            "log_entries": serialized_entries,
            "current_filter": self.current_filter
        }
    
    def restore_state(self, state):
        """Restore the combat log state"""
        if not state:
            return
            
        self.log_entries = []
        
        # Restore log entries
        if "log_entries" in state:
            for entry_data in state["log_entries"]:
                # Parse timestamp string back to datetime
                timestamp = datetime.datetime.fromisoformat(entry_data["timestamp"])
                
                entry = LogEntry(
                    timestamp,
                    entry_data["category"],
                    entry_data["actor"],
                    entry_data["target"],
                    entry_data["action"],
                    entry_data["result"],
                    entry_data["round_num"],
                    entry_data["turn_num"]
                )
                
                self.log_entries.append(entry)
        
        # Restore filter
        if "current_filter" in state:
            self.current_filter = state["current_filter"]
            index = self.filter_combo.findText(self.current_filter)
            if index >= 0:
                self.filter_combo.setCurrentIndex(index)
        
        # Update the display
        self._update_display() 