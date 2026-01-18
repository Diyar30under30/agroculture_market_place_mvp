const API_BASE = "";

let currentUser = null;

// Load current user on page load
document.addEventListener("DOMContentLoaded", async () => {
    try {
        const response = await fetch("/api/me");
        if (response.ok) {
            currentUser = await response.json();
            // Check if user is admin
            if (!currentUser.is_admin) {
                document.body.innerHTML = "<h1>Access Denied</h1><p>You do not have permission to access this page.</p>";
            }
        } else {
            window.location.href = "/profile";
        }
    } catch (error) {
        console.error("Error loading user:", error);
        window.location.href = "/profile";
    }
});

async function loadAllUsers() {
    try {
        const response = await fetch("/api/admin/users");
        if (!response.ok) {
            if (response.status === 403) {
                alert("You don't have admin access");
            } else {
                throw new Error(`HTTP ${response.status}`);
            }
            return;
        }

        const users = await response.json();
        const container = document.getElementById("users-container");
        container.innerHTML = "";

        if (users.length === 0) {
            container.innerHTML = "<p>No users found.</p>";
            return;
        }

        const table = document.createElement("table");
        table.className = "admin-table";
        table.innerHTML = `
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Name</th>
                    <th>Email</th>
                    <th>Phone</th>
                    <th>City</th>
                    <th>Admin</th>
                    <th>Created</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
            </tbody>
        `;

        const tbody = table.querySelector("tbody");
        users.forEach(user => {
            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td>${user.id}</td>
                <td>${user.name}</td>
                <td>${user.email}</td>
                <td>${user.phone || "—"}</td>
                <td>${user.city || "—"}</td>
                <td>${user.is_admin ? "✓ Admin" : "User"}</td>
                <td>${new Date(user.created_at).toLocaleDateString()}</td>
                <td>
                    ${user.id !== currentUser.id ? 
                        `<button onclick="deleteUser(${user.id}, '${user.name}')" class="btn-delete">Delete</button>` 
                        : "—"}
                </td>
            `;
            tbody.appendChild(tr);
        });

        container.appendChild(table);
    } catch (error) {
        console.error("Error loading users:", error);
        alert("Error loading users: " + error.message);
    }
}

async function deleteUser(userId, userName) {
    if (!confirm(`Are you sure you want to delete user "${userName}" and all their products?`)) {
        return;
    }

    try {
        const response = await fetch(`/api/admin/users/${userId}`, {
            method: "DELETE",
        });

        if (!response.ok) {
            const data = await response.json();
            alert("Error: " + (data.detail || "Failed to delete user"));
            return;
        }

        alert("User deleted successfully");
        loadAllUsers();
    } catch (error) {
        console.error("Error deleting user:", error);
        alert("Error deleting user: " + error.message);
    }
}

async function loadAllProducts() {
    try {
        const response = await fetch("/api/admin/products");
        if (!response.ok) {
            if (response.status === 403) {
                alert("You don't have admin access");
            } else {
                throw new Error(`HTTP ${response.status}`);
            }
            return;
        }

        const products = await response.json();
        const container = document.getElementById("products-container");
        container.innerHTML = "";

        if (products.length === 0) {
            container.innerHTML = "<p>No products found.</p>";
            return;
        }

        const table = document.createElement("table");
        table.className = "admin-table";
        table.innerHTML = `
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Title</th>
                    <th>Price</th>
                    <th>Quantity</th>
                    <th>Owner ID</th>
                    <th>Photo</th>
                    <th>Created</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
            </tbody>
        `;

        const tbody = table.querySelector("tbody");
        products.forEach(product => {
            const tr = document.createElement("tr");
            const photoStatus = product.photo_filename ? "✓ Yes" : "—";
            tr.innerHTML = `
                <td>${product.id}</td>
                <td>${product.title}</td>
                <td>${product.price} ${product.currency}</td>
                <td>${product.quantity}</td>
                <td>${product.owner_id}</td>
                <td>${photoStatus}</td>
                <td>${new Date(product.created_at).toLocaleDateString()}</td>
                <td>
                    <button onclick="deleteProduct(${product.id}, '${product.title}')" class="btn-delete">Delete</button>
                </td>
            `;
            tbody.appendChild(tr);
        });

        container.appendChild(table);
    } catch (error) {
        console.error("Error loading products:", error);
        alert("Error loading products: " + error.message);
    }
}

async function deleteProduct(productId, productTitle) {
    if (!confirm(`Delete product "${productTitle}"?`)) {
        return;
    }

    try {
        const response = await fetch(`/api/products/${productId}`, {
            method: "DELETE",
        });

        if (!response.ok) {
            const data = await response.json();
            alert("Error: " + (data.detail || "Failed to delete product"));
            return;
        }

        alert("Product deleted successfully");
        loadAllProducts();
    } catch (error) {
        console.error("Error deleting product:", error);
        alert("Error deleting product: " + error.message);
    }
}
