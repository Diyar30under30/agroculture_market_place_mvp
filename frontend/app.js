const API_BASE = "http://127.0.0.1:8000";

const statusEl = document.getElementById("status");
const refreshBtn = document.getElementById("refresh");
const profileForm = document.getElementById("profile-form");
const productForm = document.getElementById("product-form");
const productResult = document.getElementById("product-result");
const photoPreview = document.getElementById("photo-preview");
const photoInput = productForm?.querySelector('input[name="photo"]');
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
  const photoHtml = product.photo_filename 
    ? `<img src="/uploads/${product.photo_filename}" style="max-width: 200px; height: auto; border-radius: 8px; margin-bottom: 10px;" />`
    : '';
  return `
    <div class="api-item">
      ${photoHtml}
      <h4>${product.title}</h4>
      <p>${product.description || "No description"}</p>
      <p><strong>${product.price} ${product.currency}</strong> × qty ${product.quantity}</p>
      <p><strong>Owner:</strong> ${product.owner_id} – <strong>Id:</strong> ${product.id}</p>
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
    // Get current user info if logged in
    let currentUserId = null;
    let isAdmin = false;
    try {
      const me = await api("/api/me");
      currentUserId = me.id;
      isAdmin = me.is_admin;
    } catch {
      // Not logged in
    }

    const params = new URLSearchParams();
    if (ownerFilter && ownerFilter.value) params.append("owner_id", ownerFilter.value);
    if (searchInput && searchInput.value.trim()) params.append("q", searchInput.value.trim());

    const data = await api(`/api/products?${params.toString()}`);
    if (!data.length) {
      productsList.innerHTML = `<div class="api-empty">No products yet.</div>`;
      return;
    }
    
    productsList.innerHTML = data.map(product => {
      const isOwner = currentUserId === product.owner_id;
      const canDelete = isOwner || isAdmin;
      let photoHtml = '';
      if (product.photo_filename) {
        photoHtml = `<img src="/uploads/${product.photo_filename}" alt="${product.title}" style="width: 100%; max-width: 300px; height: auto; border-radius: 8px; margin-bottom: 10px; object-fit: cover;" onerror="this.style.display='none'" />`;
      } else {
        photoHtml = `<div style="width: 100%; max-width: 300px; height: 200px; background: #e5e5e5; border-radius: 8px; margin-bottom: 10px; display: flex; align-items: center; justify-content: center; color: #999;">No image</div>`;
      }
      const deleteBtn = canDelete 
        ? `<button class="api-button" onclick="deleteProduct(${product.id})" style="background: #ef4444; margin-top: 10px;">Delete</button>`
        : '';
      return `
        <div class="api-item">
          ${photoHtml}
          <h4>${product.title}</h4>
          <p>${product.description || "No description"}</p>
          <p><strong>${product.price} ${product.currency}</strong> × qty ${product.quantity}</p>
          <p><strong>Owner:</strong> ${product.owner_id} – <strong>Id:</strong> ${product.id}</p>
          ${deleteBtn}
        </div>
      `;
    }).join("");
  } catch (err) {
    productsList.innerHTML = `<div class="api-empty">${err.message}</div>`;
  }
}

async function deleteProduct(productId) {
  if (!confirm("Are you sure you want to delete this product?")) {
    return;
  }
  
  try {
    await api(`/api/products/${productId}`, { method: "DELETE" });
    await refreshProducts();
  } catch (err) {
    alert(`Error: ${err.message}`);
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
    const photoFile = formData.get("photo");
    
    const payload = {
      title: formData.get("title"),
      description: formData.get("description"),
      price: Number(formData.get("price")),
      currency: formData.get("currency") || "KZT",
      quantity: Number(formData.get("quantity") || 1),
    };

    try {
      const product = await api("/api/products/by-me", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      
      // Upload photo if provided
      if (photoFile && photoFile.size > 0) {
        try {
          const photoFormData = new FormData();
          photoFormData.append("file", photoFile);
          
          const photoResponse = await fetch(`${API_BASE}/api/products/${product.id}/upload-photo`, {
            method: "POST",
            body: photoFormData,
            credentials: "include",
          });
          
          if (!photoResponse.ok) {
            const errorData = await photoResponse.json();
            throw new Error(errorData.detail || "Photo upload failed");
          }
        } catch (photoErr) {
          if (productResult) {
            productResult.textContent = `Product created (id ${product.id}) but photo upload failed: ${photoErr.message}`;
            productResult.style.color = "#f59e0b";
          }
        }
      }
      
      if (productResult) {
        productResult.textContent = `Product created (id ${product.id})${photoFile && photoFile.size > 0 ? ' with photo' : ''}`;
        productResult.style.color = "#0e7c2a";
      }
      productForm.reset();
      if (photoPreview) photoPreview.style.display = "none";
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
  
  // Photo preview
  if (photoInput) {
    photoInput.addEventListener("change", (e) => {
      const file = e.target.files[0];
      if (file && photoPreview) {
        const reader = new FileReader();
        reader.onload = (event) => {
          photoPreview.src = event.target.result;
          photoPreview.style.display = "block";
        };
        reader.readAsDataURL(file);
      }
    });
  }
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
