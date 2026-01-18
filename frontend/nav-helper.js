// Helper to show/hide admin link based on user role
async function updateNavigation() {
    try {
        const response = await fetch("/api/me");
        if (response.ok) {
            const user = await response.json();
            const adminLink = document.querySelector('a[href="/admin"]');
            if (adminLink && adminLink.parentElement) {
                // Show/hide the list item containing the admin link
                if (user.is_admin) {
                    adminLink.parentElement.style.display = "block";
                } else {
                    adminLink.parentElement.style.display = "none";
                }
            }
        }
    } catch (error) {
        console.error("Error updating navigation:", error);
    }
}

// Update navigation when page loads
document.addEventListener("DOMContentLoaded", updateNavigation);
