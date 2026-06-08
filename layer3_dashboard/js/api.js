// ═══════════════════════════════════════════════════════════════════════════════
// api.js — STMS Dashboard API Utilities
//
// Handles all API communication with backend.
// Authentication, error handling, token management.
//
// FIXED: Dynamic API_BASE for local + Docker environments
// ═══════════════════════════════════════════════════════════════════════════════

// Determine API_BASE dynamically based on environment
// Local: http://localhost:8000 (direct connection)
// Docker: /api (proxied through nginx)
const API_BASE = (() => {
    const isLocalhost = window.location.hostname === 'localhost' || 
                       window.location.hostname === '127.0.0.1';
    
    if (isLocalhost) {
        // Local development: direct connection to backend
        return 'http://localhost:8000';
    } else {
        // Docker / Production: use relative path, nginx proxies to backend
        // Assumes nginx.conf has:
        // location /api { proxy_pass http://backend:8000; }
        return '/api';
    }
})();

const POLL_INTERVAL = 5000;  // 5 seconds

console.log(`[API] BASE URL: ${API_BASE} (hostname: ${window.location.hostname})`);


// ═══════════════════════════════════════════════════════════════════════════════
// TOKEN MANAGEMENT
// ═══════════════════════════════════════════════════════════════════════════════

function getToken() {
    const token = localStorage.getItem('access_token');
    if (!token) {
        // Redirect to login if no token
        console.warn('[API] No token found, redirecting to login');
        window.location.href = '/login.html';
        return null;
    }
    return token;
}


// ═══════════════════════════════════════════════════════════════════════════════
// JWT DECODING (for getting user info without backend call)
// ═══════════════════════════════════════════════════════════════════════════════

function decodeJWT(token) {
    try {
        // JWT format: header.payload.signature
        const payload = token.split('.')[1];
        
        // Pad with '=' to make valid base64
        const padded = payload.padEnd(payload.length + (4 - (payload.length % 4)) % 4, '=');
        
        // Convert base64url to base64
        const base64 = padded.replace(/-/g, '+').replace(/_/g, '/');
        
        // Decode and parse
        const decoded = atob(base64);
        return JSON.parse(decoded);
    } catch (e) {
        console.error('[JWT] Decode error:', e);
        return null;
    }
}


function getUserRole() {
    const token = localStorage.getItem('access_token');
    if (!token) return null;
    
    const payload = decodeJWT(token);
    return payload ? payload.role : null;
}


// ═══════════════════════════════════════════════════════════════════════════════
// API FETCH WRAPPER
// ═══════════════════════════════════════════════════════════════════════════════

async function apiFetch(url, options = {}) {
    const token = getToken();
    if (!token) return null;

    // Set up headers
    const headers = {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
        ...(options.headers || {})
    };

    try {
        console.log(`[API] ${options.method || 'GET'} ${url}`);
        
        const response = await fetch(url, { ...options, headers });
        
        // Handle auth errors
        if (response.status === 401) {
            console.error('[API] Unauthorized (401), clearing token');
            localStorage.removeItem('access_token');
            window.location.href = '/login.html';
            return null;
        }
        
        // Log response status
        if (!response.ok) {
            console.warn(`[API] Response ${response.status}`);
        }
        
        return response;
    } catch (err) {
        console.error('[API] Fetch error:', err);
        return null;
    }
}


// ═══════════════════════════════════════════════════════════════════════════════
// AUTH & SESSION
// ═══════════════════════════════════════════════════════════════════════════════

function logout() {
    console.log('[API] Logging out');
    localStorage.removeItem('access_token');
    localStorage.removeItem('username');
    localStorage.removeItem('role');
    window.location.href = '/login.html';
}


function isAuthenticated() {
    const token = localStorage.getItem('access_token');
    if (!token) return false;
    
    // Check token expiration
    const payload = decodeJWT(token);
    if (!payload || !payload.exp) return false;
    
    const now = Math.floor(Date.now() / 1000);
    return payload.exp > now;
}


// ═══════════════════════════════════════════════════════════════════════════════
// UTILITY: Build full URL
// ═══════════════════════════════════════════════════════════════════════════════

function buildApiUrl(path) {
    // Remove leading slash if present
    const cleanPath = path.startsWith('/') ? path : '/' + path;
    return API_BASE + cleanPath;
}


// ═══════════════════════════════════════════════════════════════════════════════
// ERROR HANDLING
// ═══════════════════════════════════════════════════════════════════════════════

function handleApiError(error, defaultMessage = 'API Error') {
    console.error('[API] Error:', error);
    return defaultMessage;
}