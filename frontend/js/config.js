// config.js - Configuración global de la aplicación
(function initializeAppConfig() {
    const existingConfig = typeof window.APP_CONFIG === 'object' ? window.APP_CONFIG : {};
    const fallbackHttpOrigin = 'http://localhost:8000';

    const getWindowOrigin = () => {
        try {
            if (window?.location?.origin && window.location.origin !== 'null') {
                return window.location.origin;
            }
        } catch (error) {
            console.warn('No se pudo obtener window.location.origin:', error);
        }
        return null;
    };

    const resolveOrigin = () => {
        if (existingConfig.API_BASE_URL) {
            try {
                return new URL(existingConfig.API_BASE_URL).origin;
            } catch (error) {
                console.warn('API_BASE_URL inválido. Usando valores por defecto.', error);
            }
        }

        return getWindowOrigin() || fallbackHttpOrigin;
    };

    const ensureTrailingRemoved = (value) => value.replace(/\/$/, '');

    const origin = ensureTrailingRemoved(resolveOrigin());
    const defaultApiBase = `${origin}/api`;

    const normalizeApiBase = (value) => ensureTrailingRemoved(value || defaultApiBase);

    const resolveWsUrl = () => {
        if (existingConfig.WS_URL) {
            return ensureTrailingRemoved(existingConfig.WS_URL);
        }

        try {
            const url = new URL(origin);
            const protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
            return `${protocol}//${url.host}/ws/market-data`;
        } catch (error) {
            console.warn('No se pudo construir la URL de WebSocket. Usando valores por defecto.', error);
            return 'ws://localhost:8000/ws/market-data';
        }
    };

    window.APP_CONFIG = {
        ...existingConfig,
        ENV: existingConfig.ENV || 'development',
        DEBUG: existingConfig.DEBUG !== undefined ? existingConfig.DEBUG : true,
        API_BASE_URL: normalizeApiBase(existingConfig.API_BASE_URL),
        WS_URL: resolveWsUrl()
    };

    window.buildApiUrl = function buildApiUrl(path = '') {
        const base = ensureTrailingRemoved(window.APP_CONFIG.API_BASE_URL);
        if (!path) return base;
        const normalisedPath = `/${String(path).replace(/^\/+/g, '')}`;
        return `${base}${normalisedPath}`;
    };

    window.buildWsUrl = function buildWsUrl(path = '') {
        const base = ensureTrailingRemoved(window.APP_CONFIG.WS_URL);
        if (!path) return base;
        const normalisedPath = `/${String(path).replace(/^\/+/g, '')}`;
        return `${base}${normalisedPath}`;
    };

    console.log('🚀 Configuración de la aplicación cargada:', window.APP_CONFIG);

    // Función para verificar la conectividad
    window.checkConnectivity = async function checkConnectivity() {
        try {
            const response = await fetch(window.buildApiUrl('health'));
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
})();
