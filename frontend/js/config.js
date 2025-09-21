// config.js - Configuración global de la aplicación
(function initializeAppConfig() {
    const globalWindow = typeof window !== 'undefined' ? window : undefined;
    const preloadedConfig = globalWindow && typeof globalWindow.__BULL_BEAR_CONFIG__ === 'object'
        ? globalWindow.__BULL_BEAR_CONFIG__
        : {};
    const existingConfig = globalWindow && typeof globalWindow.APP_CONFIG === 'object'
        ? globalWindow.APP_CONFIG
        : {};
    const scriptConfig = (() => {
        const currentScript = typeof document !== 'undefined' ? document.currentScript : null;
        if (!currentScript) return {};
        const { dataset = {} } = currentScript;
        const normaliseValue = (value) => (typeof value === 'string' && value.trim().length > 0
            ? value.trim()
            : undefined);
        return {
            API_BASE_URL: normaliseValue(dataset.apiBaseUrl),
            WS_URL: normaliseValue(dataset.wsUrl),
            BACKEND_ORIGIN: normaliseValue(dataset.backendOrigin)
        };
    })();

    const combinedConfig = {
        ...preloadedConfig,
        ...existingConfig,
        ...scriptConfig
    };

    const fallbackHttpOrigin = combinedConfig.BACKEND_ORIGIN || 'http://localhost:8000';

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
        if (combinedConfig.API_BASE_URL) {
            try {
                return new URL(combinedConfig.API_BASE_URL).origin;
            } catch (error) {
                console.warn('API_BASE_URL inválido. Usando valores por defecto.', error);
            }
        }

        const windowOrigin = getWindowOrigin();
        if (windowOrigin) {
            try {
                const parsed = new URL(windowOrigin);
                if (parsed.port && parsed.port !== '8000') {
                    return fallbackHttpOrigin;
                }
                return windowOrigin;
            } catch (error) {
                console.warn('window.location.origin inválido. Usando valores por defecto.', error);
            }
        }

        return fallbackHttpOrigin;
    };

    const ensureTrailingRemoved = (value) => value.replace(/\/$/, '');

    const origin = ensureTrailingRemoved(resolveOrigin());
    const defaultApiBase = `${origin}/api`;

    const normalizeApiBase = (value) => ensureTrailingRemoved(value || defaultApiBase);

    const resolveWsUrl = () => {
        if (combinedConfig.WS_URL) {
            return ensureTrailingRemoved(combinedConfig.WS_URL);
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
        ...combinedConfig,
        ENV: combinedConfig.ENV || 'development',
        DEBUG: combinedConfig.DEBUG !== undefined ? combinedConfig.DEBUG : true,
        API_BASE_URL: normalizeApiBase(combinedConfig.API_BASE_URL),
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
