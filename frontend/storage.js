const API_BASE = "";

const productForm = document.getElementById("product-form");
const productResult = document.getElementById("product-result");
const storageProducts = document.getElementById("storage-products");
const loadStorageBtn = document.getElementById("load-storage");
const photoPreview = document.getElementById("photo-preview");
const photoInput = productForm?.querySelector('input[name="photo"]');

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

function productMarkup(product, isOwner) {
  let photoHtml = '';
  if (product.photo_filename) {
    photoHtml = `<img src="/uploads/${product.photo_filename}" alt="${product.title}" style="width: 100%; max-width: 300px; height: auto; border-radius: 8px; margin-bottom: 10px; object-fit: cover;" onerror="this.style.display='none'" />`;
  } else {
    photoHtml = `<div style="width: 100%; max-width: 300px; height: 200px; background: #e5e5e5; border-radius: 8px; margin-bottom: 10px; display: flex; align-items: center; justify-content: center; color: #999;">No image</div>`;
  }
  const deleteBtn = isOwner 
    ? `<button class="api-button" onclick="deleteProduct(${product.id})" style="background: #ef4444; margin-top: 10px;">Delete</button>`
    : '';
  return `
    <div class="api-item">
      ${photoHtml}
      <h4>${product.title}</h4>
      <p>${product.description || "No description"}</p>
      <p><strong>${product.price} ${product.currency}</strong> × qty ${product.quantity}</p>
      <p><strong>Id:</strong> ${product.id}</p>
      ${deleteBtn}
    </div>
  `;
}

async function loadMyProducts() {
  try {
    const me = await api("/api/me");
    const products = await api(`/api/profiles/${me.id}/products`);
    
    if (!products.length) {
      storageProducts.innerHTML = `<div class="api-empty">No products yet.</div>`;
      return;
    }
    
    storageProducts.innerHTML = products.map(p => productMarkup(p, true)).join("");
  } catch (err) {
    storageProducts.innerHTML = `<div class="api-empty">${err.message}</div>`;
  }
}

async function deleteProduct(productId) {
  if (!confirm("Are you sure you want to delete this product?")) {
    return;
  }
  
  try {
    await api(`/api/products/${productId}`, { method: "DELETE" });
    await loadMyProducts();
  } catch (err) {
    alert(`Error: ${err.message}`);
  }
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
      await loadMyProducts();
    } catch (err) {
      if (productResult) {
        productResult.textContent = err.message;
        productResult.style.color = "#b42318";
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

if (loadStorageBtn) {
  loadStorageBtn.addEventListener("click", loadMyProducts);
}

// Load on page load
loadMyProducts();
