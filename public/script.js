class RouletteGame {
    constructor() {
        this.socket = io();
        this.token = localStorage.getItem('token');
        this.user = null;
        this.selectedColor = null;
        this.gameState = {};
        
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.checkAuth();
    }

    checkAuth() {
        if (this.token) {
            this.verifyToken();
        } else {
            this.showAuthScreen();
        }
    }

    async verifyToken() {
        try {
            const response = await fetch('/api/profile', {
                headers: {
                    'Authorization': `Bearer ${this.token}`
                }
            });

            if (response.ok) {
                const data = await response.json();
                this.user = data.user;
                this.showGameScreen();
            } else {
                localStorage.removeItem('token');
                this.showAuthScreen();
            }
        } catch (error) {
            console.error('Ошибка проверки токена:', error);
            this.showAuthScreen();
        }
    }

    setupEventListeners() {
        // Auth form handlers
        document.getElementById('loginForm').addEventListener('submit', (e) => {
            e.preventDefault();
            this.handleLogin();
        });

        document.getElementById('registerForm').addEventListener('submit', (e) => {
            e.preventDefault();
            this.handleRegister();
        });

        // Game handlers
        document.querySelectorAll('.bet-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                this.selectColor(btn.dataset.color);
            });
        });

        document.getElementById('placeBetBtn').addEventListener('click', () => {
            this.placeBet();
        });

        document.getElementById('betAmount').addEventListener('input', () => {
            this.updateBetButton();
        });

        document.getElementById('profileBtn').addEventListener('click', () => {
            this.showProfile();
        });

        document.getElementById('logoutBtn').addEventListener('click', () => {
            this.logout();
        });

        // Modal handlers
        document.querySelector('.close').addEventListener('click', () => {
            document.getElementById('profileModal').style.display = 'none';
        });

        window.addEventListener('click', (e) => {
            const modal = document.getElementById('profileModal');
            if (e.target === modal) {
                modal.style.display = 'none';
            }
        });

        // Socket event listeners
        this.setupSocketListeners();
    }

    setupSocketListeners() {
        this.socket.on('gameState', (state) => {
            this.gameState = state;
            this.updateGameUI();
        });

        this.socket.on('timeUpdate', (timeLeft) => {
            document.getElementById('timeLeft').textContent = timeLeft;
            
            if (timeLeft <= 5 && this.gameState.phase === 'betting') {
                document.getElementById('timeLeft').style.color = '#ff4444';
            } else {
                document.getElementById('timeLeft').style.color = '#ffd700';
            }
        });

        this.socket.on('spinStart', () => {
            this.startRouletteAnimation();
        });

        this.socket.on('spinResult', (result) => {
            this.showResult(result);
            this.loadGameHistory();
        });

        this.socket.on('newBet', (bet) => {
            this.addBetToList(bet);
        });

        this.socket.on('balanceUpdate', (newBalance) => {
            this.user.balance = newBalance;
            this.updateBalance();
        });

        this.socket.on('betsResult', (data) => {
            this.processBetsResult(data);
        });

        this.socket.on('error', (message) => {
            this.showError(message);
        });
    }

    // Auth methods
    switchTab(tab) {
        document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
        document.querySelectorAll('.auth-form').forEach(form => form.classList.remove('active'));
        
        document.querySelector(`[onclick="switchTab('${tab}')"]`).classList.add('active');
        document.getElementById(`${tab}Form`).classList.add('active');
        
        document.getElementById('authError').textContent = '';
    }

    async handleLogin() {
        const username = document.getElementById('loginUsername').value;
        const password = document.getElementById('loginPassword').value;

        try {
            const response = await fetch('/api/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ username, password })
            });

            const data = await response.json();

            if (response.ok) {
                this.token = data.token;
                this.user = data.user;
                localStorage.setItem('token', this.token);
                this.showGameScreen();
            } else {
                this.showAuthError(data.error);
            }
        } catch (error) {
            this.showAuthError('Ошибка соединения с сервером');
        }
    }

    async handleRegister() {
        const username = document.getElementById('registerUsername').value;
        const password = document.getElementById('registerPassword').value;

        try {
            const response = await fetch('/api/register', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ username, password })
            });

            const data = await response.json();

            if (response.ok) {
                this.token = data.token;
                this.user = data.user;
                localStorage.setItem('token', this.token);
                this.showGameScreen();
            } else {
                this.showAuthError(data.error);
            }
        } catch (error) {
            this.showAuthError('Ошибка соединения с сервером');
        }
    }

    showAuthError(message) {
        document.getElementById('authError').textContent = message;
    }

    // Screen management
    showAuthScreen() {
        document.getElementById('authScreen').classList.remove('hidden');
        document.getElementById('gameScreen').classList.add('hidden');
    }

    showGameScreen() {
        document.getElementById('authScreen').classList.add('hidden');
        document.getElementById('gameScreen').classList.remove('hidden');
        
        this.updateUserInfo();
        this.loadGameHistory();
    }

    updateUserInfo() {
        document.getElementById('username').textContent = this.user.username;
        this.updateBalance();
    }

    updateBalance() {
        document.getElementById('balance').textContent = this.user.balance;
        document.getElementById('profileBalance').textContent = this.user.balance;
    }

    // Game methods
    updateGameUI() {
        const timerText = document.getElementById('timerText');
        const placeBetBtn = document.getElementById('placeBetBtn');

        switch (this.gameState.phase) {
            case 'betting':
                timerText.textContent = 'Ставки: ';
                placeBetBtn.disabled = false;
                break;
            case 'spinning':
                timerText.textContent = 'Вращение: ';
                placeBetBtn.disabled = true;
                this.selectedColor = null;
                this.updateColorSelection();
                break;
            case 'result':
                timerText.textContent = 'Результат';
                placeBetBtn.disabled = true;
                break;
        }

        this.updateBetButton();
      selectColor(color) {
        if (this.gameState.phase !== 'betting') return;
        
        this.selectedColor = color;
        this.updateColorSelection();
        this.updateBetButton();
    }

    updateColorSelection() {
        document.querySelectorAll('.bet-btn').forEach(btn => {
            btn.classList.remove('selected');
        });

        if (this.selectedColor) {
            document.querySelector(`[data-color="${this.selectedColor}"]`).classList.add('selected');
        }
    }

    updateBetButton() {
        const betAmount = parseInt(document.getElementById('betAmount').value);
        const placeBetBtn = document.getElementById('placeBetBtn');

        const canBet = this.selectedColor && 
                      betAmount > 0 && 
                      betAmount <= this.user.balance && 
                      this.gameState.phase === 'betting';

        placeBetBtn.disabled = !canBet;
    }

    placeBet() {
        const betAmount = parseInt(document.getElementById('betAmount').value);
        
        if (!this.selectedColor || betAmount <= 0 || betAmount > this.user.balance) {
            this.showError('Неверная ставка');
            return;
        }

        this.socket.emit('placeBet', {
            token: this.token,
            color: this.selectedColor,
            amount: betAmount
        });

        // Очистка формы
        document.getElementById('betAmount').value = '';
        this.selectedColor = null;
        this.updateColorSelection();
        this.updateBetButton();
    }

    startRouletteAnimation() {
        const wheel = document.getElementById('rouletteWheel');
        wheel.classList.add('spinning');
        
        // Генерируем случайное количество оборотов
        const spins = 5 + Math.random() * 5; // 5-10 оборотов
        const finalRotation = spins * 360;
        
        setTimeout(() => {
            wheel.classList.remove('spinning');
            wheel.style.transform = `rotate(${finalRotation}deg)`;
        }, 100);
    }

    showResult(result) {
        const wheel = document.getElementById('rouletteWheel');
        
        // Определяем финальный угол для результата
        const colorAngles = {
            'green': 348, // Зеленый сектор
            'red': [12, 36, 60, 84, 108, 132, 156, 180, 204, 228, 252, 276, 300, 324], // Красные секторы
            'black': [24, 48, 72, 96, 120, 144, 168, 192, 216, 240, 264, 288, 312, 336] // Черные секторы
        };

        let targetAngle;
        if (result === 'green') {
            targetAngle = colorAngles.green;
        } else {
            const angles = colorAngles[result];
            targetAngle = angles[Math.floor(Math.random() * angles.length)];
        }

        // Добавляем дополнительные обороты для эффектности
        const extraSpins = 5 * 360;
        const finalAngle = extraSpins + targetAngle;

        wheel.style.transition = 'transform 4s cubic-bezier(0.23, 1, 0.32, 1)';
        wheel.style.transform = `rotate(${finalAngle}deg)`;

        // Показываем результат
        setTimeout(() => {
            this.displayResult(result);
        }, 4000);
    }

    displayResult(result) {
        // Создаем элемент для отображения результата
        const resultElement = document.createElement('div');
        resultElement.className = `result-announcement ${result}`;
        resultElement.innerHTML = `
            <div class="result-content">
                <div class="result-color ${result}"></div>
                <h2>Выпало: ${this.getColorName(result)}!</h2>
            </div>
        `;
        
        document.body.appendChild(resultElement);
        
        setTimeout(() => {
            resultElement.remove();
        }, 3000);
    }

    getColorName(color) {
        const names = {
            'red': 'Красное',
            'black': 'Черное',
            'green': 'Зеленое'
        };
        return names[color];
    }

    processBetsResult(data) {
        const { result, bets } = data;
        
        // Обновляем баланс пользователя
        this.loadUserProfile();
        
        // Показываем результаты ставок
        bets.forEach(bet => {
            if (bet.userId === this.user.id) {
                const won = bet.color === result;
                const message = won ? 
                    `Вы выиграли ${bet.amount * this.getMultiplier(bet.color)}!` :
                    `Вы проиграли ${bet.amount}`;
                
                this.showNotification(message, won ? 'success' : 'error');
            }
        });
    }

    getMultiplier(color) {
        const multipliers = { red: 2, black: 2, green: 14 };
        return multipliers[color];
    }

    addBetToList(bet) {
        const betsList = document.getElementById('currentBets');
        const betElement = document.createElement('div');
        betElement.className = 'bet-item fade-in';
        betElement.innerHTML = `
            <div class="bet-username">${bet.username}</div>
            <div>
                <span class="result-color ${bet.color}"></span>
                ${this.getColorName(bet.color)} - ${bet.amount}
            </div>
        `;
        
        betsList.insertBefore(betElement, betsList.firstChild);
        
        // Ограничиваем количество отображаемых ставок
        while (betsList.children.length > 10) {
            betsList.removeChild(betsList.lastChild);
        }
    }

    async loadGameHistory() {
        try {
            const response = await fetch('/api/history');
            const games = await response.json();
            
            const historyList = document.getElementById('gameHistory');
            historyList.innerHTML = '';
            
            games.forEach(game => {
                const historyItem = document.createElement('div');
                historyItem.className = 'history-item';
                historyItem.innerHTML = `
                    <div>
                        <span class="result-color ${game.result}"></span>
                        ${this.getColorName(game.result)}
                    </div>
                    <div class="game-time">${new Date(game.timestamp).toLocaleTimeString()}</div>
                `;
                historyList.appendChild(historyItem);
            });
        } catch (error) {
            console.error('Ошибка загрузки истории:', error);
        }
    }

    async loadUserProfile() {
        try {
            const response = await fetch('/api/profile', {
                headers: {
                    'Authorization': `Bearer ${this.token}`
                }
            });
            
            if (response.ok) {
                const data = await response.json();
                this.user = data.user;
                this.updateBalance();
                this.displayUserBets(data.bets);
            }
        } catch (error) {
            console.error('Ошибка загрузки профиля:', error);
        }
    }

    displayUserBets(bets) {
        const betsList = document.getElementById('userBets');
        betsList.innerHTML = '';
        
        if (bets.length === 0) {
            betsList.innerHTML = '<p>У вас пока нет ставок</p>';
            return;
        }
        
        bets.forEach(bet => {
            const betItem = document.createElement('div');
            betItem.className = 'user-bet-item';
            
            const resultClass = bet.won ? 'won' : 'lost';
            const resultText = bet.won ? `+${bet.winnings}` : `-${bet.amount}`;
            
            betItem.innerHTML = `
                <div class="bet-details">
                    <span class="result-color ${bet.color}"></span>
                    <div>
                        <div>${this.getColorName(bet.color)} - ${bet.amount}</div>
                        <div class="bet-time">${new Date(bet.game_time).toLocaleString()}</div>
                    </div>
                </div>
                <div class="bet-result ${resultClass}">
                    ${resultText}
                </div>
            `;
            
            betsList.appendChild(betItem);
        });
    }

    showProfile() {
        this.loadUserProfile();
        document.getElementById('profileModal').style.display = 'block';
    }

    logout() {
        localStorage.removeItem('token');
        this.token = null;
        this.user = null;
        this.socket.disconnect();
        this.socket.connect();
        this.showAuthScreen();
    }

    showError(message) {
        this.showNotification(message, 'error');
    }

    showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.textContent = message;
        
        // Добавляем стили для уведомлений
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 1rem 2rem;
            border-radius: 10px;
            color: white;
            font-weight: bold;
            z-index: 1001;
            animation: slideIn 0.3s ease-out;
            max-width: 300px;
        `;
        
        switch (type) {
            case 'success':
                notification.style.background = '#4caf50';
                break;
            case 'error':
                notification.style.background = '#f44336';
                break;
            default:
                notification.style.background = '#2196f3';
        }
        
        document.body.appendChild(notification);
        
        setTimeout(() => {
            notification.style.animation = 'slideOut 0.3s ease-in';
            setTimeout(() => {
                notification.remove();
            }, 300);
        }, 3000);
    }
}

// Глобальные функции для HTML
function switchTab(tab) {
    game.switchTab(tab);
}

// Добавляем CSS для анимаций уведомлений
const notificationStyles = document.createElement('style');
notificationStyles.textContent = `
    @keyframes slideIn {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
    
    @keyframes slideOut {
        from { transform: translateX(0); opacity: 1; }
        to { transform: translateX(100%); opacity: 0; }
    }
    
    .result-announcement {
        position: fixed;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        z-index: 1002;
        background: rgba(0, 0, 0, 0.9);
        padding: 2rem;
        border-radius: 20px;
        text-align: center;
        animation: fadeIn 0.5s ease-out;
    }
    
    .result-announcement .result-color {
        width: 60px;
        height: 60px;
        border-radius: 50%;
        margin: 0 auto 1rem;
    }
    
    .result-announcement h2 {
        color: white;
        font-size: 2rem;
        margin: 0;
    }
    
    @media (max-width: 480px) {
        .result-announcement {
            padding: 1.5rem;
            margin: 1rem;
        }
        
        .result-announcement h2 {
            font-size: 1.5rem;
        }
        
        .result-announcement .result-color {
            width: 40px;
            height: 40px;
        }
    }
`;
document.head.appendChild(notificationStyles);

// Инициализация игры
let game;
document.addEventListener('DOMContentLoaded', () => {
    game = new RouletteGame();
});
                                                               }
