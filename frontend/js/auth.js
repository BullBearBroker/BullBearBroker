class AuthManager {
    constructor() {
        this.token = localStorage.getItem('bb_token');
        this.user = JSON.parse(localStorage.getItem('bb_user') || 'null');
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.checkAuthStatus();
    }

    setupEventListeners() {
        // Switch entre login y registro
        document.getElementById('switchToRegister')?.addEventListener('click', () => this.showRegister());
        document.getElementById('switchToLogin')?.addEventListener('click', () => this.showLogin());

        // Formularios
        document.getElementById('loginForm')?.addEventListener('submit', (e) => this.handleLogin(e));
        document.getElementById('registerForm')?.addEventListener('submit', (e) => this.handleRegister(e));
    }

    showRegister() {
        document.getElementById('loginForm').style.display = 'none';
        document.getElementById('registerForm').style.display = 'block';
        document.getElementById('switchToRegister').style.display = 'none';
        document.getElementById('switchToLogin').style.display = 'block';
    }

    showLogin() {
        document.getElementById('registerForm').style.display = 'none';
        document.getElementById('loginForm').style.display = 'block';
        document.getElementById('switchToLogin').style.display = 'none';
        document.getElementById('switchToRegister').style.display = 'block';
    }

    async handleLogin(e) {
        e.preventDefault();
        
        const email = document.getElementById('loginEmail').value;
        const password = document.getElementById('loginPassword').value;

        try {
            const response = await fetch('http://127.0.0.1:8000/api/auth/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                body: JSON.stringify({ email, password }),
                mode: 'cors' // ✅ Important for CORS
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
            }

            const data = await response.json();

            if (data.token && data.user) {
                this.saveAuthData(data);
                this.redirectToApp();
            } else {
                this.showError('Respuesta inválida del servidor');
            }
        } catch (error) {
            console.error('Login error:', error);
            this.showError(error.message || 'Error de conexión con el servidor');
        }
    }

    async handleRegister(e) {
        e.preventDefault();
        
        const email = document.getElementById('registerEmail').value;
        const username = document.getElementById('registerUsername').value;
        const password = document.getElementById('registerPassword').value;

        if (password.length < 6) {
            this.showError('La contraseña debe tener al menos 6 caracteres');
            return;
        }

        try {
            const response = await fetch('http://127.0.0.1:8000/api/auth/register', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                body: JSON.stringify({ email, username, password }),
                mode: 'cors' // ✅ Important for CORS
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
            }

            const data = await response.json();

            if (data.token && data.user) {
                this.saveAuthData(data);
                this.redirectToApp();
            } else {
                this.showError('Respuesta inválida del servidor');
            }
        } catch (error) {
            console.error('Register error:', error);
            this.showError(error.message || 'Error de conexión con el servidor');
        }
    }

    saveAuthData(data) {
        this.token = data.token;
        this.user = data.user;
        
        localStorage.setItem('bb_token', data.token);
        localStorage.setItem('bb_user', JSON.stringify(data.user));
        
        this.showSuccess('¡Autenticación exitosa!');
    }

    redirectToApp() {
        setTimeout(() => {
            window.location.href = 'index.html';
        }, 1000);
    }

    checkAuthStatus() {
        if (this.token && this.user) {
            this.redirectToApp();
        }
    }

    showError(message) {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-message';
        errorDiv.innerHTML = `
            <i class="fas fa-exclamation-circle"></i>
            ${message}
        `;
        
        document.body.appendChild(errorDiv);
        
        setTimeout(() => {
            errorDiv.remove();
        }, 5000);
    }

    showSuccess(message) {
        const successDiv = document.createElement('div');
        successDiv.className = 'success-message';
        successDiv.innerHTML = `
            <i class="fas fa-check-circle"></i>
            ${message}
        `;
        
        document.body.appendChild(successDiv);
        
        setTimeout(() => {
            successDiv.remove();
        }, 3000);
    }

    getToken() {
        return this.token;
    }

    getUser() {
        return this.user;
    }

    logout() {
        localStorage.removeItem('bb_token');
        localStorage.removeItem('bb_user');
        this.token = null;
        this.user = null;
        window.location.href = 'login.html';
    }

    isAuthenticated() {
        return !!this.token;
    }
}

// Inicializar cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', () => {
    window.authManager = new AuthManager();
});
