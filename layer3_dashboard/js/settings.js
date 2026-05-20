async function initSettingsPage() {
    const form = document.getElementById('camera-form');
    
    // 1. Handle Submit Form
    form.onsubmit = async (e) => {
        e.preventDefault();
        
        const payload = {
            camera_id: document.getElementById('set-cam-id').value,
            location_name: document.getElementById('set-cam-location').value,
            stream_url: document.getElementById('set-cam-url').value,
            road_capacity: parseInt(document.getElementById('set-cam-capacity').value),
            status: "active" // Default saat baru dibuat
        };

        try {
            const res = await fetch(`${API_BASE}/cameras/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (res.ok) {
                alert("✅ Kamera berhasil disimpan/diperbarui!");
                form.reset();
                loadCamerasTable(); // Refresh tabel di bawahnya
            } else {
                alert("❌ Gagal menyimpan kamera. Cek kembali datanya.");
            }
        } catch (err) {
            console.error(err);
            alert("⚠️ Error koneksi ke server.");
        }
    };

    // 2. Load Tabel Pertama Kali
    loadCamerasTable();
}

async function loadCamerasTable() {
    const tbody = document.getElementById('settings-camera-table');
    if (!tbody) return;

    try {
        const res = await fetch(`${API_BASE}/cameras/`);
        const cameras = await res.json();

        if (cameras.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;color:#8b949e">Belum ada kamera terdaftar.</td></tr>';
            return;
        }

        tbody.innerHTML = cameras.map(cam => `
            <tr>
                <td><b>${cam.camera_id}</b></td>
                <td>${cam.location_name}</td>
                <td>
                    <span class="badge ${cam.status === 'active' ? 'badge-active' : 'badge-archived'}">
                        ${cam.status.toUpperCase()}
                    </span>
                </td>
                <td>
                    <button class="btn-archive" onclick="handleArchive('${cam.camera_id}')">
                        ${cam.status === 'active' ? '📦 Arsip' : '♻️ Aktifkan'}
                    </button>
                </td>
            </tr>
        `).join('');

    } catch (err) {
        tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;color:#f85149">⚠️ Gagal memuat data.</td></tr>';
    }
}

async function handleArchive(id) {
    try {
        const res = await fetch(`${API_BASE}/cameras/${id}/archive`, {
            method: 'PATCH'
        });
        
        if (res.ok) {
            const data = await res.json();
            console.log(data.message);
            loadCamerasTable(); // Refresh tabel
        }
    } catch (err) {
        alert("Gagal mengubah status kamera.");
    }
}

// Inisialisasi
initSettingsPage();