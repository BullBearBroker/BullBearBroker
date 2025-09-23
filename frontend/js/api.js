class APIService {
    constructor() {
        const computedBase = typeof window.buildApiUrl === 'function'
            ? window.buildApiUrl('')
            : (window.APP_CONFIG?.API_BASE_URL || 'http://localhost:8000/api');

        this.baseURL = computedBase.replace(/\/$/, '');
    }

    buildUrl(endpoint = '') {
        const normalisedEndpoint = endpoint ? `/${endpoint.replace(/^\/+/, '')}` : '';
        return `${this.baseURL}${normalisedEndpoint}`;
    }

    getAuthToken() {
        if (typeof window === 'undefined') {
            return null;
        }

        try {
            return localStorage.getItem('bb_token');
        } catch (error) {
            console.warn('Unable to access auth token from storage:', error);
            return null;
        }
    }

    async request(endpoint, options = {}) {
        const headers = {
            'Content-Type': 'application/json',
            ...options.headers
        };

        const token = this.getAuthToken();
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        try {
            const response = await fetch(this.buildUrl(endpoint), {
                ...options,
                headers
            });

            if (!response.ok) {
                let errorPayload = null;
                try {
                    errorPayload = await response.json();
                } catch (jsonError) {
                    errorPayload = null;
                }

                const message = errorPayload?.detail
                    || (Array.isArray(errorPayload?.errors)
                        ? errorPayload.errors.map(err => err.msg || err.detail).join(' ')
                        : null)
                    || `HTTP error! status: ${response.status}`;

                const error = new Error(message);
                error.status = response.status;
                error.payload = errorPayload;
                throw error;
            }

            return await response.json();
        } catch (error) {
            console.error('API request failed:', error);
            throw error;
        }
    }

    async getMarketData() {
        try {
            const response = await this.request('market/top-performers');
            return response.data;
        } catch (error) {
            console.log('Using simulated market data');
            return null;
        }
    }

    async getPrice(symbol) {
        try {
            const response = await this.request(`market/price/${symbol}`);
            return response.data;
        } catch (error) {
            console.log(`Price not available for ${symbol}`);
            return null;
        }
    }

    async listAlerts() {
        return await this.request('alerts');
    }

    async createAlert(payload) {
        return await this.request('alerts', {
            method: 'POST',
            body: JSON.stringify(payload)
        });
    }

    async sendChatMessage(message) {
        try {
            const response = await this.request('chat/message', {
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
