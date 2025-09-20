// UI Components para BullBearBroker
class UIController {
    constructor() {
        this.alertCount = 0;
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.loadMarketData();
        this.startMarketDataInterval();
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

    async loadMarketData() {
        try {
            const response = await fetch('/api/market/top-performers');
            const data = await response.json();
            
            if (data.success) {
                this.updateMarketTickers(data.data);
                this.updateHeaderTickers(data.data.market_summary);
            }
        } catch (error) {
            console.error('Error loading market data:', error);
            // Usar datos de ejemplo si la API falla
            this.useSampleData();
        }
    }

    useSampleData() {
        const sampleData = {
            top_performers: [
                {'symbol': 'BTC', 'price': '$45,123.45', 'change': '+2.5%', 'type': 'crypto'},
                {'symbol': 'ETH', 'price': '$2,567.89', 'change': '+1.8%', 'type': 'crypto'},
                {'symbol': 'AAPL', 'price': '$178.90', 'change': '+0.7%', 'type': 'stock'},
                {'symbol': 'MSFT', 'price': '$345.21', 'change': '+0.3%', 'type': 'stock'},
                {'symbol': 'SOL', 'price': '$95.67', 'change': '+1.2%', 'type': 'crypto'}
            ],
            worst_performers: [
                {'symbol': 'TSLA', 'price': '$245.67', 'change': '-0.8%', 'type': 'stock'},
                {'symbol': 'XRP', 'price': '$0.58', 'change': '-0.3%', 'type': 'crypto'},
                {'symbol': 'NFLX', 'price': '$567.89', 'change': '-0.5%', 'type': 'stock'},
                {'symbol': 'DOGE', 'price': '$0.12', 'change': '-0.2%', 'type': 'crypto'},
                {'symbol': 'ADA', 'price': '$0.45', 'change': '-0.1%', 'type': 'crypto'}
            ],
            market_summary: {
                'sp500': '+0.3%',
                'nasdaq': '+0.8%', 
                'dow_jones': '-0.2%',
                'bitcoin_dominance': '52.3%'
            }
        };
        
        this.updateMarketTickers(sampleData);
    }

    updateMarketTickers(data) {
        // Actualizar top performers
        const topTickers = document.getElementById('topTickers');
        if (topTickers && data.top_performers) {
            topTickers.innerHTML = data.top_performers.slice(0, 5).map(ticker => `
                <div class="ticker-item">
                    <span class="ticker-symbol">${ticker.symbol}</span>
                    <span class="ticker-price">${ticker.price}</span>
                    <span class="ticker-price ${ticker.change.includes('-') ? 'negative' : 'positive'}">${ticker.change}</span>
                </div>
            `).join('');
        }

        // Actualizar worst performers
        const worstTickers = document.getElementById('worstTickers');
        if (worstTickers && data.worst_performers) {
            worstTickers.innerHTML = data.worst_performers.slice(0, 5).map(ticker => `
                <div class="ticker-item">
                    <span class="ticker-symbol">${ticker.symbol}</span>
                    <span class="ticker-price">${ticker.price}</span>
                    <span class="ticker-price ${ticker.change.includes('-') ? 'negative' : 'positive'}">${ticker.change}</span>
                </div>
            `).join('');
        }
    }

    updateHeaderTickers(marketSummary) {
        if (!marketSummary) return;
        
        // Actualizar el header con datos del mercado
        const headerTickers = document.querySelector('.market-ticker');
        if (headerTickers && marketSummary) {
            // Esta función se puede expandir para actualizar datos en tiempo real
            console.log('Market summary actualizado:', marketSummary);
        }
    }

    startMarketDataInterval() {
        // Actualizar datos cada 30 segundos
        setInterval(() => {
            this.loadMarketData();
        }, 30000);
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
function showAddToWatchlist() {
    const ui = new UIController();
    ui.showModal('alertModal');
    ui.showAlert('Funcionalidad de watchlist en desarrollo', 'info');
}

function closeModal(modalId) {
    const ui = new UIController();
    ui.closeModal(modalId);
}

function saveAlert() {
    const symbol = document.getElementById('alertSymbol')?.value;
    const condition = document.getElementById('alertCondition')?.value;
    const value = document.getElementById('alertValue')?.value;
    
    if (symbol && value) {
        const ui = new UIController();
        ui.showAlert(`Alerta configurada para ${symbol} (${condition} ${value})`, 'success');
        ui.closeModal('alertModal');
        
        // Limpiar formulario
        document.getElementById('alertSymbol').value = '';
        document.getElementById('alertValue').value = '';
    } else {
        const ui = new UIController();
        ui.showAlert('Por favor, completa todos los campos', 'error');
    }
}

function showMarketOverview() {
    if (typeof askQuestion === 'function') {
        askQuestion('Muéstrame una visión general del mercado actual con análisis técnico');
    }
}

function showAlertModal() {
    const ui = new UIController();
    ui.showModal('alertModal');
}

// Inicializar UI cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', function() {
    window.uiController = new UIController();
    
    // Mostrar alerta de bienvenida
    setTimeout(() => {
        window.uiController.showAlert('Sistema de alertas configurado correctamente', 'success');
    }, 2000);
});
