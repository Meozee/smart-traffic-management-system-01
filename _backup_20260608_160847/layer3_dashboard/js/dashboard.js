// ─────────────────────────────────────────────
// dashboard.js — STMS Dashboard (REVISI FINAL)
// ─────────────────────────────────────────────

let currentAlertId = null;
let trendChartInstance = null;
let classChartInstance = null;
const startTime = Date.now();

// Konfigurasi Warna untuk tiap kamera (Bisa ditambah jika kamera lebih dari 3)
const CAMERA_COLORS = ['#4e73df', '#1cc88a', '#e74a3b', '#f6c23e'];

async function fetchDashboardData() {
    try {
        // 1. Data History untuk Line Chart (Wajib dari /history)
        const today = new Date().toISOString().split('T')[0];
        const historyRes = await apiFetch(`${API_BASE}/api/v1/density/history?start_date=${today}T00:00:00Z&end_date=${today}T12:00:00Z`);
        
        // 2. Data Realtime untuk Stat Widgets & Tabel
        const realtimeRes = await apiFetch(`${API_BASE}/api/v1/density/realtime`);
        
        // 3. Active alerts
        const alertsRes = await apiFetch(`${API_BASE}/api/v1/alerts?status=active`);

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

        // 4. Cameras (active count)
        const camerasRes = await apiFetch(`${API_BASE}/api/v1/cameras`);
        if (camerasRes && camerasRes.ok) {
            const camerasData = await camerasRes.json();
            updateActiveCamerasWidget(camerasData);
        }

    } catch (error) {
        console.error('Dashboard Error:', error);
    }
}

// ── STAT WIDGETS (Sama seperti sebelumnya) ──
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

function updateUptimeWidget() {
    const elapsed = Math.floor((Date.now() - startTime) / 1000);
    const hours = Math.floor(elapsed / 3600);
    const minutes = Math.floor((elapsed % 3600) / 60);
    const el = document.getElementById('val-uptime');
    if (el) el.textContent = `${hours > 0 ? hours + 'j ' : ''}${minutes}m`;
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

// ── CHARTS: MULTI-SERIES LINE CHART ───────────────────
function renderTrendChart(historyData) {
    const canvas = document.getElementById('trafficTrendChart');
    if (!canvas || historyData.length === 0) return;
    const ctx = canvas.getContext('2d');

    // 1. Ekstrak label waktu unik (Sumbu X)
    const timeLabels = [...new Set(historyData.map(d => {
        const date = new Date(d.interval_start);
        return date.toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' });
    }))].sort();

    // 2. Ekstrak list kamera unik
    const cameras = [...new Set(historyData.map(d => d.camera_id))];

    // 3. Buat dataset terpisah (Garis) untuk setiap kamera
    const datasets = cameras.map((camId, index) => {
        const camData = historyData.filter(d => d.camera_id === camId);
        
        // Map data sesuai dengan urutan waktu di Sumbu X
        const dataPoints = timeLabels.map(timeLabel => {
            const record = camData.find(d => {
                const dTime = new Date(d.interval_start).toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' });
                return dTime === timeLabel;
            });
            return record ? record.total_vehicles : 0;
        });

        const color = CAMERA_COLORS[index % CAMERA_COLORS.length];
        return {
            label: camId,
            data: dataPoints,
            borderColor: color,
            backgroundColor: 'transparent',
            borderWidth: 2,
            tension: 0.4
        };
    });

    if (trendChartInstance) trendChartInstance.destroy();
    trendChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: timeLabels,
            datasets: datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: true, position: 'top' } },
            scales: { y: { beginAtZero: true } }
        }
    });
}

function renderClassificationChart(densityData) {
    const canvas = document.getElementById('classificationChart');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const counts = { Low: 0, Medium: 0, High: 0 };
    densityData.forEach(d => {
        const level = d.density_level || 'Low';
        if (counts[level] !== undefined) counts[level] += 1;
    });

    if (classChartInstance) classChartInstance.destroy();
    classChartInstance = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: Object.keys(counts),
            datasets: [{
                data: Object.values(counts),
                backgroundColor: ['#1cc88a', '#f6c23e', '#e74a3b'],
                borderWidth: 1.5
            }]
        },
        options: { responsive: true, maintainAspectRatio: false, cutout: '65%' }
    });
}

// ── DOM RENDERERS (Sama seperti sebelumnya) ──
function renderDensityTable(densityData) {
    const tbody = document.getElementById('density-status-tbody');
    if (!tbody) return;

    if (!densityData || densityData.length === 0) {
        tbody.innerHTML = '<tr><td colspan="3" style="text-align:center;">Tidak ada data.</td></tr>';
        return;
    }

    const dotColor = lvl => lvl === 'High' ? 'var(--red)' : lvl === 'Medium' ? 'var(--yellow)' : 'var(--green)';

    tbody.innerHTML = densityData.map(d => {
        const lvl = d.density_level || 'Low';
        return `
        <tr>
            <td class="cam-id">${d.camera_id}</td>
            <td><span class="badge"><span class="badge-dot" style="background:${dotColor(lvl)}"></span>${lvl}</span></td>
            <td>${d.total_vehicles}</td>
        </tr>`;
    }).join('');
}

function renderFeedPreviews(densityData) {
    const grid = document.getElementById('dashboard-feed-grid');
    if (!grid) return;

    grid.innerHTML = densityData.map(d => `
        <div class="feed-card" style="border: 1px solid #ddd; padding: 10px; border-radius: 8px;">
            <div class="feed-header"><b>${d.camera_id}</b></div>
            <img src="${API_BASE}/api/v1/stream/${d.camera_id}" alt="Stream" style="width:100%; height:200px; object-fit:cover; border-radius:4px; margin-top:10px;">
            <div class="feed-footer" style="margin-top:10px; font-size:12px;">Density: ${d.density_level}</div>
        </div>
    `).join('');
}

function renderAlertList(alertsData) {
    const container = document.getElementById('alert-list-container');
    if (!container) return;

    if (!alertsData || alertsData.length === 0) {
        container.innerHTML = '<div style="padding:20px;text-align:center;">Tidak ada alert aktif</div>';
        return;
    }

    container.innerHTML = alertsData.map(alert => `
        <div style="border-left: 4px solid red; padding: 10px; margin-bottom: 10px; background: #fff;">
            <b>${alert.camera_id}</b>: ${alert.message}
            <button onclick="acknowledgeAlertItem(${alert.alert_id})" style="float:right;">✓ Ack</button>
        </div>
    `).join('');
}

// ── ACKNOWLEDGE & INIT ──
async function acknowledgeAlertItem(alertId) {
    const res = await apiFetch(`${API_BASE}/api/v1/alerts/${alertId}/read`, { method: 'PATCH' });
    if (res && res.ok) fetchDashboardData();
}

async function acknowledgeAlert(alertId) {
    const res = await apiFetch(`${API_BASE}/api/v1/alerts/${alertId}/read`, { method: 'PATCH' });
    if (res && res.ok) fetchDashboardData();
}

function initDashboardPage() {
    if (!getToken()) return;
    fetchDashboardData();
    window.pageIntervalId = setInterval(fetchDashboardData, POLL_INTERVAL);
    updateUptimeWidget();
    setInterval(updateUptimeWidget, 60000);
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initDashboardPage);
} else {
    initDashboardPage();
}