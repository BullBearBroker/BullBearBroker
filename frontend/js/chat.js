class ChatManager {
    constructor() {
        this.messages = [];
        this.isWaitingForResponse = false;
        this.retryCount = 0;
        this.maxRetries = 3;
    }

    init() {
        this.loadFromLocalStorage();
        this.setupEventListeners();
        this.renderMessages();
        
        // Mensaje de bienvenida si no hay mensajes
        if (this.messages.length === 0) {
            this.addWelcomeMessage();
        }
        
        console.log('✅ ChatManager inicializado correctamente');
    }

    addWelcomeMessage() {
        const welcomeMessage = {
            id: Date.now(),
            text: '¡Hola! Soy tu asistente especializado en mercados financieros. Conectado a **datos en tiempo real** de Binance y mercados globales. ¿En qué te puedo ayudar hoy?',
            sender: 'ai',
            timestamp: new Date(),
            type: 'text'
        };
        this.messages.push(welcomeMessage);
        this.saveToLocalStorage();
        this.renderMessages();
    }

    setupEventListeners() {
        const input = document.getElementById('messageInput');
        if (!input) {
            console.warn('⚠️ Input de mensaje no encontrado');
            return;
        }
        
        input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        input.addEventListener('input', this.autoResize.bind(this));
        
        // Asegurar que el botón de enviar también funciona
        const sendButton = document.querySelector('.send-button');
        if (sendButton) {
            sendButton.addEventListener('click', () => this.sendMessage());
        }
    }

    autoResize() {
        const textarea = document.getElementById('messageInput');
        if (!textarea) return;
        
        textarea.style.height = 'auto';
        textarea.style.height = Math.min(textarea.scrollHeight, 150) + 'px';
    }

    async sendMessage() {
        const input = document.getElementById('messageInput');
        if (!input) return;
        
        const message = input.value.trim();

        if (!message || this.isWaitingForResponse) return;

        this.addMessage(message, 'user');
        input.value = '';
        this.autoResize();
        this.retryCount = 0;

        // Mostrar indicador de typing
        this.showTypingIndicator();

        try {
            // Intentar obtener respuesta del backend
            const response = await this.fetchAIResponse(message);
            this.removeTypingIndicator();
            this.addMessage(response, 'ai');
        } catch (error) {
            console.log('Error con API, usando respuesta local:', error);
            // Fallback a respuesta local
            this.removeTypingIndicator();
            const localResponse = this.generateAIResponse(message);
            this.addMessage(localResponse, 'ai');
        }
    }

    async fetchAIResponse(message) {
        try {
            const response = await fetch('http://localhost:8000/api/chat/message', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ message })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            
            if (data.success && data.response) {
                return data.response;
            } else {
                throw new Error('Respuesta inválida del servidor');
            }
        } catch (error) {
            console.error('Error fetching AI response:', error);
            
            // Reintentar si es un error de red y no hemos excedido los intentos
            if (error.name === 'TypeError' && this.retryCount < this.maxRetries) {
                this.retryCount++;
                console.log(`🔄 Reintentando (${this.retryCount}/${this.maxRetries})...`);
                await new Promise(resolve => setTimeout(resolve, 1000 * this.retryCount));
                return this.fetchAIResponse(message);
            }
            
            throw error;
        }
    }

    showTypingIndicator() {
        this.isWaitingForResponse = true;
        const container = document.getElementById('chatMessages');
        if (!container) return;
        
        const typingDiv = document.createElement('div');
        typingDiv.id = 'typing-indicator';
        typingDiv.className = 'message ai-message';
        
        typingDiv.innerHTML = `
            <div class="message-icon">🤖</div>
            <div class="message-content">
                <div class="message-sender">BullBearBroker AI</div>
                <div class="message-text">
                    <div class="typing-indicator">
                        <span></span>
                        <span></span>
                        <span></span>
                    </div>
                </div>
            </div>
        `;
        
        container.appendChild(typingDiv);
        this.scrollToBottom();
    }

    removeTypingIndicator() {
        this.isWaitingForResponse = false;
        const typingIndicator = document.getElementById('typing-indicator');
        if (typingIndicator) {
            typingIndicator.remove();
        }
    }

    addMessage(text, sender) {
        const message = {
            id: Date.now(),
            text,
            sender,
            timestamp: new Date(),
            type: 'text'
        };

        this.messages.push(message);
        this.renderMessage(message);
        this.saveToLocalStorage();
        this.scrollToBottom();
    }

    renderMessages() {
        const container = document.getElementById('chatMessages');
        if (!container) return;

        container.innerHTML = '';

        this.messages.forEach(message => {
            this.renderMessage(message);
        });

        this.scrollToBottom();
    }

    renderMessage(message) {
        const container = document.getElementById('chatMessages');
        if (!container) return;
        
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${message.sender}-message`;
        messageDiv.dataset.messageId = message.id;

        messageDiv.innerHTML = `
            <div class="message-icon">${message.sender === 'user' ? '👤' : '🤖'}</div>
            <div class="message-content">
                <div class="message-sender">${message.sender === 'user' ? 'Tú' : 'BullBearBroker AI'}</div>
                <div class="message-text">${this.formatMessage(message.text)}</div>
                <div class="message-time">${this.formatTime(message.timestamp)}</div>
            </div>
        `;

        container.appendChild(messageDiv);
    }

    formatMessage(text) {
        if (!text) return '';
        
        let formattedText = String(text);
        
        // Convertir URLs en links (mejorado)
        formattedText = formattedText.replace(
            /(https?:\/\/[^\s<]+[^<.,:;"')\]\s])/g, 
            '<a href="$1" target="_blank" style="color: #1a73e8; text-decoration: underline;">$1</a>'
        );
        
        // Destacar precios (mejorado para diferentes formatos)
        formattedText = formattedText.replace(
            /\$(\d{1,3}(?:,\d{3})*(?:\.\d{2})?|\d+\.\d{2})/g, 
            '<span class="highlight-price">$$1</span>'
        );
        
        // Destacar porcentajes (mejorado)
        formattedText = formattedText.replace(
            /([+-]?\d+\.?\d*%)/g, 
            (match) => {
                const isPositive = !match.includes('-');
                return `<span class="highlight-percent ${isPositive ? 'positive' : 'negative'}">${match}</span>`;
            }
        );
        
        // Destacar símbolos de tickers (mejorado)
        formattedText = formattedText.replace(
            /\b([A-Z]{1,5})\b/g, 
            (match) => {
                // Solo destacar si parece un símbolo (2-5 letras mayúsculas)
                if (match.length >= 2 && match.length <= 5 && match === match.toUpperCase()) {
                    return `<span class="highlight-symbol">${match}</span>`;
                }
                return match;
            }
        );
        
        // Negrita (Markdown) - mejorado
        formattedText = formattedText.replace(
            /\*\*([^*]+)\*\*/g, 
            '<strong>$1</strong>'
        );
        
        // Cursiva (Markdown)
        formattedText = formattedText.replace(
            /\*([^*]+)\*/g, 
            '<em>$1</em>'
        );
        
        // Listas
        formattedText = formattedText.replace(/^•\s+(.+)$/gm, '<li>$1</li>');
        formattedText = formattedText.replace(/(<li>.*<\/li>)/gs, '<ul>$1</ul>');
        
        // Saltos de línea
        formattedText = formattedText.replace(/\n/g, '<br>');
        
        return formattedText;
    }

    formatTime(timestamp) {
        try {
            const date = new Date(timestamp);
            const now = new Date();
            const diffMs = now - date;
            const diffMins = Math.floor(diffMs / 60000);
            const diffHours = Math.floor(diffMs / 3600000);
            
            if (diffMins < 1) return 'Ahora mismo';
            if (diffMins < 60) return `Hace ${diffMins} min`;
            if (diffHours < 24) return `Hace ${diffHours} h`;
            
            return date.toLocaleTimeString('es-ES', {
                hour: '2-digit',
                minute: '2-digit',
                day: '2-digit',
                month: '2-digit'
            });
        } catch (e) {
            return '--:--';
        }
    }

    scrollToBottom() {
        const container = document.getElementById('chatMessages');
        if (!container) return;
        
        // Scroll suave al final
        container.scrollTo({
            top: container.scrollHeight,
            behavior: 'smooth'
        });
    }

    generateAIResponse(userMessage) {
        const lowerMessage = userMessage.toLowerCase();
        
        // Verificar si hay datos de mercado disponibles
        if (window.marketData && window.marketData.tickers) {
            // Intentar proporcionar datos reales si están disponibles
            const pricePatterns = [
                /precio de (\w+)/i,
                /valor de (\w+)/i,
                /cuánto vale (\w+)/i,
                /price of (\w+)/i,
                /cotización de (\w+)/i,
                /cómo está (\w+)/i
            ];
        
            for (const pattern of pricePatterns) {
                const match = userMessage.match(pattern);
                if (match) {
                    const symbol = match[1].toUpperCase();
                    return this.generatePriceResponse(symbol);
                }
            }
        }
        
        // Respuestas predefinidas mejoradas
        const responses = {
            'bitcoin': '📈 **Bitcoin** está mostrando fortaleza en el mercado. Los soportes clave se mantienen en $40,000 con resistencia en $45,000. El volumen ha aumentado un 15% en las últimas 24 horas. Recomendación: estrategia de acumulación en dips con stop-loss en $38,000.',
            'ethereum': '🔷 **Ethereum** se encuentra consolidando en la zona de $2,500. Los próximos upgrades de la red podrían impulsar el precio. Los indicadores técnicos muestran un patrón alcista a medio plazo. Volumen estable con dominancia del 18.5% en el mercado crypto.',
            'acciones': '💼 **Estrategia de acciones**: Recomiendo diversificación en:\n• Tecnología: AAPL, MSFT, NVDA\n• Energías renovables: ENPH, FSLR\n• Healthcare: JNJ, PFE, MRNA\n\nAllocation sugerida: 60% stocks, 20% crypto, 20% cash para oportunidades.',
            'estrategia': '🎯 **Estrategias de inversión**:\n\n• Conservadora: 40% bonds, 40% blue chips, 20% gold\n• Moderada: 50% stocks, 30% ETFs, 20% crypto\n• Agresiva: 50% growth stocks, 30% crypto, 20% emerging markets\n\nRebalancear trimestralmente según condiciones de mercado.',
            'mercado': '🌍 **Panorama global**:\n• S&P 500: +0.3% (4,890.15)\n• NASDAQ: +0.8% (15,234.67)  \n• DOW: -0.2% (38,456.12)\n• Bitcoin: +2.5% ($45,123.45)\n\nRecomiendo dollar-cost averaging y diversificación across asset classes.',
            'forex': '💱 **Mercado Forex**:\n• EUR/USD: 1.0850 (+0.3%)\n• GBP/USD: 1.2450 (-0.2%)\n• USD/JPY: 150.20 (+0.5%)\n• USD/MXN: 17.25 (-0.1%)\n\nAtención a las próximas reuniones del Fed para posibles cambios en tasas de interés.',
            'noticias': '📰 **Noticias del mercado**: Sigue estos eventos clave:\n• Reuniones del Federal Reserve\n• Reportes de earnings trimestrales\n• Datos de inflación (CPI, PPI)\n• Indicadores económicos (GDP, empleo)\n\nFuentes recomendadas: Bloomberg, Reuters, Financial Times.',
            'portfolio': '📊 **Construcción de portfolio**:\n1. Define tu perfil de riesgo (conservador/moderado/agresivo)\n2. Diversifica across asset classes y sectores\n3. Considera tu horizonte temporal de inversión\n4. Establece porcentajes de allocation\n5. Rebalancea regularmente (trimestral/anual)',
            'riesgo': '⚖️ **Gestión de riesgo**:\n• Nunca inviertas más del 5% en un solo activo\n• Utiliza órdenes stop-loss para proteger capital\n• Mantén entre 10-20% en cash para oportunidades\n• Diversifica across diferentes sectores y geografías\n• Revisa tu portfolio regularmente',
            'gracias': '¡De nada! 😊 Estoy aquí para ayudarte con tus decisiones de inversión. ¿Hay algo más en lo que te pueda asistir hoy?',
            'hola': '¡Hola! 👋 Soy BullBearBroker, tu asistente de mercados financieros. Puedo ayudarte con:\n• 📊 Análisis de mercado\n• 💰 Estrategias de inversión\n• 📈 Seguimiento de activos\n• ⚠️ Gestión de riesgo\n\n¿En qué te puedo ayudar?'
        };
    
        for (const [keyword, response] of Object.entries(responses)) {
            if (lowerMessage.includes(keyword)) {
                return response;
            }
        }
    
        return `🤖 **BullBearBroker Analysis**\n\nHe analizado tu consulta sobre "${userMessage}". Como asistente financiero especializado, te recomiendo:\n\n📊 **Diversificación**: Spread investments across stocks, crypto, bonds, and real estate\n⏰ **Horizonte Temporal**: Align investments with your time horizon and goals  \n📉 **Gestión de Riesgo**: Never invest more than you can afford to lose\n🔍 **Due Diligence**: Research thoroughly before any investment\n💡 **Educación Continua**: Stay informed about market trends and developments\n\n**¿En qué aspecto te gustaría que profundice?**\n- 📈 Análisis técnico de algún activo\n- 💰 Estrategias de inversión específicas  \n- 📰 Impacto de noticias recientes\n- 🎯 Recomendaciones de portfolio`;
    }
    
    generatePriceResponse(symbol) {
        // Intentar obtener datos reales si están disponibles
        if (window.marketData && typeof window.marketData.getPrice === 'function') {
            return `📊 Consultando datos en tiempo real para **${symbol}**...\n\nMientras tanto, te recomiendo:\n• Verificar el orderbook para liquidez\n• Analizar tendencias de volumen\n• Considerar soportes y resistencias clave\n• Revisar noticias recientes del activo`;
        }
        
        return `📈 He detectado que preguntas por el precio de **${symbol}**. Nuestro sistema de datos en tiempo real se está actualizando. Pronto tendrás acceso a:\n\n• Precios spot actualizados\n• Gráficos en tiempo real\n• Análisis técnico automático\n• Alertas de precio personalizadas\n\nMientras tanto, ¿te gustaría que analice alguna estrategia específica para ${symbol}?`;
    }
    
    saveToLocalStorage() {
        try {
            // Limitar a los últimos 50 mensajes para no exceder almacenamiento
            const recentMessages = this.messages.slice(-50);
            localStorage.setItem('chatMessages', JSON.stringify(recentMessages));
        } catch (error) {
            console.warn('Error guardando en localStorage:', error);
        }
    }
    
    loadFromLocalStorage() {
        try {
            const saved = localStorage.getItem('chatMessages');
            if (saved) {
                this.messages = JSON.parse(saved);
            }
        } catch (error) {
            console.warn('Error cargando desde localStorage:', error);
            this.messages = [];
        }
    }
    
    clearChat() {
        if (confirm('¿Estás seguro de que quieres limpiar toda la conversación?')) {
            this.messages = [];
            this.saveToLocalStorage();
            this.renderMessages();
            
            // Mensaje inicial del bot
            this.addWelcomeMessage();
            
            // Mostrar notificación
            this.showAlert('Chat limpiado correctamente', 'success');
        }
    }
    
    exportChat() {
        try {
            const chatText = this.messages.map(msg => 
                `${msg.sender === 'user' ? 'Tú' : 'AI'} (${this.formatTime(msg.timestamp)}): ${msg.text.replace(/<[^>]*>/g, '')}`
            ).join('\n\n');
        
            const blob = new Blob([chatText], { type: 'text/plain' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `bullbearbroker-chat-${new Date().toISOString().split('T')[0]}.txt`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            
            this.showAlert('Chat exportado correctamente', 'success');
        } catch (error) {
            console.error('Error exportando chat:', error);
            this.showAlert('Error al exportar el chat', 'error');
        }
    }
    
    showAlert(message, type = 'info') {
        // Intentar usar el sistema de alertas global si existe
        if (window.uiController && typeof window.uiController.showAlert === 'function') {
            window.uiController.showAlert(message, type);
        } else {
            // Fallback a alerta nativa
            alert(`${type.toUpperCase()}: ${message}`);
        }
    }
}

// Funciones globales para los botones HTML
function sendMessage() {
    if (window.chatManager) {
        window.chatManager.sendMessage();
    } else {
        console.error('ChatManager no está inicializado');
    }
}

function clearChat() {
    if (window.chatManager) {
        window.chatManager.clearChat();
    }
}

function exportChat() {
    if (window.chatManager) {
        window.chatManager.exportChat();
    }
}

function askQuestion(question) {
    const input = document.getElementById('messageInput');
    if (input && window.chatManager) {
        input.value = question;
        window.chatManager.sendMessage();
    }
}

function addQuickQuestion(question) {
    const input = document.getElementById('messageInput');
    if (input) {
        input.value = question;
        input.focus();
        // Auto-resize
        if (window.chatManager) {
            window.chatManager.autoResize();
        }
    }
}

// ✅ FUNCIÓN REQUERIDA POR EL HTML
function initChat() {
    if (!window.chatManager) {
        window.chatManager = new ChatManager();
        window.chatManager.init();
    }
    return window.chatManager;
}

// Inicializar el chat cuando se carga la página
document.addEventListener('DOMContentLoaded', () => {
    // Pequeño delay para asegurar que todo esté cargado
    setTimeout(() => {
        initChat();
        addChatStyles();
    }, 100);
});

// Añadir estilos para el chat
function addChatStyles() {
    if (document.getElementById('chat-styles')) return;
    
    const style = document.createElement('style');
    style.id = 'chat-styles';
    style.textContent = `
        .typing-indicator {
            display: inline-flex;
            align-items: center;
            height: 20px;
        }
        
        .typing-indicator span {
            display: inline-block;
            width: 6px;
            height: 6px;
            border-radius: 50%;
            background-color: #666;
            margin: 0 2px;
            animation: typing 1.4s infinite both;
        }
        
        .typing-indicator span:nth-child(2) {
            animation-delay: 0.2s;
        }
        
        .typing-indicator span:nth-child(3) {
            animation-delay: 0.4s;
        }
        
        @keyframes typing {
            0%, 60%, 100% {
                transform: translateY(0);
            }
            30% {
                transform: translateY(-5px);
            }
        }
        
        .highlight-price {
            font-weight: 700;
            color: #1a237e;
            background: rgba(26, 35, 126, 0.1);
            padding: 2px 4px;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
        }
        
        .highlight-percent {
            font-weight: 700;
            padding: 2px 4px;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
        }
        
        .highlight-percent.positive {
            color: #2ecc71;
            background: rgba(46, 204, 113, 0.1);
        }
        
        .highlight-percent.negative {
            color: #e74c3c;
            background: rgba(231, 76, 60, 0.1);
        }
        
        .highlight-symbol {
            font-weight: 700;
            color: #3949ab;
            background: rgba(57, 73, 171, 0.1);
            padding: 2px 4px;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
        }
        
        .message-text ul {
            margin: 8px 0;
            padding-left: 20px;
        }
        
        .message-text li {
            margin: 4px 0;
            line-height: 1.5;
        }
        
        .message-text strong {
            color: #1a237e;
            font-weight: 700;
        }
        
        .message-text em {
            font-style: italic;
            color: #555;
        }
    `;
    document.head.appendChild(style);
}
