// Pastikan variabel chart didefinisikan agar bisa di-reset (destroy)
if (typeof trendChartInstance !== 'undefined') trendChartInstance.destroy();
if (typeof classChartInstance !== 'undefined') classChartInstance.destroy();

var trendChartInstance = null;
var classChartInstance = null;

async function updateDashboardAnalytics() {
    try {
        const today = getTodayWIB(); // Fungsi dari main.js

        // 1. Ambil Data Trend & Total (Gunakan Endpoint Range)
        const resRange = await fetch(`${API_BASE}/detections/range?start=${today}&end=${today}&limit=5000`);
        const todayData = await resRange.json();

        // 2. Ambil Data Klasifikasi (Gunakan Endpoint Summary)
        const resSummary = await fetch(`${API_BASE}/detections/summary?date=${today}`);
        const summaryData = await resSummary.json();

        // Update Angka & Status
        document.getElementById('total-count').textContent = todayData.length.toLocaleString();
        updateDensityStatus(todayData.length);

        // Render Grafik
        renderTrendChart(todayData);
        renderClassificationChart(summaryData);

    } catch (error) {
        console.error("Dashboard Error:", error);
    }
}

function updateDensityStatus(count) {
    const el = document.getElementById('density-status');
    if (!el) return;
    
    // Logika sederhana: Misal kapasitas total 1000 kendaraan/hari
    if (count > 500) {
        el.textContent = "PADAT";
        el.style.color = "#f85149";
    } else if (count > 200) {
        el.textContent = "RAMAI";
        el.style.color = "#fbbf24";
    } else {
        el.textContent = "LANCAR";
        el.style.color = "#3fb950";
    }
}

function renderTrendChart(data) {
    const ctx = document.getElementById('trafficTrendChart').getContext('2d');
    const hourlyData = new Array(24).fill(0);

    data.forEach(item => {
        const hour = new Date(item.timestamp).getHours();
        hourlyData[hour]++;
    });

    if (trendChartInstance) trendChartInstance.destroy();
    trendChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: Array.from({length: 24}, (_, i) => `${i}:00`),
            datasets: [{
                label: 'Jumlah Kendaraan',
                data: hourlyData,
                borderColor: '#58a6ff',
                backgroundColor: 'rgba(88, 166, 255, 0.1)',
                fill: true,
                tension: 0.3
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                y: { beginAtZero: true, grid: { color: '#30363d' } },
                x: { grid: { display: false } }
            }
        }
    });
}

function renderClassificationChart(summary) {
    const ctx = document.getElementById('classificationChart').getContext('2d');
    const labels = Object.keys(summary).map(l => l.toUpperCase());
    const values = Object.values(summary);

    if (classChartInstance) classChartInstance.destroy();
    classChartInstance = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: values,
                backgroundColor: ['#58a6ff', '#3fb950', '#fbbf24', '#f85149'],
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

// Jalankan update pertama kali
updateDashboardAnalytics();

// Refresh data setiap 10 detik agar tetap real-time
const dashboardInterval = setInterval(updateDashboardAnalytics, 10000);

// Bersihkan interval jika pindah halaman (PENTING!)
window.addEventListener('hashchange', () => clearInterval(dashboardInterval), { once: true });