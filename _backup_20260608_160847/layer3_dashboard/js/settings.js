// ─────────────────────────────────────────────
// settings.js — STMS Dashboard (REVISI FINAL)
// ─────────────────────────────────────────────

function checkAdminAccess() {
    const role = getUserRole();
    if (!role) {
        window.location.href = '/login.html';
        return false;
    }

    if (role !== 'admin') {
        document.getElementById('access-denied-msg').style.display = 'block';
        document.getElementById('settings-content').style.display = 'none';
        return false;
    }
    return true;
}

async function initSettingsPage() {
    if (!checkAdminAccess()) return;

    // EVENT LISTENER FORM TAMBAH/UPDATE KAMERA
    document.getElementById('camera-form').onsubmit = async (e) => {
        e.preventDefault();

        // 1. Ambil nilai dari input form
        const lowThr = parseFloat(document.getElementById('set-cam-low').value);
        const highThr = parseFloat(document.getElementById('set-cam-high').value);

        // 2. Validasi Logika Threshold
        if (lowThr >= highThr) {
            alert('❌ Gagal: Nilai Low Threshold harus LEBIH KECIL dari High Threshold!');
            return;
        }

        // 3. Susun Payload (Harus 100% sama dengan schemas.py -> CameraCreate)
        const payload = {
            camera_id: document.getElementById('set-cam-id').value,
            location_name: document.getElementById('set-cam-location').value,
            road_capacity: parseInt(document.getElementById('set-cam-capacity').value, 10),
            direction: "Bidirectional", // Default
            status: "active",
            stream_url: document.getElementById('set-cam-url').value,
            
            // Pengaturan Baru per Kamera
            low_density_threshold: lowThr,
            high_density_threshold: highThr,
            confidence_tolerance: parseFloat(document.getElementById('set-cam-conf').value)
        };

        try {
            const res = await apiFetch(`${API_BASE}/api/v1/cameras/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            
            if (res && res.ok) {
                alert('✅ Konfigurasi Kamera dan AI berhasil disimpan ke Database!');
                e.target.reset(); // Kosongkan form
                loadCamerasTable(); // Refresh tabel bawah
            } else {
                alert('❌ Gagal menyimpan kamera. Pastikan data tidak ada yang kosong.');
            }
        } catch (err) {
            console.error(err);
            alert('⚠️ Error koneksi ke server Backend.');
        }
    };

    // Pemuatan awal saat masuk halaman
    loadCamerasTable();
}

async function loadCamerasTable() {
    const tbody = document.getElementById('settings-camera-table');
    if (!tbody) return;

    try {
        const res = await apiFetch(`${API_BASE}/api/v1/cameras`);
        if (!res || !res.ok) {
            tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:#f85149">⚠️ Gagal memuat data dari Database.</td></tr>';
            return;
        }

        const cameras = await res.json();
        if (cameras.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:#8b949e">Belum ada kamera yang didaftarkan.</td></tr>';
            return;
        }

        // Tampilkan data kamera yang diambil dari PostgreSQL
        tbody.innerHTML = cameras.map(cam => `
            <tr style="border-bottom: 1px solid #eee;">
                <td style="padding: 10px;"><b>${cam.camera_id}</b></td>
                <td style="padding: 10px;">${cam.location_name}</td>
                <td style="padding: 10px; font-family: monospace;">${cam.road_capacity ?? '—'}</td>
                <td style="padding: 10px; font-family: monospace;">${cam.low_density_threshold} / ${cam.high_density_threshold}</td>
                <td style="padding: 10px; font-family: monospace;">${cam.confidence_tolerance}</td>
                <td style="padding: 10px;">
                    <span style="background: ${cam.status === 'active' ? '#d1fae5' : '#fee2e2'}; color: ${cam.status === 'active' ? '#065f46' : '#991b1b'}; padding: 4px 8px; border-radius: 4px; font-size: 11px; font-weight: bold;">
                        ${cam.status.toUpperCase()}
                    </span>
                </td>
                <td style="padding: 10px;">
                    <button onclick="handleArchive('${cam.camera_id}')" style="background: transparent; border: 1px solid #ccc; border-radius: 4px; cursor: pointer; padding: 4px 8px;">
                        ${cam.status === 'active' ? '📦 Arsip' : '♻️ Aktifkan'}
                    </button>
                </td>
            </tr>
        `).join('');
    } catch (err) {
        console.error(err);
        tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:#f85149">⚠️ Gagal memuat data kamera.</td></tr>';
    }
}

async function handleArchive(id) {
    try {
        const res = await apiFetch(`${API_BASE}/api/v1/cameras/${id}/archive`, {
            method: 'PATCH'
        });
        if (res && res.ok) {
            loadCamerasTable(); // Refresh tabel setelah status diubah
        } else {
            alert('Gagal mengubah status kamera.');
        }
    } catch (err) {
        console.error(err);
        alert('Gagal mengubah status kamera.');
    }
}

// Bootstrapping
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initSettingsPage);
} else {
    initSettingsPage();
}