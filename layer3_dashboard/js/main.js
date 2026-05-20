// Konfigurasi Global
const API_BASE = "http://localhost:8000/api/v1";

// Fungsi untuk mendapatkan WIB
function getTodayWIB() {
    const now = new Date();
    const wibOffset = 7 * 60;
    const localOffset = now.getTimezoneOffset();
    const wibTime = new Date(now.getTime() + (wibOffset + localOffset) * 60000);
    return wibTime.toISOString().split('T')[0];
}

// Router Sederhana: Mengambil file HTML dari folder /pages
async function loadPage(pageName) {
    const contentDiv = document.getElementById('app-content');
    
    // Update tombol aktif di Sidebar
    document.querySelectorAll('.nav-btn').forEach(btn => btn.classList.remove('active'));
    event.currentTarget?.classList.add('active');

    try {
        // Ambil struktur HTML dari folder pages
        const response = await fetch(`pages/${pageName}.html`);
        if (!response.ok) throw new Error("Page not found");
        const html = await response.text();
        
        // Pasang HTML ke layar
        contentDiv.innerHTML = html;

        // Muat JS spesifik untuk halaman tersebut (Lazy Loading)
        loadPageScript(pageName);
        
    } catch (error) {
        contentDiv.innerHTML = `<div class="loading-state">⚠️ Gagal memuat halaman ${pageName}</div>`;
        console.error(error);
    }
}

// Fungsi untuk memuat file JS secara dinamis
function loadPageScript(pageName) {
    // Hapus script lama jika ada agar tidak double eksekusi
    const oldScript = document.getElementById('dynamic-script');
    if (oldScript) oldScript.remove();

    const script = document.createElement('script');
    script.id = 'dynamic-script';
    script.src = `js/${pageName}.js`; // Contoh: js/dashboard.js
    document.body.appendChild(script);
}

// Jam Digital
setInterval(() => {
    const clockEl = document.getElementById('clock');
    if (!clockEl) return;
    clockEl.textContent = new Date().toLocaleTimeString('id-ID', {
        timeZone: 'Asia/Jakarta',
        hour: '2-digit', minute: '2-digit', second: '2-digit'
    });
}, 1000);

// Load Dashboard pertama kali web dibuka
window.onload = () => {
    loadPage('dashboard');
    // Karena dipanggil manual tanpa klik, kita set manual nav-btn nya
    document.querySelector('.nav-btn').classList.add('active');
};