class ChatManager {
    constructor() {
        this.messages = [];
        this.init();
    }

    init() {
        this.loadFromLocalStorage();
        this.setupEventListeners();
        this.renderMessages();
    }

    setupEventListeners() {
        const input = document.getElementById('messageInput');
        
        input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        input.addEventListener('input', this.autoResize.bind(this));
    }

    autoResize() {
        const textarea = document.getElementById('messageInput');
        textarea.style.height = 'auto';
        textarea.style.height = Math.min(textarea.scrollHeight, 150) + 'px';
    }

    async sendMessage() {
        const input = document.getElementById('messageInput');
        const message = input.value.trim();

        if (!message) return;

        this.addMessage(message, 'user');
        input.value = '';
        this.autoResize();

        try {
            // Intentar obtener respuesta del backend
            const response = await this.fetchAIResponse(message);
            this.addMessage(response, 'ai');
        } catch (error) {
            console.log('Using local AI response:', error);
            // Fallback a respuesta local
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
                throw new Error('API response not OK');
            }

            const data = await response.json();
            return data.response;
        } catch (error) {
            throw new Error('Failed to fetch AI response');
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
        container.innerHTML = '';

        this.messages.forEach(message => {
            this.renderMessage(message);
        });

        this.scrollToBottom();
    }

    renderMessage(message) {
        const container = document.getElementById('chatMessages');
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${message.sender}-message`;

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
        // Convertir URLs en links
        return text.replace(
            /(https?:\/\/[^\s]+)/g, 
            '<a href="$1" target="_blank" style="color: #1a237e; text-decoration: underline;">$1</a>'
        );
    }

    formatTime(timestamp) {
        return new Date(timestamp).toLocaleTimeString('es-ES', {
            hour: '2-digit',
            minute: '2-digit'
        });
    }

    scrollToBottom() {
        const container = document.getElementById('chatMessages');
        container.scrollTop = container.scrollHeight;
    }

    generateAIResponse(userMessage) {
        const lowerMessage = userMessage.toLowerCase();
        
        // Patrones para detectar consultas de precio
        const pricePatterns = [
            /precio de (\w+)/i,
            /valor de (\w+)/i,
            /cuánto vale (\w+)/i,
            /price of (\w+)/i,
            /cotización de (\w+)/i
        ];
    
        // Verificar si es consulta de precio
        for (const pattern of pricePatterns) {
            const match = userMessage.match(pattern);
            if (match) {
                const symbol = match[1].toUpperCase();
                const priceInfo = marketData.getPrice(symbol);
                
                if (priceInfo) {
                    return `El precio actual de ${symbol} es ${priceInfo.price} (${priceInfo.change} en 24h).`;
                } else {
                    return `No tengo información del precio de ${symbol} en este momento. ¿Podrías verificar el símbolo?`;
                }
            }
        }
    
        // Respuestas predefinidas
        const responses = {
            'bitcoin': '📈 Bitcoin está mostrando fortaleza. Soporte en $40K, resistencia en $45K. Volumen +15% en 24h. Recomendación: acumular en dips.',
            'ethereum': '🔷 Ethereum consolidando en $2,500. El merge próximamente podría impulsar el precio. Technicals muestran patrón alcista.',
            'acciones': '💼 Recomiendo diversificar: Tech (AAPL, MSFT), Renewable Energy (ENPH), Healthcare (JNJ). Allocation sugerida: 60% stocks, 20% crypto, 20% cash.',
            'estrategia': '🎯 Estrategias: Conservadora (40% bonds, 40% blue chips, 20% gold). Agresiva (50% growth stocks, 30% crypto, 20% emerging markets). Rebalancear trimestralmente.',
            'mercado': '🌍 Mercados globales: S&P 500 +0.3%, NASDAQ +0.8%, DOW -0.2%. Recomiendo dollar-cost averaging y diversificación.',
            'forex': '💱 Forex: EUR/USD 1.0850, GBP/USD 1.2450, USD/JPY 150.20. Atención a reuniones del Fed para cambios en tasas.'
        };
    
        for (const [keyword, response] of Object.entries(responses)) {
            if (lowerMessage.includes(keyword)) {
                return response;
            }
        }
    
        return `He analizado tu consulta sobre "${userMessage}". Como asistente financiero, recomiendo: 
        
1. 📊 Diversificar across asset classes
2. ⏰ Considerar horizonte temporal de inversión  
3. 📉 Mantener cash para oportunidades de mercado
4. 🔍 Hacer due diligence antes de cada inversión

¿Te gustaría que profundice en algún aspecto específico?`;
    }
    
    saveToLocalStorage() {
        localStorage.setItem('chatMessages', JSON.stringify(this.messages));
    }
    
    loadFromLocalStorage() {
        const saved = localStorage.getItem('chatMessages');
        if (saved) {
            this.messages = JSON.parse(saved);
        }
    }
    
    clearChat() {
        if (confirm('¿Estás seguro de que quieres limpiar toda la conversación?')) {
            this.messages = [];
            localStorage.removeItem('chatMessages');
            this.renderMessages();
            
            // Mensaje inicial del bot
            this.addMessage('¡Hola! Conversación reiniciada. ¿En qué puedo ayudarte con los mercados financieros hoy?', 'ai');
        }
    }
    
    exportChat() {
        const chatText = this.messages.map(msg => 
            `${msg.sender === 'user' ? 'Tú' : 'AI'} (${this.formatTime(msg.timestamp)}): ${msg.text}`
        ).join('\n\n');
    
        const blob = new Blob([chatText], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `bullbearbroker-chat-${new Date().toISOString().split('T')[0]}.txt`;
        a.click();
        URL.revokeObjectURL(url);
    }
}

// Funciones globales para los botones HTML
function sendMessage() {
    chatManager.sendMessage();
}

function clearChat() {
    chatManager.clearChat();
}

function exportChat() {
    chatManager.exportChat();
}

function askQuestion(question) {
    document.getElementById('messageInput').value = question;
    chatManager.sendMessage();
}

function addQuickQuestion(question) {
    document.getElementById('messageInput').value = question;
}

// Inicializar el chat cuando se carga la página
let chatManager;

document.addEventListener('DOMContentLoaded', () => {
    chatManager = new ChatManager();
});