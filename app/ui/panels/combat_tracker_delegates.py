# combat_tracker_delegates.py
"""
Custom QStyledItemDelegate subclasses for the combat tracker UI.
"""
from PySide6.QtWidgets import QStyledItemDelegate
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor

class InitiativeUpdateDelegate(QStyledItemDelegate):
    """Delegate to handle initiative updates with auto-sorting"""
    
    # Signal to notify initiative changes
    initChanged = Signal(int, int)  # row, new_initiative
    
    def __init__(self, parent=None):
        super().__init__(parent)
    
    def createEditor(self, parent, option, index):
        """Create editor for Initiative cell (SpinBox)"""
        editor = QSpinBox(parent)
        editor.setMinimum(-20)  # Allow negative initiative
        editor.setMaximum(30)
        return editor
    
    def setEditorData(self, editor, index):
        """Set editor data from the model"""
        try:
            value = int(index.data(Qt.DisplayRole) or 0)
            editor.setValue(value)
        except ValueError:
            editor.setValue(0)
    
    def setModelData(self, editor, model, index):
        """Set model data from the editor"""
        value = editor.value()
        model.setData(index, str(value), Qt.DisplayRole)
        
        # Emit signal for initiative changed
        self.initChanged.emit(index.row(), value)

class CurrentTurnDelegate(QStyledItemDelegate):
    '''Delegate to handle custom painting for the current turn row.'''
    def paint(self, painter, option, index):
        is_current = index.data(Qt.UserRole + 1)
        if is_current == True:
            painter.save()
            highlight_bg = QColor(0, 51, 102)
            highlight_fg = QColor(Qt.white)
            painter.fillRect(option.rect, highlight_bg)
            pen = painter.pen()
            pen.setColor(highlight_fg)
            painter.setPen(pen)
            text_rect = option.rect.adjusted(5, 0, -5, 0)
            painter.drawText(text_rect, option.displayAlignment, index.data(Qt.DisplayRole))
            painter.restore()
        else:
            super().paint(painter, option, index)

class HPUpdateDelegate(QStyledItemDelegate):
    """Delegate to handle HP updates with quick buttons"""
    hpChanged = Signal(int, int)  # row, new_hp
    def __init__(self, parent=None):
        super().__init__(parent)
        self.buttons = {}
    def createEditor(self, parent, option, index):
        from PySide6.QtWidgets import QSpinBox
        editor = QSpinBox(parent)
        editor.setMinimum(0)
        editor.setMaximum(999)
        max_hp = index.data(Qt.UserRole) or 999
        editor.setMaximum(max_hp)
        return editor
