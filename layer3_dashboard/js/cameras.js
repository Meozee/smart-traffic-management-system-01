async function initCamerasPage() {
    const container = document.getElementById('cameras-grid');
    if (!container) return;

    try {
        const response = await apiFetch(`${API_BASE}/api/v1/cameras`);
        if (!response || !response.ok) {
            container.innerHTML = '<div class="loading-state">⚠️ Gagal memuat feed kamera.</div>';
            return;
        }

        const cameras = await response.json();
        const activeCams = cameras.filter(c => c.status === 'active');

        if (activeCams.length === 0) {
            container.innerHTML = '<div class="loading-state">Tidak ada kamera aktif untuk ditampilkan.</div>';
            return;
        }

        container.innerHTML = activeCams.map(cam => `
            <div class="card live-feed">
                <div class="feed-header">
                    <h3>${cam.location_name} <span class="cam-id">(${cam.camera_id})</span></h3>
                    <span class="badge-active">LIVE</span>
                </div>
                
                <div class="stream-container">
                    <img src="${API_BASE}/api/v1/stream/${cam.camera_id}" 
                         alt="Stream ${cam.camera_id}"
                         onerror="this.parentElement.innerHTML='<div class=\'stream-error\'>⚠️ Koneksi Terputus</div>'">
                </div>

                <div class="cam-controls">
                    <label>Posisi Garis: <b id="val-${cam.camera_id}">${cam.virtual_line_y}</b>px</label>
                    <input type="range" 
                           min="50" max="600" 
                           value="${cam.virtual_line_y}" 
                           oninput="updateLineDisplay('${cam.camera_id}', this.value)"
                           onchange="saveLinePosition('${cam.camera_id}', this.value)">
                </div>
            </div>
        `).join('');

    } catch (error) {
        container.innerHTML = '<div class="loading-state">⚠️ Gagal memuat feed kamera.</div>';
    }
}

function updateLineDisplay(id, val) {
    const el = document.getElementById(`val-${id}`);
    if (el) el.textContent = val;
}

async function saveLinePosition(id, val) {
    try {
        const res = await apiFetch(`${API_BASE}/api/v1/cameras/${id}/line?y_position=${val}`, {
            method: 'PATCH'
        });
        if (res && res.ok) {
            console.log(`Garis ${id} disimpan di ${val}px`);
        }
    } catch (e) {
        console.error('Gagal simpan posisi garis', e);
    }
}

function initCamerasScript() {
    if (!getToken()) return;
    initCamerasPage();
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initCamerasScript);
} else {
    initCamerasScript();
}