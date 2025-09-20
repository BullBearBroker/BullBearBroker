// config.js - Configuración global de la aplicación
window.APP_CONFIG = {
    API_BASE_URL: 'http://localhost:8000/api',
    WS_URL: 'ws://localhost:8000/ws/market-data',
    ENV: 'development',
    DEBUG: true
};

console.log('🚀 Configuración de la aplicación cargada:', window.APP_CONFIG);

// Función para verificar la conectividad
window.checkConnectivity = async function() {
    try {
        const response = await fetch(`${window.APP_CONFIG.API_BASE_URL}/health`);
        const data = await response.json();
        console.log('✅ Backend conectado:', data);
        return true;
    } catch (error) {
        console.error('❌ Error conectando al backend:', error);
        return false;
    }
};

// Verificar conectividad al cargar
setTimeout(() => {
    window.checkConnectivity();
}, 2000);
