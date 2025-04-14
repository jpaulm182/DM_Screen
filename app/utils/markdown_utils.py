# markdown_utils.py
# Utility for converting Markdown to HTML for use in QTextBrowser
# Uses the markdown2 library for simplicity and compatibility

import markdown2

# Convert Markdown text to HTML
# This function can be used before setting content in QTextBrowser
# to ensure clickable links and formatting are preserved.
def markdown_to_html(text: str) -> str:
    """
    Convert Markdown text to HTML for display in QTextBrowser.
    Supports standard Markdown, including [links](dnd://type/id).
    """
    # extras can be extended as needed
    return markdown2.markdown(text, extras=["fenced-code-blocks", "tables", "strike", "cuddled-lists"]) 