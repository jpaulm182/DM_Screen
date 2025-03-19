"""
Test script for LLM service and data manager

This script tests basic functionality of the LLM service and data manager components.
"""

import sys
import os
from pathlib import Path
import pytest
import json
import logging
import time

# Set up logging
logging.basicConfig(level=logging.INFO)

# Add app directory to path
app_dir = Path(__file__).parent.parent
sys.path.append(str(app_dir))

# Import app modules
from app.core.app_state import AppState
from app.core.llm_service import LLMService, ModelProvider, ModelInfo
from app.data.llm_data_manager import LLMDataManager


class TestAppState:
    """Test class for AppState that provides a minimal implementation"""
    
    def __init__(self):
        self.app_dir = Path("./test_data")
        self.data_dir = self.app_dir / "data"
        self.config_dir = self.app_dir / "config"
        self.settings = {}
        
        # Ensure directories exist
        self.app_dir.mkdir(exist_ok=True)
        self.data_dir.mkdir(exist_ok=True)
        self.config_dir.mkdir(exist_ok=True)
    
    def get_setting(self, key, default=None):
        return self.settings.get(key, default)
    
    def set_setting(self, key, value):
        self.settings[key] = value
        return True


@pytest.fixture
def app_state():
    """Create a test app state"""
    state = TestAppState()
    return state


@pytest.fixture
def llm_data_manager(app_state):
    """Create a test LLM data manager"""
    manager = LLMDataManager(app_state)
    yield manager
    manager.close()


@pytest.fixture
def llm_service(app_state):
    """Create a test LLM service"""
    service = LLMService(app_state)
    return service


def test_data_manager_init(llm_data_manager):
    """Test LLM data manager initialization"""
    assert llm_data_manager is not None
    assert llm_data_manager.connection is not None


def test_create_conversation(llm_data_manager):
    """Test creating a conversation"""
    conversation_id = llm_data_manager.create_conversation(
        "Test Conversation",
        ModelInfo.OPENAI_GPT4O,
        system_prompt="You are a helpful assistant.",
        tags=["test", "demo"]
    )
    assert conversation_id is not None
    
    # Verify conversation exists
    conversation = llm_data_manager.get_conversation(conversation_id)
    assert conversation is not None
    assert conversation["title"] == "Test Conversation"
    assert conversation["model_id"] == ModelInfo.OPENAI_GPT4O
    assert conversation["system_prompt"] == "You are a helpful assistant."
    assert "test" in conversation["tags"]
    assert "demo" in conversation["tags"]


def test_add_message(llm_data_manager):
    """Test adding messages to a conversation"""
    # Create a conversation
    conversation_id = llm_data_manager.create_conversation(
        "Message Test",
        ModelInfo.OPENAI_GPT4O
    )
    
    # Add user message
    user_message_id = llm_data_manager.add_message(
        conversation_id,
        "user",
        "Hello, how are you?"
    )
    assert user_message_id is not None
    
    # Add assistant message
    assistant_message_id = llm_data_manager.add_message(
        conversation_id,
        "assistant",
        "I'm doing well, thanks for asking!"
    )
    assert assistant_message_id is not None
    
    # Get conversation messages
    messages = llm_data_manager.get_conversation_messages(conversation_id)
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "Hello, how are you?"
    assert messages[1]["role"] == "assistant"
    assert messages[1]["content"] == "I'm doing well, thanks for asking!"


def test_service_init(llm_service):
    """Test LLM service initialization"""
    assert llm_service is not None


def test_provider_detection(llm_service):
    """Test provider detection for models"""
    openai_provider = ModelInfo.get_provider_for_model(ModelInfo.OPENAI_GPT4O)
    assert openai_provider == ModelProvider.OPENAI
    
    anthropic_provider = ModelInfo.get_provider_for_model(ModelInfo.ANTHROPIC_CLAUDE_3_HAIKU)
    assert anthropic_provider == ModelProvider.ANTHROPIC


def test_api_key_setting(llm_service, app_state):
    """Test setting API keys"""
    # Skip test if no OPENAI_API_KEY in environment
    openai_key = os.environ.get("OPENAI_API_KEY")
    if not openai_key:
        pytest.skip("OPENAI_API_KEY not set in environment")
    
    # Set API key
    result = llm_service.set_api_key(ModelProvider.OPENAI, openai_key)
    assert result is True
    
    # Check if provider is available
    assert llm_service.is_provider_available(ModelProvider.OPENAI) is True


if __name__ == "__main__":
    """Run tests directly"""
    # Create app state
    state = TestAppState()
    
    # Create data manager
    data_manager = LLMDataManager(state)
    
    # Test conversation creation
    conversation_id = data_manager.create_conversation(
        "Direct Test",
        ModelInfo.OPENAI_GPT4O,
        system_prompt="You are a helpful assistant."
    )
    print(f"Created conversation: {conversation_id}")
    
    # Test message addition
    message_id = data_manager.add_message(
        conversation_id,
        "user",
        "Hello, what can you help me with?"
    )
    print(f"Added message: {message_id}")
    
    # Get conversation
    conversation = data_manager.get_conversation(conversation_id)
    print(f"Conversation: {json.dumps(conversation, indent=2)}")
    
    # Get messages
    messages = data_manager.get_conversation_messages(conversation_id)
    print(f"Messages: {json.dumps(messages, indent=2)}")
    
    # Clean up
    data_manager.close()
    print("Tests completed successfully") 