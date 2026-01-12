from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel
from typing import Optional, List
import sqlite3
from contextlib import contextmanager

from auth import hash_password, verify_password, create_access_token, get_current_user
from query_config import get_query, set_query, get_all_queries, get_query_with_sql, delete_query, validate_query_syntax, get_default_query
from logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])
SQLITE_DB_PATH = "building_schedules.db"

@contextmanager
def get_sqlite_connection():
    conn = sqlite3.connect(SQLITE_DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    else:
        conn.commit()
    finally:
        conn.close()

# Models
class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    username: str
    is_admin: bool

class QueryRequest(BaseModel):
    query_name: str
    query_sql: str
    description: Optional[str] = ""

class QueryResponse(BaseModel):
    query_name: str
    query_sql: str
    description: str
    created_at: Optional[str]
    updated_at: Optional[str]

class CreateUserRequest(BaseModel):
    username: str
    password: str
    is_admin: bool = False

class UpdateUserRequest(BaseModel):
    is_admin: Optional[bool] = None
    new_password: Optional[str] = None

class UserResponse(BaseModel):
    id: int
    username: str
    is_admin: bool
    created_at: str
    updated_at: str

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

# Auth Dependencies
def get_current_admin_user(authorization: Optional[str] = Header(None)) -> tuple:
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    
    try:
        scheme, token = authorization.split()
        if scheme.lower() != 'bearer':
            raise HTTPException(status_code=401, detail="Invalid authentication scheme")
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid authorization header format")
    
    username = get_current_user(token)
    if username is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    with get_sqlite_connection() as conn:
        cursor = conn.execute("SELECT is_admin FROM admin_users WHERE username = ?", (username,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=401, detail="User not found")
        return username, bool(row['is_admin'])

def require_admin(auth_info: tuple = Depends(get_current_admin_user)) -> str:
    username, is_admin = auth_info
    if not is_admin:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return username

# ==================== AUTH ROUTES ====================

@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    with get_sqlite_connection() as conn:
        cursor = conn.execute("SELECT username, password_hash, is_admin FROM admin_users WHERE username = ?", (request.username,))
        row = cursor.fetchone()
        if not row or not verify_password(request.password, row['password_hash']):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        access_token = create_access_token(data={"sub": request.username})
        return LoginResponse(
            access_token=access_token, 
            token_type="bearer", 
            username=request.username, 
            is_admin=bool(row['is_admin'])
        )

@router.post("/change-password")
async def change_password(request: ChangePasswordRequest, auth_info: tuple = Depends(get_current_admin_user)):
    username, is_admin = auth_info
    
    with get_sqlite_connection() as conn:
        # Verify current password
        cursor = conn.execute("SELECT password_hash FROM admin_users WHERE username = ?", (username,))
        row = cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="User not found")
        
        if not verify_password(request.current_password, row['password_hash']):
            raise HTTPException(status_code=401, detail="Current password is incorrect")
        
        # Update password
        new_password_hash = hash_password(request.new_password)
        conn.execute(
            "UPDATE admin_users SET password_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE username = ?",
            (new_password_hash, username)
        )
    
    logger.info(f"Password changed successfully for user: {username}")
    return {"success": True, "message": "Password changed successfully"}

# ==================== QUERY ROUTES ====================

@router.get("/queries")
async def list_queries(auth_info: tuple = Depends(get_current_admin_user)):
    username, is_admin = auth_info
    queries = [
        {'query_name': 'device_query', 'description': 'Main configuration for Device_TBL retrieval'},
        {'query_name': 'building_query', 'description': 'Main configuration for Building_TBL retrieval'}
    ]
    return {"queries": queries, "is_admin": is_admin}

@router.get("/queries/{query_name}", response_model=QueryResponse)
async def get_query_details(query_name: str, auth_info: tuple = Depends(get_current_admin_user)):
    query_data = get_query_with_sql(query_name)
    if not query_data:
        raise HTTPException(status_code=404, detail=f"Query '{query_name}' not found")
    return QueryResponse(**query_data)

@router.get("/queries/{query_name}/default")
async def get_default_query_endpoint(query_name: str, auth_info: tuple = Depends(get_current_admin_user)):
    """Get the default query SQL for a query name"""
    default_sql = get_default_query(query_name)
    
    if not default_sql:
        raise HTTPException(status_code=404, detail=f"No default query found for '{query_name}'")
    
    return {
        "query_name": query_name,
        "query_sql": default_sql,
        "description": f"Default {query_name} configuration"
    }

@router.post("/queries")
async def update_query(request: QueryRequest, admin_username: str = Depends(require_admin)):
    is_valid, error_message = validate_query_syntax(request.query_sql)
    if not is_valid:
        raise HTTPException(status_code=400, detail=f"Invalid query: {error_message}")
    if not set_query(request.query_name, request.query_sql, request.description):
        raise HTTPException(status_code=500, detail="Failed to save query")
    return {"success": True, "message": f"Query '{request.query_name}' saved successfully"}

# ==================== USER MANAGEMENT ROUTES ====================

@router.get("/users", response_model=List[UserResponse])
async def list_users(admin_username: str = Depends(require_admin)):
    """Get all users (admin only)"""
    with get_sqlite_connection() as conn:
        cursor = conn.execute("""
            SELECT id, username, is_admin, created_at, updated_at 
            FROM admin_users 
            ORDER BY created_at DESC
        """)
        rows = cursor.fetchall()
        
        users = []
        for row in rows:
            users.append(UserResponse(
                id=row['id'],
                username=row['username'],
                is_admin=bool(row['is_admin']),
                created_at=row['created_at'],
                updated_at=row['updated_at']
            ))
        
        return users

@router.post("/users")
async def create_user(request: CreateUserRequest, admin_username: str = Depends(require_admin)):
    """Create a new user (admin only)"""
    
    # Validate username length
    if len(request.username) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters")
    
    # Validate password length
    if len(request.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    
    with get_sqlite_connection() as conn:
        # Check if username already exists
        cursor = conn.execute("SELECT id FROM admin_users WHERE username = ?", (request.username,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail=f"Username '{request.username}' already exists")
        
        # Hash password and create user
        password_hash = hash_password(request.password)
        
        try:
            conn.execute("""
                INSERT INTO admin_users (username, password_hash, is_admin)
                VALUES (?, ?, ?)
            """, (request.username, password_hash, request.is_admin))
            
            logger.info(f"User created: {request.username} (admin: {request.is_admin}) by {admin_username}")
            
            return {
                "success": True, 
                "message": f"User '{request.username}' created successfully"
            }
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            raise HTTPException(status_code=500, detail="Failed to create user")

@router.put("/users/{user_id}")
async def update_user(user_id: int, request: UpdateUserRequest, admin_username: str = Depends(require_admin)):
    """Update user (admin only)"""
    
    with get_sqlite_connection() as conn:
        # Check if user exists
        cursor = conn.execute("SELECT username FROM admin_users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="User not found")
        
        target_username = row['username']
        
        # Prevent admin from removing their own admin privileges
        if target_username == admin_username and request.is_admin is False:
            raise HTTPException(status_code=400, detail="Cannot remove your own admin privileges")
        
        # Update admin status if provided
        if request.is_admin is not None:
            conn.execute(
                "UPDATE admin_users SET is_admin = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (request.is_admin, user_id)
            )
            logger.info(f"User {target_username} admin status changed to {request.is_admin} by {admin_username}")
        
        # Update password if provided
        if request.new_password:
            if len(request.new_password) < 6:
                raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
            
            new_password_hash = hash_password(request.new_password)
            conn.execute(
                "UPDATE admin_users SET password_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (new_password_hash, user_id)
            )
            logger.info(f"Password reset for user {target_username} by {admin_username}")
        
        return {"success": True, "message": f"User updated successfully"}

@router.delete("/users/{user_id}")
async def delete_user(user_id: int, admin_username: str = Depends(require_admin)):
    """Delete user (admin only)"""
    
    with get_sqlite_connection() as conn:
        # Check if user exists
        cursor = conn.execute("SELECT username FROM admin_users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="User not found")
        
        target_username = row['username']
        
        # Prevent admin from deleting themselves
        if target_username == admin_username:
            raise HTTPException(status_code=400, detail="Cannot delete your own account")
        
        # Delete user
        conn.execute("DELETE FROM admin_users WHERE id = ?", (user_id,))
        
        logger.info(f"User {target_username} deleted by {admin_username}")
        
        return {"success": True, "message": f"User '{target_username}' deleted successfully"}