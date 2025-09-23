// Market Data Service - Versión Mejorada y Corregida

// Registro global de timers asociados al servicio de datos de mercado.
// Nos permite proteger timers críticos cuando la capa de emergencia limpia
// los identificadores pendientes.
if (typeof window !== 'undefined' && !window.__marketDataTimers) {
    window.__marketDataTimers = new Set();
}

function registerMarketDataTimer(timerId) {
    if (typeof window !== 'undefined' && typeof timerId === 'number') {
        window.__marketDataTimers.add(timerId);
    }
    return timerId;
}

function unregisterMarketDataTimer(timerId) {
    if (typeof window !== 'undefined' && window.__marketDataTimers) {
        window.__marketDataTimers.delete(timerId);
    }
}

class MarketDataService {
    constructor() {
        this.tickers = {
            top: [],
            worst: []
        };
        this.wsManager = null;
        this.connectionStatus = 'disconnected';
        this.initialLoadDone = false;
        this.useWebSockets = true;
        this.pollingIntervals = []; // Track intervals para limpiarlos después
        this.eventListeners = new Map();
        this.lastEmittedTickers = {
            top: [],
            worst: []
        };
        this.ready = false;
        this.watchlistConfig = [
            { symbol: 'BTC', type: 'crypto' },
            { symbol: 'ETH', type: 'crypto' },
            { symbol: 'AAPL', type: 'stock' }
        ];
        this.watchlistData = new Map();
        this.cryptoSymbols = new Set([
            'BTC', 'ETH', 'BNB', 'XRP', 'ADA', 'DOGE', 'SOL', 'DOT', 'AVAX',
            'MATIC', 'LTC', 'LINK', 'UNI', 'ATOM', 'ETC', 'XLM', 'BCH', 'VET',
            'TRX', 'FIL'
        ]);
        this.watchlistRefreshTimer = null;
    }

    on(event, callback) {
        if (typeof callback !== 'function') {
            return () => {};
        }

        if (!this.eventListeners.has(event)) {
            this.eventListeners.set(event, new Set());
        }

        const listeners = this.eventListeners.get(event);
        listeners.add(callback);

        return () => this.off(event, callback);
    }

    off(event, callback) {
        const listeners = this.eventListeners.get(event);
        if (!listeners) return;

        listeners.delete(callback);

        if (!listeners.size) {
            this.eventListeners.delete(event);
        }
    }

    emit(event, payload) {
        const listeners = this.eventListeners.get(event);
        if (listeners) {
            listeners.forEach(listener => {
                try {
                    listener(payload);
                } catch (error) {
                    console.error(`Error ejecutando listener para ${event}:`, error);
                }
            });
        }

        if (typeof window !== 'undefined' && typeof window.dispatchEvent === 'function') {
            try {
                window.dispatchEvent(new CustomEvent(`marketData:${event}`, { detail: payload }));
            } catch (error) {
                console.error('Error dispatching marketData event:', error);
            }
        }
    }

    emitTickers(source = 'unknown') {
        const snapshot = this.getTickerSnapshot();
        this.lastEmittedTickers = snapshot;
        this.emit('tickers', {
            ...snapshot,
            source,
            timestamp: Date.now()
        });
    }

    getTickerSnapshot() {
        return {
            top: Array.isArray(this.tickers.top) ? [...this.tickers.top] : [],
            worst: Array.isArray(this.tickers.worst) ? [...this.tickers.worst] : []
        };
    }

    getAuthHeaders() {
        if (typeof window === 'undefined') {
            return {};
        }

        try {
            const token = localStorage.getItem('bb_token');
            return token ? { 'Authorization': `Bearer ${token}` } : {};
        } catch (error) {
            console.warn('Unable to access auth token from storage:', error);
            return {};
        }
    }

    parseNumber(value) {
        if (typeof value === 'number') {
            return Number.isFinite(value) ? value : null;
        }

        if (typeof value === 'string') {
            const cleaned = value.replace(/[^0-9+\-.,]/g, '');
            const normalised = cleaned.replace(/,/g, '');
            const parsed = Number.parseFloat(normalised);
            return Number.isNaN(parsed) ? null : parsed;
        }

        return null;
    }

    formatCurrency(value) {
        const numeric = this.parseNumber(value);

        if (numeric === null) {
            if (typeof value === 'string' && value.trim()) {
                return value;
            }
            return '--';
        }

        return `$${numeric.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    }

    formatPercent(value) {
        const numeric = this.parseNumber(value);

        if (numeric === null) {
            if (typeof value === 'string' && value.trim()) {
                return value;
            }
            return '0%';
        }

        const sign = numeric > 0 ? '+' : '';
        return `${sign}${numeric.toFixed(2)}%`;
    }

    normalizeWatchlistEntry(symbol, data) {
        const upperSymbol = String(symbol || '').toUpperCase();

        if (!data) {
            const fallback = this.getSimulatedPrice(upperSymbol);
            return {
                symbol: upperSymbol,
                price: fallback.price,
                change: fallback.change,
                changeValue: this.parseNumber(fallback.change) || 0
            };
        }

        const priceCandidate = data.raw_price ?? data.price ?? data.lastPrice ?? data.value;
        const changeCandidate = data.raw_change ?? data.changeValue ?? data.change_percent ?? data.change;

        const price = this.formatCurrency(priceCandidate);
        const change = this.formatPercent(changeCandidate);
        const changeValue = this.parseNumber(changeCandidate ?? change) || 0;

        return {
            symbol: upperSymbol,
            price,
            change,
            changeValue
        };
    }

    storeWatchlistEntries(entries = [], source = 'unknown') {
        if (!Array.isArray(entries)) {
            return;
        }

        entries.forEach(entry => {
            if (!entry || !entry.symbol) {
                return;
            }

            const normalized = this.normalizeWatchlistEntry(entry.symbol, entry);
            this.watchlistData.set(normalized.symbol, normalized);
        });

        this.emitWatchlist(source);
    }

    emitWatchlist(source = 'unknown') {
        const snapshot = this.watchlistConfig.map(item => {
            const cached = this.watchlistData.get(item.symbol);
            if (cached) {
                return cached;
            }
            const fallback = this.normalizeWatchlistEntry(item.symbol, this.getSimulatedPrice(item.symbol));
            this.watchlistData.set(item.symbol, fallback);
            return fallback;
        });

        this.emit('watchlist', {
            items: snapshot,
            source,
            timestamp: Date.now()
        });
    }

    async refreshWatchlistFromApi(source = 'api') {
        const tasks = this.watchlistConfig.map(async (item) => {
            try {
                const price = await this.getPrice(item.symbol);
                return this.normalizeWatchlistEntry(item.symbol, price);
            } catch (error) {
                console.warn(`Error refreshing watchlist symbol ${item.symbol}:`, error);
                return this.normalizeWatchlistEntry(item.symbol, this.getSimulatedPrice(item.symbol));
            }
        });

        const results = await Promise.all(tasks);
        this.storeWatchlistEntries(results, source);
    }

    updateWatchlistFromRealtime(marketData) {
        if (!marketData) {
            return;
        }

        const combined = [
            ...(Array.isArray(marketData.top_performers) ? marketData.top_performers : []),
            ...(Array.isArray(marketData.worst_performers) ? marketData.worst_performers : [])
        ];

        if (!combined.length) {
            return;
        }

        const watchSymbols = new Set(this.watchlistConfig.map(item => item.symbol.toUpperCase()));
        const relevant = combined
            .filter(item => item && item.symbol && watchSymbols.has(String(item.symbol).toUpperCase()))
            .map(item => this.normalizeWatchlistEntry(item.symbol, item));

        if (relevant.length) {
            this.storeWatchlistEntries(relevant, 'realtime');
        }
    }

    scheduleWatchlistRefresh() {
        if (this.watchlistRefreshTimer) {
            return;
        }

        this.watchlistRefreshTimer = setInterval(() => {
            this.refreshWatchlistFromApi('interval').catch(error => {
                console.error('Watchlist interval refresh failed:', error);
            });
        }, 60000);

        registerMarketDataTimer(this.watchlistRefreshTimer);
        this.pollingIntervals.push(this.watchlistRefreshTimer);
    }

    isCryptoSymbol(symbol) {
        return this.cryptoSymbols.has(String(symbol || '').toUpperCase());
    }

    async init() {
        console.log('🚀 Inicializando MarketDataService...');

        // Limpiar intervals anteriores si existen
        this.cleanup();
        
        // Configuración segura de API base
        this.API_BASE_URL = window.APP_CONFIG?.API_BASE_URL || window.API_BASE_URL || 'http://localhost:8000/api';
        this.WS_URL = window.APP_CONFIG?.WS_URL || 'ws://localhost:8000/ws/market-data';
        
        console.log('📡 Configuración:', {
            API_BASE_URL: this.API_BASE_URL,
            WS_URL: this.WS_URL
        });

        await this.start();
        this.ready = true;
        this.emit('ready', { service: this, timestamp: Date.now() });
    }

    async start() {
        // Cargar datos iniciales
        await this.loadInitialMarketData();
        await this.refreshWatchlistFromApi('initial');
        this.scheduleWatchlistRefresh();

        // Intentar WebSockets solo si está habilitado
        if (this.useWebSockets) {
            this.initWebSocketManager();
        } else {
            console.log('⚠️ WebSockets deshabilitados, usando modo estático');
            this.updateConnectionStatus('static');
        }
    }

    async loadInitialMarketData() {
        if (this.initialLoadDone) {
            this.emitTickers('cache');
            return;
        }

        try {
            console.log('📊 Cargando datos iniciales...');
            const apiData = await this.fetchFromBackend();

            if (apiData && apiData.success) {
                this.processApiData(apiData.data);
                this.initialLoadDone = true;
                console.log('✅ Datos iniciales cargados correctamente');
                this.emitTickers('api');
            } else {
                this.loadSimulatedData('api_unavailable');
                console.log('⚠️ Usando datos simulados (API no disponible)');
            }
        } catch (error) {
            console.log('❌ Error cargando datos iniciales, usando simulados:', error);
            this.loadSimulatedData('api_error');
        }
    }

    async fetchFromBackend() {
        try {
            const response = await fetch(`${this.API_BASE_URL}/market/top-performers`);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            return await response.json();
        } catch (error) {
            console.error('❌ Error fetching from backend:', error);
            throw error;
        }
    }

    initWebSocketManager() {
        console.log('🔌 Inicializando WebSocket manager...');
        this.wsManager = new WebSocketManager(this.WS_URL);
        
        this.wsManager.on('connected', () => {
            this.connectionStatus = 'connected';
            this.updateConnectionStatus('connected');
            console.log('✅ WebSocket conectado correctamente');
        });

        this.wsManager.on('disconnected', () => {
            this.connectionStatus = 'disconnected';
            this.updateConnectionStatus('disconnected');
            console.log('❌ WebSocket desconectado');
        });

        this.wsManager.on('error', (error) => {
            this.connectionStatus = 'error';
            this.updateConnectionStatus('error');
            console.error('❌ Error de WebSocket:', error);
            
            // Deshabilitar WebSockets después de múltiples errores
            this.useWebSockets = false;
        });

        this.wsManager.on('market_data', (data) => {
            console.log('📊 Datos recibidos via WebSocket');
            this.handleMarketData(data);
        });

        this.wsManager.on('heartbeat', () => {
            console.log('💓 Heartbeat recibido');
        });

        this.wsManager.on('alert', (alertPayload) => {
            this.emit('alert', {
                ...alertPayload,
                timestamp: Date.now(),
                source: 'realtime'
            });
        });

        // Conectar WebSocket después de un delay
        const connectTimeout = setTimeout(() => {
            if (this.useWebSockets) {
                console.log('🔗 Conectando WebSocket...');
                this.wsManager.connect();
            }
            unregisterMarketDataTimer(connectTimeout);
        }, 2000);

        registerMarketDataTimer(connectTimeout);
        this.pollingIntervals.push(connectTimeout);
    }

    processApiData(apiData) {
        if (!apiData) {
            console.warn('⚠️ Datos de API no válidos para procesar');
            return;
        }

        const { top_performers = [], worst_performers = [] } = apiData;

        this.tickers.top = Array.isArray(top_performers) ? top_performers : [];
        this.tickers.worst = Array.isArray(worst_performers) ? worst_performers : [];
    }

    async getPrice(symbol) {
        const upperSymbol = String(symbol || '').toUpperCase();
        const isCrypto = this.isCryptoSymbol(upperSymbol);
        const url = isCrypto
            ? `${this.API_BASE_URL}/crypto/${upperSymbol}`
            : `${this.API_BASE_URL}/market/price/${upperSymbol}`;

        try {
            const response = await fetch(url, { headers: this.getAuthHeaders() });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();

            if (isCrypto) {
                return data;
            }

            if (data && data.success) {
                return data.data;
            }

            return data || this.getSimulatedPrice(upperSymbol);
        } catch (error) {
            console.warn(`Falling back to simulated price for ${upperSymbol}:`, error);
            return this.getSimulatedPrice(upperSymbol);
        }
    }

    getSimulatedPrice(symbol) {
        const simulatedPrices = {
            'BTC': { price: '$45,123.45', change: '+2.5%' },
            'ETH': { price: '$2,567.89', change: '+1.8%' },
            'AAPL': { price: '$178.90', change: '+0.7%' },
            'TSLA': { price: '$245.67', change: '-0.8%' },
            'MSFT': { price: '$345.21', change: '+0.3%' },
            'GOOGL': { price: '$145.32', change: '+0.5%' },
            'AMZN': { price: '$178.56', change: '+0.4%' },
            'NVDA': { price: '$456.78', change: '+1.5%' },
            'BNB': { price: '$312.45', change: '+0.2%' },
            'XRP': { price: '$0.58', change: '-0.3%' },
            'DOGE': { price: '$0.12', change: '-0.2%' },
            'ADA': { price: '$0.45', change: '-0.1%' }
        };
        
        return simulatedPrices[symbol.toUpperCase()] || { price: '--', change: '0%' };
    }

    loadSimulatedData(reason = 'fallback') {
        console.log('🔄 Cargando datos simulados...');
        this.tickers = {
            top: [
                { symbol: 'BTC', change: '+2.5%', price: '$45,123', changeValue: 2.5 },
                { symbol: 'ETH', change: '+1.8%', price: '$2,567', changeValue: 1.8 },
                { symbol: 'AAPL', change: '+0.7%', price: '$178.90', changeValue: 0.7 },
                { symbol: 'MSFT', change: '+0.3%', price: '$345.21', changeValue: 0.3 },
                { symbol: 'BNB', change: '+0.2%', price: '$312.45', changeValue: 0.2 }
            ],
            worst: [
                { symbol: 'TSLA', change: '-0.8%', price: '$245.67', changeValue: -0.8 },
                { symbol: 'XRP', change: '-0.3%', price: '$0.58', changeValue: -0.3 },
                { symbol: 'DOGE', change: '-0.2%', price: '$0.12', changeValue: -0.2 },
                { symbol: 'ADA', change: '-0.1%', price: '$0.45', changeValue: -0.1 }
            ]
        };
        this.initialLoadDone = true;
        this.emitTickers('simulated');
        this.emit('fallback', {
            reason,
            timestamp: Date.now()
        });
        this.storeWatchlistEntries(
            this.watchlistConfig.map(item => this.normalizeWatchlistEntry(item.symbol, this.getSimulatedPrice(item.symbol))),
            'simulated'
        );
        if (this.connectionStatus !== 'static') {
            this.updateConnectionStatus('static', { reason });
        }
    }

    handleMarketData(marketData) {
        if (marketData && marketData.top_performers) {
            console.log('✅ Datos reales recibidos via WebSocket');
            this.tickers.top = marketData.top_performers.slice(0, 5);
            this.tickers.worst = marketData.worst_performers.slice(0, 5);
            this.emitTickers('realtime');
            this.updateWatchlistFromRealtime(marketData);
        }
    }

    updateConnectionStatus(status, metadata = {}) {
        this.connectionStatus = status;
        this.emit('connection', {
            status,
            timestamp: Date.now(),
            ...metadata
        });
    }

    cleanup() {
        // Limpiar todos los intervals y timeouts
        this.pollingIntervals.forEach(intervalId => {
            clearTimeout(intervalId);
            clearInterval(intervalId);
            unregisterMarketDataTimer(intervalId);
        });
        this.pollingIntervals = [];
        this.watchlistRefreshTimer = null;

        if (this.watchlistData) {
            this.watchlistData.clear();
        }

        if (this.wsManager) {
            this.wsManager.disconnect();
        }
    }

    disconnect() {
        this.cleanup();
    }
}

// WebSocket Manager Mejorado
class WebSocketManager {
    constructor(wsUrl) {
        this.wsUrl = wsUrl || 'ws://localhost:8000/ws/market-data';
        this.ws = null;
        this.isConnected = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 3;
        this.reconnectDelay = 2000;
        this.pingInterval = null;
        this.eventListeners = {};
    }

    on(event, callback) {
        if (!this.eventListeners[event]) this.eventListeners[event] = [];
        this.eventListeners[event].push(callback);
    }

    emit(event, data) {
        if (this.eventListeners[event]) {
            this.eventListeners[event].forEach(callback => callback(data));
        }
    }

    connect() {
        try {
            console.log('🔗 Conectando a WebSocket:', this.wsUrl);
            this.ws = new WebSocket(this.wsUrl);

            this.ws.onopen = () => {
                console.log('✅ WebSocket conectado');
                this.isConnected = true;
                this.reconnectAttempts = 0;
                this.emit('connected');
                this.startPingInterval();
            };

            this.ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    if (data.type === 'market_data') {
                        this.emit('market_data', data.data);
                    } else if (data.type === 'alert') {
                        this.emit('alert', data);
                    } else if (data.type === 'pong') {
                        console.log('🏓 Pong recibido');
                    } else if (data.type === 'connection_established') {
                        console.log('✅ Conexión establecida:', data.message);
                    }
                } catch (error) {
                    console.error('Error parsing message:', error);
                }
            };

            this.ws.onclose = (event) => {
                console.log('❌ WebSocket cerrado:', event.code, event.reason);
                this.handleDisconnection();
            };

            this.ws.onerror = (error) => {
                console.error('❌ WebSocket error:', error);
                this.emit('error', error);
                this.handleDisconnection();
            };

        } catch (error) {
            console.error('Error creating WebSocket:', error);
            this.handleDisconnection();
        }
    }

    handleDisconnection() {
        this.isConnected = false;
        this.stopPingInterval();
        this.emit('disconnected');
        
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            const delay = this.reconnectDelay * this.reconnectAttempts;
            console.log(`🔄 Reintentando en ${delay/1000}s (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
            setTimeout(() => this.connect(), delay);
        } else {
            console.error('❌ Máximo de intentos alcanzado');
            this.emit('error', 'Max reconnection attempts');
        }
    }

    startPingInterval() {
        this.pingInterval = setInterval(() => {
            if (this.isConnected && this.ws.readyState === WebSocket.OPEN) {
                this.ws.send(JSON.stringify({ type: 'ping', timestamp: new Date().toISOString() }));
            }
        }, 30000);
    }

    stopPingInterval() {
        if (this.pingInterval) {
            clearInterval(this.pingInterval);
            this.pingInterval = null;
        }
    }

    disconnect() {
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
        this.isConnected = false;
        this.stopPingInterval();
    }
}

// Inicialización segura cuando el DOM esté listo
function initializeMarketData(options = {}) {
    const { forceReinitialize = false } = options;
    console.log('🚀 Inicializando BullBearBroker Market Data...', options);

    // Configuración global
    window.APP_CONFIG = window.APP_CONFIG || {
        API_BASE_URL: 'http://localhost:8000/api',
        WS_URL: 'ws://localhost:8000/ws/market-data'
    };

    const setupService = () => {
        if (forceReinitialize && window.marketData) {
            console.log('♻️ Reiniciando instancia existente de MarketDataService');
            if (typeof window.marketData.cleanup === 'function') {
                window.marketData.cleanup();
            }
            window.marketData = null;
        }

        if (!window.marketData) {
            window.marketData = new MarketDataService();
            if (typeof window.dispatchEvent === 'function') {
                window.dispatchEvent(new CustomEvent('marketData:service-created', {
                    detail: { service: window.marketData }
                }));
            }
        }

        window.marketData.init();
    };

    const setupGlobalHelpers = () => {
        window.getAssetPrice = async function(symbol) {
            if (window.marketData) {
                return await window.marketData.getPrice(symbol);
            }
            return null;
        };

        window.testWebSocketConnection = function() {
            if (window.marketData && window.marketData.wsManager) {
                window.marketData.wsManager.disconnect();
                setTimeout(() => window.marketData.wsManager.connect(), 1000);
            }
        };

        window.cleanupMarketData = function() {
            if (window.marketData) {
                window.marketData.cleanup();
            }
        };
    };

    const ensureWebSocketConnection = () => {
        const verificationTimeout = setTimeout(() => {
            try {
                if (window.marketData && window.marketData.useWebSockets) {
                    if (!window.marketData.wsManager) {
                        console.warn('⚠️ WebSocket manager no inicializado, reintentando init...');
                        window.marketData.init();
                    } else if (!window.marketData.wsManager.isConnected && typeof window.marketData.wsManager.connect === 'function') {
                        console.log('🔁 Forzando conexión del WebSocket tras verificación...');
                        window.marketData.wsManager.connect();
                    }
                }
            } finally {
                unregisterMarketDataTimer(verificationTimeout);
            }
        }, 1500);

        registerMarketDataTimer(verificationTimeout);
    };

    const runInitialization = () => {
        setupService();
        setupGlobalHelpers();
        ensureWebSocketConnection();
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', runInitialization, { once: true });
    } else {
        runInitialization();
    }
}

// Inicializar cuando esté listo
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeMarketData);
} else {
    initializeMarketData();
}
