// ─────────────────────────────────────────────
// cameras.js — STMS Dashboard (VIRTUAL LINE INTERAKTIF)
// Perbaikan: Menyelipkan Token JWT ke URL gambar agar lolos dari Satpam Backend.
// ─────────────────────────────────────────────

let _allCameras = [];
let currentCameraId = null;

// ── VARIABEL KANVAS & KOORDINAT ──
let canvas, ctx;
let point1 = { x: 150, y: 250, radius: 15, isDragging: false };
let point2 = { x: 450, y: 250, radius: 15, isDragging: false };

// ── INISIALISASI HALAMAN ──
async function initCamerasPage() {
    try {
        const response = await apiFetch(`${API_BASE}/api/v1/cameras/`);
        if (!response || !response.ok) {
            showCameraError('⚠️ Gagal memuat data kamera.');
            return;
        }

        const cameras = await response.json();
        _allCameras = cameras.filter(c => c.status === 'active');

        if (_allCameras.length === 0) {
            showCameraError('Tidak ada kamera aktif untuk ditampilkan.');
            return;
        }

        // Siapkan Dropdown dan Kanvas
        populateSelector(_allCameras);
        initCanvasLogic();

        // Auto-pilih kamera pertama saat halaman dimuat
        const selector = document.getElementById('camera-selector');
        if (selector && _allCameras.length > 0) {
            selector.value = _allCameras[0].camera_id;
            updateDetailView(_allCameras[0]);
        }
    } catch (error) {
        showCameraError('⚠️ Terjadi kesalahan jaringan saat memuat kamera.');
        console.error(error);
    }
}

// ── POPULATE DROPDOWN KAMERA ──
function populateSelector(cameras) {
    const selector = document.getElementById('camera-selector');
    if (!selector) return;

    selector.innerHTML = cameras.map(cam =>
        `<option value="${cam.camera_id}">${cam.camera_id} · ${cam.location_name}</option>`
    ).join('');

    selector.addEventListener('change', function () {
        const cam = _allCameras.find(c => c.camera_id === this.value);
        if (cam) updateDetailView(cam);
    });
}

// ── UPDATE TAMPILAN DETAIL (SAAT KAMERA DIPILIH) ──
function updateDetailView(cam) {
    currentCameraId = cam.camera_id;

    // Update Judul
    const titleEl = document.getElementById('cam-detail-title');
    const subEl = document.getElementById('cam-detail-sub');

    if (titleEl) titleEl.textContent = 'Camera Detail';
    if (subEl) subEl.textContent = `${cam.camera_id} · ${cam.location_name}`;

    // Update Video Stream
    const feedImg = document.getElementById('video-feed');
    const placeholder = document.getElementById('feed-placeholder');

    if (feedImg) {
        // Ambil langsung dari localStorage, bypass getToken() yang bisa redirect
        const token = localStorage.getItem('access_token');
        if (!token) {
            showCameraError('⚠️ Sesi habis, silakan login ulang.');
            return;
        }
        feedImg.src = `${API_BASE}/api/v1/stream/${cam.camera_id}?token=${token}`;
        feedImg.style.display = 'block';

        if (placeholder) {
            placeholder.style.display = 'none';
        }
    }

    // Terapkan koordinat dari database ke Kanvas
    point1.x = cam.line_x1 ?? 150;
    point1.y = cam.line_y1 ?? 250;
    point2.x = cam.line_x2 ?? 450;
    point2.y = cam.line_y2 ?? 250;

    drawCanvas();
}


// ── LOGIKA CANVAS INTERAKTIF (DRAG & DROP) ──
function initCanvasLogic() {
    canvas = document.getElementById('virtualLineCanvas');
    if (!canvas) return;
    
    // Atur ukuran kanvas statis untuk standarisasi koordinat AI (misal 640x480)
    // CSS akan men-scale ini ke ukuran layar user, tapi koordinat internal tetap akurat
    canvas.width = 640;
    canvas.height = 480;
    ctx = canvas.getContext('2d');

    // Daftarkan event pendeteksi mouse
    canvas.addEventListener('mousedown', handleMouseDown);
    canvas.addEventListener('mousemove', handleMouseMove);
    canvas.addEventListener('mouseup', handleMouseUp);
    canvas.addEventListener('mouseout', handleMouseUp);
}

function drawCanvas() {
    if (!ctx) return;
    
    // Bersihkan frame sebelumnya
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // 1. Gambar Garis Utama
    ctx.beginPath();
    ctx.moveTo(point1.x, point1.y);
    ctx.lineTo(point2.x, point2.y);
    ctx.strokeStyle = 'rgba(231, 74, 59, 0.8)'; // Merah Transparan
    ctx.lineWidth = 4;
    ctx.stroke();

    // 2. Gambar Teks Bantuan Sisi A & B
    ctx.fillStyle = '#1cc88a'; // Hijau
    ctx.font = 'bold 16px Arial';
    ctx.fillText("▲ SISI A (Inbound)", point1.x + 20, point1.y - 15);
    
    ctx.fillStyle = '#f6c23e'; // Kuning
    ctx.fillText("▼ SISI B (Outbound)", point2.x - 170, point2.y + 25);

    // 3. Gambar Lingkaran Titik 1 (Biru)
    ctx.beginPath();
    ctx.arc(point1.x, point1.y, point1.radius, 0, Math.PI * 2);
    ctx.fillStyle = '#4e73df'; 
    ctx.fill();
    ctx.lineWidth = 2;
    ctx.strokeStyle = '#ffffff';
    ctx.stroke();

    // 4. Gambar Lingkaran Titik 2 (Kuning)
    ctx.beginPath();
    ctx.arc(point2.x, point2.y, point2.radius, 0, Math.PI * 2);
    ctx.fillStyle = '#f6c23e';
    ctx.fill();
    ctx.stroke();
}

// ── FUNGSI PERHITUNGAN KOORDINAT MOUSE ──
function getMousePos(evt) {
    const rect = canvas.getBoundingClientRect();
    // Kalkulasi rasio jika ukuran tampilan CSS berbeda dengan ukuran internal kanvas
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;

    return {
        x: (evt.clientX - rect.left) * scaleX,
        y: (evt.clientY - rect.top) * scaleY
    };
}

function handleMouseDown(e) {
    const mousePos = getMousePos(e);

    // Cek apakah mouse mengklik area Titik 1 (dengan toleransi klik)
    const dist1 = Math.hypot(mousePos.x - point1.x, mousePos.y - point1.y);
    if (dist1 < point1.radius + 10) {
        point1.isDragging = true;
        return; // Jangan drag dua-duanya sekaligus
    }

    // Cek apakah mouse mengklik area Titik 2
    const dist2 = Math.hypot(mousePos.x - point2.x, mousePos.y - point2.y);
    if (dist2 < point2.radius + 10) {
        point2.isDragging = true;
    }
}

function handleMouseMove(e) {
    // Jika tidak ada yang di-drag, ubah kursor saja jika hovering
    const mousePos = getMousePos(e);
    const dist1 = Math.hypot(mousePos.x - point1.x, mousePos.y - point1.y);
    const dist2 = Math.hypot(mousePos.x - point2.x, mousePos.y - point2.y);
    
    if (dist1 < point1.radius + 10 || dist2 < point2.radius + 10) {
        canvas.style.cursor = 'grab';
    } else {
        canvas.style.cursor = 'crosshair';
    }

    // Update koordinat jika sedang drag
    if (point1.isDragging) {
        point1.x = mousePos.x;
        point1.y = mousePos.y;
        drawCanvas();
    } else if (point2.isDragging) {
        point2.x = mousePos.x;
        point2.y = mousePos.y;
        drawCanvas();
    }
}

function handleMouseUp() {
    point1.isDragging = false;
    point2.isDragging = false;
}

// ── SIMPAN KE BACKEND ──
async function saveVirtualLine() {
    if (!currentCameraId) {
        alert("Pilih kamera terlebih dahulu!");
        return;
    }
    
    const btn = document.getElementById('saveLineBtn');
    const originalText = btn.innerHTML;
    btn.innerHTML = "Menyimpan...";
    btn.disabled = true;

    // Bulatkan koordinat ke Integer sesuai schema database
    const payload = {
        line_x1: Math.round(point1.x),
        line_y1: Math.round(point1.y),
        line_x2: Math.round(point2.x),
        line_y2: Math.round(point2.y)
    };

    try {
        const res = await apiFetch(`${API_BASE}/api/v1/cameras/${currentCameraId}/line`, {
            method: 'PATCH',
            body: JSON.stringify(payload)
        });

        if (res && res.ok) {
            alert(`✅ Garis Virtual Berhasil Disimpan!\n\nKoordinat AI yang baru:\nTitik 1: (${payload.line_x1}, ${payload.line_y1})\nTitik 2: (${payload.line_x2}, ${payload.line_y2})`);
            
            // Perbarui data di cache lokal agar tidak reset saat pindah kamera
            const cam = _allCameras.find(c => c.camera_id === currentCameraId);
            if(cam) {
                cam.line_x1 = payload.line_x1; cam.line_y1 = payload.line_y1;
                cam.line_x2 = payload.line_x2; cam.line_y2 = payload.line_y2;
            }
        } else {
            alert('❌ Gagal menyimpan posisi garis ke database.');
        }
    } catch (e) {
        console.error('Error saving line:', e);
        alert('❌ Terjadi kesalahan jaringan saat menyimpan.');
    } finally {
        btn.innerHTML = originalText;
        btn.disabled = false;
    }
}

// ── HELPER ERROR & INISIALISASI ──
function showCameraError(msg) {
    const detail = document.querySelector('.cam-detail-grid');
    if (detail) {
        detail.innerHTML = `<div class="loading-state" style="padding: 50px; text-align: center;">${msg}</div>`;
    }
}

function initCamerasScript() {
    if (!getToken()) return;
    initCamerasPage();
}

// Bootstrapping saat halaman HTML dimuat
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initCamerasScript);
} else {
    initCamerasScript();
}