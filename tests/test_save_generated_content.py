"""
Tests for saving generated content
"""

import pytest
from unittest.mock import MagicMock, patch

from app.ui.panels.rules_clarification_panel import RulesClarificationPanel
from app.ui.panels.npc_generator_panel import NPCGeneratorPanel


@pytest.fixture
def app_state():
    """Create a mock app_state for testing"""
    app_state = MagicMock()
    app_state.llm_service = MagicMock()
    app_state.llm_data_manager = MagicMock()
    # Mock the add_generated_content method to return a test ID
    app_state.llm_data_manager.add_generated_content.return_value = "test-content-id"
    return app_state


def test_rules_clarification_save(app_state):
    """Test that rules clarification uses the correct method name"""
    # Create the panel
    panel = RulesClarificationPanel(app_state)
    
    # Set up test data
    panel.current_generation = {
        "content": "Test rule content",
        "type": "rule_clarification",
        "query": "Test rule query"
    }
    panel.model_combo = MagicMock()
    panel.model_combo.currentData.return_value = "test-model"
    
    # Mock the prompt creation
    panel._create_rules_prompt = MagicMock(return_value="Test prompt")
    
    # Call the save method
    panel._save_rule()
    
    # Verify the correct method was called
    app_state.llm_data_manager.add_generated_content.assert_called_once()
    # Check the arguments
    call_args = app_state.llm_data_manager.add_generated_content.call_args[1]
    assert call_args["title"] == "Test rule query"
    assert call_args["content_type"] == "rule_clarification"
    assert call_args["content"] == "Test rule content"
    assert call_args["model_id"] == "test-model"


def test_npc_generator_save(app_state):
    """Test that NPC generator uses the correct method name"""
    # Create the panel
    panel = NPCGeneratorPanel(app_state)
    
    # Set up test data
    panel.current_generation = {
        "content": "Test NPC Name\nSome description",
        "type": "npc",
        "parameters": {"race": "Human", "role": "Merchant"}
    }
    panel.model_combo = MagicMock()
    panel.model_combo.currentData.return_value = "test-model"
    
    # Mock the prompt creation
    panel._create_npc_prompt = MagicMock(return_value="Test prompt")
    
    # Call the save method
    panel._save_npc()
    
    # Verify the correct method was called
    app_state.llm_data_manager.add_generated_content.assert_called_once()
    # Check the arguments
    call_args = app_state.llm_data_manager.add_generated_content.call_args[1]
    assert call_args["title"] == "Test NPC Name"
    assert call_args["content_type"] == "npc"
    assert call_args["content"] == "Test NPC Name\nSome description"
    assert call_args["model_id"] == "test-model"
    assert "npc" in call_args["tags"]
    assert "Human" in call_args["tags"]
    assert "Merchant" in call_args["tags"] 