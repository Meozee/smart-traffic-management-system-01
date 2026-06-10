// ─────────────────────────────────────────────
// dashboard.js — STMS Dashboard (FIXED FINAL)
// Fixes:
//   1. Canvas ID sync dengan dashboard.html
//   2. renderDensityTable & renderAlertList implemented
//   3. interval_start field digunakan untuk trend chart
//   4. Uptime counter berjalan
//   5. stream token pakai localStorage langsung
// ─────────────────────────────────────────────

let currentAlertId = null;
let trendChartInstance = null;
let classChartInstance = null;
const startTime = Date.now();

// Update uptime setiap detik
setInterval(() => {
    const el = document.getElementById('val-uptime');
    if (!el) return;
    const elapsed = Math.floor((Date.now() - startTime) / 1000);
    const h = Math.floor(elapsed / 3600);
    const m = Math.floor((elapsed % 3600) / 60);
    const s = elapsed % 60;
    el.textContent = h > 0
        ? `${h}j ${m}m`
        : m > 0 ? `${m}m ${s}s` : `${s}s`;
}, 1000);

async function fetchDashboardData() {
    try {
        const today = new Date().toISOString().split('T')[0];

        // 1. History untuk trend chart (hari ini)
        const historyRes = await apiFetch(`${API_BASE}/api/v1/density/history?start_date=${today}T00:00:00Z&end_date=${today}T23:59:59Z`);

        // 2. Realtime density
        const realtimeRes = await apiFetch(`${API_BASE}/api/v1/density/realtime`);

        // 3. Active alerts
        const alertsRes = await apiFetch(`${API_BASE}/api/v1/alerts/?status=active`);

        if (historyRes && historyRes.ok) {
            const historyData = await historyRes.json();
            const chartData = Array.isArray(historyData) ? historyData : (historyData.data || []);
            renderTrendChart(chartData);
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
    const label = document.getElementById('alert-count-label');
    if (label) label.textContent = alertsData.length;
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

// ── DENSITY TABLE (Current Status) ──
function renderDensityTable(realtimeData) {
    const tbody = document.getElementById('density-status-tbody');
    if (!tbody) return;

    if (!realtimeData || realtimeData.length === 0) {
        tbody.innerHTML = '<tr><td colspan="3" style="text-align:center;color:#aaa;padding:10px;">Tidak ada data realtime.</td></tr>';
        return;
    }

    const levelColor = { High: '#e74a3b', Medium: '#f6c23e', Low: '#1cc88a' };

    tbody.innerHTML = realtimeData.map(d => `
        <tr style="border-bottom: 1px solid #eee;">
            <td style="padding:8px;font-weight:bold;">${d.camera_id}</td>
            <td style="padding:8px;">
                <span style="background:${levelColor[d.density_level] || '#aaa'}22;
                             color:${levelColor[d.density_level] || '#666'};
                             padding:2px 8px; border-radius:4px; font-size:11px; font-weight:bold;">
                    ${d.density_level || '-'}
                </span>
            </td>
            <td style="padding:8px;font-family:monospace;">${d.total_vehicles ?? 0}</td>
        </tr>
    `).join('');
}

// ── ALERT LIST ──
function renderAlertList(alertsData) {
    const container = document.getElementById('alert-list-container');
    if (!container) return;

    if (!alertsData || alertsData.length === 0) {
        container.innerHTML = '<div style="padding:20px;text-align:center;color:#aaa;">Tidak ada alert aktif. ✅</div>';
        return;
    }

    container.innerHTML = alertsData.slice(0, 5).map(a => `
        <div class="alert-item" style="border-left: 3px solid #e74a3b; background:#fff5f5;
                padding: 10px 12px; margin-bottom: 8px; border-radius: 4px; font-size:13px;">
            <div style="font-weight:bold;color:#c62828;">🚨 ${a.camera_id}</div>
            <div style="color:#555; margin: 4px 0;">${a.message || 'Kepadatan tinggi terdeteksi.'}</div>
            <div style="display:flex; justify-content:space-between; align-items:center; margin-top:6px;">
                <span style="color:#999;font-size:11px;">
                    ${a.triggered_at ? new Date(a.triggered_at).toLocaleString('id-ID') : ''}
                </span>
                <button onclick="acknowledgeAlertItem(${a.alert_id})"
                    style="background:#e74a3b;color:white;border:none;border-radius:4px;
                           padding:3px 10px;cursor:pointer;font-size:11px;">
                    ✓ Ack
                </button>
            </div>
        </div>
    `).join('');
}

// ── TREND CHART (canvas: trafficTrendChart) ──
function renderTrendChart(historyData) {
    // Support both canvas IDs (dashboard.html uses 'trafficTrendChart')
    const ctx = document.getElementById('trafficTrendChart') || document.getElementById('trendChart');
    if (!ctx) return;

    // Kelompokkan per jam, gunakan interval_start (dari /density/history)
    const hourlyMap = {};
    historyData.forEach(d => {
        const ts = d.interval_start || d.timestamp;
        if (!ts) return;
        const hour = new Date(ts).getHours();
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
            labels: labels.length > 0 ? labels : ['Belum ada data'],
            datasets: [{
                label: 'Total Kendaraan',
                data: data.length > 0 ? data : [0],
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

// ── CLASSIFICATION CHART (canvas: classificationChart) ──
function renderClassificationChart(realtimeData) {
    // Support both canvas IDs
    const ctx = document.getElementById('classificationChart') || document.getElementById('classChart');
    if (!ctx) return;

    // Hitung total per level density (karena realtime tidak punya breakdown per vehicle type)
    const levelCounts = { Low: 0, Medium: 0, High: 0 };
    realtimeData.forEach(d => {
        const lvl = d.density_level;
        if (lvl in levelCounts) levelCounts[lvl]++;
    });

    const labels = ['Low', 'Medium', 'High'];
    const data   = [levelCounts.Low, levelCounts.Medium, levelCounts.High];
    const colors = ['#1cc88a', '#f6c23e', '#e74a3b'];

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

// ── RENDER FEED PREVIEW ──
function renderFeedPreviews(densityData) {
    const grid = document.getElementById('dashboard-feed-grid');
    if (!grid) return;
    const token = localStorage.getItem('access_token');
    if (!token) return;

    grid.innerHTML = densityData.map(d => `
        <div class="feed-card" style="border: 1px solid #ddd; padding: 10px; border-radius: 8px;">
            <div class="feed-header" style="font-weight:bold;margin-bottom:6px;">${d.camera_id}</div>
            <img src="${API_BASE}/api/v1/stream/${d.camera_id}?token=${encodeURIComponent(token)}"
                 alt="Stream ${d.camera_id}"
                 style="width:100%; height:160px; object-fit:cover; border-radius:4px;"
                 onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';">
            <div style="display:none; width:100%; height:160px; background:#f5f5f5; border-radius:4px;
                        align-items:center; justify-content:center; color:#999; font-size:13px;">
                📷 Stream tidak tersedia
            </div>
            <div style="margin-top:8px; font-size:12px; color:#666;">
                Density: <b style="color:${d.density_level === 'High' ? '#e74a3b' : d.density_level === 'Medium' ? '#f6c23e' : '#1cc88a'}">
                    ${d.density_level || '-'}
                </b>
            </div>
        </div>
    `).join('');
}

// ── ALERT ACKNOWLEDGE ──
async function acknowledgeAlertItem(alertId) {
    const res = await apiFetch(`${API_BASE}/api/v1/alerts/${alertId}/acknowledge`, {
        method: 'POST'
    });
    if (res && res.ok) fetchDashboardData();
}

// Alias untuk dipanggil dari dashboard.html inline onclick
async function acknowledgeAlert(alertId) {
    return acknowledgeAlertItem(alertId);
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