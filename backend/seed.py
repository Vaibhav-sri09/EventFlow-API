"""
seed.py
Seeds the SQLite database with:
1. Default Admin user (username: admin, password: admin123)
2. Default Member user (username: member, password: member123)
3. Initial sample events
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from database import init_db, get_db_connection
from auth import hash_password

def seed_database():
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Create Admin
    admin_pw = hash_password("admin123")
    cursor.execute("""
        INSERT OR IGNORE INTO users (id, username, password_hash, role)
        VALUES (1, 'admin', ?, 'admin');
    """, (admin_pw,))

    # 2. Create Member
    member_pw = hash_password("member123")
    cursor.execute("""
        INSERT OR IGNORE INTO users (id, username, password_hash, role)
        VALUES (2, 'member', ?, 'member');
    """, (member_pw,))

    # 3. Create Sample Events
    sample_events = [
        (1, "Python Web Development Bootcamp", "Hands-on Flask, APIs, and SQLite fundamentals.", "2026-11-10", "Tech Auditorium 1", 30, 1),
        (2, "AI & Machine Learning Workshop", "Deep dive into PyTorch and Neural Networks.", "2026-11-15", "Innovation Lab", 25, 1),
        (3, "Cloud & DevOps Masterclass", "Containerization with Docker and cloud deployment on AWS.", "2026-11-20", "Seminar Hall B", 15, 1),
        (4, "Exclusive 1-Seat VIP Session", "One-on-one architectural consultation.", "2026-12-01", "Boardroom", 1, 1),
    ]

    for ev_id, title, desc, date, loc, cap, creator in sample_events:
        cursor.execute("""
            INSERT OR IGNORE INTO events (id, title, description, date, location, capacity, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?);
        """, (ev_id, title, desc, date, loc, cap, creator))

    conn.commit()
    conn.close()
    print("Database seeded successfully with default users ('admin' / 'admin123', 'member' / 'member123') and sample events.")

if __name__ == "__main__":
    seed_database()
