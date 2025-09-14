class MarketData {
    constructor() {
        this.tickers = {
            top: [
                { symbol: 'BTC', change: '+2.5%', price: '$45,123' },
                { symbol: 'ETH', change: '+1.8%', price: '$2,567' },
                { symbol: 'AAPL', change: '+0.7%', price: '$178.90' }
            ],
            worst: [
                { symbol: 'TSLA', change: '-0.8%', price: '$245.67' },
                { symbol: 'NFLX', change: '-0.5%', price: '$567.89' }
            ]
        };
        this.init();
    }

    init() {
        this.renderTickers();
        this.startLiveUpdates();
    }

    renderTickers() {
        this.renderTickerList('topTickers', this.tickers.top);
        this.renderTickerList('worstTickers', this.tickers.worst);
    }

    renderTickerList(containerId, tickers) {
        const container = document.getElementById(containerId);
        if (!container) return;

        container.innerHTML = tickers.map(ticker => `
            <div class="ticker-item">
                <span class="ticker-symbol">${ticker.symbol}</span>
                <span class="ticker-price ${ticker.change.includes('+') ? 'positive' : 'negative'}">
                    ${ticker.change}
                </span>
            </div>
        `).join('');
    }

    startLiveUpdates() {
        // Simular actualizaciones en tiempo real
        setInterval(() => {
            this.updateTickers();
        }, 5000);
    }

    updateTickers() {
        // Simular cambios aleatorios en los precios
        this.tickers.top.forEach(ticker => {
            const change = Math.random() > 0.5 ? '+' : '-';
            const amount = (Math.random() * 0.8).toFixed(1);
            ticker.change = `${change}${amount}%`;
        });

        this.tickers.worst.forEach(ticker => {
            const change = Math.random() > 0.3 ? '+' : '-';
            const amount = (Math.random() * 0.5).toFixed(1);
            ticker.change = `${change}${amount}%`;
        });

        this.renderTickers();
    }

    async getRealMarketData() {
        try {
            // Aquí luego integraremos APIs reales
            const response = await fetch('https://api.binance.com/api/v3/ticker/24hr');
            const data = await response.json();
            return data;
        } catch (error) {
            console.log('Usando datos simulados por ahora');
            return this.getSimulatedData();
        }
    }

    getSimulatedData() {
        return this.tickers;
    }
}

// Inicializar datos de mercado
const marketData = new MarketData();