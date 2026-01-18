const API_BASE = "http://127.0.0.1:8000";

const registerForm = document.getElementById("register-form");
const registerResult = document.getElementById("register-result");
const loginForm = document.getElementById("login-form");
const loginResult = document.getElementById("login-result");

async function api(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    ...options,
  });

  if (!response.ok) {
    let message = "Request failed";
    try {
      const data = await response.json();
      message = data.detail || message;
    } catch {
      // ignore JSON parse errors
    }
    throw new Error(message);
  }

  if (response.status === 204) {
    return null;
  }
  return response.json();
}

function showResult(el, message, ok = false) {
  if (!el) return;
  el.textContent = message;
  el.style.color = ok ? "#0e7c2a" : "#b42318";
}

if (registerForm) {
  registerForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(registerForm);
    const payload = Object.fromEntries(formData.entries());

    try {
      const profile = await api("/api/auth/register", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      showResult(registerResult, `Registered: ${profile.name} (id ${profile.id})`, true);
      registerForm.reset();
    } catch (err) {
      showResult(registerResult, err.message);
    }
  });
}

if (loginForm) {
  loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(loginForm);
    const payload = Object.fromEntries(formData.entries());

    try {
      const profile = await api("/api/auth/login", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      showResult(loginResult, `Welcome back, ${profile.name} (id ${profile.id})`, true);
      loginForm.reset();
    } catch (err) {
      showResult(loginResult, err.message);
    }
  });
}
