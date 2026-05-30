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

function saveThresholds() {
    const low = parseInt(document.getElementById('threshold-low').value, 10);
    const high = parseInt(document.getElementById('threshold-high').value, 10);
    const msg = document.getElementById('threshold-message');

    if (isNaN(low) || isNaN(high) || low < 0 || high > 100 || low >= high) {
        alert('Nilai threshold tidak valid. Pastikan Low < High dan 0-100.');
        return;
    }

    localStorage.setItem('threshold_low', low.toString());
    localStorage.setItem('threshold_high', high.toString());
    msg.style.display = 'block';
    setTimeout(() => { msg.style.display = 'none'; }, 3000);
}

function loadThresholds() {
    const low = localStorage.getItem('threshold_low') || '40';
    const high = localStorage.getItem('threshold_high') || '70';
    document.getElementById('threshold-low').value = low;
    document.getElementById('threshold-high').value = high;
}

async function initSettingsPage() {
    if (!checkAdminAccess()) return;

    document.getElementById('camera-form').onsubmit = async (e) => {
        e.preventDefault();
        const payload = {
            camera_id: document.getElementById('set-cam-id').value,
            location_name: document.getElementById('set-cam-location').value,
            stream_url: document.getElementById('set-cam-url').value,
            road_capacity: parseInt(document.getElementById('set-cam-capacity').value, 10),
            status: 'active'
        };

        try {
            const res = await apiFetch(`${API_BASE}/api/v1/cameras/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (res && res.ok) {
                alert('✅ Kamera berhasil disimpan/diperbarui!');
                e.target.reset();
                loadCamerasTable();
            } else {
                alert('❌ Gagal menyimpan kamera. Cek kembali datanya.');
            }
        } catch (err) {
            console.error(err);
            alert('⚠️ Error koneksi ke server.');
        }
    };

    loadThresholds();
    loadCamerasTable();
}

async function loadCamerasTable() {
    const tbody = document.getElementById('settings-camera-table');
    if (!tbody) return;

    try {
        const res = await apiFetch(`${API_BASE}/api/v1/cameras`);
        if (!res || !res.ok) {
            tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;color:#f85149">⚠️ Gagal memuat data.</td></tr>';
            return;
        }

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
        console.error(err);
        tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;color:#f85149">⚠️ Gagal memuat data.</td></tr>';
    }
}

async function handleArchive(id) {
    try {
        const res = await apiFetch(`${API_BASE}/api/v1/cameras/${id}/archive`, {
            method: 'PATCH'
        });
        if (res && res.ok) {
            loadCamerasTable();
        } else {
            alert('Gagal mengubah status kamera.');
        }
    } catch (err) {
        console.error(err);
        alert('Gagal mengubah status kamera.');
    }
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initSettingsPage);
} else {
    initSettingsPage();
}
