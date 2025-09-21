// UI Components para BullBearBroker
class UIController {
    constructor() {
        this.alertCount = 0;
        this.marketData = null;
        this.marketDataUnsubscribers = [];
        this.fallbackNotified = false;

        this.handleTickersUpdate = this.handleTickersUpdate.bind(this);
        this.handleConnectionUpdate = this.handleConnectionUpdate.bind(this);
        this.handleFallbackEvent = this.handleFallbackEvent.bind(this);
        this.onMarketDataReady = this.onMarketDataReady.bind(this);
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.bindMarketData();
    }

    setupEventListeners() {
        // Auto-resize textarea
        const textarea = document.getElementById('messageInput');
        if (textarea) {
            textarea.addEventListener('input', function() {
                this.style.height = 'auto';
                this.style.height = (this.scrollHeight) + 'px';
            });

            // Enter para enviar mensaje
            textarea.addEventListener('keypress', function(e) {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    if (typeof sendMessage === 'function') {
                        sendMessage();
                    }
                }
            });
        }
    }

    bindMarketData() {
        if (typeof window === 'undefined') return;

        this.attachMarketData(window.marketData);

        window.addEventListener('marketData:ready', this.onMarketDataReady);
        window.addEventListener('marketData:service-created', this.onMarketDataReady);
    }

    onMarketDataReady(event) {
        const service = event?.detail?.service || (typeof window !== 'undefined' ? window.marketData : null);
        this.attachMarketData(service);
    }

    attachMarketData(service) {
        if (!service || this.marketData === service) {
            return;
        }

        this.detachMarketData();
        this.marketData = service;

        const unsubscribers = [];

        if (typeof service.on === 'function') {
            unsubscribers.push(service.on('tickers', this.handleTickersUpdate));
            unsubscribers.push(service.on('connection', this.handleConnectionUpdate));
            unsubscribers.push(service.on('fallback', this.handleFallbackEvent));
        }

        this.marketDataUnsubscribers = unsubscribers.filter(Boolean);

        if (typeof service.getTickerSnapshot === 'function') {
            const snapshot = service.getTickerSnapshot();
            if (snapshot && (snapshot.top.length || snapshot.worst.length)) {
                this.handleTickersUpdate({ ...snapshot, source: 'snapshot' });
            }
        }

        if (service.connectionStatus) {
            this.handleConnectionUpdate({ status: service.connectionStatus });
        }
    }

    detachMarketData() {
        this.marketDataUnsubscribers.forEach(unsubscribe => {
            try {
                if (typeof unsubscribe === 'function') {
                    unsubscribe();
                }
            } catch (error) {
                console.error('Error detaching market data listener:', error);
            }
        });
        this.marketDataUnsubscribers = [];
        this.marketData = null;
    }

    handleTickersUpdate(update = {}) {
        const topTickers = Array.isArray(update.top)
            ? update.top
            : Array.isArray(update.top_performers) ? update.top_performers : [];
        const worstTickers = Array.isArray(update.worst)
            ? update.worst
            : Array.isArray(update.worst_performers) ? update.worst_performers : [];

        this.updateMarketTickers({ top: topTickers, worst: worstTickers });
        this.updateHeaderTickers(topTickers);
        this.updateWatchlist(topTickers, worstTickers);
    }

    handleConnectionUpdate(detail = {}) {
        const status = detail.status || 'disconnected';
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
            if (status === 'connected') {
                statusTextElement.textContent = 'Conectado';
            } else if (status === 'static') {
                statusTextElement.textContent = 'Modo estático';
            } else {
                statusTextElement.textContent = 'Desconectado';
            }
        }

        if (status === 'connected') {
            this.fallbackNotified = false;
        }
    }

    handleFallbackEvent(detail = {}) {
        const reason = detail.reason || 'fallback';
        this.handleConnectionUpdate({ status: 'static', reason });

        if (!this.fallbackNotified) {
            this.showAlert('Mostrando datos estáticos mientras restablecemos la conexión en tiempo real.', 'warning');
            this.fallbackNotified = true;
        }
    }

    updateMarketTickers(data = {}) {
        const topList = Array.isArray(data.top)
            ? data.top
            : Array.isArray(data.top_performers) ? data.top_performers : [];
        const worstList = Array.isArray(data.worst)
            ? data.worst
            : Array.isArray(data.worst_performers) ? data.worst_performers : [];

        // Actualizar top performers
        const topTickers = document.getElementById('topTickers');
        if (topTickers) {
            topTickers.innerHTML = topList.slice(0, 5).map(ticker => `
                <div class="ticker-item">
                    <span class="ticker-symbol">${ticker.symbol}</span>
                    <span class="ticker-price">${ticker.price}</span>
                    <span class="ticker-price ${ticker.change.includes('-') ? 'negative' : 'positive'}">${ticker.change}</span>
                </div>
            `).join('');
        }

        // Actualizar worst performers
        const worstTickers = document.getElementById('worstTickers');
        if (worstTickers) {
            worstTickers.innerHTML = worstList.slice(0, 5).map(ticker => `
                <div class="ticker-item">
                    <span class="ticker-symbol">${ticker.symbol}</span>
                    <span class="ticker-price">${ticker.price}</span>
                    <span class="ticker-price ${ticker.change.includes('-') ? 'negative' : 'positive'}">${ticker.change}</span>
                </div>
            `).join('');
        }
    }

    updateHeaderTickers(topTickers = []) {
        const header = document.querySelector('.market-ticker');
        if (!header || !Array.isArray(topTickers) || !topTickers.length) {
            return;
        }

        header.innerHTML = topTickers.slice(0, 3).map(item => `
            <div class="ticker-item">
                <span class="ticker-name">${item.symbol}</span>
                <span class="ticker-price">${item.price}</span>
                <span class="ticker-change ${item.change.includes('-') ? 'negative' : 'positive'}">${item.change}</span>
            </div>
        `).join('');
    }

    updateWatchlist(topTickers = [], worstTickers = []) {
        const combined = [
            ...(Array.isArray(topTickers) ? topTickers : []),
            ...(Array.isArray(worstTickers) ? worstTickers : [])
        ];

        const symbols = ['btc', 'eth', 'aapl'];
        symbols.forEach(symbol => {
            const priceElem = document.getElementById(`${symbol}Price`);
            const changeElem = document.getElementById(`${symbol}Change`);

            if (!priceElem || !changeElem) return;

            const ticker = combined.find(t => t.symbol && t.symbol.toLowerCase() === symbol);

            if (ticker) {
                priceElem.textContent = ticker.price;
                changeElem.textContent = ticker.change;
                changeElem.className = `item-change ${ticker.change.includes('-') ? 'negative' : 'positive'}`;
            }
        });
    }

    showAlert(message, type = 'info') {
        const alertContainer = document.getElementById('alertContainer');
        if (!alertContainer) return;

        const alertId = `alert-${Date.now()}-${this.alertCount++}`;
        
        const alert = document.createElement('div');
        alert.id = alertId;
        alert.className = `alert alert-${type}`;
        alert.innerHTML = `
            <i class="fas ${this.getAlertIcon(type)}"></i>
            <div>${message}</div>
            <button class="alert-close" onclick="document.getElementById('${alertId}').remove()">
                <i class="fas fa-times"></i>
            </button>
        `;
        
        alertContainer.appendChild(alert);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (document.getElementById(alertId)) {
                document.getElementById(alertId).remove();
            }
        }, 5000);
    }

    getAlertIcon(type) {
        const icons = {
            'success': 'fa-check-circle',
            'warning': 'fa-exclamation-triangle',
            'error': 'fa-exclamation-circle',
            'info': 'fa-info-circle'
        };
        return icons[type] || 'fa-info-circle';
    }

    showModal(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.style.display = 'block';
        }
    }

    closeModal(modalId) {
        const modal = document.getElementById(modalId);
        if (modal) {
            modal.style.display = 'none';
        }
    }
}

// Funciones globales para uso en HTML
function withUIController(callback) {
    const ui = typeof window !== 'undefined' ? window.uiController : null;
    if (!ui) {
        console.warn('UIController no está inicializado todavía.');
        return;
    }

    if (typeof callback === 'function') {
        callback(ui);
    }
}

function showAddToWatchlist() {
    withUIController((ui) => {
        ui.showModal('alertModal');
        ui.showAlert('Funcionalidad de watchlist en desarrollo', 'info');
    });
}

function closeModal(modalId) {
    withUIController((ui) => ui.closeModal(modalId));
}

function saveAlert() {
    const symbol = document.getElementById('alertSymbol')?.value;
    const condition = document.getElementById('alertCondition')?.value;
    const value = document.getElementById('alertValue')?.value;

    withUIController((ui) => {
        if (symbol && value) {
            ui.showAlert(`Alerta configurada para ${symbol} (${condition} ${value})`, 'success');
            ui.closeModal('alertModal');

            // Limpiar formulario
            const symbolInput = document.getElementById('alertSymbol');
            const valueInput = document.getElementById('alertValue');
            if (symbolInput) symbolInput.value = '';
            if (valueInput) valueInput.value = '';
        } else {
            ui.showAlert('Por favor, completa todos los campos', 'error');
        }
    });
}

function showMarketOverview() {
    if (typeof askQuestion === 'function') {
        askQuestion('Muéstrame una visión general del mercado actual con análisis técnico');
    }
}

function showAlertModal() {
    withUIController((ui) => ui.showModal('alertModal'));
}

// Inicializar UI cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', function() {
    window.uiController = new UIController();
    
    // Mostrar alerta de bienvenida
    setTimeout(() => {
        window.uiController.showAlert('Sistema de alertas configurado correctamente', 'success');
    }, 2000);
});
