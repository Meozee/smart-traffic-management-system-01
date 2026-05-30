let reportParams = null;

async function initReportsPage() {
    if (!getToken()) return;
    await populateCameraDropdown();
    setupDefaultDateRange();
}

async function populateCameraDropdown() {
    const select = document.getElementById('filter-camera');
    if (!select) return;

    const camerasRes = await apiFetch(`${API_BASE}/api/v1/cameras`);
    if (!camerasRes || !camerasRes.ok) return;

    const cameras = await camerasRes.json();
    cameras.forEach(cam => {
        const opt = document.createElement('option');
        opt.value = cam.camera_id;
        opt.textContent = `${cam.camera_id} — ${cam.location_name}`;
        select.appendChild(opt);
    });
}

function setupDefaultDateRange() {
    const today = new Date();
    const thirtyDaysAgo = new Date(today.getTime() - 30 * 24 * 60 * 60 * 1000);
    document.getElementById('filter-end-date').value = today.toISOString().split('T')[0];
    document.getElementById('filter-start-date').value = thirtyDaysAgo.toISOString().split('T')[0];
}

async function generateReport() {
    const startDate = document.getElementById('filter-start-date').value;
    const endDate = document.getElementById('filter-end-date').value;
    const cameraId = document.getElementById('filter-camera').value;

    if (!startDate || !endDate) {
        alert('Pilih tanggal mulai dan tanggal akhir.');
        return;
    }

    let url = `${API_BASE}/api/v1/density/history?start_date=${startDate}T00:00:00&end_date=${endDate}T23:59:59`;
    if (cameraId) url += `&camera_id=${cameraId}`;

    const res = await apiFetch(url);
    if (!res || !res.ok) {
        alert('Gagal mengambil data laporan.');
        return;
    }

    const result = await res.json();
    updateReportSummary(result.summary);
    renderReportTable(result.data || []);
    document.getElementById('export-buttons').style.display = 'flex';
    reportParams = { startDate, endDate, cameraId };
}

function updateReportSummary(summary) {
    const summaryEl = document.getElementById('report-summary');
    if (!summary || !summaryEl) return;

    document.getElementById('sum-total-vehicles').textContent = summary.total_vehicles || 0;
    document.getElementById('sum-avg-density').textContent = summary.average_density_ratio !== null
        ? `${(summary.average_density_ratio * 100).toFixed(1)}%`
        : '-';
    document.getElementById('sum-peak-hour').textContent = summary.peak_hour || '-';
    document.getElementById('sum-peak-day').textContent = summary.peak_day || '-';
    summaryEl.style.display = 'grid';
}

function renderReportTable(data) {
    const container = document.getElementById('report-table-container');
    if (!container) return;

    if (!data || data.length === 0) {
        container.innerHTML = '<div class="loading-state">Tidak ada data untuk rentang waktu ini.</div>';
        return;
    }

    const rows = data.map(d => {
        return `
            <tr>
                <td>${new Date(d.interval_start).toLocaleDateString('id-ID')}</td>
                <td>${new Date(d.interval_start).toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' })}</td>
                <td>${d.camera_id}</td>
                <td>${d.total_vehicles ?? 0}</td>
                <td>${d.inflow_count ?? 0}</td>
                <td>${d.outflow_count ?? 0}</td>
                <td>${d.density_ratio !== null ? `${(d.density_ratio * 100).toFixed(1)}%` : '-'}</td>
                <td>${d.density_level || '-'}</td>
            </tr>
        `;
    }).join('');

    container.innerHTML = `
        <table class="data-table">
            <thead>
                <tr>
                    <th>Tanggal</th>
                    <th>Waktu</th>
                    <th>Kamera</th>
                    <th>Total</th>
                    <th>Inflow</th>
                    <th>Outflow</th>
                    <th>Density</th>
                    <th>Level</th>
                </tr>
            </thead>
            <tbody>
                ${rows}
            </tbody>
        </table>
        <p style="margin-top:12px;color:#8b949e;">Menampilkan ${data.length} record.</p>
    `;
}

async function exportReport(format) {
    if (!reportParams) {
        alert('Generate report dulu sebelum export.');
        return;
    }

    const { startDate, endDate, cameraId } = reportParams;
    let url = `${API_BASE}/api/v1/reports/export?format=${format}&start_date=${startDate}T00:00:00&end_date=${endDate}T23:59:59`;
    if (cameraId) url += `&camera_id=${cameraId}`;

    try {
        const token = localStorage.getItem('access_token');
        const res = await fetch(url, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (!res.ok) {
            alert('Export gagal.');
            return;
        }

        const blob = await res.blob();
        const downloadUrl = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = downloadUrl;
        a.download = `stms_report_${startDate}_${endDate}.${format}`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(downloadUrl);
    } catch (err) {
        alert('Export gagal: ' + err.message);
    }
}

function initReportsScript() {
    initReportsPage();
    document.getElementById('filter-camera')?.addEventListener('change', () => { });
    window.generateReport = generateReport;
    window.exportReport = exportReport;
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initReportsScript);
} else {
    initReportsScript();
}
