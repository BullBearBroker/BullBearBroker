// UI Components para BullBearBroker
class UIController {
    constructor() {
        this.alertCount = 0;
        this.marketData = null;
        this.marketDataUnsubscribers = [];
        this.fallbackNotified = false;
        this.defaultWatchlistSymbols = ['BTC', 'ETH', 'AAPL'];
        this.watchlistSymbols = [...this.defaultWatchlistSymbols];
        this.watchlistState = new Map();
        this.alerts = [];
        this.alertsLoading = false;
        this.alertFetchInProgress = false;
        this.alertFormSubmitting = false;

        this.handleTickersUpdate = this.handleTickersUpdate.bind(this);
        this.handleConnectionUpdate = this.handleConnectionUpdate.bind(this);
        this.handleFallbackEvent = this.handleFallbackEvent.bind(this);
        this.onMarketDataReady = this.onMarketDataReady.bind(this);
        this.handleWatchlistUpdate = this.handleWatchlistUpdate.bind(this);
        this.handleRealtimeAlert = this.handleRealtimeAlert.bind(this);
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.bindMarketData();
        this.renderAlerts();
        if (this.isAuthenticated()) {
            this.refreshAlerts({ silent: true });
        } else {
            this.renderAlertsInfo('Inicia sesión para gestionar tus alertas.');
        }
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
            unsubscribers.push(service.on('watchlist', this.handleWatchlistUpdate));
            unsubscribers.push(service.on('alert', this.handleRealtimeAlert));
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
        this.updateWatchlistFromTickers(topTickers, worstTickers);
    }

    handleWatchlistUpdate(payload = {}) {
        const items = Array.isArray(payload.items) ? payload.items : [];
        if (!items.length && payload.symbol && payload.price) {
            this.renderWatchlistItems([payload]);
            return;
        }

        this.renderWatchlistItems(items);
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

    updateWatchlistFromTickers(topTickers = [], worstTickers = []) {
        const combined = [
            ...(Array.isArray(topTickers) ? topTickers : []),
            ...(Array.isArray(worstTickers) ? worstTickers : [])
        ];

        if (!combined.length) {
            return;
        }

        const watchSet = new Set(this.watchlistSymbols.map(symbol => symbol.toUpperCase()));
        const entries = combined
            .filter(item => item && item.symbol && watchSet.has(String(item.symbol).toUpperCase()))
            .map(item => ({
                symbol: String(item.symbol || '').toUpperCase(),
                price: item.price,
                change: item.change,
                changeValue: typeof item.changeValue === 'number' ? item.changeValue : this.parsePercent(item.change)
            }));

        this.renderWatchlistItems(entries);
    }

    renderWatchlistItems(entries = []) {
        if (!Array.isArray(entries) || !entries.length) {
            return;
        }

        entries.forEach(entry => {
            if (!entry || !entry.symbol) {
                return;
            }

            const upperSymbol = String(entry.symbol).toUpperCase();
            const normalized = {
                symbol: upperSymbol,
                price: entry.price || '--',
                change: entry.change || '--',
                changeValue: typeof entry.changeValue === 'number'
                    ? entry.changeValue
                    : this.parsePercent(entry.change)
            };

            this.watchlistState.set(upperSymbol, normalized);
        });

        this.watchlistSymbols.forEach(symbol => {
            const entry = this.watchlistState.get(symbol) || null;
            const priceElem = document.getElementById(`${symbol.toLowerCase()}Price`);
            const changeElem = document.getElementById(`${symbol.toLowerCase()}Change`);

            if (priceElem) {
                priceElem.textContent = entry?.price || '--';
            }

            if (changeElem) {
                const changeValue = entry?.changeValue ?? this.parsePercent(entry?.change || '0');
                const isNegative = changeValue < 0;
                const isPositive = changeValue > 0;
                const baseClass = 'item-change';
                let modifier = '';
                if (isNegative) {
                    modifier = 'negative';
                } else if (isPositive) {
                    modifier = 'positive';
                }
                changeElem.textContent = entry?.change || '--';
                changeElem.className = modifier ? `${baseClass} ${modifier}` : baseClass;
            }
        });
    }

    parsePercent(value) {
        if (typeof value === 'number') {
            return Number.isFinite(value) ? value : 0;
        }

        if (typeof value === 'string') {
            const cleaned = value.replace(/[^0-9+\-.,]/g, '');
            const normalised = cleaned.replace(/,/g, '');
            const parsed = Number.parseFloat(normalised);
            return Number.isNaN(parsed) ? 0 : parsed;
        }

        return 0;
    }

    isAuthenticated() {
        if (typeof window === 'undefined') {
            return false;
        }

        try {
            return Boolean(localStorage.getItem('bb_token'));
        } catch (error) {
            console.warn('Unable to determine authentication status:', error);
            return false;
        }
    }

    async refreshAlerts(options = {}) {
        const { silent = false } = options;

        if (!this.isAuthenticated()) {
            this.renderAlertsInfo('Inicia sesión para ver tus alertas configuradas.');
            return;
        }

        if (this.alertFetchInProgress) {
            return;
        }

        this.alertFetchInProgress = true;
        this.alertsLoading = true;
        this.renderAlerts();

        try {
            const response = await apiService.listAlerts();
            this.alerts = Array.isArray(response) ? response : [];
            this.renderAlerts();
        } catch (error) {
            const message = this.extractErrorMessage(error, 'No fue posible cargar las alertas.');
            if (error && error.status === 401) {
                this.renderAlertsInfo('Tu sesión ha expirado. Inicia sesión nuevamente para ver tus alertas.');
            } else {
                this.renderAlertsError(message);
            }
            if (!silent) {
                this.showAlert(message, 'error');
            }
        } finally {
            this.alertFetchInProgress = false;
            this.alertsLoading = false;
        }
    }

    renderAlerts(alerts = this.alerts) {
        const container = document.getElementById('alertsList');
        if (!container) {
            return;
        }

        if (this.alertsLoading) {
            container.innerHTML = '<div class="loading-text">Cargando alertas...</div>';
            return;
        }

        const list = Array.isArray(alerts) ? alerts : [];

        if (!list.length) {
            container.innerHTML = '<div class="empty-state">Aún no tienes alertas configuradas.</div>';
            return;
        }

        container.innerHTML = list.map(alert => {
            const asset = this.escapeHtml(alert.asset);
            const conditionSymbol = this.escapeHtml(this.formatAlertCondition(alert.condition));
            const value = this.escapeHtml(this.formatAlertValue(alert.value));
            const createdAt = this.escapeHtml(this.formatAlertTimestamp(alert.created_at));

            return `
                <div class="alert-list-item">
                    <div class="alert-list-header">
                        <span class="alert-asset">${asset}</span>
                        <span class="alert-condition">${conditionSymbol} ${value}</span>
                    </div>
                    <div class="alert-list-meta">Creada: ${createdAt}</div>
                </div>
            `;
        }).join('');
    }

    renderAlertsInfo(message) {
        const container = document.getElementById('alertsList');
        if (!container) {
            return;
        }

        container.innerHTML = `<div class="info-text">${this.escapeHtml(message)}</div>`;
    }

    renderAlertsError(message) {
        const container = document.getElementById('alertsList');
        if (!container) {
            return;
        }

        container.innerHTML = `<div class="error-text">${this.escapeHtml(message)}</div>`;
    }

    formatAlertCondition(condition) {
        const normalized = String(condition || '').toLowerCase();
        const mapping = {
            'above': '≥',
            'below': '≤',
            'equal': '='
        };
        return mapping[normalized] || normalized || '≥';
    }

    formatAlertValue(value) {
        const numeric = Number.parseFloat(value);
        if (Number.isNaN(numeric)) {
            return value;
        }

        return `$${numeric.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    }

    formatAlertTimestamp(timestamp) {
        if (!timestamp) {
            return '--';
        }

        try {
            const date = new Date(timestamp);
            if (Number.isNaN(date.getTime())) {
                return '--';
            }
            return date.toLocaleString();
        } catch (error) {
            console.warn('Unable to format timestamp:', error);
            return '--';
        }
    }

    extractErrorMessage(error, fallback = 'Ocurrió un error inesperado.') {
        if (!error) {
            return fallback;
        }

        const detail = error.payload?.detail || error.payload?.message;
        if (Array.isArray(detail)) {
            return detail.map(item => item.msg || item.detail || '').filter(Boolean).join(' ') || fallback;
        }

        if (typeof detail === 'string' && detail.trim()) {
            return detail;
        }

        if (error.message) {
            return error.message;
        }

        return fallback;
    }

    setAlertFormState(state) {
        const submitButton = document.querySelector('#alertModal .btn-primary');
        if (!submitButton) {
            return;
        }

        if (state === 'loading') {
            this.alertFormSubmitting = true;
            submitButton.disabled = true;
            if (!submitButton.dataset.originalText) {
                submitButton.dataset.originalText = submitButton.innerHTML;
            }
            submitButton.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Guardando...';
        } else {
            this.alertFormSubmitting = false;
            submitButton.disabled = false;
            if (submitButton.dataset.originalText) {
                submitButton.innerHTML = submitButton.dataset.originalText;
            }
        }
    }

    setAlertFormError(message) {
        const errorElement = document.getElementById('alertFormError');
        if (!errorElement) {
            return;
        }

        if (message) {
            errorElement.textContent = message;
            errorElement.style.display = 'block';
        } else {
            errorElement.textContent = '';
            errorElement.style.display = 'none';
        }
    }

    showAlertFormError(message) {
        this.setAlertFormError(message);
        if (message) {
            this.showAlert(message, 'error');
        }
    }

    resetAlertForm() {
        const symbolInput = document.getElementById('alertSymbol');
        const valueInput = document.getElementById('alertValue');
        const conditionSelect = document.getElementById('alertCondition');

        if (symbolInput) {
            symbolInput.value = '';
        }
        if (valueInput) {
            valueInput.value = '';
        }
        if (conditionSelect) {
            conditionSelect.value = 'above';
        }

        this.setAlertFormError('');
    }

    async createAlert(alertInput, options = {}) {
        const { closeModalOnSuccess = true } = options;

        if (!this.isAuthenticated()) {
            this.showAlert('Inicia sesión para crear alertas personalizadas.', 'warning');
            return;
        }

        if (this.alertFormSubmitting) {
            return;
        }

        const payload = {
            asset: String(alertInput.symbol || '').toUpperCase(),
            condition: alertInput.condition || 'above',
            value: Number(alertInput.value)
        };

        this.setAlertFormError('');
        this.setAlertFormState('loading');

        try {
            await apiService.createAlert(payload);
            this.showAlert(`Alerta configurada para ${payload.asset} (${this.formatAlertCondition(payload.condition)} ${this.formatAlertValue(payload.value)})`, 'success');
            await this.refreshAlerts({ silent: true });
            if (closeModalOnSuccess) {
                this.closeModal('alertModal');
            }
            this.resetAlertForm();
        } catch (error) {
            const message = this.extractErrorMessage(error, 'No fue posible crear la alerta.');
            this.setAlertFormError(message);
            this.showAlert(message, 'error');
        } finally {
            this.setAlertFormState('idle');
        }
    }

    handleRealtimeAlert(payload = {}) {
        const symbol = payload.symbol || payload.asset || 'Activo';
        const price = typeof payload.price === 'number'
            ? `$${payload.price.toFixed(2)}`
            : payload.price || '--';
        const target = payload.target || payload.value;
        const comparison = payload.comparison || payload.condition;
        const condition = comparison ? this.formatAlertCondition(comparison) : '≥';
        const message = payload.message
            || `Alerta activada para ${symbol}: precio ${price} ${condition} ${this.formatAlertValue(target)}`;

        this.showAlert(message, 'warning');
        this.refreshAlerts({ silent: true });
    }

    escapeHtml(value) {
        if (value === null || value === undefined) {
            return '';
        }

        return String(value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    showAlert(message, type = 'info') {
        const alertContainer = document.getElementById('alertContainer');
        if (!alertContainer) return;

        const alertId = `alert-${Date.now()}-${this.alertCount++}`;

        const safeMessage = this.escapeHtml(message);

        const alert = document.createElement('div');
        alert.id = alertId;
        alert.className = `alert alert-${type}`;
        alert.innerHTML = `
            <i class="fas ${this.getAlertIcon(type)}"></i>
            <div>${safeMessage}</div>
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
        const trimmedSymbol = String(symbol || '').trim();
        const numericValue = Number.parseFloat(value);

        if (!trimmedSymbol) {
            ui.showAlertFormError('El símbolo del activo es obligatorio.');
            return;
        }

        if (Number.isNaN(numericValue)) {
            ui.showAlertFormError('Ingresa un valor numérico válido para la alerta.');
            return;
        }

        if (numericValue <= 0) {
            ui.showAlertFormError('El valor objetivo debe ser mayor que cero.');
            return;
        }

        ui.createAlert({
            symbol: trimmedSymbol,
            condition: condition || 'above',
            value: numericValue
        });
    });
}

function showMarketOverview() {
    if (typeof askQuestion === 'function') {
        askQuestion('Muéstrame una visión general del mercado actual con análisis técnico');
    }
}

function showAlertModal() {
    withUIController((ui) => {
        ui.setAlertFormError('');
        ui.showModal('alertModal');
    });
}

// Inicializar UI cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', function() {
    window.uiController = new UIController();
    
    // Mostrar alerta de bienvenida
    setTimeout(() => {
        window.uiController.showAlert('Sistema de alertas configurado correctamente', 'success');
    }, 2000);
});
