# detail_dialog.py
# Minimal dialog for displaying player and DM information in tabs

from PySide6.QtWidgets import QDialog, QVBoxLayout, QTabWidget, QTextBrowser, QDialogButtonBox, QWidget

class DetailDialog(QDialog):
    def __init__(self, parent, title, player_content, dm_content):
        super().__init__(parent)
        self.setWindowTitle(f"Details: {title}")
        self.resize(600, 400)
        layout = QVBoxLayout(self)

        tabs = QTabWidget()

        # Player tab
        player_tab = QWidget()
        player_layout = QVBoxLayout(player_tab)
        player_browser = QTextBrowser()
        player_browser.setHtml(player_content)
        player_browser.setReadOnly(True)
        player_layout.addWidget(player_browser)
        tabs.addTab(player_tab, "Player Info")

        # DM tab
        dm_tab = QWidget()
        dm_layout = QVBoxLayout(dm_tab)
        dm_browser = QTextBrowser()
        dm_browser.setHtml(dm_content)
        dm_browser.setReadOnly(True)
        dm_layout.addWidget(dm_browser)
        tabs.addTab(dm_tab, "DM Info")

        layout.addWidget(tabs)

        # Close button
        button_box = QDialogButtonBox(QDialogButtonBox.Close)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        # For future: add edit/regenerate buttons, etc. 