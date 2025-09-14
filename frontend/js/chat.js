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

        // Simular respuesta de la IA
        setTimeout(() => {
            const response = this.generateAIResponse(message);
            this.addMessage(response, 'ai');
        }, 1000 + Math.random() * 1000);
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
        
        const responses = {
            'bitcoin': 'Bitcoin está mostrando fortaleza en el corto plazo. El soporte clave está en $40,000 y la resistencia en $45,000. El volumen de trading ha aumentado un 15% en las últimas 24 horas.',
            'ethereum': 'Ethereum se mantiene estable alrededor de $2,500. El upcoming merge podría impulsar el precio significativamente. Technical analysis muestra un patrón alcista en formación.',
            'tesla': 'TSLA cerró con una caída del 0.8% hoy. Las expectativas de ganancias para el próximo trimestre son positivas. El consensus de analistas es "Buy" con target price de $300.',
            'acciones': 'Basado en el análisis actual, recomiendo diversificar en: tecnología (AAPL, MSFT), energía renovable (ENPH), y healthcare (JNJ). Considera un 60% stocks, 20% crypto, 20% cash.',
            'mercado': 'Los mercados globales muestran mixed signals hoy. El S&P 500 +0.3%, NASDAQ +0.8%, DOW -0.2%. Recomiendo cautela y dollar-cost averaging en posiciones largas.',
            'estrategia': 'Para perfiles conservadores: 40% bonds, 40% blue chips, 20% gold. Para agresivos: 50% growth stocks, 30% crypto, 20% emerging markets. Rebalancear trimestralmente.'
        };

        for (const [keyword, response] of Object.entries(responses)) {
            if (lowerMessage.includes(keyword)) {
                return response;
            }
        }

        return `He analizado tu consulta sobre "${userMessage}". Como asistente financiero, recomiendo considerar el horizonte temporal de inversión y diversificar across diferentes asset classes. ¿Te gustaría que profundice en algún aspecto específico?`;
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