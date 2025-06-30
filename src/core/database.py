import sqlite3
import json
from datetime import datetime
from pathlib import Path

class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._ensure_db_directory()
        self._init_database()
    
    def _ensure_db_directory(self):
        """Ensure the database directory exists"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
    
    def _init_database(self):
        """Initialize the database with required tables"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Research sessions table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS research_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'in_progress',
                    final_answer TEXT,
                    context_variables TEXT
                )
            ''')
            
            # Agent interactions table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS agent_interactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER,
                    agent_name TEXT NOT NULL,
                    action TEXT NOT NULL,
                    result TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES research_sessions (id)
                )
            ''')
            
            # Code executions table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS code_executions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER,
                    code TEXT NOT NULL,
                    output TEXT,
                    error TEXT,
                    execution_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES research_sessions (id)
                )
            ''')
            
            conn.commit()
    
    def create_research_session(self, query: str) -> int:
        """Create a new research session and return its ID"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO research_sessions (query) VALUES (?)',
                (query,)
            )
            conn.commit()
            return cursor.lastrowid
    
    def update_session_status(self, session_id: int, status: str, final_answer: str = None, context_variables: dict = None):
        """Update the status and final answer of a research session"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''UPDATE research_sessions 
                   SET status = ?, final_answer = ?, context_variables = ?
                   WHERE id = ?''',
                (status, final_answer, json.dumps(context_variables) if context_variables else None, session_id)
            )
            conn.commit()
    
    def log_agent_interaction(self, session_id: int, agent_name: str, action: str, result: str = None):
        """Log an agent interaction"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO agent_interactions (session_id, agent_name, action, result) VALUES (?, ?, ?, ?)',
                (session_id, agent_name, action, result)
            )
            conn.commit()
    
    def log_code_execution(self, session_id: int, code: str, output: str = None, error: str = None):
        """Log a code execution"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO code_executions (session_id, code, output, error) VALUES (?, ?, ?, ?)',
                (session_id, code, output, error)
            )
            conn.commit()
    
    def get_session_history(self, session_id: int) -> dict:
        """Get the complete history of a research session"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Get session details
            cursor.execute('SELECT * FROM research_sessions WHERE id = ?', (session_id,))
            session = cursor.fetchone()
            
            if not session:
                return None
            
            # Get agent interactions
            cursor.execute('SELECT * FROM agent_interactions WHERE session_id = ? ORDER BY timestamp', (session_id,))
            interactions = cursor.fetchall()
            
            # Get code executions
            cursor.execute('SELECT * FROM code_executions WHERE session_id = ? ORDER BY execution_time', (session_id,))
            code_executions = cursor.fetchall()
            
            return {
                'session': session,
                'interactions': interactions,
                'code_executions': code_executions
            } 