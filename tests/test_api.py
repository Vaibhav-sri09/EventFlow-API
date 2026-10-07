"""
test_api.py
Automated tests using pytest to verify:
1. User registration & login with JWT tokens
2. Role-based access control (Admin vs Member actions)
3. Event creation, updating, deletion, and retrieval
4. Event pagination and search filtering
5. Event registration & cancellation flows
6. Concurrency safety and atomic capacity limits under parallel requests
"""
import os
import sys
import datetime
import concurrent.futures
import pytest
import jwt

# Add backend directory to path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(BASE_DIR, "..", "backend")
sys.path.insert(0, BACKEND_DIR)

from app import app
from database import init_db, get_db_connection
from auth import JWT_SECRET, hash_password

@pytest.fixture
def client(tmp_path, monkeypatch):
    """Creates a test client with an isolated temporary SQLite database."""
    test_db = str(tmp_path / "test_app.db")
    monkeypatch.setenv("DATABASE_PATH", test_db)
    
    # Initialize schema in test database
    init_db(test_db)
    
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client

# ----------------------------------------------------
# Helper Functions
# ----------------------------------------------------
def seed_user(username, role="member", password="password123"):
    """Seeds a user directly in the database (useful for creating test admins)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
        (username, hash_password(password), role)
    )
    conn.commit()
    user_id = cursor.lastrowid
    conn.close()
    return user_id

def get_auth_headers(client, username, password="password123"):
    """Logs in and returns Authorization header with Bearer access token."""
    res = client.post("/auth/login", json={"username": username, "password": password})
    token = res.get_json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ----------------------------------------------------
# Authentication & Token Tests
# ----------------------------------------------------
def test_successful_registration(client):
    """Test standard user registration with default 'member' role."""
    response = client.post("/auth/register", json={
        "username": "alice",
        "password": "alicepassword123"
    })
    
    assert response.status_code == 201
    data = response.get_json()
    assert data["message"] == "User registered successfully"
    assert data["user"]["username"] == "alice"
    assert data["user"]["role"] == "member"
    assert "password" not in data["user"]
    assert "password_hash" not in data["user"]

def test_prevent_public_admin_registration(client):
    """Test that public registration endpoint rejects attempts to register as 'admin'."""
    response = client.post("/auth/register", json={
        "username": "sneaky_admin",
        "password": "secretpassword",
        "role": "admin"
    })
    
    assert response.status_code == 403
    data = response.get_json()
    assert "Admin account creation is not allowed" in data["error"]

def test_duplicate_user_registration_rejected(client):
    """Test that duplicate usernames return 409 Conflict."""
    client.post("/auth/register", json={
        "username": "bob",
        "password": "bobpassword123"
    })
    
    response = client.post("/auth/register", json={
        "username": "bob",
        "password": "anotherpassword"
    })
    assert response.status_code == 409
    data = response.get_json()
    assert "already exists" in data["error"]

def test_successful_login(client):
    """Test user login returns both short-lived access token and refresh token."""
    client.post("/auth/register", json={
        "username": "charlie",
        "password": "charliepassword123"
    })
    
    response = client.post("/auth/login", json={
        "username": "charlie",
        "password": "charliepassword123"
    })
    
    assert response.status_code == 200
    data = response.get_json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "Bearer"
    assert data["expires_in"] == 15 * 60
    assert data["user"]["username"] == "charlie"
    assert data["user"]["role"] == "member"

def test_invalid_login(client):
    """Test login failure with wrong password and non-existent username."""
    client.post("/auth/register", json={
        "username": "david",
        "password": "correctpassword"
    })
    
    res_wrong_pw = client.post("/auth/login", json={
        "username": "david",
        "password": "wrongpassword"
    })
    assert res_wrong_pw.status_code == 401
    assert "Invalid username or password" in res_wrong_pw.get_json()["error"]
    
    res_no_user = client.post("/auth/login", json={
        "username": "nonexistent_user",
        "password": "somepassword"
    })
    assert res_no_user.status_code == 401
    assert "Invalid username or password" in res_no_user.get_json()["error"]

def test_access_protected_me_endpoint_with_valid_token(client):
    """Test accessing /auth/me with a valid Bearer access token."""
    client.post("/auth/register", json={
        "username": "eve",
        "password": "evepassword123"
    })
    headers = get_auth_headers(client, "eve", "evepassword123")
    
    response = client.get("/auth/me", headers=headers)
    assert response.status_code == 200
    data = response.get_json()
    assert data["user"]["username"] == "eve"
    assert data["user"]["role"] == "member"

def test_reject_invalid_or_missing_token(client):
    """Test that protected endpoint rejects missing or malformed tokens."""
    res_missing = client.get("/auth/me")
    assert res_missing.status_code == 401
    assert "Authorization header is missing" in res_missing.get_json()["error"]
    
    res_malformed = client.get("/auth/me", headers={
        "Authorization": "Bearer not-a-real-jwt-token"
    })
    assert res_malformed.status_code == 401
    assert "Invalid token" in res_malformed.get_json()["error"]

def test_reject_expired_access_token(client):
    """Test that expired access token is rejected with 401."""
    past_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=30)
    expired_payload = {
        "user_id": 1,
        "username": "frank",
        "role": "member",
        "type": "access",
        "exp": past_time,
        "iat": past_time - datetime.timedelta(minutes=15)
    }
    expired_token = jwt.encode(expired_payload, JWT_SECRET, algorithm="HS256")
    
    response = client.get("/auth/me", headers={
        "Authorization": f"Bearer {expired_token}"
    })
    assert response.status_code == 401
    assert "Token has expired" in response.get_json()["error"]

def test_refresh_token_cannot_be_used_as_access_token(client):
    """Test that a refresh token is rejected when sent to access-token protected routes."""
    client.post("/auth/register", json={
        "username": "grace",
        "password": "gracepassword123"
    })
    login_res = client.post("/auth/login", json={
        "username": "grace",
        "password": "gracepassword123"
    })
    refresh_token = login_res.get_json()["refresh_token"]
    
    response = client.get("/auth/me", headers={
        "Authorization": f"Bearer {refresh_token}"
    })
    assert response.status_code == 401
    assert "Invalid token type" in response.get_json()["error"]

def test_refresh_token_flow_success(client):
    """Test successfully exchanging a valid refresh token for a new access token."""
    client.post("/auth/register", json={
        "username": "helen",
        "password": "helenpassword123"
    })
    login_res = client.post("/auth/login", json={
        "username": "helen",
        "password": "helenpassword123"
    })
    refresh_token = login_res.get_json()["refresh_token"]
    
    refresh_res = client.post("/auth/refresh", json={
        "refresh_token": refresh_token
    })
    assert refresh_res.status_code == 200
    refresh_data = refresh_res.get_json()
    assert "access_token" in refresh_data
    assert refresh_data["token_type"] == "Bearer"
    
    new_access_token = refresh_data["access_token"]
    
    me_res = client.get("/auth/me", headers={
        "Authorization": f"Bearer {new_access_token}"
    })
    assert me_res.status_code == 200
    assert me_res.get_json()["user"]["username"] == "helen"


# ----------------------------------------------------
# Events & Role-Based Access Control (RBAC) Tests
# ----------------------------------------------------
def test_admin_can_create_event(client):
    """Test that an authenticated Admin can successfully create an event."""
    admin_id = seed_user("admin_user", role="admin")
    admin_headers = get_auth_headers(client, "admin_user")
    
    event_payload = {
        "title": "Python Web Dev Summit",
        "description": "Annual conference on backend & web development",
        "date": "2026-11-15",
        "location": "Auditorium A",
        "capacity": 50
    }
    
    response = client.post("/events", json=event_payload, headers=admin_headers)
    assert response.status_code == 201
    data = response.get_json()
    assert data["message"] == "Event created successfully"
    assert data["event"]["title"] == "Python Web Dev Summit"
    assert data["event"]["capacity"] == 50
    assert data["event"]["created_by"] == admin_id
    assert data["event"]["registered_count"] == 0

def test_member_cannot_create_event(client):
    """Test that a Member receives 403 Forbidden when trying to create an event."""
    seed_user("member_user", role="member")
    member_headers = get_auth_headers(client, "member_user")
    
    event_payload = {
        "title": "Unauthorized Event",
        "description": "Should fail",
        "date": "2026-12-01",
        "location": "Room 101",
        "capacity": 20
    }
    
    response = client.post("/events", json=event_payload, headers=member_headers)
    assert response.status_code == 403
    data = response.get_json()
    assert "Admin access required" in data["error"]

def test_member_can_view_events_and_details(client):
    """Test that a Member can list events and view individual event details."""
    seed_user("admin_org", role="admin")
    admin_headers = get_auth_headers(client, "admin_org")
    
    # Admin creates event
    create_res = client.post("/events", json={
        "title": "Cloud Computing Workshop",
        "description": "Hands-on AWS and backend workshop",
        "date": "2026-10-25",
        "location": "Lab 3",
        "capacity": 30
    }, headers=admin_headers)
    event_id = create_res.get_json()["event"]["id"]
    
    # Member logs in and views events
    seed_user("member_viewer", role="member")
    member_headers = get_auth_headers(client, "member_viewer")
    
    list_res = client.get("/events", headers=member_headers)
    assert list_res.status_code == 200
    list_data = list_res.get_json()
    assert len(list_data["events"]) == 1
    assert list_data["events"][0]["title"] == "Cloud Computing Workshop"
    
    # Member views individual event
    detail_res = client.get(f"/events/{event_id}", headers=member_headers)
    assert detail_res.status_code == 200
    assert detail_res.get_json()["event"]["id"] == event_id
    assert detail_res.get_json()["event"]["title"] == "Cloud Computing Workshop"

def test_admin_can_edit_and_delete_event(client):
    """Test that an Admin can update and delete an event."""
    seed_user("admin_editor", role="admin")
    admin_headers = get_auth_headers(client, "admin_editor")
    
    # Create event
    create_res = client.post("/events", json={
        "title": "Original Title",
        "description": "Original Description",
        "date": "2026-10-30",
        "location": "Room 1",
        "capacity": 25
    }, headers=admin_headers)
    event_id = create_res.get_json()["event"]["id"]
    
    # Admin updates event
    update_res = client.put(f"/events/{event_id}", json={
        "title": "Updated Title",
        "capacity": 40
    }, headers=admin_headers)
    assert update_res.status_code == 200
    assert update_res.get_json()["event"]["title"] == "Updated Title"
    assert update_res.get_json()["event"]["capacity"] == 40
    
    # Admin deletes event
    delete_res = client.delete(f"/events/{event_id}", headers=admin_headers)
    assert delete_res.status_code == 200
    assert "deleted successfully" in delete_res.get_json()["message"]
    
    # Verify event no longer exists
    get_res = client.get(f"/events/{event_id}", headers=admin_headers)
    assert get_res.status_code == 404

def test_member_cannot_edit_or_delete_event(client):
    """Test that a Member receives 403 Forbidden when trying to edit or delete an event."""
    seed_user("admin_host", role="admin")
    admin_headers = get_auth_headers(client, "admin_host")
    
    create_res = client.post("/events", json={
        "title": "Protected Event",
        "description": "Members cannot modify this",
        "date": "2026-11-01",
        "location": "Main Hall",
        "capacity": 100
    }, headers=admin_headers)
    event_id = create_res.get_json()["event"]["id"]
    
    seed_user("member_intruder", role="member")
    member_headers = get_auth_headers(client, "member_intruder")
    
    # Member tries to edit
    put_res = client.put(f"/events/{event_id}", json={"title": "Hacked Title"}, headers=member_headers)
    assert put_res.status_code == 403
    assert "Admin access required" in put_res.get_json()["error"]
    
    # Member tries to delete
    del_res = client.delete(f"/events/{event_id}", headers=member_headers)
    assert del_res.status_code == 403
    assert "Admin access required" in del_res.get_json()["error"]

def test_events_pagination_and_filtering(client):
    """Test pagination (page, limit, total) and keyword search filtering."""
    seed_user("admin_paginator", role="admin")
    admin_headers = get_auth_headers(client, "admin_paginator")
    
    # Create 5 sample events
    events_data = [
        {"title": "Python Bootcamp Level 1", "description": "Intro to Python", "date": "2026-10-10", "location": "Room A", "capacity": 20},
        {"title": "JavaScript Frontend Fundamentals", "description": "DOM & Events", "date": "2026-10-12", "location": "Room B", "capacity": 25},
        {"title": "Python Advanced Decorators", "description": "Deep dive Python", "date": "2026-10-15", "location": "Room A", "capacity": 15},
        {"title": "SQL Database Optimization", "description": "Indexing and SQLite", "date": "2026-10-18", "location": "Room C", "capacity": 30},
        {"title": "Python Flask API Mastery", "description": "REST APIs in Python", "date": "2026-10-20", "location": "Room D", "capacity": 40},
    ]
    for ev in events_data:
        client.post("/events", json=ev, headers=admin_headers)
    
    # Test Pagination: page=1, limit=2
    res_p1 = client.get("/events?page=1&limit=2", headers=admin_headers)
    assert res_p1.status_code == 200
    p1_data = res_p1.get_json()
    assert len(p1_data["events"]) == 2
    assert p1_data["page"] == 1
    assert p1_data["limit"] == 2
    assert p1_data["total"] == 5
    assert p1_data["total_pages"] == 3
    
    # Test Pagination: page=2, limit=2
    res_p2 = client.get("/events?page=2&limit=2", headers=admin_headers)
    assert res_p2.status_code == 200
    p2_data = res_p2.get_json()
    assert len(p2_data["events"]) == 2
    assert p2_data["page"] == 2
    
    # Ensure items on page 1 and page 2 are different
    p1_ids = [e["id"] for e in p1_data["events"]]
    p2_ids = [e["id"] for e in p2_data["events"]]
    assert len(set(p1_ids).intersection(set(p2_ids))) == 0
    
    # Test Search Filtering: search=Python
    res_search = client.get("/events?search=Python", headers=admin_headers)
    assert res_search.status_code == 200
    search_data = res_search.get_json()
    assert search_data["total"] == 3
    for ev in search_data["events"]:
        assert "python" in ev["title"].lower() or "python" in ev["description"].lower()


# ----------------------------------------------------
# Event Registration & Concurrency Tests
# ----------------------------------------------------
def test_member_can_register_for_event(client):
    """Test that a member can successfully register for an event with available seats."""
    # Create event with capacity 10
    seed_user("admin_host_reg", role="admin")
    admin_headers = get_auth_headers(client, "admin_host_reg")
    create_res = client.post("/events", json={
        "title": "AI & ML Workshop",
        "description": "Intro to neural networks",
        "date": "2026-11-20",
        "location": "Auditorium",
        "capacity": 10
    }, headers=admin_headers)
    event_id = create_res.get_json()["event"]["id"]
    
    # Register member
    seed_user("attendee_1", role="member")
    member_headers = get_auth_headers(client, "attendee_1")
    
    reg_res = client.post(f"/events/{event_id}/register", headers=member_headers)
    assert reg_res.status_code == 201
    reg_data = reg_res.get_json()
    assert reg_data["message"] == "Successfully registered for event"
    assert reg_data["registration"]["event_id"] == event_id
    
    # Verify registered_count increased to 1
    event_res = client.get(f"/events/{event_id}", headers=member_headers)
    assert event_res.get_json()["event"]["registered_count"] == 1

def test_duplicate_event_registration_rejected(client):
    """Test that a member cannot register twice for the same event."""
    seed_user("admin_host_dup", role="admin")
    admin_headers = get_auth_headers(client, "admin_host_dup")
    create_res = client.post("/events", json={
        "title": "Design Systems 101",
        "description": "Figma & UI",
        "date": "2026-11-22",
        "location": "Room 5",
        "capacity": 5
    }, headers=admin_headers)
    event_id = create_res.get_json()["event"]["id"]
    
    seed_user("attendee_dup", role="member")
    member_headers = get_auth_headers(client, "attendee_dup")
    
    # First registration -> Success
    res1 = client.post(f"/events/{event_id}/register", headers=member_headers)
    assert res1.status_code == 201
    
    # Second registration -> 409 Conflict
    res2 = client.post(f"/events/{event_id}/register", headers=member_headers)
    assert res2.status_code == 409
    assert "already registered" in res2.get_json()["error"]

def test_full_event_rejects_registration(client):
    """Test that registration is rejected with 409 when event capacity is reached."""
    seed_user("admin_host_full", role="admin")
    admin_headers = get_auth_headers(client, "admin_host_full")
    create_res = client.post("/events", json={
        "title": "Small Seminar",
        "description": "Strict 2-seat limit",
        "date": "2026-11-25",
        "location": "Conference Room B",
        "capacity": 2
    }, headers=admin_headers)
    event_id = create_res.get_json()["event"]["id"]
    
    # Register 2 users to fill capacity
    for i in range(2):
        username = f"seat_holder_{i}"
        seed_user(username, role="member")
        h = get_auth_headers(client, username)
        res = client.post(f"/events/{event_id}/register", headers=h)
        assert res.status_code == 201
    
    # 3rd user tries to register -> Rejected with 409 Conflict
    seed_user("unlucky_member", role="member")
    unlucky_headers = get_auth_headers(client, "unlucky_member")
    res_overflow = client.post(f"/events/{event_id}/register", headers=unlucky_headers)
    assert res_overflow.status_code == 409
    assert "Event is full" in res_overflow.get_json()["error"]

def test_cancel_registration_decreases_count(client):
    """Test that cancelling a registration deletes the record and decreases registered_count."""
    seed_user("admin_host_cancel", role="admin")
    admin_headers = get_auth_headers(client, "admin_host_cancel")
    create_res = client.post("/events", json={
        "title": "Hackathon 2026",
        "description": "48-hour build",
        "date": "2026-12-05",
        "location": "Tech Park",
        "capacity": 50
    }, headers=admin_headers)
    event_id = create_res.get_json()["event"]["id"]
    
    seed_user("canceller_user", role="member")
    member_headers = get_auth_headers(client, "canceller_user")
    
    # Register
    reg_res = client.post(f"/events/{event_id}/register", headers=member_headers)
    assert reg_res.status_code == 201
    
    # Verify count is 1
    ev_check1 = client.get(f"/events/{event_id}", headers=member_headers)
    assert ev_check1.get_json()["event"]["registered_count"] == 1
    
    # Cancel registration
    cancel_res = client.delete(f"/events/{event_id}/register", headers=member_headers)
    assert cancel_res.status_code == 200
    assert "Registration cancelled successfully" in cancel_res.get_json()["message"]
    
    # Verify count decremented back to 0
    ev_check2 = client.get(f"/events/{event_id}", headers=member_headers)
    assert ev_check2.get_json()["event"]["registered_count"] == 0

def test_concurrent_registrations_respect_capacity(client):
    """
    Concurrency Safety Test:
    Creates an event with capacity = 1.
    Spawns 10 concurrent threads attempting to register 10 distinct users at the exact same moment.
    Verifies that exactly 1 succeeds (201 Created) and the remaining 9 are rejected with 409 Conflict,
    ensuring registered_count never exceeds capacity.
    """
    # 1. Admin creates event with capacity = 1
    seed_user("admin_conc", role="admin")
    admin_headers = get_auth_headers(client, "admin_conc")
    
    create_res = client.post("/events", json={
        "title": "Exclusive 1-Seat Masterclass",
        "description": "High demand, single seat only",
        "date": "2026-12-31",
        "location": "VIP Room",
        "capacity": 1
    }, headers=admin_headers)
    event_id = create_res.get_json()["event"]["id"]
    
    # 2. Seed 10 distinct members and get their auth headers
    num_users = 10
    user_headers = []
    for i in range(num_users):
        username = f"racer_user_{i}"
        seed_user(username, role="member")
        user_headers.append(get_auth_headers(client, username))
    
    # 3. Fire simultaneous registration requests across parallel threads
    def attempt_registration(headers):
        with app.test_client() as thread_client:
            return thread_client.post(f"/events/{event_id}/register", headers=headers)
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_users) as executor:
        responses = list(executor.map(attempt_registration, user_headers))

    
    # 4. Assert outcomes: Exactly 1 success, 9 conflicts
    status_codes = [r.status_code for r in responses]
    success_count = status_codes.count(201)
    conflict_count = status_codes.count(409)
    
    assert success_count == 1, f"Expected exactly 1 successful registration, got {success_count}"
    assert conflict_count == num_users - 1, f"Expected {num_users - 1} rejections, got {conflict_count}"
    assert success_count <= 1
    
    # 5. Verify database integrity
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT registered_count, capacity FROM events WHERE id = ?", (event_id,))
    ev = cursor.fetchone()
    assert ev["registered_count"] == 1
    assert ev["registered_count"] <= ev["capacity"]
    
    cursor.execute("SELECT COUNT(*) FROM registrations WHERE event_id = ?", (event_id,))
    total_reg = cursor.fetchone()[0]
    assert total_reg == 1
    conn.close()
