// emergency-fix.js - Solución de emergencia para problemas de conexión
console.log('🆘 Activando solución de emergencia...');

// 1. Detener TODOS los intervals y timeouts
function stopAllIntervals() {
    const maxId = setTimeout(() => {}, 0);
    for (let i = 0; i < maxId; i++) {
        clearInterval(i);
        clearTimeout(i);
    }
    console.log('🛑 Todos los intervals detenidos');
}

// 2. Sobrescribir fetch para redirigir correctamente
const originalFetch = window.fetch;
window.fetch = function(url, options) {
    // Redirigir solicitudes de API al backend correcto
    if (typeof url === 'string') {
        // Si es una ruta de API pero no tiene el host correcto
        if (url.includes('/api/') && !url.includes('localhost:8000')) {
            const newUrl = `http://localhost:8000${url.startsWith('/') ? '' : '/'}${url}`;
            console.log('🔁 Redirigiendo solicitud:', url, '→', newUrl);
            return originalFetch(newUrl, options);
        }
        
        // Si es una ruta relativa que debería ser API
        if (url.startsWith('/market/') || url.startsWith('market/')) {
            const newUrl = `http://localhost:8000/api/${url.replace(/^\//, '')}`;
            console.log('🔁 Redirigiendo market request:', url, '→', newUrl);
            return originalFetch(newUrl, options);
        }
    }
    
    return originalFetch(url, options);
};

// 3. Cargar datos estáticos inmediatamente
function loadStaticData() {
    console.log('📊 Cargando datos estáticos de emergencia...');
    const staticData = {
        top: [
            {symbol: 'BTC', price: '$45,123', change: '+2.5%'},
            {symbol: 'ETH', price: '$2,567', change: '+1.8%'},
            {symbol: 'AAPL', price: '$178', change: '+0.7%'}
        ],
        worst: [
            {symbol: 'TSLA', price: '$245', change: '-0.8%'},
            {symbol: 'XRP', price: '$0.58', change: '-0.3%'}
        ]
    };
    
    // Actualizar UI
    const updateUI = (id, data) => {
        const el = document.getElementById(id);
        if (el) {
            el.innerHTML = data.map(item => `
                <div class="ticker-item">
                    <span class="ticker-symbol">${item.symbol}</span>
                    <span class="ticker-price">${item.price}</span>
                    <span class="ticker-change ${item.change.includes('-') ? 'negative' : 'positive'}">
                        ${item.change}
                    </span>
                </div>
            `).join('');
        }
    };
    
    updateUI('topTickers', staticData.top);
    updateUI('worstTickers', staticData.worst);
    
    // Actualizar watchlist
    const symbols = ['btc', 'eth', 'aapl'];
    symbols.forEach(symbol => {
        const priceElem = document.getElementById(`${symbol}Price`);
        const changeElem = document.getElementById(`${symbol}Change`);
        const ticker = [...staticData.top, ...staticData.worst]
            .find(t => t.symbol.toLowerCase() === symbol);
        
        if (priceElem && changeElem && ticker) {
            priceElem.textContent = ticker.price;
            changeElem.textContent = ticker.change;
            changeElem.className = `item-change ${ticker.change.includes('-') ? 'negative' : 'positive'}`;
        }
    });
    
    // Actualizar status
    const statusEl = document.getElementById('connectionStatus');
    if (statusEl) {
        statusEl.innerHTML = '<i class="fas fa-check-circle"></i> Modo emergencia activado';
        statusEl.className = 'connection-status static';
    }
    
    const statusTextEl = document.getElementById('connectionStatusText');
    if (statusTextEl) {
        statusTextEl.textContent = 'Modo estático';
    }
}

// Ejecutar solución de emergencia
stopAllIntervals();
loadStaticData();

console.log('✅ Solución de emergencia activada');