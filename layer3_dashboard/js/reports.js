// Konfigurasi Pagination
let currentPage = 1;
const itemsPerPage = 50; 
let currentDataLength = 0;

async function loadReportsData() {
    const tbody = document.getElementById('reports-body');
    const btnPrev = document.getElementById('btn-prev');
    const btnNext = document.getElementById('btn-next');
    const indicator = document.getElementById('page-indicator');

    if (!tbody) return;
    
    tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:#8b949e">Loading data...</td></tr>';

    try {
        // Hitung nilai OFFSET (skip)
        const skipAmount = (currentPage - 1) * itemsPerPage;
        
        // Panggil endpoint GET ALL dengan Pagination
        const response = await fetch(`${API_BASE}/detections/?skip=${skipAmount}&limit=${itemsPerPage}`);
        const data = await response.json();
        
        currentDataLength = data.length;

        if (data.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:#8b949e">Tidak ada data di halaman ini.</td></tr>';
        } else {
            // Render data dari terbaru ke terlama (reverse)
            tbody.innerHTML = data.reverse().map(d => {
                // Format waktu lokal (WIB)
                const timeString = new Date(d.timestamp).toLocaleString('id-ID', { 
                    timeZone: 'Asia/Jakarta',
                    year: 'numeric', month: '2-digit', day: '2-digit',
                    hour: '2-digit', minute: '2-digit', second: '2-digit'
                });

                // Warna badge tipe kendaraan
                let badgeClass = 'badge-type';
                if (d.vehicle_type === 'motorcycle') badgeClass += ' type-moto';
                if (d.vehicle_type === 'truck' || d.vehicle_type === 'bus') badgeClass += ' type-heavy';

                return `
                    <tr>
                        <td>${timeString}</td>
                        <td>${d.camera_id}</td>
                        <td><span class="${badgeClass}">${d.vehicle_type.toUpperCase()}</span></td>
                        <td>${d.direction}</td>
                        <td>${(d.confidence * 100).toFixed(1)}%</td>
                    </tr>
                `;
            }).join('');
        }

        // Update Navigasi
        indicator.textContent = `Halaman ${currentPage}`;
        btnPrev.disabled = currentPage === 1;
        
        // Jika data yang didapat kurang dari limit, berarti ini halaman terakhir
        btnNext.disabled = currentDataLength < itemsPerPage;

    } catch (error) {
        console.error("Gagal load reports:", error);
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:#f85149">⚠️ Error mengambil data</td></tr>';
    }
}

// Fungsi tombol Next / Prev
function changePage(step) {
    if (step === -1 && currentPage === 1) return;
    currentPage += step;
    loadReportsData();
}

// ==========================================
// FITUR EXPORT CSV (Kebutuhan Instansi)
// ==========================================
async function exportTodayCSV() {
    try {
        const today = getTodayWIB(); // Panggil dari main.js
        
        // Gunakan endpoint /range agar tidak menarik semua data dari awal zaman
        const res = await fetch(`${API_BASE}/detections/range?start=${today}&end=${today}&limit=10000`);
        const data = await res.json();

        if (data.length === 0) {
            alert("Tidak ada data untuk diexport hari ini.");
            return;
        }

        const headers = ['Waktu (WIB)','Camera ID','Tipe Kendaraan','Arah','Confidence'];
        const rows = data.map(d => {
            const timeStr = new Date(d.timestamp).toLocaleString('id-ID', { timeZone: 'Asia/Jakarta' });
            return `"${timeStr}","${d.camera_id}","${d.vehicle_type}","${d.direction}","${d.confidence}"`;
        });

        const csv = [headers.join(','), ...rows].join('\n');
        const blob = new Blob([csv], { type: 'text/csv' });
        const url  = URL.createObjectURL(blob);

        const a = document.createElement('a');
        a.href = url;
        a.download = `STMS_Report_${today}.csv`;
        document.body.appendChild(a);
        a.click();
        
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    } catch (err) {
        console.error(err);
        alert('Gagal membuat file CSV.');
    }
}

// Inisialisasi saat file diload
loadReportsData();