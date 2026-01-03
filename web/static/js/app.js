// Main application controller

class ChessCoachApp {
    constructor() {
        this.api = new ChessAPI();
        this.board = null;
        this.game = new Chess();
        this.moveHistory = [];

        this.init();
    }

    async init() {
        try {
            // Load available models first
            await this.loadModels();

            // Create new game
            this.showStatus('Starting new game...', 'success');
            const gameState = await this.api.createGame();

            // Initialize board
            this.initBoard();

            this.showStatus('Game ready!', 'success');
        } catch (error) {
            this.showStatus(`Error: ${error.message}`, 'error');
        }
    }

    async resetGame() {
        if (!confirm('Are you sure you want to start a new game? Current progress will be lost.')) return;

        try {
            const gameState = await this.api.createGame();
            this.game = new Chess();
            this.moveHistory = [];
            this.board.position('start');
            document.getElementById('game-log').innerHTML = '';
            document.getElementById('position-theme').textContent = 'Opening development';
            this.showStatus('New game started!', 'success');
        } catch (error) {
            this.showStatus(`Error starting new game: ${error.message}`, 'error');
        }
    }

    async loadModels() {
        try {
            const models = await this.api.getModels();
            const select = document.getElementById('model-select');
            select.innerHTML = ''; // Clear existing

            // Google Models
            if (models.google && models.google.length > 0) {
                const group = document.createElement('optgroup');
                group.label = 'Google Gemini';
                models.google.forEach(model => {
                    const option = document.createElement('option');
                    option.value = model;
                    option.textContent = model;
                    // Auto-select a good default
                    if (model === 'gemini-2.5-flash') option.selected = true;
                    group.appendChild(option);
                });
                select.appendChild(group);
            }

            // Ollama Models
            if (models.ollama && models.ollama.length > 0) {
                const group = document.createElement('optgroup');
                group.label = 'Local (Ollama)';
                models.ollama.forEach(model => {
                    const option = document.createElement('option');
                    option.value = model;
                    option.textContent = model;
                    group.appendChild(option);
                });
                select.appendChild(group);
            }
        } catch (error) {
            console.error('Failed to load models:', error);
            this.showStatus('Failed to load LLM list', 'error');
        }
    }

    initBoard() {
        const config = {
            draggable: true,
            position: 'start',
            onDragStart: this.onDragStart.bind(this),
            onDrop: this.onDrop.bind(this),
            pieceTheme: 'https://chessboardjs.com/img/chesspieces/wikipedia/{piece}.png'
        };

        this.board = Chessboard('board', config);
        window.addEventListener('resize', () => this.board.resize());
    }

    onDragStart(source, piece) {
        // Only allow dragging own pieces (White)
        if (this.game.game_over()) return false;
        if (piece.search(/^b/) !== -1) return false; // Don't drag black pieces
    }

    async onDrop(source, target) {
        // Check if move is legal on client side first
        const move = this.game.move({
            from: source,
            to: target,
            promotion: 'q' // Temporary client-side promotion
        });

        // Illegal move
        if (move === null) return 'snapback';

        try {
            // Construct UCI move string
            let uciMove = source + target;

            // Check for promotion to append 'q' (backend expectation)
            // piece is e.g. 'wP' or 'bP'
            const piece = this.game.get(target);
            // Note: after .move(), the piece is at target
            if (piece && piece.type === 'p') {
                if ((piece.color === 'w' && target[1] === '8') ||
                    (piece.color === 'b' && target[1] === '1')) {
                    uciMove += 'q';
                }
            }

            // Make the move via API
            const state = await this.api.makeMove(uciMove);

            // Update move history
            this.updateMoveHistory(move.san);

            // Show opponent's move
            if (state.opponent_move) {
                setTimeout(() => {
                    const oppMove = this.game.move({
                        from: state.opponent_move.substring(0, 2),
                        to: state.opponent_move.substring(2, 4),
                        promotion: state.opponent_move.length === 5 ? state.opponent_move[4] : undefined
                    });

                    this.board.position(this.game.fen());
                    this.updateMoveHistory(oppMove.san);

                    this.showStatus('Opponent played: ' + oppMove.san, 'success');

                    // Check game over after opponent move
                    if (this.game.game_over()) {
                        alert(`Game Over! Result: ${state.result || 'Draw'}`);
                    }
                }, 300);
            }

            // Show coach advice if available
            if (state.advice) {
                this.showCoachMessage(state.advice);
            }

            // Update position theme
            this.updatePositionTheme(state.position_theme);

            // Check game over (after my move)
            if (state.game_over) {
                // Use alert for visibility
                setTimeout(() => {
                    alert(`Game Over! Result: ${state.result}`);
                }, 100);
            }

        } catch (error) {
            this.showStatus(`Error: ${error.message}`, 'error');
            this.game.undo();
            return 'snapback';
        }
    }

    updatePositionTheme(theme) {
        if (theme) {
            document.getElementById('position-theme').textContent = theme;
        }
    }

    updateMoveHistory(san) {
        this.moveHistory.push(san);
        this.renderMoveHistory();
    }

    renderMoveHistory() {
        const gameLog = document.getElementById('game-log');
        const totalMovesInHistory = this.moveHistory.length;

        if (totalMovesInHistory === 0) {
            gameLog.innerHTML = ''; // Clear if no moves
            return;
        }

        const isWhiteMove = totalMovesInHistory % 2 !== 0;
        const currentMoveNumber = Math.ceil(totalMovesInHistory / 2);

        let targetMoveEntry;

        if (isWhiteMove) {
            // White just moved, create a new move-entry div
            const div = document.createElement('div');
            div.className = 'move-entry';
            div.id = `move-${currentMoveNumber}`;

            const whiteMove = this.moveHistory[totalMovesInHistory - 1];
            const blackMove = ''; // Black's move is not yet made

            div.innerHTML = `
                <div class="move-header">
                    <span class="move-number">${currentMoveNumber}.</span>
                    <span class="move-san white-move">${whiteMove}</span>
                    <span class="move-san black-move">${blackMove}</span>
                </div>
                <div class="analysis-container" id="analysis-${currentMoveNumber}"></div>
            `;
            gameLog.appendChild(div);
            targetMoveEntry = div;
        } else {
            // Black just moved, update the last move-entry div
            targetMoveEntry = document.getElementById(`move-${currentMoveNumber}`);
            if (targetMoveEntry) {
                const blackMoveSpan = targetMoveEntry.querySelector('.black-move');
                if (blackMoveSpan) {
                    blackMoveSpan.textContent = this.moveHistory[totalMovesInHistory - 1];
                }
            }
        }

        // Scroll to bottom
        gameLog.scrollTop = gameLog.scrollHeight;
    }

    addAnalysis(text, type = 'normal') {
        const gameLog = document.getElementById('game-log');

        // Find the last move to append analysis to
        const moves = gameLog.getElementsByClassName('move-entry');
        let targetContainer;

        if (moves.length > 0) {
            const lastMove = moves[moves.length - 1];
            targetContainer = lastMove.querySelector('.analysis-container');
        } else {
            // No moves yet? Append to main log (e.g. welcome message area)
            targetContainer = gameLog;
        }

        const div = document.createElement('div');
        div.className = `analysis-content ${type === 'coach' ? 'highlight' : ''}`;
        div.innerHTML = text.replace(/\n/g, '<br>'); // Simple formatting
        targetContainer.appendChild(div);

        gameLog.scrollTop = gameLog.scrollHeight;
    }

    async handleSettingsChange() {
        const difficulty = document.getElementById('difficulty-select').value;
        const style = document.getElementById('style-select').value;
        const model = document.getElementById('model-select').value;

        try {
            await this.api.updateSettings(difficulty, style, model);
            this.showStatus(`Settings updated: ${difficulty} / ${style} / ${model}`, 'success');
        } catch (error) {
            this.showStatus(`Error updating settings: ${error.message}`, 'error');
        }
    }

    async handleExplainClick() {
        const btn = document.getElementById('explain-btn');
        btn.disabled = true;

        this.addAnalysis('Analyzing position...', 'coach');

        try {
            const explanation = await this.api.explainPosition();
            // Remove "Analyzing..." text (simple approach: remove last child)
            this.removeLastAnalysis();
            this.addAnalysis(explanation.explanation, 'coach');
        } catch (error) {
            this.removeLastAnalysis();
            this.addAnalysis(`Error: ${error.message}`, 'error');
        } finally {
            btn.disabled = false;
        }
    }

    removeLastAnalysis() {
        const gameLog = document.getElementById('game-log');
        const moves = gameLog.getElementsByClassName('move-entry');
        if (moves.length > 0) {
            const lastMove = moves[moves.length - 1];
            const container = lastMove.querySelector('.analysis-container');
            if (container.lastChild) container.removeChild(container.lastChild);
        }
    }

    async handleSendChat() {
        const input = document.getElementById('chat-input');
        const message = input.value.trim();
        if (!message) return;

        input.value = '';
        this.addAnalysis(`<strong>You:</strong> ${message}`, 'user');
        this.addAnalysis('Thinking...', 'coach');

        try {
            const data = await this.api.sendChat(message);
            this.removeLastAnalysis(); // Remove "Thinking..."
            this.addAnalysis(data.response, 'coach');
        } catch (error) {
            this.removeLastAnalysis();
            this.addAnalysis(`Error: ${error.message}`, 'error');
        }
    }

    replaceLastLoadingMessage(text, sender) {
        const chatBox = document.getElementById('chat-box');
        const loadingMsgs = chatBox.getElementsByClassName('loading');
        if (loadingMsgs.length > 0) {
            const lastLoading = loadingMsgs[loadingMsgs.length - 1];
            lastLoading.textContent = text;
            lastLoading.classList.remove('loading');
        } else {
            this.addMessage(text, sender);
        }
        chatBox.scrollTop = chatBox.scrollHeight;
    }

    showCoachMessage(message) {
        this.addAnalysis(message, 'coach');
    }

    showStatus(message, type = 'success') {
        const existing = document.querySelector('.status-message');
        if (existing) existing.remove();

        const div = document.createElement('div');
        div.className = `status-message ${type}`;
        div.textContent = message;
        document.body.appendChild(div);

        setTimeout(() => div.remove(), 3000);
    }
}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.app = new ChessCoachApp();

    // Bind explain button
    document.getElementById('explain-btn').addEventListener('click', () => {
        window.app.handleExplainClick();
    });

    // Bind send chat button
    document.getElementById('send-chat-btn').addEventListener('click', () => {
        window.app.handleSendChat();
    });

    // Bind Enter key for chat
    document.getElementById('chat-input').addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            window.app.handleSendChat();
        }
    });

    // Bind settings changes
    document.getElementById('difficulty-select').addEventListener('change', () => {
        window.app.handleSettingsChange();
    });

    document.getElementById('style-select').addEventListener('change', () => {
        window.app.handleSettingsChange();
    });

    document.getElementById('model-select').addEventListener('change', () => {
        window.app.handleSettingsChange();
    });

    // Bind export button
    const exportBtn = document.getElementById('export-btn');
    if (exportBtn) {
        exportBtn.addEventListener('click', (e) => {
            e.preventDefault();
            try {
                window.app.api.downloadGame();
            } catch (error) {
                window.app.showStatus(`Error exporting game: ${error.message}`, 'error');
            }
        });
    }

    // Bind New Game button
    const newGameBtn = document.getElementById('new-game-btn');
    if (newGameBtn) {
        newGameBtn.addEventListener('click', (e) => {
            e.preventDefault();
            console.log("New Game Clicked");
            window.app.resetGame();
        });
    }

    // Bind Resign button
    const resignBtn = document.getElementById('resign-btn');
    if (resignBtn) {
        resignBtn.addEventListener('click', async (e) => {
            e.preventDefault();
            console.log("Resign Clicked");
            if (!confirm('Are you sure you want to resign?')) return;
            try {
                const state = await window.app.api.resign();
                alert(`Game Over! Result: ${state.result}`);
            } catch (error) {
                window.app.showStatus(`Error resigning: ${error.message}`, 'error');
                alert(`Error resigning: ${error.message}`);
            }
        });
    }

    // Bind Draw button
    const drawBtn = document.getElementById('draw-btn');
    if (drawBtn) {
        drawBtn.addEventListener('click', async (e) => {
            e.preventDefault();
            console.log("Draw Clicked");
            try {
                const result = await window.app.api.offerDraw();
                if (result.accepted) {
                    alert('Draw Accepted! Result: 1/2-1/2');
                } else {
                    alert('Draw Declined! The game continues.');
                }
            } catch (error) {
                window.app.showStatus(`Error offering draw: ${error.message}`, 'error');
                alert(`Error offering draw: ${error.message}`);
            }
        });
    }
});
