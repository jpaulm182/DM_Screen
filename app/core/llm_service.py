# app/core/llm_service.py - LLM service module
"""
LLM Service module for DM Screen

Provides API integrations for OpenAI GPT-4.1-mini (preferred) and Anthropic Claude models.
"""

import os
import json
import time
import logging
from enum import Enum
from pathlib import Path
import base64
import uuid
import hashlib

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
    OPENAI_GPT4O = "gpt-4.1"
    OPENAI_GPT4O_MINI = "gpt-4.1-mini"
    
    # Anthropic models
    ANTHROPIC_CLAUDE_3_OPUS = "claude-3-opus-20240229"
    ANTHROPIC_CLAUDE_3_SONNET = "claude-3-sonnet-20240229"
    ANTHROPIC_CLAUDE_3_HAIKU = "claude-3-haiku-20240307"
    
    @classmethod
    def get_all_models(cls):
        """Get all available models"""
        return {
            ModelProvider.OPENAI: [
                {"id": cls.OPENAI_GPT4O, "name": "GPT-4.1", "context_window": 128000},
                {"id": cls.OPENAI_GPT4O_MINI, "name": "GPT-4.1 Mini", "context_window": 128000},
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
    
    def __init__(self, service, model, messages, system_prompt=None, temperature=0.7, max_tokens=1000, request_id=None):
        """Initialize the worker"""
        super().__init__()
        self.service = service
        self.model = model
        self.messages = messages
        self.system_prompt = system_prompt
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.request_id = request_id
    
    @Slot()
    def run(self):
        """Run the API call in a background thread"""
        try:
            try:
                response = self.service.generate_completion(
                    self.model, 
                    self.messages, 
                    system_prompt=self.system_prompt,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens
                )
                logging.info(f"LLM generation completed. Response length: {len(response) if response else 0}")
                logging.debug(f"Full response content: {response}")
                print(f"[DEBUG] Emitting completion_ready with response: {repr(response)} from LLMService id: {id(self.service)}", flush=True)
                self.service.completion_ready.emit(response, self.request_id)
            except Exception as e:
                logging.error(f"LLM API error: {str(e)}", exc_info=True)
                print(f"[DEBUG] Exception in LLMWorker.run: {e}", flush=True)
                self.service.completion_error.emit(str(e), self.request_id)
        except Exception as outer_e:
            print(f"[DEBUG] Outer exception in LLMWorker.run: {outer_e}", flush=True)


class LLMService(QObject):
    """
    Service for interacting with LLM APIs
    
    Handles authentication, API calls, and response processing for
    OpenAI GPT-4.1-mini (preferred) and Anthropic Claude models.
    """
    
    # Signals
    completion_ready = Signal(str, object)  # response, request_id
    completion_error = Signal(str, object)  # error message, request_id
    
    def __init__(self, app_state):
        """Initialize the LLM service"""
        super().__init__()
        print(f"[DEBUG] LLMService instance created: {id(self)}", flush=True)
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
        
        # Ensure image directory exists
        self.monster_images_dir = self.app_state.app_dir / "data" / "monster_images"
        self.monster_images_dir.mkdir(parents=True, exist_ok=True)
    
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
        print(f"[DEBUG] generate_completion called on LLMService id: {id(self)} with model: {model}", flush=True)
        provider = ModelInfo.get_provider_for_model(model)
        if provider == ModelProvider.OPENAI:
            result = self._generate_openai_completion(model, messages, system_prompt, temperature, max_tokens)
            print(f"[DEBUG] generate_completion returning from _generate_openai_completion: {repr(result)}", flush=True)
            return result
        elif provider == ModelProvider.ANTHROPIC:
            result = self._generate_anthropic_completion(model, messages, system_prompt, temperature, max_tokens)
            print(f"[DEBUG] generate_completion returning from _generate_anthropic_completion: {repr(result)}", flush=True)
            return result
        else:
            raise ValueError(f"Unsupported model: {model}")
    
    def _generate_openai_completion(self, model, messages, system_prompt, temperature, max_tokens):
        """Generate a completion using OpenAI"""
        print(f"[DEBUG] _generate_openai_completion called with model: {model}", flush=True)
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
        
        try:
            self.logger.info(f"Sending request to OpenAI API. Model: {model}, Messages count: {len(formatted_messages)}")
            
            response = self.openai_client.chat.completions.create(
                model=model,
                messages=formatted_messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            # Check if we have a valid response with choices
            if not response or not hasattr(response, 'choices') or not response.choices:
                self.logger.error(f"Invalid response format from OpenAI: {response}")
                raise ValueError("Invalid response format from OpenAI")
                
            # Check if the first choice has a message with content
            if not hasattr(response.choices[0], 'message') or not hasattr(response.choices[0].message, 'content'):
                self.logger.error(f"Missing message content in OpenAI response: {response.choices}")
                raise ValueError("Missing message content in OpenAI response")
                
            content = response.choices[0].message.content
            
            # Check if content is empty or None
            if not content:
                self.logger.warning("Received empty content from OpenAI API")
                print(f"[DEBUG] _generate_openai_completion got empty content", flush=True)
                return ""  # Return empty string instead of None
                
            self.logger.info(f"Received valid response from OpenAI. Content length: {len(content)}")
            print(f"[DEBUG] _generate_openai_completion returning content: {repr(content)}", flush=True)
            return content
            
        except Exception as e:
            self.logger.error(f"Error calling OpenAI API: {str(e)}", exc_info=True)
            print(f"[DEBUG] Exception in _generate_openai_completion: {e}", flush=True)
            raise
    
    def _generate_anthropic_completion(self, model, messages, system_prompt, temperature, max_tokens):
        """Generate a completion using Anthropic"""
        print(f"[DEBUG] _generate_anthropic_completion called with model: {model}", flush=True)
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
        
        result = response.content[0].text
        print(f"[DEBUG] _generate_anthropic_completion returning content: {repr(result)}", flush=True)
        return result
    
    def generate_completion_async(self, model, messages, system_prompt=None, temperature=0.7, max_tokens=1000):
        """
        Generate a completion asynchronously
        
        Args:
            model: Model ID string
            messages: List of message dictionaries (role, content)
            system_prompt: Optional system prompt
            temperature: Temperature for generation
            max_tokens: Maximum tokens to generate
        """
        worker = LLMWorker(
            self, model, messages, system_prompt, temperature, max_tokens
        )
        print(f"[DEBUG] generate_completion_async called on LLMService id: {id(self)}, starting worker id: {id(worker)}", flush=True)
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

    def generate_text(self, prompt, model=None, system_prompt=None, temperature=0.7, max_tokens=1000):
        """
        Generate text from a single prompt string
        
        Args:
            prompt (str): The prompt text
            model (str, optional): Model to use. If None, uses the default model logic.
            system_prompt (str, optional): System prompt to use.
            temperature (float, optional): Temperature for generation.
            max_tokens (int, optional): Maximum tokens to generate.
            
        Returns:
            str: Generated text
        """
        # If a specific model is requested, use it
        if model:
            self.logger.info(f"Using explicitly requested model: {model}")
            target_model = model
        else:
            # Check for user preference
            preferred_model = self.app_state.get_setting("preferred_llm_model")
            available_models = self.get_available_models()
            available_model_ids = [m["id"] for m in available_models]

            if preferred_model and preferred_model in available_model_ids:
                self.logger.info(f"Using preferred model from settings: {preferred_model}")
                target_model = preferred_model
            else:
                # Default logic: Prefer Mini, then fallback
                if not available_models:
                    self.logger.error("No LLM models available. Please set up API keys.")
                    raise ValueError("No LLM models available. Please set up API keys.")
                
                # Prefer OpenAI GPT-4.1 Mini if available
                if ModelInfo.OPENAI_GPT4O_MINI in available_model_ids:
                    target_model = ModelInfo.OPENAI_GPT4O_MINI
                    self.logger.info(f"Using default model: {target_model}")
                # Fallback to GPT-4.1 if Mini isn't available but GPT-4.1 is
                elif ModelInfo.OPENAI_GPT4O in available_model_ids:
                     target_model = ModelInfo.OPENAI_GPT4O
                     self.logger.info(f"Using fallback default model (GPT-4.1): {target_model}")
                # Fallback to Anthropic Sonnet if available
                elif ModelInfo.ANTHROPIC_CLAUDE_3_SONNET in available_model_ids:
                     target_model = ModelInfo.ANTHROPIC_CLAUDE_3_SONNET
                     self.logger.info(f"Using fallback default model (Sonnet): {target_model}")
                # Finally, use the first available model
                else:
                     target_model = available_model_ids[0]
                     self.logger.info(f"Using first available model as default: {target_model}")

        # Create a simple message array with the prompt as user input
        messages = [{"role": "user", "content": prompt}]
        
        # Generate the completion using the determined target model
        return self.generate_completion(target_model, messages, system_prompt, temperature, max_tokens)

    def generate_image(self, prompt, output_path=None, monster_id=None, size="1024x1024"):
        """Generate an image using OpenAI DALL-E (potentially via GPT-4.1-Mini interface)"""
        if not self.openai_client:
            self.logger.error("OpenAI client not initialized. Please set an API key.")
            return None
            
        try:
            self.logger.info(f"Generating image for prompt: {prompt}")
            
            # Format the prompt for D&D Monster Manual style
            enhanced_prompt = (
                f"A D&D Monster Manual style illustration of {prompt}. "
                f"Use the exact iconic art style from the official 5th Edition D&D Monster Manual: "
                f"detailed professional fantasy illustration with a dynamic pose against a subtle neutral background. "
                f"Clean ink lines with watercolor-style coloring, slightly desaturated fantasy art, heroic proportions. "
                f"Include a slight drop shadow beneath the monster to ground it. "
                f"The full creature should be visible and centered, with dramatic lighting. "
                f"The art should look like it belongs on an official D&D Monster Manual page."
            )
            
            # Remove potentially problematic words and phrases
            problematic_words = [
                "terrifying", "scary", "fearsome", "evil", "demonic", "satanic", 
                "bloody", "gore", "violent", "dead", "savage", "ferocious", 
                "predator", "attack", "kill", "destroy", "dangerous", "threatening"
            ]
            for word in problematic_words:
                enhanced_prompt = enhanced_prompt.replace(word, "")
            
            # Clean up any double spaces that might have been created
            enhanced_prompt = " ".join(enhanced_prompt.split())
            
            # Generate image
            try:
                response = self.openai_client.images.generate(
                    model="dall-e-3",
                    prompt=enhanced_prompt,
                    size=size,
                    quality="standard",
                    n=1,
                    response_format="b64_json"
                )
            except Exception as api_error:
                # If there's a content policy violation, try a more sanitized prompt
                if "content_policy_violation" in str(api_error):
                    self.logger.warning(f"Content policy violation, trying more generic prompt for: {prompt}")
                    # Try with a more generic prompt based only on the creature type
                    safe_creature_type = prompt.split(',')[0] if ',' in prompt else prompt
                    # Make a safe prompt that still maintains D&D Monster Manual style
                    safe_prompt = (
                        f"A fantasy illustration of a {safe_creature_type} in the style of the D&D Monster Manual. "
                        f"Official Dungeons and Dragons art style, professional fantasy illustration, clean lines, "
                        f"watercolor-style coloring. Child-friendly, non-threatening."
                    )
                    
                    response = self.openai_client.images.generate(
                        model="dall-e-3",
                        prompt=safe_prompt,
                        size=size,
                        quality="standard",
                        n=1,
                        response_format="b64_json"
                    )
                else:
                    # Re-raise if it's not a content policy violation
                    raise
            
            # Get the base64-encoded image data
            image_data = response.data[0].b64_json
            revised_prompt = response.data[0].revised_prompt
            
            self.logger.debug(f"Image generated with revised prompt: {revised_prompt}")
            
            # Determine output path if not provided
            if not output_path:
                # Sanitize filename creation
                base_filename = "monster"
                # Check if monster_id is a simple type (int, str) and reasonably short
                if isinstance(monster_id, (int, str)) and len(str(monster_id)) < 50:
                     # Use monster_id if it's simple and short
                     base_filename = f"monster_{monster_id}"
                else:
                     # Otherwise, use a UUID to guarantee a valid length
                     base_filename = f"monster_{uuid.uuid4()}"
                     # Log a warning if monster_id was unusable (and not None)
                     if monster_id is not None:
                         self.logger.warning(f"Monster ID '{monster_id}' was unsuitable for filename, using UUID instead.")

                filename = f"{base_filename}.png"
                output_path = self.monster_images_dir / filename
            else:
                output_path = Path(output_path)
                
            # Ensure the directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Save image
            with open(output_path, "wb") as f:
                f.write(base64.b64decode(image_data))
                
            self.logger.info(f"Image saved to {output_path}")
            return str(output_path)
            
        except Exception as e:
            self.logger.error(f"Error generating image: {e}", exc_info=True)
            return None
            
    def generate_image_async(self, prompt, callback, output_path=None, monster_id=None, size="1024x1024"):
        """
        Generate an image asynchronously
        
        Args:
            prompt (str): The image generation prompt
            callback (callable): Function to call with result (path_to_image, error)
            output_path (str or Path, optional): Path to save the image to
            monster_id (int, optional): ID of the monster for naming the file
            size (str, optional): Image size
        """
        def run_in_thread():
            try:
                path = self.generate_image(prompt, output_path, monster_id, size)
                callback(path, None)
            except Exception as e:
                self.logger.error(f"Error in async image generation: {e}", exc_info=True)
                callback(None, str(e))
                
        # Run in thread pool
        self.thread_pool.start(QRunnable.create(run_in_thread)) 