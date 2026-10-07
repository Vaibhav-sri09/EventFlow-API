// Event Registration Portal - Client-Side JavaScript
const API_BASE_URL = "http://127.0.0.1:5000";

// --- Token and User Helpers ---
function getAccessToken() {
    return localStorage.getItem("accessToken");
}

function getRefreshToken() {
    return localStorage.getItem("refreshToken");
}

function getCurrentUser() {
    const userStr = localStorage.getItem("user");
    return userStr ? JSON.parse(userStr) : null;
}

function saveAuth(data) {
    if (data.access_token) localStorage.setItem("accessToken", data.access_token);
    if (data.refresh_token) localStorage.setItem("refreshToken", data.refresh_token);
    if (data.user) localStorage.setItem("user", JSON.stringify(data.user));
}

function logout() {
    localStorage.removeItem("accessToken");
    localStorage.removeItem("refreshToken");
    localStorage.removeItem("user");
    window.location.href = "login.html";
}

// Display alert messages on pages
function showMessage(elementId, text, isError = false) {
    const el = document.getElementById(elementId);
    if (!el) return;
    el.textContent = text;
    el.className = isError ? "message-box message-error" : "message-box message-success";
    el.style.display = "block";
    setTimeout(() => {
        // Optional auto hide after 5 seconds
    }, 5000);
}

// Update navbar based on login state
function updateNavbar() {
    const user = getCurrentUser();
    const userDisplay = document.getElementById("user-display");
    const loginBtn = document.getElementById("nav-login-btn");
    const logoutBtn = document.getElementById("logout-btn");
    const adminLink = document.getElementById("nav-admin-link");

    if (user) {
        if (userDisplay) userDisplay.textContent = `Hello, ${user.username} (${user.role})`;
        if (loginBtn) loginBtn.style.display = "none";
        if (logoutBtn) {
            logoutBtn.style.display = "inline-block";
            logoutBtn.onclick = logout;
        }
        if (adminLink && user.role === "admin") {
            adminLink.style.display = "inline-block";
        }
    } else {
        if (userDisplay) userDisplay.textContent = "";
        if (loginBtn) loginBtn.style.display = "inline-block";
        if (logoutBtn) logoutBtn.style.display = "none";
        if (adminLink) adminLink.style.display = "none";
    }
}


// --- 1. Login & Registration Page Logic ---
function initAuthPage() {
    const loginForm = document.getElementById("login-form");
    const registerForm = document.getElementById("register-form");
    const showRegister = document.getElementById("show-register");
    const showLogin = document.getElementById("show-login");
    const loginBox = document.getElementById("login-box");
    const registerBox = document.getElementById("register-box");

    if (showRegister && showLogin) {
        showRegister.addEventListener("click", (e) => {
            e.preventDefault();
            loginBox.style.display = "none";
            registerBox.style.display = "block";
        });
        showLogin.addEventListener("click", (e) => {
            e.preventDefault();
            registerBox.style.display = "none";
            loginBox.style.display = "block";
        });
    }

    if (loginForm) {
        loginForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const username = document.getElementById("login-username").value.trim();
            const password = document.getElementById("login-password").value.trim();

            try {
                const response = await fetch(`${API_BASE_URL}/auth/login`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ username, password })
                });
                const data = await response.json();

                if (response.ok) {
                    saveAuth(data);
                    showMessage("login-message", "Login successful! Redirecting...", false);
                    setTimeout(() => {
                        window.location.href = data.user.role === "admin" ? "admin.html" : "events.html";
                    }, 800);
                } else {
                    showMessage("login-message", data.error || "Login failed", true);
                }
            } catch (err) {
                showMessage("login-message", "Unable to connect to server. Is Flask running?", true);
            }
        });
    }

    if (registerForm) {
        registerForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const username = document.getElementById("reg-username").value.trim();
            const password = document.getElementById("reg-password").value.trim();

            try {
                const response = await fetch(`${API_BASE_URL}/auth/register`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ username, password })
                });
                const data = await response.json();

                if (response.ok) {
                    showMessage("register-message", "Account registered! You can now log in.", false);
                    setTimeout(() => {
                        registerBox.style.display = "none";
                        loginBox.style.display = "block";
                        document.getElementById("login-username").value = username;
                    }, 1200);
                } else {
                    showMessage("register-message", data.error || "Registration failed", true);
                }
            } catch (err) {
                showMessage("register-message", "Unable to connect to server.", true);
            }
        });
    }
}


// --- 2. Events Page Logic ---
let currentPage = 1;
let currentSearch = "";

async function loadEvents(page = 1, search = "") {
    const token = getAccessToken();
    const grid = document.getElementById("events-grid");
    if (!grid) return;

    if (!token) {
        grid.innerHTML = `<div class="card"><p>Please <a href="login.html">Login</a> to view and register for events.</p></div>`;
        return;
    }

    try {
        let url = `${API_BASE_URL}/events?page=${page}&limit=6`;
        if (search) {
            url += `&search=${encodeURIComponent(search)}`;
        }

        const response = await fetch(url, {
            headers: { "Authorization": `Bearer ${token}` }
        });
        const data = await response.json();

        if (response.status === 401) {
            grid.innerHTML = `<p class="message-error">Session expired. Please <a href="login.html">log in again</a>.</p>`;
            return;
        }

        if (!response.ok) {
            showMessage("event-message", data.error || "Failed to load events", true);
            return;
        }

        if (data.events.length === 0) {
            grid.innerHTML = `<p>No events found.</p>`;
            return;
        }

        // Render event cards
        grid.innerHTML = data.events.map(ev => {
            const isFull = ev.registered_count >= ev.capacity;
            const badgeClass = isFull ? "badge-full" : "badge-success";
            const badgeText = isFull ? "Full" : `${ev.capacity - ev.registered_count} seats left`;

            return `
                <div class="card event-card">
                    <div>
                        <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                            <h3>${escapeHtml(ev.title)}</h3>
                            <span class="badge ${badgeClass}">${badgeText}</span>
                        </div>
                        <p>${escapeHtml(ev.description || "No description provided.")}</p>
                        <div class="event-meta">
                            <span>📅 <strong>Date:</strong> ${escapeHtml(ev.date)}</span>
                            <span>📍 <strong>Location:</strong> ${escapeHtml(ev.location)}</span>
                            <span>👥 <strong>Capacity:</strong> ${ev.registered_count} / ${ev.capacity}</span>
                        </div>
                    </div>
                    <div class="event-actions">
                        <button class="btn btn-primary btn-sm" onclick="registerForEvent(${ev.id})" ${isFull ? 'disabled' : ''}>
                            ${isFull ? 'Full' : 'Register'}
                        </button>
                        <button class="btn btn-secondary btn-sm" onclick="cancelEventRegistration(${ev.id})">
                            Cancel Registration
                        </button>
                    </div>
                </div>
            `;
        }).join("");

        // Update Pagination controls
        const pageIndicator = document.getElementById("page-indicator");
        const prevBtn = document.getElementById("prev-page-btn");
        const nextBtn = document.getElementById("next-page-btn");

        if (pageIndicator) pageIndicator.textContent = `Page ${data.page} of ${data.total_pages}`;
        if (prevBtn) prevBtn.disabled = data.page <= 1;
        if (nextBtn) nextBtn.disabled = data.page >= data.total_pages;

    } catch (err) {
        grid.innerHTML = `<p class="message-error">Could not connect to API server.</p>`;
    }
}

async function registerForEvent(eventId) {
    const token = getAccessToken();
    if (!token) {
        alert("Please login first!");
        window.location.href = "login.html";
        return;
    }

    try {
        const res = await fetch(`${API_BASE_URL}/events/${eventId}/register`, {
            method: "POST",
            headers: {
                "Authorization": `Bearer ${token}`,
                "Content-Type": "application/json"
            }
        });
        const data = await res.json();

        if (res.ok) {
            showMessage("event-message", "Registered successfully for event!", false);
            loadEvents(currentPage, currentSearch);
        } else {
            showMessage("event-message", data.error || "Registration failed", true);
        }
    } catch (err) {
        showMessage("event-message", "Network error when attempting registration", true);
    }
}

async function cancelEventRegistration(eventId) {
    const token = getAccessToken();
    if (!token) return;

    if (!confirm("Are you sure you want to cancel your registration?")) return;

    try {
        const res = await fetch(`${API_BASE_URL}/events/${eventId}/register`, {
            method: "DELETE",
            headers: {
                "Authorization": `Bearer ${token}`
            }
        });
        const data = await res.json();

        if (res.ok) {
            showMessage("event-message", "Registration cancelled successfully.", false);
            loadEvents(currentPage, currentSearch);
        } else {
            showMessage("event-message", data.error || "Could not cancel registration", true);
        }
    } catch (err) {
        showMessage("event-message", "Network error when attempting cancellation", true);
    }
}

function initEventsPage() {
    const searchBtn = document.getElementById("search-btn");
    const searchInput = document.getElementById("search-input");
    const prevBtn = document.getElementById("prev-page-btn");
    const nextBtn = document.getElementById("next-page-btn");

    if (searchBtn && searchInput) {
        searchBtn.addEventListener("click", () => {
            currentSearch = searchInput.value.trim();
            currentPage = 1;
            loadEvents(currentPage, currentSearch);
        });
        searchInput.addEventListener("keypress", (e) => {
            if (e.key === "Enter") {
                currentSearch = searchInput.value.trim();
                currentPage = 1;
                loadEvents(currentPage, currentSearch);
            }
        });
    }

    if (prevBtn) {
        prevBtn.addEventListener("click", () => {
            if (currentPage > 1) {
                currentPage--;
                loadEvents(currentPage, currentSearch);
            }
        });
    }

    if (nextBtn) {
        nextBtn.addEventListener("click", () => {
            currentPage++;
            loadEvents(currentPage, currentSearch);
        });
    }

    loadEvents(currentPage, currentSearch);
}


// --- 3. Admin Dashboard Logic ---
async function loadAdminEvents() {
    const token = getAccessToken();
    const tbody = document.getElementById("admin-events-body");
    if (!tbody) return;

    try {
        const response = await fetch(`${API_BASE_URL}/events?limit=100`, {
            headers: { "Authorization": `Bearer ${token}` }
        });
        const data = await response.json();

        if (!response.ok) {
            tbody.innerHTML = `<tr><td colspan="7" class="message-error">${data.error || "Failed to load events"}</td></tr>`;
            return;
        }

        if (data.events.length === 0) {
            tbody.innerHTML = `<tr><td colspan="7">No events created yet.</td></tr>`;
            return;
        }

        tbody.innerHTML = data.events.map(ev => `
            <tr>
                <td>${ev.id}</td>
                <td><strong>${escapeHtml(ev.title)}</strong></td>
                <td>${escapeHtml(ev.date)}</td>
                <td>${escapeHtml(ev.location)}</td>
                <td>${ev.capacity}</td>
                <td>${ev.registered_count}</td>
                <td>
                    <button class="btn btn-sm btn-secondary" onclick="adminEditEvent(${ev.id}, '${escapeHtml(ev.title)}', ${ev.capacity})">Edit</button>
                    <button class="btn btn-sm btn-outline" style="color: var(--danger); border-color: var(--danger);" onclick="adminDeleteEvent(${ev.id})">Delete</button>
                </td>
            </tr>
        `).join("");
    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="7">Network error loading events table.</td></tr>`;
    }
}

async function adminEditEvent(id, currentTitle, currentCapacity) {
    const newTitle = prompt("Enter new title for event:", currentTitle);
    if (!newTitle) return;
    const newCapacity = prompt("Enter new capacity for event:", currentCapacity);
    if (!newCapacity) return;

    const token = getAccessToken();
    try {
        const res = await fetch(`${API_BASE_URL}/events/${id}`, {
            method: "PUT",
            headers: {
                "Authorization": `Bearer ${token}`,
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                title: newTitle,
                capacity: parseInt(newCapacity, 10)
            })
        });
        const data = await res.json();

        if (res.ok) {
            showMessage("admin-message", "Event updated successfully!", false);
            loadAdminEvents();
        } else {
            showMessage("admin-message", data.error || "Failed to update event", true);
        }
    } catch (err) {
        showMessage("admin-message", "Error updating event", true);
    }
}

async function adminDeleteEvent(id) {
    if (!confirm(`Are you sure you want to delete event #${id}?`)) return;

    const token = getAccessToken();
    try {
        const res = await fetch(`${API_BASE_URL}/events/${id}`, {
            method: "DELETE",
            headers: { "Authorization": `Bearer ${token}` }
        });
        const data = await res.json();

        if (res.ok) {
            showMessage("admin-message", "Event deleted successfully.", false);
            loadAdminEvents();
        } else {
            showMessage("admin-message", data.error || "Failed to delete event", true);
        }
    } catch (err) {
        showMessage("admin-message", "Error deleting event", true);
    }
}

function initAdminPage() {
    const user = getCurrentUser();
    const adminContent = document.getElementById("admin-content");
    const accessDenied = document.getElementById("admin-access-denied");

    if (!user || user.role !== "admin") {
        if (adminContent) adminContent.style.display = "none";
        if (accessDenied) accessDenied.style.display = "block";
        return;
    }

    if (adminContent) adminContent.style.display = "block";
    if (accessDenied) accessDenied.style.display = "none";

    const createForm = document.getElementById("create-event-form");
    if (createForm) {
        createForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            const title = document.getElementById("event-title").value.trim();
            const date = document.getElementById("event-date").value;
            const location = document.getElementById("event-location").value.trim();
            const capacity = parseInt(document.getElementById("event-capacity").value, 10);
            const description = document.getElementById("event-desc").value.trim();

            const token = getAccessToken();
            try {
                const res = await fetch(`${API_BASE_URL}/events`, {
                    method: "POST",
                    headers: {
                        "Authorization": `Bearer ${token}`,
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify({ title, date, location, capacity, description })
                });
                const data = await res.json();

                if (res.ok) {
                    showMessage("admin-message", "Event created successfully!", false);
                    createForm.reset();
                    loadAdminEvents();
                } else {
                    showMessage("admin-message", data.error || "Failed to create event", true);
                }
            } catch (err) {
                showMessage("admin-message", "Error submitting new event", true);
            }
        });
    }

    loadAdminEvents();
}

function escapeHtml(str) {
    if (!str) return "";
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// Global initialization
document.addEventListener("DOMContentLoaded", () => {
    updateNavbar();
    initAuthPage();
    if (document.getElementById("events-grid")) initEventsPage();
    if (document.getElementById("admin-content")) initAdminPage();
});
