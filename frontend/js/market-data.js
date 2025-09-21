// Market Data Service - Versión Mejorada y Corregida
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

        this.start();
    }

    async start() {
        // Cargar datos iniciales
        await this.loadInitialMarketData();
        this.renderTickers();
        
        // Intentar WebSockets solo si está habilitado
        if (this.useWebSockets) {
            this.initWebSocketManager();
        } else {
            console.log('⚠️ WebSockets deshabilitados, usando modo estático');
            this.updateConnectionStatus('static');
        }
    }

    async loadInitialMarketData() {
        if (this.initialLoadDone) return;
        
        try {
            console.log('📊 Cargando datos iniciales...');
            const apiData = await this.fetchFromBackend();
            
            if (apiData && apiData.success) {
                this.processApiData(apiData.data);
                this.initialLoadDone = true;
                console.log('✅ Datos iniciales cargados correctamente');
            } else {
                this.loadSimulatedData();
                console.log('⚠️ Usando datos simulados (API no disponible)');
            }
        } catch (error) {
            console.log('❌ Error cargando datos iniciales, usando simulados:', error);
            this.loadSimulatedData();
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

        // Conectar WebSocket después de un delay
        const connectTimeout = setTimeout(() => {
            if (this.useWebSockets) {
                console.log('🔗 Conectando WebSocket...');
                this.wsManager.connect();
            }
        }, 2000);
        
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
        try {
            const response = await fetch(`${this.API_BASE_URL}/market/price/${symbol}`);
            
            if (response.ok) {
                const data = await response.json();
                if (data.success) {
                    return data.data;
                }
            }
            return this.getSimulatedPrice(symbol);
        } catch (error) {
            return this.getSimulatedPrice(symbol);
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

    loadSimulatedData() {
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
    }

    renderTickers() {
        this.renderTickerList('topTickers', this.tickers.top);
        this.renderTickerList('worstTickers', this.tickers.worst);
        this.updateWatchlist();
    }

    renderTickerList(containerId, tickers) {
        const container = document.getElementById(containerId);
        if (!container) {
            console.warn(`⚠️ Contenedor no encontrado: ${containerId}`);
            return;
        }

        container.innerHTML = tickers.map(ticker => `
            <div class="ticker-item" onclick="askQuestion('Precio de ${ticker.symbol}')">
                <span class="ticker-symbol">${ticker.symbol}</span>
                <span class="ticker-price">${ticker.price}</span>
                <span class="ticker-change ${ticker.change.includes('-') ? 'negative' : 'positive'}">
                    ${ticker.change}
                </span>
            </div>
        `).join('');
    }

    handleMarketData(marketData) {
        if (marketData && marketData.top_performers) {
            console.log('✅ Datos reales recibidos via WebSocket');
            this.tickers.top = marketData.top_performers.slice(0, 5);
            this.tickers.worst = marketData.worst_performers.slice(0, 5);
            this.renderTickers();
            this.updateMarketHeader();
        }
    }

    updateMarketHeader() {
        const marketTicker = document.querySelector('.market-ticker');
        if (!marketTicker || !this.tickers.top.length) return;

        marketTicker.innerHTML = this.tickers.top.slice(0, 3).map(item => `
            <div class="ticker-item">
                <span class="ticker-name">${item.symbol}</span>
                <span class="ticker-price">${item.price}</span>
                <span class="ticker-change ${item.change.includes('-') ? 'negative' : 'positive'}">
                    ${item.change}
                </span>
            </div>
        `).join('');
    }

    updateWatchlist() {
        const symbols = ['btc', 'eth', 'aapl'];
        symbols.forEach(symbol => {
            const priceElem = document.getElementById(`${symbol}Price`);
            const changeElem = document.getElementById(`${symbol}Change`);
            
            if (priceElem && changeElem) {
                const ticker = [...this.tickers.top, ...this.tickers.worst]
                    .find(t => t.symbol.toLowerCase() === symbol);
                
                if (ticker) {
                    priceElem.textContent = ticker.price;
                    changeElem.textContent = ticker.change;
                    changeElem.className = `item-change ${ticker.change.includes('-') ? 'negative' : 'positive'}`;
                }
            }
        });
    }

    updateConnectionStatus(status) {
        const statusElement = document.getElementById('connectionStatus');
        const statusTextElement = document.getElementById('connectionStatusText');
        
        if (statusElement) {
            statusElement.className = `connection-status ${status}`;
            const statusMessages = {
                'connected': '✅ Conectado a datos en tiempo real',
                'disconnected': '❌ Desconectado',
                'error': '⚠️ Error de conexión - Modo estático',
                'static': '📊 Usando datos estáticos'
            };
            statusElement.textContent = statusMessages[status] || 'Estado desconocido';
        }
        
        if (statusTextElement) {
            statusTextElement.textContent = status === 'connected' ? 'Conectado' : 'Desconectado';
        }
    }

    cleanup() {
        // Limpiar todos los intervals y timeouts
        this.pollingIntervals.forEach(intervalId => {
            clearTimeout(intervalId);
            clearInterval(intervalId);
        });
        this.pollingIntervals = [];
        
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
function initializeMarketData() {
    console.log('🚀 Inicializando BullBearBroker Market Data...');
    
    // Configuración global
    window.APP_CONFIG = window.APP_CONFIG || {
        API_BASE_URL: 'http://localhost:8000/api',
        WS_URL: 'ws://localhost:8000/ws/market-data'
    };
    
    // Inicializar con retraso para asegurar que todo esté cargado
    setTimeout(() => {
        if (!window.marketData) {
            window.marketData = new MarketDataService();
            window.marketData.init();
        }
        
        // Funciones globales
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
    }, 1000);
}

// Inicializar cuando esté listo
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeMarketData);
} else {
    initializeMarketData();
}
