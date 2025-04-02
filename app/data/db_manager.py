# app/data/db_manager.py - Database manager
"""
Database manager for the DM Screen application

Handles database connections, schema management, and common queries.
"""

import os
import sqlite3
from datetime import datetime, timezone
import json
import random
from pathlib import Path
from typing import List, Optional, Dict, Any

from app.core.config import get_database_path
from app.core.models.monster import Monster


class DatabaseManager:
    """
    Manages database connections and operations for the application
    """
    
    def __init__(self, app_state):
        """Initialize the database manager"""
        self.app_state = app_state
        self.db_path = get_database_path()
        self.connection = None
        
        # Initialize the database
        self._init_database()
    
    def _init_database(self):
        """Initialize the database and tables"""
        # Ensure data directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        # Connect to the database
        self.connection = sqlite3.connect(str(self.db_path))
        self.connection.row_factory = sqlite3.Row
        
        # Create tables if they don't exist
        self._create_tables()
    
    def _create_tables(self):
        """Create database tables if they don't exist"""
        cursor = self.connection.cursor()
        
        # Create reference tables
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS spells (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            level INTEGER NOT NULL,
            school TEXT NOT NULL,
            casting_time TEXT NOT NULL,
            range TEXT NOT NULL,
            components TEXT NOT NULL,
            duration TEXT NOT NULL,
            description TEXT NOT NULL,
            class TEXT NOT NULL,
            source TEXT NOT NULL
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS conditions (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT NOT NULL
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS monsters (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            cr TEXT NOT NULL,
            size TEXT NOT NULL,
            alignment TEXT NOT NULL,
            ac INTEGER NOT NULL,
            hp TEXT NOT NULL,
            speed TEXT NOT NULL,
            str INTEGER NOT NULL,
            dex INTEGER NOT NULL,
            con INTEGER NOT NULL,
            int INTEGER NOT NULL,
            wis INTEGER NOT NULL,
            cha INTEGER NOT NULL,
            skills TEXT,
            senses TEXT,
            languages TEXT,
            traits TEXT,
            actions TEXT,
            legendary_actions TEXT,
            description TEXT,
            source TEXT NOT NULL
        )
        ''')
        
        # Create tables for user content
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS custom_monsters (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            data TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS encounters (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            data TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS npcs (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            data TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS session_notes (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            tags TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS custom_tables (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            data TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        ''')
        
        # Commit the changes
        self.connection.commit()
    
    def close(self):
        """Close the database connection"""
        if self.connection:
            self.connection.close()
    
    def execute_query(self, query, parameters=None):
        """
        Execute a query and return all results
        
        Args:
            query: SQL query string
            parameters: Optional parameters for the query
            
        Returns:
            List of query results as dictionaries
        """
        cursor = self.connection.cursor()
        
        if parameters:
            cursor.execute(query, parameters)
        else:
            cursor.execute(query)
        
        # Convert results to dictionaries
        results = [dict(row) for row in cursor.fetchall()]
        return results
    
    def execute_update(self, query, parameters=None):
        """
        Execute an update query
        
        Args:
            query: SQL query string
            parameters: Optional parameters for the query
            
        Returns:
            Number of affected rows
        """
        cursor = self.connection.cursor()
        
        if parameters:
            cursor.execute(query, parameters)
        else:
            cursor.execute(query)
        
        self.connection.commit()
        return cursor.rowcount
    
    def insert(self, table, data):
        """
        Insert data into a table
        
        Args:
            table: Table name
            data: Dictionary of column:value pairs
            
        Returns:
            ID of the inserted row, or None on failure
        """
        # Ensure connection is available
        if not self.connection:
            print("Error: Database connection is not available.")
            return None
        try:
            columns = ", ".join(data.keys())
            placeholders = ", ".join(["?"] * len(data))
            values = list(data.values())
            
            query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
            
            cursor = self.connection.cursor()
            cursor.execute(query, values)
            self.connection.commit()
            
            # Get the last row ID
            row_id = cursor.lastrowid
            
            # Handle cases where lastrowid might be None (less common with SQLite autoinc PK)
            if row_id is None:
                print(f"Warning: lastrowid is None after insertion into {table}. Attempting retrieval.")
                # For tables with an explicit integer primary key often named 'id'
                # This assumes the primary key is 'id' and is auto-incrementing
                # A more robust approach might be needed if PK names vary or aren't integers
                if 'id' in data: # If we provided an ID (less likely for autoinc)
                    # Try to select based on what we inserted (best guess)
                    conditions = " AND ".join([f"{col} = ?" for col in data.keys()])
                    select_query = f"SELECT id FROM {table} WHERE {conditions} ORDER BY id DESC LIMIT 1" # Get the latest match
                    cursor.execute(select_query, values)
                else:
                    # If no ID provided, rely on SQLite's special function
                    select_query = "SELECT last_insert_rowid()"
                    cursor.execute(select_query)

                result = cursor.fetchone()
                if result and result[0] is not None:
                    row_id = result[0]
                    print(f"Retrieved ID: {row_id}")
                else:
                    print(f"Error: Could not retrieve last inserted ID for table {table}.")
                    return None # Indicate failure
            
            return row_id
        except sqlite3.Error as e:
            print(f"Database error during insert into {table}: {e}")
            # Consider rolling back if applicable, though commit is inside try
            return None
        except Exception as e:
            print(f"An unexpected error occurred during insert: {e}")
            return None
    
    def update(self, table, data, where_clause, where_params=None):
        """
        Update data in a table
        
        Args:
            table: Table name
            data: Dictionary of column:value pairs for the SET clause
            where_clause: SQL WHERE clause (e.g., "id = ?")
            where_params: Optional parameters for the WHERE clause
            
        Returns:
            Number of affected rows, or None on failure
        """
        # Ensure connection is available
        if not self.connection:
            print("Error: Database connection is not available.")
            return None
        try:
            set_clause = ", ".join([f"{col} = ?" for col in data.keys()])
            values = list(data.values())
            
            query = f"UPDATE {table} SET {set_clause} WHERE {where_clause}"
            
            all_params = values + list(where_params if where_params is not None else [])
            
            return self.execute_update(query, tuple(all_params))
        except sqlite3.Error as e:
            print(f"Database error during update on {table}: {e}")
            return None
        except Exception as e:
            print(f"An unexpected error occurred during update: {e}")
            return None
    
    def delete(self, table, where_clause, where_params=None):
        """
        Delete data from a table
        
        Args:
            table: Table name
            where_clause: SQL WHERE clause (e.g., "id = ?")
            where_params: Optional parameters for the WHERE clause
            
        Returns:
            Number of affected rows, or None on failure
        """
        # Ensure connection is available
        if not self.connection:
            print("Error: Database connection is not available.")
            return None
        try:
            query = f"DELETE FROM {table} WHERE {where_clause}"
            return self.execute_update(query, where_params)
        except sqlite3.Error as e:
            print(f"Database error during delete from {table}: {e}")
            return None
        except Exception as e:
            print(f"An unexpected error occurred during delete: {e}")
            return None
    
    def import_json_data(self, table, json_file):
        """
        Import data from a JSON file into a table
        
        Args:
            table: Table name
            json_file: Path to the JSON file
            
        Returns:
            Number of imported rows
        """
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if not isinstance(data, list):
                data = [data]
            
            count = 0
            for item in data:
                self.insert(table, item)
                count += 1
            
            return count
        except Exception as e:
            print(f"Error importing data: {e}")
            return 0

    # --- Monster Specific Methods ---

    def save_custom_monster(self, monster: Monster) -> Optional[Monster]:
        """
        Saves a new custom monster or updates an existing one.

        Args:
            monster: The Monster object to save. Assumes monster.is_custom is True.

        Returns:
            The updated Monster object with ID set, or None on failure.
        """
        if not monster.is_custom:
            print("Error: Attempted to save a non-custom monster using save_custom_monster.")
            return None

        now = datetime.now(timezone.utc).isoformat()
        
        # Debug logging to check monster before saving
        print(f"DEBUG: Saving monster: name={monster.name}, is_custom={monster.is_custom}, has_actions={len(monster.actions) if monster.actions else 0}")
        
        monster_data = monster.to_dict() # Get dict representation
        
        # Debug logging to check dict conversion
        print(f"DEBUG: Monster to_dict() result has {len(monster_data)} keys")
        
        monster_json = json.dumps(monster_data) # Serialize the data part
        
        # Debug logging to check serialization
        print(f"DEBUG: Serialized JSON length: {len(monster_json)}")

        data_to_save = {
            "name": monster.name,
            "data": monster_json,
            "updated_at": now
        }

        if monster.id is None: # New monster
            data_to_save["created_at"] = now
            inserted_id = self.insert("custom_monsters", data_to_save)
            if inserted_id is not None:
                monster.id = inserted_id # Update the object with the new ID
                monster.created_at = now
                monster.updated_at = now
                print(f"Saved new custom monster '{monster.name}' with ID {monster.id}")
                return monster # Return the updated monster object
            else:
                print(f"Failed to insert new custom monster '{monster.name}'")
                # Debug logging for insert failure
                print(f"DEBUG: Insert failed. Data keys: {list(data_to_save.keys())}")
                return None
        else: # Update existing monster
            affected_rows = self.update(
                "custom_monsters",
                data_to_save,
                "id = ?",
                (monster.id,)
            )
            if affected_rows is not None and affected_rows > 0:
                monster.updated_at = now
                print(f"Updated custom monster '{monster.name}' with ID {monster.id}")
                return monster # Return the updated monster object
            elif affected_rows == 0:
                print(f"Warning: Update for custom monster ID {monster.id} ('{monster.name}') affected 0 rows. Does it exist?")
                return None
            else:
                print(f"Failed to update custom monster '{monster.name}' with ID {monster.id}")
                print(f"DEBUG: Update failed. Data keys: {list(data_to_save.keys())}")
                return None

    def get_monster_by_id(self, monster_id: int, is_custom: bool) -> Optional[Monster]:
        """
        Retrieves a single monster by its database ID.

        Args:
            monster_id: The ID of the monster.
            is_custom: True if fetching from 'custom_monsters', False for 'monsters'.

        Returns:
            A Monster object or None if not found or on error.
        """
        table = "custom_monsters" if is_custom else "monsters"
        query = f"SELECT * FROM {table} WHERE id = ?"
        try:
            results = self.execute_query(query, (monster_id,))
            if results:
                return Monster.from_db_row(results[0], is_custom=is_custom)
            else:
                return None
        except sqlite3.Error as e:
            print(f"Database error fetching monster ID {monster_id} from {table}: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error fetching monster ID {monster_id}: {e}")
            return None

    def search_monsters(self, search_term: str, include_custom: bool = True, include_standard: bool = True) -> List[Monster]:
        """
        Searches for monsters by name in standard and/or custom tables.

        Args:
            search_term: The term to search for in monster names (case-insensitive).
            include_custom: Whether to include results from 'custom_monsters'.
            include_standard: Whether to include results from 'monsters'.

        Returns:
            A list of matching Monster objects.
        """
        monsters = []
        search_pattern = f"%{search_term}%"

        try:
            # Search standard monsters
            if include_standard:
                query_std = "SELECT * FROM monsters WHERE name LIKE ?"
                results_std = self.execute_query(query_std, (search_pattern,))
                for row in results_std:
                    try:
                        monsters.append(Monster.from_db_row(row, is_custom=False))
                    except Exception as e:
                        print(f"Error parsing standard monster row ID {row.get('id', 'N/A')}: {e}")

            # Search custom monsters
            if include_custom:
                query_custom = "SELECT * FROM custom_monsters WHERE name LIKE ?"
                results_custom = self.execute_query(query_custom, (search_pattern,))
                for row in results_custom:
                    try:
                        monsters.append(Monster.from_db_row(row, is_custom=True))
                    except Exception as e:
                        print(f"Error parsing custom monster row ID {row.get('id', 'N/A')}: {e}")

        except sqlite3.Error as e:
            print(f"Database error during monster search for '{search_term}': {e}")
            # Return potentially partial results collected so far
        except Exception as e:
            print(f"Unexpected error during monster search: {e}")

        # Optional: Sort results, e.g., alphabetically by name
        monsters.sort(key=lambda m: m.name)

        return monsters

    def get_all_monster_names(self, include_custom: bool = True, include_standard: bool = True) -> List[Dict[str, Any]]:
        """
        Retrieves a list of all monster names and their IDs/type.

        Args:
            include_custom: Whether to include names from 'custom_monsters'.
            include_standard: Whether to include names from 'monsters'.

        Returns:
            A list of dictionaries, each containing {'id': int, 'name': str, 'is_custom': bool}.
        """
        names = []
        try:
            if include_standard:
                query_std = "SELECT id, name FROM monsters ORDER BY name ASC"
                results_std = self.execute_query(query_std)
                names.extend([{'id': row['id'], 'name': row['name'], 'is_custom': False} for row in results_std])

            if include_custom:
                query_custom = "SELECT id, name FROM custom_monsters ORDER BY name ASC"
                results_custom = self.execute_query(query_custom)
                names.extend([{'id': row['id'], 'name': row['name'], 'is_custom': True} for row in results_custom])

        except sqlite3.Error as e:
            print(f"Database error fetching all monster names: {e}")
        except Exception as e:
            print(f"Unexpected error fetching all monster names: {e}")

        # Ensure consistent sorting if combined
        names.sort(key=lambda x: x['name'])
        return names

    def delete_custom_monster(self, monster_id: int) -> bool:
        """
        Deletes a custom monster by its ID.

        Args:
            monster_id: The ID of the custom monster to delete.

        Returns:
            True if deletion was successful (or monster didn't exist), False on error.
        """
        print(f"Attempting to delete custom monster with ID: {monster_id}")
        affected_rows = self.delete("custom_monsters", "id = ?", (monster_id,))

        if affected_rows is not None:
            if affected_rows > 0:
                print(f"Successfully deleted custom monster ID {monster_id}.")
                return True
            else:
                print(f"Custom monster ID {monster_id} not found for deletion.")
                return True # Still considered successful as the monster is gone
        else:
            print(f"Error occurred while trying to delete custom monster ID {monster_id}.")
            return False

    def get_monster_by_name(self, name: str, include_custom: bool = True, include_standard: bool = True) -> Optional[Monster]:
        """
        Retrieves a monster by its exact name.

        Args:
            name: The exact name of the monster to find (case-sensitive).
            include_custom: Whether to search in 'custom_monsters'.
            include_standard: Whether to search in 'monsters'.

        Returns:
            A Monster object if found or None if not found or on error.
        """
        if not name:
            return None
            
        monsters = []
        try:
            # Check standard monsters
            if include_standard:
                query_std = "SELECT * FROM monsters WHERE name = ? LIMIT 1"
                results_std = self.execute_query(query_std, (name,))
                if results_std:
                    monsters.append(Monster.from_db_row(results_std[0], is_custom=False))

            # Check custom monsters
            if include_custom:
                query_custom = "SELECT * FROM custom_monsters WHERE name = ? LIMIT 1"
                results_custom = self.execute_query(query_custom, (name,))
                if results_custom:
                    monsters.append(Monster.from_db_row(results_custom[0], is_custom=True))

            # Return the first matching monster found
            # (Custom results will be preferred if they come second in the check order)
            if monsters:
                return monsters[0]
            return None
            
        except sqlite3.Error as e:
            print(f"Database error retrieving monster by name '{name}': {e}")
            return None
        except Exception as e:
            print(f"Unexpected error retrieving monster by name '{name}': {e}")
            return None
