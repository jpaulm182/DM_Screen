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
        
        # Create campaign content directory
        self.campaign_dir = self.llm_dir / "campaigns"
        self.campaign_dir.mkdir(exist_ok=True, parents=True)
        
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
        
        # Campaign table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS llm_campaigns (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        ''')
        
        # Campaign context elements table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS llm_campaign_contexts (
            id TEXT PRIMARY KEY,
            campaign_id TEXT NOT NULL,
            element_type TEXT NOT NULL,
            name TEXT NOT NULL,
            content TEXT NOT NULL,
            priority INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (campaign_id) REFERENCES llm_campaigns (id) ON DELETE CASCADE
        )
        ''')
        
        # Content - Campaign relationship table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS llm_content_campaigns (
            content_id TEXT NOT NULL,
            campaign_id TEXT NOT NULL,
            PRIMARY KEY (content_id, campaign_id),
            FOREIGN KEY (campaign_id) REFERENCES llm_campaigns (id) ON DELETE CASCADE
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
        
        cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_llm_campaign_contexts_campaign_id 
        ON llm_campaign_contexts (campaign_id)
        ''')
        
        cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_llm_campaign_contexts_element_type 
        ON llm_campaign_contexts (element_type)
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
    
    # Campaign Context Management Methods
    
    def create_campaign(self, name, description=None):
        """
        Create a new campaign for context management
        
        Args:
            name: Campaign name
            description: Optional campaign description
            
        Returns:
            Campaign ID
        """
        campaign_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            '''
            INSERT INTO llm_campaigns 
            (id, name, description, created_at, updated_at) 
            VALUES (?, ?, ?, ?, ?)
            ''',
            (campaign_id, name, description, timestamp, timestamp)
        )
        
        conn.commit()
        
        # Create campaign directory
        campaign_path = self.campaign_dir / campaign_id
        campaign_path.mkdir(exist_ok=True)
        
        return campaign_id
    
    def get_campaign(self, campaign_id):
        """
        Get campaign details
        
        Args:
            campaign_id: Campaign ID
            
        Returns:
            Dictionary with campaign details
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT * FROM llm_campaigns WHERE id = ?
            ''',
            (campaign_id,)
        )
        
        row = cursor.fetchone()
        if not row:
            return None
        
        return dict(row)
    
    def get_all_campaigns(self):
        """
        Get all campaigns
        
        Returns:
            List of campaign dictionaries
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT * FROM llm_campaigns ORDER BY name
            '''
        )
        
        return [dict(row) for row in cursor.fetchall()]
    
    def update_campaign(self, campaign_id, name=None, description=None):
        """
        Update campaign details
        
        Args:
            campaign_id: Campaign ID
            name: New campaign name (or None to keep existing)
            description: New description (or None to keep existing)
            
        Returns:
            True if updated successfully
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Get current values
        cursor.execute(
            '''
            SELECT name, description FROM llm_campaigns WHERE id = ?
            ''',
            (campaign_id,)
        )
        
        row = cursor.fetchone()
        if not row:
            return False
        
        # Use provided values or fall back to existing values
        name = name if name is not None else row['name']
        description = description if description is not None else row['description']
        timestamp = datetime.now().isoformat()
        
        cursor.execute(
            '''
            UPDATE llm_campaigns 
            SET name = ?, description = ?, updated_at = ? 
            WHERE id = ?
            ''',
            (name, description, timestamp, campaign_id)
        )
        
        conn.commit()
        return cursor.rowcount > 0
    
    def delete_campaign(self, campaign_id):
        """
        Delete a campaign and all its context elements
        
        Args:
            campaign_id: Campaign ID
            
        Returns:
            True if deleted successfully
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Delete campaign
        cursor.execute(
            '''
            DELETE FROM llm_campaigns WHERE id = ?
            ''',
            (campaign_id,)
        )
        
        result = cursor.rowcount > 0
        conn.commit()
        
        # Delete campaign directory if it exists
        campaign_path = self.campaign_dir / campaign_id
        if campaign_path.exists():
            for file in campaign_path.glob('*'):
                file.unlink()
            campaign_path.rmdir()
        
        return result
    
    def add_context_element(self, campaign_id, element_type, name, content, priority=0):
        """
        Add a context element to a campaign
        
        Args:
            campaign_id: Campaign ID
            element_type: Type of element (e.g., 'character', 'location', 'plot')
            name: Name of the element
            content: Element content/description
            priority: Priority for context inclusion (higher = more important)
            
        Returns:
            Element ID
        """
        element_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            '''
            INSERT INTO llm_campaign_contexts 
            (id, campaign_id, element_type, name, content, priority, created_at, updated_at) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (element_id, campaign_id, element_type, name, content, priority, timestamp, timestamp)
        )
        
        # Update campaign's updated_at timestamp
        cursor.execute(
            '''
            UPDATE llm_campaigns SET updated_at = ? WHERE id = ?
            ''',
            (timestamp, campaign_id)
        )
        
        conn.commit()
        return element_id
    
    def get_context_element(self, element_id):
        """
        Get a context element
        
        Args:
            element_id: Element ID
            
        Returns:
            Dictionary with element details
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT * FROM llm_campaign_contexts WHERE id = ?
            ''',
            (element_id,)
        )
        
        row = cursor.fetchone()
        if not row:
            return None
        
        return dict(row)
    
    def update_context_element(self, element_id, name=None, content=None, priority=None):
        """
        Update a context element
        
        Args:
            element_id: Element ID
            name: New element name (or None to keep existing)
            content: New content (or None to keep existing)
            priority: New priority (or None to keep existing)
            
        Returns:
            True if updated successfully
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Get current values
        cursor.execute(
            '''
            SELECT name, content, priority, campaign_id FROM llm_campaign_contexts WHERE id = ?
            ''',
            (element_id,)
        )
        
        row = cursor.fetchone()
        if not row:
            return False
        
        # Use provided values or fall back to existing values
        name = name if name is not None else row['name']
        content = content if content is not None else row['content']
        priority = priority if priority is not None else row['priority']
        timestamp = datetime.now().isoformat()
        
        cursor.execute(
            '''
            UPDATE llm_campaign_contexts 
            SET name = ?, content = ?, priority = ?, updated_at = ? 
            WHERE id = ?
            ''',
            (name, content, priority, timestamp, element_id)
        )
        
        # Update campaign's updated_at timestamp
        cursor.execute(
            '''
            UPDATE llm_campaigns SET updated_at = ? WHERE id = ?
            ''',
            (timestamp, row['campaign_id'])
        )
        
        conn.commit()
        return cursor.rowcount > 0
    
    def delete_context_element(self, element_id):
        """
        Delete a context element
        
        Args:
            element_id: Element ID
            
        Returns:
            True if deleted successfully
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Get campaign_id first
        cursor.execute(
            '''
            SELECT campaign_id FROM llm_campaign_contexts WHERE id = ?
            ''',
            (element_id,)
        )
        
        row = cursor.fetchone()
        if not row:
            return False
        
        campaign_id = row['campaign_id']
        timestamp = datetime.now().isoformat()
        
        # Delete element
        cursor.execute(
            '''
            DELETE FROM llm_campaign_contexts WHERE id = ?
            ''',
            (element_id,)
        )
        
        result = cursor.rowcount > 0
        
        # Update campaign's updated_at timestamp
        if result:
            cursor.execute(
                '''
                UPDATE llm_campaigns SET updated_at = ? WHERE id = ?
                ''',
                (timestamp, campaign_id)
            )
        
        conn.commit()
        return result
    
    def get_campaign_context_elements(self, campaign_id, element_type=None, limit_by_priority=None):
        """
        Get context elements for a campaign
        
        Args:
            campaign_id: Campaign ID
            element_type: Optional filter by element type
            limit_by_priority: Optional limit to top N highest priority elements
            
        Returns:
            List of element dictionaries
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        query = '''
            SELECT * FROM llm_campaign_contexts 
            WHERE campaign_id = ?
        '''
        params = [campaign_id]
        
        if element_type:
            query += ' AND element_type = ?'
            params.append(element_type)
        
        query += ' ORDER BY priority DESC'
        
        if limit_by_priority is not None and isinstance(limit_by_priority, int) and limit_by_priority > 0:
            query += ' LIMIT ?'
            params.append(limit_by_priority)
        
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]
    
    def get_campaign_context_for_prompt(self, campaign_id, max_elements=10, max_tokens=2000):
        """
        Get formatted campaign context for use in LLM prompts
        
        Args:
            campaign_id: Campaign ID
            max_elements: Maximum number of context elements to include
            max_tokens: Approximate maximum tokens (characters / 4)
            
        Returns:
            Formatted context string ready for inclusion in prompts
        """
        # Get campaign details
        campaign = self.get_campaign(campaign_id)
        if not campaign:
            return ""
        
        # Get context elements sorted by priority
        elements = self.get_campaign_context_elements(campaign_id, limit_by_priority=max_elements)
        
        # Format context string
        context_parts = [f"# Campaign: {campaign['name']}"]
        if campaign['description']:
            context_parts.append(f"Campaign Description: {campaign['description']}")
        
        # Group elements by type
        element_types = {}
        for element in elements:
            element_type = element['element_type']
            if element_type not in element_types:
                element_types[element_type] = []
            element_types[element_type].append(element)
        
        # Add elements by type
        for element_type, type_elements in element_types.items():
            context_parts.append(f"\n## {element_type.title()}s:")
            for element in type_elements:
                context_parts.append(f"### {element['name']}")
                context_parts.append(element['content'])
        
        # Join all parts
        full_context = "\n".join(context_parts)
        
        # Truncate if necessary to approximate token limit
        if len(full_context) > max_tokens * 4:
            return full_context[:max_tokens * 4] + "\n\n[Context truncated due to length]"
        
        return full_context
    
    def associate_content_with_campaign(self, content_id, campaign_id):
        """
        Associate generated content with a campaign
        
        Args:
            content_id: Content ID
            campaign_id: Campaign ID
            
        Returns:
            True if association was created
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                '''
                INSERT INTO llm_content_campaigns (content_id, campaign_id)
                VALUES (?, ?)
                ''',
                (content_id, campaign_id)
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            # Association already exists or foreign key constraint failed
            return False
    
    def get_campaign_content(self, campaign_id, content_type=None, limit=100, offset=0):
        """
        Get content associated with a campaign
        
        Args:
            campaign_id: Campaign ID
            content_type: Optional filter by content type
            limit: Maximum number of items to return
            offset: Offset for pagination
            
        Returns:
            List of content items
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        query = '''
            SELECT c.* FROM llm_generated_content c
            JOIN llm_content_campaigns cc ON c.id = cc.content_id
            WHERE cc.campaign_id = ?
        '''
        params = [campaign_id]
        
        if content_type:
            query += ' AND c.content_type = ?'
            params.append(content_type)
        
        query += ' ORDER BY c.created_at DESC LIMIT ? OFFSET ?'
        params.extend([limit, offset])
        
        cursor.execute(query, params)
        
        result = []
        for row in cursor.fetchall():
            item = dict(row)
            item['tags'] = json.loads(item['tags'])
            result.append(item)
        
        return result 