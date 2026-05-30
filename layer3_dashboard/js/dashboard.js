let currentAlertId = null;
let trendChartInstance = null;
let classChartInstance = null;
const startTime = Date.now();

async function fetchDashboardData() {
    try {
        const densityRes = await apiFetch(`${API_BASE}/api/v1/density/realtime`);
        if (densityRes && densityRes.ok) {
            const densityData = await densityRes.json();
            updateDensityWidgets(densityData);
            renderTrendChart(densityData);
            renderClassificationChart(densityData);
        }

        const alertsRes = await apiFetch(`${API_BASE}/api/v1/alerts?status=active`);
        if (alertsRes && alertsRes.ok) {
            const alertsData = await alertsRes.json();
            updateAlertWidget(alertsData);
            showAlertNotification(alertsData);
        }

        const camerasRes = await apiFetch(`${API_BASE}/api/v1/cameras`);
        if (camerasRes && camerasRes.ok) {
            const camerasData = await camerasRes.json();
            updateActiveCamerasWidget(camerasData);
        }
    } catch (error) {
        console.error('Dashboard Error:', error);
    }
}

function updateDensityWidgets(densityData) {
    const totalVehicles = densityData.reduce((sum, d) => sum + (d.total_vehicles || 0), 0);
    document.getElementById('val-vehicles').textContent = totalVehicles.toLocaleString();
}

function updateActiveCamerasWidget(camerasData) {
    const activeCount = camerasData.filter(c => c.status === 'active').length;
    document.getElementById('val-active-cameras').textContent = activeCount;
}

function updateAlertWidget(alertsData) {
    document.getElementById('val-alerts').textContent = alertsData.length;
}

function showAlertNotification(alertsData) {
    const bar = document.getElementById('alert-notification-bar');
    const text = document.getElementById('alert-notification-text');
    if (!bar || !text) return;

    if (alertsData.length > 0) {
        const latest = alertsData[0];
        currentAlertId = latest.alert_id;
        text.textContent = `⚠️ Alert: ${latest.message}`;
        bar.style.display = 'flex';
    } else {
        bar.style.display = 'none';
        currentAlertId = null;
    }
}

function updateUptimeWidget() {
    const elapsed = Math.floor((Date.now() - startTime) / 1000);
    const hours = Math.floor(elapsed / 3600);
    const minutes = Math.floor((elapsed % 3600) / 60);
    const uptimeEl = document.getElementById('val-uptime');
    if (!uptimeEl) return;
    uptimeEl.textContent = `${hours > 0 ? hours + 'j ' : ''}${minutes}m`;
}

function renderTrendChart(densityData) {
    const ctx = document.getElementById('trafficTrendChart').getContext('2d');
    const labels = densityData.map(d => d.camera_id || 'Unknown');
    const values = densityData.map(d => d.total_vehicles || 0);

    if (trendChartInstance) trendChartInstance.destroy();
    trendChartInstance = new Chart(ctx, {
        type: 'bar',
        data: {
            labels,
            datasets: [{
                label: 'Total Kendaraan',
                data: values,
                backgroundColor: 'rgba(88, 166, 255, 0.7)',
                borderColor: '#58a6ff',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                y: { beginAtZero: true, grid: { color: '#30363d' } },
                x: { ticks: { color: '#c9d1d9' }, grid: { display: false } }
            }
        }
    });
}

function renderClassificationChart(densityData) {
    const ctx = document.getElementById('classificationChart').getContext('2d');
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
                backgroundColor: ['#3fb950', '#fbbf24', '#f85149'],
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'bottom', labels: { color: '#8b949e' } }
            }
        }
    });
}

async function acknowledgeAlert(alertId) {
    if (!alertId) return;
    const res = await apiFetch(`${API_BASE}/api/v1/alerts/${alertId}/acknowledge`, { method: 'POST' });
    if (res && res.ok) {
        document.getElementById('alert-notification-bar').style.display = 'none';
        currentAlertId = null;
        fetchDashboardData();
    } else {
        alert('Gagal melakukan acknowledge alert.');
    }
}

function initDashboardPage() {
    if (!getToken()) return;
    fetchDashboardData();
    setInterval(fetchDashboardData, POLL_INTERVAL);
    updateUptimeWidget();
    setInterval(updateUptimeWidget, 60000);
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initDashboardPage);
} else {
    initDashboardPage();
}