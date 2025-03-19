# app/core/llm_service.py - LLM service module
"""
LLM Service module for DM Screen

Provides API integrations for OpenAI GPT-4o and Anthropic Claude models.
"""

import os
import json
import time
import logging
from enum import Enum
from pathlib import Path

import openai
from openai import OpenAI
import anthropic
from PySide6.QtCore import QObject, Signal, QThreadPool, QRunnable, Slot, QMutex


class ModelProvider(Enum):
    """Enum for supported model providers"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class ModelInfo:
    """Information about available models"""
    
    # OpenAI models
    OPENAI_GPT4O = "gpt-4o"
    OPENAI_GPT4O_MINI = "gpt-4o-mini"
    
    # Anthropic models
    ANTHROPIC_CLAUDE_3_OPUS = "claude-3-opus-20240229"
    ANTHROPIC_CLAUDE_3_SONNET = "claude-3-sonnet-20240229"
    ANTHROPIC_CLAUDE_3_HAIKU = "claude-3-haiku-20240307"
    
    @classmethod
    def get_all_models(cls):
        """Get all available models"""
        return {
            ModelProvider.OPENAI: [
                {"id": cls.OPENAI_GPT4O, "name": "GPT-4o", "context_window": 128000},
                {"id": cls.OPENAI_GPT4O_MINI, "name": "GPT-4o Mini", "context_window": 128000},
            ],
            ModelProvider.ANTHROPIC: [
                {"id": cls.ANTHROPIC_CLAUDE_3_OPUS, "name": "Claude 3 Opus", "context_window": 200000},
                {"id": cls.ANTHROPIC_CLAUDE_3_SONNET, "name": "Claude 3 Sonnet", "context_window": 180000},
                {"id": cls.ANTHROPIC_CLAUDE_3_HAIKU, "name": "Claude 3 Haiku", "context_window": 150000},
            ]
        }
    
    @classmethod
    def get_provider_for_model(cls, model_id):
        """Get the provider for a specific model"""
        for provider, models in cls.get_all_models().items():
            if any(m["id"] == model_id for m in models):
                return provider
        return None


class LLMWorker(QRunnable):
    """Worker for running LLM API calls in a background thread"""
    
    def __init__(self, service, model, messages, callback, system_prompt=None, temperature=0.7, max_tokens=1000):
        """Initialize the worker"""
        super().__init__()
        self.service = service
        self.model = model
        self.messages = messages
        self.callback = callback
        self.system_prompt = system_prompt
        self.temperature = temperature
        self.max_tokens = max_tokens
    
    @Slot()
    def run(self):
        """Run the API call in a background thread"""
        try:
            response = self.service.generate_completion(
                self.model, 
                self.messages, 
                system_prompt=self.system_prompt,
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            self.callback(response, None)
        except Exception as e:
            logging.error(f"LLM API error: {str(e)}")
            self.callback(None, str(e))


class LLMService(QObject):
    """
    Service for interacting with LLM APIs
    
    Handles authentication, API calls, and response processing for
    OpenAI GPT-4o and Anthropic Claude models.
    """
    
    # Signals
    completion_ready = Signal(str, object)  # response, request_id
    completion_error = Signal(str, object)  # error message, request_id
    
    def __init__(self, app_state):
        """Initialize the LLM service"""
        super().__init__()
        self.app_state = app_state
        self.openai_client = None
        self.anthropic_client = None
        self.thread_pool = QThreadPool()
        self.mutex = QMutex()
        
        # Set up logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger("LLMService")
        
        # Initialize API clients
        self._init_clients()
    
    def _init_clients(self):
        """Initialize API clients based on available credentials"""
        # Try to get API keys from app settings first
        openai_api_key = self.app_state.get_setting("openai_api_key")
        anthropic_api_key = self.app_state.get_setting("anthropic_api_key")
        
        # Fall back to environment variables if not found in settings
        if not openai_api_key:
            openai_api_key = os.getenv("OPENAI_API_KEY")
        
        if not anthropic_api_key:
            anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        
        # Initialize clients if we have keys
        if openai_api_key:
            try:
                self.openai_client = OpenAI(api_key=openai_api_key)
                self.logger.info("OpenAI client initialized")
            except Exception as e:
                self.logger.error(f"Failed to initialize OpenAI client: {e}")
        
        if anthropic_api_key:
            try:
                self.anthropic_client = anthropic.Anthropic(api_key=anthropic_api_key)
                self.logger.info("Anthropic client initialized")
            except Exception as e:
                self.logger.error(f"Failed to initialize Anthropic client: {e}")
    
    def set_api_key(self, provider, api_key):
        """Set API key for a provider"""
        if provider == ModelProvider.OPENAI:
            self.app_state.set_setting("openai_api_key", api_key)
            try:
                self.openai_client = OpenAI(api_key=api_key)
                self.logger.info("OpenAI client updated with new API key")
                return True
            except Exception as e:
                self.logger.error(f"Failed to update OpenAI client: {e}")
                return False
        
        elif provider == ModelProvider.ANTHROPIC:
            self.app_state.set_setting("anthropic_api_key", api_key)
            try:
                self.anthropic_client = anthropic.Anthropic(api_key=api_key)
                self.logger.info("Anthropic client updated with new API key")
                return True
            except Exception as e:
                self.logger.error(f"Failed to update Anthropic client: {e}")
                return False
        
        return False
    
    def generate_completion(self, model, messages, system_prompt=None, temperature=0.7, max_tokens=1000):
        """
        Generate a completion using the specified model
        
        Args:
            model: Model ID string
            messages: List of message dictionaries (role, content)
            system_prompt: Optional system prompt
            temperature: Temperature for generation
            max_tokens: Maximum tokens to generate
            
        Returns:
            Generated text response
        """
        provider = ModelInfo.get_provider_for_model(model)
        
        if provider == ModelProvider.OPENAI:
            return self._generate_openai_completion(model, messages, system_prompt, temperature, max_tokens)
        elif provider == ModelProvider.ANTHROPIC:
            return self._generate_anthropic_completion(model, messages, system_prompt, temperature, max_tokens)
        else:
            raise ValueError(f"Unsupported model: {model}")
    
    def _generate_openai_completion(self, model, messages, system_prompt, temperature, max_tokens):
        """Generate a completion using OpenAI"""
        if not self.openai_client:
            raise ValueError("OpenAI client not initialized. Please set an API key.")
        
        # Format messages for OpenAI
        formatted_messages = []
        
        # Add system prompt if provided
        if system_prompt:
            formatted_messages.append({"role": "system", "content": system_prompt})
        
        # Add the rest of the messages
        for msg in messages:
            formatted_messages.append(msg)
        
        response = self.openai_client.chat.completions.create(
            model=model,
            messages=formatted_messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        return response.choices[0].message.content
    
    def _generate_anthropic_completion(self, model, messages, system_prompt, temperature, max_tokens):
        """Generate a completion using Anthropic"""
        if not self.anthropic_client:
            raise ValueError("Anthropic client not initialized. Please set an API key.")
        
        # Format system prompt
        system = system_prompt if system_prompt else ""
        
        # Format messages for Anthropic
        formatted_messages = []
        for msg in messages:
            role = "assistant" if msg["role"] == "assistant" else "user"
            formatted_messages.append({"role": role, "content": msg["content"]})
        
        response = self.anthropic_client.messages.create(
            model=model,
            system=system,
            messages=formatted_messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        return response.content[0].text
    
    def generate_completion_async(self, model, messages, callback, system_prompt=None, temperature=0.7, max_tokens=1000):
        """
        Generate a completion asynchronously
        
        Args:
            model: Model ID string
            messages: List of message dictionaries (role, content)
            callback: Function to call with result
            system_prompt: Optional system prompt
            temperature: Temperature for generation
            max_tokens: Maximum tokens to generate
        """
        worker = LLMWorker(
            self, model, messages, callback, system_prompt, temperature, max_tokens
        )
        self.thread_pool.start(worker)
    
    def is_provider_available(self, provider):
        """Check if a specific provider is available
        
        Args:
            provider (ModelProvider): The provider to check
            
        Returns:
            bool: True if the provider is available, False otherwise
        """
        if provider == ModelProvider.OPENAI:
            return self.openai_client is not None
        elif provider == ModelProvider.ANTHROPIC:
            return self.anthropic_client is not None
        return False
    
    def get_available_models(self):
        """Get list of available models based on initialized clients"""
        result = []
        
        all_models = ModelInfo.get_all_models()
        
        if self.is_provider_available(ModelProvider.OPENAI):
            result.extend(all_models[ModelProvider.OPENAI])
        
        if self.is_provider_available(ModelProvider.ANTHROPIC):
            result.extend(all_models[ModelProvider.ANTHROPIC])
        
        return result 