# app/ui/panel_settings_dialog.py - Panel settings configuration dialog
"""
Dialog for configuring panel layout settings

This dialog allows users to customize how panels are displayed and organized,
and configure other application settings like the preferred LLM.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, 
    QCheckBox, QSpinBox, QPushButton, QGroupBox, QFormLayout,
    QSlider, QComboBox
)
from PySide6.QtCore import Qt

# Import necessary LLM components
from app.core.llm_service import ModelInfo, ModelProvider 

class PanelSettingsDialog(QDialog):
    """Dialog for configuring panel layout and other application settings"""
    
    def __init__(self, parent=None, app_state=None):
        """Initialize the panel settings dialog
        
        Args:
            parent: Parent widget
            app_state: Application state object
        """
        super().__init__(parent)
        
        self.app_state = app_state
        
        self.setWindowTitle("Application Settings")
        self.setMinimumWidth(450)
        self.setMinimumHeight(500)
        
        self._setup_ui()
        self._load_settings()
        
    def _setup_ui(self):
        """Set up the dialog UI"""
        layout = QVBoxLayout(self)
        
        # Panel Tabbing Group
        tabbing_group = QGroupBox("Panel Tabbing")
        tabbing_layout = QFormLayout(tabbing_group)
        
        # Tab threshold slider
        self.tab_threshold_slider = QSlider(Qt.Horizontal)
        self.tab_threshold_slider.setMinimum(2)
        self.tab_threshold_slider.setMaximum(10)
        self.tab_threshold_slider.setValue(4)
        self.tab_threshold_slider.setTickPosition(QSlider.TicksBelow)
        self.tab_threshold_slider.setTickInterval(1)
        
        self.tab_threshold_label = QLabel("4")
        self.tab_threshold_slider.valueChanged.connect(
            lambda v: self.tab_threshold_label.setText(str(v))
        )
        
        threshold_layout = QHBoxLayout()
        threshold_layout.addWidget(self.tab_threshold_slider)
        threshold_layout.addWidget(self.tab_threshold_label)
        
        tabbing_layout.addRow("Auto-tab threshold:", threshold_layout)
        
        # Tabbing checkboxes
        self.always_tab_reference = QCheckBox("Always tab Reference panels")
        self.always_tab_reference.setChecked(True)
        tabbing_layout.addRow("", self.always_tab_reference)
        
        self.always_tab_campaign = QCheckBox("Always tab Campaign panels")
        self.always_tab_campaign.setChecked(True)
        tabbing_layout.addRow("", self.always_tab_campaign)
        
        self.always_tab_utility = QCheckBox("Always tab Utility panels")
        self.always_tab_utility.setChecked(True)
        tabbing_layout.addRow("", self.always_tab_utility)
        
        layout.addWidget(tabbing_group)
        
        # Panel Size Group
        size_group = QGroupBox("Panel Size")
        size_layout = QFormLayout(size_group)
        
        # Min panel width
        self.min_panel_width = QSpinBox()
        self.min_panel_width.setMinimum(100)
        self.min_panel_width.setMaximum(800)
        self.min_panel_width.setValue(350)
        self.min_panel_width.setSingleStep(50)
        size_layout.addRow("Minimum panel width:", self.min_panel_width)
        
        # Min panel height
        self.min_panel_height = QSpinBox()
        self.min_panel_height.setMinimum(100)
        self.min_panel_height.setMaximum(600)
        self.min_panel_height.setValue(250)
        self.min_panel_height.setSingleStep(50)
        size_layout.addRow("Minimum panel height:", self.min_panel_height)
        
        # Percentage sizing
        self.use_percentage_sizing = QCheckBox("Use percentage-based sizing")
        self.use_percentage_sizing.setChecked(True)
        size_layout.addRow("", self.use_percentage_sizing)
        
        # Panel color intensity
        self.panel_border_intensity = QSlider(Qt.Horizontal)
        self.panel_border_intensity.setMinimum(1)
        self.panel_border_intensity.setMaximum(5)
        self.panel_border_intensity.setValue(3)
        self.panel_border_intensity.setTickPosition(QSlider.TicksBelow)
        self.panel_border_intensity.setTickInterval(1)
        
        self.border_intensity_label = QLabel("3")
        self.panel_border_intensity.valueChanged.connect(
            lambda v: self.border_intensity_label.setText(str(v))
        )
        
        border_layout = QHBoxLayout()
        border_layout.addWidget(self.panel_border_intensity)
        border_layout.addWidget(self.border_intensity_label)
        
        size_layout.addRow("Border intensity:", border_layout)
        
        layout.addWidget(size_group)
        
        # LLM Settings Group
        llm_group = QGroupBox("LLM Settings")
        llm_layout = QFormLayout(llm_group)

        self.llm_preference_combo = QComboBox()
        
        # Populate with available OpenAI models
        if self.app_state and self.app_state.llm_service:
            all_models = self.app_state.llm_service.get_available_models()
            openai_models = [m for m in all_models if ModelInfo.get_provider_for_model(m['id']) == ModelProvider.OPENAI]
            
            # Add default/automatic option
            self.llm_preference_combo.addItem("Automatic (Prefer Mini)", None) 
            
            # Add specific OpenAI models
            for model in openai_models:
                 # Only add the two models we care about for this toggle
                if model['id'] in [ModelInfo.OPENAI_GPT4O_MINI, ModelInfo.OPENAI_GPT4O]:
                    self.llm_preference_combo.addItem(model['name'], model['id'])

        llm_layout.addRow("Preferred LLM:", self.llm_preference_combo)
        layout.addWidget(llm_group)
        
        # Buttons
        layout.addStretch(1)

        button_layout = QHBoxLayout()
        
        self.reset_button = QPushButton("Reset to Defaults")
        self.reset_button.clicked.connect(self._reset_to_defaults)
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        
        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self._save_settings)
        self.save_button.setDefault(True)
        
        button_layout.addWidget(self.reset_button)
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.save_button)
        
        layout.addLayout(button_layout)
    
    def _load_settings(self):
        """Load current settings into the UI"""
        if not self.app_state:
            return
        
        # Load panel layout settings
        self.tab_threshold_slider.setValue(
            self.app_state.get_panel_layout_setting("tab_threshold", 4)
        )
        self.always_tab_reference.setChecked(
            self.app_state.get_panel_layout_setting("always_tab_reference", True)
        )
        self.always_tab_campaign.setChecked(
            self.app_state.get_panel_layout_setting("always_tab_campaign", True)
        )
        self.always_tab_utility.setChecked(
            self.app_state.get_panel_layout_setting("always_tab_utility", True)
        )
        self.min_panel_width.setValue(
            self.app_state.get_panel_layout_setting("min_panel_width", 350)
        )
        self.min_panel_height.setValue(
            self.app_state.get_panel_layout_setting("min_panel_height", 250)
        )
        self.use_percentage_sizing.setChecked(
            self.app_state.get_panel_layout_setting("use_percentage_sizing", True)
        )
        self.panel_border_intensity.setValue(
            self.app_state.get_panel_layout_setting("panel_border_intensity", 3)
        )

        # Load LLM preference
        preferred_model_id = self.app_state.get_setting("preferred_llm_model", None)
        index = self.llm_preference_combo.findData(preferred_model_id)
        if index != -1:
            self.llm_preference_combo.setCurrentIndex(index)
        else:
             # Default to "Automatic" if preference not set or not found
            self.llm_preference_combo.setCurrentIndex(0)
    
    def _save_settings(self):
        """Save settings to app_state"""
        if not self.app_state:
            self.accept()
            return
        
        # Save panel layout settings
        self.app_state.update_panel_layout_setting(
            "tab_threshold", self.tab_threshold_slider.value()
        )
        self.app_state.update_panel_layout_setting(
            "always_tab_reference", self.always_tab_reference.isChecked()
        )
        self.app_state.update_panel_layout_setting(
            "always_tab_campaign", self.always_tab_campaign.isChecked()
        )
        self.app_state.update_panel_layout_setting(
            "always_tab_utility", self.always_tab_utility.isChecked()
        )
        self.app_state.update_panel_layout_setting(
            "min_panel_width", self.min_panel_width.value()
        )
        self.app_state.update_panel_layout_setting(
            "min_panel_height", self.min_panel_height.value()
        )
        self.app_state.update_panel_layout_setting(
            "use_percentage_sizing", self.use_percentage_sizing.isChecked()
        )
        self.app_state.update_panel_layout_setting(
            "panel_border_intensity", self.panel_border_intensity.value()
        )

        # Save LLM preference
        selected_model_id = self.llm_preference_combo.currentData()
        self.app_state.set_setting("preferred_llm_model", selected_model_id)
        
        self.accept()
    
    def _reset_to_defaults(self):
        """Reset settings to defaults"""
        # Reset panel layout settings
        self.tab_threshold_slider.setValue(4)
        self.always_tab_reference.setChecked(True)
        self.always_tab_campaign.setChecked(True)
        self.always_tab_utility.setChecked(True)
        self.min_panel_width.setValue(350)
        self.min_panel_height.setValue(250)
        self.use_percentage_sizing.setChecked(True)
        self.panel_border_intensity.setValue(3)

        # Reset LLM preference
        # Set to "Automatic" (index 0)
        self.llm_preference_combo.setCurrentIndex(0) 