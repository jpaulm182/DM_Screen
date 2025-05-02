#!/usr/bin/env python3

"""
Test script for the LLM service.

This script initializes the app state and LLM service, then attempts to
make a simple call to the LLM service to verify it's working.
"""

import sys
import os
from pathlib import Path
import logging
import json

# Configure logging
logging.basicConfig(level=logging.DEBUG, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("LLM-Test")

# Add the app directory to the Python path
app_dir = Path(__file__).parent
sys.path.append(str(app_dir))

# Import the necessary modules
from app.core.app_state import AppState
from app.core.llm_service import ModelInfo

def main():
    """Main function to test the LLM service"""
    logger.info("Initializing app state...")
    app_state = AppState()
    llm_service = app_state.llm_service
    
    logger.info("Checking available models...")
    available_models = llm_service.get_available_models()
    
    if not available_models:
        logger.error("No LLM models available. Check your API keys.")
        print("API Keys:")
        openai_key = app_state.get_setting("openai_api_key") or os.getenv("OPENAI_API_KEY")
        anthropic_key = app_state.get_setting("anthropic_api_key") or os.getenv("ANTHROPIC_API_KEY")
        print(f"OpenAI API key: {'Set' if openai_key else 'Not set'}")
        print(f"Anthropic API key: {'Set' if anthropic_key else 'Not set'}")
        return 1
    
    logger.info(f"Found {len(available_models)} available models: {available_models}")
    
    # Choose a model to test with
    model_id = None
    if ModelInfo.OPENAI_GPT4O_MINI in [m['id'] for m in available_models]:
        model_id = ModelInfo.OPENAI_GPT4O_MINI
        logger.info(f"Using preferred model: {model_id}")
    elif available_models:
        model_id = available_models[0]['id']
        logger.info(f"Using fallback model: {model_id}")
    
    if not model_id:
        logger.error("No model ID could be determined.")
        return 1
    
    # Simple test prompt
    logger.info(f"Testing LLM service with model {model_id}...")
    test_prompt = "You are a D&D combat assistant. Please respond with a simple 'LLM service is working' message."
    test_messages = [{"role": "user", "content": test_prompt}]
    
    try:
        # Make the LLM call
        response = llm_service.generate_completion(
            model=model_id,
            messages=test_messages,
            temperature=0.7,
            max_tokens=100
        )
        
        logger.info(f"Response received, length: {len(response) if response else 0}")
        if response:
            print("\n=== LLM RESPONSE ===")
            print(response)
            print("===================\n")
            logger.info("LLM service test successful!")
            return 0
        else:
            logger.error("Empty response received from LLM service.")
            return 1
            
    except Exception as e:
        logger.error(f"Error testing LLM service: {e}", exc_info=True)
        return 1

if __name__ == "__main__":
    sys.exit(main()) 