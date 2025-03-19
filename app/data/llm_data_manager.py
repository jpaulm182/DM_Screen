# app/data/llm_data_manager.py - LLM data management
"""
Data management for LLM-generated content

Handles storage and retrieval of conversations, generated content,
and LLM-related assets.
"""

import json
import sqlite3
import uuid
import threading
from datetime import datetime
from pathlib import Path


class LLMDataManager:
    """
    Manages storage and retrieval of LLM-generated content
    """
    
    def __init__(self, app_state):
        """Initialize the LLM data manager"""
        self.app_state = app_state
        self.db_path = app_state.data_dir / "dm_screen.db"
        self.connection = None
        self.local = threading.local()  # Thread-local storage for connections
        
        # Create LLM content directories
        self.llm_dir = app_state.data_dir / "llm"
        self.llm_dir.mkdir(exist_ok=True, parents=True)
        
        # Initialize database
        self._init_database()
    
    def _init_database(self):
        """Initialize database connection and tables"""
        # Create the main connection in the main thread
        self.connection = sqlite3.connect(str(self.db_path))
        self.connection.row_factory = sqlite3.Row
        
        # Create tables for LLM data
        self._create_tables()
    
    def _get_connection(self):
        """Get a thread-safe database connection"""
        # Check if this thread already has a connection
        if not hasattr(self.local, 'connection'):
            # Create a new connection for this thread
            self.local.connection = sqlite3.connect(str(self.db_path))
            self.local.connection.row_factory = sqlite3.Row
        
        return self.local.connection
    
    def _create_tables(self):
        """Create database tables for LLM data"""
        cursor = self.connection.cursor()
        
        # Conversations table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS llm_conversations (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            model_id TEXT NOT NULL,
            system_prompt TEXT,
            tags TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        ''')
        
        # Messages table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS llm_messages (
            id TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (conversation_id) REFERENCES llm_conversations (id) ON DELETE CASCADE
        )
        ''')
        
        # Generated content table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS llm_generated_content (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            content_type TEXT NOT NULL,
            content TEXT NOT NULL,
            model_id TEXT NOT NULL,
            prompt TEXT NOT NULL,
            tags TEXT,
            created_at TEXT NOT NULL
        )
        ''')
        
        # Create indexes
        cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_llm_messages_conversation_id 
        ON llm_messages (conversation_id)
        ''')
        
        cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_llm_generated_content_type 
        ON llm_generated_content (content_type)
        ''')
        
        # Commit changes
        self.connection.commit()
    
    def close(self):
        """Close the database connection"""
        if self.connection:
            self.connection.close()
            self.connection = None
        
        # Close any thread-local connections
        if hasattr(self.local, 'connection'):
            self.local.connection.close()
            self.local.connection = None
    
    # Conversation Methods
    
    def create_conversation(self, title, model_id, system_prompt=None, tags=None):
        """
        Create a new conversation
        
        Args:
            title: Conversation title
            model_id: ID of the model used
            system_prompt: Optional system prompt
            tags: Optional tags for filtering/categorization
            
        Returns:
            Conversation ID
        """
        conversation_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            '''
            INSERT INTO llm_conversations 
            (id, title, model_id, system_prompt, tags, created_at, updated_at) 
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                conversation_id, 
                title, 
                model_id, 
                system_prompt, 
                json.dumps(tags or []), 
                timestamp, 
                timestamp
            )
        )
        
        conn.commit()
        return conversation_id
    
    def add_message(self, conversation_id, role, content):
        """
        Add a message to a conversation
        
        Args:
            conversation_id: Conversation ID
            role: Message role ('user' or 'assistant')
            content: Message content
            
        Returns:
            Message ID
        """
        message_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            '''
            INSERT INTO llm_messages 
            (id, conversation_id, role, content, timestamp) 
            VALUES (?, ?, ?, ?, ?)
            ''',
            (message_id, conversation_id, role, content, timestamp)
        )
        
        # Update conversation's updated_at timestamp
        cursor.execute(
            '''
            UPDATE llm_conversations SET updated_at = ? WHERE id = ?
            ''',
            (timestamp, conversation_id)
        )
        
        conn.commit()
        return message_id
    
    def get_conversation(self, conversation_id):
        """
        Get conversation details
        
        Args:
            conversation_id: Conversation ID
            
        Returns:
            Dictionary with conversation details
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT * FROM llm_conversations WHERE id = ?
            ''',
            (conversation_id,)
        )
        
        row = cursor.fetchone()
        if not row:
            return None
        
        result = dict(row)
        result['tags'] = json.loads(result['tags'])
        
        return result
    
    def get_conversation_messages(self, conversation_id):
        """
        Get all messages for a conversation
        
        Args:
            conversation_id: Conversation ID
            
        Returns:
            List of message dictionaries
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT * FROM llm_messages 
            WHERE conversation_id = ? 
            ORDER BY timestamp
            ''',
            (conversation_id,)
        )
        
        return [dict(row) for row in cursor.fetchall()]
    
    def get_all_conversations(self, limit=100, offset=0, tag=None):
        """
        Get all conversations
        
        Args:
            limit: Maximum number of conversations to return
            offset: Offset for pagination
            tag: Optional tag to filter by
            
        Returns:
            List of conversation dictionaries
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        query = '''
            SELECT * FROM llm_conversations 
            ORDER BY updated_at DESC
            LIMIT ? OFFSET ?
        '''
        params = (limit, offset)
        
        if tag:
            # This is a simple implementation - for production, you'd want
            # a more robust JSON search capability
            query = '''
                SELECT * FROM llm_conversations 
                WHERE tags LIKE ? 
                ORDER BY updated_at DESC
                LIMIT ? OFFSET ?
            '''
            params = (f'%"{tag}"%', limit, offset)
        
        cursor.execute(query, params)
        
        result = []
        for row in cursor.fetchall():
            conversation = dict(row)
            conversation['tags'] = json.loads(conversation['tags'])
            result.append(conversation)
            
        return result
    
    def delete_conversation(self, conversation_id):
        """
        Delete a conversation and all its messages
        
        Args:
            conversation_id: Conversation ID
            
        Returns:
            bool: True if deleted successfully
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # Delete conversation (messages will cascade due to foreign key)
            cursor.execute(
                '''
                DELETE FROM llm_conversations WHERE id = ?
                ''',
                (conversation_id,)
            )
            
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            conn.rollback()
            print(f"Error deleting conversation: {e}")
            return False
    
    # Generated Content Methods
    
    def add_generated_content(self, title, content_type, content, model_id, prompt, tags=None):
        """
        Add generated content to the database
        
        Args:
            title: Content title/name
            content_type: Type of content (npc, location, encounter, etc.)
            content: The generated content (text or JSON string)
            model_id: ID of the model used
            prompt: The prompt used to generate the content
            tags: Optional tags for filtering/categorization
            
        Returns:
            Content ID
        """
        content_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            '''
            INSERT INTO llm_generated_content 
            (id, title, content_type, content, model_id, prompt, tags, created_at) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                content_id,
                title,
                content_type,
                content,
                model_id,
                prompt,
                json.dumps(tags or []),
                timestamp
            )
        )
        
        conn.commit()
        return content_id
    
    def get_generated_content(self, content_id):
        """
        Get specific generated content
        
        Args:
            content_id: Content ID
            
        Returns:
            Dictionary with content details
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            '''
            SELECT * FROM llm_generated_content WHERE id = ?
            ''',
            (content_id,)
        )
        
        row = cursor.fetchone()
        if not row:
            return None
        
        result = dict(row)
        result['tags'] = json.loads(result['tags'])
        
        return result
    
    def get_all_generated_content(self, content_type=None, limit=100, offset=0, tag=None):
        """
        Get all generated content, optionally filtered
        
        Args:
            content_type: Optional content type to filter by
            limit: Maximum number of items to return
            offset: Offset for pagination
            tag: Optional tag to filter by
            
        Returns:
            List of content dictionaries
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        query = '''
            SELECT * FROM llm_generated_content 
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        '''
        params = (limit, offset)
        
        if content_type:
            query = '''
                SELECT * FROM llm_generated_content 
                WHERE content_type = ? 
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            '''
            params = (content_type, limit, offset)
        
        if tag:
            # This is a simple implementation - for production, you'd want
            # a more robust JSON search capability
            if content_type:
                query = '''
                    SELECT * FROM llm_generated_content 
                    WHERE content_type = ? AND tags LIKE ? 
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                '''
                params = (content_type, f'%"{tag}"%', limit, offset)
            else:
                query = '''
                    SELECT * FROM llm_generated_content 
                    WHERE tags LIKE ? 
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                '''
                params = (f'%"{tag}"%', limit, offset)
        
        cursor.execute(query, params)
        
        result = []
        for row in cursor.fetchall():
            content = dict(row)
            content['tags'] = json.loads(content['tags'])
            result.append(content)
            
        return result
    
    def delete_generated_content(self, content_id):
        """
        Delete generated content
        
        Args:
            content_id: Content ID
            
        Returns:
            bool: True if deleted successfully
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                '''
                DELETE FROM llm_generated_content WHERE id = ?
                ''',
                (content_id,)
            )
            
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            conn.rollback()
            print(f"Error deleting content: {e}")
            return False
    
    def search_generated_content(self, query, content_type=None, limit=100, offset=0):
        """
        Search for generated content containing the query string
        
        Args:
            query: Text to search for
            content_type: Optional content type to filter by
            limit: Maximum number of items to return
            offset: Offset for pagination
            
        Returns:
            List of matching content dictionaries
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        search_params = []
        search_query = f"%{query}%"  # For LIKE operator
        
        if content_type:
            sql_query = '''
                SELECT * FROM llm_generated_content 
                WHERE (title LIKE ? OR content LIKE ?) 
                  AND content_type = ? 
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            '''
            search_params = [search_query, search_query, content_type, limit, offset]
        else:
            sql_query = '''
                SELECT * FROM llm_generated_content 
                WHERE title LIKE ? OR content LIKE ? 
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            '''
            search_params = [search_query, search_query, limit, offset]
        
        cursor.execute(sql_query, search_params)
        
        result = []
        for row in cursor.fetchall():
            content = dict(row)
            content['tags'] = json.loads(content['tags'])
            result.append(content)
            
        return result 