const API_BASE = 'http://localhost:8000';
const POLL_INTERVAL = 5000;

function getToken() {
    const token = localStorage.getItem('access_token');
    if (!token) {
        window.location.href = '/login.html';
        return null;
    }
    return token;
}

function decodeJWT(token) {
    try {
        const payload = token.split('.')[1];
        const padded = payload.padEnd(payload.length + (4 - (payload.length % 4)) % 4, '=');
        const base64 = padded.replace(/-/g, '+').replace(/_/g, '/');
        const decoded = atob(base64);
        return JSON.parse(decoded);
    } catch (e) {
        return null;
    }
}

function getUserRole() {
    const token = localStorage.getItem('access_token');
    if (!token) return null;
    const payload = decodeJWT(token);
    return payload ? payload.role : null;
}

async function apiFetch(url, options = {}) {
    const token = getToken();
    if (!token) return null;

    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
        ...(options.headers || {})
    };

    try {
        const response = await fetch(url, { ...options, headers });
        if (response.status === 401) {
            localStorage.removeItem('access_token');
            window.location.href = '/login.html';
            return null;
        }
        return response;
    } catch (err) {
        console.error('API fetch error:', err);
        return null;
    }
}

function logout() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('username');
    localStorage.removeItem('role');
    window.location.href = '/login.html';
}
