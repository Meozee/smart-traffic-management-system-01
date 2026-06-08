// ─────────────────────────────────────────────
// dashboard.js — STMS Dashboard (REVISI FINAL)
// ─────────────────────────────────────────────

let currentAlertId = null;
let trendChartInstance = null;
let classChartInstance = null;
const startTime = Date.now();

const CAMERA_COLORS = ['#4e73df', '#1cc88a', '#e74a3b', '#f6c23e'];

async function fetchDashboardData() {
    try {
        const today = new Date().toISOString().split('T')[0];
        // 1. Data History (FIX: Gunakan rute history yang benar)
        const historyRes = await apiFetch(`${API_BASE}/api/v1/density/history?start_date=${today}T00:00:00Z&end_date=${today}T23:59:59Z`);
        
        // 2. Data Realtime
        const realtimeRes = await apiFetch(`${API_BASE}/api/v1/density/realtime`);
        
        // 3. Active alerts (FIX: Pindah ke rute /alerts/ dengan query status=active)
        const alertsRes = await apiFetch(`${API_BASE}/api/v1/alerts/?status=active`);

        if (historyRes && historyRes.ok) {
            const historyData = await historyRes.json();
            renderTrendChart(historyData.data || []);
        }

        if (realtimeRes && realtimeRes.ok) {
            const realtimeData = await realtimeRes.json();
            updateDensityWidgets(realtimeData);
            renderClassificationChart(realtimeData);
            renderDensityTable(realtimeData);
            renderFeedPreviews(realtimeData);
        }

        if (alertsRes && alertsRes.ok) {
            const alertsData = await alertsRes.json();
            updateAlertWidget(alertsData);
            showAlertNotification(alertsData);
            renderAlertList(alertsData);
        }

        const camerasRes = await apiFetch(`${API_BASE}/api/v1/cameras/`);
        if (camerasRes && camerasRes.ok) {
            const camerasData = await camerasRes.json();
            updateActiveCamerasWidget(camerasData);
        }

    } catch (error) {
        console.error('Dashboard Error:', error);
    }
}

// ── WIDGETS ──
function updateDensityWidgets(densityData) {
    const totalVehicles = densityData.reduce((sum, d) => sum + (d.total_vehicles || 0), 0);
    const el = document.getElementById('val-vehicles');
    if (el) el.textContent = totalVehicles.toLocaleString('id-ID');
}

function updateActiveCamerasWidget(camerasData) {
    const activeCount = camerasData.filter(c => c.status === 'active').length;
    const el = document.getElementById('val-active-cameras');
    if (el) el.textContent = activeCount;
}

function updateAlertWidget(alertsData) {
    const el = document.getElementById('val-alerts');
    if (el) el.textContent = alertsData.length;
}

function showAlertNotification(alertsData) {
    const bar = document.getElementById('alert-notification-bar');
    const text = document.getElementById('alert-notification-text');
    if (!bar || !text) return;

    if (alertsData.length > 0) {
        const latest = alertsData[0];
        currentAlertId = latest.alert_id;
        text.textContent = `⚠️ ${latest.message}`;
        bar.style.display = 'flex';
    } else {
        bar.style.display = 'none';
        currentAlertId = null;
    }
}

// ── CHARTS ──
function renderTrendChart(historyData) {
    const ctx = document.getElementById('trendChart');
    if (!ctx) return;

    // Kelompokkan data per jam
    const hourlyMap = {};
    historyData.forEach(d => {
        const hour = new Date(d.timestamp).getHours();
        const label = `${String(hour).padStart(2, '0')}:00`;
        if (!hourlyMap[label]) hourlyMap[label] = 0;
        hourlyMap[label] += d.total_vehicles || 0;
    });

    const labels = Object.keys(hourlyMap).sort();
    const data = labels.map(l => hourlyMap[l]);

    if (trendChartInstance) trendChartInstance.destroy();

    trendChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels,
            datasets: [{
                label: 'Total Kendaraan',
                data,
                borderColor: '#4e73df',
                backgroundColor: 'rgba(78,115,223,0.08)',
                borderWidth: 2,
                pointRadius: 3,
                fill: true,
                tension: 0.3
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { ticks: { autoSkip: true, maxTicksLimit: 12 } },
                y: { beginAtZero: true }
            }
        }
    });
}

function renderClassificationChart(realtimeData) {
    const ctx = document.getElementById('classChart');
    if (!ctx) return;

    // Agregat per tipe kendaraan dari semua kamera
    const totals = { car: 0, truck: 0, motorcycle: 0, bus: 0 };
    realtimeData.forEach(d => {
        totals.car        += d.car_count        || 0;
        totals.truck      += d.truck_count      || 0;
        totals.motorcycle += d.motorcycle_count || 0;
        totals.bus        += d.bus_count        || 0;
    });

    const labels = ['Mobil', 'Truk', 'Motor', 'Bus'];
    const data   = [totals.car, totals.truck, totals.motorcycle, totals.bus];
    const colors = ['#4e73df', '#e74a3b', '#1cc88a', '#f6c23e'];

    if (classChartInstance) classChartInstance.destroy();

    classChartInstance = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels,
            datasets: [{
                data,
                backgroundColor: colors,
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { position: 'bottom' } },
            cutout: '65%'
        }
    });
}

// ── RENDER FEED PREVIEW (FIX: Token Injection) ──
function renderFeedPreviews(densityData) {
    const grid = document.getElementById('dashboard-feed-grid');
    if (!grid) return;
    const token = getToken();

    grid.innerHTML = densityData.map(d => `
        <div class="feed-card" style="border: 1px solid #ddd; padding: 10px; border-radius: 8px;">
            <div class="feed-header"><b>${d.camera_id}</b></div>
            <img src="${API_BASE}/api/v1/stream/${d.camera_id}?token=${token}" 
                 alt="Stream" style="width:100%; height:200px; object-fit:cover; border-radius:4px; margin-top:10px;">
            <div class="feed-footer" style="margin-top:10px; font-size:12px;">Density: ${d.density_level}</div>
        </div>
    `).join('');
}

// ── ALERT ACKNOWLEDGE (FIX: Rute POST) ──
async function acknowledgeAlertItem(alertId) {
    // FIX: Menggunakan rute POST baru yang disepakati
    const res = await apiFetch(`${API_BASE}/api/v1/alerts/${alertId}/acknowledge`, { 
        method: 'POST' 
    });
    if (res && res.ok) fetchDashboardData();
}

// ── INIT ──
function initDashboardPage() {
    if (!getToken()) return;
    fetchDashboardData();
    window.pageIntervalId = setInterval(fetchDashboardData, POLL_INTERVAL);
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initDashboardPage);
} else {
    initDashboardPage();
}