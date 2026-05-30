// Konfigurasi Global
const API_URL = "http://localhost:8000/api/v1";
const BASE_PATH = window.location.pathname.includes('/layer3_dashboard/') ? '' : 'layer3_dashboard/';

let lastAlertId = 0;

// Fungsi util: tanggal hari ini di WIB (YYYY-MM-DD)
function getTodayWIB() {
    const now = new Date();
    const wibOffset = 7 * 60; // menit
    const localOffset = now.getTimezoneOffset();
    const wibTime = new Date(now.getTime() + (wibOffset + localOffset) * 60000);
    return wibTime.toISOString().split('T')[0];
}

// Jam digital di topnav (WIB)
setInterval(() => {
    const clockEl = document.getElementById('clock');
    if (!clockEl) return;
    clockEl.textContent = new Date().toLocaleTimeString('id-ID', {
        timeZone: 'Asia/Jakarta',
        hour: '2-digit', minute: '2-digit', second: '2-digit'
    });
}, 1000);

function checkAuth() {
    const token = localStorage.getItem("access_token");
    if (!token && !window.location.href.includes("login.html")) {
        window.location.href = BASE_PATH + "login.html";
    }
    return token;
}

function setActiveNav(pageName) {
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.page === pageName);
    });
}

function setPageTheme(pageName) {
    document.body.classList.remove('page-dashboard', 'page-cameras', 'page-reports', 'page-settings');
    document.body.classList.add(`page-${pageName}`);
}

async function loadPage(evt, pageName) {
    if (window.pageIntervalId) {
        clearInterval(window.pageIntervalId);
        window.pageIntervalId = null;
    }

    checkAuth();
    setActiveNav(pageName);
    setPageTheme(pageName);

    const contentDiv = document.getElementById('app-content');
    try {
        const response = await fetch(`${BASE_PATH}pages/${pageName}.html`);
        if (!response.ok) throw new Error(`Gagal memuat halaman ${pageName}`);
        const html = await response.text();
        contentDiv.innerHTML = html;
        loadPageScript(pageName);
    } catch (error) {
        contentDiv.innerHTML = `<div class="loading-state">⚠️ Gagal memuat halaman ${pageName}</div>`;
        console.error(error);
    }
}

function loadPageScript(pageName) {
    const oldScript = document.getElementById('dynamic-script');
    if (oldScript) oldScript.remove();

    const script = document.createElement('script');
    script.id = 'dynamic-script';
    script.src = `${BASE_PATH}js/${pageName}.js`;
    script.onload = () => console.log(`Loaded page script: ${pageName}`);
    script.onerror = () => console.error(`Failed to load page script: ${pageName}`);
    document.body.appendChild(script);
}

// Polling Alert (UC-08)
setInterval(async () => {
    if (!localStorage.getItem("access_token")) return;

    try {
        const res = await apiFetch(`${API_URL}/detections/alerts/latest`);
        if (!res || !res.ok) return;
        const alerts = await res.json();

        const latest = alerts[0];
        if (latest && latest.alert_id > lastAlertId) {
            showNotification(latest.message);
            try {
                await apiFetch(`${API_URL}/detections/alerts/${latest.alert_id}/read`, { method: 'PATCH' });
            } catch (e) {
                console.warn('Gagal menandai alert read');
            }
            lastAlertId = latest.alert_id;
        }
    } catch (e) {
        console.error('Polling alert gagal', e);
    }
}, POLL_INTERVAL);

function showNotification(msg) {
    const toast = document.createElement('div');
    toast.className = 'alert-toast';
    toast.innerText = "🚨 " + msg;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 5000);
}

// Router & Init
document.addEventListener("DOMContentLoaded", () => {
    if (checkAuth()) loadPage(null, 'dashboard');
});