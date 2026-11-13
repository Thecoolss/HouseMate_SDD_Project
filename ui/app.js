// Shared front-end helpers: config, token storage, the fetch wrapper, the auth
// guard and the nav. Loaded by every page after config.js.

const CONFIG = window.HOUSEMATE_CONFIG;
const HOUSEHOLD = CONFIG.HOUSEHOLD_URL;
const FAIRNESS = CONFIG.FAIRNESS_URL;

// --- token + current user, kept in localStorage so they survive a page load ---------------

const TOKEN_KEY = "housemate_token";
const USER_KEY = "housemate_user";

function saveSession(token, user) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

function clearSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

function getUser() {
  const raw = localStorage.getItem(USER_KEY);
  return raw ? JSON.parse(raw) : null;
}

// --- fetch wrapper ------------------------------------------------------------------------

// Raised when a service does not answer in time or cannot be reached. The pages turn this
// into a visible "service unavailable" notice instead of a hung request (Assignment 2 §3).
class ServiceUnavailable extends Error {}

// Raised for a non-2xx JSON response; carries the status and the server's error message.
class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

// Every outbound call has a timeout, attaches the bearer token, and normalises failures.
async function apiFetch(baseUrl, path, options = {}) {
  const { timeoutMs = 5000, ...rest } = options;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  const headers = { ...(rest.headers || {}) };
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (rest.body) headers["Content-Type"] = "application/json";

  let response;
  try {
    response = await fetch(baseUrl + path, { ...rest, headers, signal: controller.signal });
  } catch (err) {
    // Network error, CORS failure, or the timeout firing: the service is effectively down.
    throw new ServiceUnavailable(`Could not reach the service at ${baseUrl}.`);
  } finally {
    clearTimeout(timer);
  }

  // An expired or invalid token: drop the session and send the user back to login.
  if (response.status === 401) {
    clearSession();
    if (!location.pathname.endsWith("index.html") && location.pathname !== "/") {
      location.href = "index.html";
    }
    throw new ApiError(401, "Your session has expired. Please log in again.");
  }

  if (response.status === 204) return null;

  let data = null;
  try {
    data = await response.json();
  } catch {
    data = null;
  }

  if (!response.ok) {
    const message = (data && data.error) || `Request failed (${response.status}).`;
    throw new ApiError(response.status, message);
  }
  return data;
}

const household = (path, options) => apiFetch(HOUSEHOLD, path, options);
const fairness = (path, options) => apiFetch(FAIRNESS, path, options);

// --- auth guard + nav ---------------------------------------------------------------------

// Call at the top of every page except the login page. Redirects to login if there is no
// token, and renders the shared nav bar.
function requireLogin() {
  if (!getToken()) {
    location.href = "index.html";
    return false;
  }
  renderNav();
  return true;
}

function renderNav() {
  const user = getUser();
  const nav = document.querySelector("nav");
  if (!nav) return;
  const page = location.pathname.split("/").pop() || "index.html";
  const link = (href, label) =>
    `<a href="${href}"${page === href ? ' aria-current="page"' : ""}>${label}</a>`;
  nav.innerHTML = `
    <span class="brand">HouseMate</span>
    ${link("tasks.html", "Tasks")}
    ${link("bookings.html", "Bookings")}
    ${link("fairness.html", "Contribution/Fairness")}
    <span class="nav-user">${user ? escapeHtml(user.username) : ""}</span>
    <button type="button" id="logout-btn">Logout</button>
  `;
  document.getElementById("logout-btn").addEventListener("click", () => {
    clearSession();
    location.href = "index.html";
  });
}

// --- small helpers ------------------------------------------------------------------------

// Escape user-supplied strings before putting them in innerHTML (usernames, titles, etc.).
function escapeHtml(value) {
  if (value === null || value === undefined) return "";
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

// Show a message in the page's .flash area, styled as error or success.
function flash(message, kind = "error") {
  const box = document.querySelector(".flash");
  if (!box) return;
  box.textContent = message;
  box.className = `flash flash-${kind}`;
  box.hidden = false;
}

function clearFlash() {
  const box = document.querySelector(".flash");
  if (box) box.hidden = true;
}

// Turn an error from apiFetch into a flash message.
function flashError(err) {
  if (err instanceof ServiceUnavailable) {
    flash("This service is currently unavailable. Please try again shortly.", "error");
  } else if (err instanceof ApiError) {
    flash(err.message, "error");
  } else {
    flash("Something went wrong.", "error");
    console.error(err);
  }
}

// --- datetime helpers ---------------------------------------------------------------------

// The services return UTC ISO strings with a Z suffix. Show them in the browser's local time.
function formatDateTime(iso) {
  if (!iso) return "";
  const date = new Date(iso);
  return date.toLocaleString([], {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatDate(iso) {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString([], { year: "numeric", month: "short", day: "2-digit" });
}

// A <input type="datetime-local"> value is local wall-clock time with no zone. The services
// read a naive datetime as household local time, so send it through as-is (no Z).
function localInputToSend(value) {
  return value || null;
}
