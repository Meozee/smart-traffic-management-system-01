async function initCamerasPage() {
    const container = document.getElementById('cameras-grid');
    
    try {
        const response = await fetch(`${API_BASE}/cameras/`);
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
                    <video src="http://localhost:3000/output_result.mp4" 
				autoplay loop muted style="width:100%">
		    </video>
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

// Update angka di layar saja (cepat)
function updateLineDisplay(id, val) {
    document.getElementById(`val-${id}`).textContent = val;
}

// Simpan ke database (ketika user lepas klik slider)
async function saveLinePosition(id, val) {
    try {
        const res = await fetch(`${API_BASE}/cameras/${id}/line?y_position=${val}`, {
            method: 'PATCH'
        });
        if (res.ok) {
            console.log(`Garis ${id} disimpan di ${val}px`);
        }
    } catch (e) {
        console.error("Gagal simpan posisi garis");
    }
}

initCamerasPage();