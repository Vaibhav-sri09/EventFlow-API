# Event Registration API

A beginner-friendly full-stack application for managing and registering for events. Built with **Python Flask**, **SQLite**, **HTML/CSS**, and vanilla **JavaScript `fetch()`**.

---

## 📁 Project Structure

```text
event-registration-api/
│
├── backend/
│   ├── app.py          # Flask REST API endpoints (Auth, Events, Registrations)
│   ├── database.py     # SQLite connection helper & schema creation
│   ├── auth.py         # Password hashing & JWT (Access + Refresh) auth
│   └── seed.py         # Seed script for initial admin/member accounts and sample events
│
├── frontend/
│   ├── index.html      # Landing / Home page
│   ├── login.html      # User login and registration page
│   ├── events.html     # Browse, search, and register for events
│   ├── admin.html      # Admin dashboard for creating & managing events
│   ├── style.css       # Clean, modern CSS styling
│   └── script.js       # Minimal vanilla JavaScript using fetch() for API communication
│
├── tests/
│   └── test_api.py     # 21 automated pytest test cases covering all requirements
│
├── database/
│   └── app.db          # SQLite database file
│
├── requirements.txt    # Python package dependencies
└── README.md           # Project documentation and guide
```

---

## 🚀 Quick Start Guide

### 1. Install Dependencies
```powershell
pip install -r requirements.txt
```

### 2. Initialize & Seed the Database
```powershell
python backend/seed.py
```
*Creates initial database and default accounts:*
* **Admin**: `username: admin`, `password: admin123`
* **Member**: `username: member`, `password: member123`

### 3. Start the Backend API
```powershell
python backend/app.py
```
*The API runs at `http://127.0.0.1:5000`.*

### 4. Open the Frontend
Open `frontend/index.html` (or `frontend/login.html`) directly in any web browser.

---

## 🧪 Running Automated Tests

Run the complete test suite with pytest:
```powershell
python -m pytest tests/test_api.py -v
```

**21 passed test cases**, verifying:
* User registration, password hashing with Werkzeug, and duplicate prevention
* Public admin creation blocking (403 Forbidden)
* Login returning short-lived access token (15 min) and refresh token (7 days)
* Token refresh flow (`POST /auth/refresh`)
* Role-based access control (Admin CRUD vs Member viewing)
* Event pagination (`?page=1&limit=10`) and search filtering (`?search=keyword`)
* Event seat registration & cancellation
* Concurrency safety under parallel requests using atomic conditional updates and SQLite transactions
