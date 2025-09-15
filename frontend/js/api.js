class APIService {
    constructor() {
        this.baseURL = 'http://localhost:8000';
    }

    async request(endpoint, options = {}) {
        try {
            const response = await fetch(`${this.baseURL}${endpoint}`, {
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers
                },
                ...options
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('API request failed:', error);
            throw error;
        }
    }

    async getMarketData() {
        try {
            const response = await this.request('/api/market/top-performers');
            return response.data;
        } catch (error) {
            console.log('Using simulated market data');
            return null;
        }
    }

    async getPrice(symbol) {
        try {
            const response = await this.request(`/api/market/price/${symbol}`);
            return response.data;
        } catch (error) {
            console.log(`Price not available for ${symbol}`);
            return null;
        }
    }

    async sendChatMessage(message) {
        try {
            const response = await this.request('/api/chat/message', {
                method: 'POST',
                body: JSON.stringify({ message })
            });
            return response.response;
        } catch (error) {
            console.log('Using local AI response');
            return null;
        }
    }
}

// Exportar instancia global
const apiService = new APIService();