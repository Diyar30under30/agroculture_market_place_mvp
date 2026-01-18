const API_BASE = "";

const registerForm = document.getElementById("register-form");
const registerResult = document.getElementById("register-result");
const loginForm = document.getElementById("login-form");
const loginResult = document.getElementById("login-result");
const loadProfileBtn = document.getElementById("load-profile");
const profileDetails = document.getElementById("profile-details");

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

if (loadProfileBtn) {
  loadProfileBtn.addEventListener("click", async () => {
    try {
      const profile = await api("/api/me");
      const adminStatus = profile.is_admin ? "✓ Admin" : "User";
      profileDetails.innerHTML = `
        <div class="api-item">
          <h4>${profile.name}</h4>
          <p><strong>Email:</strong> ${profile.email}</p>
          <p><strong>Id:</strong> ${profile.id}</p>
          <p><strong>Status:</strong> ${adminStatus}</p>
        </div>
      `;
    } catch (err) {
      showResult(profileDetails, err.message);
    }
  });
}
