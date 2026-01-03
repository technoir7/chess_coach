// API client for backend communication

const API_BASE = 'http://localhost:8000/api';

class ChessAPI {
    constructor() {
        this.gameId = null;
    }

    async createGame() {
        const response = await fetch(`${API_BASE}/game/new`, {
            method: 'POST'
        });
        const data = await response.json();
        this.gameId = data.game_id;
        return data;
    }

    async getGameState() {
        if (!this.gameId) throw new Error('No active game');

        const response = await fetch(`${API_BASE}/game/${this.gameId}`);
        return await response.json();
    }

    async getModels() {
        const response = await fetch(`${API_BASE}/models`);
        return await response.json();
    }

    async makeMove(move) {
        if (!this.gameId) throw new Error('No active game');

        const response = await fetch(`${API_BASE}/game/${this.gameId}/move`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ move })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Move failed');
        }

        return await response.json();
    }

    async explainPosition() {
        if (!this.gameId) throw new Error('No active game');

        const response = await fetch(`${API_BASE}/game/${this.gameId}/explain`);
        return await response.json();
    }

    async sendChat(message) {
        if (!this.gameId) throw new Error('No active game');

        const response = await fetch(`${API_BASE}/game/${this.gameId}/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ message })
        });
        return await response.json();
    }

    async updateSettings(difficulty, style, model) {
        if (!this.gameId) throw new Error('No active game');

        const response = await fetch(`${API_BASE}/game/${this.gameId}/settings`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ difficulty, style, model })
        });
        return await response.json();
    }

    downloadGame() {
        if (!this.gameId) throw new Error('No active game');
        // Trigger download in new tab
        window.open(`${API_BASE}/game/${this.gameId}/export`, '_blank');
    }

    async resign() {
        if (!this.gameId) throw new Error('No active game');
        const response = await fetch(`${API_BASE}/game/${this.gameId}/resign`, {
            method: 'POST'
        });
        return await response.json();
    }

    async offerDraw() {
        if (!this.gameId) throw new Error('No active game');
        const response = await fetch(`${API_BASE}/game/${this.gameId}/draw/offer`, {
            method: 'POST'
        });
        return await response.json();
    }
}

// Export for use in app.js
window.ChessAPI = ChessAPI;
