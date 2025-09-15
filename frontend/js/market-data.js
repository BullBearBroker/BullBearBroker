class MarketData {
    constructor() {
        this.tickers = {
            top: [],
            worst: []
        };
        this.init();
    }

    async init() {
        await this.loadMarketData();
        this.renderTickers();
        this.startLiveUpdates();
    }

    async loadMarketData() {
        try {
            // Intentar cargar datos desde la API del backend
            const apiData = await this.fetchFromBackend();
            
            if (apiData && apiData.success) {
                this.processApiData(apiData.data);
            } else {
                // Fallback a datos simulados
                this.loadSimulatedData();
            }
        } catch (error) {
            console.log('Usando datos simulados:', error);
            this.loadSimulatedData();
        }
    }

    async fetchFromBackend() {
        try {
            const response = await fetch('http://localhost:8000/api/market/top-performers');
            if (!response.ok) {
                throw new Error('API not available');
            }
            return await response.json();
        } catch (error) {
            throw new Error('Error fetching from backend');
        }
    }

    processApiData(apiData) {
        // Procesar datos del backend
        this.tickers.top = apiData.top_performers || [];
        this.tickers.worst = apiData.worst_performers || [];
    }

    async getPrice(symbol) {
        try {
            // Intentar obtener precio del backend
            const response = await fetch(`http://localhost:8000/api/market/price/${symbol}`);
            
            if (response.ok) {
                const data = await response.json();
                if (data.success) {
                    return data.data;
                }
            }
            
            // Fallback a precio simulado
            return this.getSimulatedPrice(symbol);
            
        } catch (error) {
            console.log(`Price request failed for ${symbol}:`, error);
            return this.getSimulatedPrice(symbol);
        }
    }

    getSimulatedPrice(symbol) {
        // Datos simulados de respaldo
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
        
        return simulatedPrices[symbol.toUpperCase()] || null;
    }

    loadSimulatedData() {
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
                { symbol: 'NFLX', change: '-0.5%', price: '$567.89', changeValue: -0.5 },
                { symbol: 'XRP', change: '-0.3%', price: '$0.58', changeValue: -0.3 },
                { symbol: 'DOGE', change: '-0.2%', price: '$0.12', changeValue: -0.2 },
                { symbol: 'ADA', change: '-0.1%', price: '$0.45', changeValue: -0.1 }
            ]
        };
    }

    renderTickers() {
        this.renderTickerList('topTickers', this.tickers.top);
        this.renderTickerList('worstTickers', this.tickers.worst);
    }

    renderTickerList(containerId, tickers) {
        const container = document.getElementById(containerId);
        if (!container) return;

        container.innerHTML = tickers.map(ticker => `
            <div class="ticker-item" onclick="askQuestion('Precio de ${ticker.symbol}')">
                <span class="ticker-symbol">${ticker.symbol}</span>
                <span class="ticker-price ${ticker.change.includes('+') ? 'positive' : 'negative'}">
                    ${ticker.change}
                </span>
            </div>
        `).join('');
    }

    startLiveUpdates() {
        // Actualizar cada 30 segundos
        setInterval(async () => {
            await this.loadMarketData();
            this.renderTickers();
        }, 30000);
    }
}

// Función global para obtener precios
async function getAssetPrice(symbol) {
    return await marketData.getPrice(symbol);
}

// Inicializar datos de mercado
const marketData = new MarketData();