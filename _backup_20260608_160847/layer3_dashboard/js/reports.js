// ─────────────────────────────────────────────
// report.js — STMS Dashboard (REVISI FINAL)
// ─────────────────────────────────────────────

let reportParams = null;
let reportChartInstance = null;

async function initReportsPage() {
    if (!getToken()) return;
    await populateCameraDropdown();
    setupDefaultDateRange();
    initReportChart();
}

async function populateCameraDropdown() {
    const select = document.getElementById('filter-camera');
    if (!select) return;

    try {
        const camerasRes = await apiFetch(`${API_BASE}/api/v1/cameras`);
        if (!camerasRes || !camerasRes.ok) return;

        const cameras = await camerasRes.json();
        cameras.forEach(cam => {
            const opt = document.createElement('option');
            opt.value = cam.camera_id;
            opt.textContent = `${cam.camera_id} — ${cam.location_name}`;
            select.appendChild(opt);
        });
    } catch (e) {
        console.error("Gagal memuat kamera untuk dropdown", e);
    }
}

function setupDefaultDateRange() {
    const today = new Date();
    // Default: 7 hari terakhir agar chart tidak terlalu padat
    const sevenDaysAgo = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000);
    document.getElementById('filter-end-date').value = today.toISOString().split('T')[0];
    document.getElementById('filter-start-date').value = sevenDaysAgo.toISOString().split('T')[0];
}

async function generateReport() {
    const startDate = document.getElementById('filter-start-date').value;
    const endDate = document.getElementById('filter-end-date').value;
    const cameraId = document.getElementById('filter-camera').value;

    if (!startDate || !endDate) {
        alert('Pilih tanggal mulai dan tanggal akhir.');
        return;
    }

    // Tampilkan loading state
    const container = document.getElementById('report-table-container');
    container.innerHTML = '<div class="loading-state" style="text-align: center; padding: 30px; color: #888;">Memproses Data...</div>';

    let url = `${API_BASE}/api/v1/density/history?start_date=${startDate}T00:00:00Z&end_date=${endDate}T23:59:59Z`;
    if (cameraId) url += `&camera_id=${cameraId}`;

    try {
        const res = await apiFetch(url);
        if (!res || !res.ok) {
            alert('Gagal mengambil data laporan dari server.');
            container.innerHTML = '<div class="loading-state" style="text-align: center; padding: 30px; color: red;">Gagal memuat data.</div>';
            return;
        }

        const result = await res.json();
        
        // Perbarui semua komponen UI
        updateReportSummary(result.summary);
        renderReportTable(result.data || []);
        updateReportChart(result.data || []);
        
        // Tampilkan tombol export
        document.getElementById('export-buttons').style.display = 'flex';
        reportParams = { startDate, endDate, cameraId };

    } catch (e) {
        console.error("Error generating report:", e);
        container.innerHTML = '<div class="loading-state" style="text-align: center; padding: 30px; color: red;">Terjadi kesalahan jaringan.</div>';
    }
}

function updateReportSummary(summary) {
    const summaryEl = document.getElementById('report-summary');
    if (!summary || !summaryEl) return;

    document.getElementById('sum-total-vehicles').textContent = (summary.total_vehicles || 0).toLocaleString('id-ID');
    document.getElementById('sum-avg-density').textContent = summary.average_density_ratio !== null
        ? `${(summary.average_density_ratio * 100).toFixed(1)}%`
        : '-';
    document.getElementById('sum-peak-hour').textContent = summary.peak_hour || '-';
    
    summaryEl.style.display = 'grid';
}

function renderReportTable(data) {
    const container = document.getElementById('report-table-container');
    if (!container) return;

    if (!data || data.length === 0) {
        container.innerHTML = '<div class="loading-state" style="text-align: center; padding: 30px; color: #888;">Tidak ada data untuk rentang waktu ini.</div>';
        return;
    }

    const rows = data.map(d => {
        const dateObj = new Date(d.interval_start);
        return `
            <tr style="border-bottom: 1px solid #eee;">
                <td style="padding: 10px;">${dateObj.toLocaleDateString('id-ID')}</td>
                <td style="padding: 10px;">${dateObj.toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' })}</td>
                <td style="padding: 10px;"><b>${d.camera_id}</b></td>
                <td style="padding: 10px; font-family: monospace;">${d.total_vehicles ?? 0}</td>
                <td style="padding: 10px; font-family: monospace; color: #1cc88a;">${d.inflow_count ?? 0}</td>
                <td style="padding: 10px; font-family: monospace; color: #e74a3b;">${d.outflow_count ?? 0}</td>
                <td style="padding: 10px;">${d.density_ratio !== null ? `${(d.density_ratio * 100).toFixed(1)}%` : '-'}</td>
                <td style="padding: 10px;">
                    <span style="padding: 3px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; background: ${d.density_level === 'High' ? '#fee2e2' : d.density_level === 'Medium' ? '#fef3c7' : '#d1fae5'}; color: ${d.density_level === 'High' ? '#991b1b' : d.density_level === 'Medium' ? '#b45309' : '#065f46'};">
                        ${d.density_level || '-'}
                    </span>
                </td>
            </tr>
        `;
    }).join('');

    container.innerHTML = `
        <table class="data-table" style="width: 100%; border-collapse: collapse; text-align: left; font-size: 13px;">
            <thead>
                <tr style="background: #f8f9fa; border-bottom: 2px solid #ddd;">
                    <th style="padding: 10px;">Tanggal</th>
                    <th style="padding: 10px;">Waktu</th>
                    <th style="padding: 10px;">Kamera</th>
                    <th style="padding: 10px;">Total</th>
                    <th style="padding: 10px;">Inflow (Masuk)</th>
                    <th style="padding: 10px;">Outflow (Keluar)</th>
                    <th style="padding: 10px;">Ratio Density</th>
                    <th style="padding: 10px;">Level</th>
                </tr>
            </thead>
            <tbody>
                ${rows}
            </tbody>
        </table>
        <p style="margin-top:12px; color:#888; font-size: 12px; text-align: right;">Menampilkan ${data.length} baris data.</p>
    `;
}

// ── FUNGSI CHART BARU ──
function initReportChart() {
    const ctx = document.getElementById('reportBarChart');
    if (!ctx) return;
    
    reportChartInstance = new Chart(ctx.getContext('2d'), {
        type: 'bar',
        data: {
            labels: [],
            datasets: [{
                label: 'Total Kendaraan Per Hari',
                data: [],
                backgroundColor: '#4e73df',
                borderRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: { y: { beginAtZero: true } }
        }
    });
}

function updateReportChart(data) {
    if (!reportChartInstance || data.length === 0) return;

    // Kelompokkan total kendaraan berdasarkan Tanggal (Hari)
    const dailyTotals = {};
    data.forEach(d => {
        const dateStr = new Date(d.interval_start).toLocaleDateString('id-ID');
        if (!dailyTotals[dateStr]) dailyTotals[dateStr] = 0;
        dailyTotals[dateStr] += (d.total_vehicles || 0);
    });

    const labels = Object.keys(dailyTotals);
    const values = Object.values(dailyTotals);

    // Update data Chart
    reportChartInstance.data.labels = labels;
    reportChartInstance.data.datasets[0].data = values;
    reportChartInstance.update();
}

async function exportReport(format) {
    if (!reportParams) {
        alert('Generate report dulu sebelum export.');
        return;
    }

    const { startDate, endDate, cameraId } = reportParams;
    let url = `${API_BASE}/api/v1/reports/export?format=${format}&start_date=${startDate}T00:00:00Z&end_date=${endDate}T23:59:59Z`;
    if (cameraId) url += `&camera_id=${cameraId}`;

    try {
        const token = localStorage.getItem('access_token');
        
        // Visual feedback saat loading export
        const btn = event.target;
        const originalText = btn.innerHTML;
        btn.innerHTML = "Mengekspor...";
        btn.disabled = true;

        const res = await fetch(url, {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (!res.ok) {
            alert('Export gagal. Endpoint backend mungkin belum diimplementasikan.');
            btn.innerHTML = originalText;
            btn.disabled = false;
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
        
        btn.innerHTML = originalText;
        btn.disabled = false;
    } catch (err) {
        alert('Export gagal: ' + err.message);
    }
}

// Bootstrapping
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initReportsPage);
} else {
    initReportsPage();
}