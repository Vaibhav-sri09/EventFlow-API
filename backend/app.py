"""
app.py
Flask Application implementing:
- User registration (POST /auth/register)
- Login (POST /auth/login)
- Token refresh (POST /auth/refresh)
- Authenticated user profile (GET /auth/me)
"""
import math
import sqlite3
from flask import Flask, request, jsonify
from flask_cors import CORS

from database import get_db_connection, init_db
from auth import (
    hash_password,
    verify_password,
    create_tokens,
    create_access_token,
    decode_token,
    token_required,
    admin_required,
    ACCESS_TOKEN_EXP_MINUTES
)

app = Flask(__name__)
CORS(app)


# ----------------------------------------------------
# Health Check Endpoint
# ----------------------------------------------------
@app.route("/health", methods=["GET"])
@app.route("/api/health", methods=["GET"])
def health_check():
    return jsonify({"status": "ok", "message": "Event Registration API is running"}), 200


# ----------------------------------------------------
# 1. User Registration
# ----------------------------------------------------
@app.route("/auth/register", methods=["POST"])
@app.route("/api/auth/register", methods=["POST"])
def register():
    data = request.get_json() or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    requested_role = data.get("role", "member").strip().lower()

    # Validation: Ensure username and password are provided
    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    if len(password) < 4:
        return jsonify({"error": "Password must be at least 4 characters long"}), 400

    # Security check: Prevent public creation of admin accounts
    if requested_role == "admin":
        return jsonify({"error": "Admin account creation is not allowed via public registration"}), 403

    # Default to 'member' role
    role = "member"

    # Hash password with Werkzeug
    password_hash = hash_password(password)

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            (username, password_hash, role)
        )
        conn.commit()
        user_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"error": f"Username '{username}' already exists"}), 409
    finally:
        conn.close()

    return jsonify({
        "message": "User registered successfully",
        "user": {
            "id": user_id,
            "username": username,
            "role": role
        }
    }), 201


# ----------------------------------------------------
# 2. Login
# ----------------------------------------------------
@app.route("/auth/login", methods=["POST"])
@app.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, password_hash, role FROM users WHERE username = ?", (username,))
    user = cursor.fetchone()
    conn.close()

    # Verify user existence and password hash
    if not user or not verify_password(password, user["password_hash"]):
        return jsonify({"error": "Invalid username or password"}), 401

    # Generate short-lived access token + long-lived refresh token
    tokens = create_tokens(user["id"], user["username"], user["role"])

    return jsonify({
        "message": "Login successful",
        **tokens,
        "user": {
            "id": user["id"],
            "username": user["username"],
            "role": user["role"]
        }
    }), 200


# ----------------------------------------------------
# 3. Refresh Token
# ----------------------------------------------------
@app.route("/auth/refresh", methods=["POST"])
@app.route("/api/auth/refresh", methods=["POST"])
def refresh():
    data = request.get_json() or {}
    refresh_token = data.get("refresh_token")

    # If not in JSON body, check Authorization header
    if not refresh_token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            refresh_token = auth_header.split(" ")[1]

    if not refresh_token:
        return jsonify({"error": "Refresh token is required in request body or Authorization header"}), 400

    # Validate the refresh token (specifically expecting type='refresh')
    payload, error = decode_token(refresh_token, expected_type="refresh")
    if error:
        return jsonify({"error": error}), 401

    # Issue a brand-new short-lived access token
    new_access_token = create_access_token(
        user_id=payload["user_id"],
        username=payload["username"],
        role=payload["role"]
    )

    return jsonify({
        "access_token": new_access_token,
        "token_type": "Bearer",
        "expires_in": ACCESS_TOKEN_EXP_MINUTES * 60
    }), 200


# ----------------------------------------------------
# 4. Authenticated User Profile
# ----------------------------------------------------
@app.route("/auth/me", methods=["GET"])
@app.route("/api/auth/me", methods=["GET"])
@token_required
def get_current_user_profile(current_user):
    """
    Returns profile information of the currently authenticated user.
    Accessible to any authenticated user (members and admins).
    """
    return jsonify({
        "user": current_user
    }), 200


# ----------------------------------------------------
# 5. Events - List with Pagination & Filtering
# ----------------------------------------------------
@app.route("/events", methods=["GET"])
@app.route("/api/events", methods=["GET"])
@token_required
def list_events(current_user):
    """
    Lists events with pagination (page & limit) and optional search filter.
    Accessible to both authenticated members and admins.
    """
    # Parse pagination query params
    try:
        page = int(request.args.get("page", 1))
        limit = int(request.args.get("limit", 10))
    except ValueError:
        return jsonify({"error": "Page and limit parameters must be integers"}), 400

    if page < 1:
        page = 1
    if limit < 1:
        limit = 10
    elif limit > 100:
        limit = 100

    offset = (page - 1) * limit
    search = request.args.get("search", "").strip()

    conn = get_db_connection()
    cursor = conn.cursor()

    # Query with or without search filter
    if search:
        search_pattern = f"%{search}%"
        count_query = """
            SELECT COUNT(*) FROM events 
            WHERE title LIKE ? OR description LIKE ? OR location LIKE ?
        """
        cursor.execute(count_query, (search_pattern, search_pattern, search_pattern))
        total = cursor.fetchone()[0]

        select_query = """
            SELECT id, title, description, date, location, capacity, registered_count, created_by, created_at 
            FROM events 
            WHERE title LIKE ? OR description LIKE ? OR location LIKE ?
            ORDER BY date ASC, id DESC 
            LIMIT ? OFFSET ?
        """
        cursor.execute(select_query, (search_pattern, search_pattern, search_pattern, limit, offset))
    else:
        cursor.execute("SELECT COUNT(*) FROM events")
        total = cursor.fetchone()[0]

        select_query = """
            SELECT id, title, description, date, location, capacity, registered_count, created_by, created_at 
            FROM events 
            ORDER BY date ASC, id DESC 
            LIMIT ? OFFSET ?
        """
        cursor.execute(select_query, (limit, offset))

    rows = cursor.fetchall()
    conn.close()

    events = [dict(row) for row in rows]
    total_pages = math.ceil(total / limit) if total > 0 else 1

    return jsonify({
        "events": events,
        "page": page,
        "limit": limit,
        "total": total,
        "total_pages": total_pages
    }), 200


# ----------------------------------------------------
# 6. Events - Get Single Event Details
# ----------------------------------------------------
@app.route("/events/<int:event_id>", methods=["GET"])
@app.route("/api/events/<int:event_id>", methods=["GET"])
@token_required
def get_event(current_user, event_id):
    """
    Returns single event details.
    Accessible to both authenticated members and admins.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, title, description, date, location, capacity, registered_count, created_by, created_at 
        FROM events 
        WHERE id = ?
    """, (event_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return jsonify({"error": "Event not found"}), 404

    return jsonify({"event": dict(row)}), 200


# ----------------------------------------------------
# 7. Events - Create New Event (Admin Only)
# ----------------------------------------------------
@app.route("/events", methods=["POST"])
@app.route("/api/events", methods=["POST"])
@admin_required
def create_event(current_user):
    """
    Creates a new event.
    ADMIN ONLY: Members receive 403 Forbidden.
    """
    data = request.get_json() or {}
    title = data.get("title", "").strip()
    description = data.get("description", "").strip()
    date = data.get("date", "").strip()
    location = data.get("location", "").strip()
    capacity = data.get("capacity")

    # Validate required fields
    if not title or not date or not location or capacity is None:
        return jsonify({"error": "Fields 'title', 'date', 'location', and 'capacity' are required"}), 400

    try:
        capacity = int(capacity)
        if capacity <= 0:
            return jsonify({"error": "Capacity must be a positive integer greater than 0"}), 400
    except (ValueError, TypeError):
        return jsonify({"error": "Capacity must be a valid integer"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO events (title, description, date, location, capacity, created_by)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (title, description, date, location, capacity, current_user["id"]))
    conn.commit()
    event_id = cursor.lastrowid

    # Fetch created event to return
    cursor.execute("SELECT * FROM events WHERE id = ?", (event_id,))
    created_event = cursor.fetchone()
    conn.close()

    return jsonify({
        "message": "Event created successfully",
        "event": dict(created_event)
    }), 201


# ----------------------------------------------------
# 8. Events - Edit Event (Admin Only)
# ----------------------------------------------------
@app.route("/events/<int:event_id>", methods=["PUT"])
@app.route("/api/events/<int:event_id>", methods=["PUT"])
@admin_required
def update_event(current_user, event_id):
    """
    Edits an existing event.
    ADMIN ONLY: Members receive 403 Forbidden.
    """
    data = request.get_json() or {}

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM events WHERE id = ?", (event_id,))
    existing_event = cursor.fetchone()

    if not existing_event:
        conn.close()
        return jsonify({"error": "Event not found"}), 404

    title = data.get("title", existing_event["title"]).strip()
    description = data.get("description", existing_event["description"]).strip()
    date = data.get("date", existing_event["date"]).strip()
    location = data.get("location", existing_event["location"]).strip()
    capacity = data.get("capacity", existing_event["capacity"])

    try:
        capacity = int(capacity)
        if capacity <= 0:
            conn.close()
            return jsonify({"error": "Capacity must be a positive integer"}), 400
        if capacity < existing_event["registered_count"]:
            conn.close()
            return jsonify({
                "error": f"Capacity cannot be reduced below current registered count ({existing_event['registered_count']})"
            }), 400
    except (ValueError, TypeError):
        conn.close()
        return jsonify({"error": "Capacity must be a valid integer"}), 400

    cursor.execute("""
        UPDATE events 
        SET title = ?, description = ?, date = ?, location = ?, capacity = ?
        WHERE id = ?
    """, (title, description, date, location, capacity, event_id))
    conn.commit()

    cursor.execute("SELECT * FROM events WHERE id = ?", (event_id,))
    updated_event = cursor.fetchone()
    conn.close()

    return jsonify({
        "message": "Event updated successfully",
        "event": dict(updated_event)
    }), 200


# ----------------------------------------------------
# 9. Events - Delete Event (Admin Only)
# ----------------------------------------------------
@app.route("/events/<int:event_id>", methods=["DELETE"])
@app.route("/api/events/<int:event_id>", methods=["DELETE"])
@admin_required
def delete_event(current_user, event_id):
    """
    Deletes an event.
    ADMIN ONLY: Members receive 403 Forbidden.
    Cascading foreign keys automatically delete associated registrations.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM events WHERE id = ?", (event_id,))
    existing_event = cursor.fetchone()

    if not existing_event:
        conn.close()
        return jsonify({"error": "Event not found"}), 404

    cursor.execute("DELETE FROM events WHERE id = ?", (event_id,))
    conn.commit()
    conn.close()

    return jsonify({"message": "Event deleted successfully"}), 200


# ----------------------------------------------------
# 10. Registrations - Register for an Event
# ----------------------------------------------------
@app.route("/events/<int:event_id>/register", methods=["POST"])
@app.route("/api/events/<int:event_id>/register", methods=["POST"])
@token_required
def register_for_event(current_user, event_id):
    """
    Registers the authenticated user for an event.
    Concurrency Safe:
    - Uses BEGIN IMMEDIATE SQLite transaction.
    - Uses atomic conditional UPDATE: WHERE id = ? AND registered_count < capacity.
    - If 0 rows updated -> event is full (returns 409 Conflict).
    - If user already registered -> returns 409 Conflict.
    - Rolls back on any failure.
    """
    conn = get_db_connection()
    conn.isolation_level = None  # Manual transaction management
    cursor = conn.cursor()

    try:
        cursor.execute("BEGIN IMMEDIATE;")

        # 1. Check if event exists
        cursor.execute("SELECT id, capacity, registered_count FROM events WHERE id = ?", (event_id,))
        event = cursor.fetchone()
        if not event:
            cursor.execute("ROLLBACK;")
            return jsonify({"error": "Event not found"}), 404

        # 2. Check if user is already registered
        cursor.execute(
            "SELECT id FROM registrations WHERE user_id = ? AND event_id = ?",
            (current_user["id"], event_id)
        )
        if cursor.fetchone():
            cursor.execute("ROLLBACK;")
            return jsonify({"error": "User is already registered for this event."}), 409

        # 3. Atomic capacity check and increment
        cursor.execute("""
            UPDATE events 
            SET registered_count = registered_count + 1 
            WHERE id = ? AND registered_count < capacity;
        """, (event_id,))

        if cursor.rowcount == 0:
            # 0 rows updated means event is full (capacity reached)
            cursor.execute("ROLLBACK;")
            return jsonify({"error": "Event is full. Maximum capacity reached."}), 409

        # 4. Insert registration record
        cursor.execute("""
            INSERT INTO registrations (user_id, event_id) 
            VALUES (?, ?);
        """, (current_user["id"], event_id))
        registration_id = cursor.lastrowid

        # 5. Commit transaction
        cursor.execute("COMMIT;")

        return jsonify({
            "message": "Successfully registered for event",
            "registration": {
                "id": registration_id,
                "user_id": current_user["id"],
                "event_id": event_id
            }
        }), 201

    except sqlite3.IntegrityError:
        cursor.execute("ROLLBACK;")
        return jsonify({"error": "User is already registered for this event."}), 409
    except Exception as e:
        cursor.execute("ROLLBACK;")
        return jsonify({"error": f"Failed to process registration: {str(e)}"}), 500
    finally:
        conn.close()


# ----------------------------------------------------
# 11. Registrations - Cancel Registration
# ----------------------------------------------------
@app.route("/events/<int:event_id>/register", methods=["DELETE"])
@app.route("/api/events/<int:event_id>/register", methods=["DELETE"])
@token_required
def cancel_registration(current_user, event_id):
    """
    Cancels the authenticated user's registration for an event.
    Atomic Transaction:
    - Removes registration record from registrations table.
    - Decrements registered_count by 1 in events table.
    """
    conn = get_db_connection()
    conn.isolation_level = None  # Manual transaction management
    cursor = conn.cursor()

    try:
        cursor.execute("BEGIN IMMEDIATE;")

        # Check if user has an active registration for this event
        cursor.execute(
            "SELECT id FROM registrations WHERE user_id = ? AND event_id = ?",
            (current_user["id"], event_id)
        )
        reg = cursor.fetchone()
        if not reg:
            cursor.execute("ROLLBACK;")
            return jsonify({"error": "Registration not found for this user and event"}), 404

        # Delete registration
        cursor.execute("DELETE FROM registrations WHERE id = ?", (reg["id"],))

        # Decrement registered count in events table
        cursor.execute("""
            UPDATE events 
            SET registered_count = CASE WHEN registered_count > 0 THEN registered_count - 1 ELSE 0 END 
            WHERE id = ?;
        """, (event_id,))

        cursor.execute("COMMIT;")
        return jsonify({"message": "Registration cancelled successfully"}), 200

    except Exception as e:
        cursor.execute("ROLLBACK;")
        return jsonify({"error": f"Failed to cancel registration: {str(e)}"}), 500
    finally:
        conn.close()


# ----------------------------------------------------
# 12. Registrations - View Event Registrations (Admin Only)
# ----------------------------------------------------
@app.route("/events/<int:event_id>/registrations", methods=["GET"])
@app.route("/api/events/<int:event_id>/registrations", methods=["GET"])
@admin_required
def get_event_registrations(current_user, event_id):
    """
    Returns list of all registrations for an event.
    ADMIN ONLY.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, title, capacity, registered_count FROM events WHERE id = ?", (event_id,))
    event = cursor.fetchone()
    if not event:
        conn.close()
        return jsonify({"error": "Event not found"}), 404

    cursor.execute("""
        SELECT r.id, r.user_id, u.username, r.registered_at 
        FROM registrations r 
        JOIN users u ON r.user_id = u.id 
        WHERE r.event_id = ?
        ORDER BY r.registered_at ASC
    """, (event_id,))
    registrations = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return jsonify({
        "event_id": event_id,
        "event_title": event["title"],
        "capacity": event["capacity"],
        "registered_count": event["registered_count"],
        "registrations": registrations
    }), 200


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)


