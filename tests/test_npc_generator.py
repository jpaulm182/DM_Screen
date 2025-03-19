"""
Tests for the NPC Generator panel
"""

import pytest
from unittest.mock import MagicMock, patch
from PySide6.QtCore import Qt, Signal, QCoreApplication

# Import the panel class
from app.ui.panels.npc_generator_panel import NPCGeneratorPanel


@pytest.fixture
def app_state():
    """Create a mock app_state for testing"""
    app_state = MagicMock()
    app_state.llm_service = MagicMock()
    app_state.llm_data_manager = MagicMock()
    return app_state


@pytest.fixture
def npc_panel(app_state):
    """Create an NPC Generator panel for testing"""
    return NPCGeneratorPanel(app_state)


def test_npc_panel_init(npc_panel):
    """Test panel initialization"""
    # Basic initialization checks
    assert npc_panel.PANEL_TYPE == "npc_generator"
    assert npc_panel.PANEL_TITLE == "NPC Generator"
    assert npc_panel.PANEL_CATEGORY == "Campaign"
    
    # Check UI elements initialization
    assert hasattr(npc_panel, "name_input")
    assert hasattr(npc_panel, "race_combo")
    assert hasattr(npc_panel, "role_combo")
    assert hasattr(npc_panel, "generate_button")
    assert hasattr(npc_panel, "save_button")
    assert hasattr(npc_panel, "clear_button")
    assert hasattr(npc_panel, "npc_display")


def test_npc_generation_parameters(npc_panel):
    """Test parameter collection for NPC generation"""
    # Set test values
    npc_panel.name_input.setText("Test NPC")
    npc_panel.race_combo.setCurrentText("Human")
    npc_panel.male_gender.setChecked(True)
    npc_panel.role_combo.setCurrentText("Merchant")
    npc_panel.level_spinner.setValue(5)
    npc_panel.alignment_combo.setCurrentText("Chaotic Good")
    npc_panel.campaign_context.setPlainText("This is a test context")
    
    # Get parameters
    params = npc_panel._get_generation_params()
    
    # Verify parameters
    assert params["name"] == "Test NPC"
    assert params["race"] == "Human"
    assert params["gender"] == "Male"
    assert params["role"] == "Merchant"
    assert params["level"] == 5
    assert params["alignment"] == "Chaotic Good"
    assert params["context"] == "This is a test context"
    assert params["generate_stats"] is True
    assert params["add_quirk"] is True


def test_prompt_creation(npc_panel):
    """Test NPC prompt creation"""
    # Create test parameters
    params = {
        "name": "Test NPC",
        "race": "Dwarf",
        "gender": "Male",
        "role": "Blacksmith",
        "level": 3,
        "alignment": "Lawful Neutral",
        "generate_stats": True,
        "add_quirk": True,
        "context": "Mountain village setting"
    }
    
    # Create prompt
    prompt = npc_panel._create_npc_prompt(params)
    
    # Verify prompt content
    assert "Name: Test NPC" in prompt
    assert "Race: Dwarf" in prompt
    assert "Gender: Male" in prompt
    assert "Role/Occupation: Blacksmith" in prompt
    assert "Level/CR: 3" in prompt
    assert "Alignment: Lawful Neutral" in prompt
    assert "Mountain village setting" in prompt
    assert "Physical description" in prompt
    assert "Personality traits" in prompt
    assert "Background and history" in prompt
    assert "Goals and motivations" in prompt
    assert "unique quirk" in prompt
    assert "Basic D&D 5e statistics" in prompt
    assert "Format the response in markdown" in prompt


def test_clear_form(npc_panel):
    """Test form clearing functionality"""
    # Set test values
    npc_panel.name_input.setText("Test NPC")
    npc_panel.race_combo.setCurrentText("Human")
    npc_panel.male_gender.setChecked(True)
    npc_panel.role_combo.setCurrentText("Merchant")
    npc_panel.level_spinner.setValue(5)
    npc_panel.alignment_combo.setCurrentText("Chaotic Good")
    npc_panel.campaign_context.setPlainText("This is a test context")
    npc_panel.save_button.setEnabled(True)
    npc_panel.status_label.setText("Test status")
    npc_panel.status_label.setStyleSheet("color: green;")
    npc_panel.current_generation = {"test": "data"}
    
    # Clear form
    npc_panel._clear_form()
    
    # Verify form is cleared
    assert npc_panel.name_input.text() == ""
    assert npc_panel.race_combo.currentText() == "Random"
    assert npc_panel.random_gender.isChecked() is True
    assert npc_panel.role_combo.currentText() == "Random"
    assert npc_panel.level_spinner.value() == 1
    assert npc_panel.campaign_context.toPlainText() == ""
    assert npc_panel.save_button.isEnabled() is False
    assert npc_panel.status_label.text() == "Ready to generate"
    assert npc_panel.current_generation is None


def test_thread_safe_generation_handling(npc_panel, monkeypatch):
    """Test thread-safe generation handling"""
    # Mock the QMetaObject.invokeMethod to verify it's called properly
    mock_invoke = MagicMock()
    monkeypatch.setattr("app.ui.panels.npc_generator_panel.QMetaObject.invokeMethod", mock_invoke)
    
    # Call the handler with test data
    npc_panel._handle_generation_result("Test Response", None)
    
    # Verify invokeMethod was called with correct parameters
    assert mock_invoke.called
    assert mock_invoke.call_args[0][0] == npc_panel
    assert mock_invoke.call_args[0][1] == "_update_ui_with_generation_result"
    assert mock_invoke.call_args[0][2] == Qt.QueuedConnection
    
    # Test error handling
    npc_panel._handle_generation_result(None, "Test Error")
    assert mock_invoke.call_count == 2 