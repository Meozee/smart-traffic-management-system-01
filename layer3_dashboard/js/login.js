// Deteksi base path ketika Live Server melayani workspace root
const BASE_PATH = window.location.pathname.includes('/layer3_dashboard/') ? '' : 'layer3_dashboard/';

document.getElementById('login-form').onsubmit = async (e) => {
    e.preventDefault();

    const usernameInput = document.getElementById('login-username').value;
    const passwordInput = document.getElementById('login-password').value;
    const errorBox = document.getElementById('error-box');

    // Sembunyikan error box setiap kali mencoba submit ulang
    errorBox.style.display = 'none';

    // Ambil base URL yang sama dari main config atau tulis manual untuk login
    const API_LOGIN = "http://localhost:8000/api/v1/auth/login";

    // Gunakan URLSearchParams karena OAuth2 di FastAPI membaca data via Form Data
    const formData = new URLSearchParams();
    formData.append('username', usernameInput);
    formData.append('password', passwordInput);

    try {
        const response = await fetch(API_LOGIN, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded'
            },
            body: formData
        });

        if (response.ok) {
            const data = await response.json();

            // SIMPAN TOKEN KE LOCAL STORAGE
            localStorage.setItem("access_token", data.access_token);

            // Lempar user ke halaman dashboard utama
            window.location.href = BASE_PATH + "index.html";
        } else {
            // Jika gagal (status 401/400)
            errorBox.textContent = "❌ Username atau password salah";
            errorBox.style.display = 'block';
        }
    } catch (err) {
        console.error(err);
        errorBox.textContent = "⚠️ Gagal terhubung ke backend server.";
        errorBox.style.display = 'block';
    }
};