"""
Query Configuration Manager
============================
Manages dynamic SQL queries stored in SQLite database.
Queries are encrypted for security and can be updated via admin panel.
"""

import sqlite3
import json
from contextlib import contextmanager
from logger import get_logger
from cryptography.fernet import Fernet
import base64
import os
from typing import Dict, List, Optional


logger = get_logger(__name__)

SQLITE_DB_PATH = "building_schedules.db"

# ⚠️ ENCRYPTION KEY: In production, store this in environment variable or use the same key management as config
# For now, we'll generate a key if it doesn't exist
QUERY_ENCRYPTION_KEY_FILE = "query_encryption.key"


def get_or_create_encryption_key() -> bytes:
    """
    Get existing encryption key or create a new one.
    ⚠️ IMPORTANT: Backup this key! Lost key = lost queries.
    """
    if os.path.exists(QUERY_ENCRYPTION_KEY_FILE):
        with open(QUERY_ENCRYPTION_KEY_FILE, 'rb') as f:
            return f.read()
    else:
        key = Fernet.generate_key()
        with open(QUERY_ENCRYPTION_KEY_FILE, 'wb') as f:
            f.write(key)
        logger.info(f"✅ Generated new query encryption key: {QUERY_ENCRYPTION_KEY_FILE}")
        return key


ENCRYPTION_KEY = get_or_create_encryption_key()
cipher_suite = Fernet(ENCRYPTION_KEY)


@contextmanager
def get_sqlite_connection():
    """Context manager for SQLite database connections."""
    conn = sqlite3.connect(SQLITE_DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    except Exception as e:
        conn.rollback()
        logger.error(f"SQLite transaction error: {e}")
        raise
    else:
        conn.commit()
    finally:
        conn.close()


def encrypt_query(query: str) -> str:
    """Encrypt a SQL query string."""
    encrypted = cipher_suite.encrypt(query.encode('utf-8'))
    return base64.b64encode(encrypted).decode('utf-8')


def decrypt_query(encrypted_query: str) -> str:
    """Decrypt a SQL query string."""
    try:
        decoded = base64.b64decode(encrypted_query.encode('utf-8'))
        decrypted = cipher_suite.decrypt(decoded)
        return decrypted.decode('utf-8')
    except Exception as e:
        logger.error(f"Query decryption failed: {e}")
        raise


# ==================== DEFAULT QUERIES ====================
# These are the queries that will be used if not overridden by admin

# DEVICE QUERY - Gets panel device states for buildings
DEFAULT_DEVICE_QUERY = """
SELECT dvcBuilding_FRK, dvcCurrentState_TXT
FROM Device_TBL
WHERE dvcDeviceType_FRK = 138
"""

# BUILDING QUERY - Gets all buildings
DEFAULT_BUILDING_QUERY = """
SELECT Building_PRK, bldBuildingName_TXT
FROM Building_TBL
"""


def get_query(query_name: str) -> str:
    """
    Retrieve a query by name from database, or return default.
    
    Args:
        query_name: Name of the query to retrieve ('device_query' or 'building_query')
        
    Returns:
        Decrypted SQL query string
    """
    try:
        with get_sqlite_connection() as conn:
            cursor = conn.execute(
                "SELECT query_sql FROM query_config WHERE query_name = ?",
                (query_name,)
            )
            row = cursor.fetchone()
            
            if row:
                encrypted_query = row['query_sql']
                return decrypt_query(encrypted_query)
            else:
                # Return default query if not found
                logger.info(f"Query '{query_name}' not found in DB, using default")
                return get_default_query(query_name)
                
    except Exception as e:
        logger.error(f"Error retrieving query '{query_name}': {e}")
        # Fallback to default on error
        return get_default_query(query_name)


def get_default_query(query_name: str) -> str:
    """Get the default query for a given query name."""
    defaults = {
        'device_query': DEFAULT_DEVICE_QUERY,
        'building_query': DEFAULT_BUILDING_QUERY,
        # Legacy names for backward compatibility
        'device': DEFAULT_DEVICE_QUERY,
        'building': DEFAULT_BUILDING_QUERY
    }
    return defaults.get(query_name, "")


def set_query(query_name: str, query_sql: str, description: str = "") -> bool:
    """
    Save or update a query in the database.
    
    Args:
        query_name: Unique name for the query
        query_sql: SQL query string (will be encrypted)
        description: Optional description of what the query does
        
    Returns:
        True if successful, False otherwise
    """
    try:
        encrypted_query = encrypt_query(query_sql)
        
        with get_sqlite_connection() as conn:
            conn.execute("""
                INSERT INTO query_config (query_name, query_sql, description, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(query_name) DO UPDATE SET
                    query_sql = excluded.query_sql,
                    description = excluded.description,
                    updated_at = CURRENT_TIMESTAMP
            """, (query_name, encrypted_query, description))
        
        logger.info(f"✅ Query '{query_name}' saved successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error saving query '{query_name}': {e}")
        return False


def get_all_queries() -> list[dict]:
    """
    Get all configured queries with metadata (without decrypting SQL).
    
    Returns:
        List of query metadata dictionaries
    """
    try:
        with get_sqlite_connection() as conn:
            cursor = conn.execute("""
                SELECT query_name, description, created_at, updated_at
                FROM query_config
                ORDER BY query_name
            """)
            rows = cursor.fetchall()
            
            return [dict(row) for row in rows]
            
    except Exception as e:
        logger.error(f"Error retrieving all queries: {e}")
        return []


def get_query_with_sql(query_name: str) -> Optional[dict]:
    """
    Get a specific query with its decrypted SQL.
    
    Args:
        query_name: Name of the query
        
    Returns:
        Dictionary with query details including decrypted SQL
    """
    try:
        with get_sqlite_connection() as conn:
            cursor = conn.execute("""
                SELECT query_name, query_sql, description, created_at, updated_at
                FROM query_config
                WHERE query_name = ?
            """, (query_name,))
            row = cursor.fetchone()
            
            if row:
                result = dict(row)
                result['query_sql'] = decrypt_query(result['query_sql'])
                return result
            else:
                # Return default query info
                return {
                    'query_name': query_name,
                    'query_sql': get_default_query(query_name),
                    'description': f'Default {query_name} query',
                    'created_at': None,
                    'updated_at': None
                }
                
    except Exception as e:
        logger.error(f"Error retrieving query '{query_name}' with SQL: {e}")
        return None


def delete_query(query_name: str) -> bool:
    """
    Delete a query from the database (will revert to default).
    
    Args:
        query_name: Name of the query to delete
        
    Returns:
        True if successful, False otherwise
    """
    try:
        with get_sqlite_connection() as conn:
            conn.execute("DELETE FROM query_config WHERE query_name = ?", (query_name,))
        
        logger.info(f"✅ Query '{query_name}' deleted (will use default)")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error deleting query '{query_name}': {e}")
        return False


def validate_query_syntax(query: str) -> tuple[bool, str]:
    """
    Basic validation of SQL query syntax.
    ⚠️ This is NOT foolproof! Always use prepared statements.
    
    Args:
        query: SQL query string to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    # Basic checks
    query_lower = query.lower().strip()
    
    # Must be a SELECT statement
    if not query_lower.startswith('select'):
        return False, "Query must be a SELECT statement"
    
    # Dangerous keywords check
    dangerous_keywords = ['drop', 'delete', 'truncate', 'insert', 'update', 'alter', 'create']
    for keyword in dangerous_keywords:
        if keyword in query_lower:
            return False, f"Query contains forbidden keyword: {keyword}"
    
    # Check for balanced parentheses
    if query.count('(') != query.count(')'):
        return False, "Unbalanced parentheses in query"
    
    # Basic SQL injection patterns
    suspicious_patterns = ['--', ';--', '/*', '*/', 'xp_', 'sp_']
    for pattern in suspicious_patterns:
        if pattern in query_lower:
            return False, f"Query contains suspicious pattern: {pattern}"
    
    return True, "Query validation passed"