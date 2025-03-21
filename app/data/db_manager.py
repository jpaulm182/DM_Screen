# app/data/db_manager.py - Database manager
"""
Database manager for the DM Screen application

Handles database connections, schema management, and common queries.
"""

import os
import sqlite3
from datetime import datetime
import json
import random
from pathlib import Path

from app.core.config import get_database_path


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
            ID of the inserted row
        """
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
            
            # If no ID was returned but we need one, get the ID through a select query
            if row_id is None:
                print(f"Warning: lastrowid is None after insertion into {table}")
                
                # Try to get the ID of the row we just inserted
                # For tables with auto-increment primary key
                select_query = f"SELECT last_insert_rowid()"
                cursor.execute(select_query)
                result = cursor.fetchone()
                
                if result and result[0]:
                    row_id = result[0]
                    print(f"Retrieved ID using last_insert_rowid(): {row_id}")
                else:
                    # As a last resort, try to query for the exact record we just inserted
                    # This is not perfect but may work in many cases
                    conditions = []
                    condition_values = []
                    
                    # Use string columns that are likely to be unique for identification
                    string_cols = [k for k, v in data.items() if isinstance(v, str) and k not in ('created_at', 'updated_at')]
                    
                    if string_cols:
                        for col in string_cols[:2]:  # Use up to 2 string columns for identification
                            conditions.append(f"{col} = ?")
                            condition_values.append(data[col])
                            
                        where_clause = " AND ".join(conditions)
                        
                        # Order by ID descending to get the most recently added record
                        select_query = f"SELECT id FROM {table} WHERE {where_clause} ORDER BY id DESC LIMIT 1"
                        cursor.execute(select_query, condition_values)
                        result = cursor.fetchone()
                        
                        if result and result[0]:
                            row_id = result[0]
                            print(f"Retrieved ID using query: {row_id}")
                        else:
                            # Generate a random high ID to avoid conflicts
                            row_id = random.randint(10000, 99999)
                            print(f"Generated random ID: {row_id}")
                    else:
                        # Generate a random high ID to avoid conflicts
                        row_id = random.randint(10000, 99999)
                        print(f"Generated random ID: {row_id}")
            
            return row_id
            
        except Exception as e:
            print(f"Error in DatabaseManager.insert: {str(e)}")
            self.connection.rollback()
            raise
    
    def update(self, table, data, where_clause, where_params=None):
        """
        Update data in a table
        
        Args:
            table: Table name
            data: Dictionary of column:value pairs to update
            where_clause: WHERE clause for the update
            where_params: Parameters for the WHERE clause
            
        Returns:
            Number of affected rows
        """
        set_clause = ", ".join([f"{key} = ?" for key in data.keys()])
        values = list(data.values())
        
        query = f"UPDATE {table} SET {set_clause} WHERE {where_clause}"
        
        if where_params:
            values.extend(where_params)
        
        cursor = self.connection.cursor()
        cursor.execute(query, values)
        self.connection.commit()
        
        return cursor.rowcount
    
    def delete(self, table, where_clause, where_params=None):
        """
        Delete data from a table
        
        Args:
            table: Table name
            where_clause: WHERE clause for the deletion
            where_params: Parameters for the WHERE clause
            
        Returns:
            Number of affected rows
        """
        query = f"DELETE FROM {table} WHERE {where_clause}"
        
        cursor = self.connection.cursor()
        
        if where_params:
            cursor.execute(query, where_params)
        else:
            cursor.execute(query)
        
        self.connection.commit()
        return cursor.rowcount
    
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
