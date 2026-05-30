document.getElementById('login-form').onsubmit = async (e) => {
    e.preventDefault();

    const usernameInput = document.getElementById('login-username').value.trim();
    const passwordInput = document.getElementById('login-password').value;
    const errorBox = document.getElementById('error-box');

    errorBox.style.display = 'none';

    const API_LOGIN = `${API_BASE}/api/v1/auth/login`;
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
            localStorage.setItem('access_token', data.access_token);
            localStorage.setItem('username', data.username || usernameInput);
            localStorage.setItem('role', data.role || 'supervisor');
            window.location.href = 'index.html';
            return;
        }

        const errorText = await response.text();
        errorBox.textContent = response.status === 401
            ? '❌ Username atau password salah'
            : `⚠️ Gagal login: ${response.status}`;
        errorBox.style.display = 'block';
        console.warn('Login failed', response.status, errorText);
    } catch (err) {
        console.error(err);
        errorBox.textContent = '⚠️ Gagal terhubung ke backend server.';
        errorBox.style.display = 'block';
    }
};