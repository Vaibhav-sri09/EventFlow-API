# EventFlow API

A full-stack event registration system built with **Python, Flask, SQLite, HTML, CSS, and JavaScript**. This project demonstrates REST API development, JWT authentication, role-based access control, and concurrency-safe event registration.

## ✨ Features

* **User Authentication:** Registration and login with securely hashed passwords.
* **JWT Authentication:** Short-lived access tokens and a refresh token flow.
* **Role-Based Access Control:** Separate permissions for members and administrators.
* **Event Management:** Create, browse, search, and manage events.
* **Event Registration:** Register for events and cancel registrations.
* **Capacity Management:** Prevents registrations from exceeding available seats.
* **Search & Pagination:** Filter events and browse results page by page.
* **Concurrency Safety:** Uses SQLite transactions and atomic conditional updates to help prevent overbooking.
* **Automated Testing:** 21 tests covering authentication, authorization, and event registration.

## 🛠️ Tech Stack

| Technology | Purpose                                     |
| ---------- | ------------------------------------------- |
| Python     | Backend programming                         |
| Flask      | REST API development                        |
| SQLite     | Database management                         |
| JWT        | Token-based authentication                  |
| HTML & CSS | Frontend structure and styling              |
| JavaScript | Frontend interactions and API communication |
| Pytest     | Automated testing                           |

## 📁 Project Structure

```text
EventFlow-API/
├── backend/
│   ├── app.py
│   ├── auth.py
│   ├── database.py
│   └── seed.py
├── frontend/
│   ├── index.html
│   ├── login.html
│   ├── events.html
│   ├── admin.html
│   ├── style.css
│   └── script.js
├── tests/
│   └── test_api.py
├── database/
│   └── app.db
├── requirements.txt
└── README.md
```

## 🚀 Getting Started

### Prerequisites

* Python installed
* Git installed

### 1. Clone the repository

```bash
git clone https://github.com/Vaibhav-sri09/EventFlow-API.git
cd EventFlow-API
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Initialize the database

```bash
python backend/seed.py
```

This initializes the database and creates the default accounts configured in the seed script.

### 4. Start the backend

```bash
python backend/app.py
```

The API runs at `http://127.0.0.1:5000`.

### 5. Open the frontend

Open `frontend/index.html` in your browser. Ensure the backend is running and the frontend's API URL matches your local server.

## 🧪 Running Tests

Run the automated test suite from the project root:

```bash
python -m pytest tests/test_api.py -v
```

The test suite contains **21 automated tests** covering:

* User registration and password hashing
* Login and token validation
* Access token expiration and refresh flow
* Role-based access restrictions
* Duplicate registration prevention
* Event registration and cancellation
* Pagination and search
* Registration capacity and concurrent requests

## 🔐 Key Backend Concepts

* **Authentication vs Authorization:** Verifying user identity and controlling access to protected operations.
* **Relational Data:** Connecting events and registrations through database relationships.
* **Transactions:** Maintaining database consistency during registration.
* **Concurrency Handling:** Preventing capacity violations when requests overlap.
* **API Testing:** Checking expected behavior and handling invalid requests.

## 🎯 What I Learned

Building this project helped me gain practical experience in designing REST APIs, connecting a frontend to a backend, implementing authentication, managing relational data, and testing important edge cases.

## 👨‍💻 Author

**Vaibhav Sri Sannidh**

* GitHub: [@Vaibhav-sri09](https://github.com/Vaibhav-sri09)
* Repository: [EventFlow-API](https://github.com/Vaibhav-sri09/EventFlow-API)

---

*Built as a hands-on project to practise backend development and API design.*
