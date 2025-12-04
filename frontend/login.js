// frontend/login.js
/**
 * Admin Login Page Script
 * =======================
 * Handles admin authentication and token storage
 */

document.addEventListener('DOMContentLoaded', () => {
    // Check if already logged in
    const token = localStorage.getItem('adminToken');
    if (token) {
        // Verify token is still valid
        verifyTokenAndRedirect(token);
    }
    
    // Setup form submission
    const loginForm = document.getElementById('loginForm');
    loginForm.addEventListener('submit', handleLogin);
});

/**
 * Verify if stored token is still valid
 */
async function verifyTokenAndRedirect(token) {
    try {
        const response = await fetch('http://127.0.0.1:7070/api/admin/queries', {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (response.ok) {
            // Token is valid, redirect to the main device list page (/)
            window.location.href = '/';
        } else {
            // Token is invalid, clear it
            localStorage.removeItem('adminToken');
            localStorage.removeItem('adminUsername');
        }
    } catch (error) {
        console.error('Token verification failed:', error);
    }
}

/**
 * Handle login form submission
 */
async function handleLogin(event) {
    event.preventDefault();
    
    const loginButton = document.getElementById('loginButton');
    const errorMessage = document.getElementById('errorMessage');
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    
    // Disable button and show loading state
    loginButton.disabled = true;
    loginButton.textContent = 'Logging in...';
    errorMessage.classList.remove('show');
    
    try {
        const response = await fetch('http://127.0.0.1:7070/api/admin/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                username: username,
                password: password
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            // Login successful
            console.log('Login successful');
            
            // Store token and username in localStorage
            localStorage.setItem('adminToken', data.access_token);
            localStorage.setItem('adminUsername', data.username);
            
            // Redirect to the main device list page (/)
            window.location.href = '/';
        } else {
            // Login failed
            showError(data.detail || 'Invalid credentials. Please try again.');
            loginButton.disabled = false;
            loginButton.textContent = 'Login';
        }
    } catch (error) {
        console.error('Login error:', error);
        showError('Connection error. Please check if the server is running.');
        loginButton.disabled = false;
        loginButton.textContent = 'Login';
    }
}

/**
 * Display error message
 */
function showError(message) {
    const errorMessage = document.getElementById('errorMessage');
    errorMessage.textContent = message;
    errorMessage.classList.add('show');
    
    // Auto-hide after 5 seconds
    setTimeout(() => {
        errorMessage.classList.remove('show');
    }, 5000);
}