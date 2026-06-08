// ─────────────────────────────────────────────
// main.js — STMS Dashboard
// Perubahan dari versi lama:
//   1. DOM Caching pada loadPage() agar Live Video tidak ter-refresh/lag.
//   2. Script per-halaman hanya di-load 1x seumur hidup.
// ─────────────────────────────────────────────

const API_URL = "http://localhost:8000/api/v1";
const BASE_PATH = '';
let lastAlertId = 0;

// ── CLOCK (WIB) ───────────────────────────────
setInterval(() => {
    const clockEl = document.getElementById('clock');
    if (!clockEl) return;
    clockEl.textContent = new Date().toLocaleTimeString('id-ID', {
        timeZone: 'Asia/Jakarta',
        hour: '2-digit', minute: '2-digit', second: '2-digit'
    });
    const lu = document.getElementById('lastUpdate');
    if (lu) lu.textContent = 'Updated ' + new Date().toLocaleTimeString('id-ID', {
        timeZone: 'Asia/Jakarta', hour: '2-digit', minute: '2-digit'
    });
}, 1000);

// ── AUTH ──────────────────────────────────────
function checkAuth() {
    const token = localStorage.getItem("access_token");
    if (!token && !window.location.href.includes("login.html")) {
        window.location.href = '/login.html';
    }
    return token;
}

// ── ACTIVE NAV ────────────────────────────────
function setActiveNav(pageName) {
    document.querySelectorAll('.nav-link, .nav-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.page === pageName);
    });
}

function setPageTheme(pageName) {
    document.body.classList.remove('page-dashboard', 'page-cameras', 'page-reports', 'page-settings');
    document.body.classList.add(`page-${pageName}`);
}

// ── PAGE LOADER (DOM CACHING STRATEGY) ────────
async function loadPage(evt, pageName) {
    checkAuth();
    setActiveNav(pageName);
    setPageTheme(pageName);

    const contentDiv = document.getElementById('app-content');

    // 1. Sembunyikan SEMUA halaman yang sedang aktif di dalam app-content
    Array.from(contentDiv.children).forEach(child => {
        if (child.classList.contains('page-wrapper')) {
            child.style.display = 'none';
        }
    });

    // 2. Cari apakah halaman ini sudah pernah dimuat sebelumnya
    let pageContainer = document.getElementById(`page-wrapper-${pageName}`);

    if (!pageContainer) {
        // JIKA BELUM ADA: Tarik dari server, buat bungkusannya (wrapper)
        try {
            const response = await fetch(`${BASE_PATH}pages/${pageName}.html`);
            if (!response.ok) throw new Error(`Gagal memuat halaman ${pageName}`);
            const html = await response.text();

            pageContainer = document.createElement('div');
            pageContainer.id = `page-wrapper-${pageName}`;
            pageContainer.className = 'page-wrapper';
            pageContainer.style.width = '100%';
            pageContainer.style.height = '100%';
            pageContainer.innerHTML = html;
            
            contentDiv.appendChild(pageContainer);
            
            // Muat script khusus halaman ini (Hanya dilakukan SATU KALI)
            loadPageScript(pageName);
        } catch (error) {
            console.error(error);
            return;
        }
    } else {
        // JIKA SUDAH ADA: Tinggal dimunculkan kembali (Video tidak terputus!)
        pageContainer.style.display = 'block';
    }
}

function loadPageScript(pageName) {
    const script = document.createElement('script');
    script.id = `script-${pageName}`;
    script.src = `${BASE_PATH}js/${pageName}.js`;
    script.onload = () => console.log(`✅ Loaded: ${pageName}.js`);
    script.onerror = () => console.error(`❌ Failed to load: ${pageName}.js`);
    document.body.appendChild(script);
}

// ── SIDEBAR KAMERA (dinamis dari API) ─────────
async function loadSidebarCameras() {
    const sidebar = document.getElementById('camera-sidebar');
    if (!sidebar || !localStorage.getItem('access_token')) return;

    try {
        const res = await fetch(`${API_URL}/cameras`);
        if (!res || !res.ok) return;

        const cameras = await res.json();
        const locations = {};
        cameras.forEach(cam => {
            const loc = cam.location_name || 'Unknown';
            if (!locations[loc]) locations[loc] = [];
            locations[loc].push(cam);
        });

        const colorByStatus = s => s === 'active' ? 'var(--green)' : 'var(--red)';
        const glowByStatus  = s => s === 'active' ? '0 0 5px var(--green)' : '0 0 5px var(--red)';

        const html = Object.entries(locations).map(([loc, cams]) => {
            const allActive = cams.every(c => c.status === 'active');
            const locColor  = allActive ? 'var(--green)' : 'var(--red)';
            const locGlow   = allActive ? '0 0 5px var(--green)' : '0 0 5px var(--red)';
            return `
                <div class="location-item">
                    <div class="location-header">
                        <div class="location-dot" style="background:${locColor};box-shadow:${locGlow}"></div>
                        <div class="location-name">${loc}</div>
                    </div>
                    <div class="cam-list">
                        ${cams.map(c => `
                            <div class="cam-item">
                                <div class="cam-status-dot" style="background:${colorByStatus(c.status)}"></div>
                                ${c.camera_id}
                            </div>
                        `).join('')}
                    </div>
                </div>`;
        }).join('');

        sidebar.innerHTML = `
            <div class="sidebar-label">Locations</div>
            ${html}
            <div class="divider" style="margin-top:auto"></div>
            <div class="sidebar-label">Refresh · 5s</div>
            <div class="sidebar-label" id="lastUpdate">Updated --:--</div>
        `;
    } catch (e) {
        console.error('Sidebar load error', e);
    }
}

// ── ALERT POLLING (UC-08) ─────────────────────
setInterval(async () => {
    if (!localStorage.getItem("access_token")) return;
    try {
        const res = await fetch(`${API_URL}/detections/alerts/latest`);
        if (!res || !res.ok) return;
        const alerts = await res.json();
        const latest = alerts[0];
        if (latest && latest.alert_id > lastAlertId) {
            showNotification(latest.message);
            try {
                await fetch(`${API_URL}/detections/alerts/${latest.alert_id}/read`, { method: 'PATCH' });
            } catch (e) { console.warn('Gagal mark alert read'); }
            lastAlertId = latest.alert_id;
        }
    } catch (e) { console.error('Alert polling error', e); }
}, 5000); // 5 Detik Polling

function showNotification(msg) {
    const toast = document.createElement('div');
    toast.className = 'alert-toast';
    toast.innerText = "🚨 " + msg;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 5000);
}

// ── INIT ──────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
    if (checkAuth()) {
        loadPage(null, 'dashboard');
        loadSidebarCameras();
        setInterval(loadSidebarCameras, 30000);
    }
});