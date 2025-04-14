# link_handler.py
# Utility for handling dnd:// links in QTextBrowser
# This function should be called from anchorClicked handlers in panels

from PySide6.QtCore import QUrl
from app.ui.dialogs.detail_dialog import DetailDialog

# In a real implementation, you would check a database or data manager for stored content
# For now, this is a stub that always opens a dialog with placeholder content

def handle_dnd_link(parent, url: QUrl, app_state):
    """
    Handle dnd:// links. Parse the type and id, check for stored content, and open a detail dialog.
    """
    if url.scheme() != "dnd":
        return
    
    # Example: dnd://npc/Bartender_Joren
    path = url.path().lstrip("/")
    if not path:
        return
    
    # Split type and id
    if "/" in path:
        element_type, element_id = path.split("/", 1)
    elif "-" in path:
        element_type, element_id = path.split("-", 1)
    else:
        element_type, element_id = "unknown", path
    
    # TODO: Check for stored content using app_state.llm_data_manager or similar
    # For now, always show a placeholder dialog
    player_content = f"<p>Player-facing info for <b>{element_id.replace('_', ' ')}</b> ({element_type})</p>"
    dm_content = f"<p>DM-only info for <b>{element_id.replace('_', ' ')}</b> ({element_type})</p>"
    
    dialog = DetailDialog(parent, element_id.replace('_', ' '), player_content, dm_content)
    dialog.exec()

def generate_entity_from_selection(parent, llm_service, selected_text, entity_type, context, callback):
    """
    Generate an entity using the LLM given selected text, entity type, and context.
    Calls the callback(result, error) when done.
    """
    # Build a minimal prompt
    context_str = ""
    if isinstance(context, dict):
        # Use name/title and description if available
        name = context.get("name") or context.get("title")
        desc = context.get("description") or context.get("content")
        if name:
            context_str += f"Name/Title: {name}\n"
        if desc:
            context_str += f"Description: {desc}\n"
    elif isinstance(context, str):
        context_str = context
    
    prompt = (
        f"Generate a {entity_type} for a D&D 5e campaign.\n"
        f"Name or description: \"{selected_text}\"\n"
        f"Context: {context_str}\n"
        "Output JSON with 'player_description' and 'dm_description' fields."
    )
    
    # Get an available model from the LLM service
    available_models = llm_service.get_available_models()
    model_id = None
    
    if available_models:
        # Try to use the default model from settings if available
        from app.core.llm_service import ModelInfo
        default_model = None
        
        # First check if we have a saved default model in settings
        if hasattr(llm_service, 'app_state'):
            default_model = llm_service.app_state.get_setting("default_llm_model")
            
        # If default model is set and available, use it
        if default_model and any(m["id"] == default_model for m in available_models):
            model_id = default_model
        else:
            # Otherwise prefer OpenAI GPT-4.1 or Claude 3 Sonnet if available
            for m in available_models:
                if m["id"] == ModelInfo.OPENAI_GPT4O:
                    model_id = m["id"]
                    break
                elif m["id"] == ModelInfo.ANTHROPIC_CLAUDE_3_SONNET:
                    model_id = m["id"]
                    break
            
            # If neither preferred model is available, use the first available model
            if model_id is None and available_models:
                model_id = available_models[0]["id"]
    
    # Call the LLM asynchronously
    llm_service.generate_completion_async(
        model=model_id,  # Use the selected model instead of None
        messages=[{"role": "user", "content": prompt}],
        callback=callback,
        temperature=0.7,
        max_tokens=800
    ) 