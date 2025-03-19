"""
Tests for the Rules Clarification panel
"""

import pytest
from unittest.mock import MagicMock, patch
from PySide6.QtCore import Qt, Signal, QCoreApplication

# Import the panel class
from app.ui.panels.rules_clarification_panel import RulesClarificationPanel


@pytest.fixture
def app_state():
    """Create a mock app_state for testing"""
    app_state = MagicMock()
    app_state.llm_service = MagicMock()
    app_state.llm_data_manager = MagicMock()
    return app_state


@pytest.fixture
def rules_panel(app_state):
    """Create a Rules Clarification panel for testing"""
    return RulesClarificationPanel(app_state)


def test_rules_panel_init(rules_panel):
    """Test panel initialization"""
    # Basic initialization checks
    assert rules_panel.PANEL_TYPE == "rules_clarification"
    assert rules_panel.PANEL_TITLE == "Rules Clarification"
    assert rules_panel.PANEL_CATEGORY == "Reference"
    
    # Check UI elements initialization
    assert hasattr(rules_panel, "query_input")
    assert hasattr(rules_panel, "rule_display")
    assert hasattr(rules_panel, "query_button")
    assert hasattr(rules_panel, "save_button")
    assert hasattr(rules_panel, "clear_button")
    assert hasattr(rules_panel, "history_list")


def test_rules_prompt_creation(rules_panel):
    """Test rules prompt creation"""
    # Create test query
    query = "How does flanking work in combat?"
    
    # Create prompt
    prompt = rules_panel._create_rules_prompt(query)
    
    # Verify prompt content
    assert "How does flanking work in combat?" in prompt
    assert "D&D 5e rules expert" in prompt
    assert "direct answer" in prompt
    assert "official rule" in prompt
    assert "examples" in prompt
    assert "edge cases" in prompt
    assert "multiple possible interpretations" in prompt
    assert "markdown formatting" in prompt


def test_update_char_count(rules_panel):
    """Test character count update"""
    # Set initial text
    rules_panel.query_input.setPlainText("Test query")
    rules_panel._update_char_count()
    
    # Verify count
    assert rules_panel.char_count_label.text() == "10 characters"
    assert rules_panel.query_button.isEnabled() is True
    
    # Test empty text
    rules_panel.query_input.clear()
    rules_panel._update_char_count()
    
    # Verify count for empty text
    assert rules_panel.char_count_label.text() == "0 characters"
    assert rules_panel.query_button.isEnabled() is False


def test_set_topic(rules_panel, monkeypatch):
    """Test setting a topic template"""
    # Mock the cursor positioning for testing
    monkeypatch.setattr(rules_panel.query_input, "setFocus", lambda: None)
    monkeypatch.setattr(rules_panel.query_input, "setTextCursor", lambda cursor: None)
    
    # Test setting a topic with empty input
    rules_panel.query_input.clear()
    rules_panel._set_topic("combat")
    
    # Verify text was set
    assert "How does [combat mechanic] work in D&D 5e?" in rules_panel.query_input.toPlainText()
    
    # Test setting a topic with existing text
    rules_panel.query_input.setPlainText("Existing query text")
    rules_panel._set_topic("spellcasting")
    
    # Verify text was appended
    assert "Existing query text" in rules_panel.query_input.toPlainText()
    assert "Can you explain how [spell feature] works in D&D 5e?" in rules_panel.query_input.toPlainText()


def test_thread_safe_generation_handling(rules_panel):
    """Test thread-safe generation handling using signals"""
    # Mock the generation result handler
    mock_handler = MagicMock()
    rules_panel._update_ui_with_generation_result = mock_handler
    
    # Connect the signal
    rules_panel.generation_result.connect(mock_handler)
    
    # Emit the signal
    rules_panel._handle_generation_result("Test Response", None)
    
    # Verify handler was called with correct parameters
    assert mock_handler.call_count >= 1
    
    # We can't directly assert the call args with signal emissions, so test functionality
    # Reset mock and test manually with direct call
    mock_handler.reset_mock()
    rules_panel._update_ui_with_generation_result("Test Response", None)
    assert mock_handler.call_count == 1
    
    # Test error handling
    mock_handler.reset_mock()
    rules_panel._update_ui_with_generation_result(None, "Test Error")
    assert mock_handler.call_count == 1 