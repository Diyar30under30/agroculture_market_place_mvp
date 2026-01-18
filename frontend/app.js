const API_BASE = "http://127.0.0.1:8000";

const statusEl = document.getElementById("status");
const refreshBtn = document.getElementById("refresh");
const profileForm = document.getElementById("profile-form");
const productForm = document.getElementById("product-form");
const productResult = document.getElementById("product-result");
const profileIdInput = document.getElementById("profile-id");
const fetchProfileBtn = document.getElementById("fetch-profile");
const profileDetails = document.getElementById("profile-details");
const ownerFilter = document.getElementById("owner-filter");
const searchInput = document.getElementById("search");
const fetchProductsBtn = document.getElementById("fetch-products");
const productsList = document.getElementById("products");

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

function setStatus(text, tone = "neutral") {
  if (!statusEl) return;
  statusEl.textContent = text;
  statusEl.style.color = tone === "ok" ? "#0e7c2a" : tone === "error" ? "#b42318" : "#5a5a5a";
}

function profileMarkup(profile) {
  return `
    <div class="api-item">
      <h4>${profile.name}</h4>
      <p><strong>Email:</strong> ${profile.email}</p>
      <p><strong>Phone:</strong> ${profile.phone || "-"}</p>
      <p><strong>City:</strong> ${profile.city || "-"}</p>
      <p><strong>About:</strong> ${profile.about || "-"}</p>
      <p><strong>Id:</strong> ${profile.id}</p>
    </div>
  `;
}

function productMarkup(product) {
  return `
    <div class="api-item">
      <h4>${product.title}</h4>
      <p>${product.description || "No description"}</p>
      <p><strong>${product.price} ${product.currency}</strong> · qty ${product.quantity}</p>
      <p><strong>Owner:</strong> ${product.owner_id} · <strong>Id:</strong> ${product.id}</p>
    </div>
  `;
}

async function checkHealth() {
  try {
    await api("/api/health");
    setStatus("API online", "ok");
  } catch (err) {
    setStatus(`API offline: ${err.message}`, "error");
  }
}

async function refreshProducts() {
  if (!productsList) return;
  try {
    const params = new URLSearchParams();
    if (ownerFilter && ownerFilter.value) params.append("owner_id", ownerFilter.value);
    if (searchInput && searchInput.value.trim()) params.append("q", searchInput.value.trim());

    const data = await api(`/api/products?${params.toString()}`);
    if (!data.length) {
      productsList.innerHTML = `<div class="api-empty">No products yet.</div>`;
      return;
    }
    productsList.innerHTML = data.map(productMarkup).join("");
  } catch (err) {
    productsList.innerHTML = `<div class="api-empty">${err.message}</div>`;
  }
}

if (profileForm) {
  profileForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(profileForm);
    const payload = Object.fromEntries(formData.entries());

    try {
      const profile = await api("/api/profiles", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      if (profileDetails) {
        profileDetails.innerHTML = profileMarkup(profile);
      }
      profileForm.reset();
    } catch (err) {
      if (profileDetails) {
        profileDetails.innerHTML = `<div class="api-empty">${err.message}</div>`;
      }
    }
  });
}

if (productForm) {
  productForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(productForm);
    const payload = Object.fromEntries(formData.entries());

    payload.price = Number(payload.price);
    payload.quantity = Number(payload.quantity || 1);

    try {
      const product = await api("/api/products/by-me", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      if (productResult) {
        productResult.textContent = `Product created (id ${product.id})`;
        productResult.style.color = "#0e7c2a";
      }
      productForm.reset();
      await refreshProducts();
    } catch (err) {
      if (productResult) {
        productResult.textContent = err.message;
        productResult.style.color = "#b42318";
      } else if (productsList) {
        productsList.innerHTML = `<div class="api-empty">${err.message}</div>`;
      }
    }
  });
}

if (fetchProfileBtn) {
  fetchProfileBtn.addEventListener("click", async () => {
    const id = profileIdInput ? profileIdInput.value : "";
    if (!id) {
      if (profileDetails) {
        profileDetails.innerHTML = `<div class="api-empty">Enter a profile id.</div>`;
      }
      return;
    }

    try {
      const profile = await api(`/api/profiles/${id}`);
      if (profileDetails) {
        profileDetails.innerHTML = profileMarkup(profile);
      }
    } catch (err) {
      if (profileDetails) {
        profileDetails.innerHTML = `<div class="api-empty">${err.message}</div>`;
      }
    }
  });
}

if (fetchProductsBtn) {
  fetchProductsBtn.addEventListener("click", refreshProducts);
}

if (refreshBtn) {
  refreshBtn.addEventListener("click", async () => {
    await checkHealth();
    await refreshProducts();
  });
}

checkHealth();
refreshProducts();
