"""
auth.py
Handles password hashing and JWT token generation/verification:
- Short-lived Access Token (15 minutes)
- Long-lived Refresh Token (7 days)
- Token verification decorator (@token_required)
"""
import os
import datetime
import jwt
from functools import wraps
from flask import request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash

# Secret key for signing JWTs (can be overridden with environment variable)
JWT_SECRET = os.environ.get("JWT_SECRET", "super-secret-jwt-key-for-dev-environment-32bytes")
ACCESS_TOKEN_EXP_MINUTES = 15
REFRESH_TOKEN_EXP_DAYS = 7

def hash_password(password: str) -> str:
    """Hashes plain-text password using Werkzeug's secure PBKDF2/scrypt."""
    return generate_password_hash(password)

def verify_password(password: str, password_hash: str) -> bool:
    """Verifies a plain-text password against a stored hash."""
    return check_password_hash(password_hash, password)

def create_access_token(user_id: int, username: str, role: str) -> str:
    """Creates a short-lived access token (expires in 15 minutes)."""
    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        "user_id": user_id,
        "username": username,
        "role": role,
        "type": "access",
        "exp": now + datetime.timedelta(minutes=ACCESS_TOKEN_EXP_MINUTES),
        "iat": now
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def create_tokens(user_id: int, username: str, role: str) -> dict:
    """
    Creates a pair of tokens:
    1. Short-lived Access Token (15 min)
    2. Long-lived Refresh Token (7 days)
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    
    access_token = create_access_token(user_id, username, role)
    
    refresh_payload = {
        "user_id": user_id,
        "username": username,
        "role": role,
        "type": "refresh",
        "exp": now + datetime.timedelta(days=REFRESH_TOKEN_EXP_DAYS),
        "iat": now
    }
    refresh_token = jwt.encode(refresh_payload, JWT_SECRET, algorithm="HS256")
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "Bearer",
        "expires_in": ACCESS_TOKEN_EXP_MINUTES * 60
    }

def decode_token(token: str, expected_type: str = "access"):
    """
    Decodes and validates a JWT token:
    - Verifies signature using secret key
    - Checks expiration time
    - Verifies expected token type ('access' or 'refresh')
    Returns: (payload, error_message)
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        if payload.get("type") != expected_type:
            return None, f"Invalid token type: expected '{expected_type}' token"
        return payload, None
    except jwt.ExpiredSignatureError:
        return None, "Token has expired"
    except jwt.InvalidTokenError:
        return None, "Invalid token"

def token_required(f):
    """
    Decorator to protect routes requiring a valid Access Token.
    Extracts Bearer token from 'Authorization' header and passes 'current_user' to the route.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return jsonify({"error": "Authorization header is missing"}), 401
        
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return jsonify({"error": "Authorization header must be in format: Bearer <token>"}), 401
        
        token = parts[1]
        payload, error = decode_token(token, expected_type="access")
        if error:
            return jsonify({"error": error}), 401
        
        current_user = {
            "id": payload["user_id"],
            "username": payload["username"],
            "role": payload["role"]
        }
        return f(current_user, *args, **kwargs)
    return decorated

def admin_required(f):
    """
    Decorator to protect routes requiring 'admin' role.
    First ensures a valid access token is provided, then checks role == 'admin'.
    Returns 403 Forbidden if the user is a member or any non-admin role.
    """
    @wraps(f)
    @token_required
    def decorated(current_user, *args, **kwargs):
        if current_user.get("role") != "admin":
            return jsonify({"error": "Admin access required. Forbidden."}), 403
        return f(current_user, *args, **kwargs)
    return decorated

